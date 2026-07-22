"""Independent recommendation protocol for high-risk decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.domain import RiskLevel
from core.domain.base import json_value

from .protocol import CollaborationError


@dataclass(frozen=True)
class CommitteeRecommendation:
    member_id: str
    vote: str
    rationale: str


@dataclass(frozen=True)
class CommitteeDecision:
    decision: str
    decided_by: str
    recommendations: tuple[CommitteeRecommendation, ...]
    dissent: tuple[CommitteeRecommendation, ...]

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)


class HighRiskCommittee:
    """Collect sealed independent votes and preserve dissent in the final record."""

    def __init__(self, risk_level: RiskLevel, members: tuple[str, ...], authorized_decider: str,
                 context_package_ids: dict[str, str] | None = None) -> None:
        if risk_level not in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            raise CollaborationError("committee protocol is reserved for high-risk decisions")
        if len(members) < 2 or len(set(members)) != len(members):
            raise CollaborationError("committee needs at least two unique members")
        self.members = members
        self.authorized_decider = authorized_decider
        self.context_package_ids = context_package_ids or {member: f"sealed:{member}" for member in members}
        if set(self.context_package_ids) != set(members) or \
                len(set(self.context_package_ids.values())) != len(members):
            raise CollaborationError("committee members require independent context packages")
        self._recommendations: dict[str, CommitteeRecommendation] = {}

    def submit(self, member_id: str, vote: str, rationale: str) -> None:
        if member_id not in self.members or member_id in self._recommendations:
            raise CollaborationError("invalid or duplicate committee member submission")
        if vote not in {"approve", "reject", "abstain"} or not rationale.strip():
            raise CollaborationError("committee vote or rationale is invalid")
        self._recommendations[member_id] = CommitteeRecommendation(member_id, vote, rationale)

    def reveal(self) -> tuple[CommitteeRecommendation, ...]:
        if len(self._recommendations) != len(self.members):
            raise CollaborationError("recommendations remain sealed until all members submit")
        return tuple(self._recommendations[member] for member in self.members)

    def finalize(self, actor_id: str, decision: str) -> CommitteeDecision:
        if actor_id != self.authorized_decider:
            raise CollaborationError("actor is not authorized to finalize committee decision")
        if decision not in {"approve", "reject"}:
            raise CollaborationError("final committee decision is invalid")
        recommendations = self.reveal()
        dissent = tuple(item for item in recommendations if item.vote not in {decision, "abstain"})
        return CommitteeDecision(decision, actor_id, recommendations, dissent)
