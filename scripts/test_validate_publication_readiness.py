#!/usr/bin/env python3
"""Regression tests for public-repository readiness policy."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import validate_publication_readiness


class PublicationReadinessValidatorTest(unittest.TestCase):
    def write(self, root: Path, relative: str, content: str = "present") -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def fixture(self, root: Path) -> None:
        for relative in validate_publication_readiness.REQUIRED_FILES:
            self.write(root, relative)
        self.write(
            root,
            "README.md",
            "Apache License 2.0\nCommunity self-hosting\nSecurity and responsible use\nPublication status\n",
        )
        self.write(root, "SECURITY.md", "Reporting a vulnerability through a private channel, not a public issue.\n")
        self.write(root, "SUPPORT.md", "Community support is best-effort and there is no paid support plan.\n")
        self.write(root, "CHANGELOG.md", "## [Unreleased]\nSemantic releases begin with v1.0.0.\n")
        self.write(
            root,
            "docs/publication-checklist.md",
            "Scan the complete Git history, test mobile, enable branch protection, follow dependency-maintenance.md, then change private to public.\n",
        )
        self.write(
            root,
            "docs/dependency-maintenance.md",
            "Security updates remain enabled. Major upgrades use dedicated work. Every change passes full CI and is not auto-merged.\n",
        )
        self.write(
            root,
            ".github/dependabot.yml",
            """version: 2
updates:
  - package-ecosystem: npm
    open-pull-requests-limit: 2
    schedule: {interval: weekly, timezone: Europe/Berlin}
    groups: {security: {applies-to: security-updates}}
  - package-ecosystem: gomod
    open-pull-requests-limit: 2
    schedule: {interval: weekly, timezone: Europe/Berlin}
    groups: {security: {applies-to: security-updates}}
  - package-ecosystem: pip
    open-pull-requests-limit: 2
    schedule: {interval: weekly, timezone: Europe/Berlin}
    groups: {security: {applies-to: security-updates}}
  - package-ecosystem: bundler
    open-pull-requests-limit: 2
    schedule: {interval: weekly, timezone: Europe/Berlin}
    groups: {security: {applies-to: security-updates}}
  - package-ecosystem: github-actions
    open-pull-requests-limit: 2
    schedule: {interval: weekly, timezone: Europe/Berlin}
    groups: {security: {applies-to: security-updates}}
""",
        )
        self.write(
            root,
            "docs/repository-history-audit.md",
            "Audit the complete Git history with Gitleaks and a hashed denylist before changing private to public.\n",
        )
        self.write(
            root,
            ".github/workflows/repository-history-audit.yml",
            "fetch-depth: 0\ngitleaks git\naudit_repository_history.py\nactions/upload-artifact\n",
        )
        self.write(
            root,
            "docs/single-server-kubernetes.md",
            "A single-owner k3s server supports backup.sh, restore.sh, acceptance.sh and mobile access.\n",
        )
        self.write(
            root,
            "scripts/single-server/backup.sh",
            "runtime.env.age pg_dump neo4j-admin database dump neo4j neo4j-admin database dump system minio.tar application_quiesced SHA256SUMS\n",
        )
        self.write(root, "scripts/single-server/restore.sh", "exec restore-v1.sh\n")
        self.write(
            root,
            "scripts/single-server/restore-v1.sh",
            "sha256sum -c pg_restore neo4j-admin database load system neo4j-admin database load neo4j neo4j-system.dump application_quiesced --yes\n",
        )
        self.write(
            root,
            "scripts/single-server/acceptance.sh",
            "signalchord-feed-collector /api/v1/sources /api/v1/watchlists /api/v1/alerts\n",
        )
        self.write(
            root,
            "apps/mobile/app/index.tsx",
            "const serverUrl = 'configured'; const submitting = false; const label = 'Server URL';\n",
        )
        self.write(
            root,
            "apps/mobile/lib/session.tsx",
            "const API_URL_KEY='key'; SecureStore; normalizeApiUrl; EXPO_PUBLIC_API_URL;\n",
        )
        self.write(
            root,
            ".github/workflows/release.yml",
            "v*.*.* release-manifest.json cosign sign attest-build-provenance image-digests.txt\n",
        )
        self.write(
            root,
            ".github/ISSUE_TEMPLATE/config.yml",
            "blank_issues_enabled: false\nurl: https://github.com/example/project/security/advisories/new\n",
        )

    def assert_fails(self, root: Path) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            validate_publication_readiness.validate(root)

    def test_repository_validates(self) -> None:
        validate_publication_readiness.validate()

    def test_missing_publication_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            (root / "CHANGELOG.md").unlink()
            self.assert_fails(root)

    def test_missing_history_audit_control_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.write(root, ".github/workflows/repository-history-audit.yml", "fetch-depth: 0\n")
            self.assert_fails(root)

    def test_dependabot_major_version_updates_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            path = root / ".github/dependabot.yml"
            path.write_text(path.read_text(encoding="utf-8") + "version-update:semver-major\n", encoding="utf-8")
            self.assert_fails(root)

    def test_missing_dependabot_security_group_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            text = (root / ".github/dependabot.yml").read_text(encoding="utf-8")
            self.write(root, ".github/dependabot.yml", text.replace("applies-to: security-updates", "applies-to: version-updates"))
            self.assert_fails(root)

    def test_incomplete_restore_contract_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.write(root, "scripts/single-server/restore-v1.sh", "sha256sum -c pg_restore --yes\n")
            self.assert_fails(root)

    def test_prefilled_mobile_credentials_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.write(
                root,
                "apps/mobile/app/index.tsx",
                'const serverUrl="configured"; const submitting=false; const label="Server URL"; analyst@signalchord.local',
            )
            self.assert_fails(root)

    def test_mobile_localhost_fallback_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.write(
                root,
                "apps/mobile/lib/session.tsx",
                'const API_URL_KEY="key"; SecureStore; normalizeApiUrl; EXPO_PUBLIC_API_URL ?? "http://localhost:3000";',
            )
            self.assert_fails(root)

    def test_release_missing_provenance_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            self.write(
                root,
                ".github/workflows/release.yml",
                "v*.*.* release-manifest.json cosign sign image-digests.txt\n",
            )
            self.assert_fails(root)


if __name__ == "__main__":
    unittest.main()
