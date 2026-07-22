# Sandbox contract

`SandboxExecutor` accepts a `SandboxSpec` containing an argument-array command, read-only inputs, writable output convention, CPU, memory, timeout and process limits, optional network allowlist and executable allowlist. It returns captured stdout/stderr, exit status, timeout state and collected artifact paths. Adapters own isolated workspace creation and cleanup.

`DryRunExecutor` never starts a process. `FakeSandboxExecutor` is deterministic for unit tests. `RestrictedSubprocessExecutor` uses a temporary working directory, `shell=False`, command allowlisting, timeout, output capture, artifact enumeration and automatic cleanup.

The subprocess adapter is not a security sandbox. It does not claim to enforce CPU, memory, process or filesystem isolation, and it rejects requested network allowlists because it cannot enforce them. Production `sandbox` mode must use a container/VM/OS isolation adapter that enforces every requested limit and deny-by-default networking.

Generated code must not receive arbitrary host paths or environment variables. Inputs should be copied or mounted read-only, outputs collected from the designated output directory, and the isolated directory destroyed after artifact collection.
