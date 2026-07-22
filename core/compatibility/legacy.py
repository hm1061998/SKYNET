"""Observability-only adapters for legacy Skill Agent behavior."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.domain.base import Clock, IdGenerator, UtcClock, UuidIdGenerator
from core.domain.enums import AgentKind, GoalStatus, Priority, RiskLevel, TaskStatus, WorkOrderStatus
from core.domain.models import (
    AgentDefinition,
    Department,
    Goal,
    Organization,
    OrganizationConstitution,
    RoleDefinition,
    Task,
    WorkOrder,
)
from core.memory import Memory


@dataclass(frozen=True)
class LegacyInvocationProjection:
    """Domain projection of one invocation; it does not execute legacy work."""

    organization: Organization
    agent_definition: AgentDefinition
    goal: Goal
    work_order: WorkOrder
    task: Task

    def to_dict(self) -> dict[str, object]:
        return {
            "organization": self.organization.to_dict(),
            "agent_definition": self.agent_definition.to_dict(),
            "goal": self.goal.to_dict(),
            "work_order": self.work_order.to_dict(),
            "task": self.task.to_dict(),
        }


class LegacyInvocationAdapter:
    """Map a legacy task string to a minimal governed-domain projection."""

    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def project(self, task_text: str, owner_id: str = "legacy_owner") -> LegacyInvocationProjection:
        now = self.clock.now()
        organization_id = self.ids.new_id("org")
        department_id = self.ids.new_id("dept")
        role_id = self.ids.new_id("role")
        agent_id = self.ids.new_id("agent")
        goal_id = self.ids.new_id("goal")
        work_order_id = self.ids.new_id("wo")
        task_id = self.ids.new_id("task")
        constitution = OrganizationConstitution(
            version="legacy-v1",
            principles=("Preserve legacy behavior", "Observe without rerouting execution"),
            effective_at=now,
        )
        role = RoleDefinition(role_id, "Legacy Skill Agent", ("Execute one legacy invocation",))
        department = Department(department_id, "Legacy Runtime", (role_id,))
        organization = Organization(organization_id, "Default Legacy Organization", constitution,
                                    (department,), (role,))
        agent = AgentDefinition(agent_id, "Legacy Skill Agent", AgentKind.ROLE, role_id)
        goal = Goal(goal_id, task_text, task_text, owner_id, GoalStatus.ACTIVE, now)
        work_order = WorkOrder(work_order_id, goal_id, task_text, owner_id, constitution.version,
                               WorkOrderStatus.IN_PROGRESS, now, task_ids=(task_id,))
        task = Task(task_id, work_order_id, task_text, owner_id, TaskStatus.READY,
                    Priority.NORMAL, RiskLevel.MEDIUM, now)
        return LegacyInvocationProjection(organization, agent, goal, work_order, task)


class LegacyMemoryAdapter:
    """Preserve the existing JSONL Memory API behind an explicit compatibility seam."""

    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    def add_turn(self, role: str, content: str) -> None:
        self.memory.add_turn(role, content)

    def remember(self, text: str, kind: str = "note", tags: list[str] | None = None) -> dict:
        return self.memory.remember(text, kind=kind, tags=tags)

    def recall(self, query: str, k: int = 5) -> list[dict]:
        return self.memory.recall(query, k=k)

    def context_block(self, query: str = "") -> str:
        return self.memory.context_block(query)
