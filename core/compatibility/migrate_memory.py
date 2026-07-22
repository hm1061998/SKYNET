"""CLI for optional legacy-memory migration."""
from __future__ import annotations

import argparse
import json

from .migration import LegacyMemoryMigrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Import legacy JSONL memory into SQLite")
    parser.add_argument("source")
    parser.add_argument("database")
    parser.add_argument("--apply", action="store_true", help="write after creating a backup")
    parser.add_argument("--backup-directory")
    args = parser.parse_args()
    report = LegacyMemoryMigrator(args.database).migrate(
        args.source, dry_run=not args.apply, backup_directory=args.backup_directory)
    print(json.dumps(report.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0 if report.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
