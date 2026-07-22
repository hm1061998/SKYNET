# Retrospective checkpoint — Phase 04

Scope: Goal, Work Order and Task DAG foundation, reviewed against the current tree and Phase 04 report. No new feature was introduced by this checkpoint.

## Findings

- **Compatibility:** legacy `_decompose`/`_run_pipeline` remains separate; `LegacyPipelineAdapter` only projects a linear DAG. Current legacy E2E coverage confirms the original pipeline remains available.
- **Boundaries:** `core.work` depends on domain/repository ports, not UI, provider SDKs or the skill runner. UI does not call scheduler repositories directly.
- **Execution safety:** graph validation precedes dispatch; permission, artifact, role, timeout, idempotency and allocation prerequisites are checked before the dispatcher.
- **State correctness:** Goal, Work Order and Task changes use explicit state machines. Completion is emitted once. Pause/resume, cancellation, input/approval waits, retry exhaustion and dependency failure are covered.
- **Persistence:** SQLite restart/resume is tested. The remaining production gap is a durable effect/idempotency ledger around irreversible adapters.
- **Budgets/approvals:** task allocation and Work Order plan approval gates are enforced. Later governance adds exact action approvals; no direct bypass was found.
- **Duplication:** the legacy linear pipeline and governed DAG are intentionally separate execution models connected by one adapter, not competing scheduler implementations.
- **Tests/docs:** task DAG, lifecycle and scheduler documents match code. Restart and failure-path tests remain green.

## Decision

No critical Phase 04 defect found. Distributed leases/outbox and durable irreversible-effect deduplication remain production work, not a checkpoint fix.
