# Organization operations console

The dashboard preserves chat as the command surface and adds an organization mode selected by `agent.config.json` / backend feature flags. Users can switch back to the legacy chat at any time. The Organization view uses the same Three.js visual language as Chat mode and exposes an accessible keyboard entity list and text inspector alongside the 3D canvas.

```text
+--------------------------------------------------------------------------------+
| AI Software Company                              Chat mode | 1 approval          |
+-------------+------------------------------------------+-----------------------+
| Command     | Active goal / Work Order / progress      | Chat conversation     |
| Organization| blockers / approval / budget / artifacts | remains available     |
| Task DAG    |                                          | without voice          |
| Timeline    | selected operational view                |                       |
| Approvals   |                                          |                       |
| Artifacts   |                                          |                       |
| Metrics     |                                          |                       |
| Config      |                                          |                       |
+-------------+------------------------------------------+-----------------------+
```

Views cover Command Center, 3D Organization Graph, Task DAG with selectable details, concise Activity Timeline, prominent Approval Inbox, Artifact Center, Cost & Performance, and read-only Organization Configuration. Command Center provides state-aware pause, resume, and confirmed cancellation. Failed or blocked tasks expose a bounded retry action. Loading, empty Work Order/task, refresh error, waiting approval, blocked and completed states have explicit render paths.

The 3D graph is a Collective AI Brain rather than an organization chart. The company Work Order forms the neural core; role agents are neural clusters across two hemispheres; temporary workers are orange transient synapses; tasks sit near their accountable agent; artifacts orbit outside the brain; approvals are amber junctions. Workflow signals travel along neural paths. Reporting and DAG lines stay hidden until a node is selected or the operator enables Debug links. Drag rotation, wheel zoom, raycast selection, filters, keyboard controls, and direct task navigation remain available. The renderer reads `/api/v1/topology`; visual motion never fabricates runtime state.

Every displayed value comes from `/api/v1` structured projections. React escapes text by default; the UI uses no `innerHTML` or `dangerouslySetInnerHTML`. JSON previews are text in `<pre>`, model HTML is never executed, and high-risk approval decisions require browser confirmation.

The page polls every five seconds and receives persisted command events on the next refresh. It works with keyboard/pointer input and without voice. Responsive layouts collapse navigation and keep chat accessible on narrow screens; reduced-motion preferences disable animation.

Manual checklist: verify 3D drag/zoom/raycast selection, keyboard entity selection, filters, high-risk confirm/cancel, approval beacon, task detail close button, mobile navigation scroll, legacy chat switch, browser with voice denied, network error/retry, and no script execution when API text contains XSS fixtures.
