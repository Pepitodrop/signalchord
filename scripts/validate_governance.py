#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_SOURCE_FIELDS = {
    "id",
    "name",
    "owner",
    "rights_status",
    "legal_basis",
    "endpoint_patterns",
    "adapter",
    "permitted_uses",
    "attribution",
    "terms_status",
    "robots_status",
    "geography",
    "retention_days",
    "deletion_obligations",
    "takedown_contact",
    "last_reviewed",
    "next_review_due",
}
REQUIRED_STORES = {"postgresql", "kafka", "object_storage", "neo4j", "opensearch", "redis", "telemetry"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_source_inventory(inventory: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()
    for source in inventory.get("sources", []):
        source_id = source.get("id", "<missing>")
        missing = sorted(key for key in REQUIRED_SOURCE_FIELDS if not source.get(key))
        if missing:
            failures.append(f"source {source_id} missing fields: {', '.join(missing)}")
        if source.get("id") in seen:
            failures.append(f"duplicate source id: {source_id}")
        seen.add(source.get("id"))
        if source.get("rights_status") != "approved":
            failures.append(f"source {source_id} must be approved before production enablement")
        if not isinstance(source.get("retention_days"), int) or source.get("retention_days") < 0:
            failures.append(f"source {source_id} retention_days must be a non-negative integer")
        if not isinstance(source.get("permitted_uses"), list) or not source.get("permitted_uses"):
            failures.append(f"source {source_id} permitted_uses must be a non-empty list")
        if not isinstance(source.get("deletion_obligations"), list) or not source.get("deletion_obligations"):
            failures.append(f"source {source_id} deletion_obligations must be a non-empty list")
    if not inventory.get("sources"):
        failures.append("source inventory must contain at least one approved source record or fixture")
    return failures


def validate_retention_policy(policy: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    stores = {store.get("store") for store in policy.get("stores", [])}
    missing_stores = sorted(REQUIRED_STORES - stores)
    if missing_stores:
        failures.append(f"retention policy missing stores: {', '.join(missing_stores)}")
    for store in policy.get("stores", []):
        name = store.get("store", "<missing>")
        for key in ["classification", "retention_days", "deletion_action", "backup_retention_days", "owner"]:
            if key not in store or store.get(key) in ("", None):
                failures.append(f"{name} missing {key}")
        if not isinstance(store.get("retention_days"), int) or store.get("retention_days") < 0:
            failures.append(f"{name} retention_days must be a non-negative integer")
        if not isinstance(store.get("backup_retention_days"), int) or store.get("backup_retention_days") < 0:
            failures.append(f"{name} backup_retention_days must be a non-negative integer")
    if policy.get("subprocessors_required_before_launch") is not True:
        failures.append("subprocessors_required_before_launch must remain true until external approval is attached")
    return failures


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures = validate_source_inventory(load_json(root / "governance/source-inventory.json"))
    failures.extend(validate_retention_policy(load_json(root / "governance/retention-policy.json")))
    if failures:
        print("Governance validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Governance validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
