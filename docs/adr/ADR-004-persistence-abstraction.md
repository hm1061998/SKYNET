# ADR-004: Persistence abstraction

- Status: Accepted
- Date: 2026-07-22

## Context

Memory and plans use global filesystem paths, while jobs exist only in process memory. Domain state will need atomic transitions, restart recovery, audit append, versioned artifacts and deterministic tests without forcing a heavyweight framework now.

## Decision

Define narrow ports owned by the application/domain boundary for Work Orders, task graphs, approvals, events/audit, artifacts, memory, leases and idempotency records. Begin with standard-library in-memory/filesystem adapters where sufficient. Inject clocks and ID generators for tests. Persistence implementations store state but do not define domain rules.

## Consequences

The initial implementation remains lightweight and testable, while later database/object-store adapters do not change domain behavior. Atomicity across ports must be designed explicitly; an outbox or equivalent may be required before distributed execution.
