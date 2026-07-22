# Security review before real execution

Conclusion: **real external/production actions remain disabled**. The offline MVP may be used with mock/dry-run adapters. Do not treat the development subprocess adapter as isolation.

| Threat | Implemented controls | Remaining gap / decision |
|---|---|---|
| Prompt injection | trusted/untrusted prompt sections, structured validation, policy in code | Continue adversarial provider/repository tests |
| Path traversal | resolved workspace scopes and generated artifact IDs | Run symlink test on a host with permission |
| Symlink escape | resolve-before-containment | Environment coverage gap on this Windows host |
| Secret leakage | secret broker, persistence rejection, recursive redaction, safe examples | Managed KMS/broker and log DLP needed |
| Dependency confusion | installation denied by default, package-name validation | Pin/hash/SBOM and private-index policy needed |
| Command injection | argument-vector subprocess, command allowlist, no shell | Replace development adapter with strong sandbox |
| Host package installation | only explicit `legacy_unsafe` compatibility mode | Never enable in production |
| Unauthorized network | policy + allowlist; development adapter rejects network scopes | Enforce at container/VM/network layer |
| Self-approval | separation of duties and exact grant actor/scope | Production identity/RBAC required |
| Approval replay | action/arguments hash, actor, task, Work Order, constitution, expiry | Durable consumed-grant/effect ledger needed |
| Budget bypass | scheduler allocation checks and budget manager | Central transactional accounting needed at scale |
| Memory poisoning | scope/owner/sensitivity filter, validation/provenance, reviewed promotion | Add production moderation/retention workflows |
| Unsafe HTML | React escaping and no raw HTML sink | CSP and production web hardening needed |
| Generated skill load | pre-write AST gate rejects module-level execution | Skill body still requires real sandbox at run time |

No compliance certification is claimed. External messaging, deployment, secret access, permission changes, destructive data operations and dependency installation require production-grade adapters plus human approval and must remain unavailable until the gaps above are resolved.
