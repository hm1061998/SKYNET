"""Task DAG representation and deterministic validation."""
from __future__ import annotations

from dataclasses import dataclass

from core.domain import Budget, DomainValidationError, Task, TaskStatus, WorkOrder


class TaskGraphError(DomainValidationError):
    """Raised when a proposed Task graph violates execution invariants."""


@dataclass(frozen=True)
class TaskGraph:
    work_order_id: str
    tasks: tuple[Task, ...]

    def by_id(self) -> dict[str, Task]:
        return {task.id: task for task in self.tasks}

    def dependencies_of(self, task_id: str) -> tuple[str, ...]:
        task = self.by_id()[task_id]
        return tuple(edge.depends_on_task_id for edge in task.dependencies)

    def dependents_of(self, task_id: str) -> tuple[str, ...]:
        return tuple(task.id for task in self.tasks
                     if any(edge.depends_on_task_id == task_id for edge in task.dependencies))


class TaskGraphValidator:
    """Reject invalid graphs before they can enter scheduling."""

    def validate(self, work_order: WorkOrder, graph: TaskGraph, budget: Budget) -> None:
        if graph.work_order_id != work_order.id:
            raise TaskGraphError("task graph belongs to a different Work Order")
        task_map = graph.by_id()
        if len(task_map) != len(graph.tasks) or not task_map:
            raise TaskGraphError("task IDs must be unique and graph cannot be empty")
        if set(work_order.task_ids) != set(task_map):
            raise TaskGraphError("Work Order task IDs do not match the task graph")
        idempotency = [task.idempotency_key for task in graph.tasks]
        if any(not key for key in idempotency) or len(idempotency) != len(set(idempotency)):
            raise TaskGraphError("task idempotency keys must be non-empty and unique")
        for task in graph.tasks:
            if task.work_order_id != work_order.id:
                raise TaskGraphError(f"task {task.id} belongs to a different Work Order")
            if not task.assigned_role:
                raise TaskGraphError(f"task {task.id} has no accountable role")
            if "external_action" in task.required_permissions and not work_order.approval_required:
                raise TaskGraphError(
                    f"task {task.id} performs an external action but Work Order approval is not required")
            for dependency in task.dependencies:
                if dependency.depends_on_task_id not in task_map:
                    raise TaskGraphError(
                        f"task {task.id} has missing dependency {dependency.depends_on_task_id}")
            for permission in task.required_permissions:
                if permission.startswith("approval:"):
                    approver_task = permission.split(":", 1)[1]
                    if not approver_task or approver_task == task.id or approver_task not in task_map:
                        raise TaskGraphError(f"task {task.id} has impossible approval dependency {permission}")
        self._reject_cycles(graph)
        if sum(task.allocated_tokens for task in graph.tasks) > budget.token_limit:
            raise TaskGraphError("task token allocation exceeds Work Order budget")
        if sum(task.allocated_cost_units for task in graph.tasks) > budget.cost_limit:
            raise TaskGraphError("task cost allocation exceeds Work Order budget")
        if sum(task.allocated_wall_seconds for task in graph.tasks) > budget.wall_seconds_limit:
            raise TaskGraphError("task time allocation exceeds Work Order budget")

    def _reject_cycles(self, graph: TaskGraph) -> None:
        task_map = graph.by_id()
        visiting: list[str] = []
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                start = visiting.index(task_id)
                cycle = visiting[start:] + [task_id]
                raise TaskGraphError("task cycle detected: " + " -> ".join(cycle))
            if task_id in visited:
                return
            visiting.append(task_id)
            for edge in task_map[task_id].dependencies:
                visit(edge.depends_on_task_id)
            visiting.pop()
            visited.add(task_id)

        for task_id in task_map:
            visit(task_id)
