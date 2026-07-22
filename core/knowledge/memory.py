"""Layered, provenanced organizational memory records and promotion workflow."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any

from core.domain import Clock, DomainValidationError, IdGenerator, UtcClock, UuidIdGenerator
from core.domain.base import json_value, require_id, require_utc


class MemoryError(DomainValidationError):
    """Raised when organizational memory invariants are violated."""


class MemoryScope(str, Enum):
    CONVERSATION = "conversation"
    TASK = "task"
    AGENT = "agent"
    DEPARTMENT = "department"
    ORGANIZATION = "organization"


class MemoryKind(str, Enum):
    FACT = "fact"
    DECISION = "decision"
    PREFERENCE = "preference"
    LESSON = "lesson"
    PROCEDURE = "procedure"
    WARNING = "warning"


class ValidationStatus(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class RetentionPolicy:
    expires_at: datetime | None = None
    archive_with_work_order: bool = False

    def __post_init__(self) -> None:
        if self.expires_at is not None:
            require_utc(self.expires_at, "retention.expires_at")


def content_hash(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    scope: MemoryScope
    owner_id: str
    kind: MemoryKind
    content: str
    source_refs: tuple[str, ...]
    created_at: datetime
    created_by: str
    confidence: float
    validation_status: ValidationStatus
    sensitivity: Sensitivity
    retention: RetentionPolicy
    tags: tuple[str, ...]
    content_hash: str
    version: int = 1

    @property
    def id(self) -> str:
        return self.memory_id

    def __post_init__(self) -> None:
        for value in (self.memory_id, self.owner_id, self.created_by):
            require_id(value)
        require_utc(self.created_at, "memory.created_at")
        if not self.content.strip() or not self.source_refs:
            raise MemoryError("memory content and provenance are required")
        if not 0 <= self.confidence <= 1:
            raise MemoryError("memory confidence must be between zero and one")
        if self.content_hash != content_hash(self.content):
            raise MemoryError("memory content hash mismatch")

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)


@dataclass(frozen=True)
class MemoryConflict:
    id: str
    existing_memory_id: str
    proposed_memory_id: str
    source_refs: tuple[str, ...]
    review_required: bool = True
    active_memory_id: str | None = None
    version: int = 1


class MemoryStore:
    """Namespace-preserving in-memory adapter."""
    def __init__(self) -> None:
        self._records: dict[str, MemoryRecord] = {}
        self._conflicts: dict[str, MemoryConflict] = {}

    def add(self, record: MemoryRecord) -> None:
        if record.id in self._records:
            raise MemoryError("memory record already exists")
        self._records[record.id] = record

    def list(self) -> list[MemoryRecord]:
        return list(self._records.values())

    def add_conflict(self, conflict: MemoryConflict) -> None:
        self._conflicts[conflict.id] = conflict

    def conflicts(self) -> list[MemoryConflict]:
        return list(self._conflicts.values())


class MemoryFactory:
    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()

    def create(self, *, scope: MemoryScope, owner_id: str, kind: MemoryKind, content: str,
               source_refs: tuple[str, ...], created_by: str, confidence: float,
               sensitivity: Sensitivity = Sensitivity.INTERNAL,
               retention: RetentionPolicy = RetentionPolicy(), tags: tuple[str, ...] = (),
               status: ValidationStatus = ValidationStatus.UNVERIFIED) -> MemoryRecord:
        return MemoryRecord(self.ids.new_id("MEM"), scope, owner_id, kind, content, source_refs,
                            self.clock.now(), created_by, confidence, status, sensitivity,
                            retention, tags, content_hash(content))


class PromotionService:
    """Require reviewed provenance before shared-memory promotion."""
    def __init__(self, store: MemoryStore, factory: MemoryFactory,
                 constitution_terms: tuple[str, ...] = ()) -> None:
        self.store = store
        self.factory = factory
        self.constitution_terms = tuple(term.lower() for term in constitution_terms)

    def promote(self, source: MemoryRecord, *, target_scope: MemoryScope, owner_id: str,
                reviewer_id: str, approved: bool) -> MemoryRecord | MemoryConflict:
        if source.scope is not MemoryScope.TASK:
            raise MemoryError("only task memory enters the shared promotion workflow")
        if target_scope not in {MemoryScope.DEPARTMENT, MemoryScope.ORGANIZATION}:
            raise MemoryError("promotion target must be shared memory")
        if source.created_by == reviewer_id or not approved or source.confidence < 0.7:
            raise MemoryError("promotion requires independent approval and sufficient confidence")
        if source.sensitivity in {Sensitivity.CONFIDENTIAL, Sensitivity.RESTRICTED}:
            raise MemoryError("sensitive memory cannot be promoted to shared scope")
        if source.retention.expires_at and source.retention.expires_at <= self.factory.clock.now():
            raise MemoryError("expired memory cannot be promoted")
        if self.constitution_terms and any(term in source.content.lower() for term in ("ignore policy", "bypass")):
            raise MemoryError("proposed lesson conflicts with constitution controls")
        duplicate = next((item for item in self.store.list() if item.scope is target_scope and
                          item.owner_id == owner_id and item.content_hash == source.content_hash), None)
        if duplicate:
            return duplicate
        proposed = self.factory.create(scope=target_scope, owner_id=owner_id, kind=source.kind,
            content=source.content, source_refs=source.source_refs + (source.id,),
            created_by=reviewer_id, confidence=source.confidence, sensitivity=source.sensitivity,
            tags=source.tags, status=ValidationStatus.VERIFIED)
        conflict = next((item for item in self.store.list() if item.scope is target_scope and
                         item.owner_id == owner_id and item.kind is source.kind and
                         item.validation_status is ValidationStatus.VERIFIED and
                         set(item.tags) & set(source.tags) and item.content_hash != source.content_hash), None)
        self.store.add(proposed)
        if conflict:
            record = MemoryConflict(self.factory.ids.new_id("CONFLICT"), conflict.id, proposed.id,
                                    conflict.source_refs + proposed.source_refs)
            self.store.add_conflict(record)
            return record
        return proposed

    def resolve_conflict(self, conflict: MemoryConflict, active_memory_id: str,
                         reviewer_id: str) -> MemoryConflict:
        if active_memory_id not in {conflict.existing_memory_id, conflict.proposed_memory_id}:
            raise MemoryError("active conflict version must be one of the preserved records")
        return replace(conflict, active_memory_id=active_memory_id, review_required=False,
                       version=conflict.version + 1)
