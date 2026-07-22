from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.compatibility import LegacyMemoryAdapter
from core.domain import SequenceIdGenerator
from core.knowledge import (
    ArtifactStoreError, InMemoryArtifactStore, LegacyKnowledgeAdapter,
    LocalFileArtifactStore, MemoryConflict, MemoryError, MemoryFactory, MemoryKind,
    MemoryScope, MemoryStore, PromotionService, ReferenceContextAssembler,
    RetentionPolicy, RetrievalService, Sensitivity, ValidationStatus,
)
from core.memory import Memory


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class FixedClock:
    def now(self):
        return NOW


def factory(start=1):
    return MemoryFactory(FixedClock(), SequenceIdGenerator(start))


def record(scope=MemoryScope.TASK, owner="task", content="Use atomic writes",
           sensitivity=Sensitivity.INTERNAL, retention=RetentionPolicy(), tags=("storage",),
           created_by="worker", confidence=0.9, status=ValidationStatus.UNVERIFIED):
    return factory().create(scope=scope, owner_id=owner, kind=MemoryKind.LESSON,
        content=content, source_refs=("artifact:1",), created_by=created_by,
        confidence=confidence, sensitivity=sensitivity, retention=retention,
        tags=tags, status=status)


class LayeredMemoryTests(unittest.TestCase):
    def test_namespace_isolation_and_unauthorized_retrieval(self):
        records = [record(MemoryScope.AGENT, "agent-a"),
                   record(MemoryScope.DEPARTMENT, "engineering", "Review all patches")]
        found = RetrievalService().retrieve(records, query="review patches",
            scopes=frozenset({MemoryScope.DEPARTMENT}), permitted_owner_ids=frozenset({"engineering"}),
            allowed_sensitivity=frozenset({Sensitivity.INTERNAL}), now=NOW)
        self.assertEqual([item.content for item in found], ["Review all patches"])
        denied = RetrievalService().retrieve(records, query="atomic",
            scopes=frozenset({MemoryScope.AGENT}), permitted_owner_ids=frozenset({"agent-b"}),
            allowed_sensitivity=frozenset({Sensitivity.INTERNAL}), now=NOW)
        self.assertEqual(denied, ())

    def test_promotion_requires_independent_approval_and_blocks_sensitive(self):
        store = MemoryStore()
        source = record()
        store.add(source)
        service = PromotionService(store, factory(10))
        with self.assertRaises(MemoryError):
            service.promote(source, target_scope=MemoryScope.ORGANIZATION,
                            owner_id="org", reviewer_id="worker", approved=True)
        promoted = service.promote(source, target_scope=MemoryScope.ORGANIZATION,
                                   owner_id="org", reviewer_id="reviewer", approved=True)
        self.assertEqual(promoted.validation_status, ValidationStatus.VERIFIED)
        self.assertIn(source.id, promoted.source_refs)
        with self.assertRaises(MemoryError):
            service.promote(record(content="secret procedure", sensitivity=Sensitivity.RESTRICTED),
                            target_scope=MemoryScope.ORGANIZATION, owner_id="org",
                            reviewer_id="reviewer", approved=True)

    def test_conflict_preserves_both_records_for_review(self):
        store = MemoryStore()
        existing = record(MemoryScope.DEPARTMENT, "engineering", "Always squash commits",
                          tags=("git-policy",), created_by="reviewer",
                          status=ValidationStatus.VERIFIED)
        source = replace(record(content="Never squash commits", tags=("git-policy",)),
                         memory_id="MEM_source")
        store.add(existing)
        store.add(source)
        conflict = PromotionService(store, factory(20)).promote(source,
            target_scope=MemoryScope.DEPARTMENT, owner_id="engineering",
            reviewer_id="other-reviewer", approved=True)
        self.assertIsInstance(conflict, MemoryConflict)
        self.assertTrue(conflict.review_required)
        self.assertEqual(len(store.list()), 3)

    def test_retention_expiration_and_sensitive_exclusion(self):
        expired = record(retention=RetentionPolicy(NOW - timedelta(seconds=1)))
        restricted = record(content="restricted", sensitivity=Sensitivity.RESTRICTED)
        found = RetrievalService().retrieve([expired, restricted], query="",
            scopes=frozenset({MemoryScope.TASK}), permitted_owner_ids=frozenset({"task"}),
            allowed_sensitivity=frozenset({Sensitivity.PUBLIC, Sensitivity.INTERNAL}), now=NOW)
        self.assertEqual(found, ())

    def test_context_budget_returns_provenance(self):
        item = record(content="a" * 50)
        retrieved = RetrievalService().retrieve([item], query="", scopes=frozenset({MemoryScope.TASK}),
            permitted_owner_ids=frozenset({"task"}), allowed_sensitivity=frozenset({Sensitivity.INTERNAL}),
            now=NOW, max_chars=50)
        artifact_store = InMemoryArtifactStore(FixedClock(), SequenceIdGenerator())
        version = artifact_store.put(artifact_id="artifact", data=b"b" * 100, display_name="x",
            producer_agent_id="agent", source_task_id="task", mime_type="text/plain",
            artifact_type="report", provenance=("task",), sensitivity=Sensitivity.INTERNAL)
        snippets = ReferenceContextAssembler(80, 30).assemble(retrieved, ((artifact_store, version),))
        self.assertLessEqual(sum(len(item.text) for item in snippets), 80)
        self.assertTrue(snippets[-1].summarized)
        self.assertEqual(snippets[-1].authoritative_hash, version.content_hash)


