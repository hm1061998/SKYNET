"""Chạy skill an toàn: gọi run(**params), bắt lỗi và chuẩn hoá kết quả về dict."""
from __future__ import annotations
import io
import traceback
from contextlib import redirect_stdout


def run_skill(entry: dict, params: dict) -> dict:
    """entry = mục trong Registry.skills; params = tham số đã rút.

    Trả về dict luôn có khoá "success" (bool). Khi skill NÉM exception (lỗi code) ->
    {"success": False, "error": <traceback>, "_crashed": True}. Còn khi skill tự trả
    {"success": False, "error": ...} (lỗi dữ liệu/đầu vào) thì KHÔNG có "_crashed".
    """
    run = entry["run"]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            result = run(**params)
    except Exception:
        return {"success": False, "error": traceback.format_exc(limit=6).strip(),
                "_crashed": True, "stdout": buf.getvalue()}

    if not isinstance(result, dict):
        result = {"success": True, "result": result}
    result.setdefault("success", True)
    out = buf.getvalue()
    if out:
        result.setdefault("stdout", out)
    return result
