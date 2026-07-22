# Retrospective checkpoint — Phase 08

Scope: AI Software Company roles and feature-delivery workflow, reviewed against the current tree and Phase 08 report.

## Findings

- **Compatibility:** organization templates/workflow are additive. Legacy agent/provider/skill/memory modules are neither imported nor replaced by `core.company`.
- **Boundaries:** seven persistent role definitions and reduced ephemeral workers use the agent domain/factory. Workflow writes through the artifact port and emits structured operational events.
- **Separation of duties:** developer self-approval, architect code approval, reviewer release, unauthorized criteria changes and production deployment without human approval are denied in code.
- **Artifacts/review:** code review, QA and security reports bind exact candidate hashes; artifact versions preserve producer/task provenance. The release checkpoint corrected dashboard projection provenance for review/security/delivery paths.
- **Budgets/approval:** mock workflow records bounded token/tool cost and blocks final delivery without human approval. It performs no real deploy/network/install.
- **Duplication:** the deterministic mock workflow is explicitly a demo/eval fixture, not a second production scheduler.
- **Tests/docs:** happy path, revision, QA repair, approval block, role definitions and separation rules are covered. Documentation identifies simulation boundaries.

## Decision

No unresolved critical Phase 08 defect. Persisting the mock workflow through the general scheduler remains future integration work and is not represented as production-complete.
