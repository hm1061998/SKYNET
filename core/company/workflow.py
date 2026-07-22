"""Deterministic offline feature-to-release workflow template."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any

from core.domain import Clock, IdGenerator, UtcClock, UuidIdGenerator
from core.knowledge import InMemoryArtifactStore, Sensitivity


class StageStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CHANGES_REQUESTED = "changes_requested"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class WorkflowStage:
    id: str
    owner_role: str
    dependencies: tuple[str, ...]
    max_revision_rounds: int


STAGES = (
    WorkflowStage("intake", "chief_of_staff", (), 0),
    WorkflowStage("product_specification", "product_manager", ("intake",), 2),
    WorkflowStage("technical_design", "solution_architect", ("product_specification",), 2),
    WorkflowStage("implementation", "developer", ("technical_design",), 3),
    WorkflowStage("code_review", "code_reviewer", ("implementation",), 3),
    WorkflowStage("qa", "qa_engineer", ("code_review",), 3),
    WorkflowStage("security_release_review", "security_release_officer", ("code_review",), 0),
    WorkflowStage("final_approval_delivery", "chief_of_staff", ("qa", "security_release_review"), 0),
)


@dataclass(frozen=True)
class FeatureDeliveryResult:
    status: str
    stage_statuses: dict[str, str]
    artifact_versions: dict[str, str]
    review_rounds: int
    human_approved: bool
    cost_summary: dict[str, float | int]
    trace: tuple[str, ...]
    final_report: str


class MockFeatureDeliveryWorkflow:
    """Run the required health-check scenario without external services or host changes."""

    workflow_id = "software_feature_delivery_v1"

    def __init__(self, artifacts: InMemoryArtifactStore | None = None,
                 clock: Clock | None = None, ids: IdGenerator | None = None,
                 event_sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.artifacts = artifacts or InMemoryArtifactStore(self.clock, self.ids)
        self.event_sink = event_sink or (lambda event: None)

    def run_health_check(self, *, human_approved: bool = True) -> FeatureDeliveryResult:
        statuses: dict[str, str] = {}
        versions: dict[str, str] = {}
        trace = []
        tokens = 0
        tool_calls = 0

        def complete(stage: str) -> None:
            statuses[stage] = StageStatus.COMPLETED.value
            trace.append(f"{stage}:completed")
            self.event_sink({"type": "task.transition", "stage": stage, "status": "completed",
                             "summary": f"{stage.replace('_', ' ')} completed"})

        def artifact(path: str, producer: str, content: str, artifact_type: str,
                     artifact_id: str | None = None) -> str:
            nonlocal tokens, tool_calls
            record = self.artifacts.put(artifact_id=artifact_id or self.ids.new_id("ART"),
                data=content.encode("utf-8"), display_name=path, producer_agent_id=producer,
                source_task_id=f"task-{producer}", mime_type="text/markdown",
                artifact_type=artifact_type, provenance=(f"workflow:{self.workflow_id}",),
                sensitivity=Sensitivity.INTERNAL, metadata={"path": path})
            versions[path] = record.id
            tokens += len(content.split())
            tool_calls += 1
            self.event_sink({"type": "artifact.versioned" if record.version_number > 1 else "artifact.created",
                             "artifact_version_id": record.id, "content_hash": record.content_hash,
                             "summary": f"Artifact created: {path}"})
            return record.content_hash

        complete("intake")
        artifact("product/feature-specification.md", "product_manager",
                 "Problem: no health command. User: operator. Scope: offline health check. "
                 "Story: verify service readiness. Acceptance: exit 0 and print healthy. "
                 "NFR: deterministic. Out of scope: network. Assumptions: sample fixture. Open questions: none.",
                 "requirements")
        complete("product_specification")
        artifact("architecture/technical-design.md", "solution_architect",
                 "Add an isolated CLI command with no dependency; include tests and rollback by removing command.",
                 "architecture_document")
        artifact("architecture/ADR-001-health-command.md", "solution_architect",
                 "Decision: standard-library health command; compatibility preserved.", "architecture_document")
        complete("technical_design")
        patch_artifact_id = self.ids.new_id("ART")
        first_hash = artifact("implementation/health-check.patch", "developer",
                              "revision 1: command prints status but lacks exit-code test", "source_patch",
                              patch_artifact_id)
        complete("implementation")
        statuses["code_review"] = StageStatus.CHANGES_REQUESTED.value
        trace.append(f"code_review:changes_requested:{first_hash}")
        self.event_sink({"type": "review.decided", "decision": "changes_requested",
                         "artifact_hash": first_hash, "summary": "Code review requested changes"})
        review_rounds = 1
        revised_hash = artifact("implementation/health-check-revision.patch", "developer",
            "revision 2: command prints healthy, exits zero, includes deterministic tests and docs", "source_patch",
            patch_artifact_id)
        trace.append("developer:revision:1")
        artifact("review/code-review.md", "code_reviewer",
                 f"Approved exact patch {revised_hash} after required exit-code test was added.", "review_report")
        complete("code_review")
        artifact("quality/test-plan.md", "qa_engineer", "Test output, exit code and regression behavior.", "test_report")
        artifact("quality/test-report.md", "qa_engineer", f"PASS exact candidate {revised_hash}.", "test_report")
        complete("qa")
        artifact("security/release-risk-report.md", "security_release_officer",
                 f"PASS exact candidate {revised_hash}; no network, secrets, dependency or host mutation.", "security_report")
        artifact("release/release-checklist.md", "security_release_officer",
                 "Tests pass; rollback verified; human production approval still required.", "release_notes")
        complete("security_release_review")
        if not human_approved:
            statuses["final_approval_delivery"] = StageStatus.BLOCKED.value
            trace.append("final_approval_delivery:blocked:human_approval")
            self.event_sink({"type": "approval.requested", "status": "pending",
                             "summary": "Human final approval required"})
            return FeatureDeliveryResult("blocked", statuses, versions, review_rounds, False,
                                         {"tokens": tokens, "cost_units": 0.0, "tool_calls": tool_calls},
                                         tuple(trace), "")
        final = json.dumps({"delivery": "health-check command", "approval": "human-approved",
                            "review_rounds": review_rounds, "candidate_hash": revised_hash,
                            "cost": {"tokens": tokens, "cost_units": 0.0, "tool_calls": tool_calls},
                            "trace": trace}, sort_keys=True)
        artifact("delivery/final-report.md", "chief_of_staff", final, "final_delivery_package")
        self.event_sink({"type": "approval.decided", "status": "approved",
                         "summary": "Human final approval simulated"})
        complete("final_approval_delivery")
        self.event_sink({"type": "execution.completed", "status": "completed",
                         "summary": "Feature delivery completed"})
        return FeatureDeliveryResult("completed", statuses, versions, review_rounds, True,
                                     {"tokens": tokens, "cost_units": 0.0, "tool_calls": tool_calls},
                                     tuple(trace), final)
