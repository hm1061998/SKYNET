"""Agent lifecycle transitions with mandatory audit emission."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from core.domain import (AgentInstance, AgentStatus, AuditEvent, Clock, IdGenerator,
                         InvalidTransitionError, UtcClock, UuidIdGenerator)


LIFECYCLE_TRANSITIONS: dict[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.DEFINED: frozenset({AgentStatus.READY, AgentStatus.SUSPENDED, AgentStatus.CANCELLED, AgentStatus.FAILED}),
    AgentStatus.READY: frozenset({AgentStatus.ASSIGNED, AgentStatus.SUSPENDED, AgentStatus.CANCELLED, AgentStatus.FAILED}),
    AgentStatus.ASSIGNED: frozenset({AgentStatus.RUNNING, AgentStatus.SUSPENDED, AgentStatus.CANCELLED, AgentStatus.FAILED}),
    AgentStatus.RUNNING: frozenset({AgentStatus.WAITING, AgentStatus.COMPLETED, AgentStatus.SUSPENDED, AgentStatus.CANCELLED, AgentStatus.FAILED}),
    AgentStatus.WAITING: frozenset({AgentStatus.RUNNING, AgentStatus.SUSPENDED, AgentStatus.CANCELLED, AgentStatus.FAILED}),
    AgentStatus.COMPLETED: frozenset({AgentStatus.TERMINATED}),
    AgentStatus.FAILED: frozenset({AgentStatus.TERMINATED}),
    AgentStatus.SUSPENDED: frozenset({AgentStatus.READY, AgentStatus.CANCELLED, AgentStatus.TERMINATED}),
    AgentStatus.CANCELLED: frozenset({AgentStatus.TERMINATED}),
    AgentStatus.TERMINATED: frozenset(),
}


class AgentLifecycleManager:
    """Validate transitions and emit one audit event for every successful change."""

    def __init__(self, emit: Callable[[AuditEvent], None], clock: Clock | None = None,
                 ids: IdGenerator | None = None) -> None:
        self.emit = emit
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def transition(self, instance: AgentInstance, target: AgentStatus,
                   actor_id: str, reason: str = "") -> AgentInstance:
        if target == instance.status:
            return instance
        allowed = LIFECYCLE_TRANSITIONS.get(instance.status, frozenset())
        if target not in allowed:
            raise InvalidTransitionError(
                f"cannot transition agent from {instance.status.value} to {target.value}")
        changed = replace(instance, status=target, version=instance.version + 1)
        event = AuditEvent(
            self.ids.new_id("event"), "agent.lifecycle.transition", actor_id, instance.id,
            self.clock.now(), instance.work_order_id or instance.id,
            {"from": instance.status.value, "to": target.value, "reason": reason},
        )
        self.emit(event)
        return changed

    def terminate_if_expired(self, instance: AgentInstance, actor_id: str) -> AgentInstance:
        if instance.expires_at is None or self.clock.now() < instance.expires_at:
            return instance
        current = instance
        if current.status is AgentStatus.TERMINATED:
            return current
        if current.status not in (AgentStatus.COMPLETED, AgentStatus.FAILED,
                                  AgentStatus.SUSPENDED, AgentStatus.CANCELLED):
            if AgentStatus.CANCELLED in LIFECYCLE_TRANSITIONS.get(current.status, ()):
                current = self.transition(current, AgentStatus.CANCELLED, actor_id, "worker expired")
        return self.transition(current, AgentStatus.TERMINATED, actor_id, "worker expired")
