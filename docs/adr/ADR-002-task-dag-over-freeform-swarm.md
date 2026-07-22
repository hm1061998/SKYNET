# ADR-002: Task DAG over a free-form swarm

- Status: Accepted
- Date: 2026-07-22

## Context

The existing pipeline is a sequential list mediated by one orchestrator. The target needs multiple roles and workers, but unrestricted agent-to-agent delegation would make ownership, readiness, retries, budget and completion nondeterministic.

## Decision

Represent work as a persisted directed acyclic graph of stable Task entities. Code computes dependency readiness and transitions. Agents communicate through typed handoffs/reviews and are assigned ephemerally. Exactly one owner remains accountable for every Work Order and Task.

## Consequences

Parallelism becomes explicit and auditable. Cycles, retries and completion are testable. Natural-language plans require validation before becoming a DAG, and spontaneous collaboration must be translated into proposed graph changes rather than direct execution.
