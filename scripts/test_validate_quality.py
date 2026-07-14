#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("validate_quality.py")
SPEC = importlib.util.spec_from_file_location("validate_quality", MODULE_PATH)
validator = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(validator)


def test_plan_requires_all_critical_stages_and_review_rules() -> None:
    failures = validator.validate_plan({"critical_stages": {"extraction": {"metrics": {}}}})

    assert any("missing critical stages" in failure for failure in failures)
    assert any("human_review_rules" in failure for failure in failures)


def test_dataset_requires_rights_split_and_high_risk_review() -> None:
    failures = validator.validate_dataset(
        {
            "rights": {"status": "unknown", "third_party_text": True},
            "train_test_split": {"train_ids": ["case-1"], "test_ids": ["case-1"]},
            "coverage": {"languages": ["en"]},
            "cases": [{"id": "case-1", "split": "test", "risk_level": "high", "expected": {"requires_human_review": False}}],
        }
    )

    assert any("legal_approval" in failure for failure in failures)
    assert any("third_party_text" in failure for failure in failures)
    assert any("disjoint" in failure for failure in failures)
    assert any("high-risk" in failure for failure in failures)


def test_results_fail_below_threshold_and_production_claim() -> None:
    plan = {"critical_stages": {"extraction": {"metrics": {"precision": 0.9}}}}
    dataset = {"dataset_id": "dataset-1"}
    results = {
        "dataset_id": "dataset-1",
        "metrics": {"extraction": {"precision": 0.5}},
        "approval": {"approved_for_production": True},
    }

    failures = validator.validate_results(plan, dataset, results)

    assert any("below threshold" in failure for failure in failures)
    assert any("must not claim production approval" in failure for failure in failures)
