#!/usr/bin/env python3

from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import validate_single_server


ROOT = Path(__file__).resolve().parents[1]


class SingleServerValidatorTest(unittest.TestCase):
    def fixture(self, target: Path) -> None:
        for relative in validate_single_server.REQUIRED:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def assert_fails(self, root: Path) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            validate_single_server.validate(root)

    def test_repository_validates(self) -> None:
        validate_single_server.validate()

    def test_latest_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            values = root / validate_single_server.COMMUNITY / "values.yaml"
            values.write_text(values.read_text().replace("apache/kafka:4.3.0", "apache/kafka:latest"), encoding="utf-8")
            self.assert_fails(root)

    def test_public_dependency_service_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            template = root / validate_single_server.COMMUNITY / "templates/postgres.yaml"
            template.write_text(template.read_text() + "\nspec:\n  type: NodePort\n", encoding="utf-8")
            self.assert_fails(root)

    def test_loopback_application_endpoint_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            values = root / validate_single_server.APPLICATION_VALUES
            values.write_text(values.read_text().replace("kafka:9092", "localhost:9092"), encoding="utf-8")
            self.assert_fails(root)

    def test_development_runtime_password_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            runtime = root / "infrastructure/kubernetes/single-server/runtime.env.example"
            runtime.write_text(runtime.read_text().replace("<generate-unique-value>", "signalchord-dev", 1), encoding="utf-8")
            self.assert_fails(root)


if __name__ == "__main__":
    unittest.main()
