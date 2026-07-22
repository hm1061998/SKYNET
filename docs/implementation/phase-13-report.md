# Phase 13 Report — Live Operations Graph

## 1. Summary of implementation

Replaced the Organization tab's static agent-card list with an interactive live topology. The graph shows the active Work Order, role and temporary worker agents, tasks, artifacts, and human approval gates. Operators can filter entity classes, select nodes, inspect current state, highlight connected relationships, and open a task in the existing task detail view.

## 2. Architecture decisions

- Added a backend topology read model rather than inferring domain relationships in React.
- Reused the legacy neural graph's dark luminous visual language while using accessible SVG for the operational view.
- Kept the legacy Three.js chat graph unchanged for compatibility.
- Made state polling explicit at five seconds; animation does not invent activity.
- Encoded relationships as typed edges: `reports_to`, `assigned_to`, `contains`, `depends_on`, `produces`, and `gated_by`.

## 3. Files created

- `src/LiveOrganizationGraph.jsx`
- `docs/implementation/phase-13-report.md`

## 4. Files modified

- `core/dashboard/state.py`
- `server.py`
- `src/OrganizationDashboard.jsx`
- `src/dashboard.css`
- `tests/dashboard/test_dashboard.py`

## 5. Commands executed

- `py -m unittest tests.dashboard.test_dashboard tests.release.test_release tests.e2e.test_phase11_e2e`
- Vite production build using the bundled Node runtime
- Local `/api/v1/topology` HTTP probe
- Full unit-test discovery (final result recorded below)

## 6. Test results

- Focused Python regression: 27 passed.
- Full Python suite: 133 passed, 1 skipped.
- Frontend production build: passed; Vite emitted only the existing large-chunk advisory.
- Local topology endpoint: HTTP 200.
- In-app visual browser verification: blocked because its isolated browser could not reach the host loopback server; the host-side HTTP probe succeeded.

## 7. Compatibility impact

Legacy chat, voice, Three.js neural graph, and existing dashboard routes remain intact. `/api/v1/topology` is additive. The Organization tab preserves the existing navigation position and polling behavior.

## 8. Security impact

The topology endpoint exposes only sanitized operational fields already present in dashboard read models. It excludes prompts, chain-of-thought, secrets, and raw generated HTML. React renders labels as text. Approval decisions retain CSRF and action-hash validation.

## 9. Known limitations

- The projection is still backed by the Phase 09 file/in-memory dashboard state, not a streaming event bus.
- Large organizations will need viewport zoom/pan and clustering.
- The frontend bundle still includes the legacy Three.js renderer and triggers Vite's chunk-size advisory.
- Visual browser QA must be repeated in a browser environment that can access the host loopback interface.

## 10. Recommended next phase

Connect topology generation to persisted runtime repositories and an event stream (SSE or WebSocket), then add operator commands for creating goals, pausing/resuming work orders, retrying safe tasks, and spawning governed temporary workers.
