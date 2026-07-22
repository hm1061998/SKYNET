# Changelog

## 0.12.0 — 2026-07-22

- Integrated legacy Skill Agent and governed AI Software Company MVP.
- Added stable domain models, repositories, agent runtime, task DAG scheduling, collaboration/review, governance, layered memory/artifacts, organization template/workflow, dashboard projection, observability/KPI/evals, compatibility migration, offline demo and release CLI.
- Added safe configuration examples, constitution/model profiles, operations/security documentation and 129-test release suite.
- Preserved the explicit legacy self-test baseline (41 pass, 2 historical expectation failures).

### Security and compatibility

- Safe default is legacy enabled, organization disabled and dry-run execution.
- Host auto-install is denied unless development-only `legacy_unsafe` is explicitly selected.
- No API key is required for offline demo/tests; examples reference environment-variable names only.

### Dependency and license note

The offline Python path uses the standard library. Frontend and optional provider dependencies remain declared in `package.json` and `requirements.txt`; production releases must pin, scan and review licenses. The repository currently has no project license file, which remains a distribution blocker.
