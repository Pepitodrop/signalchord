#!/usr/bin/env python3
"""Evaluate a GitHub Actions workflow-runs response for an exact release SHA."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class GateError(RuntimeError):
    pass


@dataclass(frozen=True)
class GateState:
    successful: tuple[str, ...]
    pending: tuple[str, ...]
    failed: tuple[str, ...]


def latest_runs_by_name(
    runs: Iterable[dict[str, Any]],
    *,
    sha: str,
    branch: str,
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        if run.get("head_sha") != sha or run.get("head_branch") != branch:
            continue
        name = str(run.get("name", "")).strip()
        if not name:
            continue
        current = latest.get(name)
        if current is None or int(run.get("id", 0)) > int(current.get("id", 0)):
            latest[name] = run
    return latest


def evaluate_runs(
    runs: Iterable[dict[str, Any]],
    *,
    required: Iterable[str],
    sha: str,
    branch: str,
) -> GateState:
    latest = latest_runs_by_name(runs, sha=sha, branch=branch)
    successful: list[str] = []
    pending: list[str] = []
    failed: list[str] = []
    for name in sorted(set(required)):
        run = latest.get(name)
        if run is None:
            pending.append(f"{name}:missing")
            continue
        status = str(run.get("status", ""))
        conclusion = run.get("conclusion")
        if status == "completed" and conclusion == "success":
            successful.append(name)
        elif status == "completed":
            failed.append(f"{name}:{conclusion or 'unknown'}")
        else:
            pending.append(f"{name}:{status or 'unknown'}")
    return GateState(tuple(successful), tuple(pending), tuple(failed))


def parse_payload(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read workflow-runs JSON: {exc}") from exc
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise GateError("workflow-runs JSON has no workflow_runs array")
    return [run for run in runs if isinstance(run, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-json", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--required", action="append", default=[])
    args = parser.parse_args()
    try:
        if len(args.sha) != 40 or any(character not in "0123456789abcdef" for character in args.sha.lower()):
            raise GateError("--sha must be a full 40-character hexadecimal commit SHA")
        required = tuple(dict.fromkeys(value.strip() for value in args.required if value.strip()))
        if not required:
            raise GateError("at least one --required workflow is necessary")
        state = evaluate_runs(
            parse_payload(args.runs_json),
            required=required,
            sha=args.sha,
            branch=args.branch,
        )
        if state.failed:
            print("failed=" + ",".join(state.failed))
            return 2
        if state.pending:
            print("pending=" + ",".join(state.pending))
            return 3
        print("success=" + ",".join(state.successful))
        return 0
    except GateError as exc:
        print(f"release workflow evaluation error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
