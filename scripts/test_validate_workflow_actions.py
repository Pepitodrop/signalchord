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
ROOT = Path(__file__).resolve().parents[1]


class WorkflowActionValidatorTest(unittest.TestCase):
    def write_workflow(self, root: Path, content: str) -> None:
        workflow = root / ".github" / "workflows" / "test.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text(content, encoding="utf-8")

    def test_repository_workflows_validate(self) -> None:
        validate_workflow_actions.validate()

    def test_full_commit_sha_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(
                root,
                f"jobs:\n  test:\n    steps:\n      - uses: actions/checkout@{PINNED_SHA} # v4\n",
            )
            validate_workflow_actions.validate(root)

    def test_mutable_tag_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n")
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                validate_workflow_actions.validate(root)

    def test_local_action_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, "jobs:\n  test:\n    steps:\n      - uses: ./.github/actions/test\n")
            validate_workflow_actions.validate(root)

    def test_mutable_container_action_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_workflow(root, "jobs:\n  test:\n    steps:\n      - uses: docker://alpine:3.22\n")
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                validate_workflow_actions.validate(root)

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
