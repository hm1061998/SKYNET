from __future__ import annotations

import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from core.domain import Goal, GoalStatus
from core.persistence import SQLiteStore, migrate
from core.repositories import ConcurrentUpdateError, InMemoryRepositories, RepositoryError

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class RepositoryTests(unittest.TestCase):
    def make_goal(self) -> Goal:
        return Goal("goal_1", "Build", "desc", "owner", GoalStatus.DRAFT, NOW)

    def exercise_crud(self, repository) -> None:
        goal = self.make_goal()
        repository.add(goal)
        self.assertEqual(goal, repository.get(goal.id))
        self.assertEqual([goal], repository.list())
        changed = replace(goal, status=GoalStatus.ACTIVE, version=2)
        repository.save(changed, expected_version=1)
        self.assertEqual(changed, repository.get(goal.id))
        with self.assertRaises(ConcurrentUpdateError):
            repository.save(replace(changed, version=3), expected_version=1)
        repository.delete(goal.id, expected_version=2)
        self.assertIsNone(repository.get(goal.id))

    def test_all_required_in_memory_repositories_exist(self) -> None:
        repositories = InMemoryRepositories()
        names = ("organizations", "agent_definitions", "agent_instances", "goals", "work_orders",
                 "tasks", "artifacts", "approvals", "audit_events", "budgets")
        for name in names:
            with self.subTest(name=name):
                repository = getattr(repositories, name)
                self.assertEqual([], repository.list())

    def test_in_memory_crud_and_optimistic_lock(self) -> None:
        self.exercise_crud(InMemoryRepositories().goals)

    def test_sqlite_crud_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.db"
            with SQLiteStore(path) as store:
                repository = store.repository("goals", Goal)
                repository.add(self.make_goal())
            with SQLiteStore(path) as reopened:
                repository = reopened.repository("goals", Goal)
                self.assertEqual(self.make_goal(), repository.get("goal_1"))
                changed = replace(self.make_goal(), status=GoalStatus.ACTIVE, version=2)
                repository.save(changed, expected_version=1)
                with self.assertRaises(ConcurrentUpdateError):
                    repository.save(replace(changed, version=3), expected_version=1)

    def test_sqlite_migration_is_idempotent(self) -> None:
        connection = sqlite3.connect(":memory:")
        self.assertEqual([1], migrate(connection))
        self.assertEqual([], migrate(connection))
        count = connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
        self.assertEqual(1, count)
        connection.close()

    def test_sqlite_rejects_raw_secrets(self) -> None:
        class UnsafeGoal:
            id = "unsafe"
            version = 1

            def to_dict(self):
                return {"id": self.id, "api_key": "do-not-store"}

            @classmethod
            def from_dict(cls, data):
                return cls()

        with tempfile.TemporaryDirectory() as directory, SQLiteStore(Path(directory) / "runtime.db") as store:
            with self.assertRaises(RepositoryError):
                store.repository("goals", UnsafeGoal).add(UnsafeGoal())


if __name__ == "__main__":
    unittest.main()
