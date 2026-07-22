# Phase 06 implementation report

## 1. Summary of implementation

Phase 06 introduces fail-closed governance and safe execution boundaries: versioned constitutions, deterministic policy decisions, scoped permissions, exact approval binding, multi-dimensional budgets, secret/redaction/audit services, action/risk classification, sandbox contracts and execution modes. Legacy host installation now requires explicit `legacy_unsafe`; the default is `dry_run`.

## 2. Architecture decisions

- Governance lives in `core.governance` and is independent of LLM requests.
- Missing policy rules deny by default and return an explanation.
- Permission, policy, approval and budget checks remain separate controls.
- Approval arguments use canonical JSON SHA-256 binding.
- Filesystem authorization resolves paths and symlinks before workspace containment and glob checks.
- Subprocess execution is clearly labeled a development restriction adapter, not a security sandbox.
- Legacy recalled context is supplied as untrusted user data rather than trusted system instructions.

## 3. Files created

- `core/governance/__init__.py`
- `core/governance/models.py`
- `core/governance/policy.py`
- `core/governance/permissions.py`
- `core/governance/services.py`
- `core/governance/sandbox.py`
- `tests/governance/__init__.py`
- `tests/governance/test_governance.py`
- `docs/security/threat-model.md`
- `docs/security/permission-model.md`
- `docs/security/sandbox.md`
- `docs/security/approval-model.md`
- `docs/implementation/phase-06-report.md`

## 4. Files modified

- `core/autoinstall.py`: host package installation disabled unless `legacy_unsafe` is explicit.
- `core/llm.py`: provider SDK recovery now uses the gated installer.
- `core/orchestrator.py`: host system-tool installation gated; legacy mode warning; recalled memory moved to an untrusted boundary.
- `core/config.py`: validated execution mode with safe default and unsafe-mode warning in descriptions.

## 5. Commands executed

- `python -m unittest discover -s tests/governance -v`
- `python -m unittest discover -s tests -v`
- `python -m compileall -q core tests`
- `$env:PYTHONIOENCODING='utf-8'; $env:JAVIS_EXECUTION_MODE='legacy_unsafe'; python selftest.py`
- Git status/diff/check commands recorded before commit.

## 6. Test results

- Governance suite: 10 passed, 1 skipped. The symlink escape test is skipped on this Windows host because creating a symlink is not permitted; traversal and containment tests pass, and the implementation resolves symlinks before containment checks.
- Full unit suite: 66 passed, 1 skipped.
- Python compilation: passed.
- Legacy offline self-test in explicit compatibility mode: 41 passed, 2 failed. These are the pre-existing metadata normalization and `cv2`/`opencv-python` expectation mismatches documented in prior phases. The prominent unsafe-mode warning appeared as required.

## 7. Compatibility impact

CLI/provider/skill behavior remains available, but autonomous package and system-tool installation is intentionally no longer the default. Users requiring the historical behavior must explicitly set `JAVIS_EXECUTION_MODE=legacy_unsafe`. Mock and existing unit-test providers remain offline and require no paid credentials.

## 8. Security impact

- Host mutation is blocked by default.
- Filesystem traversal, symlink escape, implicit network and non-allowlisted commands fail closed.
- Workers cannot exceed parent permission scopes.
- Approvals cannot be replayed after argument, actor, task, Work Order, constitution or expiration changes.
- Budget exhaustion returns controlled block and escalation information without consuming denied usage.
- Secret redaction occurs before audit persistence; raw secrets are not exposed by the broker outside action scope.
- Prompt-injection content is retained as data, never promoted into trusted policy sections.
- Fixed HTML rendering continues to escape model-supplied task/step text.

## 9. Known limitations

- A production container/VM sandbox adapter is not included; the subprocess adapter cannot enforce CPU, memory, process or network isolation.
- Permission globs are exact declarative scopes; hierarchical scope-subset reasoning beyond exact entries is intentionally conservative.
- YAML parsing is dependency-free through already-parsed declarative dictionaries; loading raw YAML text requires a future adapter.
- Scheduler integration must translate `BudgetResult.blocked` into persisted task transitions and collaboration escalation messages.
- The Windows CI environment should run the symlink test with Developer Mode or elevated symlink permission for direct coverage.

## 10. Recommended next phase

Wire governance decisions into the scheduler/tool dispatch transaction boundary and add a production sandbox adapter in the next prescribed phase. Phase 06 stops here as requested.
