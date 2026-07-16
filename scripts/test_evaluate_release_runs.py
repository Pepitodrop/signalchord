#!/usr/bin/env python3
from __future__ import annotations

import unittest

import evaluate_release_runs


SHA = "a" * 40


def run(name: str, *, status: str, conclusion: str | None, run_id: int, sha: str = SHA, branch: str = "main") -> dict[str, object]:
    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "id": run_id,
        "head_sha": sha,
        "head_branch": branch,
    }


class ReleaseRunEvaluatorTest(unittest.TestCase):
    def test_all_required_success(self) -> None:
        state = evaluate_release_runs.evaluate_runs(
            [
                run("CI", status="completed", conclusion="success", run_id=1),
                run("History Audit", status="completed", conclusion="success", run_id=2),
            ],
            required=["CI", "History Audit"],
            sha=SHA,
            branch="main",
        )
        self.assertEqual(("CI", "History Audit"), state.successful)
        self.assertEqual((), state.pending)
        self.assertEqual((), state.failed)

    def test_missing_and_in_progress_are_pending(self) -> None:
        state = evaluate_release_runs.evaluate_runs(
            [run("CI", status="in_progress", conclusion=None, run_id=1)],
            required=["CI", "History Audit"],
            sha=SHA,
            branch="main",
        )
        self.assertEqual(("CI:in_progress", "History Audit:missing"), state.pending)

    def test_completed_failure_is_failed(self) -> None:
        state = evaluate_release_runs.evaluate_runs(
            [run("CI", status="completed", conclusion="failure", run_id=1)],
            required=["CI"],
            sha=SHA,
            branch="main",
        )
        self.assertEqual(("CI:failure",), state.failed)

    def test_latest_exact_sha_main_run_wins(self) -> None:
        state = evaluate_release_runs.evaluate_runs(
            [
                run("CI", status="completed", conclusion="failure", run_id=1),
                run("CI", status="completed", conclusion="success", run_id=2),
                run("CI", status="completed", conclusion="failure", run_id=3, sha="b" * 40),
                run("CI", status="completed", conclusion="failure", run_id=4, branch="feature"),
            ],
            required=["CI"],
            sha=SHA,
            branch="main",
        )
        self.assertEqual(("CI",), state.successful)
        self.assertEqual((), state.failed)


if __name__ == "__main__":
    unittest.main()
