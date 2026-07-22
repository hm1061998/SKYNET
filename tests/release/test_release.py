import json
import tempfile
from pathlib import Path
import unittest

from company_cli import main as company_main
from core.dashboard import DashboardState, DashboardStateError
from core.release import ConfigurationValidationError, ReleaseConfigurationValidator
from demo.run_demo import run


ROOT = Path(__file__).resolve().parents[2]


class ConfigurationReleaseTests(unittest.TestCase):
    def test_release_configuration_set_is_valid_and_secret_free(self):
        validated = ReleaseConfigurationValidator().validate_release_set(ROOT)
        self.assertEqual(validated["organization"]["roles"], 7)
        self.assertEqual(validated["constitution_version"], "1")
        self.assertIn("balanced_reasoning", validated["model_profiles"])
        for path in (ROOT / "config.example.json", ROOT / "model-profiles.example.yaml",
                     ROOT / "policies" / "default-constitution-v1.yaml"):
            text = path.read_text(encoding="utf-8").lower()
            self.assertNotIn('"api_key":', text)
            self.assertNotIn("sk-", text)
            self.assertNotIn("password", text)

    def test_configuration_errors_are_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "config.json"
            invalid.write_text('{"execution":{"mode":"legacy_unsafe"}}', encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationValidationError, "explicit allow flag"):
                ReleaseConfigurationValidator().validate_config(invalid)

    def test_cli_validation_eval_and_inspection_commands(self):
        self.assertEqual(company_main(["validate-release"]), 0)
        self.assertEqual(company_main(["run-evals"]), 0)
        self.assertEqual(company_main(["inspect-task", "task-code_review"]), 0)
        self.assertEqual(company_main(["list-artifacts"]), 0)
        self.assertEqual(company_main(["list-approvals"]), 0)


class IntegrationBoundaryTests(unittest.TestCase):
    def test_ui_boundary_uses_dashboard_application_state(self):
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        ui = (ROOT / "src" / "OrganizationDashboard.jsx").read_text(encoding="utf-8")
        self.assertIn("DashboardState", server)
        self.assertNotIn("core.repositories", server)
        self.assertNotIn("run_skill", server)
        self.assertNotIn("sqlite", ui.lower())

    def test_approval_hash_binds_exact_action(self):
        state = DashboardState(ROOT)
        approval = state.approvals()[0]
        with self.assertRaises(DashboardStateError):
            state.decide_approval(approval["id"], approval["action_hash"] + "tampered",
                                  "approved", state.csrf_token)

    def test_legacy_adapters_remain_isolated_from_company_workflow(self):
        legacy = (ROOT / "core" / "compatibility" / "legacy.py").read_text(encoding="utf-8")
        company = (ROOT / "core" / "company" / "workflow.py").read_text(encoding="utf-8")
        self.assertNotIn("core.company", legacy)
        self.assertNotIn("core.compatibility", company)

    def test_dashboard_artifact_provenance_maps_to_accountable_stage(self):
        artifacts = {item["path"]: item for item in DashboardState(ROOT).artifacts()}
        self.assertEqual(artifacts["review/code-review.md"]["source_task"], "task-code_review")
        self.assertEqual(artifacts["security/release-risk-report.md"]["source_task"],
                         "task-security_release_review")
        self.assertEqual(artifacts["delivery/final-report.md"]["source_task"],
                         "task-final_approval_delivery")


class OfflineDemoAcceptanceTests(unittest.TestCase):
    def test_fresh_offline_demo_exports_complete_inspectable_package(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture_before = (ROOT / "demo" / "fixture_repository" / "health_service.py").read_bytes()
            summary = run(directory)
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(len(summary["task_dag"]), 8)
            self.assertGreaterEqual(len(summary["artifacts"]), 11)
            self.assertEqual(summary["approval"], {"simulated": True, "decision": "approved"})
            self.assertTrue(summary["audit"]["hash_chain_valid"])
            self.assertEqual(summary["audit"]["correlation_id"], summary["trace"]["goal_id"])
            self.assertEqual(summary["trace"]["span_count"], 8)
            self.assertEqual(summary["cost"]["cost_units"], 0.0)
            self.assertEqual(summary["offline_guarantees"],
                {"network_calls": 0, "host_installs": 0, "paid_credentials_required": False})
            self.assertTrue(Path(directory, "delivery", "final-report.md").is_file())
            self.assertTrue(Path(directory, "demo-summary.json").is_file())
            self.assertEqual((ROOT / "demo" / "fixture_repository" / "health_service.py").read_bytes(), fixture_before)

    def test_performance_sanity_is_bounded_and_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            performance = run(directory)["performance"]
            self.assertLess(performance["startup_and_workflow_ms"], 5000)
            self.assertEqual(performance["database_operations"], 0)
            self.assertEqual(performance["scheduler_stages"], 8)
            self.assertLessEqual(performance["artifact_count"], 20)
            self.assertLessEqual(performance["trace_event_count"], 40)
            self.assertLessEqual(performance["estimated_memory_records"], 64)

    def test_demo_summary_contains_no_private_reasoning_or_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            rendered = json.dumps(run(directory)).lower()
            self.assertNotIn("chain_of_thought", rendered)
            self.assertNotIn("api_key", rendered)
            self.assertNotIn("password", rendered)


if __name__ == "__main__":
    unittest.main()
