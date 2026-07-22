"""Fully offline, deterministic AI Software Company release demonstration."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.company import MockFeatureDeliveryWorkflow, STAGES  # noqa: E402
from core.domain import SequenceIdGenerator  # noqa: E402
from core.knowledge import InMemoryArtifactStore  # noqa: E402
from core.observability import AppendOnlyAuditLog, EventRecorder, TraceService  # noqa: E402
from core.work import GoalIntakeService  # noqa: E402


class DemoClock:
    def now(self):
        return datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def run(output_root: str | Path | None = None) -> dict:
    """Run the demo and return its inspectable release summary."""
    started = perf_counter()
    output = Path(output_root) if output_root else ROOT / "demo" / "output"
    output.mkdir(parents=True, exist_ok=True)
    clock = DemoClock()
    ids = SequenceIdGenerator()
    goal = GoalIntakeService(clock, ids).intake(
        "Add a health-check capability to the fixture project", "demo-user",
        ("Print healthy and exit zero", "Use no network or new dependency"))

    raw_events: list[dict] = []
    artifacts = InMemoryArtifactStore(clock, ids)
    workflow = MockFeatureDeliveryWorkflow(artifacts, clock, ids, raw_events.append)
    result = workflow.run_health_check(human_approved=True)

    audit = AppendOnlyAuditLog()
    recorded = []
    recorder = EventRecorder(lambda event: (recorded.append(event), audit.append(event)), clock, ids)
    previous = None
    for raw in raw_events:
        event = recorder.record(type=raw["type"], organization_id="ai_software_company",
            work_order_id="demo-work-order", task_id=f"task-{raw.get('stage', 'workflow')}",
            agent_id="demo-runtime", correlation_id=goal.goal.id, causation_id=previous,
            public_summary=raw["summary"], metadata={key: value for key, value in raw.items()
                                                    if key not in {"type", "summary"}})
        previous = event.id

    trace_service = TraceService(clock, ids)
    trace = trace_service.create("ai_software_company", "demo-work-order", goal.goal.id)
    for stage in STAGES:
        trace, span = trace_service.start_span(trace, kind="approval_wait" if stage.id == "final_approval_delivery" else "artifact_write",
                                                name=stage.id, inputs={"owner": stage.owner_role})
        trace = trace_service.finish_span(trace, span.id, status="completed",
                                          outputs={"stage_status": result.stage_statuses[stage.id]}, usage={"cost": 0})

    exported = []
    for version in artifacts.list_versions():
        relative = Path(str(version.metadata["path"]))
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifacts.read(version))
        exported.append({"path": relative.as_posix(), "version": version.version_number,
                         "content_hash": version.content_hash, "producer": version.producer_agent_id,
                         "source_task": version.source_task_id})

    dag = [{"id": stage.id, "owner": stage.owner_role,
            "dependencies": list(stage.dependencies)} for stage in STAGES]
    summary = {
        "status": result.status,
        "goal": goal.goal.to_dict(),
        "work_order_id": "demo-work-order",
        "task_dag": dag,
        "artifacts": exported,
        "approval": {"simulated": True, "decision": "approved"},
        "audit": {"entries": len(audit.entries()), "hash_chain_valid": audit.verify(),
                  "correlation_id": goal.goal.id,
                  "event_ids": [event.id for event in recorded]},
        "trace": {"trace_id": trace.trace_id, "goal_id": trace.goal_id,
                  "work_order_id": trace.work_order_id, "span_count": len(trace.spans),
                  "spans": [{"id": span.id, "name": span.name, "status": span.status,
                             "duration_ms": span.duration_ms} for span in trace.spans]},
        "cost": result.cost_summary,
        "performance": {"startup_and_workflow_ms": round((perf_counter() - started) * 1000, 3),
                        "database_operations": 0, "scheduler_stages": len(STAGES),
                        "artifact_count": len(exported), "trace_event_count": len(recorded),
                        "estimated_memory_records": len(recorded) + len(exported)},
        "offline_guarantees": {"network_calls": 0, "host_installs": 0,
                               "paid_credentials_required": False},
    }
    (output / "demo-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary


if __name__ == "__main__":
    value = run()
    print(json.dumps({"status": value["status"], "output": str(ROOT / "demo" / "output"),
                      "artifacts": len(value["artifacts"]), "audit_valid": value["audit"]["hash_chain_valid"],
                      "cost": value["cost"]}, ensure_ascii=False, sort_keys=True))
