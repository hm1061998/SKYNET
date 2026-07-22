"""Deterministic policy, risk and action classification."""
from __future__ import annotations

from core.domain import RiskLevel

from .models import (ActionRequest, Constitution, GovernanceDecision, PolicyEffect)


class ActionClassifier:
    """Normalize known external and host-changing actions."""

    ALIASES = {"pip_install": "install_dependency", "delete": "delete_file",
               "deploy": "deploy_production", "http_request": "send_network_request"}

    def classify(self, action: str) -> str:
        value = action.strip().lower().replace(" ", "_")
        return self.ALIASES.get(value, value)


class RiskClassifier:
    """Conservatively classify action risk without model inference."""

    CRITICAL = {"deploy_production", "access_secret", "production_data_access"}
    HIGH = {"delete_file", "install_dependency", "send_external_message", "change_permissions"}
    MEDIUM = {"send_network_request", "write_file", "execute_command"}

    def classify(self, action: str) -> RiskLevel:
        action = ActionClassifier().classify(action)
        if action in self.CRITICAL:
            return RiskLevel.CRITICAL
        if action in self.HIGH:
            return RiskLevel.HIGH
        if action in self.MEDIUM:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


class PolicyEngine:
    """Resolve the first exact policy rule; absence deterministically denies."""

    def __init__(self, constitution: Constitution) -> None:
        self.constitution = constitution
        self.classifier = ActionClassifier()

    def decide(self, request: ActionRequest, *, explicitly_granted: bool = False,
               allowlisted: bool = False, approved: bool = False) -> GovernanceDecision:
        if request.constitution_version != self.constitution.version:
            return GovernanceDecision(request.id, PolicyEffect.DENY, False,
                                      "constitution version mismatch", None)
        action = self.classifier.classify(request.action)
        rule = next((item for item in self.constitution.policies if item.action == action), None)
        if rule is None:
            return GovernanceDecision(request.id, PolicyEffect.DENY, False,
                                      "deny by default: no matching policy", None)
        allowed = {
            PolicyEffect.ALLOW: True,
            PolicyEffect.DENY: False,
            PolicyEffect.REQUIRE_EXPLICIT_GRANT: explicitly_granted,
            PolicyEffect.DENY_UNLESS_ALLOWLISTED: allowlisted,
            PolicyEffect.REQUIRE_HUMAN_APPROVAL: approved,
            PolicyEffect.REQUIRE_SECURITY_APPROVAL: approved,
        }[rule.effect]
        reason = rule.reason or ("policy conditions satisfied" if allowed else
                                 f"policy requires {rule.effect.value}")
        return GovernanceDecision(request.id, rule.effect, allowed, reason, rule.action)
