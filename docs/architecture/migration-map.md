# Incremental migration map

## Phase sequence

The sequence below is a blueprint, not authorization to implement later phases. Each phase must be separately prompted, tested, reported and committed.

1. Discovery and architecture baseline (this phase).
2. Foundational domain types, stable IDs, serialization and transition tests.
3. Persistence and event/audit ports with filesystem/in-memory adapters.
4. Governance: capabilities, policies, budgets and approval records.
5. Goals, Work Orders and deterministic task DAG orchestration.
6. Organization roles, ephemeral agents and structured collaboration.
7. Scoped execution adapter, skill quarantine and artifact provenance.
8. Layered memory and knowledge promotion adapters.
9. Additive API/dashboard organization views and approval UX.
10. Offline end-to-end evaluation, compatibility hardening and controlled cutover.

## Component destinations

| Existing component | Temporary adapter | Target component | Removal conditions |
|---|---|---|---|
| `SkillAgent.handle_message` | `LegacyConversationAdapter` preserving response dictionaries | Goal intake application service + Product Manager clarification | CLI/API contract tests pass; feature flag rollback exists; all clients use versioned DTOs. |
| `SkillAgent.execute_task` | `LegacySkillAgentAdapter` implementing a generic execution facade | Work Order service + DAG orchestrator | Governed E2E parity covers existing/missing skills, recovery and pipelines; legacy traffic is zero for a release. |
| `_plan` and `core.planner` | Legacy plan renderer attached as an artifact adapter | Structured Work Order plan + versioned artifact renderer | Dashboard consumes plan DTOs and old `/plans/` links remain readable or migrated. |
| `_decompose` / `_run_pipeline` | Linear-plan-to-DAG adapter assigning stable task IDs and sequential edges | Deterministic DAG scheduler | Persisted resume, dependency, retry, idempotency and failure tests pass. |
| `Registry` | Legacy skill catalog adapter exposing normalized descriptors | Skill catalog context | Every legacy skill loads through quarantine-safe metadata inspection; no top-level execution on discovery. |
| `runner.run_skill` | Legacy in-process executor allowed only for explicitly trusted skills | Scoped execution port + sandbox adapter | Capability enforcement, timeout, isolation and artifact capture pass on supported platforms. |
| `generator.generate/fix/validate` | Generated-skill quarantine adapter | Skill lifecycle and validation service | Generated code never enters trusted registry before static/smoke/security gates; provenance is persisted. |
| `_recover` and auto-install | Recovery recommendation adapter in dry-run by default | Policy-governed recovery commands | Package/tool installation requires explicit matching approval and is executed by a scoped adapter; no autonomous host install remains. |
| `Memory` JSONL | `LegacyMemoryAdapter` retaining file formats | Layered memory/knowledge ports | Provenance-aware migration is verified; recall parity and rollback are tested; original files are retained. |
| `plans/*.html` | Read-only legacy artifact adapter | Immutable/versioned artifact store | All references are mapped to artifact IDs and historical links remain resolvable. |
| `memory/facts.jsonl` | Imported fact records marked `legacy/unverified` | Validated knowledge store | Promotion/provenance rules exist and an audited importer has completed without data loss. |
| `server.py` handlers | Versioned legacy HTTP adapter around application services | UI/API context | Endpoint compatibility tests pass; auth/input limits/approval enforcement exist; dashboard is migrated. |
| In-memory `JOBS` | Job repository port backed initially by in-memory adapter | Durable task execution records and scheduler leases | Restart/resume and duplicate-dispatch tests pass. |
| `/api/approve` and `/api/reject` | Legacy UI action translated to a scoped approval command where possible | Governance approval service | Approval is authenticated, persisted, version-bound, expiring and enforced before dispatch. |
| React plan card/controller | Compatibility view model | Organization/Work Order dashboard | UI shows authoritative server state, roles, DAG, budgets, approvals, artifacts and audit trace. |
| `Config` chat/work roles | Legacy provider configuration adapter | Agent/model policy and LLM provider port | Existing JSON/env configurations resolve identically and role mappings are migrated with fallback. |
| `LLM` provider methods | `LegacyLLMAdapter` | LLM completion port with budgets/redaction/trace | Provider parity and offline mock contract tests pass; SDK install side effects are removed. |
| `selftest.py` | Invoked as a compatibility subprocess test | Pytest/unittest suites plus offline E2E harness | Every current assertion is represented, isolated and stable; legacy script may remain as a smoke entry point. |
| CLI `agent.py` | Legacy command adapter | Goal/Work Order CLI commands | Interactive and one-shot compatibility tests pass with a documented mode switch. |
| Hermes helpers | Tool-schema adapter | Capability-aware skill descriptor protocol | Schema compatibility tests pass and tool calls cannot bypass policy/execution ports. |

## Compatibility gates per phase

Each phase must run the UTF-8 mock self-test, its new unit/integration tests, and any available dashboard build checks. It must record pre-existing failures separately. Public response dictionaries, endpoint paths, config resolution, persisted formats and skill contracts remain unchanged unless an explicit versioned adapter and migration note are included.

## Cutover and rollback

New runtime data is written to separate namespaced storage until migration is proven. Feature flags must permit request-level rollback to the legacy adapter without deleting data. Legacy modules remain present and tested until removal criteria in this map are satisfied; cleanup is a separate approved phase, never an incidental refactor.
