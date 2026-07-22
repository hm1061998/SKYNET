# Legacy compatibility matrix

Phase 11 keeps the original Skill Agent path enabled by default and places the organization runtime behind explicit feature flags. Additive adapters project legacy invocations and memory without rerouting or rewriting them.

| Legacy capability | Before | After | Adapter / seam | Test |
|---|---|---|---|---|
| CLI chat | Available | Preserved | Existing CLI and provider roles | legacy self-test chat |
| One-shot task | Available | Preserved | `LegacyInvocationAdapter` observes task projection | compatibility tests |
| Dashboard message | Available | Preserved | Existing `/api/message` route | dashboard source smoke |
| Approval | Available | Preserved; governed approval added | legacy routes plus approval service | dashboard/governance tests |
| Skill lookup | Registry lexical/model lookup | Preserved | Existing `Registry` | E2E resize fixture |
| Skill generation | Generated Python skill | Preserved in explicit execution mode | existing generator/validation | legacy self-test |
| Auto-fix | Bounded repair | Preserved | existing generator/runtime repair | agent and legacy self-test |
| Self-fill | Parameter extraction | Preserved | registry normalization/extraction | E2E resize and legacy self-test |
| Pipeline | Sequential steps | Preserved and projectable as DAG | `LegacyPipelineAdapter` | E2E pipeline/work tests |
| Memory recall | JSONL | Preserved untouched | `LegacyMemoryAdapter`/`LegacyKnowledgeAdapter` | compatibility/knowledge tests |
| Mock self-test | Offline | Preserved | mock provider | legacy baseline and full unittest suite |

Central flags are parsed by `RuntimeFeatureFlags`. With no new configuration, `organization_enabled=false`, `legacy_enabled=true`, execution is `dry_run`, unsafe legacy execution is disallowed, storage is SQLite, and UI mode is legacy. Invalid combinations fail closed. Existing flat `execution_mode` remains readable for compatibility.

The default suite verifies provider separation, registry behavior, pipelines, memory recall, legacy dashboard routes, mock execution, and all organization-domain paths without paid keys.
