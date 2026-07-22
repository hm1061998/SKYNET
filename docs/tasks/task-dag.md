# Task DAG

## Task contract

A governed Task records title, bounded objective, accountable role, optional worker specialization, JSON-compatible inputs/output schema, acceptance criteria, dependency edges, retry/backoff, timeout, risk, required permissions/artifacts, allocated token/cost/time budget, review policy, idempotency key, lifecycle status, attempt count, next eligible time and optimistic version.

```mermaid
flowchart LR
    A["Repository analysis"] --> C["Implementation"]
    B["Acceptance criteria"] --> C
    C --> D["Code review"]
    C --> E["QA tests"]
    D --> F["Release gate"]
    E --> F
```

`TaskGraph` is an immutable Work Order ID plus a tuple of Tasks. Dependency edges live in each Task as `TaskDependency(task_id, depends_on_task_id)`. Helpers expose dependencies and dependents without adding hidden edges.

## Validation

`TaskGraphValidator` runs before every scheduler tick as defense in depth. It rejects:

- empty graphs and duplicate Task IDs;
- mismatch between Work Order Task IDs and the graph;
- Tasks owned by another Work Order;
- self or missing dependencies;
- cycles with a readable path such as `a -> b -> c -> a`;
- missing accountable roles;
- empty or duplicate idempotency keys;
- malformed/impossible `approval:<task-id>` references;
- external-action Tasks whose Work Order does not require approval;
- aggregate Task token, cost or time allocations above the Work Order budget.

## Task lifecycle

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> BLOCKED
    DRAFT --> READY
    DRAFT --> WAITING_INPUT
    DRAFT --> WAITING_APPROVAL
    READY --> IN_PROGRESS
    IN_PROGRESS --> WAITING_INPUT
    IN_PROGRESS --> WAITING_APPROVAL
    WAITING_INPUT --> READY
    WAITING_APPROVAL --> READY
    IN_PROGRESS --> REVIEW
    REVIEW --> IN_PROGRESS
    IN_PROGRESS --> COMPLETED
    REVIEW --> COMPLETED
    IN_PROGRESS --> FAILED
    REVIEW --> FAILED
    FAILED --> READY : retry remains
    DRAFT --> TIMED_OUT
    BLOCKED --> TIMED_OUT
    READY --> TIMED_OUT
    WAITING_INPUT --> TIMED_OUT
    WAITING_APPROVAL --> TIMED_OUT
    TIMED_OUT --> READY : retry remains
    DRAFT --> CANCELLED
    BLOCKED --> CANCELLED
    READY --> CANCELLED
    IN_PROGRESS --> CANCELLED
    WAITING_INPUT --> CANCELLED
    WAITING_APPROVAL --> CANCELLED
    REVIEW --> CANCELLED
```

Completed Tasks are terminal in normal scheduling. The older domain-level explicit reopen mechanism remains for compatibility but the Phase 04 scheduler does not invoke it.

## Idempotency

Every Task requires a unique Work Order-scoped key. `TaskDispatcher` derives an attempt token (`<key>:attempt:<n>`) and caches results per attempt. Replaying a tick cannot dispatch a persisted IN_PROGRESS/COMPLETED Task, while an intentional retry uses a new attempt token. External actions additionally require Work Order approval. Immutable artifact versioning remains an artifact-service responsibility; Phase 04 dispatch results only return artifact references.
