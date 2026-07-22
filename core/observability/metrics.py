"""Deterministic organizational metric aggregation."""
from __future__ import annotations

from collections import defaultdict
from typing import Any


class MetricsCalculator:
    def work_order(self, records: list[dict[str, Any]]) -> dict[str, float | int]:
        total = len(records)
        completed = sum(item["status"] == "completed" for item in records)
        return {"completion_rate": completed / total if total else 0.0,
                "cycle_time_ms": sum(item.get("duration_ms", 0) for item in records),
                "blocked_time_ms": sum(item.get("blocked_ms", 0) for item in records),
                "approval_wait_time_ms": sum(item.get("approval_wait_ms", 0) for item in records),
                "total_cost": sum(item.get("cost", 0.0) for item in records),
                "revisions": sum(item.get("revisions", 0) for item in records),
                "escalations": sum(item.get("escalations", 0) for item in records)}

    def agents(self, tasks: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in tasks:
            groups[item["agent_id"]].append(item)
        result = {}
        for agent_id, items in groups.items():
            total = len(items)
            result[agent_id] = {
                "task_success_rate": sum(item["success"] for item in items) / total,
                "first_pass_acceptance": sum(item.get("first_pass", False) for item in items) / total,
                "review_defect_density": sum(item.get("defects", 0) for item in items) / max(1, sum(item.get("artifact_units", 1) for item in items)),
                "average_cost": sum(item.get("cost", 0) for item in items) / total,
                "average_duration_ms": sum(item.get("duration_ms", 0) for item in items) / total,
                "retry_rate": sum(item.get("retries", 0) for item in items) / total,
                "policy_violation_attempts": float(sum(item.get("policy_violations", 0) for item in items)),
                "delegation_quality": sum(item.get("delegation_accepted", True) for item in items) / total,
            }
        return result

    def skills(self, calls: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in calls:
            groups[item["skill_id"]].append(item)
        result = {}
        for skill_id, items in groups.items():
            total = len(items)
            result[skill_id] = {"match_frequency": total,
                "success_rate": sum(item["success"] for item in items) / total,
                "crash_rate": sum(item.get("crashed", False) for item in items) / total,
                "recovery_rate": sum(item.get("recovered", False) for item in items) / total,
                "average_duration_ms": sum(item.get("duration_ms", 0) for item in items) / total,
                "required_permissions": sorted({permission for item in items for permission in item.get("permissions", [])}),
                "status": "generated" if any(item.get("generated", False) for item in items) else "verified"}
        return result