class ArtifactTests(unittest.TestCase):
    def test_versioning_and_immutable_hash_validation(self):
        store = InMemoryArtifactStore(FixedClock(), SequenceIdGenerator())
        args = dict(artifact_id="artifact", display_name="../unsafe.html", producer_agent_id="agent",
                    source_task_id="task", mime_type="text/plain", artifact_type="report",
                    provenance=("task",), sensitivity=Sensitivity.INTERNAL)
        first = store.put(data=b"one", **args)
        second = store.put(data=b"two", **args)
        self.assertEqual((first.version_number, second.version_number), (1, 2))
        store._data[first.id] = b"tampered"
        with self.assertRaises(ArtifactStoreError):
            store.read(first)

    def test_local_atomic_write_and_unsafe_path_rejection(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = LocalFileArtifactStore(root, FixedClock(), SequenceIdGenerator())
            with patch("core.knowledge.artifacts.os.replace", wraps=__import__("os").replace) as atomic:
                version = store.put(artifact_id="artifact", data=b"safe", display_name="../../bad.exe",
                    producer_agent_id="agent", source_task_id="task", mime_type="application/octet-stream",
                    artifact_type="source_patch", provenance=("task",), sensitivity=Sensitivity.INTERNAL)
                atomic.assert_called_once()
            self.assertEqual(store.read(version), b"safe")
            self.assertNotIn("bad.exe", version.storage_location)
            with self.assertRaises(ArtifactStoreError):
                store.read_location(str(Path(outside, "secret")))
            with self.assertRaises(ArtifactStoreError):
                store.put(artifact_id="../escape", data=b"bad", display_name="bad",
                    producer_agent_id="agent", source_task_id="task", mime_type="text/plain",
                    artifact_type="report", provenance=("task",), sensitivity=Sensitivity.INTERNAL)


class LegacyTests(unittest.TestCase):
    def test_legacy_recall_remains_readable_without_rewrite(self):
        with tempfile.TemporaryDirectory() as root:
            memory = Memory(root=Path(root), session="legacy").load()
            memory.remember("Repository uses atomic writes", kind="note", tags=["repository"])
            before = memory.facts_path.read_bytes()
            adapter = LegacyKnowledgeAdapter(LegacyMemoryAdapter(memory))
            self.assertEqual(adapter.recall("atomic", 1)[0]["text"],
                             "Repository uses atomic writes")
            self.assertEqual(memory.facts_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
