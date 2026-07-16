#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest

import acceptance


class AcceptanceUnitTest(unittest.TestCase):
    def test_fixture_requires_digest_pinned_image(self) -> None:
        with self.assertRaisesRegex(acceptance.AcceptanceError, "immutable sha256"):
            acceptance.fixture_resources("signalchord", "abc123", "python:latest")

    def test_fixture_resources_pass_restricted_baseline_and_internal_policy(self) -> None:
        image = "python@sha256:" + "a" * 64
        documents = [
            json.loads(document)
            for document in acceptance.fixture_resources("signalchord", "abc123", image).split(b"\n---\n")
        ]
        deployment = next(document for document in documents if document["kind"] == "Deployment")
        pod_template = deployment["spec"]["template"]
        self.assertEqual("signalchord", pod_template["metadata"]["labels"]["app.kubernetes.io/part-of"])
        pod = pod_template["spec"]
        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertTrue(pod["securityContext"]["runAsNonRoot"])
        container = pod["containers"][0]
        self.assertEqual(image, container["image"])
        self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertEqual(["ALL"], container["securityContext"]["capabilities"]["drop"])

    def test_canary_job_overrides_feed_tenant_and_policy(self) -> None:
        cronjob = {
            "spec": {
                "jobTemplate": {
                    "spec": {
                        "template": {
                            "metadata": {"labels": {"app.kubernetes.io/name": "feed-collector"}},
                            "spec": {
                                "restartPolicy": "OnFailure",
                                "containers": [
                                    {
                                        "name": "feed-collector",
                                        "image": "ghcr.io/pepitodrop/signalchord-feed-collector@sha256:" + "a" * 64,
                                        "env": [{"name": "FEED_URL", "value": "https://old.invalid/feed.xml"}],
                                    }
                                ],
                            },
                        }
                    }
                }
            }
        }
        policy = {
            "source_id": "source-1",
            "rights_status": "approved",
            "owner": "fixture",
            "legal_basis": "fixture",
            "permitted_uses": ["test"],
            "attribution": "fixture",
            "terms_status": "fixture",
            "geography": "test",
            "retention_days": 1,
            "deletion_obligations": "delete",
        }
        job = json.loads(
            acceptance.canary_job_manifest(
                cronjob,
                namespace="signalchord",
                name="acceptance-job",
                feed_url="http://fixture.signalchord.svc.cluster.local:8080/feed.xml",
                source_id="source-1",
                tenant_id="tenant-1",
                source_policy=policy,
            )
        )
        self.assertEqual("Job", job["kind"])
        template = job["spec"]["template"]
        self.assertEqual("signalchord", template["metadata"]["labels"]["app.kubernetes.io/part-of"])
        env = {entry["name"]: entry["value"] for entry in template["spec"]["containers"][0]["env"]}
        self.assertEqual("source-1", env["SOURCE_ID"])
        self.assertEqual("tenant-1", env["SIGNALCHORD_TENANT_ID"])
        self.assertEqual(policy, json.loads(env["SOURCE_POLICY_JSON"]))
        self.assertIn("fixture.signalchord.svc.cluster.local", env["FEED_URL"])

    def test_canary_job_rejects_unexpected_cronjob(self) -> None:
        with self.assertRaisesRegex(acceptance.AcceptanceError, "unexpected structure"):
            acceptance.canary_job_manifest(
                {},
                namespace="signalchord",
                name="acceptance-job",
                feed_url="http://fixture/feed.xml",
                source_id="source-1",
                tenant_id="tenant-1",
                source_policy={},
            )

    def test_item_map_indexes_named_resources(self) -> None:
        payload = {"items": [{"metadata": {"name": "one"}}, {"metadata": {}}, {"metadata": {"name": "two"}}]}
        self.assertEqual({"one", "two"}, set(acceptance.item_map(payload)))

    def test_ensure_fails_closed(self) -> None:
        with self.assertRaisesRegex(acceptance.AcceptanceError, "required invariant"):
            acceptance.ensure(False, "required invariant")


if __name__ == "__main__":
    unittest.main()
