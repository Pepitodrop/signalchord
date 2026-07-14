#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_AUTHORITATIVE = {"postgresql", "kafka", "object_storage", "neo4j", "secrets_and_configuration"}
REQUIRED_DERIVED = {"opensearch", "redis"}
REQUIRED_EVIDENCE = {
    "restore command log with timestamps",
    "source and restored environment identifiers",
    "image digests and git SHA",
    "RPO and RTO actuals",
    "article-to-alert canary result",
    "tenant isolation validation",
    "operator and approver",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_store(store: dict[str, Any], *, derived: bool) -> list[str]:
    failures: list[str] = []
    name = store.get("name", "<unknown>")
    for field in ("owner", "rpo_minutes", "rto_minutes", "validation"):
        if field not in store:
            failures.append(f"{name} missing {field}")
    for field in ("rpo_minutes", "rto_minutes"):
        value = store.get(field)
        if not isinstance(value, int) or value < 0:
            failures.append(f"{name}.{field} must be a non-negative integer")
    validation = store.get("validation")
    if not isinstance(validation, list) or not validation:
        failures.append(f"{name}.validation must contain at least one validation step")
    if derived:
        if store.get("rebuildable") is not True:
            failures.append(f"{name} derived stores must be marked rebuildable")
        if not store.get("derived_from"):
            failures.append(f"{name} must list derived_from sources")
    else:
        if store.get("restore_drill_required") is not True:
            failures.append(f"{name} authoritative stores must require restore drills")
        if not store.get("authoritative_for"):
            failures.append(f"{name} must list authoritative_for data")
        if not store.get("rebuild_source"):
            failures.append(f"{name} must list rebuild_source")
    return failures


def validate_matrix(matrix: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if matrix.get("schema_version") != 1:
        failures.append("schema_version must be 1")

    authoritative = matrix.get("authoritative_stores")
    if not isinstance(authoritative, list):
        failures.append("authoritative_stores must be a list")
        authoritative = []
    authoritative_names = {store.get("name") for store in authoritative if isinstance(store, dict)}
    missing_authoritative = REQUIRED_AUTHORITATIVE - authoritative_names
    if missing_authoritative:
        failures.append(f"missing authoritative stores: {', '.join(sorted(missing_authoritative))}")
    for store in authoritative:
        if isinstance(store, dict):
            failures.extend(validate_store(store, derived=False))
        else:
            failures.append("authoritative store entries must be objects")

    derived = matrix.get("derived_stores")
    if not isinstance(derived, list):
        failures.append("derived_stores must be a list")
        derived = []
    derived_names = {store.get("name") for store in derived if isinstance(store, dict)}
    missing_derived = REQUIRED_DERIVED - derived_names
    if missing_derived:
        failures.append(f"missing derived stores: {', '.join(sorted(missing_derived))}")
    for store in derived:
        if isinstance(store, dict):
            failures.extend(validate_store(store, derived=True))
        else:
            failures.append("derived store entries must be objects")

    rollback = matrix.get("rollback")
    if not isinstance(rollback, dict):
        failures.append("rollback must be an object")
    else:
        if rollback.get("immutable_digest_required") is not True:
            failures.append("rollback must require immutable digests")
        for field in ("pre_rollback_canary", "post_rollback_canary", "irreversible_change_policy"):
            if not rollback.get(field):
                failures.append(f"rollback missing {field}")

    evidence = set(matrix.get("evidence_required", []))
    missing_evidence = REQUIRED_EVIDENCE - evidence
    if missing_evidence:
        failures.append(f"missing evidence requirements: {', '.join(sorted(missing_evidence))}")

    blockers = matrix.get("external_blockers")
    if not isinstance(blockers, list) or len(blockers) < 3:
        failures.append("external_blockers must list remaining non-repository evidence")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate recovery and disaster-recovery repository evidence.")
    parser.add_argument("--matrix", type=Path, default=Path("recovery/recovery-matrix.json"))
    args = parser.parse_args()

    failures = validate_matrix(load_json(args.matrix))
    if failures:
        for failure in failures:
            print(f"recovery validation failure: {failure}", file=sys.stderr)
        return 1
    print("recovery validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
