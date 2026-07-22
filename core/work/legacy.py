"""Compatibility mapping from legacy sequential steps to a linear Task DAG."""
from __future__ import annotations

from core.domain import (Clock, IdGenerator, Priority, RiskLevel, Task, TaskDependency,
                         TaskStatus, UtcClock, UuidIdGenerator)

from .graph import TaskGraph


class LegacyPipelineAdapter:
    """Map `_decompose` output to a linear graph without changing legacy execution."""

    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def to_graph(self, work_order_id: str, steps: list[str], assigned_role: str = "legacy_role") -> TaskGraph:
        now = self.clock.now()
        tasks = []
        previous_id = None
        for index, step in enumerate(steps, 1):
            task_id = self.ids.new_id("task")
            dependencies = (() if previous_id is None
                            else (TaskDependency(task_id, previous_id),))
            tasks.append(Task(
                task_id, work_order_id, str(step), assigned_role, TaskStatus.DRAFT,
                Priority.NORMAL, RiskLevel.MEDIUM, now, dependencies,
                objective=str(step), assigned_role=assigned_role,
                idempotency_key=f"legacy:{work_order_id}:{index}",
            ))
            previous_id = task_id
        return TaskGraph(work_order_id, tuple(tasks))
