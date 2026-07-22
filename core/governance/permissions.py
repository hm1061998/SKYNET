"""Least-privilege filesystem, network, command, skill and secret scopes."""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path

from .models import GovernanceError


@dataclass(frozen=True)
class PermissionSet:
    filesystem_read: tuple[str, ...] = ()
    filesystem_write: tuple[str, ...] = ()
    network_allow: tuple[str, ...] = ()
    command_allow: tuple[str, ...] = ()
    skill_tags: tuple[str, ...] = ()
    secrets: tuple[str, ...] = ()

    def is_subset_of(self, parent: "PermissionSet") -> bool:
        return all(set(getattr(self, field)) <= set(getattr(parent, field)) for field in (
            "filesystem_read", "filesystem_write", "network_allow", "command_allow",
            "skill_tags", "secrets"))


class PermissionEngine:
    """Evaluate normalized resources against explicit scopes; deny by default."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()

    def validate_worker(self, worker: PermissionSet, parent: PermissionSet) -> None:
        if not worker.is_subset_of(parent):
            raise GovernanceError("worker permissions exceed parent permissions")

    def filesystem_allowed(self, permissions: PermissionSet, operation: str,
                           requested_path: str | Path) -> bool:
        patterns = permissions.filesystem_read if operation == "read" else permissions.filesystem_write
        try:
            raw = Path(requested_path)
            candidate = (self.workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()
            candidate.relative_to(self.workspace)
            relative = candidate.relative_to(self.workspace).as_posix()
        except (ValueError, OSError):
            return False
        return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)

    @staticmethod
    def network_allowed(permissions: PermissionSet, hostname: str) -> bool:
        host = hostname.lower().rstrip(".")
        return any(host == allowed.lower().rstrip(".") for allowed in permissions.network_allow)

    @staticmethod
    def command_allowed(permissions: PermissionSet, argv: tuple[str, ...]) -> bool:
        if not argv:
            return False
        executable = Path(argv[0]).name.lower()
        return any(executable == Path(item).name.lower() for item in permissions.command_allow)
