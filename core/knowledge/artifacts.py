"""Immutable versioned artifact metadata and safe storage adapters."""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from core.domain import Clock, IdGenerator, UtcClock, UuidIdGenerator
from core.domain.base import json_value, require_id, require_utc

from .memory import Sensitivity


class ArtifactStoreError(ValueError):
    pass


class ArtifactReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"


class ArtifactApprovalStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ArtifactVersionRecord:
    id: str
    artifact_id: str
    version_number: int
    content_hash: str
    producer_agent_id: str
    source_task_id: str
    parent_artifact_id: str | None
    mime_type: str
    artifact_type: str
    storage_location: str
    review_status: ArtifactReviewStatus
    approval_status: ArtifactApprovalStatus
    provenance: tuple[str, ...]
    created_at: datetime
    sensitivity: Sensitivity
    metadata: dict[str, Any]
    size_bytes: int

    def __post_init__(self) -> None:
        for value in (self.id, self.artifact_id, self.producer_agent_id, self.source_task_id):
            require_id(value)
        require_utc(self.created_at, "artifact.created_at")
        if self.version_number < 1 or not self.provenance or self.size_bytes < 0:
            raise ArtifactStoreError("artifact version metadata is invalid")


class ArtifactStore(Protocol):
    def put(self, *, artifact_id: str, data: bytes, display_name: str, producer_agent_id: str,
            source_task_id: str, mime_type: str, artifact_type: str,
            provenance: tuple[str, ...], sensitivity: Sensitivity,
            parent_artifact_id: str | None = None,
            metadata: dict[str, Any] | None = None) -> ArtifactVersionRecord: ...
    def read(self, version: ArtifactVersionRecord) -> bytes: ...


def _hash(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _safe_id(value: str, field: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value or ""):
        raise ArtifactStoreError(f"{field} must be a safe generated identifier")


class InMemoryArtifactStore:
    def __init__(self, clock: Clock | None = None, ids: IdGenerator | None = None) -> None:
        self.clock = clock or UtcClock()
        self.ids = ids or UuidIdGenerator()
        self._versions: dict[str, list[ArtifactVersionRecord]] = {}
        self._data: dict[str, bytes] = {}

    def put(self, *, artifact_id: str, data: bytes, display_name: str, producer_agent_id: str,
            source_task_id: str, mime_type: str, artifact_type: str,
            provenance: tuple[str, ...], sensitivity: Sensitivity,
            parent_artifact_id: str | None = None,
            metadata: dict[str, Any] | None = None) -> ArtifactVersionRecord:
        _safe_id(artifact_id, "artifact_id")
        versions = self._versions.setdefault(artifact_id, [])
        version_id = self.ids.new_id("ARTVER")
        _safe_id(version_id, "version_id")
        record = ArtifactVersionRecord(version_id, artifact_id, len(versions) + 1, _hash(data),
            producer_agent_id, source_task_id, parent_artifact_id, mime_type, artifact_type,
            f"memory://{version_id}", ArtifactReviewStatus.UNREVIEWED,
            ArtifactApprovalStatus.NOT_REQUIRED, provenance, self.clock.now(), sensitivity,
            {**(metadata or {}), "display_name": display_name}, len(data))
        versions.append(record)
        self._data[version_id] = bytes(data)
        return record

    def read(self, version: ArtifactVersionRecord) -> bytes:
        data = self._data[version.id]
        if _hash(data) != version.content_hash:
            raise ArtifactStoreError("artifact immutable hash validation failed")
        return bytes(data)

    def list_versions(self) -> tuple[ArtifactVersionRecord, ...]:
        """Return immutable metadata ordered by artifact ID and version."""
        return tuple(record for artifact_id in sorted(self._versions)
                     for record in self._versions[artifact_id])


class LocalFileArtifactStore(InMemoryArtifactStore):
    """Atomic local store using generated ID paths, never model-provided names."""
    def __init__(self, root: str | Path, clock: Clock | None = None,
                 ids: IdGenerator | None = None) -> None:
        super().__init__(clock, ids)
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, **kwargs: Any) -> ArtifactVersionRecord:
        data = kwargs["data"]
        record = super().put(**kwargs)
        directory = self.root / record.artifact_id
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{record.id}.bin"
        self._ensure_safe(target)
        handle, temporary = tempfile.mkstemp(prefix=".artifact-", dir=directory)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        except Exception:
            versions = self._versions.get(record.artifact_id, [])
            if versions and versions[-1].id == record.id:
                versions.pop()
            if not versions:
                self._versions.pop(record.artifact_id, None)
            self._data.pop(record.id, None)
            raise
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        stored = ArtifactVersionRecord(**{**record.__dict__, "storage_location": str(target)})
        self._versions[record.artifact_id][-1] = stored
        self._data.pop(record.id, None)
        return stored

    def read(self, version: ArtifactVersionRecord) -> bytes:
        path = Path(version.storage_location).resolve()
        self._ensure_safe(path)
        data = path.read_bytes()
        if _hash(data) != version.content_hash:
            raise ArtifactStoreError("artifact immutable hash validation failed")
        return data

    def read_location(self, location: str) -> bytes:
        """Reject arbitrary/model-provided paths outside the generated store."""
        path = Path(location).resolve()
        self._ensure_safe(path)
        return path.read_bytes()

    def _ensure_safe(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.root)
        except ValueError as exc:
            raise ArtifactStoreError("artifact path escapes configured store") from exc
