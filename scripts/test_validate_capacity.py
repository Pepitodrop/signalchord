#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest
from pathlib import Path

import validate_capacity


ROOT = Path(__file__).resolve().parents[1]


class CapacityValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = validate_capacity.load_json(ROOT / "load/scenarios/signalchord-capacity-v1.json")
        self.result = validate_capacity.load_json(ROOT / "load/results/repository-smoke.json")

    def test_repository_scenario_and_result_are_valid(self) -> None:
        self.assertEqual([], validate_capacity.validate_scenario(self.scenario))
        self.assertEqual([], validate_capacity.validate_result(self.scenario, self.result))

    def test_result_fails_when_threshold_is_exceeded(self) -> None:
        bad = copy.deepcopy(self.result)
        bad["metrics"]["control_plane_api"]["p95_latency_ms"] = 999999

        failures = validate_capacity.validate_result(self.scenario, bad)

        self.assertTrue(any("control_plane_api.p95_latency_ms" in failure for failure in failures))

    def test_scenario_requires_degraded_dependency_profile(self) -> None:
        bad = copy.deepcopy(self.scenario)
        bad["profiles"] = [profile for profile in bad["profiles"] if profile["name"] != "degraded-dependency"]

        failures = validate_capacity.validate_scenario(bad)

        self.assertTrue(any("degraded-dependency" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
