"""Sanitized organizational event model and recorder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from core.domain import Clock, IdGenerator, UtcClock, UuidIdGenerator
from core.domain.base import json_value, require_id, require_utc
from core.governance import RedactionService


class ObservabilityError(ValueError):
    pass


class EventSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


EVENT_TYPES = frozenset({
    "goal.created", "work_order.planned", "plan.approved", "plan.rejected",
    "task.transition", "agent.transition", "delegation.created", "handoff.decided",
    "model.called", "tool.called", "skill.called", "sandbox.executed",
    "artifact.created", "artifact.versioned", "review.decided", "policy.decided",
    "approval.requested", "approval.decided", "budget.used", "task.retried",
    "escalation.created", "execution.failed", "execution.completed",
})
FORBIDDEN_FIELDS = frozenset({"chain_of_thought", "reasoning", "hidden_reasoning", "private_thoughts"})


def _reject_hidden(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_FIELDS:
                raise ObservabilityError("private reasoning fields may not be recorded")
            _reject_hidden(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_hidden(item)


@dataclass(frozen=True)
class OrganizationEvent:
    event_id: str
    type: str
    timestamp: datetime
    organization_id: str
    work_order_id: str | None
    task_id: str | None
    agent_id: str | None
    correlation_id: str
    causation_id: str | None
    severity: EventSeverity
    public_summary: str
    metadata: dict[str, Any]
    redaction_status: str
    version: int = 1

    @property
    def id(self) -> str:
        return self.event_id

    def __post_init__(self) -> None:
        for value in (self.event_id, self.organization_id, self.correlation_id):
            require_id(value)
        require_utc(self.timestamp, "event.timestamp")
        if self.type not in EVENT_TYPES or not self.public_summary.strip():
            raise ObservabilityError("event type and public summary are required")
        _reject_hidden(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)


class EventRecorder:
    """Create redacted events and append them to the configured sink."""
    def __init__(self, sink: Callable[[OrganizationEvent], None], clock: Clock | None = None,
                 ids: IdGenerator | None = None, redaction: RedactionService | None = None) -> None:
        self.sink = sink
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.redaction = redaction or RedactionService()

    def record(self, *, type: str, organization_id: str, correlation_id: str,
               public_summary: str, metadata: dict[str, Any], work_order_id: str | None = None,
               task_id: str | None = None, agent_id: str | None = None,
               causation_id: str | None = None,
               severity: EventSeverity = EventSeverity.INFO) -> OrganizationEvent:
        _reject_hidden(metadata)
        sanitized = self.redaction.redact(metadata)
        sanitized_summary = self.redaction.redact(public_summary)
        redacted = sanitized != metadata or sanitized_summary != public_summary
        event = OrganizationEvent(self.ids.new_id("EVT"), type, self.clock.now(), organization_id,
            work_order_id, task_id, agent_id, correlation_id, causation_id, severity,
            sanitized_summary, sanitized, "redacted" if redacted else "clean")
        self.sink(event)
        return event
