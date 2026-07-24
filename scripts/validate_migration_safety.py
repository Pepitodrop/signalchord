#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

DEFAULT_MIGRATE_DIR = Path("apps/control-plane/db/migrate")

# Matched as whole-word method-call identifiers, so e.g. a comment mentioning
# "drop_table" in prose, or an unrelated identifier like "rename_column_map",
# does not trip these. Comment-only lines are stripped before matching (see
# find_destructive_operations), which additionally avoids false positives from
# these words appearing only in prose.
DESTRUCTIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "drop_table": re.compile(r"\bdrop_table\b"),
    "remove_column": re.compile(r"\bremove_column\b"),
    "drop_column": re.compile(r"\bdrop_column\b"),
    "rename_column": re.compile(r"\brename_column\b"),
}

# The forward-repair policy this acknowledges is the one already written in
# recovery/recovery-matrix.json's rollback.irreversible_change_policy:
# "forward-repair only; do not reverse incompatible event contracts or
# destructive migrations." A migration is exempted from the destructive-
# pattern check only if one of its comment lines contains ALL of the four
# substrings below -- deliberately strict and co-located on a single line, so
# a marker cannot be satisfied by scattering the right words across unrelated
# comments.
ACKNOWLEDGMENT_MARKER = "recovery-safety:"
ACKNOWLEDGMENT_REQUIRED_SUBSTRINGS = (
    ACKNOWLEDGMENT_MARKER,
    "acknowledged-destructive",
    "forward-repair",
    "recovery-matrix.json",
)
ACKNOWLEDGMENT_EXAMPLE = (
    "# recovery-safety: acknowledged-destructive "
    "(forward-repair-only policy, see recovery/recovery-matrix.json)"
)


def _is_comment_line(line: str) -> bool:
    return line.strip().startswith("#")


def find_destructive_operations(text: str) -> list[str]:
    """Return the destructive pattern names found in non-comment lines, sorted."""
    found: set[str] = set()
    for line in text.splitlines():
        if _is_comment_line(line):
            continue
        for name, pattern in DESTRUCTIVE_PATTERNS.items():
            if pattern.search(line):
                found.add(name)
    return sorted(found)


def has_forward_repair_acknowledgment(text: str) -> bool:
    for line in text.splitlines():
        if not _is_comment_line(line):
            continue
        stripped = line.strip()
        if all(substring in stripped for substring in ACKNOWLEDGMENT_REQUIRED_SUBSTRINGS):
            return True
    return False


def validate_migration(path: Path, text: str) -> list[str]:
    """Return failure strings for a single migration file's contents."""
    destructive = find_destructive_operations(text)
    if not destructive:
        return []
    if has_forward_repair_acknowledgment(text):
        return []
    joined = ", ".join(destructive)
    return [
        f"{path}: destructive migration pattern(s) [{joined}] require an explicit "
        f"acknowledgment comment citing the forward-repair policy, e.g.:\n"
        f"    {ACKNOWLEDGMENT_EXAMPLE}"
    ]


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def changed_migration_files(
    migrate_dir: Path,
    base: str | None,
    head: str,
    run: Callable[[list[str]], subprocess.CompletedProcess[str]] = _run_git,
) -> list[Path]:
    """Return migration files to check: changed-since-base, or all as a safe fallback.

    Falls back to scanning every migration file under migrate_dir -- never to
    scanning nothing -- whenever `base` is absent, or a git diff against it
    cannot be computed (e.g. the base SHA was never fetched into a shallow
    checkout). Scanning all files is always safe here: it can only ever find
    the same violations a full-diff scan would, never fewer.
    """
    all_files = sorted(p for p in migrate_dir.glob("*.rb") if p.is_file())
    if not base:
        return all_files
    try:
        result = run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", base, head, "--", str(migrate_dir)]
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        print(
            f"warning: could not diff against base {base!r}; scanning all migration files instead",
            file=sys.stderr,
        )
        return all_files
    changed: list[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        candidate = Path(line)
        if candidate.suffix == ".rb" and candidate.is_file():
            changed.append(candidate)
    return sorted(changed)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail a PR that introduces a destructive Rails migration pattern "
        "without an explicit forward-repair acknowledgment."
    )
    parser.add_argument("--migrate-dir", type=Path, default=DEFAULT_MIGRATE_DIR)
    parser.add_argument(
        "--base",
        default=None,
        help="git ref/SHA to diff against (e.g. a PR base SHA). If omitted, or if it "
        "cannot be resolved, every migration file under --migrate-dir is scanned instead.",
    )
    parser.add_argument("--head", default="HEAD")
    args = parser.parse_args()

    base = args.base or None
    files = changed_migration_files(args.migrate_dir, base, args.head)

    failures: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        failures.extend(validate_migration(path, text))

    if failures:
        for failure in failures:
            print(f"migration safety failure: {failure}", file=sys.stderr)
        return 1
    print(f"migration safety validation passed ({len(files)} migration file(s) checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
