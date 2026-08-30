"""Lớp trừu tượng LLM đa provider: openai, anthropic, gemini, deepseek + mock offline.

- complete(messages, role, purpose) trả về text.
- SDK được tự cài (pip --break-system-packages) khi cần.
- provider "mock" không cần API key, dùng để chạy thử toàn bộ luồng.
"""
from __future__ import annotations
import importlib
import json
import re
import time
from threading import Lock

from .config import Config, RoleConfig
from .identity import AGENT_NAME


class LLMError(RuntimeError):
    pass


class LLMResponseError(LLMError):
    """Provider responded, but the response does not satisfy the requested contract."""


def validate_json(data, schema: dict | None):
    """Small dependency-free JSON contract validator.

    Schema maps keys to Python types, tuples of types, or ``(type, required)``.
    It intentionally validates control-plane responses strictly instead of
    silently accepting model-shaped data.
    """
    if schema is None:
        return data
    if not isinstance(data, dict):
        raise LLMResponseError("LLM không trả về JSON object")
    out = dict(data)
    for key, rule in schema.items():
        required = True
        expected = rule
        if isinstance(rule, tuple) and len(rule) == 2 and isinstance(rule[1], bool):
            expected, required = rule
        if key not in out:
            if required:
                raise LLMResponseError(f"JSON thiếu trường bắt buộc: {key}")
            continue
        value = out[key]
        allowed = expected if isinstance(expected, tuple) else (expected,)
        # bool is an int subclass; do not let 0/1 pass a boolean contract.
        if bool in allowed and isinstance(value, bool):
            continue
        if not isinstance(value, allowed) or (bool not in allowed and isinstance(value, bool)):
            names = ", ".join(t.__name__ for t in allowed)
            raise LLMResponseError(f"Trường '{key}' phải có kiểu {names}")
    return out


def _import(module: str, pip_name: str | None = None):
    """Import provider SDK without mutating the Python environment."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        pkg = pip_name or module
        raise LLMError(
            f"Thiếu SDK '{pkg}'. Hãy cài dependency trước khi khởi động agent; "
            "LLM runtime không tự thay đổi môi trường."
        ) from exc


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
        self._clients = {}
        self._client_lock = Lock()
        self.metrics = {"calls": 0, "failures": 0, "latency_ms": 0.0, "by_purpose": {}}

    def _client(self, key, factory):
        with self._client_lock:
            if key not in self._clients:
                self._clients[key] = factory()
            return self._clients[key]

    # ================= API chính =================
    def complete(self, messages, role: str = "chat", purpose: str | None = None,
                 temperature: float = 0.3, max_tokens: int = 2048) -> str:
        cfg = self.config.resolve(role)
        started = time.monotonic()
        purpose_key = purpose or "unspecified"
        with self._client_lock:
            self.metrics["calls"] += 1
            self.metrics["by_purpose"][purpose_key] = self.metrics["by_purpose"].get(purpose_key, 0) + 1
        try:
            if cfg.is_mock:
                return _mock_complete(messages, purpose)
            if not cfg.api_key and not cfg.is_local:
                raise LLMError(
                    f"Thiếu API key cho provider '{cfg.provider}' (role {role}). "
                    f"Điền qua biến môi trường hoặc secret store, "
                    f"hoặc đặt provider='mock' để chạy thử offline."
                )
            if cfg.provider in ("openai", "deepseek", "9router", "local"):
                return self._openai(cfg, messages, temperature, max_tokens)
            if cfg.provider == "anthropic":
                return self._anthropic(cfg, messages, temperature, max_tokens)
            if cfg.provider == "gemini":
                return self._gemini(cfg, messages, temperature, max_tokens)
            raise LLMError(f"Provider không hỗ trợ: {cfg.provider}")
        except LLMError:
            with self._client_lock:
                self.metrics["failures"] += 1
            raise
        except Exception as e:  # pragma: no cover - phụ thuộc mạng
            with self._client_lock:
                self.metrics["failures"] += 1
            raise LLMError(f"Gọi {cfg.provider}:{cfg.model} lỗi: {e}") from e
        finally:
            with self._client_lock:
                self.metrics["latency_ms"] += (time.monotonic() - started) * 1000

    def complete_json(self, messages, role="chat", purpose=None, schema=None, **kw):
        raw = self.complete(messages, role=role, purpose=purpose, **kw)
        data = extract_json(raw)
        if data is None:
            raise LLMResponseError("Không parse được JSON từ phản hồi LLM")
        return validate_json(data, schema)

    # ================= OpenAI / DeepSeek =================
    def _openai(self, cfg: RoleConfig, messages, temperature, max_tokens) -> str:
        OpenAI = _import("openai").OpenAI
        kwargs = {"api_key": cfg.api_key or "local"}
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        kwargs.update({"timeout": 90.0, "max_retries": 2})
        client = self._client(
            ("openai", cfg.base_url or "", cfg.api_key or "local"),
            lambda: OpenAI(**kwargs),
        )
        try:
            resp = client.chat.completions.create(
                model=cfg.model, messages=messages,
                temperature=temperature, max_tokens=max_tokens)
        except Exception as exc:
            # Retry without optional sampling arguments only for an explicit
            # unsupported-parameter response. Never duplicate auth/rate-limit/
            # timeout requests under the guise of compatibility.
            msg = str(exc).lower()
            unsupported = any(x in msg for x in (
                "unsupported parameter", "does not support", "unknown parameter",
                "temperature is not", "max_tokens is not",
            ))
            if not unsupported:
                raise
            resp = client.chat.completions.create(model=cfg.model, messages=messages)
        return resp.choices[0].message.content or ""

    # ================= Anthropic =================
    def _anthropic(self, cfg: RoleConfig, messages, temperature, max_tokens) -> str:
        anthropic = _import("anthropic")
        client = self._client(
            ("anthropic", cfg.api_key),
            lambda: anthropic.Anthropic(api_key=cfg.api_key, timeout=90.0, max_retries=2),
        )
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
            resp = model.generate_content(
                body, generation_config=gen_cfg, request_options={"timeout": 90}
            )
        except TypeError:
            model = genai.GenerativeModel(cfg.model)
            resp = model.generate_content(
                (system + "\n\n" + body) if system else body,
                generation_config=gen_cfg,
                request_options={"timeout": 90},
            )
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
