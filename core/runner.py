"""Chạy skill an toàn: gọi run(**params), bắt lỗi và chuẩn hoá kết quả về dict."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import traceback


def run_skill(entry: dict, params: dict) -> dict:
    """entry = mục trong Registry.skills; params = tham số đã rút.

    Trả về dict luôn có khoá "success" (bool). Khi skill NÉM exception (lỗi code) ->
    {"success": False, "error": <traceback>, "_crashed": True}. Còn khi skill tự trả
    {"success": False, "error": ...} (lỗi dữ liệu/đầu vào) thì KHÔNG có "_crashed".
    """
    path = entry.get("path")
    if path:
        timeout = max(1, int(os.environ.get("AGENT_SKILL_TIMEOUT", "300")))
        request = json.dumps({"path": str(path), "params": params}, ensure_ascii=False, default=str)
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "core.skill_worker"],
                input=request,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=os.getcwd(),
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Skill vượt quá timeout {timeout}s", "_crashed": True}
        except Exception:
            return {"success": False, "error": traceback.format_exc(limit=6).strip(), "_crashed": True}
        try:
            result = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            return {
                "success": False,
                "error": f"Skill worker trả dữ liệu không hợp lệ: {(proc.stderr or proc.stdout)[:500]}",
                "_crashed": True,
            }
        if proc.returncode != 0 and result.get("success", True):
            return {"success": False, "error": (proc.stderr or "Skill worker lỗi")[:1000], "_crashed": True}
        return result

    # Compatibility path for in-memory entries used by tests/embedders.
    run = entry["run"]
    try:
        result = run(**params)
    except Exception:
        return {"success": False, "error": traceback.format_exc(limit=6).strip(),
                "_crashed": True}

    if not isinstance(result, dict):
        result = {"success": True, "result": result}
    result.setdefault("success", True)
    return result
