#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "scripts/single-server/backup.sh"
RESTORE = ROOT / "scripts/single-server/restore.sh"
RESTORE_IMPL = ROOT / "scripts/single-server/restore-v1.sh"
ACCEPTANCE = ROOT / "scripts/single-server/acceptance.sh"
SCRIPTS = [BACKUP, RESTORE, RESTORE_IMPL, ACCEPTANCE]


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
        ):
            self.assertIn(marker, text)

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
        ):
            self.assertIn(marker, text)

    def test_acceptance_contract(self) -> None:
        text = ACCEPTANCE.read_text(encoding="utf-8")
        for marker in ("signalchord-feed-collector", "/api/v1/sources", "/api/v1/watchlists", "/api/v1/alerts"):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
