"""Validated AI Software Company organization template loader."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core.agents import AgentDefinitionError, AgentRegistry
from core.domain import AgentDefinition, AgentKind, DomainValidationError


CORE_ROLE_IDS = (
    "chief_of_staff", "product_manager", "solution_architect", "developer",
    "code_reviewer", "qa_engineer", "security_release_officer",
)


@dataclass(frozen=True)
class OrganizationTemplate:
    template_id: str
    version: str
    departments: tuple[dict[str, Any], ...]
    roles: tuple[AgentDefinition, ...]
    worker_templates: tuple[AgentDefinition, ...]
    reporting_lines: tuple[dict[str, str], ...]
    model_profiles: dict[str, Any]
    permissions: dict[str, Any]
    budgets: dict[str, Any]
    workflow_templates: dict[str, Any]
    constitution_reference: str
    kpis: tuple[dict[str, Any], ...]

    @property
    def role_registry(self) -> AgentRegistry:
        # Worker templates are a separate catalog; core-only loading intentionally
        # removes cross-catalog delegation references while preserving seven roles.
        return AgentRegistry(replace(role, delegates_to=()) for role in self.roles)

    @property
    def full_registry(self) -> AgentRegistry:
        return AgentRegistry(self.roles + self.worker_templates)


class OrganizationTemplateLoader:
    """Load dependency-free JSON-compatible YAML and enforce the MVP shape."""

    def load(self, path: str | Path) -> OrganizationTemplate:
        source = Path(path)
        if source.suffix.lower() not in {".yaml", ".yml", ".json"}:
            raise DomainValidationError("organization template must be YAML or JSON")
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            roles = tuple(AgentRegistry._from_record(item) for item in data["roles"])
            workers = tuple(AgentRegistry._from_record(item) for item in data.get("worker_templates", ()))
            template = OrganizationTemplate(
                str(data["id"]), str(data["version"]), tuple(data["departments"]), roles,
                workers, tuple(data["reporting_lines"]), dict(data["model_profiles"]),
                dict(data["permissions"]), dict(data["budgets"]),
                dict(data["workflow_templates"]), str(data["constitution_reference"]),
                tuple(data["kpis"]),
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError,
                AgentDefinitionError) as exc:
            raise DomainValidationError(f"invalid organization template: {exc}") from exc
        self._validate(template)
        return template

    @staticmethod
    def _validate(template: OrganizationTemplate) -> None:
        role_ids = tuple(role.id for role in template.roles)
        if len(role_ids) != 7 or set(role_ids) != set(CORE_ROLE_IDS):
            raise DomainValidationError("AI Software Company must contain exactly seven core roles")
        if any(role.kind is not AgentKind.ROLE for role in template.roles):
            raise DomainValidationError("all core definitions must be role agents")
        if any(worker.kind is not AgentKind.WORKER for worker in template.worker_templates):
            raise DomainValidationError("temporary templates must be worker agents")
        template.full_registry.validate()
        reporting = {(item["manager"], item["report"]) for item in template.reporting_lines}
        required = {("chief_of_staff", role) for role in (
            "product_manager", "solution_architect", "code_reviewer", "qa_engineer",
            "security_release_officer")} | {("solution_architect", "developer")}
        if not required <= reporting:
            raise DomainValidationError("organization reporting lines are incomplete")
        if "software_feature_delivery_v1" not in template.workflow_templates:
            raise DomainValidationError("required feature-delivery workflow is missing")


class SeparationOfDuties:
    """Code-enforced role constraints for the organization template."""

    def authorize(self, *, role_id: str, action: str, artifact_author_role: str | None = None,
                  product_manager_approved: bool = False,
                  human_production_approved: bool = False) -> bool:
        if action == "approve_code" and role_id == artifact_author_role:
            return False
        if role_id == "solution_architect" and action == "approve_code":
            return False
        if role_id == "code_reviewer" and action in {"release", "deploy_production"}:
            return False
        if role_id == "qa_engineer" and action == "change_acceptance_criteria":
            return product_manager_approved
        if action == "deploy_production":
            return role_id == "security_release_officer" and human_production_approved
        if role_id == "chief_of_staff" and action in {"alter_policy", "approve_own_exception"}:
            return False
        if role_id == "developer" and action in {
                "deploy_production", "install_unapproved_dependency", "change_acceptance_criteria"}:
            return False
        if role_id == "code_reviewer" and action == "modify_reviewed_artifact":
            return False
        return True
