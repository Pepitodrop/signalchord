#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import validate_migration_safety as validate


ADDITIVE_MIGRATION = """\
class CreateThings < ActiveRecord::Migration[8.0]
  def change
    create_table :things, id: :uuid do |t|
      t.string :name, null: false
      t.timestamps
    end
    add_index :things, :name
  end
end
"""

ACKNOWLEDGMENT_COMMENT = (
    "# recovery-safety: acknowledged-destructive "
    "(forward-repair-only policy, see recovery/recovery-matrix.json)\n"
)


def destructive_migration(operation: str) -> str:
    return f"""\
class DestroyThings < ActiveRecord::Migration[8.0]
  def change
    {operation}
  end
end
"""


class DestructiveOperationDetectionTest(unittest.TestCase):
    def test_additive_migration_passes(self) -> None:
        self.assertEqual([], validate.find_destructive_operations(ADDITIVE_MIGRATION))
        self.assertEqual(
            [], validate.validate_migration(Path("001_additive.rb"), ADDITIVE_MIGRATION)
        )

    def test_drop_table_is_detected(self) -> None:
        text = destructive_migration("drop_table :things")
        self.assertEqual(["drop_table"], validate.find_destructive_operations(text))
        failures = validate.validate_migration(Path("002_drop_table.rb"), text)
        self.assertEqual(1, len(failures))
        self.assertIn("drop_table", failures[0])

    def test_remove_column_is_detected(self) -> None:
        text = destructive_migration("remove_column :things, :name")
        self.assertEqual(["remove_column"], validate.find_destructive_operations(text))
        self.assertEqual(1, len(validate.validate_migration(Path("x.rb"), text)))

    def test_drop_column_is_detected(self) -> None:
        text = destructive_migration("drop_column :things, :name")
        self.assertEqual(["drop_column"], validate.find_destructive_operations(text))
        self.assertEqual(1, len(validate.validate_migration(Path("x.rb"), text)))

    def test_rename_column_is_detected(self) -> None:
        text = destructive_migration("rename_column :things, :name, :title")
        self.assertEqual(["rename_column"], validate.find_destructive_operations(text))
        self.assertEqual(1, len(validate.validate_migration(Path("x.rb"), text)))

    def test_valid_acknowledgment_passes(self) -> None:
        text = destructive_migration("drop_table :things") + "\n" + ACKNOWLEDGMENT_COMMENT
        self.assertTrue(validate.has_forward_repair_acknowledgment(text))
        self.assertEqual([], validate.validate_migration(Path("x.rb"), text))

    def test_malformed_acknowledgment_missing_policy_citation_fails(self) -> None:
        text = destructive_migration("drop_table :things") + (
            "\n# recovery-safety: acknowledged-destructive (no policy reference here)\n"
        )
        self.assertFalse(validate.has_forward_repair_acknowledgment(text))
        self.assertEqual(1, len(validate.validate_migration(Path("x.rb"), text)))

    def test_malformed_acknowledgment_missing_marker_prefix_fails(self) -> None:
        text = destructive_migration("drop_table :things") + (
            "\n# acknowledged-destructive forward-repair recovery-matrix.json\n"
        )
        self.assertFalse(validate.has_forward_repair_acknowledgment(text))
        self.assertEqual(1, len(validate.validate_migration(Path("x.rb"), text)))

    def test_malformed_acknowledgment_not_a_comment_fails(self) -> None:
        # The exact right words, but on a code line rather than a "#" comment.
        text = destructive_migration("drop_table :things") + (
            "\nrecovery_safety = "
            "'recovery-safety: acknowledged-destructive forward-repair recovery-matrix.json'\n"
        )
        self.assertFalse(validate.has_forward_repair_acknowledgment(text))
        self.assertEqual(1, len(validate.validate_migration(Path("x.rb"), text)))

    def test_comment_mentioning_destructive_words_in_prose_is_not_flagged(self) -> None:
        text = (
            "class Prose < ActiveRecord::Migration[8.0]\n"
            "  def change\n"
            "    # this migration deliberately avoids drop_table and remove_column\n"
            "    create_table :things do |t|\n"
            "      t.string :name\n"
            "    end\n"
            "  end\n"
            "end\n"
        )
        self.assertEqual([], validate.find_destructive_operations(text))

    def test_unrelated_identifier_is_not_flagged(self) -> None:
        text = (
            "class Prose < ActiveRecord::Migration[8.0]\n"
            "  def change\n"
            "    rename_column_mapping = {}\n"
            "    create_table :things\n"
            "  end\n"
            "end\n"
        )
        self.assertEqual([], validate.find_destructive_operations(text))

    def test_multiple_violations_are_reported_together(self) -> None:
        text = destructive_migration(
            "drop_table :things\n    remove_column :other, :name\n    "
            "drop_column :third, :name\n    rename_column :fourth, :old, :new"
        )
        found = validate.find_destructive_operations(text)
        self.assertEqual(
            ["drop_column", "drop_table", "remove_column", "rename_column"], found
        )
        failures = validate.validate_migration(Path("x.rb"), text)
        self.assertEqual(1, len(failures))
        for name in ("drop_table", "remove_column", "drop_column", "rename_column"):
            self.assertIn(name, failures[0])

    def test_deterministic_ordering(self) -> None:
        text = destructive_migration(
            "rename_column :fourth, :old, :new\n    drop_table :things\n    "
            "drop_column :third, :name\n    remove_column :other, :name"
        )
        first = validate.find_destructive_operations(text)
        second = validate.find_destructive_operations(text)
        self.assertEqual(first, second)
        self.assertEqual(sorted(first), first)


class ChangedMigrationFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.migrate_dir = Path(self.tmpdir.name)

    def _write(self, name: str, text: str) -> Path:
        path = self.migrate_dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_no_base_scans_all_files(self) -> None:
        self._write("001_a.rb", ADDITIVE_MIGRATION)
        self._write("002_b.rb", ADDITIVE_MIGRATION)
        files = validate.changed_migration_files(self.migrate_dir, None, "HEAD")
        self.assertEqual(2, len(files))

    def test_no_migration_files_passes(self) -> None:
        files = validate.changed_migration_files(self.migrate_dir, None, "HEAD")
        self.assertEqual([], files)
        failures: list[str] = []
        for path in files:
            failures.extend(validate.validate_migration(path, path.read_text()))
        self.assertEqual([], failures)

    def test_unresolvable_base_falls_back_to_scanning_all_files(self) -> None:
        self._write("001_a.rb", ADDITIVE_MIGRATION)
        self._write("002_b.rb", ADDITIVE_MIGRATION)

        def failing_run(args: list[str]) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(128, args, stderr="fatal: bad object deadbeef")

        files = validate.changed_migration_files(
            self.migrate_dir, "deadbeef", "HEAD", run=failing_run
        )
        self.assertEqual(2, len(files))

    def test_resolvable_base_scopes_to_diff_output(self) -> None:
        changed_path = self._write("002_changed.rb", ADDITIVE_MIGRATION)
        self._write("001_unchanged.rb", ADDITIVE_MIGRATION)

        def fake_run(args: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args, 0, stdout=f"{changed_path}\n", stderr="")

        files = validate.changed_migration_files(
            self.migrate_dir, "some-base-sha", "HEAD", run=fake_run
        )
        self.assertEqual([changed_path], files)


if __name__ == "__main__":
    unittest.main()
