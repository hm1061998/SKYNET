"""Ordered, transactional SQLite schema migrations."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATIONS = (
    Migration(1, "foundation_entities", (
        """CREATE TABLE IF NOT EXISTS entities (
               collection TEXT NOT NULL,
               id TEXT NOT NULL,
               entity_type TEXT NOT NULL,
               version INTEGER NOT NULL CHECK(version >= 1),
               payload TEXT NOT NULL,
               updated_at TEXT NOT NULL,
               PRIMARY KEY(collection, id)
           )""",
        "CREATE INDEX IF NOT EXISTS idx_entities_collection ON entities(collection)",
    )),
)


def migrate(connection: sqlite3.Connection) -> list[int]:
    """Apply pending migrations once, each in its own transaction."""
    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version INTEGER PRIMARY KEY,
               name TEXT NOT NULL,
               applied_at TEXT NOT NULL
           )""")
    applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    completed: list[int] = []
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        with connection:
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, datetime('now'))",
                (migration.version, migration.name),
            )
        completed.append(migration.version)
    return completed
