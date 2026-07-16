#!/usr/bin/env python3
"""Validate the repository-owned single-server k3s deployment contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMUNITY = Path("infrastructure/kubernetes/helm/signalchord-community")
APPLICATION_VALUES = Path("infrastructure/kubernetes/helm/signalchord/values-single-server.yaml")
REQUIRED = (
    COMMUNITY / "Chart.yaml",
    COMMUNITY / "values.yaml",
    COMMUNITY / "templates/kafka.yaml",
    COMMUNITY / "templates/postgres.yaml",
    COMMUNITY / "templates/neo4j.yaml",
    COMMUNITY / "templates/valkey.yaml",
    COMMUNITY / "templates/minio.yaml",
    COMMUNITY / "templates/opensearch.yaml",
    COMMUNITY / "templates/observability.yaml",
    COMMUNITY / "templates/init-jobs.yaml",
    APPLICATION_VALUES,
    Path("infrastructure/kubernetes/single-server/runtime.env.example"),
    Path("scripts/single-server/render_digest_values.py"),
    Path("scripts/single-server/test_render_digest_values.py"),
    Path("scripts/single-server/install.sh"),
    Path("scripts/single-server/health.sh"),
    Path("scripts/single-server/update.sh"),
    Path("scripts/single-server/rollback.sh"),
)
IMAGE_LINE = re.compile(r"^\s{2}[A-Za-z][A-Za-z0-9]*:\s+(\S+)\s*$")


def read(root: Path, relative: Path) -> str:
    return (root / relative).read_text(encoding="utf-8")


def validate(root: Path = ROOT) -> None:
    failures: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            failures.append(f"missing single-server file: {relative}")
    if failures:
        fail(failures)

    values = read(root, COMMUNITY / "values.yaml")
    in_images = False
    image_count = 0
    for line in values.splitlines():
        if line == "images:":
            in_images = True
            continue
        if in_images and line and not line.startswith("  "):
            in_images = False
        if not in_images:
            continue
        match = IMAGE_LINE.match(line)
        if not match:
            continue
        image_count += 1
        reference = match.group(1)
        if reference.endswith(":latest") or ":" not in reference.rsplit("/", 1)[-1]:
            failures.append(f"community image must use an explicit non-latest version: {reference}")
    if image_count < 9:
        failures.append("community values must define every stateful and observability image")

    templates = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((root / COMMUNITY / "templates").glob("*.yaml"))
    )
    for forbidden in ("type: LoadBalancer", "type: NodePort", "hostPort:", "hostNetwork: true"):
        if forbidden in templates:
            failures.append(f"community chart must not expose dependency services: {forbidden}")
    for service in ("kafka", "postgres", "neo4j", "valkey", "minio", "opensearch"):
        if f"name: {service}" not in templates:
            failures.append(f"community chart is missing service/stateful workload: {service}")
    if "replicas: 1" not in templates:
        failures.append("community chart must remain explicitly single-node")

    app = read(root, APPLICATION_VALUES)
    markers = (
        "environment: staging",
        "externalSecret:\n  enabled: false",
        "className: traefik",
        "ingressNamespace: kube-system",
        "kafkaBrokers: kafka:9092",
        "redisUrl: redis://valkey:6379/0",
        "opensearchUrl: http://opensearch:9200",
        "neo4jUri: neo4j://neo4j:7687",
    )
    for marker in markers:
        if marker not in app:
            failures.append(f"single-server values missing required setting: {marker}")
    if "localhost" in app or "127.0.0.1" in app:
        failures.append("single-server Kubernetes values must not use loopback endpoints")
    if app.count("replicas: 1") < 10:
        failures.append("every SignalChord workload must default to one replica on one node")

    runtime = read(root, Path("infrastructure/kubernetes/single-server/runtime.env.example"))
    for key in (
        "POSTGRES_PASSWORD",
        "SECRET_KEY_BASE",
        "CONTROL_PLANE_INTERNAL_TOKEN",
        "NEO4J_PASSWORD",
        "MINIO_SECRET_KEY",
        "GRAFANA_ADMIN_PASSWORD",
    ):
        if f"{key}=<" not in runtime:
            failures.append(f"runtime template must keep {key} as a non-secret placeholder")
    for forbidden in ("signalchord-dev", "replace-me", "password123"):
        if forbidden in runtime:
            failures.append(f"runtime template contains a development credential: {forbidden}")

    install = read(root, Path("scripts/single-server/install.sh"))
    for marker in (
        "render_digest_values.py",
        "mode 0600",
        "pod-security.kubernetes.io/enforce=restricted",
        "helm upgrade --install signalchord-community",
        "helm upgrade --install signalchord",
        "health.sh",
    ):
        if marker not in install:
            failures.append(f"installer missing fail-closed behavior: {marker}")

    if failures:
        fail(failures)
    print(f"validated {len(REQUIRED)} single-server deployment files")


def fail(failures: list[str]) -> None:
    print("single-server deployment validation failed:", file=sys.stderr)
    print("\n".join(f"- {entry}" for entry in failures), file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    validate()
