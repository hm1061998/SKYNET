"""Nested operational traces without private reasoning."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from core.domain import Clock, IdGenerator, UtcClock, UuidIdGenerator
from core.domain.base import json_value, require_id, require_utc
from core.governance import RedactionService

from .events import ObservabilityError, _reject_hidden


SPAN_KINDS = frozenset({"planning", "model_call", "retrieval", "tool_call", "skill_execution",
                        "review", "approval_wait", "persistence", "artifact_write"})


@dataclass(frozen=True)
class TraceSpan:
    span_id: str
    trace_id: str
    kind: str
    name: str
    started_at: datetime
    parent_span_id: str | None
    sanitized_inputs: dict[str, Any]
    status: str = "running"
    finished_at: datetime | None = None
    duration_ms: int | None = None
    sanitized_outputs: dict[str, Any] | None = None
    usage: dict[str, float | int] | None = None
    error_category: str | None = None

    @property
    def id(self) -> str:
        return self.span_id


@dataclass(frozen=True)
class Trace:
    trace_id: str
    organization_id: str
    work_order_id: str
    goal_id: str | None
    started_at: datetime
    spans: tuple[TraceSpan, ...] = ()


class TraceService:
    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None,
                 redaction: RedactionService | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.redaction = redaction or RedactionService()

    def create(self, organization_id: str, work_order_id: str, goal_id: str | None = None) -> Trace:
        return Trace(self.ids.new_id("TRACE"), organization_id, work_order_id, goal_id, self.clock.now())

    def start_span(self, trace: Trace, *, kind: str, name: str, inputs: dict[str, Any],
                   parent_span_id: str | None = None) -> tuple[Trace, TraceSpan]:
        if kind not in SPAN_KINDS:
            raise ObservabilityError("unsupported trace span kind")
        if parent_span_id and parent_span_id not in {item.id for item in trace.spans}:
            raise ObservabilityError("parent span does not belong to trace")
        _reject_hidden(inputs)
        span = TraceSpan(self.ids.new_id("SPAN"), trace.trace_id, kind, name, self.clock.now(),
                         parent_span_id, self.redaction.redact(inputs))
        return replace(trace, spans=trace.spans + (span,)), span

    def finish_span(self, trace: Trace, span_id: str, *, status: str,
                    outputs: dict[str, Any], usage: dict[str, float | int] | None = None,
                    error_category: str | None = None) -> Trace:
        _reject_hidden(outputs)
        now = self.clock.now()
        found = False
        spans = []
        for span in trace.spans:
            if span.id != span_id:
                spans.append(span)
                continue
            if span.status != "running":
                raise ObservabilityError("trace span is already finished")
            found = True
            duration = max(0, int((now - span.started_at).total_seconds() * 1000))
            spans.append(replace(span, status=status, finished_at=now, duration_ms=duration,
                                 sanitized_outputs=self.redaction.redact(outputs), usage=usage or {},
                                 error_category=error_category))
        if not found:
            raise ObservabilityError("unknown trace span")
        return replace(trace, spans=tuple(spans))
