#!/usr/bin/env python3
"""Audit every reachable Git blob before public repository publication.

This complements Gitleaks. It inspects all branches and tags for risky names,
unapproved binary or archive material, copied dependency trees, key material,
and distribution-restriction markers. The JSON report is suitable for release
evidence and contains object IDs and paths, but never prints matching secret
content.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

AUDIT_FORMAT = "signalchord-history-audit/v1"
MAX_TEXT_SCAN_BYTES = 4 * 1024 * 1024
MAX_REVIEW_BLOB_BYTES = 10 * 1024 * 1024

BINARY_EXTENSIONS = {
    ".7z", ".avi", ".bin", ".bmp", ".class", ".db", ".dll", ".doc", ".docx",
    ".dylib", ".exe", ".gif", ".ico", ".jar", ".jpeg", ".jpg", ".mid", ".midi",
    ".mov", ".mp3", ".mp4", ".o", ".onnx", ".pdf", ".pkl", ".png", ".ppt",
    ".pptx", ".pyc", ".so", ".sqlite", ".ttf", ".wav", ".webp", ".woff", ".woff2",
    ".xls", ".xlsx",
}
ARCHIVE_EXTENSIONS = {".bak", ".dump", ".gz", ".rar", ".sql", ".tar", ".tgz", ".xz", ".zip"}
COPIED_TREE_PARTS = {"node_modules", "vendor", "third_party", ".terraform", "dist", "build"}

SENSITIVE_BASENAMES = {
    ".env", "credentials", "credentials.json", "secrets", "secrets.json",
    "id_dsa", "id_ed25519", "id_ecdsa", "id_rsa", "known_hosts",
}
SENSITIVE_SUFFIXES = {".key", ".p12", ".pfx", ".jks", ".keystore", ".kdbx"}

RESTRICTED_MARKERS = (
    b"CONFIDENTIAL",
    b"PROPRIETARY",
    b"INTERNAL ONLY",
    b"DO NOT DISTRIBUTE",
)
KEY_MARKERS = (
    b"-----BEGIN " + b"PRIVATE KEY-----",
    b"-----BEGIN RSA " + b"PRIVATE KEY-----",
    b"-----BEGIN OPENSSH " + b"PRIVATE KEY-----",
    b"-----BEGIN EC " + b"PRIVATE KEY-----",
)

# These documents discuss publication and governance terminology rather than
# containing restricted project material. No other path receives this exemption.
MARKER_DISCUSSION_PATHS = {
    "docs/publication-checklist.md",
    "docs/data-governance.md",
    "SECURITY.md",
}


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    object_id: str
    path: str
    detail: str


@dataclass(frozen=True)
class BlobRecord:
    object_id: str
    size: int
    paths: tuple[str, ...]


def git(*args: str, input_text: str | None = None) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        input=input_text.encode("utf-8") if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout


def load_allowlist(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1:
        raise ValueError("history audit allowlist schema_version must be 1")
    for section in ("allowed_binary_paths", "allowed_archive_paths", "allowed_template_paths"):
        entries = value.get(section, [])
        if not isinstance(entries, list):
            raise ValueError(f"allowlist section {section} must be an array")
        for entry in entries:
            for field in ("pattern", "owner", "license", "reason"):
                if not str(entry.get(field, "")).strip():
                    raise ValueError(f"allowlist {section} entry is missing {field}")
    return value


def patterns(allowlist: dict[str, Any], section: str) -> list[str]:
    return [str(entry["pattern"]) for entry in allowlist.get(section, [])]


def matches_any(path: str, candidates: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, candidate) for candidate in candidates)


def reachable_blobs() -> list[BlobRecord]:
    object_paths: dict[str, set[str]] = defaultdict(set)
    for line in git("rev-list", "--objects", "--all").decode("utf-8", errors="surrogateescape").splitlines():
        object_id, separator, path = line.partition(" ")
        if separator and path:
            object_paths[object_id].add(path)

    if not object_paths:
        return []
    request = "".join(f"{object_id}\n" for object_id in object_paths)
    output = git("cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", input_text=request)
    records: list[BlobRecord] = []
    for line in output.decode("utf-8").splitlines():
        object_id, object_type, size_text = line.split(" ", 2)
        if object_type == "blob":
            records.append(BlobRecord(object_id, int(size_text), tuple(sorted(object_paths[object_id]))))
    return records


def blob_content(object_id: str, limit: int) -> bytes:
    content = git("cat-file", "blob", object_id)
    return content[:limit]


def is_binary(content: bytes) -> bool:
    if b"\x00" in content:
        return True
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def sensitive_name(path: str, template_patterns: list[str]) -> str | None:
    normalized = path.replace("\\", "/")
    name = Path(normalized).name.lower()
    if matches_any(normalized, template_patterns):
        return None
    if name in SENSITIVE_BASENAMES:
        return f"sensitive filename {name!r}"
    if name.startswith(".env."):
        return "environment file other than an approved example"
    if any(name.endswith(suffix) for suffix in SENSITIVE_SUFFIXES):
        return f"sensitive file suffix {Path(name).suffix!r}"
    if name.startswith(("id_rsa", "id_dsa", "id_ed25519", "id_ecdsa")):
        return "SSH identity filename"
    return None


def audit_blob(record: BlobRecord, allowlist: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    binary_patterns = patterns(allowlist, "allowed_binary_paths")
    archive_patterns = patterns(allowlist, "allowed_archive_paths")
    template_patterns = patterns(allowlist, "allowed_template_paths")

    content: bytes | None = None
    for path in record.paths:
        normalized = path.replace("\\", "/")
        path_parts = set(Path(normalized).parts)
        suffix = Path(normalized).suffix.lower()

        if path_parts & COPIED_TREE_PARTS:
            findings.append(Finding("critical", "copied-tree", record.object_id, normalized, "copied dependency/build tree path"))

        if reason := sensitive_name(normalized, template_patterns):
            findings.append(Finding("critical", "sensitive-path", record.object_id, normalized, reason))

        if suffix in ARCHIVE_EXTENSIONS and not matches_any(normalized, archive_patterns):
            findings.append(Finding("critical", "unapproved-archive", record.object_id, normalized, f"archive or dump extension {suffix}"))

        if suffix in BINARY_EXTENSIONS and not matches_any(normalized, binary_patterns):
            findings.append(Finding("critical", "unapproved-binary", record.object_id, normalized, f"binary extension {suffix}"))

        if record.size > MAX_REVIEW_BLOB_BYTES and not (
            matches_any(normalized, binary_patterns) or matches_any(normalized, archive_patterns)
        ):
            findings.append(Finding("critical", "large-blob", record.object_id, normalized, f"blob is {record.size} bytes and has no ownership attestation"))

    if record.size <= MAX_TEXT_SCAN_BYTES:
        content = blob_content(record.object_id, MAX_TEXT_SCAN_BYTES)
        for path in record.paths:
            normalized = path.replace("\\", "/")
            if any(marker in content for marker in KEY_MARKERS):
                findings.append(Finding("critical", "key-material", record.object_id, normalized, "private-key material marker"))
            if normalized not in MARKER_DISCUSSION_PATHS:
                for marker in RESTRICTED_MARKERS:
                    if marker in content.upper():
                        findings.append(
                            Finding(
                                "critical",
                                "distribution-restriction",
                                record.object_id,
                                normalized,
                                f"restricted-distribution marker {marker.decode('ascii')!r}",
                            )
                        )
            if is_binary(content):
                suffix = Path(normalized).suffix.lower()
                if suffix not in BINARY_EXTENSIONS and not matches_any(normalized, patterns(allowlist, "allowed_binary_paths")):
                    findings.append(Finding("critical", "unclassified-binary", record.object_id, normalized, "binary content without an approved binary path"))

    return findings


def deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    unique = {(finding.severity, finding.category, finding.object_id, finding.path, finding.detail): finding for finding in findings}
    return sorted(unique.values(), key=lambda finding: (finding.severity, finding.category, finding.path, finding.object_id))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowlist", type=Path, default=Path("governance/history-audit-allowlist.json"))
    parser.add_argument("--report", type=Path, default=Path("history-audit-report.json"))
    args = parser.parse_args()

    try:
        allowlist = load_allowlist(args.allowlist)
        records = reachable_blobs()
        findings = deduplicate(finding for record in records for finding in audit_blob(record, allowlist))
        report = {
            "format": AUDIT_FORMAT,
            "git_head": git("rev-parse", "HEAD").decode("ascii").strip(),
            "refs_scanned": git("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes", "refs/tags")
            .decode("utf-8")
            .splitlines(),
            "reachable_blobs_scanned": len(records),
            "allowlist": str(args.allowlist),
            "findings": [asdict(finding) for finding in findings],
            "result": "pass" if not findings else "fail",
            "scope": {
                "secrets": "Gitleaks full-history scan plus key/path checks",
                "ownership": "all reachable binary, archive, copied-tree, and large blobs require explicit approval",
                "limitations": "Automated provenance review cannot replace a legal ownership determination.",
            },
        }
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if findings:
            for finding in findings:
                print(
                    f"history audit failure: {finding.category}: {finding.path} "
                    f"({finding.object_id[:12]}): {finding.detail}",
                    file=sys.stderr,
                )
            return 1
        print(f"history audit passed: {len(records)} reachable blobs scanned across all refs")
        return 0
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"history audit error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
