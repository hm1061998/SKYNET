# Legacy memory migration

Existing `memory/*.jsonl` files remain the source of truth and are never modified by migration. Read-only compatibility adapters can continue using them indefinitely. Migration into a SQLite import table is optional.

Preview first:

```powershell
python -m core.compatibility.migrate_memory memory/facts.jsonl data/runtime.db
```

Apply only after reviewing the JSON report:

```powershell
python -m core.compatibility.migrate_memory memory/facts.jsonl data/runtime.db --apply --backup-directory data/backups
```

Dry-run creates neither database nor backup. Apply mode creates a byte-for-byte `.bak` before importing. Each canonical record receives a SHA-256 fingerprint; reruns skip imported fingerprints and do not duplicate records. The report counts `imported`, `skipped`, `conflicted`, and `failed` entries. Duplicate source records are conflicts, malformed lines fail, and records containing secret-key fields are skipped. Error descriptions include line numbers/categories only, never secret values.

Before a production migration, copy backups to separately protected storage, validate filesystem permissions, test restore, and retain the JSONL source until record counts and recall behavior have been accepted. The local importer is a compatibility utility, not a tenant authorization or retention system.
