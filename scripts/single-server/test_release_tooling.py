#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "scripts/single-server/backup.sh"
BACKUP_POSTGRES_ONLY = ROOT / "scripts/single-server/backup-postgres-only.sh"
RESTORE = ROOT / "scripts/single-server/restore.sh"
RESTORE_IMPL = ROOT / "scripts/single-server/restore-v1.sh"
ACCEPTANCE = ROOT / "scripts/single-server/acceptance.sh"
REPLAY_KAFKA = ROOT / "scripts/single-server/replay-kafka.sh"
SCRIPTS = [BACKUP, BACKUP_POSTGRES_ONLY, RESTORE, RESTORE_IMPL, ACCEPTANCE, REPLAY_KAFKA]


class ReleaseToolingTest(unittest.TestCase):
    def test_shell_syntax(self) -> None:
        for script in SCRIPTS:
            subprocess.run(["sh", "-n", str(script)], check=True)

    def test_backup_contract(self) -> None:
        text = BACKUP.read_text(encoding="utf-8")
        for marker in (
            "pg_dump",
            "neo4j-admin database dump neo4j",
            "neo4j-admin database dump system",
            "runtime.env.age",
            "minio.tar",
            "application_quiesced",
            "SHA256SUMS",
            "mc alias set",
            "mc mirror",
            "--dest-minio-bucket",
            "--dest-minio-access-key-file",
            "--dest-minio-secret-key-file",
        ):
            self.assertIn(marker, text)
        # The full backup's context probe must not be fatal when run from an
        # in-cluster CronJob ServiceAccount (no kubeconfig, no current-context).
        self.assertIn("kubectl config current-context 2>/dev/null || echo in-cluster", text)

    def test_backup_postgres_only_contract(self) -> None:
        text = BACKUP_POSTGRES_ONLY.read_text(encoding="utf-8")
        for marker in (
            "pg_dump",
            "runtime.env.age",
            "SHA256SUMS",
            "mc alias set",
            "mc mirror",
            "signalchord-single-server-backup-postgres-only",
            '"application_quiesced": False',
            "--minio-bucket",
            "--minio-access-key-file",
            "--minio-secret-key-file",
        ):
            self.assertIn(marker, text)
        # This cadence is defined by never touching application replicas or
        # the feed-collector cronjob: assert those calls are simply absent.
        for forbidden in ("scale deployments", "scale statefulset", "patch cronjob signalchord-feed-collector"):
            self.assertNotIn(forbidden, text)

    def test_restore_contract(self) -> None:
        wrapper = RESTORE.read_text(encoding="utf-8")
        self.assertIn("restore-v1.sh", wrapper)
        text = RESTORE_IMPL.read_text(encoding="utf-8")
        for marker in (
            "sha256sum -c",
            "pg_restore",
            "neo4j-admin database load system",
            "neo4j-admin database load neo4j",
            "neo4j-system.dump",
            "data-minio-0",
            "application_quiesced",
            "--yes",
            "--postgres-only",
            "signalchord.io/restore-target",
            "restore_target",
            "!= allowed",
            "--confirm-context",
            "current_context",
            "--smtp-blackhole-host",
            "--expo-blackhole-url",
            "SMTP_HOST=",
            "EXPO_PUSH_URL=",
            "signalchord-single-server-backup-postgres-only",
        ):
            self.assertIn(marker, text)

    def test_acceptance_contract(self) -> None:
        text = ACCEPTANCE.read_text(encoding="utf-8")
        for marker in ("signalchord-feed-collector", "/api/v1/sources", "/api/v1/watchlists", "/api/v1/alerts"):
            self.assertIn(marker, text)

    def test_replay_kafka_contract(self) -> None:
        text = REPLAY_KAFKA.read_text(encoding="utf-8")
        for marker in (
            "kafka-consumer-groups.sh",
            "--reset-offsets",
            "--to-datetime",
            "--dry-run",
            "--execute",
            "--describe",
            "--namespace",
            "--group",
            "--topic",
            "--force",
            "--yes",
            "--evidence-report",
            "retention window",
            "signalchord-alert-projector-v1",
            "signalchord-entity-resolution-v1",
            "signalchord-nlp-v1",
            "signalchord-graph-analytics-v1",
            "signalchord-graph-projector-v1",
            "signalchord-velato-v1",
            "signalchord-notification-worker-v1",
            "signalchord-claim-intelligence-v1",
            "signalchord-search-projector-v1",
        ):
            self.assertIn(marker, text)
        # No implicit namespace/group default, and no bulk/wildcard reset path.
        self.assertNotIn("NAMESPACE=signalchord\n", text)
        for forbidden in ("--all-topics", "--all-groups"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
