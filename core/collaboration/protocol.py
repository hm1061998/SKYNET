"""Task-scoped structured collaboration message protocol."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from core.domain import (AuditEvent, Clock, DomainValidationError, IdGenerator, UtcClock,
                         UuidIdGenerator)
from core.domain.base import json_value, require_id, require_utc, utc_from_iso


class CollaborationError(DomainValidationError):
    """Raised when a collaboration command or envelope is invalid."""


class MessageType(str, Enum):
    DELEGATION = "delegation"
    HANDOFF = "handoff"
    REVIEW_REQUEST = "review_request"
    REVIEW_RESULT = "review_result"
    QUESTION = "question"
    ANSWER = "answer"
    STATUS = "status"
    ESCALATION = "escalation"


class Visibility(str, Enum):
    TASK = "task"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"
    HUMAN = "human"


class ContentTrust(str, Enum):
    TRUSTED_SYSTEM = "trusted_system"
    INTERNAL_GENERATED = "internal_generated"
    EXTERNAL_UNTRUSTED = "external_untrusted"


def _object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CollaborationError("message payload must be an object")
    json_value(payload)
    return payload


def _exact(payload: dict[str, Any], required: set[str], optional: set[str] = set()) -> None:
    keys = set(payload)
    if not required <= keys or keys - required - optional:
        raise CollaborationError(
            f"payload keys must include {sorted(required)} and only allow {sorted(optional)}")


def _strings(value: Any, field_name: str) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise CollaborationError(f"{field_name} must be a list of non-empty strings")


def validate_delegation(payload: Any) -> None:
    value = _object(payload)
    required = {"worker_definition_id", "child_task_id", "deliverables", "budget_allocation",
                "deadline", "context_package_id", "return_contract"}
    _exact(value, required)
    _strings(value["deliverables"], "deliverables")
    if not isinstance(value["budget_allocation"], dict) or not isinstance(value["return_contract"], dict):
        raise CollaborationError("delegation budget and return contract must be objects")


def validate_handoff(payload: Any) -> None:
    value = _object(payload)
    required = {"reason", "receiving_role", "context_package_id", "unresolved_obligations",
                "remaining_budget", "required_approval", "accepted", "rejection_reason"}
    _exact(value, required)
    _strings(value["unresolved_obligations"], "unresolved_obligations")
    if value["accepted"] not in (None, True, False):
        raise CollaborationError("handoff accepted must be boolean or null")
    if not isinstance(value["required_approval"], bool) or not isinstance(value["remaining_budget"], dict):
        raise CollaborationError("handoff approval/budget fields are invalid")


def validate_review_request(payload: Any) -> None:
    value = _object(payload)
    required = {"artifact_id", "artifact_version_id", "artifact_hash", "review_checklist",
                "acceptance_criteria", "severity_model", "required_reviewer_role", "author_agent"}
    _exact(value, required)
    for name in ("review_checklist", "acceptance_criteria", "severity_model"):
        _strings(value[name], name)


REVIEW_DECISIONS = {"approved", "approved_with_notes", "changes_requested", "rejected"}
REVIEW_SEVERITIES = {"critical", "high", "medium", "low", "info"}
REVIEW_CATEGORIES = {"correctness", "security", "maintainability", "testing", "requirements"}


def validate_review_result(payload: Any) -> None:
    value = _object(payload)
    required = {"decision", "findings", "summary", "reviewed_artifact_hash"}
    _exact(value, required)
    if value["decision"] not in REVIEW_DECISIONS or not isinstance(value["summary"], str):
        raise CollaborationError("review decision or summary is invalid")
    if not isinstance(value["findings"], list):
        raise CollaborationError("review findings must be a list")
    finding_keys = {"severity", "category", "location", "description", "required_action"}
    for finding in value["findings"]:
        if not isinstance(finding, dict) or set(finding) != finding_keys:
            raise CollaborationError("review finding has invalid schema")
        if finding["severity"] not in REVIEW_SEVERITIES or finding["category"] not in REVIEW_CATEGORIES:
            raise CollaborationError("review finding severity/category is invalid")


def validate_question(payload: Any) -> None:
    value = _object(payload)
    _exact(value, {"question"})
    if not isinstance(value["question"], str) or not value["question"].strip():
        raise CollaborationError("question must be non-empty")


def validate_answer(payload: Any) -> None:
    value = _object(payload)
    _exact(value, {"answer"})
    if not isinstance(value["answer"], str) or not value["answer"].strip():
        raise CollaborationError("answer must be non-empty")


def validate_status(payload: Any) -> None:
    value = _object(payload)
    _exact(value, {"status", "summary"})
    if not all(isinstance(value[name], str) and value[name] for name in ("status", "summary")):
        raise CollaborationError("status payload values must be non-empty strings")


def validate_escalation(payload: Any) -> None:
    value = _object(payload)
    _exact(value, {"reason", "target", "required_action"})
    if not all(isinstance(value[name], str) and value[name] for name in value):
        raise CollaborationError("escalation values must be non-empty strings")


PAYLOAD_VALIDATORS: dict[MessageType, Callable[[Any], None]] = {
    MessageType.DELEGATION: validate_delegation,
    MessageType.HANDOFF: validate_handoff,
    MessageType.REVIEW_REQUEST: validate_review_request,
    MessageType.REVIEW_RESULT: validate_review_result,
    MessageType.QUESTION: validate_question,
    MessageType.ANSWER: validate_answer,
    MessageType.STATUS: validate_status,
    MessageType.ESCALATION: validate_escalation,
}


@dataclass(frozen=True)
class CollaborationMessage:
    message_id: str
    organization_id: str
    work_order_id: str
    task_id: str
    type: MessageType
    from_agent: str
    to_agent: str
    created_at: datetime
    correlation_id: str
    causation_id: str | None
    payload: dict[str, Any]
    artifact_refs: tuple[str, ...]
    visibility: Visibility
    content_trust: ContentTrust
    version: int = 1

    @property
    def id(self) -> str:
        return self.message_id

    def __post_init__(self) -> None:
        for name in ("message_id", "organization_id", "work_order_id", "task_id",
                     "from_agent", "to_agent", "correlation_id"):
            require_id(getattr(self, name), name)
        if self.causation_id is not None:
            require_id(self.causation_id, "causation_id")
        require_utc(self.created_at, "created_at")
        if not isinstance(self.type, MessageType) or not isinstance(self.visibility, Visibility):
            raise CollaborationError("message type or visibility is invalid")
        if not isinstance(self.content_trust, ContentTrust):
            raise CollaborationError("message content trust is invalid")
        if self.from_agent == self.to_agent:
            raise CollaborationError("message sender and receiver must differ")
        PAYLOAD_VALIDATORS[self.type](self.payload)
        if self.version < 1:
            raise CollaborationError("message version must be positive")

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollaborationMessage":
        return cls(data["message_id"], data["organization_id"], data["work_order_id"],
                   data["task_id"], MessageType(data["type"]), data["from_agent"], data["to_agent"],
                   utc_from_iso(data["created_at"]), data["correlation_id"], data.get("causation_id"),
                   dict(data["payload"]), tuple(data.get("artifact_refs", ())),
                   Visibility(data["visibility"]), ContentTrust(data["content_trust"]),
                   int(data.get("version", 1)))


class MessageFactory:
    """Create complete envelopes with injected deterministic clock and IDs."""

    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def create(self, *, organization_id: str, work_order_id: str, task_id: str,
               type: MessageType, from_agent: str, to_agent: str, payload: dict[str, Any],
               correlation_id: str | None = None, causation_id: str | None = None,
               artifact_refs: tuple[str, ...] = (), visibility: Visibility = Visibility.TASK,
               content_trust: ContentTrust = ContentTrust.INTERNAL_GENERATED) -> CollaborationMessage:
        return CollaborationMessage(
            self.ids.new_id("MSG"), organization_id, work_order_id, task_id, type,
            from_agent, to_agent, self.clock.now(), correlation_id or self.ids.new_id("CORR"),
            causation_id, payload, artifact_refs, visibility, content_trust,
        )


class MessageRouter:
    """Route validated messages to type-specific handlers."""

    def __init__(self) -> None:
        self._handlers: dict[MessageType, Callable[[CollaborationMessage], Any]] = {}

    def register(self, message_type: MessageType,
                 handler: Callable[[CollaborationMessage], Any]) -> None:
        self._handlers[message_type] = handler

    def route(self, message: CollaborationMessage) -> Any:
        PAYLOAD_VALIDATORS[message.type](message.payload)
        if message.type not in self._handlers:
            raise CollaborationError(f"no handler for message type {message.type.value}")
        return self._handlers[message.type](message)


class CollaborationLog:
    """Persist organizational messages separately and emit an audit record."""

    def __init__(self, repository, emit: Callable[[AuditEvent], None] | None = None,
                 clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.repository = repository
        self.emit = emit or (lambda event: None)
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def append(self, message: CollaborationMessage) -> None:
        self.repository.add(message)
        self.emit(AuditEvent(self.ids.new_id("event"), "collaboration.message.created",
                             message.from_agent, message.message_id, self.clock.now(),
                             message.correlation_id,
                             {"type": message.type.value, "task_id": message.task_id,
                              "to_agent": message.to_agent}))
