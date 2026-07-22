"""Normalize untrusted planner proposals into validated domain objects."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.domain import (AcceptanceCriterion, Budget, Clock, DomainValidationError, IdGenerator,
                         Priority, RiskLevel, Task, TaskDependency, TaskStatus, UtcClock,
                         UuidIdGenerator, WorkOrder, WorkOrderStatus)

from .graph import TaskGraph, TaskGraphValidator
from .states import WorkOrderStateMachine


@dataclass(frozen=True)
class WorkOrderPlan:
    work_order: WorkOrder
    graph: TaskGraph
    questions: tuple[str, ...]
    assumptions: tuple[str, ...]
    risks: tuple[str, ...]


class WorkOrderPlanner:
    """Convert structured planner output into a validated Work Order and DAG."""

    REQUIRED_KEYS = frozenset({"work_order", "tasks", "dependencies", "questions", "assumptions", "risks"})

    def __init__(self, validator: TaskGraphValidator | None = None, clock: Clock | None = None,
                 ids: IdGenerator | None = None, states: WorkOrderStateMachine | None = None) -> None:
        self.validator = validator or TaskGraphValidator()
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.states = states or WorkOrderStateMachine(clock=self.clock, ids=self.ids)

    def plan(self, goal_id: str, proposal: dict[str, Any], budget: Budget,
             constitution_version: str) -> WorkOrderPlan:
        if not isinstance(proposal, dict) or set(proposal) != self.REQUIRED_KEYS:
            raise DomainValidationError("planner output must match the required top-level schema")
        work = proposal["work_order"]
        tasks_data = proposal["tasks"]
        dependencies_data = proposal["dependencies"]
        if not isinstance(work, dict) or not isinstance(tasks_data, list) or not tasks_data:
            raise DomainValidationError("planner Work Order and tasks are invalid")
        if not all(isinstance(item, list) for item in
                   (proposal["questions"], proposal["assumptions"], proposal["risks"], dependencies_data)):
            raise DomainValidationError("planner list fields are invalid")
        work_order_id = str(work.get("id") or self.ids.new_id("wo"))
        task_ids: list[str] = []
        normalized: list[dict[str, Any]] = []
        for item in tasks_data:
            if not isinstance(item, dict):
                raise DomainValidationError("each proposed task must be an object")
            task_id = str(item.get("id") or self.ids.new_id("task"))
            task_ids.append(task_id)
            normalized.append({**item, "id": task_id})
        dependency_map: dict[str, list[TaskDependency]] = {task_id: [] for task_id in task_ids}
        for item in dependencies_data:
            if not isinstance(item, dict):
                raise DomainValidationError("each dependency must be an object")
            task_id = str(item.get("task_id", ""))
            dependency_map.setdefault(task_id, []).append(
                TaskDependency(task_id, str(item.get("depends_on_task_id", ""))))
        now = self.clock.now()
        tasks = tuple(self._task(work_order_id, item, dependency_map.get(item["id"], []), now)
                      for item in normalized)
        criteria = tuple(AcceptanceCriterion(
            str(item.get("id") or self.ids.new_id("criterion")), str(item["description"]),
            bool(item.get("required", True))) for item in work.get("acceptance_criteria", ()))
        approval_required = bool(work.get("approval_required", False))
        deadline = work.get("deadline")
        if isinstance(deadline, str):
            deadline = datetime.fromisoformat(deadline)
        work_order = WorkOrder(
            work_order_id, goal_id, str(work.get("title") or work.get("objective") or "Work Order"),
            str(work["accountable_owner_id"]), constitution_version, WorkOrderStatus.DRAFT, now,
            criteria, tuple(task_ids), 1, str(work["organization_id"]), str(work["objective"]),
            str(work["requested_by"]), tuple(work.get("deliverables", ())),
            tuple(work.get("constraints", ())), RiskLevel(str(work.get("risk_level", "low"))),
            budget.id, deadline, approval_required, False, (), False,
        )
        work_order = self.states.transition(work_order, WorkOrderStatus.PLANNED,
                                            work_order.accountable_owner_id)
        graph = TaskGraph(work_order.id, tasks)
        self.validator.validate(work_order, graph, budget)
        return WorkOrderPlan(work_order, graph, tuple(proposal["questions"]),
                             tuple(proposal["assumptions"]), tuple(proposal["risks"]))

    def _task(self, work_order_id: str, item: dict[str, Any], dependencies: list[TaskDependency],
              now: datetime) -> Task:
        criteria = tuple(AcceptanceCriterion(
            str(value.get("id") or self.ids.new_id("criterion")), str(value["description"]),
            bool(value.get("required", True))) for value in item.get("acceptance_criteria", ()))
        return Task(
            str(item["id"]), work_order_id, str(item["title"]),
            str(item.get("owner_id") or item.get("assigned_role") or ""), TaskStatus.DRAFT,
            Priority(str(item.get("priority", "normal"))), RiskLevel(str(item.get("risk_level", "low"))),
            now, tuple(dependencies), version=1, objective=str(item.get("objective", "")),
            assigned_role=str(item.get("assigned_role", "")),
            worker_specialization=item.get("worker_specialization"), inputs=dict(item.get("inputs", {})),
            expected_output_schema=dict(item.get("expected_output_schema", {})),
            acceptance_criteria=criteria, retry_max_attempts=int(item.get("retry_max_attempts", 1)),
            retry_backoff_seconds=float(item.get("retry_backoff_seconds", 0)),
            timeout_seconds=float(item.get("timeout_seconds", 300)),
            required_permissions=tuple(item.get("required_permissions", ())),
            required_artifact_ids=tuple(item.get("required_artifact_ids", ())),
            allocated_tokens=int(item.get("allocated_tokens", 0)),
            allocated_cost_units=float(item.get("allocated_cost_units", 0)),
            allocated_wall_seconds=float(item.get("allocated_wall_seconds", 0)),
            review_policy=str(item.get("review_policy", "none")),
            idempotency_key=str(item.get("idempotency_key", "")),
        )
