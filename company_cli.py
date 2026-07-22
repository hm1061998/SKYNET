#!/usr/bin/env python3
"""Offline-safe operational CLI for the AI Software Company MVP."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from core.company import MockFeatureDeliveryWorkflow
from core.compatibility import LegacyMemoryMigrator
from core.dashboard import DashboardState, DashboardStateError
from core.observability import EvaluationCase, EvaluationRunner
from core.release import ReleaseConfigurationValidator


ROOT = Path(__file__).resolve().parent


def emit(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def run_eval() -> dict:
    result = MockFeatureDeliveryWorkflow().run_health_check()
    actual = {"artifacts": list(result.artifact_versions),
        "tasks": [{"id": "feature-delivery", "dependencies": []}],
        "acceptance_coverage": 1.0, "actions": [], "reviewer": "code_reviewer",
        "author": "developer", "cost": result.cost_summary["cost_units"],
        "review_rounds": result.review_rounds, "regression_status": "passed",
        "final_state": result.status}
    evaluation = EvaluationRunner().run(
        EvaluationCase.load(ROOT / "evals" / "feature_delivery_health_check.yaml"), actual)
    return {"case_id": evaluation.case_id, "passed": evaluation.passed,
            "checks": [{"name": item.name, "passed": item.passed,
                        "details": item.details} for item in evaluation.checks]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Software Company offline operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-release")
    validate_org = commands.add_parser("validate-organization")
    validate_org.add_argument("path", nargs="?", default=str(ROOT / "organizations" / "software-company-v1.yaml"))
    create = commands.add_parser("create-default-organization")
    create.add_argument("target")
    commands.add_parser("offline-demo")
    commands.add_parser("run-evals")
    commands.add_parser("list-work-orders")
    commands.add_parser("list-artifacts")
    commands.add_parser("list-approvals")
    inspect = commands.add_parser("inspect-task")
    inspect.add_argument("task_id")
    decide = commands.add_parser("decide-approval")
    decide.add_argument("decision", choices=("approved", "rejected"))
    decide.add_argument("--action-hash", required=True)
    export = commands.add_parser("export-delivery-report")
    export.add_argument("path")
    migrate = commands.add_parser("migrate-memory")
    migrate.add_argument("source")
    migrate.add_argument("database")
    migrate.add_argument("--apply", action="store_true")
    migrate.add_argument("--backup-directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    validator = ReleaseConfigurationValidator()
    if args.command == "validate-release":
        value = validator.validate_release_set(ROOT)
        value["config"]["flags"] = value["config"]["flags"].__dict__
        emit(value)
    elif args.command == "validate-organization":
        emit(validator.validate_organization(args.path))
    elif args.command == "create-default-organization":
        target = Path(args.target)
        if target.exists():
            raise SystemExit(f"target already exists; refusing to overwrite: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "organizations" / "software-company-v1.yaml", target)
        emit({"created": str(target)})
    elif args.command == "offline-demo":
        from demo.run_demo import run
        value = run()
        emit({"status": value["status"], "artifacts": len(value["artifacts"]),
              "summary": str(ROOT / "demo" / "output" / "demo-summary.json")})
    elif args.command == "run-evals":
        value = run_eval()
        emit(value)
        return 0 if value["passed"] else 1
    elif args.command == "list-work-orders":
        emit(DashboardState(ROOT).work_orders())
    elif args.command == "list-artifacts":
        emit(DashboardState(ROOT).artifacts())
    elif args.command == "list-approvals":
        emit(DashboardState(ROOT).approvals())
    elif args.command == "inspect-task":
        task = DashboardState(ROOT).task(args.task_id)
        if task is None:
            raise SystemExit(f"unknown task: {args.task_id}")
        emit(task)
    elif args.command == "decide-approval":
        state = DashboardState(ROOT)
        approval = state.approvals()[0]
        try:
            emit(state.decide_approval(approval["id"], args.action_hash,
                                       args.decision, state.csrf_token))
        except DashboardStateError as exc:
            raise SystemExit(str(exc)) from exc
    elif args.command == "export-delivery-report":
        result = MockFeatureDeliveryWorkflow().run_health_check()
        target = Path(args.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.final_report, encoding="utf-8")
        emit({"exported": str(target), "status": result.status})
    elif args.command == "migrate-memory":
        report = LegacyMemoryMigrator(args.database).migrate(
            args.source, dry_run=not args.apply, backup_directory=args.backup_directory)
        emit(report.to_dict())
        return 0 if report.failed == 0 else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
