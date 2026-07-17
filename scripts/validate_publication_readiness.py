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
    "docs/repository-history-audit.md",
    "docs/community-self-hosting.md",
    "docs/single-server-kubernetes.md",
    "docs/dependency-maintenance.md",
    ".github/dependabot.yml",
    ".github/history-audit-denylist.sha256",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/releases/v1.0.0.md",
    ".github/workflows/release.yml",
    ".github/workflows/repository-history-audit.yml",
    "scripts/audit_repository_history.py",
    "scripts/test_audit_repository_history.py",
    "scripts/single-server/backup.sh",
    "scripts/single-server/restore.sh",
    "scripts/single-server/restore-v1.sh",
    "scripts/single-server/acceptance.sh",
    "apps/web/src/main.tsx",
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
    for marker in ("complete Git history", "private to public", "mobile", "branch protection", "dependency-maintenance.md"):
        if marker.lower() not in publication.lower():
            failures.append(f"publication checklist must cover: {marker}")

    dependency_policy = read(root, "docs/dependency-maintenance.md")
    for marker in ("Security updates remain enabled", "Major upgrades", "full CI", "not auto-merged"):
        if marker.lower() not in dependency_policy.lower():
            failures.append(f"dependency maintenance policy must cover: {marker}")

    dependabot = read(root, ".github/dependabot.yml")
    for marker in (
        "package-ecosystem: npm",
        "package-ecosystem: gomod",
        "package-ecosystem: pip",
        "package-ecosystem: bundler",
        "package-ecosystem: github-actions",
        "applies-to: security-updates",
        "open-pull-requests-limit: 2",
        "timezone: Europe/Berlin",
    ):
        if marker not in dependabot:
            failures.append(f"Dependabot release policy must retain control: {marker}")
    if "version-update:semver-major" in dependabot:
        failures.append("routine Dependabot policy must not automatically propose major version updates")

    history_audit = read(root, "docs/repository-history-audit.md")
    for marker in ("complete Git history", "Gitleaks", "hashed", "private to public"):
        if marker.lower() not in history_audit.lower():
            failures.append(f"repository history audit guide must cover: {marker}")

    history_workflow = read(root, ".github/workflows/repository-history-audit.yml")
    for marker in ("fetch-depth: 0", "gitleaks git", "audit_repository_history.py", "upload-artifact"):
        if marker not in history_workflow:
            failures.append(f"history audit workflow must retain control: {marker}")

    single_server = read(root, "docs/single-server-kubernetes.md")
    for marker in ("single-owner", "k3s", "backup.sh", "restore.sh", "acceptance.sh", "mobile"):
        if marker.lower() not in single_server.lower():
            failures.append(f"single-server Kubernetes guide must cover: {marker}")

    backup = read(root, "scripts/single-server/backup.sh")
    for marker in (
        "runtime.env.age",
        "pg_dump",
        "neo4j-admin database dump neo4j",
        "neo4j-admin database dump system",
        "minio.tar",
        "application_quiesced",
        "SHA256SUMS",
    ):
        if marker not in backup:
            failures.append(f"single-server backup must retain control: {marker}")

    restore_entrypoint = read(root, "scripts/single-server/restore.sh")
    if "restore-v1.sh" not in restore_entrypoint:
        failures.append("single-server restore entrypoint must dispatch to restore-v1.sh")
    restore = read(root, "scripts/single-server/restore-v1.sh")
    for marker in (
        "sha256sum -c",
        "pg_restore",
        "neo4j-admin database load system",
        "neo4j-admin database load neo4j",
        "neo4j-system.dump",
        "application_quiesced",
        "--yes",
    ):
        if marker not in restore:
            failures.append(f"single-server restore must retain control: {marker}")

    acceptance = read(root, "scripts/single-server/acceptance.sh")
    for marker in ("signalchord-feed-collector", "/api/v1/sources", "/api/v1/watchlists", "/api/v1/alerts"):
        if marker not in acceptance:
            failures.append(f"single-server acceptance must retain control: {marker}")

    web_screen = read(root, "apps/web/src/main.tsx")
    forbidden_web_defaults = (
        'useState("analyst@signalchord.local")',
        'useState("signalchord-demo-password")',
    )
    for marker in forbidden_web_defaults:
        if marker in web_screen:
            failures.append(f"web sign-in must not prefill development credential: {marker}")
    for marker in ('useState("")', 'autoComplete="username"', 'autoComplete="current-password"'):
        if marker not in web_screen:
            failures.append(f"web sign-in must retain empty, browser-compatible release input: {marker}")

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

    release_notes = read(root, ".github/releases/v1.0.0.md")
    for marker in ("Included", "Supported use", "Important limitations", "Install", "Upgrade and rollback", "Security"):
        if marker not in release_notes:
            failures.append(f"v1.0.0 release notes must cover: {marker}")

    release = read(root, ".github/workflows/release.yml")
    for marker in (
        "workflow_dispatch:",
        ".github/releases/v1.0.0",
        "Release tag:",
        "Release commit:",
        "release-manifest.json",
        "cosign sign",
        "cosign attest",
        "cosign verify-attestation",
        "provenance-${{ matrix.name }}.json",
        "image-digests.txt",
        "body_path: .github/releases/v1.0.0.md",
    ):
        if marker not in release:
            failures.append(f"release workflow must retain publication artifact/control: {marker}")
    for forbidden in ("attest-build-provenance", "attestations: write", "    tags:"):
        if forbidden in release:
            failures.append(f"release workflow contains unsupported or duplicate release control: {forbidden}")

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
