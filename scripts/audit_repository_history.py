#!/usr/bin/env python3
"""Audit every reachable Git blob and commit message for publication blockers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_PATHS = {".github/history-audit-denylist.sha256"}
SUSPICIOUS_PATH_RULES = {
    "environment file": re.compile(r"(^|/)\.env(?:\.|$)", re.IGNORECASE),
    "private key or certificate bundle": re.compile(r"\.(?:key|pem|p12|pfx|jks|kdbx)$", re.IGNORECASE),
    "credential configuration": re.compile(r"(^|/)(?:id_rsa|id_ed25519|\.npmrc|\.pypirc|credentials)(?:$|\.)", re.IGNORECASE),
    "database or backup artifact": re.compile(r"\.(?:dump|bak|backup|sqlite3?|kdb)$", re.IGNORECASE),
    "Terraform state": re.compile(r"(^|/)terraform\.tfstate(?:\.|$)", re.IGNORECASE),
}
SECRET_RULES = {
    "private key material": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "GitHub token": re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"),
    "AWS access key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Stripe live key": re.compile(rb"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
PROPRIETARY_PHRASES = {
    "confidentiality marker": re.compile(rb"\b(?:strictly confidential|company confidential|customer confidential)\b", re.IGNORECASE),
    "distribution restriction": re.compile(rb"\b(?:do not distribute|not for external distribution|internal use only)\b", re.IGNORECASE),
    "trade-secret marker": re.compile(rb"\btrade secret(?:s)?\b", re.IGNORECASE),
}


@dataclass(frozen=True)
class Finding:
    scope: str
    object_id: str
    path: str
    rule: str


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args], input=input_bytes)


def load_hashed_terms(path: Path) -> dict[int, set[str]]:
    terms: dict[int, set[str]] = {}
    if not path.exists():
        return terms
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            length_text, digest = line.split(":", 1)
            length = int(length_text)
        except ValueError as exc:
            raise ValueError(f"invalid denylist entry at {path}:{number}") from exc
        if length < 4 or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid denylist entry at {path}:{number}")
        terms.setdefault(length, set()).add(digest)
    return terms


def contains_hashed_term(data: bytes, terms: dict[int, set[str]]) -> bool:
    normalized = data.lower()
    for length, digests in terms.items():
        if len(normalized) < length:
            continue
        for offset in range(0, len(normalized) - length + 1):
            digest = hashlib.sha256(normalized[offset : offset + length]).hexdigest()
            if digest in digests:
                return True
    return False


def audit(repo: Path, denylist: Path) -> tuple[dict[str, int], list[Finding]]:
    if not (repo / ".git").exists():
        raise ValueError(f"not a Git repository: {repo}")
    hashed_terms = load_hashed_terms(denylist)
    findings: list[Finding] = []
    objects = git(repo, "rev-list", "--objects", "--all").decode("utf-8", errors="surrogateescape").splitlines()
    blobs: dict[str, set[str]] = {}
    for row in objects:
        object_id, _, path = row.partition(" ")
        if not path or path in SKIP_PATHS:
            continue
        try:
            object_type = git(repo, "cat-file", "-t", object_id).strip()
        except subprocess.CalledProcessError:
            continue
        if object_type == b"blob":
            blobs.setdefault(object_id, set()).add(path)

    for object_id, paths in blobs.items():
        data = git(repo, "cat-file", "blob", object_id)
        for path in sorted(paths):
            for rule, pattern in SUSPICIOUS_PATH_RULES.items():
                if pattern.search(path) and not path.endswith((".env.example", "runtime.env.example")):
                    findings.append(Finding("blob-path", object_id, path, rule))
        for rule, pattern in SECRET_RULES.items():
            if pattern.search(data):
                findings.append(Finding("blob-content", object_id, sorted(paths)[0], rule))
        for rule, pattern in PROPRIETARY_PHRASES.items():
            if pattern.search(data):
                findings.append(Finding("blob-content", object_id, sorted(paths)[0], rule))
        if hashed_terms and contains_hashed_term(data, hashed_terms):
            findings.append(Finding("blob-content", object_id, sorted(paths)[0], "private hashed denylist term"))

    commits = git(repo, "rev-list", "--all").decode().splitlines()
    for commit in commits:
        message = git(repo, "show", "-s", "--format=%B", commit)
        for rule, pattern in PROPRIETARY_PHRASES.items():
            if pattern.search(message):
                findings.append(Finding("commit-message", commit, "", rule))
        if hashed_terms and contains_hashed_term(message, hashed_terms):
            findings.append(Finding("commit-message", commit, "", "private hashed denylist term"))

    summary = {"reachable_objects": len(objects), "unique_blobs": len(blobs), "commits": len(commits), "findings": len(findings)}
    return summary, findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--denylist", type=Path, default=Path(".github/history-audit-denylist.sha256"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    denylist = args.denylist if args.denylist.is_absolute() else repo / args.denylist
    try:
        summary, findings = audit(repo, denylist)
    except (ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
    payload = {"summary": summary, "findings": [asdict(item) for item in findings]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if findings:
        print("repository history audit failed:", file=sys.stderr)
        for finding in findings:
            location = f" {finding.path}" if finding.path else ""
            print(f"- {finding.scope} {finding.object_id[:12]}{location}: {finding.rule}", file=sys.stderr)
        raise SystemExit(1)
    print(
        f"repository history audit passed: {summary['commits']} commits, "
        f"{summary['unique_blobs']} unique blobs, no publication blockers"
    )


if __name__ == "__main__":
    main()
