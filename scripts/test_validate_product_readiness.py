#!/usr/bin/env python3
"""Failure-covering tests for validate_product_readiness.py."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

import validate_product_readiness


class ProductReadinessValidatorTest(unittest.TestCase):
    def test_repository_contract_validates(self) -> None:
        validate_product_readiness.validate()

    def test_missing_control_fails(self) -> None:
        original = json.loads(validate_product_readiness.CHECKLIST.read_text(encoding="utf-8"))
        original["repository_controls"] = [
            item for item in original["repository_controls"] if item["control"] != "support_intake"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checklist = root / "product" / "readiness-checklist.json"
            checklist.parent.mkdir(parents=True)
            checklist.write_text(json.dumps(original), encoding="utf-8")
            with mock.patch.object(validate_product_readiness, "ROOT", root), \
                 mock.patch.object(validate_product_readiness, "CHECKLIST", checklist), \
                 redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    validate_product_readiness.validate()

    def test_missing_external_blocker_fails(self) -> None:
        original = json.loads(validate_product_readiness.CHECKLIST.read_text(encoding="utf-8"))
        original["external_blockers"] = [
            item for item in original["external_blockers"] if item["blocker"] != "billing_provider_integration"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checklist = root / "product" / "readiness-checklist.json"
            checklist.parent.mkdir(parents=True)
            checklist.write_text(json.dumps(original), encoding="utf-8")
            for item in original["repository_controls"]:
                for relative in item["evidence"]:
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            with mock.patch.object(validate_product_readiness, "ROOT", root), \
                 mock.patch.object(validate_product_readiness, "CHECKLIST", checklist), \
                 redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    validate_product_readiness.validate()


if __name__ == "__main__":
    unittest.main()
