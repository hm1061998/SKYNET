# Organization API v1

Read endpoints return `{ "data": ... }` JSON and include `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`:

```text
GET /api/v1/organizations
GET /api/v1/work-orders
GET /api/v1/work-orders/{id}
GET /api/v1/work-orders/{id}/tasks
GET /api/v1/tasks/{id}
GET /api/v1/agents
GET /api/v1/topology
GET /api/v1/artifacts
GET /api/v1/approvals
GET /api/v1/events
GET /api/v1/metrics
GET /api/v1/configuration
GET /api/v1/session
```

The MVP projection is file-backed/structured and redacted. `topology` returns sanitized nodes and typed edges for work orders, agents, tasks, artifacts and approvals. It never returns API keys, environment variables, secrets, prompts or chain-of-thought. Configuration is explicitly read-only.

Approval decisions use `POST /api/v1/approvals/decision` with JSON fields `approval_id`, `action_hash`, `decision` (`approved` or `rejected`) and the session token in `X-CSRF-Token`. Both ID and exact action hash must match current state. High-risk confirmation is also required in the UI. Invalid binding or CSRF returns HTTP 403.

The server remains bound to loopback by default. The CSRF token is an appropriate MVP control for this local architecture; a remotely exposed deployment must add authenticated sessions, origin enforcement and authorization roles. Legacy `/api/message`, `/api/approve`, `/api/reject`, job polling, model configuration and TTS routes remain unchanged.
