"""Append-only tamper-evident local audit chain."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.domain.base import json_value

from .events import OrganizationEvent, ObservabilityError


@dataclass(frozen=True)
class AuditChainEntry:
    sequence: int
    event: OrganizationEvent
    previous_hash: str
    entry_hash: str


class AppendOnlyAuditLog:
    """Application-level append-only log; hashes detect but cannot prevent host tampering."""
    def __init__(self) -> None:
        self._entries: list[AuditChainEntry] = []

    def append(self, event: OrganizationEvent) -> AuditChainEntry:
        previous = self._entries[-1].entry_hash if self._entries else "GENESIS"
        payload = json.dumps({"sequence": len(self._entries) + 1, "previous_hash": previous,
                              "event": event.to_dict()}, sort_keys=True, separators=(",", ":"))
        entry = AuditChainEntry(len(self._entries) + 1, event, previous,
                                hashlib.sha256(payload.encode()).hexdigest())
        self._entries.append(entry)
        return entry

    def entries(self) -> tuple[AuditChainEntry, ...]:
        return tuple(self._entries)

    def verify(self) -> bool:
        previous = "GENESIS"
        for index, entry in enumerate(self._entries, 1):
            payload = json.dumps({"sequence": index, "previous_hash": previous,
                                  "event": entry.event.to_dict()}, sort_keys=True, separators=(",", ":"))
            expected = hashlib.sha256(payload.encode()).hexdigest()
            if entry.sequence != index or entry.previous_hash != previous or entry.entry_hash != expected:
                return False
            previous = entry.entry_hash
        return True

    def save(self, *args: Any, **kwargs: Any) -> None:
        raise ObservabilityError("audit entries are append-only")

    def delete(self, *args: Any, **kwargs: Any) -> None:
        raise ObservabilityError("audit entries are append-only")
