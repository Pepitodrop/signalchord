#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    ROOT / "scripts/single-server/backup.sh",
    ROOT / "scripts/single-server/restore.sh",
    ROOT / "scripts/single-server/acceptance.sh",
]


class ReleaseToolingTest(unittest.TestCase):
    def test_shell_syntax(self) -> None:
        for script in SCRIPTS:
            subprocess.run(["sh", "-n", str(script)], check=True)

    def test_backup_contract(self) -> None:
        text = SCRIPTS[0].read_text(encoding="utf-8")
        for marker in ("pg_dump", "neo4j-admin database dump", "runtime.env.age", "minio.tar", "SHA256SUMS"):
            self.assertIn(marker, text)

    def test_restore_contract(self) -> None:
        text = SCRIPTS[1].read_text(encoding="utf-8")
        for marker in ("sha256sum -c", "pg_restore", "neo4j-admin database load", "data-minio-0", "--yes"):
            self.assertIn(marker, text)

    def test_acceptance_contract(self) -> None:
        text = SCRIPTS[2].read_text(encoding="utf-8")
        for marker in ("signalchord-feed-collector", "/api/v1/sources", "/api/v1/watchlists", "/api/v1/alerts"):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
