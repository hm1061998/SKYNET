from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.generator import GeneratorError, generate, validate_generated_source


class GeneratedSkillBoundaryTests(unittest.TestCase):
    def test_module_level_call_is_rejected_before_file_write_or_exec(self):
        marker = Path(tempfile.gettempdir()) / "javis-phase13-must-not-exist.txt"
        if marker.exists():
            marker.unlink()
        code = f'''SKILL_META = {{"name": "malicious_phase13", "description": "fixture", "params": {{}}}}
open({str(marker)!r}, "w").write("executed")
def run(**kwargs):
    return {{"success": True}}
'''

        class Provider:
            def complete(self, *args, **kwargs):
                return "===PARAMS===\n{}\n===CODE===\n```python\n" + code + "\n```"

        with patch("core.generator.SKILLS_DIR", Path(tempfile.gettempdir()) / "javis-phase13-skills"):
            with self.assertRaisesRegex(GeneratorError, "forbidden module-level"):
                generate("malicious fixture", Provider(), attempts=1)
        self.assertFalse(marker.exists())

    def test_definition_time_call_and_top_level_import_are_rejected(self):
        with self.assertRaisesRegex(GeneratorError, "execute calls"):
            validate_generated_source('SKILL_META={"name":"x"}\ndef run(value=__import__("os")):\n return {}')
        with self.assertRaisesRegex(GeneratorError, "Import"):
            validate_generated_source('import os\nSKILL_META={"name":"x"}\ndef run(**kwargs):\n return {}')
        with self.assertRaisesRegex(GeneratorError, "simple names"):
            validate_generated_source('SKILL_META={"name":"x"}\nglobals()["loaded"]=True\ndef run(**kwargs):\n return {}')

    def test_literal_metadata_and_lazy_import_inside_run_are_allowed(self):
        validate_generated_source('''SKILL_META={"name":"safe","description":"fixture","params":{}}
def helper(value: str) -> str:
    return value
def run(**kwargs) -> dict:
    import pathlib
    return {"success": True}
''')


if __name__ == "__main__":
    unittest.main()
