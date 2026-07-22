"""Lớp trừu tượng LLM đa provider: openai, anthropic, gemini, deepseek + mock offline.

- complete(messages, role, purpose) trả về text.
- SDK được tự cài (pip --break-system-packages) khi cần.
- provider "mock" không cần API key, dùng để chạy thử toàn bộ luồng.
"""
from __future__ import annotations
import importlib
import json
import re
import subprocess
import sys

from .config import Config, RoleConfig
from .identity import AGENT_NAME


class LLMError(RuntimeError):
    pass


def _import(module: str, pip_name: str | None = None):
    """Import module, tự cài bằng pip nếu thiếu."""
    try:
        return importlib.import_module(module)
    except ImportError:
        pkg = pip_name or module
        print(f"[llm] Đang cài SDK: {pkg} ...", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "pip", "install", pkg,
                        "--break-system-packages", "--quiet"], check=False)
        return importlib.import_module(module)


def extract_json(text: str):
    """Trích object/array JSON đầu tiên trong text (bỏ ```json fences)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # tìm khối {...} hoặc [...] cân bằng đầu tiên
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s = t.find(open_c)
        if s == -1:
            continue
        depth = 0
        for i in range(s, len(t)):
            if t[i] == open_c:
                depth += 1
            elif t[i] == close_c:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[s:i + 1])
                    except Exception:
                        break
    return None


class LLM:
    def __init__(self, config: Config):
        self.config = config

    # ================= API chính =================
    def complete(self, messages, role: str = "chat", purpose: str | None = None,
                 temperature: float = 0.3, max_tokens: int = 2048) -> str:
        cfg = self.config.resolve(role)
        if cfg.is_mock:
            return _mock_complete(messages, purpose)
        if not cfg.api_key and not cfg.is_local:
            raise LLMError(
                f"Thiếu API key cho provider '{cfg.provider}' (role {role}). "
                f"Điền vào config.json hoặc export biến môi trường, "
                f"hoặc đặt provider='mock' để chạy thử offline."
            )
        try:
            if cfg.provider in ("openai", "deepseek", "9router", "local"):
                return self._openai(cfg, messages, temperature, max_tokens)
            if cfg.provider == "anthropic":
                return self._anthropic(cfg, messages, temperature, max_tokens)
            if cfg.provider == "gemini":
                return self._gemini(cfg, messages, temperature, max_tokens)
            raise LLMError(f"Provider không hỗ trợ: {cfg.provider}")
        except LLMError:
            raise
        except Exception as e:  # pragma: no cover - phụ thuộc mạng
            raise LLMError(f"Gọi {cfg.provider}:{cfg.model} lỗi: {e}") from e

    def complete_json(self, messages, role="chat", purpose=None, **kw):
        return extract_json(self.complete(messages, role=role, purpose=purpose, **kw))

    # ================= OpenAI / DeepSeek =================
    def _openai(self, cfg: RoleConfig, messages, temperature, max_tokens) -> str:
        OpenAI = _import("openai").OpenAI
        kwargs = {"api_key": cfg.api_key or "local"}
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        client = OpenAI(**kwargs)
        try:
            resp = client.chat.completions.create(
                model=cfg.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens)
        except Exception:
            # vài model (o1/o4...) không nhận temperature/max_tokens -> thử tối giản
            resp = client.chat.completions.create(model=cfg.model, messages=messages)
        return resp.choices[0].message.content or ""

    # ================= Anthropic =================
    def _anthropic(self, cfg: RoleConfig, messages, temperature, max_tokens) -> str:
        anthropic = _import("anthropic")
        client = anthropic.Anthropic(api_key=cfg.api_key)
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = [{"role": ("assistant" if m["role"] == "assistant" else "user"),
                 "content": m["content"]}
                for m in messages if m["role"] != "system"]
        resp = client.messages.create(
            model=cfg.model, max_tokens=max_tokens,
            system=system or None, messages=conv, temperature=temperature)
        return "".join(getattr(b, "text", "") for b in resp.content)

    # ================= Gemini =================
    def _gemini(self, cfg: RoleConfig, messages, temperature, max_tokens) -> str:
        genai = _import("google.generativeai", "google-generativeai")
        genai.configure(api_key=cfg.api_key)
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        body = "\n\n".join(f"{m['role'].upper()}: {m['content']}"
                           for m in messages if m["role"] != "system")
        gen_cfg = {"temperature": temperature, "max_output_tokens": max_tokens}
        try:
            model = genai.GenerativeModel(cfg.model, system_instruction=system or None)
            resp = model.generate_content(body, generation_config=gen_cfg)
        except TypeError:
            model = genai.GenerativeModel(cfg.model)
            resp = model.generate_content(
                (system + "\n\n" + body) if system else body, generation_config=gen_cfg)
        return resp.text or ""


# ============================================================
#  MOCK provider — trả lời giả lập theo `purpose` để chạy offline
# ============================================================
_TASK_HINTS = [
    "cắt", "ghép", "trộn", "gộp", "tách", "nén", "resize", "crop", "rotate",
    "convert", "chuyển", "đổi", "tải", "download", "xoá nền", "xóa nền", "ocr",
    "dịch", "tóm tắt", "gửi", "vẽ", "biểu đồ", "phân tích", "tạo", "sinh",
    "extract", "merge", "split", "rename", "đổi tên", "backup", "sao lưu",
    "mã hoá", "encrypt", "qr", "screenshot", "chụp",
]


def _last_user(messages) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content", "")
    return messages[-1].get("content", "") if messages else ""


def _slug(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    words = [w for w in t.split("_") if w][:3]
    return "_".join(words) or "skill"


def _mock_params_schema(task: str) -> dict:
    params = {}
    if re.search(r"\S+\.\w{2,4}", task):
        params["input_path"] = {"type": "str", "description": "Đường dẫn tệp đầu vào", "required": True}
    if re.search(r"(\d+)\s*[x×]\s*(\d+)", task):
        params["width"] = {"type": "int", "description": "Chiều rộng", "required": True}
        params["height"] = {"type": "int", "description": "Chiều cao", "required": True}
    if not params:
        params["text"] = {"type": "str", "description": "Nội dung đầu vào", "required": False}
    return params


def _mock_complete(messages, purpose: str | None) -> str:
    user = _last_user(messages)

    if purpose == "classify":
        low = user.lower()
        is_task = any(h in low for h in _TASK_HINTS)
        if is_task:
            return json.dumps({"type": "task", "task": user,
                               "reply": ""}, ensure_ascii=False)
        return json.dumps({"type": "chat",
                           "reply": f"Chào bạn 👋 Mình là {AGENT_NAME}. Bạn vừa nói: “{user}”. "
                                    f"Mình có thể giúp gì nào?"}, ensure_ascii=False)

    if purpose == "plan":
        return json.dumps({"steps": [
            f"Phân tích yêu cầu: {user}",
            "Tìm skill phù hợp trong registry; nếu chưa có thì tự sinh skill mới",
            "Rút tham số từ yêu cầu và chạy skill",
            "Kiểm tra kết quả, tự sửa 1 lần nếu lỗi, rồi báo cáo",
        ]}, ensure_ascii=False)

    if purpose in ("generate", "fix"):
        # bỏ nhãn "Yêu cầu:" nếu có để đặt tên skill cho sạch
        task = re.sub(r"^\s*(yêu cầu|yeu cau|task|request)\s*:\s*", "", user, flags=re.I)
        name = _slug(task) + ("_safe" if purpose == "fix" else "")
        schema = _mock_params_schema(task)
        tags = re.sub(r"[^\w\s]", " ", task.lower()).split()[:4]
        # DÙNG repr() (không phải json.dumps) để nhúng vào MÃ PYTHON hợp lệ (True/False, không phải true/false)
        code = _MOCK_SKILL_TEMPLATE.format(
            name=name,
            desc=task.replace('"', "'").replace("\n", " "),
            tags=repr(tags),
            params=repr(schema),
        )
        return f"===PARAMS===\n{{}}\n===CODE===\n```python\n{code}\n```"

    # chat / mặc định
    return f"(mock) Mình đã nhận: {user}"


_MOCK_SKILL_TEMPLATE = '''SKILL_META = {{
    "name": "{name}",
    "description": "{desc}",
    "tags": {tags},
    "params": {params},
}}


def run(**kwargs):
    """Skill sinh bởi mock — tự xử lý an toàn, không cần thư viện ngoài."""
    return {{
        "success": True,
        "result": "Đã xử lý (mock) với tham số: " + str(kwargs),
    }}
'''
