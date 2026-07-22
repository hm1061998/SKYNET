"""Approval, budget, secrets, redaction and audit services."""
from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Iterator, Mapping, Protocol

from core.domain import AuditEvent, Clock, IdGenerator, UtcClock, UuidIdGenerator

from .models import (ActionRequest, ApprovalGrant, ApprovalType, GovernanceError,
                     action_hash)


class ApprovalService:
    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def grant(self, request: ActionRequest, approval_type: ApprovalType, approver_id: str,
              expires_at: datetime) -> ApprovalGrant:
        return ApprovalGrant(self.ids.new_id("APP"), approval_type, request.action,
                             request.binding_hash, request.actor_id, approver_id,
                             request.work_order_id, request.task_id,
                             request.constitution_version, self.clock.now(), expires_at)

    def valid(self, grant: ApprovalGrant, request: ActionRequest) -> bool:
        return (self.clock.now() < grant.expires_at and grant.action == request.action and
                grant.action_hash == request.binding_hash and grant.actor_id == request.actor_id and
                grant.work_order_id == request.work_order_id and grant.task_id == request.task_id and
                grant.constitution_version == request.constitution_version)


@dataclass(frozen=True)
class BudgetLimits:
    tokens: int = 0
    provider_cost: float = 0
    wall_seconds: float = 0
    tool_calls: int = 0
    retries: int = 0
    artifact_bytes: int = 0
    workers: int = 0
    parallel_tasks: int = 0

    def __post_init__(self) -> None:
        if any(getattr(self, name) < 0 for name in self.__dataclass_fields__):
            raise GovernanceError("budget values cannot be negative")


@dataclass(frozen=True)
class BudgetConsumption(BudgetLimits):
    pass


@dataclass(frozen=True)
class BudgetResult:
    allowed: bool
    usage: BudgetConsumption
    blocked: bool
    escalation: dict[str, str] | None = None


class BudgetManager:
    def __init__(self, limits: BudgetLimits, escalation_target: str = "human") -> None:
        self.limits = limits
        self.usage = BudgetConsumption()
        self.escalation_target = escalation_target

    def consume(self, delta: BudgetConsumption) -> BudgetResult:
        values = {name: getattr(self.usage, name) + getattr(delta, name)
                  for name in BudgetLimits.__dataclass_fields__}
        next_usage = BudgetConsumption(**values)
        exceeded = [name for name in values if values[name] > getattr(self.limits, name)]
        if exceeded:
            return BudgetResult(False, self.usage, True,
                                {"type": "escalation", "target": self.escalation_target,
                                 "reason": "budget exhausted: " + ", ".join(exceeded)})
        self.usage = next_usage
        return BudgetResult(True, self.usage, False)


class SecretBroker(Protocol):
    @contextmanager
    def inject(self, secret_ids: tuple[str, ...], action_id: str) -> Iterator[Mapping[str, str]]: ...


class InMemorySecretBroker:
    """Test broker that exposes approved values only inside a context manager."""
    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)

    @contextmanager
    def inject(self, secret_ids: tuple[str, ...], action_id: str) -> Iterator[Mapping[str, str]]:
        if not action_id:
            raise GovernanceError("approved action ID is required for secret injection")
        selected = {key: self._values[key] for key in secret_ids if key in self._values}
        if len(selected) != len(secret_ids):
            raise GovernanceError("secret grant is unavailable")
        yield selected
        selected.clear()


class RedactionService:
    PATTERNS = (
        re.compile(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*([^\s,;]+)"),
        re.compile(r"\b(?:sk|ghp|xox[baprs])-[A-Za-z0-9_-]{8,}\b"),
    )

    def redact(self, value: Any) -> Any:
        if isinstance(value, str):
            result = value
            result = self.PATTERNS[0].sub(lambda m: f"{m.group(1)}=[REDACTED]", result)
            result = self.PATTERNS[1].sub("[REDACTED]", result)
            return result
        if isinstance(value, dict):
            return {key: ("[REDACTED]" if key.lower() in {"api_key", "password", "secret", "token"}
                          else self.redact(item)) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(self.redact(item) for item in value)
        return value


class AuditService:
    REQUIRED = {"action", "arguments_hash", "policy_effect", "allowed", "reason"}

    def __init__(self, repository: Any, clock: Clock | None = None,
                 ids: IdGenerator | None = None, redaction: RedactionService | None = None) -> None:
        self.repository = repository
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.redaction = redaction or RedactionService()

    def record(self, request: ActionRequest, details: dict[str, Any]) -> AuditEvent:
        if not self.REQUIRED <= set(details):
            raise GovernanceError("governance audit record is incomplete")
        event = AuditEvent(self.ids.new_id("event"), "governance.action.decision",
                           request.actor_id, request.id, self.clock.now(), request.id,
                           self.redaction.redact(details))
        self.repository.add(event)
        return event
