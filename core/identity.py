"""Danh tính Agent dùng chung cho toàn bộ Python runtime."""
from __future__ import annotations

import json
from pathlib import Path

IDENTITY_PATH = Path(__file__).resolve().parent.parent / "agent.config.json"


def load_identity() -> dict:
    try:
        data = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def get_agent_name() -> str:
    return str(load_identity().get("name") or "AI Agent").strip()


AGENT_NAME = get_agent_name()
