"""Deterministic synchronous DAG scheduler and dispatch boundary."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

from core.domain import (Budget, BudgetUsage, Clock, DomainValidationError, Task, TaskStatus,
                         UtcClock, WorkOrder, WorkOrderStatus)

from .graph import TaskGraph, TaskGraphValidator
from .states import TaskStateMachine, WorkOrderStateMachine


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.backoff_seconds < 0:
            raise DomainValidationError("retry policy values are invalid")

    def exhausted(self, attempt_count: int) -> bool:
        return attempt_count >= self.max_attempts

    def next_eligible(self, now: datetime, attempt_count: int) -> datetime:
        return now + timedelta(seconds=self.backoff_seconds * max(1, attempt_count))


class DispatchStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_INPUT = "needs_input"
    WAITING_APPROVAL = "waiting_approval"


@dataclass(frozen=True)
class DispatchResult:
    status: DispatchStatus
    summary: str
    artifact_ids: tuple[str, ...] = ()
    usage: BudgetUsage = BudgetUsage()


class TaskDispatcher:
    """Idempotent dispatch wrapper around a synchronous execution callable."""

    def __init__(self, execute: Callable[[Task, str], DispatchResult]) -> None:
        self.execute = execute
        self._results: dict[str, DispatchResult] = {}

    def dispatch(self, task: Task) -> DispatchResult:
        if not task.idempotency_key:
            raise DomainValidationError("dispatch requires an idempotency key")
        token = f"{task.idempotency_key}:attempt:{task.attempt_count}"
        if token not in self._results:
            self._results[token] = self.execute(task, token)
        return self._results[token]


@dataclass(frozen=True)
class SchedulingContext:
    now: datetime
    granted_permissions: frozenset[str]
    available_artifact_ids: frozenset[str]
    available_roles: frozenset[str]
    max_parallelism: int = 1
    resumable_task_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.now.tzinfo is None or self.max_parallelism < 1:
            raise DomainValidationError("scheduling context is invalid")


@dataclass(frozen=True)
class SchedulerTickResult:
    work_order: WorkOrder
    dispatched_task_ids: tuple[str, ...]
    ready_task_ids: tuple[str, ...]
    blocked_task_ids: tuple[str, ...]
    partial_failures: tuple[str, ...]


class WorkOrderCompletionEvaluator:
    """Derive completion/failure from persisted Task states."""

    def evaluate(self, tasks: tuple[Task, ...]) -> WorkOrderStatus | None:
        if tasks and all(task.status is TaskStatus.COMPLETED for task in tasks):
            return WorkOrderStatus.COMPLETED
        terminal_failures = {TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED}
        if any(task.status in terminal_failures for task in tasks):
            active = {TaskStatus.DRAFT, TaskStatus.BLOCKED, TaskStatus.READY, TaskStatus.IN_PROGRESS,
                      TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL, TaskStatus.REVIEW}
            if not any(task.status in active for task in tasks):
                return WorkOrderStatus.FAILED
        return None


class TaskScheduler:
    """Load state on every tick, validate the graph, dispatch and persist outcomes."""

    def __init__(self, work_orders, tasks, budgets, dispatcher: TaskDispatcher,
                 validator: TaskGraphValidator | None = None,
                 task_states: TaskStateMachine | None = None,
                 work_order_states: WorkOrderStateMachine | None = None,
                 completion: WorkOrderCompletionEvaluator | None = None) -> None:
        self.work_orders = work_orders
        self.tasks = tasks
        self.budgets = budgets
        self.dispatcher = dispatcher
        self.validator = validator or TaskGraphValidator()
        self.task_states = task_states or TaskStateMachine()
        self.work_order_states = work_order_states or WorkOrderStateMachine()
        self.completion = completion or WorkOrderCompletionEvaluator()

    def tick(self, work_order_id: str, context: SchedulingContext) -> SchedulerTickResult:
        work_order = self.work_orders.get(work_order_id)
        if work_order is None:
            raise DomainValidationError(f"unknown Work Order: {work_order_id}")
        tasks = tuple(task for task in self.tasks.list() if task.work_order_id == work_order_id)
        budget = self.budgets.get(work_order.budget_id) if work_order.budget_id else None
        if budget is None:
            raise DomainValidationError("Work Order budget is missing")
        graph = TaskGraph(work_order.id, tasks)
        self.validator.validate(work_order, graph, budget)
        if work_order.status is WorkOrderStatus.PAUSED:
            return SchedulerTickResult(work_order, (), (), (), ())
        if work_order.approval_required and not work_order.approval_granted:
            if work_order.status is WorkOrderStatus.PLANNED:
                changed = self.work_order_states.transition(
                    work_order, WorkOrderStatus.APPROVAL_REQUIRED, "scheduler")
                self.work_orders.save(changed, work_order.version)
                work_order = changed
            return SchedulerTickResult(work_order, (), (), (), ())
        if work_order.status in (WorkOrderStatus.PLANNED, WorkOrderStatus.APPROVED):
            changed = self.work_order_states.transition(
                work_order, WorkOrderStatus.IN_PROGRESS, "scheduler")
            self.work_orders.save(changed, work_order.version)
            work_order = changed
        if work_order.status is not WorkOrderStatus.IN_PROGRESS:
            return SchedulerTickResult(work_order, (), (), (), ())

        task_map = {task.id: task for task in tasks}
        ready: list[str] = []
        blocked: list[str] = []
        failures: list[str] = []
        for task in tasks:
            if (task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT,
                                    TaskStatus.CANCELLED)
                    and context.now >= task.created_at + timedelta(seconds=task.timeout_seconds)):
                task = self._save_transition(task, TaskStatus.TIMED_OUT, "scheduler")
                task_map[task.id] = task
                failures.append(task.id)
                continue
            if (task.status in (TaskStatus.FAILED, TaskStatus.TIMED_OUT)
                    and task.attempt_count >= task.retry_max_attempts):
                failures.append(task.id)
                continue
            if (task.status in (TaskStatus.WAITING_INPUT, TaskStatus.WAITING_APPROVAL)
                    and task.id not in context.resumable_task_ids):
                blocked.append(task.id)
                continue
            dependency_states = [task_map[edge.depends_on_task_id].status for edge in task.dependencies]
            if any(state in (TaskStatus.FAILED, TaskStatus.TIMED_OUT, TaskStatus.CANCELLED)
                   for state in dependency_states):
                task = self._mark_blocked(task, task_map)
                blocked.append(task.id)
                continue
            if not all(state is TaskStatus.COMPLETED for state in dependency_states):
                task = self._mark_blocked(task, task_map)
                blocked.append(task.id)
                continue
            if not set(task.required_artifact_ids) <= set(context.available_artifact_ids):
                task = self._mark_blocked(task, task_map)
                blocked.append(task.id)
                continue
            if not set(task.required_permissions) <= set(context.granted_permissions):
                if task.status in (TaskStatus.DRAFT, TaskStatus.BLOCKED, TaskStatus.READY):
                    task = self._save_transition(task, TaskStatus.WAITING_APPROVAL, "scheduler")
                    task_map[task.id] = task
                blocked.append(task.id)
                continue
            if task.assigned_role not in context.available_roles:
                task = self._mark_blocked(task, task_map)
                blocked.append(task.id)
                continue
            if task.next_eligible_at and context.now < task.next_eligible_at:
                task = self._mark_blocked(task, task_map)
                blocked.append(task.id)
                continue
            if task.status in (TaskStatus.DRAFT, TaskStatus.BLOCKED, TaskStatus.WAITING_INPUT,
                               TaskStatus.WAITING_APPROVAL, TaskStatus.FAILED, TaskStatus.TIMED_OUT):
                task = self._save_transition(task, TaskStatus.READY, "scheduler")
                task_map[task.id] = task
            if task.status is TaskStatus.READY:
                ready.append(task.id)

        dispatched: list[str] = []
        for task_id in ready[:context.max_parallelism]:
            task = task_map[task_id]
            if (budget.usage.tokens + task.allocated_tokens > budget.token_limit
                    or budget.usage.cost_units + task.allocated_cost_units > budget.cost_limit
                    or budget.usage.wall_seconds + task.allocated_wall_seconds > budget.wall_seconds_limit):
                task = self._mark_blocked(task, task_map)
                blocked.append(task.id)
                continue
            running = self._save_transition(task, TaskStatus.IN_PROGRESS, "scheduler",
                                            attempt_count=task.attempt_count + 1)
            result = self.dispatcher.dispatch(running)
            dispatched.append(task.id)
            budget = budget.consume(result.usage)
            old_budget_version = budget.version - 1
            self.budgets.save(budget, old_budget_version)
            final = self._apply_result(running, result, context.now)
            task_map[task.id] = final
            if final.status is TaskStatus.FAILED:
                failures.append(task.id)

        current_tasks = tuple(task_map[task.id] for task in tasks)
        completion = self.completion.evaluate(current_tasks)
        if completion is WorkOrderStatus.COMPLETED and not work_order.completion_event_emitted:
            reviewing = self.work_order_states.transition(work_order, WorkOrderStatus.REVIEW, "scheduler")
            completed = self.work_order_states.transition(
                reviewing, WorkOrderStatus.COMPLETED, "scheduler", completion_event_emitted=True)
            self.work_orders.save(completed, work_order.version)
            work_order = completed
        elif completion is WorkOrderStatus.FAILED and work_order.status is WorkOrderStatus.IN_PROGRESS:
            failed = self.work_order_states.transition(work_order, WorkOrderStatus.FAILED, "scheduler")
            self.work_orders.save(failed, work_order.version)
            work_order = failed
        return SchedulerTickResult(work_order, tuple(dispatched), tuple(ready),
                                   tuple(dict.fromkeys(blocked)), tuple(failures))

    def _save_transition(self, task: Task, target: TaskStatus, actor: str, **changes) -> Task:
        changed = self.task_states.transition(task, target, actor, **changes)
        self.tasks.save(changed, task.version)
        return changed

    def _mark_blocked(self, task: Task, task_map: dict[str, Task]) -> Task:
        if task.status in (TaskStatus.DRAFT, TaskStatus.READY):
            task = self._save_transition(task, TaskStatus.BLOCKED, "scheduler")
            task_map[task.id] = task
        return task

    def _apply_result(self, task: Task, result: DispatchResult, now: datetime) -> Task:
        if result.status is DispatchStatus.COMPLETED:
            return self._save_transition(task, TaskStatus.COMPLETED, "dispatcher")
        if result.status is DispatchStatus.NEEDS_INPUT:
            return self._save_transition(task, TaskStatus.WAITING_INPUT, "dispatcher")
        if result.status is DispatchStatus.WAITING_APPROVAL:
            return self._save_transition(task, TaskStatus.WAITING_APPROVAL, "dispatcher")
        policy = RetryPolicy(task.retry_max_attempts, task.retry_backoff_seconds)
        failed = self._save_transition(task, TaskStatus.FAILED, "dispatcher")
        if policy.exhausted(failed.attempt_count):
            return failed
        return self._save_transition(failed, TaskStatus.READY, "scheduler",
                                     next_eligible_at=policy.next_eligible(now, failed.attempt_count))
