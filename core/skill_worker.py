"""Isolated child-process entrypoint for executing one skill.

This is process isolation, not an OS security boundary. It prevents generated
skills from crashing or hanging the long-lived agent process and gives the
parent a hard timeout. Filesystem/network permissions still come from the OS
account running the agent.
"""
from __future__ import annotations

import io
import json
import sys
import traceback
import types
from contextlib import redirect_stdout
from pathlib import Path


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
        path = Path(request["path"]).resolve()
        params = request.get("params") or {}
        output = io.StringIO()
        with redirect_stdout(output):
            source = path.read_text(encoding="utf-8")
            module = types.ModuleType(f"isolated_skill_{path.stem}")
            module.__file__ = str(path)
            exec(compile(source, str(path), "exec"), module.__dict__)
            run = getattr(module, "run", None)
            if not callable(run):
                raise RuntimeError("Skill không có hàm run(**kwargs)")
            result = run(**params)
        if not isinstance(result, dict):
            result = {"success": True, "result": result}
        result.setdefault("success", True)
        if output.getvalue():
            result.setdefault("stdout", output.getvalue())
    except Exception:
        result = {
            "success": False,
            "error": traceback.format_exc(limit=8).strip(),
            "_crashed": True,
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
