"""Factories for bounded ephemeral agent instances."""
from __future__ import annotations

from datetime import datetime

from core.domain import (AgentInstance, AgentKind, AgentStatus, Clock, DomainValidationError,
                         IdGenerator, UtcClock, UuidIdGenerator)
from core.domain.base import require_utc

from .capabilities import CapabilityResolver
from .definitions import AgentRegistry


class AgentFactory:
    """Create worker/control instances only after validating their definitions."""

    def __init__(self, registry: AgentRegistry, resolver: CapabilityResolver | None = None,
                 clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.registry = registry
        self.resolver = resolver or CapabilityResolver()
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def create_defined(self, definition_id: str, work_order_id: str | None = None) -> AgentInstance:
        self.registry.get(definition_id)
        return AgentInstance(self.ids.new_id("agent_instance"), definition_id, AgentStatus.DEFINED,
                             self.clock.now(), work_order_id)

    def create_worker(self, definition_id: str, *, parent_definition_id: str,
                      source_task_id: str, work_order_id: str, expires_at: datetime,
                      budget_id: str, requested_capabilities: set[str]) -> AgentInstance:
        worker = self.registry.get(definition_id)
        parent = self.registry.get(parent_definition_id)
        if worker.kind is not AgentKind.WORKER:
            raise DomainValidationError("create_worker requires a WORKER definition")
        now = self.clock.now()
        require_utc(expires_at, "worker.expires_at")
        if expires_at <= now:
            raise DomainValidationError("worker expiration must be in the future")
        grants = self.resolver.reduce_for_worker(parent, worker, requested_capabilities)
        instance_id = self.ids.new_id("agent_instance")
        return AgentInstance(
            instance_id, definition_id, AgentStatus.DEFINED, now, work_order_id, 1,
            parent_definition_id, source_task_id, expires_at,
            self.ids.new_id("agent_context"), budget_id, grants,
        )
