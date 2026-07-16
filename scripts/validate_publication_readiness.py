#!/usr/bin/env python3
"""Validate repository-owned requirements for safe public source publication."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "NOTICE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "CHANGELOG.md",
    "docs/publication-checklist.md",
    "docs/community-self-hosting.md",
    "docs/single-server-kubernetes.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/release.yml",
    "apps/mobile/app/index.tsx",
    "apps/mobile/lib/session.tsx",
)


def read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def validate(root: Path = ROOT) -> None:
    failures: list[str] = []

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            failures.append(f"missing required publication file: {relative}")

    if failures:
        report(failures)

    readme = read(root, "README.md")
    for marker in (
        "Apache License 2.0",
        "Community self-hosting",
        "Security and responsible use",
        "Publication status",
    ):
        if marker not in readme:
            failures.append(f"README.md must contain publication marker: {marker}")

    security = read(root, "SECURITY.md")
    if "Reporting a vulnerability" not in security or "public issue" not in security:
        failures.append("SECURITY.md must define private vulnerability reporting")

    support = read(root, "SUPPORT.md")
    if "best-effort" not in support or "no paid support" not in support.lower():
        failures.append("SUPPORT.md must state the best-effort, non-commercial support scope")

    changelog = read(root, "CHANGELOG.md")
    if "## [Unreleased]" not in changelog or "v1.0.0" not in changelog:
        failures.append("CHANGELOG.md must contain Unreleased and v1.0.0 semantics")

    publication = read(root, "docs/publication-checklist.md")
    for marker in ("complete Git history", "private to public", "mobile", "branch protection"):
        if marker.lower() not in publication.lower():
            failures.append(f"publication checklist must cover: {marker}")

    single_server = read(root, "docs/single-server-kubernetes.md")
    for marker in ("single-owner", "k3s", "backup", "rollback", "mobile"):
        if marker.lower() not in single_server.lower():
            failures.append(f"single-server Kubernetes guide must cover: {marker}")

    mobile_screen = read(root, "apps/mobile/app/index.tsx")
    forbidden_mobile_defaults = (
        "analyst@signalchord.local",
        "signalchord-demo-password",
        'useState("demo")',
    )
    for marker in forbidden_mobile_defaults:
        if marker in mobile_screen:
            failures.append(f"mobile sign-in must not prefill development credential: {marker}")
    for marker in ("Server URL", "serverUrl", "submitting"):
        if marker not in mobile_screen:
            failures.append(f"mobile sign-in must include self-hosted connection behavior: {marker}")

    mobile_session = read(root, "apps/mobile/lib/session.tsx")
    for marker in ("API_URL_KEY", "SecureStore", "normalizeApiUrl", "EXPO_PUBLIC_API_URL"):
        if marker not in mobile_session:
            failures.append(f"mobile session must securely persist and validate server configuration: {marker}")
    if '?? "http://localhost:' in mobile_session or '|| "http://localhost:' in mobile_session:
        failures.append("mobile release code must not silently fall back to localhost")

    release = read(root, ".github/workflows/release.yml")
    for marker in (
        "v*.*.*",
        "release-manifest.json",
        "cosign sign",
        "attest-build-provenance",
        "image-digests.txt",
    ):
        if marker not in release:
            failures.append(f"release workflow must retain publication artifact/control: {marker}")

    issue_config = read(root, ".github/ISSUE_TEMPLATE/config.yml")
    if "security/advisories/new" not in issue_config or "blank_issues_enabled: false" not in issue_config:
        failures.append("issue routing must direct security reports privately and disable blank issues")

    if failures:
        report(failures)

    print(f"validated {len(REQUIRED_FILES)} public-repository readiness files")


def report(failures: list[str]) -> None:
    print("publication readiness validation failed:", file=sys.stderr)
    print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    validate()
