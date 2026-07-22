# Local persistence

## Repository boundary

`core/repositories/ports.py` defines minimal CRUD contracts for organizations, agent definitions/instances, goals, work orders, tasks, artifacts, approvals, audit events and budgets. Domain code does not import SQLite or filesystem modules. Persistence implementations store domain representations and enforce concurrency mechanics; they do not define lifecycle or policy rules.

`InMemoryRepository` is thread-safe and deep-copies values at its boundary. `InMemoryRepositories` exposes all required named repositories for tests and ephemeral use.

## SQLite MVP

`SQLiteStore` owns a standard-library `sqlite3` connection and creates typed `SQLiteRepository` instances. The MVP uses one isolated `entities` table:

| Column | Purpose |
|---|---|
| `collection` | Repository namespace such as `goals` or `tasks`. |
| `id` | Stable domain string ID. |
| `entity_type` | Serialized aggregate type for inspection/migration. |
| `version` | Positive optimistic-lock version. |
| `payload` | JSON representation produced by the domain object. |
| `updated_at` | UTC database update timestamp. |

The `(collection, id)` pair is the primary key. SQL remains inside `core/persistence/`; PostgreSQL or typed-table adapters can replace it later without moving domain invariants.

```python
from core.domain import Goal
from core.persistence import SQLiteStore

with SQLiteStore("runtime-data/company.db") as store:
    goals = store.repository("goals", Goal)
    goals.add(goal)
    loaded = goals.get(goal.id)
```

No database is created by importing the package. Callers explicitly choose a path. Phase 02 does not create a production database, read or migrate legacy JSONL, or alter `config.json`.

## Optimistic concurrency

Mutable aggregates expose a positive `version`. `save(entity, expected_version)` updates only a row whose current version matches the expectation, and the new entity version must advance. A stale or missing row raises `ConcurrentUpdateError`. Deletes also require the expected version. This prevents silent lost updates across processes; callers remain responsible for retry policy.

Audit events are intended to be append-only. The common repository contract exists for compatibility, but application services should add them and never update them.

## Schema migration

`core/persistence/migrations.py` contains ordered `Migration` values. Startup creates `schema_migrations`, reads applied versions and executes each pending migration in its own transaction. Applied versions are skipped, making startup migration idempotent. Tests run the migrator twice and reopen a file-backed database to verify durability.

Rules for future migrations:

1. Never edit an applied migration; append a higher version.
2. Make forward changes safe for the immediately previous application version during rolling upgrades.
3. Back up the SQLite file before destructive or data-transforming migrations.
4. Write an offline verification and restore procedure in the phase report.
5. Prefer expand/migrate/contract steps; contract removal requires a separate approved phase.

Automatic down migrations are intentionally unsupported. Rollback means stop writers, preserve the failed database for diagnosis, restore the pre-migration backup, and deploy the prior application version. For additive migrations, application rollback may leave unused tables/columns in place until a later governed cleanup.

## Secret handling

Model profiles store provider/model identifiers but no API keys. SQLite serialization recursively rejects fields named `api_key`, `secret`, `password`, `access_token` or `refresh_token`. This is a defense-in-depth guard, not a substitute for DTO allowlists and redaction in later application layers.

## Legacy JSONL

`LegacyMemoryAdapter` delegates to the existing `core.memory.Memory`; it does not import facts into SQLite, rewrite files or change recall behavior. A future migration must preserve provenance, mark legacy facts unverified and retain rollback copies. No existing storage is deleted or silently migrated in Phase 02.
