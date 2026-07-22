# AI Software Company template

`organizations/software-company-v1.yaml` is a versioned, dependency-free JSON-compatible YAML organization template. It defines exactly seven persistent role agents: Chief of Staff, Product Manager, Solution Architect, Developer, Code Reviewer, QA Engineer, and Security & Release Officer. Eight specialist definitions are worker templates, not persistent core agents.

The template also declares departments, reporting lines, model profiles, least-privilege defaults, budgets, the feature-delivery workflow, constitution reference and KPIs. Each role has a mission, trusted prompt template, capabilities, memory scopes and policy constraints.

The reporting structure places all accountable functions under Chief of Staff except Developer, who reports to Solution Architect. Code review, QA and security/release remain independent of implementation.

`SeparationOfDuties` enforces critical constraints in code: authors cannot approve their code; architecture review is not code approval; Code Reviewer cannot release or modify the reviewed artifact; QA needs Product Manager authorization to change acceptance criteria; production deployment requires both the Security & Release Officer and human approval; Developer cannot deploy/install/change criteria; and Chief of Staff cannot alter policy or approve its own exception.

Temporary workers are created through the existing `AgentFactory`. Their capabilities must be a subset of both parent and worker template, and instances bind to a task, Work Order, budget, context and expiration.
