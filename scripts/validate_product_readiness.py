#!/usr/bin/env python3
"""Validate repository-side product readiness evidence for issue #32."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "product" / "readiness-checklist.json"
REQUIRED_CONTROLS = {
    "authentication_sessions",
    "tenant_onboarding_invitations",
    "rbac_membership_administration",
    "usage_limits_and_billing_state",
    "support_intake",
    "notification_invalid_token_handling",
    "export_and_deletion_request_api",
}
REQUIRED_BLOCKERS = {
    "production_email_delivery",
    "mfa_decision_and_provider",
    "mobile_signing_and_push_credentials",
    "billing_provider_integration",
    "terms_privacy_acceptable_use",
    "representative_customer_acceptance",
}


def fail(message: str) -> None:
    print(f"product readiness validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"{path.relative_to(ROOT)} is missing")
    except json.JSONDecodeError as error:
        fail(f"{path.relative_to(ROOT)} is invalid JSON: {error}")


def validate() -> None:
    data = load_json(CHECKLIST)
    if data.get("schema_version") != 1:
        fail("schema_version must be 1")
    if data.get("track") != "issue-32-product-operations-readiness":
        fail("track must identify issue #32")

    controls = data.get("repository_controls")
    if not isinstance(controls, list) or not controls:
        fail("repository_controls must be a non-empty list")
    by_name = {item.get("control"): item for item in controls if isinstance(item, dict)}
    missing = sorted(REQUIRED_CONTROLS - set(by_name))
    if missing:
        fail(f"missing controls: {', '.join(missing)}")
    for name in sorted(REQUIRED_CONTROLS):
        item = by_name[name]
        if item.get("status") != "implemented":
            fail(f"{name} status must be implemented")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            fail(f"{name} must list evidence files")
        for relative in evidence:
            path = ROOT / relative
            if not path.is_file():
                fail(f"{name} evidence path does not exist: {relative}")

    blockers = data.get("external_blockers")
    if not isinstance(blockers, list) or not blockers:
        fail("external_blockers must be a non-empty list")
    blockers_by_name = {item.get("blocker"): item for item in blockers if isinstance(item, dict)}
    missing_blockers = sorted(REQUIRED_BLOCKERS - set(blockers_by_name))
    if missing_blockers:
        fail(f"missing external blockers: {', '.join(missing_blockers)}")
    for name in sorted(REQUIRED_BLOCKERS):
        evidence = blockers_by_name[name].get("required_evidence")
        if not isinstance(evidence, str) or len(evidence.strip()) < 40:
            fail(f"{name} must describe required external evidence")


if __name__ == "__main__":
    validate()
