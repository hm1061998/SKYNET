from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from core.company import MockFeatureDeliveryWorkflow
from core.dashboard import DashboardState
from core.domain import BudgetUsage, RiskLevel, SequenceIdGenerator, TaskStatus, WorkOrderStatus
from core.governance import ActionRequest, Constitution, PolicyEngine, PolicyRule, PolicyEffect, RedactionService
from core.persistence import SQLiteStore
from core.registry import Registry
from core.runner import run_skill
from core.work import DispatchResult, DispatchStatus, LegacyPipelineAdapter, TaskDispatcher, TaskScheduler
from tests.fixtures.support import FakeClock, INJECTION_SAMPLES
from tests.work.test_workflow import make_budget, make_task, make_work_order, setup_memory, context


ROOT = Path(__file__).resolve().parents[2]


class Phase11EndToEndTests(unittest.TestCase):
    def test_01_legacy_resize_like_skill_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "resize_fixture.py"
            skill.write_text("SKILL_META={'name':'resize_fixture','description':'resize image photo','tags':['resize'],'params':{'width':{'type':'int','required':True}}}\ndef run(width): return {'success': True, 'width': width}\n", encoding="utf-8")
            registry = Registry(Path(directory)).load()
            name = registry.find("resize image width 800")
            params = registry.extract_params("resize image width 800", name)
            self.assertEqual(run_skill(registry.get(name), params)["width"], 800)

    def test_02_legacy_multi_step_pipeline(self):
        graph = LegacyPipelineAdapter(FakeClock(), SequenceIdGenerator()).to_graph(
            "wo", ["inspect", "resize", "verify"])
        self.assertEqual(graph.dependencies_of(graph.tasks[2].id), (graph.tasks[1].id,))

    def test_03_new_feature_delivery_happy_path(self):
        result = MockFeatureDeliveryWorkflow(clock=FakeClock(), ids=SequenceIdGenerator()).run_health_check()
        self.assertEqual(result.status, "completed")
        self.assertIn("delivery/final-report.md", result.artifact_versions)

    def test_04_review_requests_changes_once(self):
        result = MockFeatureDeliveryWorkflow(clock=FakeClock(), ids=SequenceIdGenerator()).run_health_check()
        self.assertEqual(result.review_rounds, 1)
        self.assertTrue(any("changes_requested" in item for item in result.trace))

    def test_05_qa_failure_followed_by_repair(self):
        result = MockFeatureDeliveryWorkflow(clock=FakeClock(), ids=SequenceIdGenerator()).run_health_check(qa_fail_once=True)
        self.assertEqual(result.status, "completed")
        self.assertIn("qa:failed:repair_requested", result.trace)
        self.assertIn("qa:repair_completed", result.trace)

    def test_06_budget_exhaustion(self):
        task = make_task("a", tokens=10)
        repositories = setup_memory(make_work_order(("a",)), (task,),
            replace(make_budget(10), usage=BudgetUsage(tokens=5)))
        scheduler = TaskScheduler(repositories.work_orders, repositories.tasks, repositories.budgets,
            TaskDispatcher(lambda task, token: DispatchResult(DispatchStatus.COMPLETED, "done")))
        result = scheduler.tick("wo", context())
        self.assertEqual(result.dispatched_task_ids, ())
        self.assertEqual(repositories.tasks.get("a").status, TaskStatus.BLOCKED)

    def test_07_policy_denial(self):
        constitution = Constitution("v1", ("deny by default",), ())
        request = ActionRequest("req", "change_permissions", {}, "agent", "org", "wo", "task", "v1", RiskLevel.HIGH)
        self.assertFalse(PolicyEngine(constitution).decide(request).allowed)

    def test_08_human_approval_rejection(self):
        state = DashboardState(ROOT)
        approval = state.approvals()[0]
        result = state.decide_approval(approval["id"], approval["action_hash"], "rejected", state.csrf_token)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(state.approvals()[0]["status"], "rejected")

    def test_09_process_restart_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.db"
            with SQLiteStore(path) as store:
                store.repository("work_orders", type(make_work_order(("a",)))).add(make_work_order(("a", "b")))
                store.repository("tasks", type(make_task("a"))).add(make_task("a"))
                store.repository("tasks", type(make_task("a"))).add(make_task("b", dependencies=("a",)))
                store.repository("budgets", type(make_budget())).add(make_budget())
                TaskScheduler(store.repository("work_orders", type(make_work_order(("a",)))),
                    store.repository("tasks", type(make_task("a"))), store.repository("budgets", type(make_budget())),
                    TaskDispatcher(lambda task, token: DispatchResult(DispatchStatus.COMPLETED, "done"))).tick("wo", context(max_parallelism=1))
            with SQLiteStore(path) as store:
                result = TaskScheduler(store.repository("work_orders", type(make_work_order(("a",)))),
                    store.repository("tasks", type(make_task("a"))), store.repository("budgets", type(make_budget())),
                    TaskDispatcher(lambda task, token: DispatchResult(DispatchStatus.COMPLETED, "done"))).tick("wo", context(max_parallelism=1))
                self.assertEqual(result.dispatched_task_ids, ("b",))
                self.assertEqual(result.work_order.status, WorkOrderStatus.COMPLETED)

    def test_10_malicious_content_cannot_escalate_privilege(self):
        redactor = RedactionService()
        constitution = Constitution("v1", ("deny by default",), (PolicyRule("read_repository", PolicyEffect.ALLOW),))
        for index, content in enumerate(INJECTION_SAMPLES):
            request = ActionRequest(f"req-{index}", "change_permissions", {"content": content},
                "agent", "org", "wo", "task", "v1", RiskLevel.HIGH)
            self.assertFalse(PolicyEngine(constitution).decide(request).allowed)
        self.assertNotIn("fixture-secret", redactor.redact("API_KEY=fixture-secret"))


if __name__ == "__main__":
    unittest.main()
