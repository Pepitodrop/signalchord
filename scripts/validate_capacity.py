#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_PROFILES = {"expected", "burst", "degraded-dependency"}
REQUIRED_JOURNEYS = {"article_to_alert", "control_plane_api", "realtime_notifications"}
REQUIRED_RESULT_FIELDS = {"scenario_id", "environment", "profile", "started_at", "completed_at", "git_sha", "metrics"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_scenario(scenario: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if scenario.get("schema_version") != 1:
        failures.append("scenario schema_version must be 1")
    if not scenario.get("scenario_id"):
        failures.append("scenario_id is required")

    profiles = scenario.get("profiles")
    if not isinstance(profiles, list):
        failures.append("profiles must be a list")
        profiles = []
    profile_names = {profile.get("name") for profile in profiles if isinstance(profile, dict)}
    missing_profiles = REQUIRED_PROFILES - profile_names
    if missing_profiles:
        failures.append(f"missing required profiles: {', '.join(sorted(missing_profiles))}")

    journeys = scenario.get("critical_journeys")
    if not isinstance(journeys, list):
        failures.append("critical_journeys must be a list")
        journeys = []
    journey_names = {journey.get("name") for journey in journeys if isinstance(journey, dict)}
    missing_journeys = REQUIRED_JOURNEYS - journey_names
    if missing_journeys:
        failures.append(f"missing required journeys: {', '.join(sorted(missing_journeys))}")

    for journey in journeys:
        if not isinstance(journey, dict):
            failures.append("critical_journeys entries must be objects")
            continue
        thresholds = journey.get("thresholds")
        if not isinstance(thresholds, dict):
            failures.append(f"{journey.get('name', '<unknown>')} thresholds must be an object")
            continue
        for metric in ("p95_latency_ms", "error_rate", "cpu_saturation", "memory_saturation"):
            value = thresholds.get(metric)
            if not isinstance(value, (int, float)) or value <= 0:
                failures.append(f"{journey.get('name', '<unknown>')} threshold {metric} must be positive")
        if thresholds.get("error_rate", 1) > 0.05:
            failures.append(f"{journey.get('name', '<unknown>')} error_rate threshold is too loose")

    controls = scenario.get("controls_under_test")
    if not isinstance(controls, dict):
        failures.append("controls_under_test must be an object")
    else:
        for key in ("api_rate_limit_per_minute", "auth_rate_limit_per_5_minutes", "api_max_body_bytes"):
            if not isinstance(controls.get(key), int) or controls[key] <= 0:
                failures.append(f"control {key} must be a positive integer")

    kafka_partitions = scenario.get("capacity_assumptions", {}).get("kafka_partitions")
    if not isinstance(kafka_partitions, dict) or not kafka_partitions:
        failures.append("capacity_assumptions.kafka_partitions must define topic partition counts")
    elif any(not isinstance(value, int) or value < 1 for value in kafka_partitions.values()):
        failures.append("all kafka partition counts must be positive integers")

    return failures


def threshold_map(scenario: dict[str, Any]) -> dict[str, dict[str, float]]:
    journeys = scenario.get("critical_journeys", [])
    return {
        journey["name"]: journey["thresholds"]
        for journey in journeys
        if isinstance(journey, dict) and isinstance(journey.get("thresholds"), dict)
    }


def validate_result(scenario: dict[str, Any], result: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    missing = REQUIRED_RESULT_FIELDS - set(result)
    if missing:
        failures.append(f"result missing fields: {', '.join(sorted(missing))}")
    if result.get("scenario_id") != scenario.get("scenario_id"):
        failures.append("result scenario_id does not match scenario")

    profile_names = {profile.get("name") for profile in scenario.get("profiles", []) if isinstance(profile, dict)}
    if result.get("profile") not in profile_names:
        failures.append(f"result profile {result.get('profile')!r} is not defined in scenario")

    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        failures.append("result metrics must be an object")
        return failures

    thresholds_by_journey = threshold_map(scenario)
    for journey, thresholds in thresholds_by_journey.items():
        observed = metrics.get(journey)
        if not isinstance(observed, dict):
            failures.append(f"result missing metrics for {journey}")
            continue
        for metric, limit in thresholds.items():
            if metric not in observed:
                continue
            value = observed[metric]
            if not isinstance(value, (int, float)):
                failures.append(f"{journey}.{metric} must be numeric")
            elif value > limit:
                failures.append(f"{journey}.{metric}={value} exceeds threshold {limit}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SignalChord capacity scenario definitions and machine-readable load results.")
    parser.add_argument("--scenario", type=Path, default=Path("load/scenarios/signalchord-capacity-v1.json"))
    parser.add_argument("--result", type=Path, action="append", default=[Path("load/results/repository-smoke.json")])
    args = parser.parse_args()

    failures: list[str] = []
    scenario = load_json(args.scenario)
    failures.extend(validate_scenario(scenario))
    for result_path in args.result:
        failures.extend(f"{result_path}: {failure}" for failure in validate_result(scenario, load_json(result_path)))

    if failures:
        for failure in failures:
            print(f"capacity validation failure: {failure}", file=sys.stderr)
        return 1
    print("capacity validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
