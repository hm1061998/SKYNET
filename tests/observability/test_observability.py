from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from core.company import MockFeatureDeliveryWorkflow
from core.domain import SequenceIdGenerator
from core.observability import (
    AppendOnlyAuditLog, EvaluationCase, EvaluationRunner, EventRecorder, EventSeverity,
    MetricsCalculator, ObservabilityError, ReplayService, TraceService,
)


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class MutableClock:
    def __init__(self): self.value = NOW
    def now(self): return self.value


def event(recorder, kind="task.transition", metadata=None, causation=None):
    return recorder.record(type=kind, organization_id="org", work_order_id="wo", task_id="task",
        agent_id="agent", correlation_id="corr", causation_id=causation,
        public_summary="Operational summary", metadata=metadata or {})


class EventTraceAuditTests(unittest.TestCase):
    def test_correlation_causation_redaction_and_no_reasoning(self):
        recorded = []
        recorder = EventRecorder(recorded.append, MutableClock(), SequenceIdGenerator())
        first = event(recorder, metadata={"token": "secret-value", "decision": "retry"})
        second = event(recorder, "task.retried", {"idempotency_key": "attempt-2"}, first.id)
        self.assertEqual((second.correlation_id, second.causation_id), ("corr", first.id))
        self.assertEqual(first.metadata["token"], "[REDACTED]")
        self.assertEqual(first.redaction_status, "redacted")
        self.assertNotIn("secret-value", str(first.to_dict()))
        summary = recorder.record(type="policy.decided", organization_id="org", correlation_id="corr",
            public_summary="token=secret-value denied", metadata={})
        self.assertNotIn("secret-value", summary.public_summary)
        with self.assertRaises(ObservabilityError):
            event(recorder, metadata={"chain_of_thought": "private"})

    def test_trace_nesting_duration_and_sanitized_io(self):
        clock = MutableClock()
        service = TraceService(clock, SequenceIdGenerator())
        trace = service.create("org", "wo", "goal")
        trace, parent = service.start_span(trace, kind="planning", name="plan", inputs={"secret": "x"})
        trace, child = service.start_span(trace, kind="model_call", name="model",
                                          inputs={"prompt": "public task"}, parent_span_id=parent.id)
        clock.value += timedelta(milliseconds=25)
        trace = service.finish_span(trace, child.id, status="ok", outputs={"decision": "valid"},
                                    usage={"tokens": 10, "cost": 0})
        finished = next(item for item in trace.spans if item.id == child.id)
        self.assertEqual(finished.duration_ms, 25)
        self.assertEqual(finished.parent_span_id, parent.id)
        self.assertEqual(trace.spans[0].sanitized_inputs["secret"], "[REDACTED]")

    def test_audit_is_append_only_and_tamper_evident(self):
        log = AppendOnlyAuditLog()
        recorder = EventRecorder(log.append, MutableClock(), SequenceIdGenerator())
        event(recorder, "policy.decided", {"allowed": False})
        event(recorder, "approval.decided", {"decision": "rejected"})
        self.assertTrue(log.verify())
        self.assertEqual(log.entries()[1].previous_hash, log.entries()[0].entry_hash)
        with self.assertRaises(ObservabilityError): log.delete("x")
        object.__setattr__(log._entries[0], "entry_hash", "tampered")
        self.assertFalse(log.verify())


class MetricsEvalReplayTests(unittest.TestCase):
    def test_metric_calculation(self):
        calc = MetricsCalculator()
        work = calc.work_order([{"status": "completed", "duration_ms": 10, "blocked_ms": 2,
            "approval_wait_ms": 3, "cost": 1.5, "revisions": 1, "escalations": 0},
            {"status": "failed", "duration_ms": 20, "blocked_ms": 4,
             "approval_wait_ms": 5, "cost": 2.5, "revisions": 0, "escalations": 1}])
        self.assertEqual(work, {"completion_rate": .5, "cycle_time_ms": 30,
            "blocked_time_ms": 6, "approval_wait_time_ms": 8, "total_cost": 4.0,
            "revisions": 1, "escalations": 1})
        agents = calc.agents([{"agent_id": "dev", "success": True, "first_pass": False,
            "defects": 2, "artifact_units": 4, "cost": 2, "duration_ms": 10,
            "retries": 1, "policy_violations": 0, "delegation_accepted": True}])
        self.assertEqual(agents["dev"]["review_defect_density"], .5)
        skills = calc.skills([{"skill_id": "health", "success": True, "duration_ms": 5,
                               "permissions": ["read"], "generated": False}])
        self.assertEqual(skills["health"]["success_rate"], 1.0)

    def test_eval_pass_and_fail(self):
        result = MockFeatureDeliveryWorkflow(clock=MutableClock(), ids=SequenceIdGenerator()).run_health_check()
        actual = {"artifacts": list(result.artifact_versions), "tasks": [{"id": "a", "dependencies": []}],
            "acceptance_coverage": 1.0, "actions": [], "reviewer": "code_reviewer", "author": "developer",
            "cost": result.cost_summary["cost_units"], "review_rounds": result.review_rounds,
            "regression_status": "passed", "final_state": result.status}
        case = EvaluationCase.load(ROOT / "evals" / "feature_delivery_health_check.yaml")
        passed = EvaluationRunner().run(case, actual)
        self.assertTrue(passed.passed)
        actual["actions"] = ["production_deploy"]
        failed = EvaluationRunner().run(case, actual)
        self.assertFalse(failed.passed)
        self.assertFalse(next(item for item in failed.checks if item.name == "policy_compliance").passed)

    def test_replay_blocks_irreversible_external_action(self):
        recorded = []
        recorder = EventRecorder(recorded.append, MutableClock(), SequenceIdGenerator())
        safe = event(recorder, "tool.called", {"idempotency_key": "safe-1"})
        external = event(recorder, "sandbox.executed", {"irreversible": True,
                         "action": "external_message", "idempotency_key": "external-1"}, safe.id)
        replay = ReplayService().replay(tuple(recorded), checkpoint_event_id=safe.id)
        self.assertTrue(replay.simulation)
        self.assertIn(external.id, replay.blocked_event_ids)
        self.assertEqual(replay.idempotency_keys, ("safe-1", "external-1"))
        with self.assertRaises(ObservabilityError):
            ReplayService().replay(tuple(recorded), mock_tools=False)

    def test_feature_workflow_emits_every_stage(self):
        emitted = []
        MockFeatureDeliveryWorkflow(clock=MutableClock(), ids=SequenceIdGenerator(),
                                    event_sink=emitted.append).run_health_check()
        completed = {item["stage"] for item in emitted if item["type"] == "task.transition"}
        self.assertEqual(len(completed), 8)
        self.assertIn("review.decided", {item["type"] for item in emitted})
        self.assertIn("execution.completed", {item["type"] for item in emitted})


if __name__ == "__main__":
    unittest.main()
