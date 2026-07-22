"""Validated governance requests, policies and approval bindings."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from core.domain.base import json_value, require_id, require_utc
from core.domain import DomainValidationError, RiskLevel


class GovernanceError(DomainValidationError):
    """Raised when a governed operation violates a security invariant."""


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    REQUIRE_SECURITY_APPROVAL = "require_security_approval"
    REQUIRE_EXPLICIT_GRANT = "require_explicit_grant"
    DENY_UNLESS_ALLOWLISTED = "deny_unless_allowlisted"


class ApprovalType(str, Enum):
    PLAN = "plan_approval"
    PERMISSION_ELEVATION = "permission_elevation"
    DEPENDENCY_INSTALLATION = "dependency_installation"
    DESTRUCTIVE_FILE_ACTION = "destructive_file_action"
    EXTERNAL_COMMUNICATION = "external_communication"
    DEPLOYMENT = "deployment"
    PRODUCTION_DATA_ACCESS = "production_data_access"
    BUDGET_EXTENSION = "budget_extension"
    POLICY_EXCEPTION = "policy_exception"


class ExecutionMode(str, Enum):
    MOCK = "mock"
    DRY_RUN = "dry_run"
    SANDBOX = "sandbox"
    LEGACY_UNSAFE = "legacy_unsafe"


@dataclass(frozen=True)
class PolicyRule:
    action: str
    effect: PolicyEffect
    reason: str = ""


@dataclass(frozen=True)
class Constitution:
    version: str
    principles: tuple[str, ...]
    policies: tuple[PolicyRule, ...]

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.principles:
            raise GovernanceError("constitution version and principles are required")
        actions = [rule.action for rule in self.policies]
        if len(actions) != len(set(actions)):
            raise GovernanceError("constitution policy actions must be unique")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Constitution":
        try:
            principles = tuple(item["id"] if isinstance(item, dict) else str(item)
                               for item in data["principles"])
            policies = tuple(PolicyRule(str(item["action"]), PolicyEffect(item["effect"]),
                                        str(item.get("reason", ""))) for item in data["policies"])
            return cls(str(data["version"]), principles, policies)
        except (KeyError, TypeError, ValueError) as exc:
            raise GovernanceError(f"invalid constitution: {exc}") from exc


def action_hash(action: str, arguments: dict[str, Any]) -> str:
    """Return a stable binding hash for an exact action and JSON arguments."""
    payload = json.dumps({"action": action, "arguments": json_value(arguments)},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActionRequest:
    id: str
    action: str
    arguments: dict[str, Any]
    actor_id: str
    organization_id: str
    work_order_id: str
    task_id: str
    constitution_version: str
    risk_level: RiskLevel

    def __post_init__(self) -> None:
        for value in (self.id, self.actor_id, self.organization_id, self.work_order_id, self.task_id):
            require_id(value)
        if not self.action.strip() or not self.constitution_version.strip():
            raise GovernanceError("action and constitution version are required")
        if not isinstance(self.risk_level, RiskLevel):
            raise GovernanceError("action risk level is invalid")
        json_value(self.arguments)

    @property
    def binding_hash(self) -> str:
        return action_hash(self.action, self.arguments)


@dataclass(frozen=True)
class GovernanceDecision:
    request_id: str
    effect: PolicyEffect
    allowed: bool
    reason: str
    matched_rule: str | None


@dataclass(frozen=True)
class ApprovalGrant:
    id: str
    approval_type: ApprovalType
    action: str
    action_hash: str
    actor_id: str
    approver_id: str
    work_order_id: str
    task_id: str
    constitution_version: str
    granted_at: datetime
    expires_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        for value in (self.id, self.actor_id, self.approver_id, self.work_order_id, self.task_id):
            require_id(value)
        require_utc(self.granted_at, "approval.granted_at")
        require_utc(self.expires_at, "approval.expires_at")
        if self.expires_at <= self.granted_at:
            raise GovernanceError("approval expiration must follow grant time")

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)
