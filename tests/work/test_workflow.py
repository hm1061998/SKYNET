from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.domain import (
    Budget,
    BudgetUsage,
    GoalStatus,
    Priority,
    RiskLevel,
    SequenceIdGenerator,
    Task,
    TaskDependency,
    TaskStatus,
    WorkOrder,
    WorkOrderStatus,
)
from core.persistence import SQLiteStore
from core.repositories import InMemoryRepositories
from core.work import (
    CancellationService,
    DispatchResult,
    DispatchStatus,
    GoalIntakeService,
    LegacyPipelineAdapter,
    SchedulingContext,
    TaskDispatcher,
    TaskGraph,
    TaskGraphError,
    TaskGraphValidator,
    TaskScheduler,
    WorkOrderControlService,
    WorkOrderPlanner,
    WorkOrderStateMachine,
)

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class FixedClock:
    def __init__(self, now=NOW):
        self.value = now

    def now(self):
        return self.value


def make_task(task_id, *, dependencies=(), status=TaskStatus.DRAFT, role="developer",
              key=None, retries=1, permissions=(), artifacts=(), tokens=10, timeout=300):
    return Task(
        task_id, "wo", task_id, "owner", status, Priority.NORMAL, RiskLevel.LOW, NOW,
        tuple(TaskDependency(task_id, dep) for dep in dependencies),
        objective=f"Do {task_id}", assigned_role=role, retry_max_attempts=retries,
        required_permissions=tuple(permissions), required_artifact_ids=tuple(artifacts),
        allocated_tokens=tokens, timeout_seconds=timeout, idempotency_key=key or f"key:{task_id}",
    )


def make_work_order(task_ids, *, status=WorkOrderStatus.PLANNED, approval_required=False,
                    approval_granted=False):
    return WorkOrder(
        "wo", "goal", "Build", "owner", "v1", status, NOW, task_ids=tuple(task_ids),
        organization_id="org", objective="Build", requested_by="requester",
        deliverables=("code",), constraints=("offline",), risk_level=RiskLevel.LOW,
        budget_id="budget", deadline=NOW + timedelta(days=1),
        approval_required=approval_required, approval_granted=approval_granted,
    )


def make_budget(tokens=100):
    return Budget("budget", "wo", tokens, 100.0, 1000.0)


def setup_memory(work_order, tasks, budget=None):
    repositories = InMemoryRepositories()
    repositories.work_orders.add(work_order)
    for task in tasks:
        repositories.tasks.add(task)
    repositories.budgets.add(budget or make_budget())
    return repositories


def context(**changes):
    values = dict(
        now=NOW, granted_permissions=frozenset(), available_artifact_ids=frozenset(),
        available_roles=frozenset({"developer", "reviewer"}), max_parallelism=3,
        resumable_task_ids=frozenset(),
    )
    values.update(changes)
    return SchedulingContext(**values)


class IntakePlannerGraphTests(unittest.TestCase):
    def test_goal_intake_clarification_and_ready(self):
        service = GoalIntakeService(FixedClock(), SequenceIdGenerator())
        unclear = service.intake("", "requester")
        self.assertEqual(GoalStatus.CLARIFICATION, unclear.goal.status)
        self.assertEqual(2, len(unclear.questions))
        ready = service.intake("Build feature", "requester", ("Tests pass",))
        self.assertEqual(GoalStatus.READY, ready.goal.status)
        self.assertEqual((), ready.questions)

    def test_planner_normalizes_and_validates_schema(self):
        proposal = {
            "work_order": {
                "organization_id": "org", "objective": "Build", "accountable_owner_id": "owner",
                "requested_by": "requester", "deliverables": ["code"], "constraints": ["offline"],
                "risk_level": "low", "approval_required": False,
                "acceptance_criteria": [{"description": "Tests pass"}],
            },
            "tasks": [
                {"id": "a", "title": "A", "assigned_role": "developer",
                 "idempotency_key": "a", "allocated_tokens": 10},
                {"id": "b", "title": "B", "assigned_role": "reviewer",
                 "idempotency_key": "b", "allocated_tokens": 10},
            ],
            "dependencies": [{"task_id": "b", "depends_on_task_id": "a"}],
            "questions": [], "assumptions": ["repo exists"], "risks": [],
        }
        plan = WorkOrderPlanner(clock=FixedClock(), ids=SequenceIdGenerator()).plan(
            "goal", proposal, make_budget(), "v1")
        self.assertEqual(WorkOrderStatus.PLANNED, plan.work_order.status)
        self.assertEqual(("a",), plan.graph.dependencies_of("b"))

    def test_valid_graph_and_cycle_diagnostic(self):
        tasks = (make_task("a"), make_task("b", dependencies=("a",)))
        TaskGraphValidator().validate(make_work_order(("a", "b")), TaskGraph("wo", tasks), make_budget())
        cycle = (make_task("a", dependencies=("b",)), make_task("b", dependencies=("a",)))
        with self.assertRaisesRegex(TaskGraphError, r"a -> b -> a|b -> a -> b"):
            TaskGraphValidator().validate(make_work_order(("a", "b")), TaskGraph("wo", cycle), make_budget())

    def test_graph_rejects_missing_role_dependency_idempotency_approval_and_budget(self):
        validator = TaskGraphValidator()
        cases = (
            (make_task("a", role=""), "accountable role"),
            (make_task("a", dependencies=("missing",)), "missing dependency"),
            (replace(make_task("a"), idempotency_key=""), "idempotency"),
            (make_task("a", permissions=("approval:a",)), "impossible approval"),
            (make_task("a", permissions=("external_action",)), "external action"),
            (make_task("a", tokens=101), "budget"),
        )
        for task, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(TaskGraphError, message):
                validator.validate(make_work_order(("a",)), TaskGraph("wo", (task,)), make_budget())


