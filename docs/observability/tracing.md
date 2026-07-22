# Operational tracing

`TraceService` records safe, nested operational spans for planning, model calls, retrieval, tool calls, skill execution, review, approval waits, persistence, and artifact writes. Each span records stable IDs, parent relationship, UTC times, duration, status, sanitized inputs/outputs, aggregate usage, and a bounded error category.

Tracing deliberately excludes chain-of-thought, hidden scratchpads, raw secrets, and unrestricted prompts. Inputs and outputs first pass through the same redaction boundary used by events. Unknown parents, unsupported span kinds, double completion, and private-reasoning fields are rejected.

The dashboard exposes `GET /api/v1/traces` as a read-only summary. It contains identifiers, timing, nesting, span kind/status, and error category only. It is suitable for operations and debugging but cannot reconstruct private model reasoning.

For production scale, persist traces through an adapter implementing the same domain contract and enforce retention and organization-level authorization at that boundary. OpenTelemetry export can be added later without coupling workflow domain objects to a vendor SDK.
