#!/usr/bin/env python3
"""Failure-covering tests for repository workflow and smoke-test controls."""

from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import validate_workflow_actions


PINNED_SHA = "0123456789abcdef0123456789abcdef01234567"
PINNED_DIGEST = "a" * 64
ROOT = Path(__file__).resolve().parents[1]


class WorkflowActionValidatorTest(unittest.TestCase):
    def write_workflow(self, root: Path, content: str, name: str = "test.yml") -> None:
        workflow = root / ".github" / "workflows" / name
        workflow.parent.mkdir(parents=True, exist_ok=True)
        workflow.write_text(content, encoding="utf-8")

    def standard_workflow(self, action: str) -> str:
        return f"""name: Test
permissions:
  contents: read
jobs:
  test:
    steps:
      - uses: {action}
"""

    def valid_release_workflow(self) -> str:
        return f"""name: Release
permissions:
  contents: read
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@{PINNED_SHA}
  publish-images:
    permissions:
      contents: read
      packages: write
      id-token: write
    steps:
      - uses: actions/checkout@{PINNED_SHA}
  release:
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@{PINNED_SHA}
"""

    def assert_validation_fails(self, root: Path) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            validate_workflow_actions.validate(root)

    def test_repository_workflows_validate(self) -> None:
        validate_workflow_actions.validate()

    def test_full_commit_sha_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(
                root,
                self.standard_workflow(f"actions/checkout@{PINNED_SHA} # v4"),
            )
            validate_workflow_actions.validate(root)

    def test_mutable_tag_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, self.standard_workflow("actions/checkout@v4"))
            self.assert_validation_fails(root)

    def test_local_action_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, self.standard_workflow("./.github/actions/test"))
            validate_workflow_actions.validate(root)

    def test_full_container_digest_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(
                root,
                self.standard_workflow(f"docker://alpine@sha256:{PINNED_DIGEST}"),
            )
            validate_workflow_actions.validate(root)

    def test_mutable_container_action_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, self.standard_workflow("docker://alpine:3.22"))
            self.assert_validation_fails(root)

    def test_short_container_digest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, self.standard_workflow("docker://alpine@sha256:abcd"))
            self.assert_validation_fails(root)

    def test_missing_top_level_permissions_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(
                root,
                f"jobs:\n  test:\n    steps:\n      - uses: actions/checkout@{PINNED_SHA}\n",
            )
            self.assert_validation_fails(root)

    def test_non_release_write_permission_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(
                root,
                f"""permissions:
  contents: read
jobs:
  test:
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@{PINNED_SHA}
""",
            )
            self.assert_validation_fails(root)

    def test_permissions_write_all_fails_even_when_quoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, "permissions: 'write-all'\njobs: {}\n")
            self.assert_validation_fails(root)

    def test_release_permission_boundaries_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, self.valid_release_workflow(), "release.yml")
            validate_workflow_actions.validate(root)

    def test_release_top_level_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = self.valid_release_workflow().replace(
                "permissions:\n  contents: read",
                "permissions:\n  contents: write",
                1,
            )
            self.write_workflow(root, content, "release.yml")
            self.assert_validation_fails(root)

    def test_release_publish_job_extra_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = self.valid_release_workflow().replace(
                "      id-token: write",
                "      id-token: write\n      attestations: write",
                1,
            )
            self.write_workflow(root, content, "release.yml")
            self.assert_validation_fails(root)

    def test_smoke_retry_helper_success_and_timeout_paths(self) -> None:
        subprocess.run(
            ["sh", str(ROOT / "scripts" / "test_smoke_test_lib.sh")],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
