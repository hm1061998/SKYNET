"""Declarative agent definition loading and hierarchy validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from core.domain import AgentDefinition, AgentKind, Capability, DomainValidationError, ToolGrant


class AgentDefinitionError(DomainValidationError):
    """Raised when declarative agent definitions are inconsistent."""


class AgentRegistry:
    """Validated collection of role, worker-template and control definitions."""

    def __init__(self, definitions: Iterable[AgentDefinition] = ()) -> None:
        self._definitions: dict[str, AgentDefinition] = {}
        for definition in definitions:
            self.register(definition)
        self.validate()

    @classmethod
    def from_repository(cls, repository: Any) -> "AgentRegistry":
        """Hydrate definitions through the repository port."""
        return cls(repository.list())

    def persist(self, repository: Any) -> None:
        """Persist new definitions without changing repository semantics."""
        existing = {item.id: item for item in repository.list()}
        for definition in self.list():
            current = existing.get(definition.id)
            if current is None:
                repository.add(definition)
            elif current != definition:
                repository.save(definition, expected_version=current.version)

    def register(self, definition: AgentDefinition) -> None:
        if definition.id in self._definitions:
            raise AgentDefinitionError(f"duplicate agent definition: {definition.id}")
        self._definitions[definition.id] = definition

    def get(self, definition_id: str) -> AgentDefinition:
        try:
            return self._definitions[definition_id]
        except KeyError as exc:
            raise AgentDefinitionError(f"unknown agent definition: {definition_id}") from exc

    def list(self) -> list[AgentDefinition]:
        return [self._definitions[key] for key in sorted(self._definitions)]

    def validate(self) -> None:
        for definition in self._definitions.values():
            if definition.reports_to and definition.reports_to not in self._definitions:
                raise AgentDefinitionError(
                    f"{definition.id} reports to unknown definition {definition.reports_to}")
            for delegate in definition.delegates_to:
                if delegate not in self._definitions:
                    raise AgentDefinitionError(
                        f"{definition.id} delegates to unknown definition {delegate}")
        self._validate_reporting_cycles()

    def _validate_reporting_cycles(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(definition_id: str) -> None:
            if definition_id in visiting:
                raise AgentDefinitionError(f"cyclic reporting hierarchy at {definition_id}")
            if definition_id in visited:
                return
            visiting.add(definition_id)
            parent = self._definitions[definition_id].reports_to
            if parent:
                visit(parent)
            visiting.remove(definition_id)
            visited.add(definition_id)

        for definition_id in self._definitions:
            visit(definition_id)

    @classmethod
    def load_file(cls, path: str | Path) -> "AgentRegistry":
        """Load JSON definitions without importing provider or YAML dependencies."""
        source = Path(path)
        if source.suffix.lower() != ".json":
            raise AgentDefinitionError("Phase 03 declarative loader accepts JSON files")
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentDefinitionError(f"cannot load definitions: {exc}") from exc
        records = data.get("agents") if isinstance(data, dict) else data
        if not isinstance(records, list) or not records:
            raise AgentDefinitionError("definition file must contain a non-empty agents list")
        return cls(cls._from_record(record) for record in records)

    @staticmethod
    def _from_record(record: Any) -> AgentDefinition:
        if not isinstance(record, dict):
            raise AgentDefinitionError("each agent definition must be an object")
        try:
            definition_id = str(record["id"])
            kind = AgentKind(str(record["kind"]).lower())
            capabilities = tuple(Capability(str(name)) for name in record.get("capabilities", ()))
            grants = tuple(ToolGrant(str(item["tool"]), tuple(item.get("scopes", ())))
                           for item in record.get("tool_grants", ()))
            limits = dict(record.get("limits", {}))
            return AgentDefinition(
                id=definition_id,
                name=str(record["name"]),
                kind=kind,
                role_id=str(record.get("role_id") or definition_id),
                capabilities=capabilities,
                tool_grants=grants,
                mission=str(record.get("mission", "")),
                department_id=record.get("department"),
                reports_to=record.get("reports_to"),
                delegates_to=tuple(record.get("delegates_to", ())),
                model_profile_name=record.get("model_profile"),
                memory_scopes=tuple(record.get("memory_scope", ())),
                policies=tuple(record.get("policies", ())),
                limits=limits,
                role_prompt=str(record.get("role_prompt", "")),
            )
        except (KeyError, TypeError, ValueError, DomainValidationError) as exc:
            raise AgentDefinitionError(f"invalid agent definition: {exc}") from exc
