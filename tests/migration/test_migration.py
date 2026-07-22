import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from core.compatibility import LegacyMemoryMigrator, RuntimeFeatureFlags
from core.config import Config


ROOT = Path(__file__).resolve().parents[2]


class FeatureFlagTests(unittest.TestCase):
    def test_upgrade_defaults_are_safe_and_legacy_compatible(self):
        flags = Config({}).feature_flags
        self.assertFalse(flags.organization_enabled)
        self.assertTrue(flags.legacy_enabled)
        self.assertEqual(flags.execution_mode, "dry_run")
        self.assertFalse(flags.allow_legacy_unsafe)
        self.assertEqual((flags.storage_backend, flags.ui_mode), ("sqlite", "legacy"))

    def test_flags_reject_unsafe_or_inconsistent_combinations(self):
        with self.assertRaises(ValueError):
            RuntimeFeatureFlags.from_config({"runtime": {"legacy_enabled": False}})
        with self.assertRaises(ValueError):
            RuntimeFeatureFlags.from_config({"execution": {"mode": "legacy_unsafe"}})
        enabled = RuntimeFeatureFlags.from_config({"runtime": {"organization_enabled": True},
            "execution": {"mode": "legacy_unsafe", "allow_legacy_unsafe": True},
            "ui": {"mode": "organization"}})
        self.assertTrue(enabled.organization_enabled)


class MemoryMigrationTests(unittest.TestCase):
    def test_dry_run_source_integrity_backup_and_repeatability(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "memory.jsonl"
            original = (ROOT / "tests" / "fixtures" / "legacy_memory.jsonl").read_bytes()
            source.write_bytes(original)
            database = root / "runtime.db"
            migrator = LegacyMemoryMigrator(database)
            preview = migrator.migrate(source)
            self.assertEqual((preview.imported, preview.skipped, preview.failed), (2, 0, 0))
            self.assertFalse(database.exists())
            self.assertEqual(source.read_bytes(), original)
            applied = migrator.migrate(source, dry_run=False, backup_directory=root / "backup")
            self.assertEqual(applied.imported, 2)
            self.assertTrue(Path(applied.backup_path).is_file())
            self.assertEqual(source.read_bytes(), original)
            repeated = migrator.migrate(source, dry_run=False, backup_directory=root / "backup")
            self.assertEqual((repeated.imported, repeated.skipped), (0, 2))
            connection = sqlite3.connect(database)
            try:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM legacy_memory_imports").fetchone()[0], 2)
            finally:
                connection.close()

    def test_corrupt_duplicate_and_secret_records_are_reported_without_leakage(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "memory.jsonl"
            good = {"id": "one", "text": "safe"}
            source.write_text("\n".join((json.dumps(good), json.dumps(good),
                json.dumps({"id": "secret", "api_key": "do-not-log"}), "{bad")), encoding="utf-8")
            report = LegacyMemoryMigrator(Path(directory) / "db.sqlite").migrate(source)
            self.assertEqual((report.imported, report.conflicted, report.skipped, report.failed), (1, 1, 1, 1))
            self.assertNotIn("do-not-log", str(report.to_dict()))


if __name__ == "__main__":
    unittest.main()
