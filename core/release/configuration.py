"""Actionable validation for release configuration examples."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.company import OrganizationTemplateLoader
from core.compatibility import RuntimeFeatureFlags
from core.governance import Constitution


class ConfigurationValidationError(ValueError):
    """Raised with a user-actionable configuration error."""


class ReleaseConfigurationValidator:
    """Validate the dependency-free JSON-compatible release configuration set."""

    @staticmethod
    def _load(path: str | Path, label: str) -> dict[str, Any]:
        source = Path(path)
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConfigurationValidationError(f"{label} file not found: {source}") from exc
        except json.JSONDecodeError as exc:
            raise ConfigurationValidationError(
                f"{label} contains invalid JSON-compatible YAML at line {exc.lineno}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ConfigurationValidationError(f"{label} root must be an object")
        return value

    def validate_config(self, path: str | Path) -> dict[str, Any]:
        data = self._load(path, "config")
        try:
            flags = RuntimeFeatureFlags.from_config(data)
        except ValueError as exc:
            raise ConfigurationValidationError(f"config runtime flags are invalid: {exc}") from exc
        providers = data.get("providers", {})
        if not isinstance(providers, dict):
            raise ConfigurationValidationError("config.providers must be an object")
        for name, provider in providers.items():
            if not isinstance(provider, dict):
                raise ConfigurationValidationError(f"provider {name} must be an object")
            if any(key in provider for key in ("api_key", "secret", "password")):
                raise ConfigurationValidationError(
                    f"provider {name} must reference environment variables, not secret fields")
            reference = provider.get("api_key_env")
            if reference is not None and (not isinstance(reference, str) or not reference.isupper()):
                raise ConfigurationValidationError(f"provider {name}.api_key_env must be an uppercase variable name")
        return {"flags": flags, "providers": tuple(sorted(providers))}

    def validate_organization(self, path: str | Path) -> dict[str, Any]:
        try:
            template = OrganizationTemplateLoader().load(path)
        except (ValueError, OSError) as exc:
            raise ConfigurationValidationError(f"organization template is invalid: {exc}") from exc
        return {"id": template.template_id, "version": template.version,
                "roles": len(template.roles), "workers": len(template.worker_templates)}

    def validate_constitution(self, path: str | Path) -> Constitution:
        data = self._load(path, "constitution")
        try:
            return Constitution.from_dict(data)
        except ValueError as exc:
            raise ConfigurationValidationError(f"constitution is invalid: {exc}") from exc

    def validate_model_profiles(self, path: str | Path) -> tuple[str, ...]:
        data = self._load(path, "model profiles")
        profiles = data.get("profiles")
        if not isinstance(profiles, dict) or not profiles:
            raise ConfigurationValidationError("model profiles require a non-empty profiles object")
        for name, profile in profiles.items():
            if not isinstance(profile, dict) or not profile.get("provider") or not profile.get("model"):
                raise ConfigurationValidationError(f"model profile {name} requires provider and model")
            if any(key in profile for key in ("api_key", "secret", "password")):
                raise ConfigurationValidationError(f"model profile {name} contains a forbidden secret field")
        return tuple(sorted(profiles))

    def validate_release_set(self, root: str | Path) -> dict[str, Any]:
        base = Path(root)
        config = self.validate_config(base / "config.example.json")
        organization = self.validate_organization(base / "organizations" / "software-company-v1.yaml")
        constitution = self.validate_constitution(base / "policies" / "default-constitution-v1.yaml")
        profiles = self.validate_model_profiles(base / "model-profiles.example.yaml")
        return {"config": config, "organization": organization,
                "constitution_version": constitution.version, "model_profiles": profiles}
