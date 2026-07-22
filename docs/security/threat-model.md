# Threat model

## Assets and trust boundaries

Protected assets are workspace data, credentials, provider budgets, host integrity, production systems, audit history and human-facing communications. LLM output, generated skills, external documents, tool responses and recalled external content are untrusted. Policy configuration, explicit approvals and runtime-enforced scopes are trusted only after validation.

## Attack scenarios and mitigations

| Scenario | Mitigation |
|---|---|
| A document says to ignore policy and disclose a token | External content stays in untrusted user/data sections; authorization is evaluated independently; secrets are redacted before model use. |
| Generated code requests `pip`, `winget`, `apt`, `brew` or `choco` | Default `dry_run` blocks host installation. Only explicit `legacy_unsafe` restores compatibility and prints a warning. |
| A worker asks for a broader file/command/network scope | Worker permissions must be a subset of the parent's exact scopes. |
| `../` or a symlink targets data outside the workspace | Paths are resolved and required to remain below the workspace before glob matching. |
| A prior approval is replayed with changed arguments | Approval binds to the canonical SHA-256 of exact action and arguments, actor, task, Work Order, constitution version and expiration. |
| Model output triggers network exfiltration | Network is empty/denied by default and exact-host allowlisting is independently required. |
| An autonomous loop consumes unlimited resources | Eight budget dimensions are checked before consumption; denial blocks and emits escalation data. |
| Logs leak secrets | Recursive key/value redaction runs before governance audit persistence; SQLite also rejects raw sensitive keys. |
| Model-generated HTML executes script | Existing plan renderer escapes task and step text and renders a fixed template. Raw model HTML is not accepted as executable UI. |

## Residual risks

`RestrictedSubprocessExecutor` is explicitly a development adapter, not a security sandbox. It cannot enforce CPU, memory, process or network isolation and must not be used as the production sandbox. Python process memory and third-party provider SDK behavior remain part of the trusted computing base. Production deployment requires a real container or OS sandbox adapter implementing the same contract.
