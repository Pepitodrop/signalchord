#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HIGH_RISK_NAMES = {
    ".env", "credentials", "credentials.yml.enc", "id_rsa", "id_ed25519",
    "secrets.yml", "secrets.yaml", "terraform.tfstate",
}
HIGH_RISK_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".sqlite", ".sqlite3",
    ".db", ".dump", ".bak", ".sql", ".zip", ".7z", ".rar", ".tar", ".gz",
}
PROPRIETARY_SUFFIXES = {
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".psd", ".ai",
    ".ttf", ".otf", ".woff", ".woff2", ".mp3", ".mp4", ".mov", ".avi", ".wav",
}
MAX_UNREVIEWED_BLOB_BYTES = 5 * 1024 * 1024


def run(*args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{result.stderr}")
    return result.stdout


def load_allowlist(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allowlist", type=Path, default=Path(".github/publication-audit-allowlist.txt"))
    parser.add_argument("--report", type=Path, default=Path("publication-history-audit.md"))
    args = parser.parse_args()

    allowlist = load_allowlist(args.allowlist)
    objects = run("git", "rev-list", "--objects", "--all").splitlines()
    object_rows: list[tuple[str, str]] = []
    for row in objects:
        sha, _, path = row.partition(" ")
        if path:
            object_rows.append((sha, path))

    batch_input = "".join(f"{sha}\n" for sha, _ in object_rows)
    metadata = run("git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)", input_text=batch_input)
    sizes: dict[str, tuple[str, int]] = {}
    for row in metadata.splitlines():
        sha, kind, size = row.split()
        sizes[sha] = (kind, int(size))

    findings: list[str] = []
    reviewed: list[str] = []
    for sha, raw_path in object_rows:
        path = Path(raw_path)
        normalized = path.as_posix()
        if normalized in allowlist:
            reviewed.append(normalized)
            continue
        lower_name = path.name.lower()
        suffix = path.suffix.lower()
        kind, size = sizes.get(sha, ("unknown", 0))
        reasons: list[str] = []
        if lower_name in HIGH_RISK_NAMES or lower_name.startswith(".env."):
            reasons.append("sensitive filename")
        if suffix in HIGH_RISK_SUFFIXES:
            reasons.append("secret/archive/database suffix")
        if suffix in PROPRIETARY_SUFFIXES:
            reasons.append("proprietary or binary asset requiring rights review")
        if kind == "blob" and size > MAX_UNREVIEWED_BLOB_BYTES:
            reasons.append(f"large historical blob ({size} bytes)")
        if reasons:
            findings.append(f"- `{normalized}` at `{sha[:12]}`: {', '.join(reasons)}")

    commits = run("git", "rev-list", "--all").splitlines()
    report_lines = [
        "# Repository history publication audit",
        "",
        f"- Reachable commits inspected: {len(commits)}",
        f"- Historical path objects inspected: {len(object_rows)}",
        f"- Explicitly reviewed allowlist entries encountered: {len(set(reviewed))}",
        "- Secret scanning: performed separately by Gitleaks in the audit workflow.",
        "",
        "## Findings",
        "",
    ]
    report_lines.extend(findings or ["No unallowlisted high-risk or proprietary-content paths found."])
    report_lines.extend([
        "",
        "## Interpretation",
        "",
        "A clean result means the automated history policy found no known risky paths. It does not replace",
        "legal ownership review of source code, datasets, trademarks, screenshots or third-party assets.",
        "",
    ])
    args.report.write_text("\n".join(report_lines), encoding="utf-8")

    if findings:
        print(f"publication history audit found {len(findings)} unreviewed object(s)", file=sys.stderr)
        return 1
    print("publication history audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
