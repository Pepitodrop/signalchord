#!/usr/bin/env python3
"""Require immutable references for every external GitHub Action."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIRECTORY = Path(".github/workflows")
USES_PATTERN = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)")
COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")


def workflow_files(root: Path) -> list[Path]:
    directory = root / WORKFLOW_DIRECTORY
    return sorted((*directory.glob("*.yml"), *directory.glob("*.yaml")))


def validate(root: Path = ROOT) -> None:
    failures: list[str] = []
    files = workflow_files(root)
    if not files:
        failures.append(f"{WORKFLOW_DIRECTORY} contains no workflow files")

    for path in files:
        relative = path.relative_to(root)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_PATTERN.match(line)
            if not match:
                continue

            reference = match.group(1)
            if reference.startswith("./"):
                continue
            if reference.startswith("docker://"):
                if "@sha256:" not in reference:
                    failures.append(
                        f"{relative}:{line_number}: container actions must use an immutable sha256 digest: {reference}"
                    )
                continue
            if "@" not in reference:
                failures.append(f"{relative}:{line_number}: action reference has no ref: {reference}")
                continue

            action, ref = reference.rsplit("@", 1)
            if not action or not COMMIT_SHA_PATTERN.fullmatch(ref):
                failures.append(
                    f"{relative}:{line_number}: external actions must be pinned to a full 40-character commit SHA: {reference}"
                )

    if failures:
        print("workflow action pin validation failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        raise SystemExit(1)

    print(f"validated immutable action references in {len(files)} workflow files")


if __name__ == "__main__":
    validate()
