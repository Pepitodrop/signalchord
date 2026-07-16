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
            "Scan the complete Git history, test mobile, enable branch protection, then change private to public.\n",
        )
        self.write(
            root,
            "docs/single-server-kubernetes.md",
            "A single-owner k3s server supports mobile access, backup and rollback.\n",
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
