#!/usr/bin/env python3
"""Dashboard web cho Agent — chỉ dùng thư viện chuẩn (http.server), không cần Flask.

    python server.py            # mở http://127.0.0.1:8765

- Đọc lại config.json MỖI request -> đổi API key xong chỉ cần tải lại trang, khỏi khởi động lại.
- Tự NẠP LẠI CODE khi core/*.py thay đổi (dev auto-reload) — đặt AGENT_NO_RELOAD=1 để tắt.
- In trạng thái key lúc khởi động; cảnh báo nếu cổng đã bị server cũ chiếm.
"""
import glob
import importlib
import json
import os
import sys
import threading
import uuid
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import core                                    # noqa: E402
from core import CONFIG_PATH, PLANS_DIR, PROJECT_ROOT       # noqa: E402
from core.identity import get_agent_name                    # noqa: E402
from core import config as cfg_mod             # noqa: E402
from core import llm as llm_mod                # noqa: E402
from core import runner as runner_mod          # noqa: E402
from core import registry as reg_mod           # noqa: E402
from core import generator as gen_mod          # noqa: E402
from core import memory as mem_mod             # noqa: E402
from core import planner as plan_mod           # noqa: E402
from core import tools as tools_mod            # noqa: E402
from core import orchestrator as orch_mod      # noqa: E402
from core.config import Config                 # noqa: E402
from core.orchestrator import SkillAgent       # noqa: E402

DASHBOARD_DIR = PROJECT_ROOT / "dashboard" / "dist"
DASHBOARD = DASHBOARD_DIR / "index.html"
AGENT_IDENTITY_PATH = PROJECT_ROOT / "agent.config.json"
AGENT: SkillAgent | None = None


def agent_name() -> str:
    return get_agent_name()

# ---- job nền: task chạy trong thread, UI poll log — không còn dính timeout trình duyệt ----
JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()

