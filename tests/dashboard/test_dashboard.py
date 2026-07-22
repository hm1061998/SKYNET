from pathlib import Path
import tempfile
import unittest

from core.dashboard import DashboardState, DashboardStateError


ROOT = Path(__file__).resolve().parents[2]


class DashboardContractTests(unittest.TestCase):
    def setUp(self):
        self.state = DashboardState(ROOT)

    def test_required_api_projection_contracts(self):
        self.assertEqual(len(self.state.organizations()), 1)
        work_order = self.state.work_orders()[0]
        self.assertEqual(self.state.work_order(work_order["id"])["id"], work_order["id"])
        self.assertEqual(len(self.state.tasks(work_order["id"])), 8)
        self.assertIsNotNone(self.state.task("task-code_review"))
        self.assertEqual(len([item for item in self.state.agents() if item["kind"] == "role"]), 7)
        topology = self.state.topology()
        self.assertTrue(topology["nodes"])
        self.assertTrue(topology["edges"])
        self.assertIn("assigned_to", {item["kind"] for item in topology["edges"]})
        self.assertIn("depends_on", {item["kind"] for item in topology["edges"]})
        self.assertTrue(self.state.artifacts())
        self.assertTrue(self.state.approvals())
        self.assertTrue(self.state.events())
        self.assertIn("work_orders", self.state.metrics())
        self.assertIn("completion_rate", self.state.metrics()["work_orders"]["wo-health-check"])
        traces = self.state.trace_summaries()
        self.assertTrue(traces)
        self.assertNotIn("prompt", str(traces).lower())
        self.assertNotIn("chain_of_thought", str(traces).lower())

    def test_approval_requires_id_hash_and_csrf(self):
        approval = self.state.approvals()[0]
        with self.assertRaises(DashboardStateError):
            self.state.decide_approval(approval["id"], "wrong", "approved", self.state.csrf_token)
        with self.assertRaises(DashboardStateError):
            self.state.decide_approval(approval["id"], approval["action_hash"], "approved", "wrong")
        result = self.state.decide_approval(approval["id"], approval["action_hash"],
                                            "approved", self.state.csrf_token)
        self.assertEqual(result["status"], "approved")

    def test_task_state_and_empty_state(self):
        waiting = self.state.task("task-final_approval_delivery")
        self.assertEqual(waiting["status"], "waiting_approval")
        self.assertTrue(waiting["blocked_reason"])
        self.assertEqual(self.state.tasks("unknown"), [])
        self.assertIsNone(self.state.work_order("unknown"))

    def test_configuration_is_redacted_and_read_only(self):
        value = self.state.configuration()
        self.assertTrue(value["read_only"])
        rendered = str(value).lower()
        self.assertNotIn("api_key", rendered)
        self.assertNotIn("password", rendered)


class DashboardSourceSmokeTests(unittest.TestCase):
    def test_xss_fixture_has_no_raw_html_execution_sink(self):
        component = (ROOT / "src" / "OrganizationDashboard.jsx").read_text(encoding="utf-8")
        graph = (ROOT / "src" / "LiveOrganizationGraph.jsx").read_text(encoding="utf-8")
        fixture = '<img src=x onerror="fetch(\'/secrets\')"><script>alert(1)</script>'
        self.assertNotIn("dangerouslySetInnerHTML", component)
        self.assertNotIn(".innerHTML", component)
        self.assertNotIn(fixture, component)
        self.assertNotIn("dangerouslySetInnerHTML", graph)

    def test_legacy_and_organization_dashboard_smoke(self):
        app = (ROOT / "src" / "App.jsx").read_text(encoding="utf-8")
        organization = (ROOT / "src" / "OrganizationDashboard.jsx").read_text(encoding="utf-8")
        self.assertIn("ConversationPanel", app)
        self.assertIn("OrganizationDashboard", app)
        self.assertIn("Open legacy chat", organization)
        self.assertIn("No active Work Order", organization)
        self.assertIn("Could not load organization state", organization)
        self.assertIn("LiveOrganizationGraph", organization)
        self.assertIn("Living AI Organization", organization)

    def test_live_graph_exposes_operational_interactions(self):
        graph = (ROOT / "src" / "LiveOrganizationGraph.jsx").read_text(encoding="utf-8")
        self.assertIn("Graph filters", graph)
        self.assertIn("Open task details", graph)
        self.assertIn("aria-live", graph)
        self.assertIn("onKeyDown", graph)

    def test_server_keeps_legacy_and_v1_routes(self):
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        for route in ("/api/message", "/api/approve", "/api/v1/organizations",
                      "/api/v1/work-orders", "/api/v1/agents", "/api/v1/artifacts",
                      "/api/v1/approvals", "/api/v1/events", "/api/v1/metrics",
                      "/api/v1/topology"):
            self.assertIn(route, server)
        self.assertIn("/api/v1/traces", server)


if __name__ == "__main__":
    unittest.main()
