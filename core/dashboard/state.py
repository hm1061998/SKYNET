"""Structured, redacted dashboard read models and approval commands."""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.company import OrganizationTemplateLoader, STAGES
from core.governance import action_hash
from core.observability import MetricsCalculator


class DashboardStateError(ValueError):
    pass


@dataclass
class DashboardState:
    """MVP file-backed organization projection; no chain-of-thought or secrets."""

    project_root: Path

    def __post_init__(self) -> None:
        self.template = OrganizationTemplateLoader().load(
            self.project_root / "organizations" / "software-company-v1.yaml")
        self.csrf_token = secrets.token_urlsafe(24)
        self.approval_id = "approval-health-release"
        self.approval_action = "deliver_health_check_candidate"
        self.approval_arguments = {"work_order_id": "wo-health-check", "candidate_hash": "sha256:candidate-v2"}
        self.approval_hash = action_hash(self.approval_action, self.approval_arguments)
        self.approval_status = "pending"

    def organizations(self) -> list[dict[str, Any]]:
        return [{"id": self.template.template_id, "version": self.template.version,
                 "departments": self.template.departments,
                 "reporting_lines": self.template.reporting_lines,
                 "feature_flags": {"enable_3d_graph": False}}]

    def work_orders(self) -> list[dict[str, Any]]:
        tasks = self.tasks("wo-health-check")
        completed = sum(item["status"] == "completed" for item in tasks)
        return [{"id": "wo-health-check", "goal": "Add a health-check command",
                 "title": "Health-check feature delivery", "status": "waiting_approval",
                 "accountable_owner": "chief_of_staff", "progress": completed / len(tasks),
                 "blockers": ["Human final approval required"],
                 "pending_approval_ids": [self.approval_id] if self.approval_status == "pending" else [],
                 "budget": {"tokens_used": 1840, "tokens_remaining": 48160,
                            "cost_units_used": 0.0, "tool_calls": 11},
                 "latest_deliverables": ["quality/test-report.md", "security/release-risk-report.md"]}]

    def work_order(self, work_order_id: str) -> dict[str, Any] | None:
        return next((item for item in self.work_orders() if item["id"] == work_order_id), None)

    def tasks(self, work_order_id: str) -> list[dict[str, Any]]:
        if work_order_id != "wo-health-check":
            return []
        result = []
        for index, stage in enumerate(STAGES):
            waiting = stage.id == "final_approval_delivery" and self.approval_status == "pending"
            result.append({"id": f"task-{stage.id}", "work_order_id": work_order_id,
                "title": stage.id.replace("_", " ").title(), "owner": stage.owner_role,
                "dependencies": [f"task-{item}" for item in stage.dependencies],
                "status": "waiting_approval" if waiting else "completed", "retry_count": 1 if stage.id == "code_review" else 0,
                "risk": "high" if stage.id == "security_release_review" else "medium",
                "approval_gate": self.approval_id if waiting else None,
                "artifact_outputs": self._task_artifacts(stage.id),
                "blocked_reason": "Human final approval required" if waiting else None,
                "cost": {"tokens": 150 + index * 20, "tool_calls": 1, "duration_ms": 320 + index * 30}})
        return result

    def task(self, task_id: str) -> dict[str, Any] | None:
        return next((item for item in self.tasks("wo-health-check") if item["id"] == task_id), None)

    def agents(self) -> list[dict[str, Any]]:
        task_by_owner = {item["owner"]: item for item in self.tasks("wo-health-check")}
        agents = [{"id": role.id, "name": role.name, "kind": "role", "department": role.department_id,
                   "status": task_by_owner.get(role.id, {}).get("status", "idle"),
                   "current_task": task_by_owner.get(role.id, {}).get("id"),
                   "capabilities": [item.name for item in role.capabilities]}
                  for role in self.template.roles]
        agents.append({"id": "worker-test-writer-1", "name": "Test Writer #1", "kind": "worker",
                       "department": "quality_security", "status": "completed",
                       "current_task": "task-qa", "capabilities": ["run_tests"],
                       "expires_at": "2026-07-22T13:00:00+00:00"})
        return agents

    def artifacts(self) -> list[dict[str, Any]]:
        paths = [path for stage in STAGES for path in self._task_artifacts(stage.id)]
        return [{"id": f"artifact-{index}", "path": path, "version": 2 if "patch" in path else 1,
                 "producer": self._producer(path), "source_task": self._source_task(path),
                 "review_status": "approved", "approval_status": "approved",
                 "content_hash": "sha256:" + hashlib.sha256(path.encode()).hexdigest(),
                 "preview": f"Structured preview for {path}", "download_safe": True}
                for index, path in enumerate(paths, 1)]

    def approvals(self) -> list[dict[str, Any]]:
        return [{"id": self.approval_id, "status": self.approval_status,
                 "requested_action": self.approval_action, "action_hash": self.approval_hash,
                 "requesting_agent": "chief_of_staff", "reason": "Complete governed final delivery",
                 "scope": self.approval_arguments, "risk": "high",
                 "affected_resources": ["delivery/final-report.md"],
                 "budget_impact": {"tokens": 120, "cost_units": 0.0},
                 "expires_at": "2026-07-22T14:00:00+00:00", "requires_confirmation": True}]

    def events(self) -> list[dict[str, Any]]:
        names = ("goal_received", "task_assigned", "agent_started", "artifact_created",
                 "review_requested", "task_retried", "task_completed", "approval_needed")
        return [{"id": f"event-{index}", "type": name, "occurred_at": f"2026-07-22T12:{index:02d}:00+00:00",
                 "summary": name.replace("_", " ").title(), "work_order_id": "wo-health-check"}
                for index, name in enumerate(names)]

    def metrics(self) -> dict[str, Any]:
        calculator = MetricsCalculator()
        tasks = self.tasks("wo-health-check")
        work_order_records = [{"status": "completed" if item["status"] == "completed" else "blocked",
            "duration_ms": item["cost"]["duration_ms"], "blocked_ms": 90 if item["blocked_reason"] else 0,
            "approval_wait_ms": 90 if item["approval_gate"] else 0, "cost": 0.0,
            "revisions": item["retry_count"], "escalations": int(bool(item["blocked_reason"]))}
            for item in tasks]
        agent_records = [{"agent_id": item["owner"], "success": item["status"] == "completed",
            "first_pass": item["retry_count"] == 0, "defects": item["retry_count"],
            "artifact_units": max(1, len(item["artifact_outputs"])), "cost": 0.0,
            "duration_ms": item["cost"]["duration_ms"], "retries": item["retry_count"],
            "policy_violations": 0, "delegation_accepted": True} for item in tasks]
        skill_records = [{"skill_id": "run_tests", "success": True, "duration_ms": 710,
                          "permissions": ["process:test"], "generated": False}]
        return {"work_orders": {"wo-health-check": calculator.work_order(work_order_records)},
                "agents": calculator.agents(agent_records), "skills": calculator.skills(skill_records),
                "model_profiles": {"balanced_reasoning": {"tokens": 820},
                                   "deep_reasoning": {"tokens": 600}, "code_reasoning": {"tokens": 420}}}

    def trace_summaries(self) -> list[dict[str, Any]]:
        """Return sanitized operational spans; private reasoning and raw prompts are excluded."""
        return [{"trace_id": "trace-health-check", "work_order_id": "wo-health-check",
                 "status": "waiting_approval", "started_at": "2026-07-22T12:00:00+00:00",
                 "duration_ms": 4480, "span_count": 8,
                 "spans": [{"span_id": f"span-{index}", "kind": "approval_wait" if stage.id == "final_approval_delivery" else "artifact_write",
                            "name": stage.id, "parent_span_id": None,
                            "status": "running" if stage.id == "final_approval_delivery" and self.approval_status == "pending" else "completed",
                            "duration_ms": 320 + index * 30, "error_category": None}
                           for index, stage in enumerate(STAGES)]}]

    def configuration(self) -> dict[str, Any]:
        return {"read_only": True, "departments": self.template.departments,
                "roles": [role.to_dict() for role in self.template.roles],
                "model_profiles": self.template.model_profiles, "budgets": self.template.budgets,
                "approval_rules": ["production_requires_human_approval"],
                "workflow_templates": self.template.workflow_templates,
                "feature_flags": {"ui_mode": "organization", "enable_3d_graph": False}}

    def decide_approval(self, approval_id: str, supplied_hash: str, decision: str,
                        csrf_token: str) -> dict[str, Any]:
        if csrf_token != self.csrf_token:
            raise DashboardStateError("invalid CSRF token")
        if approval_id != self.approval_id or supplied_hash != self.approval_hash:
            raise DashboardStateError("approval ID or action hash mismatch")
        if decision not in {"approved", "rejected"}:
            raise DashboardStateError("invalid approval decision")
        self.approval_status = decision
        return {"id": approval_id, "status": decision, "action_hash": supplied_hash}

    @staticmethod
    def _task_artifacts(stage: str) -> list[str]:
        return {"product_specification": ["product/feature-specification.md"],
            "technical_design": ["architecture/technical-design.md", "architecture/ADR-001-health-command.md"],
            "implementation": ["implementation/health-check.patch"],
            "code_review": ["review/code-review.md"], "qa": ["quality/test-plan.md", "quality/test-report.md"],
            "security_release_review": ["security/release-risk-report.md", "release/release-checklist.md"],
            "final_approval_delivery": ["delivery/final-report.md"]}.get(stage, [])

    @staticmethod
    def _producer(path: str) -> str:
        return "developer" if "implementation/" in path else "chief_of_staff" if "delivery/" in path else \
            "qa_engineer" if "quality/" in path else "security_release_officer" if path.startswith(("security/", "release/")) else \
            "code_reviewer" if "review/" in path else "solution_architect" if "architecture/" in path else "product_manager"

    @staticmethod
    def _source_task(path: str) -> str:
        stage = ("qa" if path.startswith("quality/") else
                 "implementation" if path.startswith("implementation/") else
                 "technical_design" if path.startswith("architecture/") else
                 "code_review" if path.startswith("review/") else
                 "security_release_review" if path.startswith(("security/", "release/")) else
                 "final_approval_delivery" if path.startswith("delivery/") else
                 "product_specification")
        return "task-" + stage
