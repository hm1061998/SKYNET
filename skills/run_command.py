"""Skill builtin: chạy một lệnh shell / cmd và trả về kết quả.

Cho phép Javis thực thi lệnh dòng lệnh (Windows: cmd; Linux/macOS: sh) — ví dụ
'dir', 'ipconfig', 'python --version', 'git status'... Chỉ dùng thư viện chuẩn.

An toàn cơ bản: có timeout, bắt lỗi, và chặn vài lệnh phá huỷ rõ ràng. Vì đây là
agent chạy trên máy của chính người dùng nên lệnh được thực thi theo yêu cầu.
"""

SKILL_META = {
    "name": "run_command",
    "description": ("Chạy một lệnh dòng lệnh (cmd/terminal/shell) trên máy và trả về "
                    "output. Ví dụ: 'dir', 'ipconfig', 'git status', 'python --version'."),
    "tags": ["cmd", "command", "lenh", "chay-lenh", "terminal", "shell", "console",
             "bash", "powershell", "run", "run_command", "thuc-thi-lenh"],
    "params": {
        "command": {"type": "str", "description": "Lệnh cần chạy", "required": True},
        "cwd": {"type": "str", "description": "Thư mục làm việc (tuỳ chọn)", "required": False},
        "timeout": {"type": "int", "description": "Giới hạn thời gian (giây)",
                    "required": False, "default": 60},
    },
}

# Vài mẫu lệnh phá huỷ hiển nhiên -> chặn để tránh tai nạn.
_BLOCK = (
    "rm -rf /", "rm -rf /*", ":(){:|:&};:", "mkfs", "dd if=", "> /dev/sda",
    "format c:", "del /f /s /q c:\\", "rd /s /q c:\\", "deltree",
)


def run(**kwargs) -> dict:
    import subprocess

    command = str(kwargs.get("command") or "").strip()
    if not command:
        return {"success": False, "error": "Thiếu tham số 'command'."}

    low = command.lower().replace(" ", "")
    if any(b.replace(" ", "") in low for b in _BLOCK):
        return {"success": False,
                "error": f"Lệnh bị chặn vì có thể phá huỷ hệ thống: {command}"}

    cwd = kwargs.get("cwd") or None
    try:
        timeout = int(kwargs.get("timeout", 60))
    except (TypeError, ValueError):
        timeout = 60

    try:
        proc = subprocess.run(
            command, shell=True, cwd=cwd, timeout=timeout,
            capture_output=True, text=True, errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Lệnh chạy quá {timeout}s và đã bị dừng."}
    except Exception as e:
        return {"success": False, "error": f"Không chạy được lệnh: {e}"}

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    ok = proc.returncode == 0

    body = out if out else "(không có output)"
    if err:
        body += ("\n[stderr]\n" + err)

    return {
        "success": ok,
        "result": f"$ {command}\n(returncode={proc.returncode})\n{body}",
        "error": None if ok else (err or f"returncode={proc.returncode}"),
        "data": {"returncode": proc.returncode, "stdout": out, "stderr": err},
    }
