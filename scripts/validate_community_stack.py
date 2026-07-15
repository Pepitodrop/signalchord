#!/usr/bin/env python3
"""Validate that the verified community runtime has no mandatory paid services."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = (
    Path("docker-compose.yml"),
    Path("docker-compose.override.yml"),
    Path("docker-compose.projector.yml"),
)

FORBIDDEN_PATTERNS = {
    "Confluent container image": re.compile(r"\bconfluentinc/", re.IGNORECASE),
    "Schema Registry service or setting": re.compile(
        r"\b(?:schema-registry|SCHEMA_REGISTRY(?:_URL)?)\b", re.IGNORECASE
    ),
    "Kafka Connect service": re.compile(r"\bkafka-connect\b", re.IGNORECASE),
    "Redis server image": re.compile(r"^\s*image:\s*redis(?:/redis)?:", re.IGNORECASE | re.MULTILINE),
    "paid LLM API key": re.compile(
        r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|COHERE_API_KEY|GEMINI_API_KEY)\b"
    ),
}

REQUIRED_PATTERNS = {
    "official Apache Kafka image": re.compile(r"^\s*image:\s*apache/kafka:", re.MULTILINE),
    "Valkey image": re.compile(r"^\s*image:\s*valkey/valkey:", re.MULTILINE),
    "Valkey application endpoint": re.compile(r"redis://valkey:6379"),
}


def validate(root: Path = ROOT) -> None:
    failures: list[str] = []
    combined = []

    for relative in COMPOSE_FILES:
        path = root / relative
        if not path.exists():
            failures.append(f"missing required Compose file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        combined.append(f"\n# {relative}\n{text}")

        for description, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{relative}: contains forbidden {description}")

    compose_text = "".join(combined)
    for description, pattern in REQUIRED_PATTERNS.items():
        if not pattern.search(compose_text):
            failures.append(f"community stack is missing {description}")

    removed_connect = root / "infrastructure/docker/connect/Dockerfile"
    if removed_connect.exists():
        failures.append(
            "infrastructure/docker/connect/Dockerfile reintroduces the optional Confluent connector runtime"
        )

    community_doc = root / "docs/community-self-hosting.md"
    if not community_doc.exists():
        failures.append("missing docs/community-self-hosting.md")

    if failures:
        print("community stack validation failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        raise SystemExit(1)

    print("validated no-mandatory-paid-service community runtime")


if __name__ == "__main__":
    validate()
