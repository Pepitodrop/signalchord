#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


DIGEST_IMAGE = re.compile(
    r'^\s*image:\s+"?ghcr\.io/pepitodrop/[a-z0-9-]+@sha256:[0-9a-f]{64}"?\s*$'
)
SHA_TAG_IMAGE = re.compile(
    r'^\s*image:\s+"?ghcr\.io/pepitodrop/[a-z0-9-]+:sha-[0-9a-f]{7,40}"?\s*$'
)
MUTABLE_IMAGE = re.compile(r'^\s*image:\s+.+:(latest|main|master|dev|sha-required|digest-required)"?\s*$')

STANDARD_REQUIRED_FRAGMENTS = [
    "kind: ExternalSecret",
    "kind: ResourceQuota",
    "kind: NetworkPolicy",
    "name: signalchord-default-deny",
    "kind: Ingress",
    "tls:",
    "kind: PodDisruptionBudget",
    "runAsNonRoot: true",
    "runAsUser: 10001",
    "runAsGroup: 10001",
    "allowPrivilegeEscalation: false",
    "privileged: false",
    "readOnlyRootFilesystem: true",
    "drop: [ALL]",
    "seccompProfile: {type: RuntimeDefault}",
    "automountServiceAccountToken: false",
    "requests:",
    "limits:",
    "revisionHistoryLimit:",
    "minReadySeconds:",
    "maxUnavailable: 0",
    "name: API_RATE_LIMIT",
    "name: AUTH_RATE_LIMIT",
    "name: API_MAX_BODY_BYTES",
    'nginx.ingress.kubernetes.io/proxy-body-size: "1m"',
    'nginx.ingress.kubernetes.io/proxy-connect-timeout: "5"',
    'nginx.ingress.kubernetes.io/proxy-send-timeout: "60"',
    'nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"',
]

SINGLE_SERVER_REQUIRED_FRAGMENTS = [
    "kind: NetworkPolicy",
    "name: signalchord-default-deny",
    "name: signalchord-ingress-controller",
    "kind: Ingress",
    "tls:",
    "secretName: signalchord-ingress-tls",
    "runAsNonRoot: true",
    "runAsUser: 10001",
    "runAsGroup: 10001",
    "allowPrivilegeEscalation: false",
    "privileged: false",
    "readOnlyRootFilesystem: true",
    "drop: [ALL]",
    "seccompProfile: {type: RuntimeDefault}",
    "automountServiceAccountToken: false",
    "requests:",
    "limits:",
    "revisionHistoryLimit:",
    "minReadySeconds:",
    "name: API_RATE_LIMIT",
    "name: AUTH_RATE_LIMIT",
    "name: API_MAX_BODY_BYTES",
    "KAFKA_BROKERS, value: kafka:9092",
    "REDIS_URL, value: redis://valkey:6379/0",
    "MINIO_ENDPOINT, value: minio:9000",
    "OPENSEARCH_URL, value: http://opensearch:9200",
    "NEO4J_URI, value: neo4j://neo4j:7687",
]


def validate_image_references(text: str, environment: str) -> list[str]:
    failures: list[str] = []
    image_lines = [line for line in text.splitlines() if line.strip().startswith("image:")]
    if not image_lines:
        return ["rendered manifest has no container images"]

    for line in image_lines:
        rendered = line.strip()
        if MUTABLE_IMAGE.match(line):
            failures.append(f"mutable image reference rejected: {rendered}")
            continue
        if environment in {"production", "single-server"} and not DIGEST_IMAGE.match(line):
            failures.append(f"{environment} image must use an immutable sha256 digest: {rendered}")
        elif environment == "staging" and not (DIGEST_IMAGE.match(line) or SHA_TAG_IMAGE.match(line)):
            failures.append(f"staging image must use a sha tag or immutable sha256 digest: {rendered}")

    return failures


def validate_manifest(text: str, environment: str) -> list[str]:
    failures: list[str] = []

    forbidden = ["localhost", "127.0.0.1", "sha-required", "digest-required"]
    if environment != "single-server":
        forbidden.extend(["http://", "redis://", "neo4j://"])
    for value in forbidden:
        if value in text:
            failures.append(f"rendered manifest contains forbidden {environment} value {value!r}")

    required_fragments = (
        SINGLE_SERVER_REQUIRED_FRAGMENTS if environment == "single-server" else STANDARD_REQUIRED_FRAGMENTS
    )
    for fragment in required_fragments:
        if fragment not in text:
            failures.append(f"rendered manifest is missing {fragment!r}")

    failures.extend(validate_image_references(text, environment))

    if "serviceAccountName: signalchord\n" in text:
        failures.append("workloads must use per-workload service accounts, not the shared base name")

    if environment == "production":
        if 'SIGNALCHORD_ENV, value: "production"' not in text:
            failures.append("production manifests must render SIGNALCHORD_ENV=production")
        if "secretName: signalchord-production-tls" not in text:
            failures.append("production ingress must use the production TLS secret")
    elif environment == "staging":
        if 'SIGNALCHORD_ENV, value: "staging"' not in text:
            failures.append("staging manifests must render SIGNALCHORD_ENV=staging")
        if "secretName: signalchord-staging-tls" not in text:
            failures.append("staging ingress must use the staging TLS secret")
    elif environment == "single-server":
        if 'SIGNALCHORD_ENV, value: "staging"' not in text:
            failures.append("single-server manifests must use the documented staging application mode")
        for forbidden_kind in ("kind: ExternalSecret", "kind: ResourceQuota", "kind: PodDisruptionBudget"):
            if forbidden_kind in text:
                failures.append(f"single-server manifest must not render {forbidden_kind!r}")
        if "ingressClassName: traefik" not in text:
            failures.append("single-server ingress must use the k3s Traefik ingress class")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--environment",
        choices=["default", "staging", "production", "single-server"],
        default="default",
    )
    args = parser.parse_args()
    text = args.manifest.read_text(encoding="utf-8")
    failures = validate_manifest(text, args.environment)

    if failures:
        for failure in failures:
            print(f"helm policy failure: {failure}", file=sys.stderr)
        return 1
    print(f"helm policy validation passed for {args.environment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
