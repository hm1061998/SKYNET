"""Governed delegation, handoff and common collaboration patterns."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any

from core.agents.definitions import AgentRegistry
from core.domain import (AgentKind, BudgetUsage, Clock, IdGenerator, UtcClock,
                         UuidIdGenerator)
from core.domain.base import json_value, require_id, require_utc

from .context import ContextPackage
from .protocol import (CollaborationError, CollaborationMessage, MessageFactory,
                       MessageType)


@dataclass(frozen=True)
class DelegationRecord:
    """Auditable assignment that keeps the delegator accountable."""

    id: str
    organization_id: str
    work_order_id: str
    task_id: str
    child_task_id: str
    delegator_id: str
    worker_definition_id: str
    accountable_agent_id: str
    deliverables: tuple[str, ...]
    budget_allocation: BudgetUsage
    deadline: datetime
    context_package_id: str
    return_contract: dict[str, Any]
    created_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        for name in ("id", "organization_id", "work_order_id", "task_id", "child_task_id",
                     "delegator_id", "worker_definition_id", "accountable_agent_id",
                     "context_package_id"):
            require_id(getattr(self, name), f"delegation.{name}")
        require_utc(self.deadline, "delegation.deadline")
        require_utc(self.created_at, "delegation.created_at")
        if self.deadline <= self.created_at:
            raise CollaborationError("delegation deadline must be in the future")
        if not self.deliverables:
            raise CollaborationError("delegation requires deliverables")
        json_value(self.return_contract)

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)


class DelegationService:
    """Create delegations only along declared organizational relationships."""

    def __init__(self, registry: AgentRegistry, messages: MessageFactory | None = None,
                 clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.registry = registry
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.messages = messages or MessageFactory(self.clock, self.ids)

    def delegate(self, *, organization_id: str, work_order_id: str, task_id: str,
                 child_task_id: str, delegator_definition_id: str,
                 delegator_agent_id: str, worker_definition_id: str,
                 worker_agent_id: str, deliverables: tuple[str, ...],
                 budget_allocation: BudgetUsage, deadline: datetime,
                 context: ContextPackage, return_contract: dict[str, Any]) -> tuple[DelegationRecord, CollaborationMessage]:
        parent = self.registry.get(delegator_definition_id)
        worker = self.registry.get(worker_definition_id)
        if parent.kind is not AgentKind.ROLE:
            raise CollaborationError("only role agents may delegate work")
        if worker_definition_id not in parent.delegates_to or worker.kind is not AgentKind.WORKER:
            raise CollaborationError("worker is not an authorized delegate")
        if (context.organization_id, context.work_order_id, context.task_id) != (
                organization_id, work_order_id, task_id):
            raise CollaborationError("delegation context scope does not match task")
        created = self.clock.now()
        record = DelegationRecord(
            self.ids.new_id("DEL"), organization_id, work_order_id, task_id, child_task_id,
            delegator_agent_id, worker_definition_id, delegator_agent_id, deliverables,
            budget_allocation, deadline, context.id, dict(return_contract), created,
        )
        message = self.messages.create(
            organization_id=organization_id, work_order_id=work_order_id, task_id=task_id,
            type=MessageType.DELEGATION, from_agent=delegator_agent_id, to_agent=worker_agent_id,
            payload={"worker_definition_id": worker_definition_id, "child_task_id": child_task_id,
                     "deliverables": list(deliverables),
                     "budget_allocation": budget_allocation.to_dict(),
                     "deadline": deadline.isoformat(), "context_package_id": context.id,
                     "return_contract": dict(return_contract)},
        )
        return record, message


class HandoffStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class HandoffRecord:
    id: str
    task_id: str
    from_agent: str
    to_agent: str
    accountable_agent_id: str
    reason: str
    status: HandoffStatus
    rejection_reason: str | None
    created_at: datetime
    decided_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        for value in (self.id, self.task_id, self.from_agent, self.to_agent,
                      self.accountable_agent_id):
            require_id(value)
        require_utc(self.created_at, "handoff.created_at")
        if self.decided_at:
            require_utc(self.decided_at, "handoff.decided_at")


class HandoffService:
    """Transfer accountability only after explicit receiver acceptance."""

    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def initiate(self, task_id: str, from_agent: str, to_agent: str, reason: str) -> HandoffRecord:
        if from_agent == to_agent or not reason.strip():
            raise CollaborationError("handoff requires a distinct receiver and reason")
        return HandoffRecord(self.ids.new_id("HAND"), task_id, from_agent, to_agent,
                             from_agent, reason, HandoffStatus.PENDING, None, self.clock.now())

    def accept(self, record: HandoffRecord, actor_id: str) -> HandoffRecord:
        self._pending_receiver(record, actor_id)
        return replace(record, status=HandoffStatus.ACCEPTED, accountable_agent_id=actor_id,
                       decided_at=self.clock.now(), version=record.version + 1)

    def reject(self, record: HandoffRecord, actor_id: str, reason: str) -> HandoffRecord:
        self._pending_receiver(record, actor_id)
        if not reason.strip():
            raise CollaborationError("handoff rejection requires a reason")
        return replace(record, status=HandoffStatus.REJECTED, rejection_reason=reason,
                       decided_at=self.clock.now(), version=record.version + 1)

    @staticmethod
    def _pending_receiver(record: HandoffRecord, actor_id: str) -> None:
        if record.status is not HandoffStatus.PENDING:
            raise CollaborationError("handoff is already decided")
        if actor_id != record.to_agent:
            raise CollaborationError("only the receiving agent may decide a handoff")


class CollaborationPatterns:
    """Construct scoped sequential and parallel specialist message flows."""

    def __init__(self, messages: MessageFactory) -> None:
        self.messages = messages

    def sequential(self, *, organization_id: str, work_order_id: str, task_id: str,
                   agents: tuple[str, ...], payloads: tuple[dict[str, Any], ...]) -> tuple[CollaborationMessage, ...]:
        if len(agents) != len(payloads) + 1:
            raise CollaborationError("sequential flow needs one more agent than payload")
        correlation: str | None = None
        causation: str | None = None
        result = []
        for index, payload in enumerate(payloads):
            message = self.messages.create(
                organization_id=organization_id, work_order_id=work_order_id, task_id=task_id,
                type=MessageType.STATUS, from_agent=agents[index], to_agent=agents[index + 1],
                payload=payload, correlation_id=correlation, causation_id=causation)
            correlation = message.correlation_id
            causation = message.message_id
            result.append(message)
        return tuple(result)

    def parallel(self, *, organization_id: str, work_order_id: str, task_id: str,
                 manager: str, specialists: tuple[str, ...], payload: dict[str, Any]) -> tuple[CollaborationMessage, ...]:
        correlation = self.messages.ids.new_id("CORR")
        return tuple(self.messages.create(
            organization_id=organization_id, work_order_id=work_order_id, task_id=task_id,
            type=MessageType.QUESTION, from_agent=manager, to_agent=specialist,
            payload=dict(payload), correlation_id=correlation) for specialist in specialists)
