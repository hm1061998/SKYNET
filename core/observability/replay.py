"""Safe simulation-only event replay."""
from __future__ import annotations

from dataclasses import dataclass

from .events import OrganizationEvent, ObservabilityError


IRREVERSIBLE_TYPES = frozenset({"external.message.sent", "production.deployed", "file.destroyed",
                                "dependency.installed", "secret.accessed"})


@dataclass(frozen=True)
class ReplayResult:
    simulation: bool
    interpreted_event_ids: tuple[str, ...]
    blocked_event_ids: tuple[str, ...]
    idempotency_keys: tuple[str, ...]


class ReplayService:
    def replay(self, events: tuple[OrganizationEvent, ...], *, checkpoint_event_id: str | None = None,
               mock_tools: bool = True) -> ReplayResult:
        if not mock_tools:
            raise ObservabilityError("replay requires mock tool adapters")
        selected = list(events)
        if checkpoint_event_id:
            positions = [index for index, item in enumerate(events) if item.id == checkpoint_event_id]
            selected = list(events[positions[0]:]) if positions else []
        interpreted, blocked, keys = [], [], []
        for event in selected:
            key = str(event.metadata.get("idempotency_key", f"replay:{event.id}"))
            keys.append(key)
            if event.type in IRREVERSIBLE_TYPES or event.metadata.get("irreversible", False):
                blocked.append(event.id)
                continue
            interpreted.append(event.id)
        return ReplayResult(True, tuple(interpreted), tuple(blocked), tuple(keys))
