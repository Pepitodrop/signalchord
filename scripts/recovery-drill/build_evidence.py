#!/usr/bin/env python3
"""Build and validate the recovery-drill's machine-readable evidence artifact.

Matches the repository's existing validate_X.py convention (argparse,
accumulated failures list, deterministic output) -- see
scripts/validate_recovery.py. This module does not talk to Kafka, Postgres
or Kubernetes itself; each drill stage in the workflow writes its own small
JSON section file, and this script merges + validates + scores them into one
schema_version-tagged artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

REQUIRED_TOP_LEVEL_FIELDS = (
    "schema_version",
    "run_id",
    "git_sha",
    "started_at",
    "finished_at",
    "total_duration_seconds",
    "environment",
    "backup",
    "restore",
    "replay",
    "python_poison_message",
    "go_poison_message",
    "transient_failure",
    "duplicate_suppression",
    "cleanup",
    "overall_result",
    "failed_assertions",
)

REQUIRED_SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "backup": ("artifact", "creation_result", "validation_result"),
    "restore": ("result", "duration_seconds", "verified"),
    "replay": (
        "topic",
        "group",
        "partitions",
        "requested_time_range",
        "offsets_before",
        "offsets_after",
        "result",
    ),
    "python_poison_message": (
        "source_topic",
        "dlq_topic",
        "source_offset",
        "dlq_offset",
        "metadata_assertions",
        "healthy_following_message_result",
    ),
    "go_poison_message": (
        "source_topic",
        "dlq_topic",
        "source_offset",
        "dlq_offset",
        "metadata_assertions",
        "healthy_following_message_result",
    ),
    "transient_failure": ("dlq_absent", "acknowledgment_absent", "retry_redelivery_result"),
    "duplicate_suppression": ("assertions", "result"),
    "cleanup": ("result",),
}

# Which field(s) in each section represent a pass/fail outcome, checked
# against either the literal string "pass" or the boolean True.
SECTION_RESULT_KEYS: dict[str, tuple[str, ...]] = {
    "backup": ("creation_result", "validation_result"),
    "restore": ("result",),
    "replay": ("result",),
    "python_poison_message": ("healthy_following_message_result",),
    "go_poison_message": ("healthy_following_message_result",),
    "transient_failure": ("dlq_absent", "acknowledgment_absent", "retry_redelivery_result"),
    "duplicate_suppression": ("result",),
    "cleanup": ("result",),
}

_PASSING_VALUES = ("pass", True)


def validate_evidence(evidence: dict[str, Any]) -> list[str]:
    """Return a list of schema-shape failures; empty means the artifact is
    well-formed (independent of whether the drill itself passed)."""
    failures: list[str] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in evidence:
            failures.append(f"missing top-level field: {field}")

    for section, fields in REQUIRED_SECTION_FIELDS.items():
        value = evidence.get(section)
        if not isinstance(value, dict):
            failures.append(f"{section} must be an object")
            continue
        for field in fields:
            if field not in value:
                failures.append(f"{section}.{field} is required")

    if evidence.get("overall_result") not in ("pass", "fail"):
        failures.append("overall_result must be 'pass' or 'fail'")
    if not isinstance(evidence.get("failed_assertions"), list):
        failures.append("failed_assertions must be a list")
    return failures


def collect_failed_assertions(sections: dict[str, Any]) -> list[str]:
    """Scan each section's own result field(s) and its optional "failures"
    list, returning a deterministic, sorted list of failed-assertion labels."""
    failed: list[str] = []
    for section, result_keys in SECTION_RESULT_KEYS.items():
        value = sections.get(section)
        if not isinstance(value, dict):
            failed.append(f"{section}: section missing or malformed")
            continue
        for key in result_keys:
            if value.get(key) not in _PASSING_VALUES:
                failed.append(f"{section}.{key}")
        for extra in value.get("failures") or []:
            failed.append(f"{section}: {extra}")
    return sorted(failed)


def build_evidence(
    *,
    run_id: str,
    git_sha: str,
    started_at: str,
    finished_at: str,
    environment: str,
    sections: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the full evidence document from per-stage section dicts."""
    duration = (datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)).total_seconds()
    evidence: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "git_sha": git_sha,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_duration_seconds": duration,
        "environment": environment,
    }
    for section in REQUIRED_SECTION_FIELDS:
        evidence[section] = sections.get(section, {})
    failed_assertions = collect_failed_assertions(evidence)
    evidence["failed_assertions"] = failed_assertions
    evidence["overall_result"] = "fail" if failed_assertions else "pass"
    return evidence


def load_sections(sections_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Load one <section>.json file per required section. Returns
    (sections, load_failures); a missing or unparseable file is recorded as
    a failure and the section is treated as an empty (failing) dict, so the
    artifact is still produced even when a drill stage never wrote its
    output (e.g. because that stage itself crashed)."""
    sections: dict[str, Any] = {}
    failures: list[str] = []
    for section in REQUIRED_SECTION_FIELDS:
        path = sections_dir / f"{section}.json"
        if not path.exists():
            failures.append(f"missing section file: {path}")
            sections[section] = {}
            continue
        try:
            sections[section] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            failures.append(f"could not parse {path}: {error}")
            sections[section] = {}
    return sections, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sections-dir",
        type=Path,
        required=True,
        help="Directory containing one <section>.json file per required section",
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--started-at", required=True, help="ISO-8601 timestamp")
    parser.add_argument("--finished-at", required=True, help="ISO-8601 timestamp")
    parser.add_argument("--environment", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    sections, load_failures = load_sections(args.sections_dir)
    evidence = build_evidence(
        run_id=args.run_id,
        git_sha=args.git_sha,
        started_at=args.started_at,
        finished_at=args.finished_at,
        environment=args.environment,
        sections=sections,
    )
    if load_failures:
        evidence["failed_assertions"] = sorted(evidence["failed_assertions"] + load_failures)
        evidence["overall_result"] = "fail"

    shape_failures = validate_evidence(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if shape_failures:
        for failure in shape_failures:
            print(f"evidence schema failure: {failure}", file=sys.stderr)
        return 1
    if evidence["overall_result"] == "fail":
        print(
            "recovery drill assertions failed: " + ", ".join(evidence["failed_assertions"]),
            file=sys.stderr,
        )
        return 1
    print(f"recovery evidence written to {args.output} (overall_result=pass)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
