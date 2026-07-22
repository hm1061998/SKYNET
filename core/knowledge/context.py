"""Assemble bounded context snippets from authoritative references."""
from __future__ import annotations

from dataclasses import dataclass

from .artifacts import ArtifactStore, ArtifactVersionRecord
from .retrieval import RetrievedMemory


@dataclass(frozen=True)
class ContextSnippet:
    reference_id: str
    text: str
    provenance: tuple[str, ...]
    authoritative_hash: str
    summarized: bool


class ReferenceContextAssembler:
    def __init__(self, max_chars: int, artifact_chunk_chars: int = 1000) -> None:
        if max_chars < 1 or artifact_chunk_chars < 1:
            raise ValueError("context budgets must be positive")
        self.max_chars = max_chars
        self.artifact_chunk_chars = artifact_chunk_chars

    def assemble(self, memories: tuple[RetrievedMemory, ...],
                 artifact_refs: tuple[tuple[ArtifactStore, ArtifactVersionRecord], ...]) -> tuple[ContextSnippet, ...]:
        result = []
        used = 0
        for memory in memories:
            if used + len(memory.content) > self.max_chars:
                continue
            result.append(ContextSnippet(memory.memory_id, memory.content, memory.source_refs,
                                         memory.content_hash, False))
            used += len(memory.content)
        for store, version in artifact_refs:
            remaining = self.max_chars - used
            if remaining <= 0:
                break
            original = store.read(version).decode("utf-8", errors="replace")
            limit = min(remaining, self.artifact_chunk_chars)
            text = original[:limit]
            result.append(ContextSnippet(version.id, text, version.provenance,
                                         version.content_hash, len(text) < len(original)))
            used += len(text)
        return tuple(result)
