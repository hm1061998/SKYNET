import json
import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import unittest

from core.agents import AgentLifecycleManager, AgentRuntime, ModelRouter, RoutedModelProfile
from core.domain import AgentInstance, AgentStatus, SequenceIdGenerator
from core.governance import (ActionRequest, ApprovalService, ApprovalType, AuditService,
                             SandboxSpec)
from core.knowledge import LocalFileArtifactStore, Sensitivity
from core.registry import Registry
from core.runner import run_skill
from tests.agents.test_agents import context_for, definitions
from tests.fixtures.support import FakeClock, MockOutputProvider, fake_sandbox
from tests.governance.test_governance import request


class FailureInjectionTests(unittest.TestCase):
    def runtime(self, outputs):
        role, _, _ = definitions()
        instance = AgentInstance("instance", role.id, AgentStatus.ASSIGNED,
                                 FakeClock().now(), "wo")
        events = []
        router = ModelRouter({"balanced_reasoning": RoutedModelProfile(
            "balanced_reasoning", "mock", "mock-1", "work")})
        runtime = AgentRuntime(MockOutputProvider(outputs), router, AgentLifecycleManager(
            events.append, FakeClock(), SequenceIdGenerator()), max_repairs=0)
        return runtime, context_for(instance, role), events

    def test_provider_timeout_fails_visibly_and_preserves_audit_transitions(self):
        runtime, context, events = self.runtime([TimeoutError("provider timed out")])
        outcome = runtime.execute(context)
        self.assertEqual(outcome.instance.status, AgentStatus.FAILED)
        self.assertEqual(outcome.error, "provider failure: TimeoutError")
        self.assertEqual([item.details["to"] for item in events], ["running", "failed"])

    def test_malformed_model_json_fails_boundedly(self):
        runtime, context, _ = self.runtime(["{broken"])
        outcome = runtime.execute(context)
        self.assertEqual(outcome.instance.status, AgentStatus.FAILED)
        self.assertIsNotNone(outcome.error)

    def test_database_lock_is_visible_and_committed_state_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "locked.db"
            owner = sqlite3.connect(path, timeout=0)
            contender = sqlite3.connect(path, timeout=0)
            try:
                owner.execute("CREATE TABLE state(id TEXT PRIMARY KEY, value TEXT)")
                owner.execute("INSERT INTO state VALUES('before','safe')")
                owner.commit()
                owner.execute("BEGIN EXCLUSIVE")
                with self.assertRaises(sqlite3.OperationalError):
                    contender.execute("INSERT INTO state VALUES('during','lost')")
                owner.rollback()
                self.assertEqual(owner.execute("SELECT value FROM state WHERE id='before'").fetchone()[0], "safe")
            finally:
                contender.close()
                owner.close()

    def test_artifact_write_failure_is_visible_and_no_version_is_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalFileArtifactStore(directory, FakeClock(), SequenceIdGenerator())
            with patch("core.knowledge.artifacts.os.replace", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    store.put(artifact_id="artifact", data=b"content", display_name="result",
                        producer_agent_id="agent", source_task_id="task", mime_type="text/plain",
                        artifact_type="report", provenance=("task",), sensitivity=Sensitivity.INTERNAL)
            self.assertNotIn("artifact", store._versions)

    def test_worker_crash_is_normalized(self):
        result = run_skill({"run": lambda: 1 / 0}, {})
        self.assertFalse(result["success"])
        self.assertTrue(result["_crashed"])

    def test_scheduler_restart_is_covered_by_durable_e2e_fixture(self):
        source = (Path(__file__).parents[1] / "e2e" / "test_phase11_e2e.py").read_text(encoding="utf-8")
        self.assertIn("test_09_process_restart_and_resume", source)
        self.assertIn("SQLiteStore", source)

    def test_audit_failure_propagates_without_false_success(self):
        class FailingRepository:
            def add(self, event):
                raise OSError("audit unavailable")
        details = {"action": "read", "arguments_hash": "hash", "policy_effect": "allow",
                   "allowed": True, "reason": "fixture"}
        with self.assertRaisesRegex(OSError, "audit unavailable"):
            AuditService(FailingRepository(), FakeClock(), SequenceIdGenerator()).record(request(), details)

    def test_approval_expiration_denies_reuse(self):
        req = request("delete_file", {"path": "output/a.txt"})
        clock = FakeClock()
        service = ApprovalService(clock, SequenceIdGenerator())
        grant = service.grant(req, ApprovalType.DESTRUCTIVE_FILE_ACTION, "human",
                              clock.now() + timedelta(seconds=1))
        clock.value += timedelta(seconds=2)
        self.assertFalse(service.valid(grant, req))

    def test_sandbox_timeout_is_structured(self):
        sandbox = fake_sandbox(timed_out=True)
        result = sandbox.execute(SandboxSpec(("fixture",), timeout_seconds=0.01))
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_status)
        self.assertEqual(len(sandbox.calls), 1)

    def test_dependency_unavailable_does_not_crash_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "broken.py").write_text(
                "import definitely_missing_phase11_dependency\nSKILL_META={}\ndef run(): return {}\n",
                encoding="utf-8")
            registry = Registry(Path(directory)).load()
            self.assertEqual(registry.count(), 0)
            self.assertIn("broken.py", registry.load_errors)


if __name__ == "__main__":
    unittest.main()
