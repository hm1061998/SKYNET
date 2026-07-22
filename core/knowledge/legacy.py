"""Read-only projection of existing JSONL memory without migration."""
from __future__ import annotations

from core.compatibility import LegacyMemoryAdapter


class LegacyKnowledgeAdapter:
    def __init__(self, adapter: LegacyMemoryAdapter) -> None:
        self.adapter = adapter

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        return self.adapter.recall(query, k=limit)

    def history(self, limit: int = 6) -> list[dict]:
        return self.adapter.memory.history(limit=limit)
