#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest
from pathlib import Path

import validate_recovery


ROOT = Path(__file__).resolve().parents[1]


class RecoveryValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix = validate_recovery.load_json(ROOT / "recovery/recovery-matrix.json")

    def test_repository_recovery_matrix_is_valid(self) -> None:
        self.assertEqual([], validate_recovery.validate_matrix(self.matrix))

    def test_authoritative_store_requires_restore_drill(self) -> None:
        bad = copy.deepcopy(self.matrix)
        bad["authoritative_stores"][0]["restore_drill_required"] = False

        failures = validate_recovery.validate_matrix(bad)

        self.assertTrue(any("restore drills" in failure for failure in failures))

    def test_rollback_requires_immutable_digest(self) -> None:
        bad = copy.deepcopy(self.matrix)
        bad["rollback"]["immutable_digest_required"] = False

        failures = validate_recovery.validate_matrix(bad)

        self.assertTrue(any("immutable digests" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
