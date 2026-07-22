# Phase 04 Report

## Objective

Add governed Goal intake, Work Order planning, validated Task DAGs and a deterministic synchronous scheduler while retaining the legacy linear pipeline behind an observability-only adapter.

## Repository state discovered

Phase 03 provided 30 passing tests, persistent agent definitions, role runtime lifecycle, model routing and prompt boundaries. Work management still had minimal Goal/WorkOrder/Task dataclasses and a Task transition table, but no intake service, rich Work Order/Task schema, graph validator, planner normalization, scheduler, dispatcher, retry/cancellation services or restart test. Production still used the legacy `SkillAgent` pipeline.

Baseline UTF-8 legacy self-test remained 41 passed / 2 documented pre-existing failures.

## Design decisions

- Extend WorkOrder and Task additively with defaulted fields to preserve old constructor/JSON compatibility.
- Keep all Phase 04 status changes behind explicit state-machine services.
- Treat model planner output as untrusted and require one exact envelope before normalization.
- Revalidate the DAG on every tick, including budget and idempotency invariants.
- Use deterministic synchronous dispatch for the MVP and repository state for restart continuity.
- Generate attempt-scoped idempotency tokens so tick replay is safe while legitimate retries remain possible.
- Require explicit resume signals for human-input/approval waits.
- Keep legacy `_decompose`/`_run_pipeline` unchanged; map steps only through an optional adapter.

## Implementation completed

- Added the requested Work Order and Task fields, lifecycle states and serialization.
- Added `GoalIntakeService`, `WorkOrderPlanner`, `TaskGraph`, `TaskGraphValidator`.
- Added Goal, Work Order and Task state machines.
- Added `TaskScheduler`, `TaskDispatcher`, `RetryPolicy`, `CancellationService`, control service and completion evaluator.
- Added dependency/artifact/permission/role/budget/timeout/approval readiness checks.
- Added pause/resume, cancellation propagation, bounded retry/backoff, partial failure and completion-once behavior.
- Added SQLite restart continuity and legacy linear-DAG mapping.
- Added 13 Phase 04 tests, bringing the total suite to 43 tests.

## Files added

- `core/work/__init__.py`
- `core/work/states.py`
- `core/work/intake.py`
- `core/work/graph.py`
- `core/work/planner.py`
- `core/work/scheduler.py`
- `core/work/services.py`
- `core/work/legacy.py`
- `tests/work/__init__.py`
- `tests/work/test_workflow.py`
- `docs/tasks/work-order-lifecycle.md`
- `docs/tasks/task-dag.md`
- `docs/tasks/scheduler.md`
- `docs/implementation/phase-04-report.md`

## Files changed

- `core/domain/enums.py`: added clarification/readiness, pause/block and wait/timeout lifecycle values.
- `core/domain/models.py`: added governed Work Order/Task fields, validation, serialization and transition edges.

## Migration and compatibility

No production route uses the new scheduler. CLI, server, dashboard, provider configuration, skills, plans and memory remain unchanged. Existing Phase 02/03 constructor and serialization tests pass because new fields have defaults. `LegacyPipelineAdapter` only projects sequential steps; it never invokes or replaces `_run_pipeline`. No feature flag is added to production config until an integration phase can test both modes end to end.

## Security considerations

Invalid graphs cannot dispatch. Tasks need accountable roles and unique idempotency keys. Required permissions/artifacts and Work Order approval are code-checked. External-action Tasks force plan approval. Budgets, timeouts and retry exhaustion are enforced before dispatch. The dispatcher is still a port: tests use pure mocks and perform no external actions. Legacy unsandboxed execution remains unchanged and outside this phase.

## Commands executed

- Read Phase 04 prompt and inspected Git, domain, repositories and SQLite implementation.
- `python -m unittest discover -s tests -v`
- `$env:PYTHONIOENCODING='utf-8'; python selftest.py`
- `python -m compileall -q core tests`
- Required-file and architecture-boundary checks.
- `git status`, `git diff --check`, staged diff/stat/name checks.
- Final commit command recorded after completion.

## Test results

Implementation suite currently passes **43 tests**. Coverage includes valid/cyclic/invalid DAGs, parallel and sequential readiness, dependency failure, pause/resume, cancellation propagation, retry exhaustion and attempt tokens, human input/approval waits, budget exhaustion, idempotent replay, completion-once events, SQLite restart and legacy linear mapping.

Final suite: **43 passed**. `compileall` completed without errors. Final UTF-8 legacy self-test: **41 passed / 2 pre-existing failures**, identical to baseline. All required Phase 04 documents and components are present, and the domain package remains independent of provider SDKs, UI/server, SQLite and filesystem details.

## Known limitations

- Scheduler is synchronous and local; there are no distributed leases, queues or outbox.
- Idempotency results are cached in-process per dispatcher; persisted Task state protects normal restart, but crash consistency around a real external action needs a durable ledger before production use.
- Planner accepts already structured data and does not call an LLM directly.
- Approval is a Work Order boolean foundation, not yet an authenticated/version-bound ApprovalRequest lookup.
- Required artifacts and permissions are supplied as approved ID sets in `SchedulingContext`; later services must build them from authoritative repositories.
- Artifact version creation and immutable-output deduplication are not implemented in this phase.
- Production orchestration feature flags are documented but intentionally not enabled.

## Follow-up

Stop after commit. The next separately authorized phase should implement code-enforced policy/approval evaluation and durable audit/idempotency records before connecting organization mode to external or legacy execution.
