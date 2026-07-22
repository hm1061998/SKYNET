"""Deterministic capability inheritance and control-agent constraints."""
from __future__ import annotations

from core.domain import AgentDefinition, AgentKind, DomainValidationError


class CapabilityError(DomainValidationError):
    """Raised when a capability or delegation rule is violated."""


class CapabilityResolver:
    """Resolve reduced worker grants and control-agent separation rules."""

    @staticmethod
    def names(definition: AgentDefinition) -> frozenset[str]:
        return frozenset(capability.name for capability in definition.capabilities)

    def reduce_for_worker(self, parent: AgentDefinition, worker: AgentDefinition,
                          requested: set[str] | frozenset[str]) -> tuple[str, ...]:
        if parent.kind is not AgentKind.ROLE:
            raise CapabilityError("workers require a ROLE parent")
        if worker.kind is not AgentKind.WORKER:
            raise CapabilityError("worker definition must have WORKER kind")
        if worker.id not in parent.delegates_to:
            raise CapabilityError(f"{parent.id} is not allowed to delegate to {worker.id}")
        parent_names = self.names(parent)
        template_names = self.names(worker)
        requested_names = frozenset(requested)
        excess = requested_names - parent_names
        if excess:
            raise CapabilityError(f"worker permissions exceed parent grants: {sorted(excess)}")
        undeclared = requested_names - template_names
        if undeclared:
            raise CapabilityError(f"worker permissions exceed worker template: {sorted(undeclared)}")
        return tuple(sorted(requested_names))

    def assert_control_review(self, controller: AgentDefinition, *, author_id: str,
                              controller_instance_id: str, action: str) -> None:
        if controller.kind is not AgentKind.CONTROL:
            raise CapabilityError("review requires a CONTROL agent")
        if author_id == controller_instance_id:
            raise CapabilityError("control agent cannot approve its own authored artifact")
        if action.startswith("write") and action not in self.names(controller):
            raise CapabilityError("review capability does not imply write permission")
