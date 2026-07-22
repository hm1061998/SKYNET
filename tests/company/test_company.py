from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from core.agents import AgentFactory
from core.company import (CORE_ROLE_IDS, STAGES, MockFeatureDeliveryWorkflow,
                          OrganizationTemplateLoader, SeparationOfDuties)
from core.domain import AgentKind, SequenceIdGenerator


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class FixedClock:
    def now(self):
        return NOW


class TemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = OrganizationTemplateLoader().load(
            ROOT / "organizations" / "software-company-v1.yaml")

    def test_exactly_seven_core_roles_load_with_required_prompts(self):
        self.assertEqual(len(self.template.roles), 7)
        self.assertEqual({role.id for role in self.template.roles}, set(CORE_ROLE_IDS))
        self.assertTrue(all(role.kind is AgentKind.ROLE and role.mission and role.role_prompt
                            for role in self.template.roles))
        self.assertEqual(len(self.template.role_registry.list()), 7)

    def test_template_contains_required_governance_sections(self):
        self.assertTrue(self.template.departments)
        self.assertTrue(self.template.model_profiles)
        self.assertTrue(self.template.permissions)
        self.assertTrue(self.template.budgets)
        self.assertTrue(self.template.constitution_reference)
        self.assertTrue(self.template.kpis)
        self.assertIn("software_feature_delivery_v1", self.template.workflow_templates)

    def test_temporary_worker_is_reduced_and_expires(self):
        instance = AgentFactory(self.template.full_registry, clock=FixedClock(),
                                ids=SequenceIdGenerator()).create_worker(
            "backend_developer", parent_definition_id="developer", source_task_id="task",
            work_order_id="wo", expires_at=NOW + timedelta(minutes=10), budget_id="budget",
            requested_capabilities={"read_repository", "run_tests"})
        self.assertEqual(instance.parent_definition_id, "developer")
        self.assertEqual(instance.source_task_id, "task")
        self.assertEqual(instance.granted_capabilities, ("read_repository", "run_tests"))

    def test_separation_of_duties(self):
        sod = SeparationOfDuties()
        self.assertFalse(sod.authorize(role_id="developer", action="approve_code",
                                       artifact_author_role="developer"))
        self.assertFalse(sod.authorize(role_id="solution_architect", action="approve_code"))
        self.assertFalse(sod.authorize(role_id="code_reviewer", action="release"))
        self.assertFalse(sod.authorize(role_id="qa_engineer", action="change_acceptance_criteria"))
        self.assertTrue(sod.authorize(role_id="qa_engineer", action="change_acceptance_criteria",
                                      product_manager_approved=True))
        self.assertFalse(sod.authorize(role_id="security_release_officer",
                                       action="deploy_production"))
        self.assertTrue(sod.authorize(role_id="security_release_officer",
                                      action="deploy_production", human_production_approved=True))
        self.assertFalse(sod.authorize(role_id="chief_of_staff", action="alter_policy"))


class WorkflowTests(unittest.TestCase):
    def test_stage_dag_and_revision_limits(self):
        stage_map = {stage.id: stage for stage in STAGES}
        self.assertEqual(len(stage_map), 8)
        self.assertEqual(stage_map["final_approval_delivery"].dependencies,
                         ("qa", "security_release_review"))
        self.assertEqual(stage_map["product_specification"].max_revision_rounds, 2)
        self.assertEqual(stage_map["technical_design"].max_revision_rounds, 2)
        self.assertEqual(stage_map["code_review"].max_revision_rounds, 3)
        self.assertEqual(stage_map["qa"].max_revision_rounds, 3)

    def test_full_offline_health_check_delivery(self):
        workflow = MockFeatureDeliveryWorkflow(clock=FixedClock(), ids=SequenceIdGenerator())
        result = workflow.run_health_check(human_approved=True)
        self.assertEqual(result.status, "completed")
        self.assertTrue(all(status == "completed" for status in result.stage_statuses.values()))
        self.assertEqual(result.review_rounds, 1)
        required = {"product/feature-specification.md", "architecture/technical-design.md",
                    "quality/test-plan.md", "quality/test-report.md",
                    "security/release-risk-report.md", "release/release-checklist.md",
                    "delivery/final-report.md"}
        self.assertTrue(required <= set(result.artifact_versions))
        self.assertIn("human-approved", result.final_report)
        self.assertIn("cost", result.final_report)
        self.assertIn("trace", result.final_report)
        self.assertEqual(result.cost_summary["cost_units"], 0.0)
        patch_versions = workflow.artifacts._versions["ART_000007"]
        self.assertEqual([item.version_number for item in patch_versions], [1, 2])
        self.assertIn(patch_versions[1].content_hash, result.final_report)

    def test_human_approval_blocks_final_delivery(self):
        result = MockFeatureDeliveryWorkflow(clock=FixedClock(),
            ids=SequenceIdGenerator()).run_health_check(human_approved=False)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.stage_statuses["final_approval_delivery"], "blocked")
        self.assertNotIn("delivery/final-report.md", result.artifact_versions)


if __name__ == "__main__":
    unittest.main()
