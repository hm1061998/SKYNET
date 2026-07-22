"""Bounded lifecycle and classification values."""
from enum import Enum


class AgentKind(str, Enum):
    ROLE = "role"
    WORKER = "worker"
    CONTROL = "control"


class AgentStatus(str, Enum):
    DEFINED = "defined"
    READY = "ready"
    ASSIGNED = "assigned"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FAILED = "failed"
    IDLE = "idle"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    RETIRED = "retired"


class GoalStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkOrderStatus(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    BLOCKED = "blocked"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PolicyOutcome(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class ArtifactType(str, Enum):
    SOURCE_CODE = "source_code"
    DOCUMENT = "document"
    TEST_RESULT = "test_result"
    PLAN = "plan"
    REPORT = "report"
    DATA = "data"
    OTHER = "other"


class ExecutionStatus(str, Enum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
