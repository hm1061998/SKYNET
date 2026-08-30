import os
import tempfile
import time
import unittest
from pathlib import Path

from core import autoinstall
from core.config import Config
from core.llm import LLMResponseError, validate_json
from core.memory import Memory
from core.orchestrator import SkillAgent, _CtxLLM
from core.registry import Registry
from core.registry import normalize_schema
from core.runner import run_skill


class FakeLLM:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.config = Config({"provider": "mock"})

    def complete(self, messages, **kwargs):
        if self.error:
            raise self.error
        return self.value or "ok"

    def complete_json(self, messages, **kwargs):
        if self.error:
            raise self.error
        return self.value


class LLMHardeningTests(unittest.TestCase):
    def test_json_contract_rejects_string_boolean(self):
        with self.assertRaises(LLMResponseError):
            validate_json({"achieved": "false"}, {"achieved": bool})
        self.assertFalse(validate_json({"achieved": False}, {"achieved": bool})["achieved"])

    def test_task_llm_budget_is_hard_limit(self):
        wrapped = _CtxLLM(FakeLLM(), lambda: "", max_calls=2)
        wrapped.complete([])
        wrapped.complete([])
        with self.assertRaisesRegex(RuntimeError, "ngân sách"):
            wrapped.complete([])

    def test_task_llm_deadline_is_enforced(self):
        wrapped = _CtxLLM(FakeLLM(), lambda: "", deadline=time.monotonic() - 1)
        with self.assertRaisesRegex(RuntimeError, "thời gian"):
            wrapped.complete([])

    def test_step_verification_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            agent = SkillAgent(Config({"provider": "mock"}), Memory(root=Path(td)).load())
            agent.llm = FakeLLM(error=RuntimeError("offline"))
            verdict = agent._step_check("step", {"skill": "", "result": "x"}, lambda _: None)
            self.assertFalse(verdict["achieved"])

    def test_artifact_validator_checks_presence_and_size(self):
        with tempfile.TemporaryDirectory() as td:
            agent = SkillAgent(Config({"provider": "mock"}), Memory(root=Path(td) / "mem").load())
            missing = str(Path(td) / "missing.txt")
            self.assertFalse(agent._artifact_check({"params": {"output_path": missing}})["achieved"])
            output = Path(td) / "result.txt"
            output.write_text("done", encoding="utf-8")
            self.assertTrue(agent._artifact_check({"params": {"output_path": str(output)}})["achieved"])

    def test_registry_discovery_does_not_execute_top_level_code(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = root / "executed.txt"
            skill = root / "unsafe.py"
            skill.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('bad')\n"
                "SKILL_META={'name':'safe_meta','description':'x','params':{}}\n"
                "def run(**kwargs): return {'success': True}\n",
                encoding="utf-8",
            )
            registry = Registry(root).load()
            self.assertIn("safe_meta", registry.skills)
            self.assertFalse(marker.exists())

    def test_file_skill_runs_in_child_process(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "echo.py"
            path.write_text(
                "SKILL_META={'name':'echo','description':'x','params':{}}\n"
                "def run(**kwargs): return {'success': True, 'result': kwargs.get('text')}\n",
                encoding="utf-8",
            )
            result = run_skill({"path": path, "run": None}, {"text": "hello"})
            self.assertTrue(result["success"])
            self.assertEqual(result["result"], "hello")

    def test_auto_install_is_opt_in(self):
        old = os.environ.pop("AGENT_ALLOW_AUTO_INSTALL", None)
        try:
            self.assertFalse(autoinstall.enabled())
            os.environ["AGENT_ALLOW_AUTO_INSTALL"] = "1"
            self.assertTrue(autoinstall.enabled())
        finally:
            if old is None:
                os.environ.pop("AGENT_ALLOW_AUTO_INSTALL", None)
            else:
                os.environ["AGENT_ALLOW_AUTO_INSTALL"] = old

    def test_verify_role_inherits_work_configuration(self):
        cfg = Config({"roles": {"work": {"provider": "mock", "model": "worker"}}})
        verify = cfg.resolve("verify")
        self.assertEqual(verify.provider, "mock")
        self.assertEqual(verify.model, "worker")

    def test_openai_parameter_schema_is_normalized(self):
        schema = normalize_schema({
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        })
        self.assertTrue(schema["path"]["required"])


if __name__ == "__main__":
    unittest.main()
