from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from urllib.parse import urlparse

LOCAL_INTERNAL_TOKEN = "signalchord-local-internal"
DEV_MINIO_ACCESS_KEY = "signalchord"
DEV_MINIO_SECRET_KEY = "signalchord-dev-secret"
DEV_NEO4J_PASSWORD = "signalchord-dev"


def kafka_config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {"bootstrap.servers": os.getenv("KAFKA_BROKERS", "localhost:29092")}
    if _truthy(os.getenv("KAFKA_TLS_ENABLED")):
        config["security.protocol"] = "SASL_SSL" if _truthy(os.getenv("KAFKA_SASL_ENABLED")) else "SSL"
        if ca := os.getenv("KAFKA_TLS_CA_PEM"):
            config["ssl.ca.pem"] = ca
    if _truthy(os.getenv("KAFKA_SASL_ENABLED")):
        config.setdefault("security.protocol", "SASL_PLAINTEXT")
        config["sasl.username"] = os.getenv("KAFKA_SASL_USER", "")
        config["sasl.password"] = os.getenv("KAFKA_SASL_PASSWORD", "")
        config["sasl.mechanisms"] = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN")
    config.update(overrides)
    return config


def validate_production_config(requirements: Iterable[str], env: Mapping[str, str] | None = None) -> None:
    data = env or os.environ
    if data.get("SIGNALCHORD_ENV", "").lower() != "production":
        return
    checks = {
        "kafka": _check_kafka,
        "minio": _check_minio,
        "opensearch": _check_opensearch,
        "neo4j": _check_neo4j,
        "redis": _check_redis,
        "control_plane": _check_control_plane,
        "internal_token": _check_internal_token,
    }
    errors: list[str] = []
    for requirement in requirements:
        try:
            checks[requirement](data)
        except ValueError as exc:
            errors.append(f"{requirement}: {exc}")
    if errors:
        raise RuntimeError("insecure production configuration: " + "; ".join(errors))


def _check_kafka(env: Mapping[str, str]) -> None:
    brokers = [broker.strip() for broker in env.get("KAFKA_BROKERS", "").split(",") if broker.strip()]
    if not brokers:
        raise ValueError("KAFKA_BROKERS is required")
    if any(_is_local_url_or_host(broker) for broker in brokers):
        raise ValueError("KAFKA_BROKERS cannot contain localhost or loopback addresses")
    if not _truthy(env.get("KAFKA_TLS_ENABLED")):
        raise ValueError("KAFKA_TLS_ENABLED must be true")
    if not _truthy(env.get("KAFKA_SASL_ENABLED")):
        raise ValueError("KAFKA_SASL_ENABLED must be true")
    if not env.get("KAFKA_SASL_USER") or not env.get("KAFKA_SASL_PASSWORD"):
        raise ValueError("KAFKA_SASL_USER and KAFKA_SASL_PASSWORD are required")


def _check_minio(env: Mapping[str, str]) -> None:
    endpoint = env.get("MINIO_ENDPOINT", "")
    if not endpoint:
        raise ValueError("MINIO_ENDPOINT is required")
    if _is_local_url_or_host(endpoint):
        raise ValueError("MINIO_ENDPOINT cannot point at localhost")
    if not _truthy(env.get("MINIO_SECURE")):
        raise ValueError("MINIO_SECURE must be true")
    if env.get("MINIO_ACCESS_KEY") in {"", DEV_MINIO_ACCESS_KEY}:
        raise ValueError("MINIO_ACCESS_KEY must be a managed secret")
    if env.get("MINIO_SECRET_KEY") in {"", DEV_MINIO_SECRET_KEY}:
        raise ValueError("MINIO_SECRET_KEY must be a managed secret")


def _check_opensearch(env: Mapping[str, str]) -> None:
    value = env.get("OPENSEARCH_URL", "")
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise ValueError("OPENSEARCH_URL must use https://")
    if _is_local_url_or_host(value):
        raise ValueError("OPENSEARCH_URL cannot point at localhost")
    if not _truthy(env.get("OPENSEARCH_VERIFY_CERTS")):
        raise ValueError("OPENSEARCH_VERIFY_CERTS must be true")


def _check_neo4j(env: Mapping[str, str]) -> None:
    value = env.get("NEO4J_URI", "")
    parsed = urlparse(value)
    if parsed.scheme not in {"neo4j+s", "bolt+s"}:
        raise ValueError("NEO4J_URI must use neo4j+s:// or bolt+s://")
    if _is_local_url_or_host(value):
        raise ValueError("NEO4J_URI cannot point at localhost")
    if env.get("NEO4J_PASSWORD") in {"", DEV_NEO4J_PASSWORD}:
        raise ValueError("NEO4J_PASSWORD must be a managed secret")


def _check_redis(env: Mapping[str, str]) -> None:
    if not env.get("REDIS_URL", "").startswith("rediss://"):
        raise ValueError("REDIS_URL must use rediss://")


def _check_control_plane(env: Mapping[str, str]) -> None:
    value = env.get("CONTROL_PLANE_URL", "")
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise ValueError("CONTROL_PLANE_URL must use https://")
    if _is_local_url_or_host(value):
        raise ValueError("CONTROL_PLANE_URL cannot point at localhost")


def _check_internal_token(env: Mapping[str, str]) -> None:
    value = env.get("CONTROL_PLANE_INTERNAL_TOKEN", "")
    if value == LOCAL_INTERNAL_TOKEN or len(value) < 32:
        raise ValueError("CONTROL_PLANE_INTERNAL_TOKEN must be a managed secret")


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() == "true"


def _is_local_url_or_host(value: str) -> bool:
    parsed = urlparse(value if "://" in value else f"scheme://{value}")
    host = (parsed.hostname or value.split(":", 1)[0]).strip("[]").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "::"}
