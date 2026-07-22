"""Artifact-bound independent review and bounded evaluator/optimizer loops."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from core.domain import Artifact, ArtifactVersion, BudgetUsage, Clock, IdGenerator, UtcClock, UuidIdGenerator
from core.domain.base import json_value, require_id, require_utc

from .protocol import CollaborationError, REVIEW_SEVERITIES, validate_review_result


@dataclass(frozen=True)
class ReviewRequest:
    id: str
    artifact_id: str
    artifact_version_id: str
    artifact_hash: str
    author_agent_id: str
    reviewer_agent_id: str
    reviewer_role: str
    checklist: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    created_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        for value in (self.id, self.artifact_id, self.artifact_version_id,
                      self.author_agent_id, self.reviewer_agent_id):
            require_id(value)
        require_utc(self.created_at, "review_request.created_at")


@dataclass(frozen=True)
class ReviewRecord:
    id: str
    request_id: str
    reviewer_agent_id: str
    decision: str
    findings: tuple[dict[str, Any], ...]
    summary: str
    reviewed_artifact_hash: str
    created_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        for value in (self.id, self.request_id, self.reviewer_agent_id):
            require_id(value)
        require_utc(self.created_at, "review_record.created_at")

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)


class ArtifactReviewService:
    """Bind independent review decisions to one immutable artifact hash."""

    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None,
                 repository: Any | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.repository = repository

    def request(self, artifact: Artifact, version: ArtifactVersion, *, author_agent_id: str,
                reviewer_agent_id: str, reviewer_role: str, checklist: tuple[str, ...],
                acceptance_criteria: tuple[str, ...]) -> ReviewRequest:
        if author_agent_id == reviewer_agent_id:
            raise CollaborationError("self-review is forbidden")
        if version.artifact_id != artifact.id or version not in artifact.versions:
            raise CollaborationError("review version does not belong to artifact")
        if version.content_hash != artifact.content_hash:
            raise CollaborationError("review must target the artifact's current hash")
        return ReviewRequest(self.ids.new_id("REVREQ"), artifact.id, version.id,
                             version.content_hash, author_agent_id, reviewer_agent_id,
                             reviewer_role, checklist, acceptance_criteria, self.clock.now())

    def submit(self, request: ReviewRequest, reviewer_agent_id: str,
               payload: dict[str, Any]) -> ReviewRecord:
        if reviewer_agent_id != request.reviewer_agent_id:
            raise CollaborationError("reviewer does not match review assignment")
        validate_review_result(payload)
        if payload["reviewed_artifact_hash"] != request.artifact_hash:
            raise CollaborationError("review result hash does not match requested artifact")
        record = ReviewRecord(self.ids.new_id("REVIEW"), request.id, reviewer_agent_id,
                              payload["decision"], tuple(payload["findings"]), payload["summary"],
                              payload["reviewed_artifact_hash"], self.clock.now())
        if self.repository is not None:
            self.repository.add(record)
        return record

    @staticmethod
    def approval_is_current(record: ReviewRecord, artifact: Artifact) -> bool:
        return record.decision in {"approved", "approved_with_notes"} and \
            record.reviewed_artifact_hash == artifact.content_hash


class RevisionState(str, Enum):
    REVISION_REQUIRED = "revision_required"
    COMPLETED = "completed"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class RevisionOutcome:
    state: RevisionState
    round_number: int
    escalation_target: str | None = None
    reason: str | None = None


class EvaluatorOptimizerLoop:
    """Apply explicit round and budget stops to producer/reviewer iteration."""

    _SEVERITY = {name: index for index, name in enumerate(("info", "low", "medium", "high", "critical"))}

    def __init__(self, *, max_rounds: int, severity_threshold: str,
                 escalation_target: str, budget_cap: BudgetUsage) -> None:
        if max_rounds < 1 or severity_threshold not in REVIEW_SEVERITIES:
            raise CollaborationError("invalid revision-loop configuration")
        require_id(escalation_target, "escalation_target")
        self.max_rounds = max_rounds
        self.severity_threshold = severity_threshold
        self.escalation_target = escalation_target
        self.budget_cap = budget_cap
        self.rounds = 0
        self.usage = BudgetUsage()

    def evaluate(self, record: ReviewRecord, usage: BudgetUsage) -> RevisionOutcome:
        self.rounds += 1
        self.usage = self.usage.plus(usage)
        if record.decision in {"approved", "approved_with_notes"}:
            return RevisionOutcome(RevisionState.COMPLETED, self.rounds)
        over_budget = (self.usage.tokens > self.budget_cap.tokens or
                       self.usage.cost_units > self.budget_cap.cost_units or
                       self.usage.wall_seconds > self.budget_cap.wall_seconds)
        severe = any(self._SEVERITY[item["severity"]] >= self._SEVERITY[self.severity_threshold]
                     for item in record.findings)
        if over_budget or self.rounds >= self.max_rounds or record.decision == "rejected":
            reason = "budget cap reached" if over_budget else "revision limit or rejection reached"
            return RevisionOutcome(RevisionState.ESCALATED, self.rounds,
                                   self.escalation_target, reason)
        if not severe:
            return RevisionOutcome(RevisionState.COMPLETED, self.rounds)
        return RevisionOutcome(RevisionState.REVISION_REQUIRED, self.rounds)
