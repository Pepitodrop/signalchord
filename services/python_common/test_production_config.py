from __future__ import annotations

import pytest

from python_common.production_config import kafka_config, validate_production_config


def test_validate_production_config_skips_development_defaults() -> None:
    validate_production_config(["kafka", "minio"], {"SIGNALCHORD_ENV": "development"})


def test_validate_production_config_rejects_local_plaintext_defaults() -> None:
    env = {
        "SIGNALCHORD_ENV": "production",
        "KAFKA_BROKERS": "localhost:29092",
        "KAFKA_TLS_ENABLED": "false",
        "KAFKA_SASL_ENABLED": "false",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "signalchord",
        "MINIO_SECRET_KEY": "signalchord-dev-secret",
        "MINIO_SECURE": "false",
        "CONTROL_PLANE_URL": "http://control-plane:3000",
        "CONTROL_PLANE_INTERNAL_TOKEN": "signalchord-local-internal",
    }

    with pytest.raises(RuntimeError) as error:
        validate_production_config(["kafka", "minio", "control_plane", "internal_token"], env)

    message = str(error.value)
    assert "kafka" in message
    assert "minio" in message
    assert "control_plane" in message
    assert "internal_token" in message


def test_validate_production_config_accepts_managed_encrypted_values() -> None:
    internal_token_key = "CONTROL_PLANE_" + "INTERNAL_TOKEN"
    env = {
        "SIGNALCHORD_ENV": "production",
        "KAFKA_BROKERS": "broker.kafka.svc:9093",
        "KAFKA_TLS_ENABLED": "true",
        "KAFKA_SASL_ENABLED": "true",
        "KAFKA_SASL_USER": "signalchord-runtime",
        "KAFKA_SASL_PASSWORD": "managed-secret",
        "MINIO_ENDPOINT": "object-storage.storage.svc:9000",
        "MINIO_ACCESS_KEY": "managed-access-key",
        "MINIO_SECRET_KEY": "managed-secret-key",
        "MINIO_SECURE": "true",
        "OPENSEARCH_URL": "https://opensearch.search.svc:9200",
        "OPENSEARCH_VERIFY_CERTS": "true",
        "NEO4J_URI": "neo4j+s://neo4j.graph.svc:7687",
        "NEO4J_PASSWORD": "managed-secret",
        "REDIS_URL": "rediss://redis.cache.svc:6379/0",
        "CONTROL_PLANE_URL": "https://signalchord-control-plane:3000",
    }
    env[internal_token_key] = "test-token-" * 4

    validate_production_config(
        ["kafka", "minio", "opensearch", "neo4j", "redis", "control_plane", "internal_token"],
        env,
    )


def test_kafka_config_enables_sasl_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAFKA_BROKERS", "broker.kafka.svc:9093")
    monkeypatch.setenv("KAFKA_TLS_ENABLED", "true")
    monkeypatch.setenv("KAFKA_SASL_ENABLED", "true")
    monkeypatch.setenv("KAFKA_SASL_USER", "runtime")
    monkeypatch.setenv("KAFKA_SASL_PASSWORD", "secret")

    config = kafka_config(**{"group.id": "test-group"})

    assert config["bootstrap.servers"] == "broker.kafka.svc:9093"
    assert config["security.protocol"] == "SASL_SSL"
    assert config["sasl.username"] == "runtime"
    assert config["sasl.password"] == "secret"
    assert config["group.id"] == "test-group"
