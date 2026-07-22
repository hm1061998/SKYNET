# Retrospective checkpoint — Phase 11

Scope: testing, migration and backward compatibility, reviewed against the current release tree.

## Findings

- **Compatibility:** safe defaults keep legacy enabled and organization opt-in. JSONL remains untouched; migration is optional, dry-run first, backed up and fingerprint-idempotent.
- **Boundaries:** fixtures use mock/fake adapters; no paid key, Docker, network, install or external action is required. Compatibility adapters remain isolated from company workflow code.
- **Persistence/restart:** SQLite scheduler restart/resume and repeatable migration are covered. Database lock and artifact-write rollback preserve committed/recoverable state.
- **Failure visibility:** provider timeout, malformed output, audit failure, approval expiry, sandbox timeout, worker crash and unavailable dependency fail visibly.
- **State/budget/approval:** E2E scenarios cover budget exhaustion, policy denial and human rejection; full state-machine/governance suites remain green.
- **Documentation drift:** compatibility matrix, test strategy and migration guidance match current commands. Release docs supersede the old assumption that safe mode auto-installs dependencies.
- **Critical finding found during this playbook review:** generated source was written and loaded by Registry before static validation, allowing model-generated module-level execution. Fixed by `validate_generated_source()` before every generated/fixed source write/return. Regression tests reject top-level calls/imports and definition-time calls while permitting literal metadata and lazy imports inside `run`.

## Decision

Critical generated-skill load defect resolved with a minimal boundary fix. Existing manually installed legacy skills remain compatible. Real sandbox and commercial production controls remain blockers.
