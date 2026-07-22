# Phase 02 Report

## Objective

Introduce the independent foundation domain model, repository contracts, in-memory and SQLite persistence, schema migrations and an observability-only legacy adapter without replacing the legacy runtime.

## Repository state discovered

Phase 01 documentation was committed. `AGENTS.md` had subsequently been committed separately and the working tree was clean at Phase 02 start. Production remained the single `SkillAgent`; there was no `tests/` directory, domain package, repository boundary, database or migration mechanism. Legacy memory remained JSONL and jobs remained process-local.

Baseline UTF-8 self-test was 41 passed and 2 failed. Both failures were already documented in Phase 01: legacy `parameters` normalization expectation and `cv2` versus `opencv-python` package-name expectation.

## Design decisions

- Use frozen dataclasses and explicit enums; mutation-like operations return new versioned aggregates.
- Require stable string IDs and timezone-aware UTC timestamps at domain boundaries.
- Inject clock and ID generator protocols, with system and deterministic implementations.
- Keep repository ports generic and domain-owned; use deep-copying in-memory adapters and standard-library SQLite locally.
- Store aggregate JSON behind repositories for the MVP while isolating SQL for later PostgreSQL/typed-schema replacement.
- Use optimistic versions to prevent lost updates.
- Reject raw secret-shaped fields before SQLite serialization.
- Keep the legacy projection and JSONL memory adapter observability-only; do not route production traffic.

## Implementation completed

- Added all required organization, agent, work-management, governance, artifact and trace models.
- Added Task transition validation, explicit reopen, dependency invariants, separation of duties, budget enforcement, approval validation and artifact provenance.
- Added JSON-compatible serialization and explicit aggregate deserialization.
- Added repository protocols and named in-memory repositories.
- Added SQLite CRUD, durable restart behavior, optimistic concurrency and ordered idempotent migrations.
- Added deterministic legacy invocation projection and JSONL memory delegation.
- Added 17 offline unit/integration tests and domain/storage documentation.

## Files added

- `core/domain/__init__.py`
- `core/domain/base.py`
- `core/domain/enums.py`
- `core/domain/models.py`
- `core/repositories/__init__.py`
- `core/repositories/ports.py`
- `core/repositories/memory.py`
- `core/persistence/__init__.py`
- `core/persistence/migrations.py`
- `core/persistence/sqlite.py`
- `core/compatibility/__init__.py`
- `core/compatibility/legacy.py`
- `tests/__init__.py`
- `tests/domain/__init__.py`
- `tests/domain/test_models.py`
- `tests/persistence/__init__.py`
- `tests/persistence/test_repositories.py`
- `tests/compatibility/__init__.py`
- `tests/compatibility/test_legacy.py`
- `docs/domain/domain-model.md`
- `docs/storage/local-persistence.md`
- `docs/implementation/phase-02-report.md`

## Files changed

No pre-existing production file was modified. New packages are additive and not imported by the legacy runtime.

## Migration and compatibility

Legacy CLI, server, dashboard, provider/config behavior, skill contracts, plan files and JSONL memory are unchanged. `LegacyInvocationAdapter` creates a connected domain projection only; it never executes or redirects a task. `LegacyMemoryAdapter` calls the existing `Memory` implementation against the same files. No SQLite production path is selected automatically and no existing data is migrated or deleted.

## Security considerations

The domain establishes explicit capability/tool-grant types, risk, permission, policy and approval records but does not yet enforce them in production. Artifact provenance and separation-of-duties checks are code-enforced foundations. SQLite rejects common raw secret field names and model profiles exclude credentials. SQLite payloads are not encrypted; callers must select a protected location. The legacy runner remains unsandboxed and autonomous installation remains unchanged because production integration is outside Phase 02.

## Commands executed

- Read Phase 02 prompt and re-inspected Git/core/docs state.
- `git status --short`, `git log -3 --oneline`
- `$env:PYTHONIOENCODING='utf-8'; python selftest.py`
- `python -m unittest discover -s tests -v`
- `python -m compileall -q core tests`
- Required-file, import-boundary and documentation checks
- `git diff --check`, `git diff --stat`, `git diff`, staged diff checks
- Final commit command recorded after completion.

## Test results

Initial new suite: 17 tests passed. Coverage includes JSON round trips, invalid construction, every Task transition, explicit reopen, dependency uniqueness, budgets, reviewer/author separation, approval decisions, artifact provenance, all named repository contracts, in-memory and SQLite CRUD, restart durability, migration idempotency, optimistic locking, secret rejection, legacy projection and JSONL memory compatibility.

Final new suite: **17 passed**. Final UTF-8 legacy self-test: **41 passed / 2 pre-existing failures**, identical to baseline. `compileall` completed without errors, all required Phase 02 documents were present, and the domain package check found no dashboard, server, provider SDK, SQLite or filesystem dependency.

## Known limitations

- Domain foundations are not connected to production execution, API or dashboard.
- Only Task has a complete transition service in this phase; other lifecycle enums are bounded foundation values for later aggregate services.
- SQLite uses a generic JSON entity table; future query-heavy use may require typed projections or tables.
- Secret-name rejection is not encryption or comprehensive data-loss prevention.
- Automatic migration rollback is not supported; documented backup/restore is required.
- Audit append-only behavior is an application rule to be enforced by the future audit service.
- The two legacy self-test failures and CP1252 console behavior remain outside this phase's scope.

## Follow-up

Stop after commit. The next separately authorized phase should build policy, approval, budget and audit application services on these ports before any governed execution cutover.
