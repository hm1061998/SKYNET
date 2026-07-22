# Operations runbook

## Preflight

1. Run `python company_cli.py validate-release`.
2. Confirm execution mode is `dry_run` or a deployment-provided secure sandbox.
3. Confirm no secret value is stored in JSON/YAML; only environment-variable names may appear.
4. Run `python -m unittest discover -s tests -v` and `python company_cli.py run-evals`.
5. Verify backup/restore procedure before applying any migration.

## Normal operations

- Start legacy CLI with `python agent.py` or dashboard with `python server.py`.
- Run organization demo with `python company_cli.py offline-demo`.
- Inspect Work Orders/tasks/artifacts/approvals from dashboard APIs or `company_cli.py` read commands.
- Treat high-risk/external decisions as pending until exact action hash, scope, actor and expiration are approved.

## Failure response

- Provider timeout/malformed output: execution becomes visibly failed; retry only within configured bounds.
- Database lock: stop writers, retain committed state, investigate the lock, then resume from persisted tasks.
- Artifact failure: no version is committed; resolve storage capacity/permissions and retry idempotently.
- Audit failure: do not report the governed action as successful.
- Budget exhaustion: keep the task blocked and escalate for an explicit extension.
- Sandbox/dependency unavailable: preserve state; do not fall back to unrestricted host execution or autonomous installation.

## Rollback

Disable organization runtime in config, keep `legacy_enabled=true`, restore the database/artifact snapshot, and retain audit/evidence. Do not delete newer data until reconciliation is complete. See [backup and restore](backup-restore.md).
