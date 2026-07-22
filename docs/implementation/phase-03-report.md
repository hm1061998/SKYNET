# Phase 03 Report

## Objective

Build persistent role definitions, ephemeral worker foundations, control-agent constraints, audited lifecycle transitions, logical model routing, trusted prompt assembly and validated structured execution without implementing the full company workflow.

## Repository state discovered

Phase 02 had introduced independent domain models, repositories, SQLite migrations and compatibility adapters. The working tree was clean. There was no role-definition registry, worker factory, agent lifecycle service, model-profile router, prompt boundary or structured agent runtime. Existing production calls still used `SkillAgent` with `roles.chat` and `roles.work`.

Baseline tests: 17/17 new tests passed. UTF-8 legacy self-test remained 41 passed / 2 documented pre-existing failures.

## Design decisions

- Extend Phase 02 agent dataclasses additively so existing constructors and serialized records remain compatible.
- Use JSON definitions to avoid a new YAML dependency.
- Separate persistent definitions from ephemeral, versioned instances.
- Require explicit reduced worker capabilities; inheritance alone grants nothing.
- Treat control review and write permissions independently and reject self-review.
- Emit an `AuditEvent` synchronously for each successful lifecycle edge.
- Resolve logical model profiles through base, organization and role overrides.
- Keep vendor/provider details in runtime adapters, not domain rules.
- Separate trusted system sections from raw task/artifact user content.
- Validate exact structured result shape with at most two repair attempts.

## Implementation completed

- Extended `AgentStatus`, `AgentDefinition` and `AgentInstance` for the Phase 03 lifecycle and runtime metadata.
- Added `AgentRegistry`, JSON loader, hierarchy/cycle validation and repository persistence.
- Added `CapabilityResolver`, `AgentFactory` and worker expiration behavior.
- Added `AgentLifecycleManager` and a complete audited transition table.
- Added logical `ModelRouter`, prompt `AgentContext`/`PromptAssembler`, provider port and legacy adapter.
- Added `AgentExecutionResult` validation and bounded `AgentRuntime` repair/failure behavior.
- Added 13 agent-specific tests, bringing the total suite to 30 tests.
- Added the required agent, routing, prompt-boundary and phase report documents.

## Files added

- `core/agents/__init__.py`
- `core/agents/definitions.py`
- `core/agents/capabilities.py`
- `core/agents/factory.py`
- `core/agents/lifecycle.py`
- `core/agents/routing.py`
- `core/agents/prompting.py`
- `core/agents/providers.py`
- `core/agents/runtime.py`
- `tests/agents/__init__.py`
- `tests/agents/test_agents.py`
- `docs/agents/agent-model.md`
- `docs/agents/model-routing.md`
- `docs/agents/prompt-boundaries.md`
- `docs/implementation/phase-03-report.md`

## Files changed

- `core/domain/enums.py`: added the Phase 03 agent lifecycle states while retaining compatibility values.
- `core/domain/models.py`: added declarative role metadata and bounded worker-instance metadata with serialization/validation.

## Migration and compatibility

Production CLI, server, dashboard and `SkillAgent` are unchanged. Existing `roles.chat` and `roles.work` remain authoritative. `LegacyProviderAdapter` maps logical profiles to those roles only when explicitly instantiated. Phase 02 constructors and serialization tests continue passing. No existing definitions, memory, plans, skills or configuration are migrated.

## Security considerations

Worker grants must be subsets of parent and template capabilities. Worker creation requires task, parent, expiry, isolated context and budget references. Control agents cannot self-review and review does not imply write. Prompt trust boundaries are explicit and structured output is treated as untrusted. These controls do not yet replace the legacy unsandboxed runner, install behavior or dashboard approval convention.

## Commands executed

- Read the Phase 03 prompt and inspected Git, source, tests and Phase 02 domain/config/provider code.
- `python -m unittest discover -s tests -v`
- `$env:PYTHONIOENCODING='utf-8'; python selftest.py`
- `python -m compileall -q core tests`
- Required-file/import-boundary checks
- `git status`, `git diff --check`, staged diff/stat/name checks
- Final commit command recorded after completion.

## Test results

Initial agent implementation and compatibility suite: **30 passed**. Tests cover JSON definition loading, invalid/unknown/cyclic reporting lines, SQLite definition persistence, capability reduction, worker creation/expiration, all lifecycle transitions and audit events, control-agent separation, model override precedence, prompt trust separation, deterministic mock execution, bounded result repair, safe malformed-output failure and legacy chat/work mapping.

Final suite: **30 passed**. `compileall` completed without errors. Final UTF-8 legacy self-test: **41 passed / 2 pre-existing failures**, identical to baseline. All required Phase 03 documents are present, and the domain package remains free of dashboard, server, provider-SDK, SQLite and filesystem dependencies.

## Known limitations

- JSON is the only declarative definition format in Phase 03; YAML can be an optional later adapter.
- Agent definitions are persistent, while application-level assignment scheduling and durable instance updates are not yet implemented.
- Control-agent checks are foundations, not a complete policy/approval service.
- Model profile configuration is injectable in code; no new config-file schema or dashboard editor is added.
- The runtime validates proposed artifacts/tasks but does not apply them.
- Existing provider SDK auto-install and legacy skill execution remain unchanged.
- Compatibility enum values `IDLE`, `ACTIVE` and `RETIRED` are retained but excluded from the new lifecycle graph.

## Follow-up

Stop after commit. The next separately authorized phase should build governed Work Order planning/orchestration and policy services using these agent/runtime boundaries rather than connecting agents directly into a free-form swarm.
