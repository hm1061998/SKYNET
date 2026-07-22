"""Model profile resolution without vendor choices in domain logic."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from core.domain import AgentDefinition, DomainValidationError


@dataclass(frozen=True)
class RoutedModelProfile:
    """Resolved adapter configuration for one logical model profile."""

    name: str
    provider: str
    model: str
    role: str
    base_url: str | None = None
    max_tokens: int = 2048
    temperature: float = 0.2

    def __post_init__(self) -> None:
        if not self.name or not self.provider or not self.model or not self.role:
            raise DomainValidationError("model route fields must be non-empty")
        if self.max_tokens < 1:
            raise DomainValidationError("model route max_tokens must be positive")


LOGICAL_PROFILE_NAMES = (
    "fast_classifier", "balanced_reasoning", "deep_reasoning",
    "code_generation", "review", "local_private",
)


class ModelRouter:
    """Resolve logical profiles with organization then role overrides."""

    def __init__(self, profiles: Mapping[str, RoutedModelProfile],
                 organization_overrides: Mapping[str, Mapping[str, Any]] | None = None,
                 role_overrides: Mapping[str, Mapping[str, Mapping[str, Any]]] | None = None) -> None:
        self.profiles = dict(profiles)
        self.organization_overrides = dict(organization_overrides or {})
        self.role_overrides = dict(role_overrides or {})

    def resolve(self, profile_name: str, *, organization_id: str | None = None,
                role_id: str | None = None) -> RoutedModelProfile:
        try:
            profile = self.profiles[profile_name]
        except KeyError as exc:
            raise DomainValidationError(f"unknown model profile: {profile_name}") from exc
        if organization_id:
            values = self.organization_overrides.get(organization_id, {}).get(profile_name, {})
            if values:
                profile = replace(profile, **values)
        if role_id:
            values = self.role_overrides.get(role_id, {}).get(profile_name, {})
            if values:
                profile = replace(profile, **values)
        return profile

    def for_agent(self, definition: AgentDefinition, *, organization_id: str | None = None) -> RoutedModelProfile:
        if not definition.model_profile_name:
            raise DomainValidationError(f"agent {definition.id} has no model profile")
        return self.resolve(definition.model_profile_name, organization_id=organization_id,
                            role_id=definition.id)
