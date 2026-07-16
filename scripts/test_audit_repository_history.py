#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import audit_repository_history as audit


ALLOWLIST = {
    "schema_version": 1,
    "allowed_binary_paths": [
        {"pattern": "velato/programs/*.mid", "owner": "SignalChord", "license": "Apache-2.0", "reason": "fixture"}
    ],
    "allowed_archive_paths": [],
    "allowed_template_paths": [
        {"pattern": ".env.example", "owner": "SignalChord", "license": "Apache-2.0", "reason": "template"}
    ],
}


class HistoryAuditUnitTest(unittest.TestCase):
    def test_allowlist_requires_complete_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "allowlist.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "allowed_binary_paths": [{"pattern": "*.mid"}],
                        "allowed_archive_paths": [],
                        "allowed_template_paths": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "missing owner"):
                audit.load_allowlist(path)

    def test_environment_example_is_allowed_but_real_environment_file_is_not(self) -> None:
        templates = audit.patterns(ALLOWLIST, "allowed_template_paths")
        self.assertIsNone(audit.sensitive_name(".env.example", templates))
        self.assertIsNotNone(audit.sensitive_name(".env.production", templates))

    def test_unapproved_archive_fails(self) -> None:
        record = audit.BlobRecord("a" * 40, 10, ("backup/database.dump",))
        with mock.patch.object(audit, "blob_content", return_value=b"fixture"):
            findings = audit.audit_blob(record, ALLOWLIST)
        self.assertTrue(any(finding.category == "unapproved-archive" for finding in findings))

    def test_approved_midi_is_not_reported_as_binary(self) -> None:
        record = audit.BlobRecord("b" * 40, 5, ("velato/programs/policy.mid",))
        with mock.patch.object(audit, "blob_content", return_value=b"\x00MThd"):
            findings = audit.audit_blob(record, ALLOWLIST)
        self.assertFalse(any(finding.category in {"unapproved-binary", "unclassified-binary"} for finding in findings))

    def test_private_key_marker_fails_without_exposing_content(self) -> None:
        record = audit.BlobRecord("c" * 40, 64, ("config.txt",))
        marker = b"-----BEGIN " + b"PRIVATE KEY-----\nredacted\n"
        with mock.patch.object(audit, "blob_content", return_value=marker):
            findings = audit.audit_blob(record, ALLOWLIST)
        self.assertTrue(any(finding.category == "key-material" for finding in findings))
        self.assertTrue(all("redacted" not in finding.detail for finding in findings))

    def test_copied_dependency_tree_fails(self) -> None:
        record = audit.BlobRecord("d" * 40, 7, ("vendor/library/file.rb",))
        with mock.patch.object(audit, "blob_content", return_value=b"fixture"):
            findings = audit.audit_blob(record, ALLOWLIST)
        self.assertTrue(any(finding.category == "copied-tree" for finding in findings))


if __name__ == "__main__":
    unittest.main()
