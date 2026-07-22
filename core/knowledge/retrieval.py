"""Dependency-light permission-aware memory retrieval."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .memory import (MemoryRecord, MemoryScope, Sensitivity, ValidationStatus)


class EmbeddingSearchPort(Protocol):
    def scores(self, query: str, records: tuple[MemoryRecord, ...]) -> dict[str, float]: ...


@dataclass(frozen=True)
class RetrievedMemory:
    memory_id: str
    content: str
    source_refs: tuple[str, ...]
    score: float
    content_hash: str


class RetrievalService:
    def __init__(self, embedding: EmbeddingSearchPort | None = None) -> None:
        self.embedding = embedding

    def retrieve(self, records: list[MemoryRecord], *, query: str,
                 scopes: frozenset[MemoryScope], permitted_owner_ids: frozenset[str],
                 allowed_sensitivity: frozenset[Sensitivity], now: datetime,
                 confidence_threshold: float = 0, max_chars: int = 2000,
                 limit: int = 10) -> tuple[RetrievedMemory, ...]:
        candidates = [item for item in records if item.scope in scopes and
                      item.owner_id in permitted_owner_ids and item.sensitivity in allowed_sensitivity and
                      item.validation_status not in {ValidationStatus.REJECTED, ValidationStatus.EXPIRED} and
                      item.confidence >= confidence_threshold and
                      not (item.retention.expires_at and item.retention.expires_at <= now)]
        words = set(re.findall(r"\w+", query.lower()))
        embedding = self.embedding.scores(query, tuple(candidates)) if self.embedding else {}
        scored = []
        for item in candidates:
            text_words = set(re.findall(r"\w+", (item.content + " " + " ".join(item.tags)).lower()))
            lexical = len(words & text_words) / max(1, len(words))
            recency = max(0.0, 1.0 - (now - item.created_at).total_seconds() / 31_536_000)
            scored.append((lexical + 0.1 * recency + embedding.get(item.id, 0), item))
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        result = []
        used = 0
        for score, item in scored[:limit]:
            if used + len(item.content) > max_chars:
                continue
            result.append(RetrievedMemory(item.id, item.content, item.source_refs, score, item.content_hash))
            used += len(item.content)
        return tuple(result)
