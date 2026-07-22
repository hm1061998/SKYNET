"""Deterministic offline evaluation cases and evaluators."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    input: dict[str, Any]
    expected: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "EvaluationCase":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(str(data["id"]), dict(data["input"]), dict(data["expected"]))


@dataclass(frozen=True)
class EvaluationCheck:
    name: str
    passed: bool
    details: str


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    passed: bool
    checks: tuple[EvaluationCheck, ...]


class EvaluationRunner:
    """Code evaluators are authoritative; optional judge only adds non-security notes."""
    def __init__(self, optional_judge: Callable[[dict[str, Any]], str] | None = None) -> None:
        self.optional_judge = optional_judge

    def run(self, case: EvaluationCase, actual: dict[str, Any]) -> EvaluationResult:
        expected = case.expected
        artifacts = set(actual.get("artifacts", ()))
        tasks = actual.get("tasks", ())
        checks = [
            EvaluationCheck("schema_validity", isinstance(actual, dict) and isinstance(tasks, list), "structured result"),
            EvaluationCheck("artifact_presence", set(expected["required_artifacts"]) <= artifacts, "required artifact paths"),
            EvaluationCheck("acceptance_criteria_coverage", actual.get("acceptance_coverage", 0) >= 1.0, "coverage must be complete"),
            EvaluationCheck("policy_compliance", not (set(actual.get("actions", ())) & set(expected["forbidden_actions"])), "forbidden actions absent"),
            EvaluationCheck("task_graph_validity", all(set(task.get("dependencies", ())) <= {item["id"] for item in tasks} for task in tasks), "dependencies resolve"),
            EvaluationCheck("review_separation", actual.get("reviewer") != actual.get("author"), "author differs from reviewer"),
            EvaluationCheck("budget_compliance", actual.get("cost", 0) <= expected["maximum_cost"], "cost within maximum"),
            EvaluationCheck("review_rounds", actual.get("review_rounds", 0) <= expected["maximum_review_rounds"], "revision bound"),
            EvaluationCheck("regression_status", actual.get("regression_status") == "passed", "regression suite passed"),
            EvaluationCheck("final_state", actual.get("final_state") in expected["allowed_final_states"], "allowed terminal state"),
        ]
        return EvaluationResult(case.id, all(item.passed for item in checks), tuple(checks))
