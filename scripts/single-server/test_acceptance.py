#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest

import acceptance


class AcceptanceUnitTest(unittest.TestCase):
    def test_fixture_requires_digest_pinned_image(self) -> None:
        with self.assertRaisesRegex(acceptance.AcceptanceError, "immutable sha256"):
            acceptance.fixture_resources("signalchord", "abc123", "python:latest")

    def test_fixture_resources_pass_restricted_baseline(self) -> None:
        image = "python@sha256:" + "a" * 64
        documents = [
            json.loads(document)
            for document in acceptance.fixture_resources("signalchord", "abc123", image).split(b"\n---\n")
        ]
        deployment = next(document for document in documents if document["kind"] == "Deployment")
        pod = deployment["spec"]["template"]["spec"]
        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertTrue(pod["securityContext"]["runAsNonRoot"])
        container = pod["containers"][0]
        self.assertEqual(image, container["image"])
        self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertEqual(["ALL"], container["securityContext"]["capabilities"]["drop"])

    def test_item_map_indexes_named_resources(self) -> None:
        payload = {"items": [{"metadata": {"name": "one"}}, {"metadata": {}}, {"metadata": {"name": "two"}}]}
        self.assertEqual({"one", "two"}, set(acceptance.item_map(payload)))

    def test_ensure_fails_closed(self) -> None:
        with self.assertRaisesRegex(acceptance.AcceptanceError, "required invariant"):
            acceptance.ensure(False, "required invariant")


if __name__ == "__main__":
    unittest.main()