class SchedulerTests(unittest.TestCase):
    def scheduler(self, repositories, execute):
        return TaskScheduler(repositories.work_orders, repositories.tasks, repositories.budgets,
                             TaskDispatcher(execute))

    def test_parallel_then_sequential_execution_and_idempotent_tick(self):
        tasks = (make_task("a"), make_task("b"), make_task("c", dependencies=("a", "b")))
        repositories = setup_memory(make_work_order(("a", "b", "c")), tasks)
        calls = []

        def execute(task, token):
            calls.append((task.id, token))
            return DispatchResult(DispatchStatus.COMPLETED, "done", usage=BudgetUsage(tokens=1))

        events = []
        scheduler = TaskScheduler(
            repositories.work_orders, repositories.tasks, repositories.budgets,
            TaskDispatcher(execute),
            work_order_states=WorkOrderStateMachine(events.append, FixedClock(), SequenceIdGenerator()))
        first = scheduler.tick("wo", context(max_parallelism=2))
        self.assertEqual(("a", "b"), first.dispatched_task_ids)
        second = scheduler.tick("wo", context(max_parallelism=2))
        self.assertEqual(("c",), second.dispatched_task_ids)
        self.assertEqual(WorkOrderStatus.COMPLETED, second.work_order.status)
        replay = scheduler.tick("wo", context(max_parallelism=2))
        self.assertEqual((), replay.dispatched_task_ids)
        self.assertEqual(3, len(calls))
        completed_events = [event for event in events
                            if event.details.get("to") == WorkOrderStatus.COMPLETED.value]
        self.assertEqual(1, len(completed_events))

    def test_dependency_failure_blocks_dependent_and_reports_partial_failure(self):
        tasks = (make_task("a"), make_task("b", dependencies=("a",)))
        repositories = setup_memory(make_work_order(("a", "b")), tasks)
        scheduler = self.scheduler(repositories, lambda task, token:
                                   DispatchResult(DispatchStatus.FAILED, "boom"))
        first = scheduler.tick("wo", context(max_parallelism=1))
        self.assertEqual(("a",), first.partial_failures)
        second = scheduler.tick("wo", context(max_parallelism=1))
        self.assertIn("b", second.blocked_task_ids)
        self.assertEqual(TaskStatus.BLOCKED, repositories.tasks.get("b").status)
        self.assertEqual(1, repositories.tasks.get("a").attempt_count)

    def test_pause_resume_and_cancellation_propagation(self):
        tasks = (make_task("a", status=TaskStatus.READY), make_task("b", status=TaskStatus.BLOCKED))
        repositories = setup_memory(make_work_order(("a", "b"), status=WorkOrderStatus.IN_PROGRESS), tasks)
        controls = WorkOrderControlService(repositories.work_orders)
        controls.pause("wo", "human")
        scheduler = self.scheduler(repositories, lambda task, token:
                                   DispatchResult(DispatchStatus.COMPLETED, "done"))
        self.assertEqual((), scheduler.tick("wo", context()).dispatched_task_ids)
        controls.resume("wo", "human")
        self.assertEqual(("a",), scheduler.tick("wo", context(max_parallelism=1)).dispatched_task_ids)
        CancellationService(repositories.work_orders, repositories.tasks).cancel("wo", "human")
        self.assertEqual(WorkOrderStatus.CANCELLED, repositories.work_orders.get("wo").status)
        self.assertEqual(TaskStatus.CANCELLED, repositories.tasks.get("b").status)

    def test_retry_exhaustion_and_attempt_tokens(self):
        task = make_task("a", retries=2)
        repositories = setup_memory(make_work_order(("a",)), (task,))
        tokens = []

        def fail(task, token):
            tokens.append(token)
            return DispatchResult(DispatchStatus.FAILED, "boom")

        scheduler = self.scheduler(repositories, fail)
        scheduler.tick("wo", context(max_parallelism=1))
        self.assertEqual(TaskStatus.READY, repositories.tasks.get("a").status)
        scheduler.tick("wo", context(max_parallelism=1))
        self.assertEqual(TaskStatus.FAILED, repositories.tasks.get("a").status)
        self.assertEqual(["key:a:attempt:1", "key:a:attempt:2"], tokens)

    def test_waiting_for_input_and_permission_approval(self):
        input_task = make_task("a")
        approval_task = make_task("b", permissions=("deploy",))
        repositories = setup_memory(make_work_order(("a", "b")), (input_task, approval_task))

        def execute(task, token):
            return (DispatchResult(DispatchStatus.NEEDS_INPUT, "question") if task.id == "a"
                    else DispatchResult(DispatchStatus.COMPLETED, "done"))

        scheduler = self.scheduler(repositories, execute)
        scheduler.tick("wo", context(max_parallelism=2))
        self.assertEqual(TaskStatus.WAITING_INPUT, repositories.tasks.get("a").status)
        self.assertEqual(TaskStatus.WAITING_APPROVAL, repositories.tasks.get("b").status)
        no_resume = scheduler.tick("wo", context(granted_permissions=frozenset({"deploy"})))
        self.assertEqual((), no_resume.dispatched_task_ids)
        resumed = scheduler.tick("wo", context(granted_permissions=frozenset({"deploy"}),
                                                 resumable_task_ids=frozenset({"a", "b"})))
        self.assertIn("b", resumed.dispatched_task_ids)

    def test_work_order_waits_for_plan_approval(self):
        repositories = setup_memory(make_work_order(("a",), approval_required=True), (make_task("a"),))
        scheduler = self.scheduler(repositories, lambda task, token:
                                   DispatchResult(DispatchStatus.COMPLETED, "done"))
        waiting = scheduler.tick("wo", context())
        self.assertEqual(WorkOrderStatus.APPROVAL_REQUIRED, waiting.work_order.status)
        WorkOrderControlService(repositories.work_orders).approve("wo", "human")
        self.assertEqual(("a",), scheduler.tick("wo", context()).dispatched_task_ids)

    def test_budget_exhaustion_blocks_dispatch(self):
        task = make_task("a", tokens=10)
        budget = replace(make_budget(10), usage=BudgetUsage(tokens=5))
        repositories = setup_memory(make_work_order(("a",)), (task,), budget)
        scheduler = self.scheduler(repositories, lambda task, token:
                                   DispatchResult(DispatchStatus.COMPLETED, "done"))
        result = scheduler.tick("wo", context())
        self.assertEqual((), result.dispatched_task_ids)
        self.assertIn("a", result.blocked_task_ids)
        self.assertEqual(TaskStatus.BLOCKED, repositories.tasks.get("a").status)

    def test_restart_safe_sqlite_scheduler(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.db"
            calls = []

            def execute(task, token):
                calls.append(task.id)
                return DispatchResult(DispatchStatus.COMPLETED, "done")

            with SQLiteStore(path) as store:
                work_orders = store.repository("work_orders", WorkOrder)
                tasks_repo = store.repository("tasks", Task)
                budgets = store.repository("budgets", Budget)
                work_orders.add(make_work_order(("a", "b")))
                tasks_repo.add(make_task("a"))
                tasks_repo.add(make_task("b", dependencies=("a",)))
                budgets.add(make_budget())
                TaskScheduler(work_orders, tasks_repo, budgets, TaskDispatcher(execute)).tick(
                    "wo", context(max_parallelism=1))
            with SQLiteStore(path) as store:
                scheduler = TaskScheduler(
                    store.repository("work_orders", WorkOrder), store.repository("tasks", Task),
                    store.repository("budgets", Budget), TaskDispatcher(execute))
                result = scheduler.tick("wo", context(max_parallelism=1))
                self.assertEqual(("b",), result.dispatched_task_ids)
            self.assertEqual(["a", "b"], calls)


class LegacyAdapterTests(unittest.TestCase):
    def test_legacy_pipeline_maps_to_linear_dag(self):
        graph = LegacyPipelineAdapter(FixedClock(), SequenceIdGenerator()).to_graph(
            "wo", ["one", "two", "three"])
        self.assertEqual(3, len(graph.tasks))
        self.assertEqual((), graph.dependencies_of(graph.tasks[0].id))
        self.assertEqual((graph.tasks[0].id,), graph.dependencies_of(graph.tasks[1].id))
        self.assertEqual((graph.tasks[1].id,), graph.dependencies_of(graph.tasks[2].id))


if __name__ == "__main__":
    unittest.main()
