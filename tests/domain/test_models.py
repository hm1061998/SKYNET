from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from core.domain import (
    AcceptanceCriterion,
    AgentDefinition,
    AgentInstance,
    AgentKind,
    AgentStatus,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    Artifact,
    ArtifactType,
    ArtifactVersion,
    Budget,
    BudgetUsage,
    Capability,
    Department,
    DomainValidationError,
    Goal,
    GoalStatus,
    InvalidTransitionError,
    ModelProfile,
    Organization,
    OrganizationConstitution,
    PermissionRequest,
    Priority,
    RiskLevel,
    RoleDefinition,
    SequenceIdGenerator,
    TASK_TRANSITIONS,
    Task,
    TaskDependency,
    TaskStatus,
    ToolGrant,
    WorkOrder,
    WorkOrderStatus,
)

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class DomainModelTests(unittest.TestCase):
    def test_deterministic_id_generator(self) -> None:
        ids = SequenceIdGenerator()
        self.assertEqual("task_000001", ids.new_id("task"))
        self.assertEqual("task_000002", ids.new_id("task"))

    def test_serialization_round_trips_are_json_compatible(self) -> None:
        constitution = OrganizationConstitution("v1", ("safe",), NOW)
        role = RoleDefinition("role_1", "Developer", ("build",), (Capability("code"),))
        organization = Organization("org_1", "Company", constitution,
                                    (Department("dept_1", "Engineering", (role.id,)),), (role,))
        profile = ModelProfile("mock", "mock-1", "work", 100)
        agent = AgentDefinition("agent_1", "Developer", AgentKind.ROLE, role.id,
                                (Capability("code"),), (ToolGrant("python", ("read",), NOW + timedelta(hours=1)),), profile)
        instance = AgentInstance("inst_1", agent.id, AgentStatus.ACTIVE, NOW, "wo_1")
        criterion = AcceptanceCriterion("criterion_1", "Tests pass")
        goal = Goal("goal_1", "Build", "Build feature", "owner_1", GoalStatus.ACTIVE, NOW, (criterion,))
        work_order = WorkOrder("wo_1", goal.id, "Build", "owner_1", "v1",
                               WorkOrderStatus.PLANNED, NOW, (criterion,), ("task_1",))
        task = Task("task_1", work_order.id, "Implement", "owner_1", TaskStatus.BLOCKED,
                    Priority.HIGH, RiskLevel.MEDIUM, NOW,
                    (TaskDependency("task_1", "task_0"),), "reviewer_1", "author_1")
        artifact_version = ArtifactVersion("av_1", "artifact_1", 1, "sha256:a", "local://a", NOW)
        artifact = Artifact("artifact_1", "code.py", ArtifactType.SOURCE_CODE, "agent_1", task.id,
                            "sha256:a", NOW, (artifact_version,))
        permission = PermissionRequest("perm_1", "agent_1", "write", "repo", ("src",), NOW)
        decision = ApprovalDecision(ApprovalStatus.APPROVED, "human_1", NOW, "approved")
        approval = ApprovalRequest("approval_1", permission, NOW, NOW + timedelta(hours=1), decision)
        budget = Budget("budget_1", work_order.id, 100, 10.0, 60.0, BudgetUsage(10, 1.0, 2.0))

        pairs = (
            (organization, Organization), (agent, AgentDefinition), (instance, AgentInstance),
            (goal, Goal), (work_order, WorkOrder), (task, Task), (artifact, Artifact),
            (approval, ApprovalRequest), (budget, Budget),
        )
        for original, model_type in pairs:
            with self.subTest(model=model_type.__name__):
                payload = original.to_dict()
                json.dumps(payload)
                self.assertEqual(original, model_type.from_dict(payload))

    def test_invalid_construction(self) -> None:
        with self.assertRaises(DomainValidationError):
            OrganizationConstitution("", ("safe",), NOW)
        with self.assertRaises(DomainValidationError):
            Goal("", "Build", "", "owner", GoalStatus.DRAFT, NOW)
        with self.assertRaises(DomainValidationError):
            Goal("goal", "Build", "", "owner", GoalStatus.DRAFT, datetime.now())
        with self.assertRaises(DomainValidationError):
            WorkOrder("wo", "goal", "Build", "", "v1", WorkOrderStatus.DRAFT, NOW)
        with self.assertRaises(DomainValidationError):
            Task("task", "wo", "Task", "owner", "ready", Priority.NORMAL, RiskLevel.LOW, NOW)

    def test_self_and_duplicate_dependencies_are_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            TaskDependency("task_1", "task_1")
        dep = TaskDependency("task_1", "task_0")
        with self.assertRaises(DomainValidationError):
            Task("task_1", "wo", "Task", "owner", TaskStatus.BLOCKED, Priority.NORMAL,
                 RiskLevel.LOW, NOW, (dep, dep))

    def test_every_task_transition(self) -> None:
        for source in TaskStatus:
            base = Task("task", "wo", "Task", "owner", source, Priority.NORMAL, RiskLevel.LOW, NOW)
            for target in TaskStatus:
                with self.subTest(source=source, target=target):
                    if target == source:
                        self.assertIs(base, base.transition(target))
                    elif target in TASK_TRANSITIONS[source]:
                        transitioned = base.transition(target)
                        self.assertEqual(target, transitioned.status)
                        self.assertEqual(2, transitioned.version)
                    else:
                        with self.assertRaises(InvalidTransitionError):
                            base.transition(target)

    def test_completed_task_requires_explicit_reopen(self) -> None:
        task = Task("task", "wo", "Task", "owner", TaskStatus.COMPLETED,
                    Priority.NORMAL, RiskLevel.LOW, NOW)
        with self.assertRaises(InvalidTransitionError):
            task.transition(TaskStatus.IN_PROGRESS)
        self.assertEqual(TaskStatus.IN_PROGRESS,
                         task.transition(TaskStatus.IN_PROGRESS, reopen=True).status)

    def test_separation_of_duties(self) -> None:
        bad = Task("task", "wo", "Review", "owner", TaskStatus.REVIEW, Priority.NORMAL,
                   RiskLevel.HIGH, NOW, reviewer_id="same", author_id="same")
        with self.assertRaises(DomainValidationError):
            bad.require_separate_reviewer()
        good = replace(bad, reviewer_id="reviewer")
        good.require_separate_reviewer()

    def test_budget_usage_and_negative_values(self) -> None:
        with self.assertRaises(DomainValidationError):
            BudgetUsage(tokens=-1)
        with self.assertRaises(DomainValidationError):
            Budget("budget", "wo", -1, 1, 1)
        budget = Budget("budget", "wo", 10, 2.0, 3.0)
        consumed = budget.consume(BudgetUsage(5, 1.0, 1.0))
        self.assertEqual(5, consumed.usage.tokens)
        with self.assertRaises(DomainValidationError):
            consumed.consume(BudgetUsage(6, 0, 0))

    def test_approval_decision_requires_actor_and_timestamp(self) -> None:
        with self.assertRaises(DomainValidationError):
            ApprovalDecision(ApprovalStatus.APPROVED, "", NOW)
        with self.assertRaises(DomainValidationError):
            ApprovalDecision(ApprovalStatus.APPROVED, "human", datetime.now())
        with self.assertRaises(DomainValidationError):
            ApprovalDecision(ApprovalStatus.PENDING, "human", NOW)

    def test_artifact_provenance_is_required(self) -> None:
        with self.assertRaises(DomainValidationError):
            Artifact("artifact", "file", ArtifactType.OTHER, "", "task", "hash", NOW)
        with self.assertRaises(DomainValidationError):
            Artifact("artifact", "file", ArtifactType.OTHER, "producer", "", "hash", NOW)
        with self.assertRaises(DomainValidationError):
            Artifact("artifact", "file", ArtifactType.OTHER, "producer", "task", "", NOW)


if __name__ == "__main__":
    unittest.main()
