# Approval model

Supported approval types are plan, permission elevation, dependency installation, destructive file action, external communication, deployment, production data access, budget extension and policy exception.

An approval binds to the exact normalized action and canonical JSON argument hash, actor, Work Order, task, constitution version, approver and expiration. Any changed argument produces a different hash and invalidates the grant. Expired grants and grants copied to another actor/task/Work Order/constitution are invalid.

Policy resolution is deterministic: normalize the action, select the first exact rule in the versioned constitution and evaluate its explicit condition. If there is no matching rule, the result is deny-by-default. The decision reports its effect, matched rule and explanation. Approval is an input to this decision; it never replaces permissions, allowlists or budget enforcement.

Every attempted governed action should write a complete audit event containing action, argument hash, policy effect, allow/deny outcome and reason. Sensitive values are redacted before persistence.
