#!/usr/bin/env python3
"""Focused image-reference policy tests for rendered Helm manifests."""

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

    def test_mutable_latest_is_rejected(self) -> None:
        failures = self.validate("ghcr.io/pepitodrop/signalchord-web:latest", "production")
        self.assertTrue(any("mutable image reference" in failure for failure in failures))

    def test_missing_images_are_rejected(self) -> None:
        self.assertEqual(
            ["rendered manifest has no container images"],
            validate_helm_policy.validate_image_references("kind: ConfigMap\n", "production"),
        )


if __name__ == "__main__":
    unittest.main()
