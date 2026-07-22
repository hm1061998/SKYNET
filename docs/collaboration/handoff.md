# Delegation and handoff

Delegation and handoff are distinct governance operations.

A role agent may delegate only to worker definitions listed in its declarative `delegates_to` relationship. `DelegationService` verifies the manager and worker kinds, task scope of the context package, explicit child task, deliverables, non-negative budget allocation, future deadline and return contract. The resulting record keeps the delegating agent as the accountable owner.

A handoff begins in `pending`. Its reason and proposed receiver are immutable in that request. Only the receiving agent can accept or reject it. Acceptance transfers accountability to that receiver; rejection requires a structured reason and leaves accountability with the original owner. A decided handoff cannot be decided again.

The handoff message payload additionally carries receiving role, bounded context package, unresolved obligations, remaining budget, approval requirement, acceptance state and rejection reason. Approval requirements are descriptive inputs to the approval policy; a handoff does not bypass the policy engine.

Operational adapters should persist delegation and handoff records and emit audit events in the same transaction boundary as ownership updates. Phase 05 supplies the domain protocol and keeps actual scheduler ownership mutation behind that future adapter boundary.
