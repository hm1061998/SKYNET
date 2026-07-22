"""Bounded, provenance-preserving context packages."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from core.domain import Clock, DomainValidationError, IdGenerator, UtcClock, UuidIdGenerator
from core.domain.base import json_value, require_id, require_utc, utc_from_iso


@dataclass(frozen=True)
class ProvenanceRecord:
    source_type: str
    source_id: str
    content_hash: str

    def __post_init__(self) -> None:
        if not self.source_type or not self.content_hash:
            raise DomainValidationError("context provenance type/hash are required")
        require_id(self.source_id, "provenance.source_id")


@dataclass(frozen=True)
class ContextPackage:
    id: str
    organization_id: str
    work_order_id: str
    task_id: str
    goal_summary: str
    current_task: str
    accepted_assumptions: tuple[str, ...]
    decisions: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    memory_excerpts: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    constraints: tuple[str, ...]
    permission_summary: str
    output_requirements: str
    provenance: tuple[ProvenanceRecord, ...]
    created_at: datetime
    truncated: bool = False
    version: int = 1

    def __post_init__(self) -> None:
        for name in ("id", "organization_id", "work_order_id", "task_id"):
            require_id(getattr(self, name), f"context.{name}")
        require_utc(self.created_at, "context.created_at")
        if not self.provenance:
            raise DomainValidationError("context package requires provenance")
        if self.version < 1:
            raise DomainValidationError("context package version must be positive")

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextPackage":
        return cls(
            data["id"], data["organization_id"], data["work_order_id"], data["task_id"],
            data.get("goal_summary", ""), data.get("current_task", ""),
            tuple(data.get("accepted_assumptions", ())), tuple(data.get("decisions", ())),
            tuple(data.get("artifact_refs", ())), tuple(data.get("memory_excerpts", ())),
            tuple(data.get("unresolved_questions", ())), tuple(data.get("constraints", ())),
            data.get("permission_summary", ""), data.get("output_requirements", ""),
            tuple(ProvenanceRecord(**item) for item in data.get("provenance", ())),
            utc_from_iso(data["created_at"]), bool(data.get("truncated", False)),
            int(data.get("version", 1)),
        )

    def serialized_size(self) -> int:
        return len(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True))

    def estimated_tokens(self) -> int:
        return (self.serialized_size() + 3) // 4


class ContextPackageBuilder:
    """Build packages and deterministically truncate low-priority sections."""

    _TRUNCATION_ORDER = (
        "memory_excerpts", "unresolved_questions", "artifact_refs", "decisions",
        "accepted_assumptions", "constraints", "permission_summary", "output_requirements",
        "current_task", "goal_summary",
    )

    def __init__(self, max_chars: int, max_tokens: int, clock: Clock | None = None,
                 ids: IdGenerator | None = None) -> None:
        if max_chars < 256 or max_tokens < 64:
            raise DomainValidationError("context budgets are too small for a valid envelope")
        self.max_chars = max_chars
        self.max_tokens = max_tokens
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def build(self, *, organization_id: str, work_order_id: str, task_id: str,
              goal_summary: str, current_task: str, accepted_assumptions: tuple[str, ...] = (),
              decisions: tuple[str, ...] = (), artifact_refs: tuple[str, ...] = (),
              memory_excerpts: tuple[str, ...] = (), unresolved_questions: tuple[str, ...] = (),
              constraints: tuple[str, ...] = (), permission_summary: str = "",
              output_requirements: str = "", provenance: tuple[ProvenanceRecord, ...] = ()) -> ContextPackage:
        package = ContextPackage(
            self.ids.new_id("CTX"), organization_id, work_order_id, task_id,
            goal_summary, current_task, accepted_assumptions, decisions, artifact_refs,
            memory_excerpts, unresolved_questions, constraints, permission_summary,
            output_requirements, provenance, self.clock.now(), False,
        )
        if self._fits(package):
            return package
        package = replace(package, truncated=True)
        for field_name in self._TRUNCATION_ORDER:
            while not self._fits(package):
                value = getattr(package, field_name)
                reduced = self._reduce(value)
                if reduced == value:
                    break
                package = replace(package, **{field_name: reduced})
        if not self._fits(package):
            raise DomainValidationError("context metadata/provenance exceeds configured budget")
        return package

    def _fits(self, package: ContextPackage) -> bool:
        return package.serialized_size() <= self.max_chars and package.estimated_tokens() <= self.max_tokens

    @staticmethod
    def _reduce(value: Any) -> Any:
        if isinstance(value, tuple):
            if not value:
                return value
            last = value[-1]
            if len(last) > 32:
                return value[:-1] + (last[: max(16, len(last) // 2)] + "…",)
            return value[:-1]
        if isinstance(value, str):
            if not value:
                return value
            if len(value) <= 32:
                return ""
            return value[: max(16, len(value) // 2)] + "…"
        return value
