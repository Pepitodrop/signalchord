#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

import audit_repository_history


class RepositoryHistoryAuditTest(unittest.TestCase):
    def repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)

    def commit(self, root: Path, path: str, content: str) -> None:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", path], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "test"], check=True)

    def test_clean_history_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.repo(root)
            self.commit(root, "README.md", "public source")
            summary, findings = audit_repository_history.audit(root, root / "missing")
            self.assertEqual([], findings)
            self.assertEqual(1, summary["commits"])

    def test_deleted_secret_remains_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.repo(root)
            self.commit(root, ".env", "TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890")
            (root / ".env").unlink()
            subprocess.run(["git", "-C", str(root), "add", "-u"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "delete"], check=True)
            _, findings = audit_repository_history.audit(root, root / "missing")
            self.assertTrue(any(item.rule == "environment file" for item in findings))
            self.assertTrue(any(item.rule == "GitHub token" for item in findings))

    def test_hashed_private_term_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.repo(root)
            self.commit(root, "notes.txt", "customer codename blue-orchid")
            term = b"blue-orchid"
            denylist = root / "denylist"
            denylist.write_text(f"{len(term)}:{hashlib.sha256(term).hexdigest()}\n", encoding="utf-8")
            _, findings = audit_repository_history.audit(root, denylist)
            self.assertTrue(any(item.rule == "private hashed denylist term" for item in findings))


if __name__ == "__main__":
    unittest.main()
