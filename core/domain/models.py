"""Validated domain objects for the governed organization runtime."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, ClassVar

from .base import (
    DomainValidationError,
    InvalidTransitionError,
    json_value,
    require_enum,
    require_id,
    require_text,
    require_utc,
    utc_from_iso,
)
from .enums import (
    AgentKind,
    AgentStatus,
    ApprovalStatus,
    ArtifactType,
    ExecutionStatus,
    GoalStatus,
    PolicyOutcome,
    Priority,
    RiskLevel,
    TaskStatus,
    WorkOrderStatus,
)


class Serializable:
    """Mixin for explicit JSON-compatible domain serialization."""

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)


@dataclass(frozen=True)
class Capability(Serializable):
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        require_text(self.name, "capability.name")


@dataclass(frozen=True)
class ToolGrant(Serializable):
    tool_name: str
    scopes: tuple[str, ...] = ()
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        require_text(self.tool_name, "tool_grant.tool_name")
        if self.expires_at is not None:
            require_utc(self.expires_at, "tool_grant.expires_at")


@dataclass(frozen=True)
class ModelProfile(Serializable):
    provider: str
    model: str
    role: str
    max_tokens: int | None = None

    def __post_init__(self) -> None:
        require_text(self.provider, "model_profile.provider")
        require_text(self.model, "model_profile.model")
        require_text(self.role, "model_profile.role")
        if self.max_tokens is not None and self.max_tokens < 0:
            raise DomainValidationError("model_profile.max_tokens cannot be negative")


@dataclass(frozen=True)
class RoleDefinition(Serializable):
    id: str
    name: str
    responsibilities: tuple[str, ...] = ()
    capabilities: tuple[Capability, ...] = ()

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.name, "role.name")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoleDefinition":
        return cls(data["id"], data["name"], tuple(data.get("responsibilities", ())),
                   tuple(Capability(**item) for item in data.get("capabilities", ())))


@dataclass(frozen=True)
class Department(Serializable):
    id: str
    name: str
    role_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.name, "department.name")
        for role_id in self.role_ids:
            require_id(role_id, "department.role_id")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Department":
        return cls(data["id"], data["name"], tuple(data.get("role_ids", ())))


@dataclass(frozen=True)
class ReportingLine(Serializable):
    manager_role_id: str
    report_role_id: str

    def __post_init__(self) -> None:
        require_id(self.manager_role_id, "manager_role_id")
        require_id(self.report_role_id, "report_role_id")
        if self.manager_role_id == self.report_role_id:
            raise DomainValidationError("a role cannot report to itself")


@dataclass(frozen=True)
class OrganizationConstitution(Serializable):
    version: str
    principles: tuple[str, ...]
    effective_at: datetime

    def __post_init__(self) -> None:
        require_text(self.version, "constitution.version")
        if not self.principles:
            raise DomainValidationError("constitution requires at least one principle")
        require_utc(self.effective_at, "constitution.effective_at")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrganizationConstitution":
        return cls(data["version"], tuple(data["principles"]), utc_from_iso(data["effective_at"]))


@dataclass(frozen=True)
class Organization(Serializable):
    id: str
    name: str
    constitution: OrganizationConstitution
    departments: tuple[Department, ...] = ()
    roles: tuple[RoleDefinition, ...] = ()
    reporting_lines: tuple[ReportingLine, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.name, "organization.name")
        if self.version < 1:
            raise DomainValidationError("organization.version must be positive")
        role_ids = [role.id for role in self.roles]
        if len(role_ids) != len(set(role_ids)):
            raise DomainValidationError("organization role IDs must be unique")
        department_ids = [department.id for department in self.departments]
        if len(department_ids) != len(set(department_ids)):
            raise DomainValidationError("organization department IDs must be unique")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Organization":
        return cls(
            id=data["id"], name=data["name"],
            constitution=OrganizationConstitution.from_dict(data["constitution"]),
            departments=tuple(Department.from_dict(item) for item in data.get("departments", ())),
            roles=tuple(RoleDefinition.from_dict(item) for item in data.get("roles", ())),
            reporting_lines=tuple(ReportingLine(**item) for item in data.get("reporting_lines", ())),
            version=int(data.get("version", 1)),
        )


@dataclass(frozen=True)
class AgentDefinition(Serializable):
    id: str
    name: str
    kind: AgentKind
    role_id: str
    capabilities: tuple[Capability, ...] = ()
    tool_grants: tuple[ToolGrant, ...] = ()
    model_profile: ModelProfile | None = None
    version: int = 1
    mission: str = ""
    department_id: str | None = None
    reports_to: str | None = None
    delegates_to: tuple[str, ...] = ()
    model_profile_name: str | None = None
    memory_scopes: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()
    limits: dict[str, int | float] = field(default_factory=dict)
    role_prompt: str = ""

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.name, "agent_definition.name")
        require_id(self.role_id, "agent_definition.role_id")
        require_enum(self.kind, AgentKind, "agent_definition.kind")
        if self.version < 1:
            raise DomainValidationError("agent_definition.version must be positive")
        if self.department_id is not None:
            require_id(self.department_id, "agent_definition.department_id")
        if self.reports_to is not None:
            require_id(self.reports_to, "agent_definition.reports_to")
            if self.reports_to == self.id:
                raise DomainValidationError("agent definition cannot report to itself")
        if any(value < 0 for value in self.limits.values()):
            raise DomainValidationError("agent definition limits cannot be negative")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentDefinition":
        profile = data.get("model_profile")
        grants = []
        for item in data.get("tool_grants", ()):
            grants.append(ToolGrant(item["tool_name"], tuple(item.get("scopes", ())),
                                    utc_from_iso(item["expires_at"]) if item.get("expires_at") else None))
        return cls(data["id"], data["name"], AgentKind(data["kind"]), data["role_id"],
                   tuple(Capability(**item) for item in data.get("capabilities", ())), tuple(grants),
                   ModelProfile(**profile) if profile else None, int(data.get("version", 1)),
                   data.get("mission", ""), data.get("department_id"), data.get("reports_to"),
                   tuple(data.get("delegates_to", ())), data.get("model_profile_name"),
                   tuple(data.get("memory_scopes", ())), tuple(data.get("policies", ())),
                   dict(data.get("limits", {})), data.get("role_prompt", ""))


@dataclass(frozen=True)
class AgentInstance(Serializable):
    id: str
    definition_id: str
    status: AgentStatus
    created_at: datetime
    work_order_id: str | None = None
    version: int = 1
    parent_definition_id: str | None = None
    source_task_id: str | None = None
    expires_at: datetime | None = None
    context_id: str | None = None
    budget_id: str | None = None
    granted_capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.definition_id, "agent_instance.definition_id")
        require_enum(self.status, AgentStatus, "agent_instance.status")
        require_utc(self.created_at, "agent_instance.created_at")
        if self.work_order_id is not None:
            require_id(self.work_order_id, "agent_instance.work_order_id")
        if self.version < 1:
            raise DomainValidationError("agent_instance.version must be positive")
        for field_name, value in (
            ("parent_definition_id", self.parent_definition_id),
            ("source_task_id", self.source_task_id),
            ("context_id", self.context_id),
            ("budget_id", self.budget_id),
        ):
            if value is not None:
                require_id(value, f"agent_instance.{field_name}")
        if self.expires_at is not None:
            require_utc(self.expires_at, "agent_instance.expires_at")
            if self.expires_at <= self.created_at:
                raise DomainValidationError("agent instance expiry must be after creation")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentInstance":
        return cls(data["id"], data["definition_id"], AgentStatus(data["status"]),
                   utc_from_iso(data["created_at"]), data.get("work_order_id"), int(data.get("version", 1)),
                   data.get("parent_definition_id"), data.get("source_task_id"),
                   utc_from_iso(data["expires_at"]) if data.get("expires_at") else None,
                   data.get("context_id"), data.get("budget_id"),
                   tuple(data.get("granted_capabilities", ())))


@dataclass(frozen=True)
class AcceptanceCriterion(Serializable):
    id: str
    description: str
    required: bool = True

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.description, "acceptance_criterion.description")


@dataclass(frozen=True)
class Goal(Serializable):
    id: str
    title: str
    description: str
    owner_id: str
    status: GoalStatus
    created_at: datetime
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.title, "goal.title")
        require_id(self.owner_id, "goal.owner_id")
        require_enum(self.status, GoalStatus, "goal.status")
        require_utc(self.created_at, "goal.created_at")
        if self.version < 1:
            raise DomainValidationError("goal.version must be positive")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        return cls(data["id"], data["title"], data.get("description", ""), data["owner_id"],
                   GoalStatus(data["status"]), utc_from_iso(data["created_at"]),
                   tuple(AcceptanceCriterion(**item) for item in data.get("acceptance_criteria", ())),
                   int(data.get("version", 1)))


@dataclass(frozen=True)
class TaskDependency(Serializable):
    task_id: str
    depends_on_task_id: str

    def __post_init__(self) -> None:
        require_id(self.task_id, "dependency.task_id")
        require_id(self.depends_on_task_id, "dependency.depends_on_task_id")
        if self.task_id == self.depends_on_task_id:
            raise DomainValidationError("a task cannot depend on itself")


TASK_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.DRAFT: frozenset({TaskStatus.BLOCKED, TaskStatus.READY, TaskStatus.WAITING_INPUT,
                                 TaskStatus.WAITING_APPROVAL, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED}),
    TaskStatus.BLOCKED: frozenset({TaskStatus.READY, TaskStatus.WAITING_INPUT,
                                   TaskStatus.WAITING_APPROVAL, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED}),
    TaskStatus.READY: frozenset({TaskStatus.BLOCKED, TaskStatus.IN_PROGRESS,
                                 TaskStatus.TIMED_OUT, TaskStatus.CANCELLED}),
    TaskStatus.IN_PROGRESS: frozenset({TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL,
                                       TaskStatus.REVIEW, TaskStatus.COMPLETED, TaskStatus.FAILED,
                                       TaskStatus.TIMED_OUT, TaskStatus.CANCELLED}),
    TaskStatus.WAITING_INPUT: frozenset({TaskStatus.READY, TaskStatus.TIMED_OUT,
                                         TaskStatus.CANCELLED, TaskStatus.FAILED}),
    TaskStatus.WAITING_APPROVAL: frozenset({TaskStatus.READY, TaskStatus.TIMED_OUT,
                                            TaskStatus.CANCELLED, TaskStatus.FAILED}),
    TaskStatus.REVIEW: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset({TaskStatus.READY, TaskStatus.CANCELLED}),
    TaskStatus.TIMED_OUT: frozenset({TaskStatus.READY, TaskStatus.CANCELLED}),
    TaskStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class Task(Serializable):
    id: str
    work_order_id: str
    title: str
    owner_id: str
    status: TaskStatus
    priority: Priority
    risk_level: RiskLevel
    created_at: datetime
    dependencies: tuple[TaskDependency, ...] = ()
    reviewer_id: str | None = None
    author_id: str | None = None
    version: int = 1
    objective: str = ""
    assigned_role: str = ""
    worker_specialization: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_output_schema: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = ()
    retry_max_attempts: int = 1
    retry_backoff_seconds: float = 0.0
    timeout_seconds: float = 300.0
    required_permissions: tuple[str, ...] = ()
    required_artifact_ids: tuple[str, ...] = ()
    allocated_tokens: int = 0
    allocated_cost_units: float = 0.0
    allocated_wall_seconds: float = 0.0
    review_policy: str = "none"
    idempotency_key: str = ""
    attempt_count: int = 0
    next_eligible_at: datetime | None = None

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.work_order_id, "task.work_order_id")
        require_text(self.title, "task.title")
        require_id(self.owner_id, "task.owner_id")
        require_enum(self.status, TaskStatus, "task.status")
        require_enum(self.priority, Priority, "task.priority")
        require_enum(self.risk_level, RiskLevel, "task.risk_level")
        require_utc(self.created_at, "task.created_at")
        if self.version < 1:
            raise DomainValidationError("task.version must be positive")
        keys = [(item.task_id, item.depends_on_task_id) for item in self.dependencies]
        if len(keys) != len(set(keys)):
            raise DomainValidationError("duplicate task dependency")
        if any(item.task_id != self.id for item in self.dependencies):
            raise DomainValidationError("dependency task_id must match task.id")
        if self.retry_max_attempts < 1 or self.retry_backoff_seconds < 0 or self.timeout_seconds <= 0:
            raise DomainValidationError("task retry and timeout values are invalid")
        if (self.allocated_tokens < 0 or self.allocated_cost_units < 0
                or self.allocated_wall_seconds < 0 or self.attempt_count < 0):
            raise DomainValidationError("task allocation and attempt values cannot be negative")
        if self.next_eligible_at is not None:
            require_utc(self.next_eligible_at, "task.next_eligible_at")
        json_value(self.inputs)
        json_value(self.expected_output_schema)

    def transition(self, target: TaskStatus, *, reopen: bool = False) -> "Task":
        """Return a new task after validating a lifecycle transition."""
        if target == self.status:
            return self
        if self.status == TaskStatus.COMPLETED and reopen and target == TaskStatus.IN_PROGRESS:
            return replace(self, status=target, version=self.version + 1)
        if target not in TASK_TRANSITIONS[self.status]:
            raise InvalidTransitionError(f"cannot transition task from {self.status.value} to {target.value}")
        return replace(self, status=target, version=self.version + 1)

    def require_separate_reviewer(self) -> None:
        """Enforce reviewer/author separation when a policy requires it."""
        if not self.reviewer_id or not self.author_id:
            raise DomainValidationError("separation of duties requires author and reviewer")
        if self.reviewer_id == self.author_id:
            raise DomainValidationError("reviewer cannot be the author")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        return cls(
            data["id"], data["work_order_id"], data["title"], data["owner_id"],
            TaskStatus(data["status"]), Priority(data["priority"]), RiskLevel(data["risk_level"]),
            utc_from_iso(data["created_at"]),
            tuple(TaskDependency(**item) for item in data.get("dependencies", ())),
            data.get("reviewer_id"), data.get("author_id"), int(data.get("version", 1)),
            data.get("objective", ""), data.get("assigned_role", ""), data.get("worker_specialization"),
            dict(data.get("inputs", {})), dict(data.get("expected_output_schema", {})),
            tuple(AcceptanceCriterion(**item) for item in data.get("acceptance_criteria", ())),
            int(data.get("retry_max_attempts", 1)), float(data.get("retry_backoff_seconds", 0)),
            float(data.get("timeout_seconds", 300)), tuple(data.get("required_permissions", ())),
            tuple(data.get("required_artifact_ids", ())), int(data.get("allocated_tokens", 0)),
            float(data.get("allocated_cost_units", 0)), float(data.get("allocated_wall_seconds", 0)),
            data.get("review_policy", "none"), data.get("idempotency_key", ""),
            int(data.get("attempt_count", 0)),
            utc_from_iso(data["next_eligible_at"]) if data.get("next_eligible_at") else None,
        )


@dataclass(frozen=True)
class WorkOrder(Serializable):
    id: str
    goal_id: str
    title: str
    accountable_owner_id: str
    constitution_version: str
    status: WorkOrderStatus
    created_at: datetime
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = ()
    task_ids: tuple[str, ...] = ()
    version: int = 1
    organization_id: str = ""
    objective: str = ""
    requested_by: str = ""
    deliverables: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    risk_level: RiskLevel = RiskLevel.LOW
    budget_id: str | None = None
    deadline: datetime | None = None
    approval_required: bool = False
    approval_granted: bool = False
    artifact_ids: tuple[str, ...] = ()
    completion_event_emitted: bool = False

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.goal_id, "work_order.goal_id")
        require_text(self.title, "work_order.title")
        require_id(self.accountable_owner_id, "work_order.accountable_owner_id")
        require_text(self.constitution_version, "work_order.constitution_version")
        require_enum(self.status, WorkOrderStatus, "work_order.status")
        require_utc(self.created_at, "work_order.created_at")
        if self.version < 1:
            raise DomainValidationError("work_order.version must be positive")
        if len(self.task_ids) != len(set(self.task_ids)):
            raise DomainValidationError("work_order task IDs must be unique")
        require_enum(self.risk_level, RiskLevel, "work_order.risk_level")
        if self.organization_id:
            require_id(self.organization_id, "work_order.organization_id")
        if self.requested_by:
            require_id(self.requested_by, "work_order.requested_by")
        if self.budget_id is not None:
            require_id(self.budget_id, "work_order.budget_id")
        if self.deadline is not None:
            require_utc(self.deadline, "work_order.deadline")
            if self.deadline <= self.created_at:
                raise DomainValidationError("work order deadline must be after creation")
        if self.approval_granted and not self.approval_required:
            raise DomainValidationError("approval cannot be granted when it is not required")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkOrder":
        return cls(
            data["id"], data["goal_id"], data["title"], data["accountable_owner_id"],
            data["constitution_version"], WorkOrderStatus(data["status"]), utc_from_iso(data["created_at"]),
            tuple(AcceptanceCriterion(**item) for item in data.get("acceptance_criteria", ())),
            tuple(data.get("task_ids", ())), int(data.get("version", 1)),
            data.get("organization_id", ""), data.get("objective", ""), data.get("requested_by", ""),
            tuple(data.get("deliverables", ())), tuple(data.get("constraints", ())),
            RiskLevel(data.get("risk_level", "low")), data.get("budget_id"),
            utc_from_iso(data["deadline"]) if data.get("deadline") else None,
            bool(data.get("approval_required", False)), bool(data.get("approval_granted", False)),
            tuple(data.get("artifact_ids", ())), bool(data.get("completion_event_emitted", False)),
        )


@dataclass(frozen=True)
class PermissionRequest(Serializable):
    id: str
    actor_id: str
    action: str
    resource: str
    scopes: tuple[str, ...]
    requested_at: datetime

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.actor_id, "permission_request.actor_id")
        require_text(self.action, "permission_request.action")
        require_text(self.resource, "permission_request.resource")
        require_utc(self.requested_at, "permission_request.requested_at")


@dataclass(frozen=True)
class ApprovalDecision(Serializable):
    status: ApprovalStatus
    actor_id: str
    decided_at: datetime
    reason: str = ""

    def __post_init__(self) -> None:
        require_enum(self.status, ApprovalStatus, "approval_decision.status")
        if self.status == ApprovalStatus.PENDING:
            raise DomainValidationError("an approval decision cannot be pending")
        require_id(self.actor_id, "approval_decision.actor_id")
        require_utc(self.decided_at, "approval_decision.decided_at")


@dataclass(frozen=True)
class ApprovalRequest(Serializable):
    id: str
    permission_request: PermissionRequest
    requested_at: datetime
    expires_at: datetime | None = None
    decision: ApprovalDecision | None = None
    version: int = 1

    def __post_init__(self) -> None:
        require_id(self.id)
        require_utc(self.requested_at, "approval_request.requested_at")
        if self.expires_at is not None:
            require_utc(self.expires_at, "approval_request.expires_at")
            if self.expires_at <= self.requested_at:
                raise DomainValidationError("approval expiry must be after request time")
        if self.version < 1:
            raise DomainValidationError("approval_request.version must be positive")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        permission = data["permission_request"]
        request = PermissionRequest(permission["id"], permission["actor_id"], permission["action"],
                                    permission["resource"], tuple(permission.get("scopes", ())),
                                    utc_from_iso(permission["requested_at"]))
        decision_data = data.get("decision")
        decision = None if not decision_data else ApprovalDecision(
            ApprovalStatus(decision_data["status"]), decision_data["actor_id"],
            utc_from_iso(decision_data["decided_at"]), decision_data.get("reason", ""))
        return cls(data["id"], request, utc_from_iso(data["requested_at"]),
                   utc_from_iso(data["expires_at"]) if data.get("expires_at") else None,
                   decision, int(data.get("version", 1)))


@dataclass(frozen=True)
class BudgetUsage(Serializable):
    tokens: int = 0
    cost_units: float = 0.0
    wall_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.tokens < 0 or self.cost_units < 0 or self.wall_seconds < 0:
            raise DomainValidationError("budget usage cannot be negative")

    def plus(self, other: "BudgetUsage") -> "BudgetUsage":
        return BudgetUsage(self.tokens + other.tokens, self.cost_units + other.cost_units,
                           self.wall_seconds + other.wall_seconds)


@dataclass(frozen=True)
class Budget(Serializable):
    id: str
    work_order_id: str
    token_limit: int
    cost_limit: float
    wall_seconds_limit: float
    usage: BudgetUsage = field(default_factory=BudgetUsage)
    version: int = 1

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.work_order_id, "budget.work_order_id")
        if self.token_limit < 0 or self.cost_limit < 0 or self.wall_seconds_limit < 0:
            raise DomainValidationError("budget limits cannot be negative")
        if self.version < 1:
            raise DomainValidationError("budget.version must be positive")
        self._validate_usage(self.usage)

    def _validate_usage(self, usage: BudgetUsage) -> None:
        if (usage.tokens > self.token_limit or usage.cost_units > self.cost_limit
                or usage.wall_seconds > self.wall_seconds_limit):
            raise DomainValidationError("budget usage exceeds a configured limit")

    def consume(self, delta: BudgetUsage) -> "Budget":
        usage = self.usage.plus(delta)
        self._validate_usage(usage)
        return replace(self, usage=usage, version=self.version + 1)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Budget":
        return cls(data["id"], data["work_order_id"], int(data["token_limit"]),
                   float(data["cost_limit"]), float(data["wall_seconds_limit"]),
                   BudgetUsage(**data.get("usage", {})), int(data.get("version", 1)))


@dataclass(frozen=True)
class PolicyDecision(Serializable):
    id: str
    request_id: str
    outcome: PolicyOutcome
    reason: str
    decided_at: datetime

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.request_id, "policy_decision.request_id")
        require_enum(self.outcome, PolicyOutcome, "policy_decision.outcome")
        require_text(self.reason, "policy_decision.reason")
        require_utc(self.decided_at, "policy_decision.decided_at")


@dataclass(frozen=True)
class ArtifactVersion(Serializable):
    id: str
    artifact_id: str
    version_number: int
    content_hash: str
    storage_reference: str
    created_at: datetime

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.artifact_id, "artifact_version.artifact_id")
        if self.version_number < 1:
            raise DomainValidationError("artifact version number must be positive")
        require_text(self.content_hash, "artifact_version.content_hash")
        require_text(self.storage_reference, "artifact_version.storage_reference")
        require_utc(self.created_at, "artifact_version.created_at")


@dataclass(frozen=True)
class Artifact(Serializable):
    id: str
    name: str
    artifact_type: ArtifactType
    producer_id: str
    source_task_id: str
    content_hash: str
    created_at: datetime
    versions: tuple[ArtifactVersion, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.name, "artifact.name")
        require_enum(self.artifact_type, ArtifactType, "artifact.artifact_type")
        require_id(self.producer_id, "artifact.producer_id")
        require_id(self.source_task_id, "artifact.source_task_id")
        require_text(self.content_hash, "artifact.content_hash")
        require_utc(self.created_at, "artifact.created_at")
        if self.version < 1:
            raise DomainValidationError("artifact.version must be positive")
        numbers = [item.version_number for item in self.versions]
        if len(numbers) != len(set(numbers)):
            raise DomainValidationError("artifact version numbers must be unique")
        if any(item.artifact_id != self.id for item in self.versions):
            raise DomainValidationError("artifact version must reference its artifact")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        versions = tuple(ArtifactVersion(
            item["id"], item["artifact_id"], int(item["version_number"]), item["content_hash"],
            item["storage_reference"], utc_from_iso(item["created_at"])) for item in data.get("versions", ()))
        return cls(data["id"], data["name"], ArtifactType(data["artifact_type"]), data["producer_id"],
                   data["source_task_id"], data["content_hash"], utc_from_iso(data["created_at"]),
                   versions, int(data.get("version", 1)))


@dataclass(frozen=True)
class AuditEvent(Serializable):
    id: str
    event_type: str
    actor_id: str
    subject_id: str
    occurred_at: datetime
    correlation_id: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_id(self.id)
        require_text(self.event_type, "audit_event.event_type")
        require_id(self.actor_id, "audit_event.actor_id")
        require_id(self.subject_id, "audit_event.subject_id")
        require_utc(self.occurred_at, "audit_event.occurred_at")
        require_id(self.correlation_id, "audit_event.correlation_id")
        json_value(self.details)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AuditEvent":
        return cls(data["id"], data["event_type"], data["actor_id"], data["subject_id"],
                   utc_from_iso(data["occurred_at"]), data["correlation_id"], dict(data.get("details", {})))


@dataclass(frozen=True)
class ExecutionRecord(Serializable):
    id: str
    task_id: str
    agent_instance_id: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime | None = None
    artifact_ids: tuple[str, ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        require_id(self.id)
        require_id(self.task_id, "execution.task_id")
        require_id(self.agent_instance_id, "execution.agent_instance_id")
        require_enum(self.status, ExecutionStatus, "execution.status")
        require_utc(self.started_at, "execution.started_at")
        if self.finished_at is not None:
            require_utc(self.finished_at, "execution.finished_at")
            if self.finished_at < self.started_at:
                raise DomainValidationError("execution cannot finish before it starts")


DOMAIN_TYPES: dict[str, type[Serializable]] = {
    cls.__name__: cls for cls in (
        Organization, AgentDefinition, AgentInstance, Goal, WorkOrder, Task,
        Artifact, ApprovalRequest, Budget,
    )
}