MODEL_CATALOG = {
    "openai": ["gpt-4o-mini", "gpt-4o", "o3-mini"],
    "anthropic": ["claude-sonnet-4-5", "claude-haiku-4-5"],
    "gemini": ["gemini-2.0-flash", "gemini-2.5-pro"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "local": ["deepseek-r1", "qwen2.5", "mistral", "gemma3"],
    "mock": ["mock-1"],
}


def _start_job(agent: SkillAgent, task: str, steps=None) -> str:
    jid = uuid.uuid4().hex[:12]
    job = {"status": "running", "task": task, "logs": [], "result": None}
    with _JOBS_LOCK:
        JOBS[jid] = job
        # dọn job cũ đã xong (giữ tối đa 20)
        done = [k for k, v in JOBS.items() if v["status"] != "running"]
        for k in done[:-20]:
            JOBS.pop(k, None)

    def _run():
        def _cb(msg: str):
            with _JOBS_LOCK:
                job["logs"].append(msg)
        try:
            res = agent.execute_task(task, log=_cb, steps=steps)
        except Exception as e:
            res = {"success": False, "error": str(e), "logs": job["logs"]}
        with _JOBS_LOCK:
            job["result"] = res
            job["status"] = "done"

    threading.Thread(target=_run, daemon=True).start()
    return jid

# ---- dev auto-reload: nạp lại code khi core/*.py thay đổi (khỏi phải restart) ----
_CODE_MTIME = 0.0
_RELOAD_ORDER = [core, cfg_mod, llm_mod, runner_mod, reg_mod, gen_mod,
                 mem_mod, plan_mod, tools_mod, orch_mod]


def _core_mtime() -> float:
    paths = glob.glob(os.path.join(str(PROJECT_ROOT), "core", "*.py"))
    return max((os.path.getmtime(p) for p in paths), default=0.0)


def maybe_reload_code():
    """Nếu code trong core/ đã đổi, nạp lại module + tạo lại agent (giữ bộ nhớ trên đĩa)."""
    global AGENT, _CODE_MTIME
    if os.environ.get("AGENT_NO_RELOAD") == "1":
        return
    try:
        mt = _core_mtime()
    except Exception:
        return
    if mt <= _CODE_MTIME:
        return
    try:
        for m in _RELOAD_ORDER:
            importlib.reload(m)
        AGENT = orch_mod.SkillAgent(cfg_mod.Config.load())
        print("[reload] Đã nạp lại code (core/*.py thay đổi).")
    except (Exception, SystemExit) as e:
        # config.json/skill đang sửa dở -> giữ agent cũ, thử lại ở lần đổi kế tiếp
        print(f"[reload] Bỏ qua vì lỗi khi nạp lại: {e}")
    finally:
        _CODE_MTIME = mt   # tránh thử lại liên tục khi lỗi kéo dài


TTS_RATE = "+30%"   # tốc độ đọc: "+0%" chuẩn, "+18%" nhanh vừa, "+30%" nhanh


def _tts_bytes(text: str, voice: str = "vi-VN-HoaiMyNeural", rate: str | None = None) -> bytes:
    """Sinh giọng nói tiếng Việt (mp3) bằng edge-tts — miễn phí, chạy được mọi trình duyệt."""
    from core import autoinstall
    try:
        import edge_tts
    except ImportError:
        if not autoinstall.pip_install("edge-tts", log=print):
            raise RuntimeError("Không cài được edge-tts (cần mạng).")
        import edge_tts
    import asyncio

    async def _gen() -> bytes:
        buf = b""
        async for chunk in edge_tts.Communicate(text, voice, rate=rate or TTS_RATE).stream():
            if chunk["type"] == "audio":
                buf += chunk["data"]
        return buf

    return asyncio.run(_gen())


def refresh_config():
    """Nạp lại config.json từ đĩa để cập nhật provider/API key mà không cần restart."""
    try:
        AGENT.config = type(AGENT.config).load()
        AGENT.llm.config = AGENT.config
    except SystemExit:
        pass  # config.json lỗi cú pháp -> giữ config cũ


def key_status() -> str:
    parts = []
    for role in ("chat", "work"):
        rc = AGENT.config.resolve(role)
        if rc.is_mock:
            s = "mock"
        elif rc.is_local:
            s = "local"
        elif rc.api_key:
            s = "key …" + rc.api_key[-4:]
        else:
            s = "THIẾU KEY"
        parts.append(f"{role}={rc.provider}:{rc.model} [{s}]")
    return " | ".join(parts)


def model_config_payload() -> dict:
    roles = {}
    for role in ("chat", "work"):
        resolved = AGENT.config.resolve(role)
        roles[role] = {"provider": resolved.provider, "model": resolved.model,
                       "base_url": resolved.base_url or "", "ready": resolved.ready}
    return {"roles": roles, "catalog": MODEL_CATALOG}


def save_model_config(roles: dict) -> dict:
    allowed_roles = {"chat", "work"}
    if not isinstance(roles, dict) or not roles or set(roles) - allowed_roles:
        raise ValueError("Cấu hình role không hợp lệ")
    current = Config.load(CONFIG_PATH).data
    stored_roles = current.setdefault("roles", {})
    for role, value in roles.items():
        if not isinstance(value, dict):
            raise ValueError(f"Cấu hình {role} không hợp lệ")
        provider = str(value.get("provider") or "").strip().lower()
        model = str(value.get("model") or "").strip()
        if provider not in MODEL_CATALOG:
            raise ValueError(f"Provider không hỗ trợ: {provider}")
        if not model or len(model) > 120 or any(ch in model for ch in "\r\n\0"):
            raise ValueError(f"Tên model cho {role} không hợp lệ")
        saved_role = {"provider": provider, "model": model}
        if provider == "local":
            base_url = str(value.get("base_url") or "http://127.0.0.1:11434/v1").strip().rstrip("/")
            if len(base_url) > 300 or not base_url.startswith(("http://", "https://")):
                raise ValueError(f"Endpoint local cho {role} không hợp lệ")
            saved_role["base_url"] = base_url
        stored_roles[role] = saved_role
    temp_path = CONFIG_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, CONFIG_PATH)
    AGENT.config = Config.load(CONFIG_PATH)
    AGENT.llm.config = AGENT.config
    return model_config_payload()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, ctype="text/html; charset=utf-8"):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self._json({"error": "not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._file(DASHBOARD)
        if self.path == "/api/health":
            maybe_reload_code()
            refresh_config()
            return self._json({"config": AGENT.config.describe(),
                               "keys": key_status(),
                               "skills": AGENT.registry.load().names()})
        if self.path == "/api/model-config":
            refresh_config()
            return self._json(model_config_payload())
        if self.path.startswith("/plans/"):
            name = os.path.basename(self.path[len("/plans/"):])
            return self._file(PLANS_DIR / name)
        # Static assets generated by the React/Vite build. Resolve the path
        # beneath dist so request paths cannot escape the dashboard directory.
        if not self.path.startswith("/api/"):
            rel = urlparse(self.path).path.lstrip("/")
            candidate = (DASHBOARD_DIR / rel).resolve()
            try:
                candidate.relative_to(DASHBOARD_DIR.resolve())
            except ValueError:
                return self._json({"error": "not found"}, 404)
            if candidate.is_file():
                ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                    ctype += "; charset=utf-8"
                return self._file(candidate, ctype)
        if self.path == "/api/tts-check":
            # tự chẩn đoán TTS: mở http://127.0.0.1:8765/api/tts-check trên trình duyệt
            try:
                audio = _tts_bytes("Xin chào, em là Hoài My.")
                return self._json({"ok": True, "engine": "edge-tts",
                                   "voice": "vi-VN-HoaiMyNeural", "bytes": len(audio)})
            except Exception as e:
                print(f"[tts] LỖI: {e}")
                return self._json({"ok": False, "error": str(e)})
        if self.path.startswith("/api/job"):
            q = parse_qs(urlparse(self.path).query)
            jid = (q.get("id") or [""])[0]
            start = int((q.get("from") or ["0"])[0] or 0)
            with _JOBS_LOCK:
                job = JOBS.get(jid)
                if not job:
                    return self._json({"error": "job not found"}, 404)
                return self._json({"status": job["status"],
                                   "logs": job["logs"][start:],
                                   "total": len(job["logs"]),
                                   "result": job["result"] if job["status"] == "done" else None})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        maybe_reload_code()                  # nạp lại code nếu core/ đổi
        refresh_config()                     # luôn dùng config mới nhất
        body = self._body()
        if self.path == "/api/message":
            text = (body.get("text") or "").strip()
            if not text:
                return self._json({"error": "empty"}, 400)
            try:
                return self._json(AGENT.handle_message(text))
            except Exception as e:
                return self._json({"mode": "chat", "reply": f"Lỗi: {e}"})
        if self.path == "/api/model-config":
            try:
                return self._json({"ok": True, **save_model_config(body.get("roles"))})
            except (ValueError, OSError) as e:
                return self._json({"ok": False, "error": str(e)}, 400)
        if self.path == "/api/approve":
            task = (body.get("task") or "").strip()
            steps = body.get("steps") if isinstance(body.get("steps"), list) else None
            try:
                return self._json({"job": _start_job(AGENT, task, steps)})
            except Exception as e:
                return self._json({"success": False, "error": str(e), "logs": [f"[✗] {e}"]})
        if self.path == "/api/reject":
            return self._json({"ok": True})
        if self.path == "/api/tts":
            text = (body.get("text") or "").strip()[:800]
            if not text:
                return self._json({"error": "empty"}, 400)
            try:
                audio = _tts_bytes(text, (body.get("voice") or "vi-VN-HoaiMyNeural").strip(),
                                   rate=(body.get("rate") or "").strip() or None)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio)))
                self.end_headers()
                self.wfile.write(audio)
                return
            except Exception as e:
                print(f"[tts] LỖI: {e}")   # hiện rõ trong cửa sổ console của server
                return self._json({"error": f"TTS lỗi: {e}"}, 500)
        return self._json({"error": "not found"}, 404)


def main():
    global AGENT, _CODE_MTIME
    AGENT = SkillAgent(Config.load())
    _CODE_MTIME = _core_mtime()
    port = int(os.environ.get("PORT", 8765))
    url = f"http://127.0.0.1:{port}"

    print("=" * 52)
    print(f"  {agent_name()} Dashboard")
    print("  " + url)
    print("  " + key_status())
    print("=" * 52)
    if "THIẾU KEY" in key_status():
        print("[!] Có role đang THIẾU KEY — điền api_key vào config.json rồi TẢI LẠI TRANG (khỏi cần restart).")

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"\n[!] KHÔNG mở được cổng {port}. Có thể một server {agent_name()} CŨ vẫn đang chạy.")
        print("    → Đóng hết cửa sổ đen cũ (hoặc Task Manager > kết thúc python.exe) rồi chạy lại.")
        print(f"    (chi tiết: {e})")
        input("\nNhấn Enter để thoát...")
        return

    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass
    print(f"[i] Đang chạy… đóng cửa sổ này để tắt {agent_name()}.")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
