"""Thread-safe in-memory repository implementations."""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Generic, TypeVar

from .ports import ConcurrentUpdateError, RepositoryError

T = TypeVar("T")


class InMemoryRepository(Generic[T]):
    """Generic repository suitable for tests and ephemeral adapters."""

    def __init__(self) -> None:
        self._items: dict[str, T] = {}
        self._lock = RLock()

    @staticmethod
    def _identity(entity: T) -> tuple[str, int]:
        entity_id = getattr(entity, "id", None)
        version = getattr(entity, "version", 1)
        if not isinstance(entity_id, str) or not entity_id:
            raise RepositoryError("entity must expose a non-empty string id")
        if not isinstance(version, int) or version < 1:
            raise RepositoryError("entity version must be a positive integer")
        return entity_id, version

    def add(self, entity: T) -> None:
        entity_id, _ = self._identity(entity)
        with self._lock:
            if entity_id in self._items:
                raise RepositoryError(f"entity already exists: {entity_id}")
            self._items[entity_id] = deepcopy(entity)

    def get(self, entity_id: str) -> T | None:
        with self._lock:
            item = self._items.get(entity_id)
            return deepcopy(item) if item is not None else None

    def list(self) -> list[T]:
        with self._lock:
            return [deepcopy(item) for _, item in sorted(self._items.items())]

    def save(self, entity: T, expected_version: int) -> None:
        entity_id, new_version = self._identity(entity)
        with self._lock:
            current = self._items.get(entity_id)
            if current is None:
                raise RepositoryError(f"entity does not exist: {entity_id}")
            current_version = getattr(current, "version", 1)
            if current_version != expected_version:
                raise ConcurrentUpdateError(
                    f"expected version {expected_version}, found {current_version}")
            if new_version <= current_version:
                raise ConcurrentUpdateError("saved entity version must advance")
            self._items[entity_id] = deepcopy(entity)

    def delete(self, entity_id: str, expected_version: int) -> None:
        with self._lock:
            current = self._items.get(entity_id)
            if current is None:
                raise RepositoryError(f"entity does not exist: {entity_id}")
            if getattr(current, "version", 1) != expected_version:
                raise ConcurrentUpdateError("delete version mismatch")
            del self._items[entity_id]


REPOSITORY_NAMES = (
    "organizations", "agent_definitions", "agent_instances", "goals", "work_orders",
    "tasks", "artifacts", "approvals", "audit_events", "budgets",
    "collaboration_messages", "context_packages", "review_records",
)


class InMemoryRepositories:
    """Collection of named repositories matching all required ports."""

    def __init__(self) -> None:
        for name in REPOSITORY_NAMES:
            setattr(self, name, InMemoryRepository())
