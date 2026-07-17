#!/usr/bin/env python3
"""Validate immutable GitHub Action refs and least-privilege workflow permissions."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIRECTORY = Path(".github/workflows")
USES_PATTERN = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^'\"\s#]+)")
COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
DOCKER_DIGEST_PATTERN = re.compile(r"^docker://[^@\s]+@sha256:[0-9a-fA-F]{64}$")
PERMISSIONS_PATTERN = re.compile(r"^(?P<indent>\s*)permissions:\s*(?P<value>[^#\s]+)?\s*(?:#.*)?$")
PERMISSION_ENTRY_PATTERN = re.compile(
    r"^(?P<indent>\s+)(?P<name>[a-z-]+):\s*(?P<value>read|write|none)\s*(?:#.*)?$"
)
JOB_PATTERN = re.compile(r"^  (?P<name>[A-Za-z0-9_-]+):\s*(?:#.*)?$")

EXPECTED_RELEASE_PERMISSIONS = {
    "workflow": {"contents": "read"},
    "job:publish-images": {
        "contents": "read",
        "packages": "write",
        "id-token": "write",
    },
    "job:release": {"contents": "write"},
}

EXPECTED_RELEASE_FAILURE_REPORT_PERMISSIONS = {
    "workflow": {
        "actions": "read",
        "contents": "read",
        "issues": "write",
    }
}

COSIGN_INSTALLER_REF = (
    "sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6"
)
EXPECTED_RELEASE_RUNTIME_COUNTS = {
    "cancel-in-progress: true": 1,
    "timeout-minutes: 20": 2,
    "timeout-minutes: 45": 1,
    f"uses: {COSIGN_INSTALLER_REF}": 1,
    "cosign-release: v3.0.6": 1,
    'timeout 5m docker buildx imagetools inspect "$IMAGE@$DIGEST"': 1,
    'timeout 5m cosign sign --yes "$IMAGE@$DIGEST"': 1,
    "timeout 5m cosign verify\n": 1,
    "timeout 5m cosign attest --yes\n": 1,
    "timeout 5m cosign verify-attestation\n": 1,
}


def workflow_files(root: Path) -> list[Path]:
    directory = root / WORKFLOW_DIRECTORY
    return sorted((*directory.glob("*.yml"), *directory.glob("*.yaml")))


def permission_blocks(path: Path, failures: list[str], root: Path) -> dict[str, dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    relative = path.relative_to(root)
    blocks: dict[str, dict[str, str]] = {}
    in_jobs = False
    current_job: str | None = None

    index = 0
    while index < len(lines):
        line = lines[index]
        if line == "jobs:":
            in_jobs = True
            current_job = None
        elif in_jobs:
            job_match = JOB_PATTERN.match(line)
            if job_match:
                current_job = job_match.group("name")

        match = PERMISSIONS_PATTERN.match(line)
        if not match:
            index += 1
            continue

        indent = len(match.group("indent"))
        inline_value = match.group("value")
        if indent == 0:
            scope = "workflow"
        elif indent == 4 and current_job:
            scope = f"job:{current_job}"
        else:
            failures.append(
                f"{relative}:{index + 1}: permissions block has unsupported indentation or scope"
            )
            index += 1
            continue

        if scope in blocks:
            failures.append(f"{relative}:{index + 1}: duplicate permissions block for {scope}")

        if inline_value:
            normalized = inline_value.strip("'\"")
            blocks[scope] = {"*": normalized}
            if normalized == "write-all":
                failures.append(f"{relative}:{index + 1}: permissions: write-all is forbidden")
            index += 1
            continue

        entries: dict[str, str] = {}
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            if not candidate.strip() or candidate.lstrip().startswith("#"):
                cursor += 1
                continue
            candidate_indent = len(candidate) - len(candidate.lstrip())
            if candidate_indent <= indent:
                break
            entry = PERMISSION_ENTRY_PATTERN.match(candidate)
            if not entry or len(entry.group("indent")) != indent + 2:
                failures.append(
                    f"{relative}:{cursor + 1}: malformed permission entry in {scope}: {candidate.strip()}"
                )
            else:
                name = entry.group("name")
                if name in entries:
                    failures.append(f"{relative}:{cursor + 1}: duplicate permission {name} in {scope}")
                entries[name] = entry.group("value")
            cursor += 1
        blocks[scope] = entries
        index = cursor

    return blocks


def write_permissions(permissions: dict[str, str]) -> list[str]:
    return sorted(name for name, value in permissions.items() if value in {"write", "write-all"})


def validate_exact_permissions(
    path: Path,
    blocks: dict[str, dict[str, str]],
    expected_blocks: dict[str, dict[str, str]],
    failures: list[str],
    root: Path,
) -> None:
    relative = path.relative_to(root)
    for scope, expected in expected_blocks.items():
        actual = blocks.get(scope)
        if actual != expected:
            failures.append(f"{relative}: {scope} permissions must be exactly {expected}, got {actual}")

    for scope, permissions in blocks.items():
        if scope in expected_blocks:
            continue
        writes = write_permissions(permissions)
        if writes:
            failures.append(
                f"{relative}: unexpected write permissions in {scope}: {', '.join(writes)}"
            )


def validate_release_runtime(path: Path, failures: list[str], root: Path) -> None:
    relative = path.relative_to(root)
    content = path.read_text(encoding="utf-8")
    for snippet, expected_count in EXPECTED_RELEASE_RUNTIME_COUNTS.items():
        actual_count = content.count(snippet)
        if actual_count != expected_count:
            failures.append(
                f"{relative}: release runtime safeguard {snippet!r} must occur exactly "
                f"{expected_count} time(s), got {actual_count}"
            )


def validate_permissions(
    path: Path,
    blocks: dict[str, dict[str, str]],
    failures: list[str],
    root: Path,
) -> None:
    relative = path.relative_to(root)
    workflow_permissions = blocks.get("workflow")
    if workflow_permissions is None:
        failures.append(f"{relative}: workflow must declare explicit top-level permissions")
    elif "*" in workflow_permissions:
        failures.append(f"{relative}: top-level permissions must use an explicit permission map")

    if path.name == "release.yml":
        validate_exact_permissions(path, blocks, EXPECTED_RELEASE_PERMISSIONS, failures, root)
        validate_release_runtime(path, failures, root)
        return

    if path.name == "release-failure-report.yml":
        validate_exact_permissions(
            path,
            blocks,
            EXPECTED_RELEASE_FAILURE_REPORT_PERMISSIONS,
            failures,
            root,
        )
        return

    for scope, permissions in blocks.items():
        writes = write_permissions(permissions)
        if writes:
            failures.append(
                f"{relative}: write permissions are not allowed in {scope}: {', '.join(writes)}"
            )


def validate(root: Path = ROOT) -> None:
    failures: list[str] = []
    files = workflow_files(root)
    if not files:
        failures.append(f"{WORKFLOW_DIRECTORY} contains no workflow files")

    for path in files:
        relative = path.relative_to(root)
        blocks = permission_blocks(path, failures, root)
        validate_permissions(path, blocks, failures, root)

        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_PATTERN.match(line)
            if not match:
                continue

            reference = match.group(1)
            if reference.startswith("./"):
                continue
            if reference.startswith("docker://"):
                if not DOCKER_DIGEST_PATTERN.fullmatch(reference):
                    failures.append(
                        f"{relative}:{line_number}: container actions must use a full immutable sha256 digest: {reference}"
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
        print("workflow security validation failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        raise SystemExit(1)

    print(
        f"validated immutable action references and permission boundaries in {len(files)} workflow files"
    )


if __name__ == "__main__":
    validate()
