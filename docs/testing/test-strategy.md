# Test strategy

The default suite is offline, deterministic, and requires neither Docker nor paid API keys. Run it from the repository root:

```powershell
python -m unittest discover -s tests -v
```

The pyramid is organized by responsibility:

- Unit suites cover domain invariants, state transitions, permissions, budgets, DAGs, context packaging, artifact hashing, review separation, memory promotion, and redaction.
- Integration suites cover SQLite repositories, mock provider boundaries, artifact persistence, event/audit behavior, approval and sandbox fakes, migration, and injected failures.
- End-to-end suites cover ten required legacy and organization workflows under `tests/e2e`.

Fixtures under `tests/fixtures` provide an in-memory repository, organization, constitution, role definitions, deterministic IDs/clock, mock model outputs, fake sandbox, sample artifacts, injection strings, corrupted results, and legacy JSONL. Fixtures contain no production credentials and never make real external calls.

Failure injection covers provider timeout, malformed JSON, database lock, artifact-write failure, worker crash, scheduler restart, audit failure, approval expiration, sandbox timeout, and missing dependencies. Expected behavior is an explicit error or bounded failure state while previously committed state remains recoverable.

The optional logical categories are represented by directories (`integration`, `e2e`, `migration`, governance/security, compatibility/legacy). The full command remains the CI source of truth; narrower discovery commands may be used during development.

The legacy `selftest.py` is additionally run with explicit compatibility mode. Its two historical failures—legacy `parameters` metadata normalization and the OpenCV missing-module expectation—are tracked as a stable pre-Phase-11 baseline and are not part of the green default unittest suite.
