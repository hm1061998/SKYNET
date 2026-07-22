"""Bounded structured agent execution runtime."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.domain import AgentInstance, AgentStatus, BudgetUsage, DomainValidationError
from core.llm import extract_json

from .lifecycle import AgentLifecycleManager
from .prompting import AgentContext, PromptAssembler
from .providers import AgentCompletionProvider
from .routing import ModelRouter


class ResultStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class AgentExecutionResult:
    """Validated structured result; construction performs no domain mutation."""

    status: ResultStatus
    summary: str
    artifacts: tuple[dict[str, Any], ...] = ()
    proposed_tasks: tuple[dict[str, Any], ...] = ()
    handoff: dict[str, Any] | None = None
    policy_requests: tuple[dict[str, Any], ...] = ()
    usage: BudgetUsage = BudgetUsage()

    @classmethod
    def from_dict(cls, data: Any) -> "AgentExecutionResult":
        if not isinstance(data, dict):
            raise DomainValidationError("agent result must be an object")
        required = {"status", "summary", "artifacts", "proposed_tasks", "handoff", "policy_requests", "usage"}
        if set(data) != required:
            raise DomainValidationError(f"agent result keys must equal {sorted(required)}")
        if not isinstance(data["summary"], str) or not data["summary"].strip():
            raise DomainValidationError("agent result summary must be non-empty")
        for field_name in ("artifacts", "proposed_tasks", "policy_requests"):
            if not isinstance(data[field_name], list) or not all(isinstance(item, dict) for item in data[field_name]):
                raise DomainValidationError(f"agent result {field_name} must be a list of objects")
        if data["handoff"] is not None and not isinstance(data["handoff"], dict):
            raise DomainValidationError("agent result handoff must be an object or null")
        usage_data = data["usage"]
        if not isinstance(usage_data, dict) or set(usage_data) - {"tokens", "cost_units", "wall_seconds"}:
            raise DomainValidationError("agent result usage is invalid")
        return cls(ResultStatus(data["status"]), data["summary"], tuple(data["artifacts"]),
                   tuple(data["proposed_tasks"]), data["handoff"], tuple(data["policy_requests"]),
                   BudgetUsage(int(usage_data.get("tokens", 0)), float(usage_data.get("cost_units", 0)),
                               float(usage_data.get("wall_seconds", 0))))


@dataclass(frozen=True)
class RuntimeOutcome:
    instance: AgentInstance
    result: AgentExecutionResult | None
    error: str | None = None


class AgentRuntime:
    """Execute one assigned agent with bounded structured-output repair."""

    def __init__(self, provider: AgentCompletionProvider, router: ModelRouter,
                 lifecycle: AgentLifecycleManager, prompts: PromptAssembler | None = None,
                 max_repairs: int = 1) -> None:
        if max_repairs < 0 or max_repairs > 2:
            raise DomainValidationError("max_repairs must be between 0 and 2")
        self.provider = provider
        self.router = router
        self.lifecycle = lifecycle
        self.prompts = prompts or PromptAssembler()
        self.max_repairs = max_repairs

    def execute(self, context: AgentContext, actor_id: str = "agent_runtime") -> RuntimeOutcome:
        if context.instance.status is not AgentStatus.ASSIGNED:
            raise DomainValidationError("agent must be ASSIGNED before execution")
        instance = self.lifecycle.transition(context.instance, AgentStatus.RUNNING, actor_id)
        profile = self.router.for_agent(context.definition, organization_id=context.organization.id)
        messages = self.prompts.assemble(context)
        last_error = "malformed structured result"
        for attempt in range(self.max_repairs + 1):
            purpose = "agent_execute" if attempt == 0 else "agent_result_repair"
            raw = self.provider.complete(messages, profile, purpose)
            try:
                result = AgentExecutionResult.from_dict(extract_json(raw))
                target = {
                    ResultStatus.COMPLETED: AgentStatus.COMPLETED,
                    ResultStatus.NEEDS_INPUT: AgentStatus.WAITING,
                    ResultStatus.BLOCKED: AgentStatus.WAITING,
                    ResultStatus.FAILED: AgentStatus.FAILED,
                }[result.status]
                return RuntimeOutcome(self.lifecycle.transition(instance, target, actor_id), result)
            except (DomainValidationError, ValueError, TypeError) as exc:
                last_error = str(exc)
                messages = messages + [{
                    "role": "system",
                    "content": "Previous output was invalid. Return exactly the required JSON schema. Error: " + last_error,
                }]
        failed = self.lifecycle.transition(instance, AgentStatus.FAILED, actor_id, last_error)
        return RuntimeOutcome(failed, None, last_error)
