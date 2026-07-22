"""Centralized upgrade flags with safe, legacy-compatible defaults."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeFeatureFlags:
    """Bounded feature flags used while migrating from the legacy runtime."""

    organization_enabled: bool = False
    legacy_enabled: bool = True
    execution_mode: str = "dry_run"
    allow_legacy_unsafe: bool = False
    storage_backend: str = "sqlite"
    ui_mode: str = "legacy"

    @classmethod
    def from_config(cls, data: dict[str, Any] | None) -> "RuntimeFeatureFlags":
        value = data or {}
        runtime = value.get("runtime", {}) or {}
        execution = value.get("execution", {}) or {}
        storage = value.get("storage", {}) or {}
        ui = value.get("ui", {}) or {}
        flags = cls(
            organization_enabled=bool(runtime.get("organization_enabled", False)),
            legacy_enabled=bool(runtime.get("legacy_enabled", True)),
            execution_mode=str(execution.get("mode", value.get("execution_mode", "dry_run"))).lower(),
            allow_legacy_unsafe=bool(execution.get("allow_legacy_unsafe", False)),
            storage_backend=str(storage.get("backend", "sqlite")).lower(),
            ui_mode=str(ui.get("mode", "legacy")).lower(),
        )
        flags.validate()
        return flags

    def validate(self) -> None:
        if not self.organization_enabled and not self.legacy_enabled:
            raise ValueError("at least one runtime must remain enabled")
        if self.execution_mode not in {"mock", "dry_run", "sandbox", "legacy_unsafe"}:
            raise ValueError("unsupported execution mode")
        if self.execution_mode == "legacy_unsafe" and not self.allow_legacy_unsafe:
            raise ValueError("legacy unsafe execution requires an explicit allow flag")
        if self.storage_backend not in {"sqlite", "memory"}:
            raise ValueError("unsupported storage backend")
        if self.ui_mode not in {"legacy", "organization"}:
            raise ValueError("unsupported UI mode")
        if self.ui_mode == "organization" and not self.organization_enabled:
            raise ValueError("organization UI requires organization runtime")
