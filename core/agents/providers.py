"""Completion port and adapter for the existing chat/work LLM abstraction."""
from __future__ import annotations

from typing import Protocol

from core.llm import LLM

from .routing import RoutedModelProfile


class AgentCompletionProvider(Protocol):
    """Provider port consumed by the agent runtime."""

    def complete(self, messages: list[dict[str, str]], profile: RoutedModelProfile,
                 purpose: str) -> str: ...


class LegacyProviderAdapter:
    """Map logical profiles to existing `roles.chat` and `roles.work` calls."""

    def __init__(self, llm: LLM, profile_roles: dict[str, str] | None = None) -> None:
        self.llm = llm
        self.profile_roles = {
            "fast_classifier": "chat",
            "balanced_reasoning": "work",
            "deep_reasoning": "work",
            "code_generation": "work",
            "review": "work",
            "local_private": "work",
            **(profile_roles or {}),
        }

    def complete(self, messages: list[dict[str, str]], profile: RoutedModelProfile,
                 purpose: str) -> str:
        role = self.profile_roles.get(profile.name, profile.role)
        return self.llm.complete(messages, role=role, purpose=purpose,
                                 temperature=profile.temperature, max_tokens=profile.max_tokens)
