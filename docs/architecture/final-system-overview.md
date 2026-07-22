# Final system overview

## Component model

```mermaid
flowchart TB
    subgraph Interfaces
      CLI["Legacy CLI / company_cli"]
      UI["Dashboard + voice"]
    end
    subgraph Application
      Intake["Goal intake / planning"]
      Scheduler["Work Order + Task DAG scheduler"]
      Company["Organization workflow"]
      ReadModel["Dashboard read model / commands"]
    end
    subgraph Domain
      Agents["Role / worker / control agents"]
      Collaboration["Delegation / handoff / review"]
      Governance["Policy / permission / budget / approval"]
      Knowledge["Memory / artifacts / context"]
    end
    subgraph PortsAdapters["Ports and adapters"]
      DB["In-memory / SQLite repositories"]
      Models["Mock + legacy provider adapters"]
      Exec["Dry-run / fake / development subprocess"]
      Telemetry["Events / audit / trace / KPI / eval"]
      Legacy["Legacy invocation / memory / pipeline adapters"]
    end
    CLI --> Intake
    UI --> ReadModel
    Intake --> Scheduler
    Company --> Scheduler
    Scheduler --> Agents
    Agents --> Collaboration
    Scheduler --> Governance
    Agents --> Knowledge
    Scheduler --> DB
    Agents --> Models
    Governance --> Exec
    Application --> Telemetry
    Legacy --> Intake
```

Interfaces do not access repositories or the skill runner directly. Application services coordinate domain objects and invoke ports. Governance decisions occur before execution; task/work-order mutations pass through state machines.

## Feature-delivery sequence

```mermaid
sequenceDiagram
    actor Human
    participant Intake as Goal Intake
    participant PM as Product Manager
    participant Arch as Solution Architect
    participant Dev as Developer
    participant Review as Code Reviewer
    participant QA as QA Engineer
    participant Sec as Security/Release
    participant Gov as Policy + Approval
    participant Art as Artifact Store
    Human->>Intake: High-level goal + criteria
    Intake->>PM: Governed Work Order/task
    PM->>Art: Product specification
    PM->>Arch: Approved scope
    Arch->>Art: Design + ADR
    Arch->>Dev: Implementation task
    Dev->>Art: Candidate v1
    Review-->>Dev: Changes requested
    Dev->>Art: Candidate v2
    Review->>QA: Exact approved hash
    par Independent checks
      QA->>Art: Test report
      Sec->>Art: Risk report + checklist
    end
    Sec->>Gov: Exact delivery action/hash
    Gov-->>Human: Human approval request
    Human->>Gov: Approve/reject exact action
    Gov->>Art: Final report (simulated in demo)
```

## Core data model

```mermaid
erDiagram
    ORGANIZATION ||--o{ AGENT_DEFINITION : defines
    AGENT_DEFINITION ||--o{ AGENT_INSTANCE : instantiates
    ORGANIZATION ||--o{ GOAL : owns
    GOAL ||--o{ WORK_ORDER : creates
    WORK_ORDER ||--o{ TASK : contains
    TASK }o--o{ TASK : depends_on
    TASK ||--o{ ARTIFACT_VERSION : produces
    WORK_ORDER ||--|| BUDGET : constrains
    TASK ||--o{ APPROVAL : gates
    WORK_ORDER ||--o{ EVENT : emits
    EVENT ||--o{ TRACE_SPAN : correlates
    TASK ||--o{ MEMORY_RECORD : derives
```

Stable IDs and explicit JSON serialization cross boundaries. Work Orders/Tasks have deterministic bounded states. Artifact versions are immutable by hash and carry producer/task provenance. Memory records carry scope, owner, sensitivity, validation and provenance.

## Security boundaries

Untrusted goals, model output, retrieved files and skill metadata remain outside trusted system/policy instructions. Structured-output validation precedes domain use. Permission and policy engines are deny-by-default; budgets gate dispatch; approvals bind action, arguments hash, actor, task/work order, constitution and expiration. Secrets are referenced by ID/environment name and redacted from events. Generated skills do not receive unrestricted host access.

The included restricted subprocess adapter cannot enforce a security boundary and must not be used as a production sandbox. Production needs an isolation adapter plus tenant authentication/authorization, managed secrets and durable externally anchored audit.

## Deployment modes

| Mode | Intended use | External effects |
|---|---|---|
| Mock | Unit/eval/demo | None |
| Dry-run | Safe default/preview | None |
| Sandbox | Production candidate with a real isolation adapter | Only governed/approved scope |
| Legacy unsafe | Explicit local compatibility only | May mutate host; not production |

Legacy and organization runtimes are independently feature flagged. SQLite is the local durable adapter; in-memory adapters support tests. The current HTTP server/dashboard is developer-grade.

## Extension points

Repository protocols allow managed databases; completion provider ports allow model vendors; sandbox ports allow real isolation; artifact/memory ports allow object/vector stores; event/trace sinks allow durable telemetry/OpenTelemetry; policy/secret adapters allow enterprise control planes; workflow templates allow new governed delivery patterns.

## Legacy compatibility

Legacy CLI, dashboard message/approval routes, chat/work model split, providers, skill lookup/generation/validation/repair, parameter extraction, pipelines and JSONL memory remain operational. Compatibility adapters project legacy invocations/pipelines into governed concepts without silently rerouting execution. JSONL migration is optional, dry-run first, backed up and repeatable.
