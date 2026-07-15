#!/usr/bin/env python3
"""Regression tests for the community stack policy."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import validate_community_stack


BASE_COMPOSE = """services:
  kafka:
    image: apache/kafka:4.3.0
  valkey:
    image: valkey/valkey:8.1.3-alpine
  app:
    environment:
      REDIS_URL: redis://valkey:6379/0
"""


class CommunityStackValidatorTest(unittest.TestCase):
    def write_fixture(self, root: Path, compose: str = BASE_COMPOSE) -> None:
        (root / "docker-compose.yml").write_text(compose, encoding="utf-8")
        (root / "docker-compose.override.yml").write_text("services: {}\n", encoding="utf-8")
        (root / "docker-compose.projector.yml").write_text("services: {}\n", encoding="utf-8")
        (root / ".env.example").write_text("REDIS_URL=redis://valkey:6379/0\n", encoding="utf-8")

        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "dev-up.sh").write_text("#!/bin/sh\ndocker compose up kafka valkey\n", encoding="utf-8")
        (scripts / "smoke-test.sh").write_text("#!/bin/sh\necho smoke\n", encoding="utf-8")
        (scripts / "create-topics.sh").write_text(
            "#!/bin/sh\n/opt/kafka/bin/kafka-topics.sh --version\n", encoding="utf-8"
        )

        docs = root / "docs"
        docs.mkdir(parents=True)
        (docs / "community-self-hosting.md").write_text("# Community\n", encoding="utf-8")

    def assert_invalid(self, root: Path) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            validate_community_stack.validate(root)

    def test_repository_stack_validates(self) -> None:
        validate_community_stack.validate()

    def test_community_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root)
            validate_community_stack.validate(root)

    def test_confluent_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root, BASE_COMPOSE + "  old:\n    image: confluentinc/cp-kafka:7.7.1\n")
            self.assert_invalid(root)

    def test_redis_server_image_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root, BASE_COMPOSE + "  old:\n    image: redis:7.4.4-alpine\n")
            self.assert_invalid(root)

    def test_schema_registry_service_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root, BASE_COMPOSE + "  schema-registry:\n    image: example/registry:1\n")
            self.assert_invalid(root)

    def test_stale_schema_registry_smoke_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root)
            (root / "scripts" / "smoke-test.sh").write_text(
                "#!/bin/sh\ncurl http://schema-registry:8081/subjects\n", encoding="utf-8"
            )
            self.assert_invalid(root)

    def test_paid_llm_key_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root, BASE_COMPOSE + "    environment:\n      OPENAI_API_KEY: required\n")
            self.assert_invalid(root)

    def test_missing_valkey_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root, BASE_COMPOSE.replace("valkey/valkey:8.1.3-alpine", "example/cache:1"))
            self.assert_invalid(root)

    def test_missing_runtime_script_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fixture(root)
            (root / "scripts" / "smoke-test.sh").unlink()
            self.assert_invalid(root)


if __name__ == "__main__":
    unittest.main()
