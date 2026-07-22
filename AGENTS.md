# AGENTS.md — Permanent instructions for Codex

## Project mission

Upgrade the existing Skill Agent project into an **AI Software Company runtime** while preserving all working legacy capabilities.

The system must model an organization composed of role agents, temporary worker agents and control/reviewer agents. It must accept high-level goals, create governed work orders, execute a dependency graph, produce auditable artifacts and require human approval for risky or externally visible actions.

## Existing capabilities that must remain operational

Preserve and test these behaviors throughout the migration:

- CLI interactive and one-shot modes.
- Web dashboard and voice interaction.
- Chat model and work/reasoning model separation.
- Anthropic, Gemini, OpenAI, DeepSeek and mock providers.
- Skill registry and skill reuse.
- Skill generation.
- Static validation, smoke testing and bounded auto-fix.
- Parameter extraction and self-fill.
- Multi-step task execution.
- Memory recall.
- Hermes/OpenAI-style tool schemas.
- Offline self-test using the mock provider.
- Existing configuration compatibility whenever reasonably possible.

## Core engineering rules

1. Inspect existing source before changing architecture.
2. Source code is more authoritative than README documentation.
3. Prefer incremental migration over a big-bang rewrite.
4. Keep public APIs compatible or add explicit adapters.
5. Do not delete legacy modules until replacements are tested and migration is documented.
6. Keep changes scoped to the current phase.
7. Do not silently add heavyweight frameworks.
8. Use standard-library solutions when sufficient, but create clear abstractions for later production replacements.
9. All domain objects require stable IDs and explicit serialization.
10. All workflows require deterministic states and transition validation.
11. LLM output must be treated as untrusted input.
12. Policies, permissions, budgets and approval rules must be enforced in code, not only prompts.
13. Generated skills must never gain unrestricted host access.
14. Never auto-install packages or system tools on the host in production mode.
15. All important actions must emit structured events and audit records.
16. Tests must not require paid API keys.
17. Every phase must update documentation and tests.

## Architecture principles

- Domain-driven boundaries without unnecessary ceremony.
- Ports and adapters around persistence, LLM providers, execution and artifact storage.
- Structured messages instead of unrestricted agent-to-agent prose.
- Manager-worker, handoff and evaluator-review patterns.
- DAG-based task orchestration.
- Idempotent execution where possible.
- At-least-once execution must not duplicate irreversible actions.
- Human-in-the-loop for risky actions.
- Ephemeral workers rather than permanently active agent swarms.
- One accountable owner per Work Order and Task.
- Artifacts are immutable or versioned.
- Memory promotion requires validation and provenance.
- Every execution is budget constrained.

## Security baseline

- Deny by default.
- Least privilege.
- Explicit file and network scopes.
- Secret redaction.
- Prompt injection boundaries.
- No arbitrary shell by default.
- No raw model-generated HTML execution.
- No host package installation by autonomous agents.
- Sandboxed or dry-run execution for generated code.
- Approval before production deployment, sending messages, deleting data, installing dependencies, changing permissions or accessing secrets.

## Required output after every implementation phase

End each phase with:

1. Summary of implementation.
2. Architecture decisions.
3. Files created.
4. Files modified.
5. Commands executed.
6. Test results.
7. Compatibility impact.
8. Security impact.
9. Known limitations.
10. Recommended next phase.

Create or update a phase report in:

```text
docs/implementation/phase-XX-report.md
```

## Coding standards

- Use type hints for new Python code.
- Prefer dataclasses or validated domain models.
- Define enums for bounded states.
- Avoid mutable global state.
- Inject clocks, ID generators and providers when tests need determinism.
- Provide docstrings for public classes and functions.
- Use JSON-compatible values at domain boundaries.
- Never expose provider secrets in logs.
- Prefer explicit error types over broad exceptions.
- Keep orchestration separate from UI and provider integrations.
- Write tests for state transitions, policy decisions and failure paths.

## Stop conditions

Stop and report instead of guessing when:

- A change would irreversibly remove user data.
- Existing behavior cannot be identified from code or tests.
- A security boundary requires a platform capability not available in the repository.
- A migration requires credentials.
- A task would perform real external actions during tests.

Use mocks, fixtures, dry-run adapters or clearly documented placeholders instead.
