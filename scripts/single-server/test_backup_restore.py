#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import backup_restore


class BackupRestoreUnitTest(unittest.TestCase):
    def test_app_state_only_includes_signalchord_deployments(self) -> None:
        payload = {
            "items": [
                {"metadata": {"name": "signalchord-web"}, "spec": {"replicas": 2}},
                {"metadata": {"name": "signalchord-control-plane"}, "spec": {}},
                {"metadata": {"name": "otel-collector"}, "spec": {"replicas": 1}},
            ]
        }
        self.assertEqual(
            {"signalchord-control-plane": 1, "signalchord-web": 2},
            backup_restore.app_state_from_deployments(payload),
        )

    def test_missing_application_deployments_fail_closed(self) -> None:
        with self.assertRaisesRegex(backup_restore.RecoveryError, "no SignalChord"):
            backup_restore.app_state_from_deployments({"items": []})

    def test_maintenance_image_requires_digest(self) -> None:
        with self.assertRaisesRegex(backup_restore.RecoveryError, "pinned by sha256"):
            backup_restore.maintenance_pod_manifest("signalchord", "minio/mc:latest")

    def test_maintenance_pod_is_restricted_and_uses_secret_refs(self) -> None:
        image = "minio/mc@sha256:" + "a" * 64
        manifest = json.loads(backup_restore.maintenance_pod_manifest("signalchord", image))
        self.assertEqual("signalchord", manifest["metadata"]["namespace"])
        self.assertFalse(manifest["spec"]["automountServiceAccountToken"])
        self.assertTrue(manifest["spec"]["securityContext"]["runAsNonRoot"])
        container = manifest["spec"]["containers"][0]
        self.assertEqual(image, container["image"])
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertEqual(["ALL"], container["securityContext"]["capabilities"]["drop"])
        self.assertEqual(
            "signalchord-runtime",
            container["env"][0]["valueFrom"]["secretKeyRef"]["name"],
        )

    def test_backup_verification_accepts_matching_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            files = {}
            for name in backup_restore.REQUIRED_FILES:
                path = directory / name
                path.write_bytes(f"fixture:{name}".encode())
                files[name] = {
                    "sha256": backup_restore.sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            manifest = {
                "format": backup_restore.BACKUP_FORMAT,
                "namespace": "signalchord",
                "files": files,
            }
            (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            loaded = backup_restore.load_and_verify_backup(directory)
            self.assertEqual(backup_restore.BACKUP_FORMAT, loaded["format"])

    def test_backup_verification_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            files = {}
            for name in backup_restore.REQUIRED_FILES:
                path = directory / name
                path.write_bytes(b"original")
                files[name] = {"sha256": backup_restore.sha256_file(path), "bytes": 8}
            (directory / "manifest.json").write_text(
                json.dumps({"format": backup_restore.BACKUP_FORMAT, "files": files}),
                encoding="utf-8",
            )
            (directory / "postgres.dump").write_bytes(b"changed")
            with self.assertRaisesRegex(backup_restore.RecoveryError, "checksum mismatch"):
                backup_restore.load_and_verify_backup(directory)


if __name__ == "__main__":
    unittest.main()
