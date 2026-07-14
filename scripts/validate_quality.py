#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_STAGES = {"extraction", "entity_resolution", "claim_linking", "alert_quality"}
REQUIRED_COVERAGE = {"languages", "source_types", "risk_levels"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_plan(plan: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not plan.get("intended_use"):
        failures.append("plan must document intended_use")
    if not plan.get("prohibited_uses"):
        failures.append("plan must document prohibited_uses")
    stages = plan.get("critical_stages", {})
    missing = REQUIRED_STAGES - set(stages)
    if missing:
        failures.append(f"plan missing critical stages: {', '.join(sorted(missing))}")
    for stage, config in stages.items():
        if not config.get("metrics"):
            failures.append(f"{stage} must define metric thresholds")
        if not config.get("regression_budget"):
            failures.append(f"{stage} must define regression_budget")
        for metric, threshold in config.get("metrics", {}).items():
            if not isinstance(threshold, (int, float)) or threshold <= 0 or threshold > 1:
                failures.append(f"{stage}.{metric} threshold must be between 0 and 1")
    if not plan.get("human_review_rules"):
        failures.append("plan must define human_review_rules")
    if not plan.get("monitoring", {}).get("rollback_criteria"):
        failures.append("plan must define rollback_criteria")
    return failures


def validate_dataset(dataset: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    rights = dataset.get("rights", {})
    if rights.get("status") != "repository_owned" and not rights.get("legal_approval"):
        failures.append("dataset must be repository-owned or include legal_approval")
    if rights.get("third_party_text") is not False:
        failures.append("repository fixture must not contain third_party_text")
    split = dataset.get("train_test_split", {})
    train_ids = set(split.get("train_ids", []))
    test_ids = set(split.get("test_ids", []))
    if train_ids & test_ids:
        failures.append("train and test ids must be disjoint")
    if not test_ids:
        failures.append("dataset must define test_ids")
    for coverage in REQUIRED_COVERAGE:
        if not dataset.get("coverage", {}).get(coverage):
            failures.append(f"dataset missing coverage.{coverage}")
    for case in dataset.get("cases", []):
        if case.get("split") == "test" and case.get("id") not in test_ids:
            failures.append(f"test case {case.get('id')} missing from train_test_split.test_ids")
        if case.get("risk_level") == "high" and not case.get("expected", {}).get("requires_human_review"):
            failures.append(f"high-risk case {case.get('id')} must require human review")
    return failures


def validate_results(plan: dict[str, Any], dataset: dict[str, Any], results: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if results.get("dataset_id") != dataset.get("dataset_id"):
        failures.append("result dataset_id must match dataset")
    metrics = results.get("metrics", {})
    for stage, config in plan.get("critical_stages", {}).items():
        stage_metrics = metrics.get(stage, {})
        for metric, threshold in config.get("metrics", {}).items():
            value = stage_metrics.get(metric)
            if not isinstance(value, (int, float)):
                failures.append(f"missing result metric {stage}.{metric}")
            elif value < threshold:
                failures.append(f"{stage}.{metric}={value} below threshold {threshold}")
    result_coverage = results.get("coverage", {})
    for coverage in REQUIRED_COVERAGE:
        if not result_coverage.get(coverage):
            failures.append(f"results missing coverage.{coverage}")
    approval = results.get("approval", {})
    if approval.get("approved_for_production") is True:
        failures.append("repository baseline must not claim production approval")
    if not approval.get("required_external_evidence"):
        failures.append("results must list required_external_evidence")
    return failures


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    plan = load_json(root / "quality/evaluation-plan.json")
    dataset = load_json(root / "quality/datasets/synthetic-fixture-v1.json")
    results = load_json(root / "quality/results/repository-baseline.json")
    failures = validate_plan(plan)
    failures.extend(validate_dataset(dataset))
    failures.extend(validate_results(plan, dataset, results))
    if failures:
        print("Quality validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("Quality validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
