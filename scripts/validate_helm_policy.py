#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


IMMUTABLE_IMAGE = re.compile(r"^\s*image:\s+\"?ghcr\.io/pepitodrop/[a-z0-9-]+:sha-[0-9a-f]{7,40}\"?\s*$")
MUTABLE_IMAGE = re.compile(r"^\s*image:\s+.+:(latest|main|master|dev|sha-required)\"?\s*$")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--environment", choices=["default", "staging", "production"], default="default")
    args = parser.parse_args()
    text = args.manifest.read_text(encoding="utf-8")
    failures: list[str] = []

    forbidden = ["localhost", "127.0.0.1", "http://", "redis://", "neo4j://", "sha-required"]
    for value in forbidden:
        if value in text:
            failures.append(f"rendered manifest contains forbidden production value {value!r}")

    required_fragments = [
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
    ]
    for fragment in required_fragments:
        if fragment not in text:
            failures.append(f"rendered manifest is missing {fragment!r}")

    image_lines = [line for line in text.splitlines() if line.strip().startswith("image:")]
    if not image_lines:
        failures.append("rendered manifest has no container images")
    for line in image_lines:
        if MUTABLE_IMAGE.match(line):
            failures.append(f"mutable image reference rejected: {line.strip()}")
        if args.environment in {"staging", "production"} and not IMMUTABLE_IMAGE.match(line):
            failures.append(f"{args.environment} image must use a digest-backed sha tag: {line.strip()}")

    if "serviceAccountName: signalchord\n" in text:
        failures.append("workloads must use per-workload service accounts, not the shared base name")

    if args.environment == "production":
        if "SIGNALCHORD_ENV, value: \"production\"" not in text:
            failures.append("production manifests must render SIGNALCHORD_ENV=production")
        if "secretName: signalchord-production-tls" not in text:
            failures.append("production ingress must use the production TLS secret")
    if args.environment == "staging":
        if "SIGNALCHORD_ENV, value: \"staging\"" not in text:
            failures.append("staging manifests must render SIGNALCHORD_ENV=staging")
        if "secretName: signalchord-staging-tls" not in text:
            failures.append("staging ingress must use the staging TLS secret")

    if failures:
        for failure in failures:
            print(f"helm policy failure: {failure}", file=sys.stderr)
        return 1
    print(f"helm policy validation passed for {args.environment}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
