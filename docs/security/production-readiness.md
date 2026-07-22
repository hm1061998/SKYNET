# Production readiness assessment

## Implemented

Deny-by-default policy evaluation, scoped permissions, exact approval hashes, budget gates, validated state machines, immutable/versioned artifacts, provenance, permission-aware memory retrieval, secret redaction, prompt trust boundaries, bounded repair/retry, safe configuration defaults, offline tests, and simulated replay are implemented and tested.

## Simulated or development-only

- Offline mock workflow and human approval are simulations.
- `DryRunExecutor` and `FakeSandboxExecutor` execute nothing.
- `RestrictedSubprocessExecutor` is a development convenience and **not a security sandbox**.
- Local append-only hash chains detect application-level mutation but are not externally anchored/WORM.
- Dashboard organization data is an MVP projection, not a multi-tenant production control plane.

## Required before commercial production

- Strong OS/container/VM isolation with filesystem, network, process and resource enforcement.
- Authentication, tenant isolation, RBAC/ABAC and CSRF/session hardening behind a production web server.
- Managed secret broker/KMS and short-lived credentials.
- Durable queues, idempotent effect ledger, HA database, migrations, retention and disaster-recovery drills.
- Central telemetry with access controls, retention and external audit anchoring.
- Dependency/SBOM/license review, pinned supported versions and vulnerability response.
- Real provider contract tests, deployment approvals, rollback automation and environment-specific SLO/load tests.
- Independent security review and organization-specific legal/compliance assessment.

No compliance certification is claimed. No project license file is currently present; distribution/commercial terms must be resolved before release outside the owner’s environment. npm packages are declared in `package.json`; optional Python provider SDKs are listed in `requirements.txt`. Operators must review their licenses and pin/scan production dependencies.
