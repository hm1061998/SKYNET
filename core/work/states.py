"""Explicit Goal, Work Order and Task state-machine services."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from core.domain import (AuditEvent, Clock, Goal, GoalStatus, IdGenerator, InvalidTransitionError,
                         Task, TaskStatus, UtcClock, UuidIdGenerator, WorkOrder, WorkOrderStatus)
from core.domain.models import TASK_TRANSITIONS

GOAL_TRANSITIONS = {
    GoalStatus.DRAFT: frozenset({GoalStatus.CLARIFICATION, GoalStatus.READY, GoalStatus.CANCELLED}),
    GoalStatus.CLARIFICATION: frozenset({GoalStatus.READY, GoalStatus.CANCELLED}),
    GoalStatus.READY: frozenset({GoalStatus.ACTIVE, GoalStatus.CANCELLED}),
    GoalStatus.ACTIVE: frozenset({GoalStatus.COMPLETED, GoalStatus.CANCELLED}),
    GoalStatus.COMPLETED: frozenset(),
    GoalStatus.CANCELLED: frozenset(),
}

WORK_ORDER_TRANSITIONS = {
    WorkOrderStatus.DRAFT: frozenset({WorkOrderStatus.PLANNED, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.PLANNED: frozenset({WorkOrderStatus.APPROVAL_REQUIRED, WorkOrderStatus.APPROVED,
                                        WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.APPROVAL_REQUIRED: frozenset({WorkOrderStatus.APPROVED, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.APPROVED: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.IN_PROGRESS: frozenset({WorkOrderStatus.PAUSED, WorkOrderStatus.BLOCKED,
                                            WorkOrderStatus.REVIEW, WorkOrderStatus.FAILED,
                                            WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.PAUSED: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.BLOCKED: frozenset({WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.FAILED,
                                        WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.REVIEW: frozenset({WorkOrderStatus.COMPLETED, WorkOrderStatus.IN_PROGRESS,
                                       WorkOrderStatus.FAILED, WorkOrderStatus.CANCELLED}),
    WorkOrderStatus.COMPLETED: frozenset(),
    WorkOrderStatus.FAILED: frozenset(),
    WorkOrderStatus.CANCELLED: frozenset(),
}


class _StateMachine:
    def __init__(self, emit: Callable[[AuditEvent], None] | None = None,
                 clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.emit = emit or (lambda event: None)
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def _event(self, kind: str, entity: Any, source: str, target: str, actor_id: str) -> None:
        self.emit(AuditEvent(self.ids.new_id("event"), f"{kind}.transition", actor_id, entity.id,
                             self.clock.now(), getattr(entity, "work_order_id", None) or entity.id,
                             {"from": source, "to": target}))


class GoalStateMachine(_StateMachine):
    def transition(self, goal: Goal, target: GoalStatus, actor_id: str) -> Goal:
        if target == goal.status:
            return goal
        if target not in GOAL_TRANSITIONS[goal.status]:
            raise InvalidTransitionError(f"cannot transition goal from {goal.status.value} to {target.value}")
        changed = replace(goal, status=target, version=goal.version + 1)
        self._event("goal", goal, goal.status.value, target.value, actor_id)
        return changed


class WorkOrderStateMachine(_StateMachine):
    def transition(self, work_order: WorkOrder, target: WorkOrderStatus, actor_id: str,
                   **changes: Any) -> WorkOrder:
        if target == work_order.status and not changes:
            return work_order
        if target != work_order.status and target not in WORK_ORDER_TRANSITIONS[work_order.status]:
            raise InvalidTransitionError(
                f"cannot transition work order from {work_order.status.value} to {target.value}")
        changed = replace(work_order, status=target, version=work_order.version + 1, **changes)
        self._event("work_order", work_order, work_order.status.value, target.value, actor_id)
        return changed


class TaskStateMachine(_StateMachine):
    def transition(self, task: Task, target: TaskStatus, actor_id: str, **changes: Any) -> Task:
        if target == task.status and not changes:
            return task
        if target != task.status and target not in TASK_TRANSITIONS[task.status]:
            raise InvalidTransitionError(f"cannot transition task from {task.status.value} to {target.value}")
        changed = replace(task, status=target, version=task.version + 1, **changes)
        self._event("task", task, task.status.value, target.value, actor_id)
        return changed
