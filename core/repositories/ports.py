"""Repository contracts owned by the application/domain boundary."""
from __future__ import annotations

from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class RepositoryError(RuntimeError):
    """Base persistence-port error."""


class NotFoundError(RepositoryError):
    """Raised when an entity does not exist."""


class ConcurrentUpdateError(RepositoryError):
    """Raised when an optimistic version check fails."""


class Repository(Protocol[T]):
    """Minimal repository contract with optimistic version checks."""

    def add(self, entity: T) -> None: ...
    def get(self, entity_id: str) -> T | None: ...
    def list(self) -> list[T]: ...
    def save(self, entity: T, expected_version: int) -> None: ...
    def delete(self, entity_id: str, expected_version: int) -> None: ...


class OrganizationRepository(Repository[Any], Protocol): pass
class AgentDefinitionRepository(Repository[Any], Protocol): pass
class AgentInstanceRepository(Repository[Any], Protocol): pass
class GoalRepository(Repository[Any], Protocol): pass
class WorkOrderRepository(Repository[Any], Protocol): pass
class TaskRepository(Repository[Any], Protocol): pass
class ArtifactRepository(Repository[Any], Protocol): pass
class ApprovalRepository(Repository[Any], Protocol): pass
class AuditEventRepository(Repository[Any], Protocol): pass
class BudgetRepository(Repository[Any], Protocol): pass
