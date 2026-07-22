# Layered memory model

Organizational memory is separate from legacy conversation/facts JSONL. Every `MemoryRecord` has a stable ID, explicit scope and owner, bounded kind, content, provenance references, UTC creation metadata, creator, confidence, validation state, sensitivity, retention policy, tags and a verified SHA-256 content hash.

Scopes are isolated:

- Conversation: bounded current-session interaction; never automatically promoted.
- Task: temporary facts, results and decisions associated with execution and Work Order retention.
- Agent: role-specific lessons, procedures and feedback.
- Department: reviewed standards, patterns, decisions and terminology.
- Organization: validated mission, constitution, products, architecture, policy and lessons.

`RetrievalService` filters by scope, owner permission, sensitivity, validation, confidence and expiration before scoring. Default ranking combines lexical overlap and recency. An optional embedding port can add vector scores without adding an offline dependency. Returned snippets retain source references and authoritative hashes, and a character budget bounds context.

Conflicting verified knowledge is never overwritten. Both records remain stored and a `MemoryConflict` references both provenance sets. No active version is selected until a reviewer resolves the conflict.

`LegacyKnowledgeAdapter` delegates reads to the existing `LegacyMemoryAdapter`. Existing `facts.jsonl` and `chat_*.jsonl` files are not rewritten, deleted or automatically promoted.
