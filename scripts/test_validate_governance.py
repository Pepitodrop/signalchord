#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("validate_governance.py")
SPEC = importlib.util.spec_from_file_location("validate_governance", MODULE_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(validator)


def test_source_inventory_requires_approved_owner_and_deletion_policy() -> None:
    failures = validator.validate_source_inventory(
        {
            "sources": [
                {
                    "id": "bad-source",
                    "name": "Bad source",
                    "rights_status": "pending_review",
                    "retention_days": 30,
                    "permitted_uses": [],
                    "deletion_obligations": [],
                }
            ]
        }
    )

    assert any("missing fields" in failure for failure in failures)
    assert any("must be approved" in failure for failure in failures)
    assert any("permitted_uses" in failure for failure in failures)
    assert any("deletion_obligations" in failure for failure in failures)


def test_retention_policy_requires_all_runtime_stores() -> None:
    failures = validator.validate_retention_policy(
        {
            "stores": [
                {
                    "store": "postgresql",
                    "classification": "tenant_metadata",
                    "retention_days": 30,
                    "deletion_action": "delete",
                    "backup_retention_days": 30,
                    "owner": "control-plane",
                }
            ],
            "subprocessors_required_before_launch": True,
        }
    )

    assert any("missing stores" in failure for failure in failures)


def test_retention_policy_keeps_external_subprocessor_gate() -> None:
    failures = validator.validate_retention_policy({"stores": [], "subprocessors_required_before_launch": False})

    assert any("subprocessors_required_before_launch" in failure for failure in failures)
