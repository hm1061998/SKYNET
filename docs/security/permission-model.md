# Permission model

`PermissionSet` has independent scopes for filesystem read/write, network hosts, executable names, skill tags and secret identifiers. Empty scopes deny access.

Filesystem checks resolve the requested path (including symlinks), ensure it remains inside the configured workspace, convert it to a normalized POSIX-relative path and only then apply allowed globs. Read and write scopes are separate. Network matching uses exact normalized hostnames; wildcards and implicit internet access are not supported. Commands are passed as argument arrays with `shell=False` and the executable must be explicitly allowlisted.

Worker scopes must be equal to or narrower than the parent's scopes. Permission possession does not override organization policy or approval requirements: all three checks remain independent.

Secrets are referenced by identifier. A `SecretBroker` exposes approved values only for the duration of a context-managed action. Secret values must never be added to prompts, artifacts, messages or logs. The in-memory broker is a deterministic test adapter, not a production secret store.

The default execution mode is `dry_run`. Supported modes are `mock`, `dry_run`, `sandbox` and `legacy_unsafe`. Set `JAVIS_EXECUTION_MODE=legacy_unsafe` only for deliberate legacy compatibility; it permits host mutation and is prominently identified as unsafe.
