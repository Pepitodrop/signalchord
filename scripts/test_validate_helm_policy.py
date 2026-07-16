#!/usr/bin/env python3
"""Focused policy tests for rendered Helm manifests."""

from __future__ import annotations

import unittest

import validate_helm_policy


DIGEST = "sha256:" + "a" * 64


class HelmImagePolicyTest(unittest.TestCase):
    def validate(self, image: str, environment: str) -> list[str]:
        return validate_helm_policy.validate_image_references(f'          image: "{image}"\n', environment)

    def test_production_accepts_sha256_digest(self) -> None:
        self.assertEqual([], self.validate(f"ghcr.io/pepitodrop/signalchord-web@{DIGEST}", "production"))

    def test_production_rejects_commit_sha_tag(self) -> None:
        failures = self.validate("ghcr.io/pepitodrop/signalchord-web:sha-1234567", "production")
        self.assertTrue(any("immutable sha256 digest" in failure for failure in failures))

    def test_staging_accepts_commit_sha_tag(self) -> None:
        self.assertEqual([], self.validate("ghcr.io/pepitodrop/signalchord-web:sha-1234567", "staging"))

    def test_staging_accepts_sha256_digest(self) -> None:
        self.assertEqual([], self.validate(f"ghcr.io/pepitodrop/signalchord-web@{DIGEST}", "staging"))

    def test_single_server_requires_digest(self) -> None:
        failures = self.validate("ghcr.io/pepitodrop/signalchord-web:sha-1234567", "single-server")
        self.assertTrue(any("single-server image must use an immutable sha256 digest" in failure for failure in failures))

    def test_mutable_latest_is_rejected(self) -> None:
        failures = self.validate("ghcr.io/pepitodrop/signalchord-web:latest", "production")
        self.assertTrue(any("mutable image reference" in failure for failure in failures))

    def test_missing_images_are_rejected(self) -> None:
        self.assertEqual(
            ["rendered manifest has no container images"],
            validate_helm_policy.validate_image_references("kind: ConfigMap\n", "production"),
        )


class SingleServerManifestPolicyTest(unittest.TestCase):
    def valid_manifest(self) -> str:
        fragments = list(validate_helm_policy.SINGLE_SERVER_REQUIRED_FRAGMENTS)
        fragments.extend(
            [
                f'image: "ghcr.io/pepitodrop/signalchord-web@{DIGEST}"',
                'SIGNALCHORD_ENV, value: "staging"',
                "ingressClassName: traefik",
                "serviceAccountName: signalchord-web",
            ]
        )
        return "\n".join(fragments) + "\n"

    def test_valid_single_server_manifest_passes(self) -> None:
        self.assertEqual([], validate_helm_policy.validate_manifest(self.valid_manifest(), "single-server"))

    def test_single_server_rejects_loopback(self) -> None:
        failures = validate_helm_policy.validate_manifest(
            self.valid_manifest() + "value: http://localhost:3000\n", "single-server"
        )
        self.assertTrue(any("localhost" in failure for failure in failures))

    def test_single_server_rejects_enterprise_only_resources(self) -> None:
        failures = validate_helm_policy.validate_manifest(
            self.valid_manifest() + "kind: ExternalSecret\n", "single-server"
        )
        self.assertTrue(any("must not render" in failure for failure in failures))

    def test_single_server_requires_default_deny(self) -> None:
        manifest = self.valid_manifest().replace("name: signalchord-default-deny\n", "")
        failures = validate_helm_policy.validate_manifest(manifest, "single-server")
        self.assertTrue(any("signalchord-default-deny" in failure for failure in failures))


if __name__ == "__main__":
    unittest.main()
