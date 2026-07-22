# Structured collaboration message protocol

Phase 05 separates organizational collaboration from legacy conversational memory. Agents exchange validated, task-scoped envelopes through `core.collaboration`; they do not receive an unbounded shared transcript.

Every `CollaborationMessage` identifies the organization, work order and task, plus sender, receiver, UTC creation time, correlation and optional causation IDs. Visibility and content trust are explicit. Artifact references are identifiers, not embedded artifact contents. The protocol supports delegation, handoff, review request, review result, question, answer, status and escalation. Each type has a dedicated exact-key payload validator, and the message can be explicitly serialized and reconstructed.

`MessageRouter` dispatches only validated message types to registered handlers. `CollaborationLog` writes to the dedicated `collaboration_messages` repository and emits a structured `collaboration.message.created` audit event. It never writes these messages into legacy chat memory.

`ContextPackage` contains only selected goal/task state, assumptions, decisions, artifact references, memory excerpts, questions, constraints, permissions, output requirements and provenance. `ContextPackageBuilder` enforces both serialized-character and estimated-token limits. It truncates in a deterministic low-priority-first order and never removes provenance. If the fixed envelope and provenance cannot fit, construction fails closed.

Sequential flows share a correlation ID and use the preceding message as causation. Parallel specialist requests share correlation but have independent recipients and no peer output, preventing accidental cross-influence before aggregation.

Messages are coordination inputs, not authority. Downstream handlers must still enforce permissions, budgets, approvals and artifact validation.
