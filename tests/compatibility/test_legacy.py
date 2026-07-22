from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone

from core.compatibility import LegacyInvocationAdapter, LegacyMemoryAdapter
from core.domain import SequenceIdGenerator
from core.memory import Memory


class FixedClock:
    def now(self):
        return datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class LegacyCompatibilityTests(unittest.TestCase):
    def test_invocation_projection_is_deterministic_and_connected(self) -> None:
        projection = LegacyInvocationAdapter(FixedClock(), SequenceIdGenerator()).project(
            "resize image", owner_id="owner")
        self.assertEqual("org_000001", projection.organization.id)
        self.assertEqual("legacy-v1", projection.work_order.constitution_version)
        self.assertEqual((projection.task.id,), projection.work_order.task_ids)
        self.assertEqual(projection.work_order.id, projection.task.work_order_id)
        self.assertEqual("owner", projection.work_order.accountable_owner_id)
        self.assertEqual("resize image", projection.task.title)
        self.assertIn("organization", projection.to_dict())

    def test_jsonl_memory_adapter_preserves_legacy_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = Memory(root=directory, session="adapter").load()
            adapter = LegacyMemoryAdapter(memory)
            adapter.add_turn("user", "hello")
            adapter.remember("Prefer safe changes", tags=["safe"])
            self.assertEqual("hello", memory.history()[-1]["content"])
            self.assertTrue(adapter.recall("safe"))
            self.assertIn("Prefer safe changes", adapter.context_block("safe"))


if __name__ == "__main__":
    unittest.main()
