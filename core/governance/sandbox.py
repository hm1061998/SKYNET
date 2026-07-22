"""Pluggable execution boundary and explicitly non-secure development adapter."""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import GovernanceError


@dataclass(frozen=True)
class SandboxSpec:
    command: tuple[str, ...]
    read_only_inputs: tuple[str, ...] = ()
    cpu_seconds: int = 1
    memory_mb: int = 128
    timeout_seconds: float = 5
    process_limit: int = 1
    network_allowlist: tuple[str, ...] = ()
    command_allowlist: tuple[str, ...] = ()


@dataclass(frozen=True)
class SandboxResult:
    stdout: str
    stderr: str
    exit_status: int | None
    timed_out: bool
    artifacts: tuple[str, ...]
    warning: str = ""


class SandboxExecutor(Protocol):
    def execute(self, spec: SandboxSpec) -> SandboxResult: ...


class DryRunExecutor:
    def execute(self, spec: SandboxSpec) -> SandboxResult:
        return SandboxResult("", "", None, False, (), "dry run: command was not executed")


class FakeSandboxExecutor:
    """Deterministic test adapter with no host process execution."""
    def __init__(self, result: SandboxResult | None = None) -> None:
        self.result = result or SandboxResult("ok", "", 0, False, ("output/result.txt",))
        self.calls: list[SandboxSpec] = []

    def execute(self, spec: SandboxSpec) -> SandboxResult:
        self.calls.append(spec)
        return self.result


class RestrictedSubprocessExecutor:
    """Development convenience adapter; this is NOT a security sandbox."""
    WARNING = "host subprocess restriction is not a security sandbox"

    def execute(self, spec: SandboxSpec) -> SandboxResult:
        if not spec.command or Path(spec.command[0]).name not in spec.command_allowlist:
            raise GovernanceError("command is not allowlisted")
        if spec.network_allowlist:
            raise GovernanceError("development subprocess adapter cannot enforce network allowlists")
        with tempfile.TemporaryDirectory(prefix="javis-dev-exec-") as workdir:
            output = Path(workdir, "output")
            output.mkdir()
            try:
                result = subprocess.run(spec.command, cwd=workdir, capture_output=True, text=True,
                                        timeout=spec.timeout_seconds, shell=False)
                artifacts = tuple(str(path.relative_to(workdir)) for path in output.rglob("*") if path.is_file())
                return SandboxResult(result.stdout, result.stderr, result.returncode, False,
                                     artifacts, self.WARNING)
            except subprocess.TimeoutExpired as exc:
                return SandboxResult(exc.stdout or "", exc.stderr or "", None, True, (), self.WARNING)
