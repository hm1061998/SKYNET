"""Repeatable, secret-aware import of legacy JSONL memory into SQLite."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = frozenset({"api_key", "password", "secret", "access_token", "refresh_token"})


@dataclass(frozen=True)
class MemoryMigrationReport:
    source: str
    dry_run: bool
    imported: int
    skipped: int
    conflicted: int
    failed: int
    backup_path: str | None
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "dry_run": self.dry_run, "imported": self.imported,
                "skipped": self.skipped, "conflicted": self.conflicted, "failed": self.failed,
                "backup_path": self.backup_path, "errors": list(self.errors)}


class LegacyMemoryMigrator:
    """Import legacy records without modifying the source or logging secret values."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    @staticmethod
    def _fingerprint(record: dict[str, Any]) -> str:
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _contains_secret(value: Any) -> bool:
        if isinstance(value, dict):
            return any(str(key).lower() in SENSITIVE_KEYS or LegacyMemoryMigrator._contains_secret(item)
                       for key, item in value.items())
        if isinstance(value, list):
            return any(LegacyMemoryMigrator._contains_secret(item) for item in value)
        return False

    def migrate(self, source: str | Path, *, dry_run: bool = True,
                backup_directory: str | Path | None = None) -> MemoryMigrationReport:
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        records: list[tuple[str, str]] = []
        failures, skipped, conflicts = 0, 0, 0
        errors: list[str] = []
        seen: set[str] = set()
        for line_number, line in enumerate(source_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record must be an object")
                if self._contains_secret(record):
                    skipped += 1
                    errors.append(f"line {line_number}: sensitive record skipped")
                    continue
                fingerprint = self._fingerprint(record)
                if fingerprint in seen:
                    conflicts += 1
                    continue
                seen.add(fingerprint)
                records.append((fingerprint, json.dumps(record, ensure_ascii=False, sort_keys=True)))
            except (json.JSONDecodeError, ValueError):
                failures += 1
                errors.append(f"line {line_number}: invalid JSON record")

        existing: set[str] = set()
        if self.database_path.exists():
            connection = sqlite3.connect(self.database_path)
            try:
                row = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='legacy_memory_imports'").fetchone()
                if row:
                    existing = {item[0] for item in connection.execute("SELECT fingerprint FROM legacy_memory_imports")}
            finally:
                connection.close()
        new_records = [item for item in records if item[0] not in existing]
        skipped += len(records) - len(new_records)
        if dry_run:
            return MemoryMigrationReport(str(source_path), True, len(new_records), skipped,
                                         conflicts, failures, None, tuple(errors))

        backup_root = Path(backup_directory) if backup_directory else source_path.parent / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()[:12]
        backup_path = backup_root / f"{source_path.name}.{source_digest}.bak"
        if not backup_path.exists():
            shutil.copy2(source_path, backup_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        try:
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS legacy_memory_imports(
                    fingerprint TEXT PRIMARY KEY, source_path TEXT NOT NULL, payload TEXT NOT NULL)""")
                connection.executemany("INSERT OR IGNORE INTO legacy_memory_imports VALUES(?,?,?)",
                    [(fingerprint, str(source_path), payload) for fingerprint, payload in new_records])
        finally:
            connection.close()
        return MemoryMigrationReport(str(source_path), False, len(new_records), skipped,
                                     conflicts, failures, str(backup_path), tuple(errors))
