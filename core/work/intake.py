"""Deterministic goal intake and clarification boundary."""
from __future__ import annotations

from dataclasses import dataclass

from core.domain import (AcceptanceCriterion, Clock, Goal, GoalStatus, IdGenerator,
                         UtcClock, UuidIdGenerator)

from .states import GoalStateMachine


@dataclass(frozen=True)
class GoalIntakeResult:
    goal: Goal
    questions: tuple[str, ...]


class GoalIntakeService:
    """Create a Goal and identify missing deterministic intake fields."""

    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None,
                 states: GoalStateMachine | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self.states = states or GoalStateMachine(clock=self.clock, ids=self.ids)

    def intake(self, objective: str, requested_by: str,
               criteria: tuple[str, ...] = ()) -> GoalIntakeResult:
        title = objective.strip()
        questions = []
        if not title:
            title = "Unclarified goal"
            questions.append("What objective should the organization achieve?")
        if not criteria:
            questions.append("What acceptance criteria define success?")
        accepted = tuple(AcceptanceCriterion(self.ids.new_id("criterion"), value)
                         for value in criteria if value.strip())
        goal = Goal(self.ids.new_id("goal"), title, objective, requested_by,
                    GoalStatus.DRAFT, self.clock.now(), accepted)
        target = GoalStatus.CLARIFICATION if questions else GoalStatus.READY
        return GoalIntakeResult(self.states.transition(goal, target, requested_by), tuple(questions))
