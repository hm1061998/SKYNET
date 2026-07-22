"""Lightweight local SQLite persistence behind repository contracts."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Callable, Generic, TypeVar

from core.repositories.memory import REPOSITORY_NAMES
from core.repositories.ports import ConcurrentUpdateError, RepositoryError

from .migrations import migrate

T = TypeVar("T")
SENSITIVE_KEYS = frozenset({"api_key", "secret", "password", "access_token", "refresh_token"})


def _reject_secrets(value: object, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                raise RepositoryError(f"raw secrets may not be persisted ({path}.{key})")
            _reject_secrets(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_secrets(item, f"{path}[{index}]")


class SQLiteRepository(Generic[T]):
    """JSON-payload repository with SQL-isolated optimistic locking."""

    def __init__(self, connection: sqlite3.Connection, collection: str,
                 entity_type: type[T], lock: RLock) -> None:
        self._connection = connection
        self._collection = collection
        self._entity_type = entity_type
        self._lock = lock

    def _payload(self, entity: T) -> tuple[str, int, str]:
        entity_id = getattr(entity, "id", None)
        version = getattr(entity, "version", 1)
        to_dict = getattr(entity, "to_dict", None)
        if not entity_id or not callable(to_dict):
            raise RepositoryError("entity must expose id and to_dict")
        data = to_dict()
        _reject_secrets(data)
        return str(entity_id), int(version), json.dumps(data, ensure_ascii=False, sort_keys=True)

    def _decode(self, payload: str) -> T:
        from_dict = getattr(self._entity_type, "from_dict", None)
        if not callable(from_dict):
            raise RepositoryError(f"{self._entity_type.__name__} does not implement from_dict")
        return from_dict(json.loads(payload))

    def add(self, entity: T) -> None:
        entity_id, version, payload = self._payload(entity)
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock, self._connection:
                self._connection.execute(
                    "INSERT INTO entities(collection,id,entity_type,version,payload,updated_at) VALUES(?,?,?,?,?,?)",
                    (self._collection, entity_id, self._entity_type.__name__, version, payload, now))
        except sqlite3.IntegrityError as exc:
            raise RepositoryError(f"entity already exists: {entity_id}") from exc

    def get(self, entity_id: str) -> T | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM entities WHERE collection=? AND id=?",
                (self._collection, entity_id)).fetchone()
        return self._decode(row[0]) if row else None

    def list(self) -> list[T]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM entities WHERE collection=? ORDER BY id",
                (self._collection,)).fetchall()
        return [self._decode(row[0]) for row in rows]

    def save(self, entity: T, expected_version: int) -> None:
        entity_id, version, payload = self._payload(entity)
        if version <= expected_version:
            raise ConcurrentUpdateError("saved entity version must advance")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """UPDATE entities SET version=?, payload=?, updated_at=?
                   WHERE collection=? AND id=? AND version=?""",
                (version, payload, now, self._collection, entity_id, expected_version))
            if cursor.rowcount != 1:
                raise ConcurrentUpdateError("entity missing or version mismatch")

    def delete(self, entity_id: str, expected_version: int) -> None:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM entities WHERE collection=? AND id=? AND version=?",
                (self._collection, entity_id, expected_version))
            if cursor.rowcount != 1:
                raise ConcurrentUpdateError("entity missing or version mismatch")


class SQLiteStore:
    """Connection owner and factory for local repositories."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._lock = RLock()
        migrate(self.connection)

    def repository(self, collection: str, entity_type: type[T]) -> SQLiteRepository[T]:
        if collection not in REPOSITORY_NAMES:
            raise RepositoryError(f"unknown repository collection: {collection}")
        return SQLiteRepository(self.connection, collection, entity_type, self._lock)

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
