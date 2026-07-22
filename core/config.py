"""Đọc config.json + biến môi trường, phân giải cấu hình cho từng role (chat/work)."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass

from . import CONFIG_PATH

# provider -> tên biến môi trường chứa API key
ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}

# model mặc định nếu config không ghi rõ
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "9router": "SKYNET",
    "local": "qwen3:4b",
    "mock": "mock-1",
}

DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "9router": "http://127.0.0.1:20128/v1",
}


@dataclass
class RoleConfig:
    """Cấu hình đã phân giải cho một vai trò (chat hoặc work)."""
    role: str
    provider: str
    model: str
    api_key: str = ""
    base_url: str | None = None

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    @property
    def is_local(self) -> bool:
        return self.provider in ("local", "9router")

    @property
    def ready(self) -> bool:
        """Có thể gọi được không (mock luôn sẵn sàng; còn lại cần key)."""
        return self.is_mock or self.is_local or bool(self.api_key)


class Config:
    def __init__(self, data: dict | None = None):
        self.data = data or {}

    @property
    def execution_mode(self) -> str:
        """Safe execution mode; legacy host mutation must be explicitly selected."""
        mode = (os.environ.get("JAVIS_EXECUTION_MODE") or
                self.data.get("execution_mode") or "dry_run").strip().lower()
        if mode not in {"mock", "dry_run", "sandbox", "legacy_unsafe"}:
            raise ValueError(f"unknown execution mode: {mode}")
        return mode

    # ---- nạp ----
    @classmethod
    def load(cls, path=CONFIG_PATH) -> "Config":
        data = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            raise SystemExit(f"[config] config.json lỗi cú pháp: {e}")
        return cls(data)

    # ---- provider mặc định ----
    @property
    def default_provider(self) -> str:
        return (
            os.environ.get("SKILL_AGENT_PROVIDER")
            or self.data.get("provider")
            or "openai"
        )

    # ---- phân giải role ----
    def resolve(self, role: str = "chat") -> RoleConfig:
        roles = self.data.get("roles", {}) or {}
        rc = roles.get(role, {}) or {}

        provider = rc.get("provider") or self.default_provider
        pcfg = self.data.get(provider, {}) or {}

        model = rc.get("model") or pcfg.get("model") or DEFAULT_MODELS.get(provider, "")

        api_key = pcfg.get("api_key") or ""
        if not api_key and provider in ENV_KEYS:
            api_key = os.environ.get(ENV_KEYS[provider], "")

        base_url = rc.get("base_url") or pcfg.get("base_url") or DEFAULT_BASE_URLS.get(provider)

        return RoleConfig(role=role, provider=provider, model=model,
                          api_key=api_key, base_url=base_url)

    def describe(self) -> str:
        chat, work = self.resolve("chat"), self.resolve("work")
        def one(r: RoleConfig):
            k = "mock" if r.is_mock else ("local" if r.is_local else ("có key" if r.api_key else "THIẾU key"))
            return f"{r.role}={r.provider}:{r.model} ({k})"
        warning = " | WARNING: LEGACY UNSAFE HOST MUTATION ENABLED" if self.execution_mode == "legacy_unsafe" else ""
        return f"{one(chat)} | {one(work)} | execution={self.execution_mode}{warning}"
