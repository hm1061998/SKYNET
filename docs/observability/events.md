# Structured events and audit records

Phase 10 introduces `OrganizationEvent` as the public operational event envelope. Every event has a stable ID, bounded type and severity, UTC timestamp, organization/work-order/task/agent scope, correlation and optional causation IDs, a safe public summary, JSON-compatible metadata, and an explicit redaction status.

The supported taxonomy covers goals, work orders, plans, tasks, agents, delegation, handoffs, model/tool/skill/sandbox activity, artifacts, reviews, policies, approvals, budgets, retries, escalations, failures, and completion. New taxonomy values must be added deliberately to `EVENT_TYPES`; arbitrary strings are rejected.

`EventRecorder` applies the governance redactor before the sink receives an event. Keys associated with secrets are replaced, and private reasoning fields such as `chain_of_thought` and `reasoning` are rejected recursively. Public summaries must describe the operational decision or result and must never contain raw prompts, hidden reasoning, credentials, or unrestricted tool output.

Sensitive and governed actions can additionally be written to `AppendOnlyAuditLog`. Entries form an application-level SHA-256 chain over their canonical payload and predecessor hash. `verify()` detects mutation or reordering. The API intentionally provides no update or delete operation. This is tamper-evident, not a substitute for an externally anchored/WORM production audit store.

Correlation IDs group one goal or work-order execution. Causation IDs point to the event that directly triggered a later event. Idempotency keys belong in sanitized metadata when retries could otherwise duplicate an effect.
