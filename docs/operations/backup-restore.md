# Backup, restore and rollback

## Backup

Stop writers or obtain a consistent SQLite snapshot. Copy the SQLite database (including WAL/SHM when applicable), artifact root, organization/policy config, and legacy JSONL memory to a protected versioned location. Never write backup secrets to logs. Record hashes and test readability.

The optional memory importer creates a content-addressed `.bak` before apply:

```powershell
python company_cli.py migrate-memory memory/facts.jsonl data/runtime.db --apply --backup-directory data/backups
```

## Restore drill

1. Keep the failed/current data read-only.
2. Restore into a new directory, not over the only copy.
3. Open SQLite with the application migration code and verify entity counts.
4. Verify artifact hashes and audit chain.
5. Run offline evals and smoke tests.
6. Switch the deployment path only after human review.

## Rollback release

Set organization disabled and legacy enabled, use `dry_run`, restore the last accepted data/config snapshot, and restart. Reconcile events created after the snapshot before any external effect. Source-code rollback does not imply data rollback; schema downgrade is not automated in this MVP.
