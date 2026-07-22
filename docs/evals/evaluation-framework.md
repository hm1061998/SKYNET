# Deterministic evaluation and safe replay

Evaluation cases live under `evals/` as JSON-compatible YAML so the offline runner can parse them with the standard library. A case declares fixtures, required artifact contracts, required task coverage and final state, policy expectations, graph validity, reviewer separation, budget limits, maximum review rounds, and regression expectations.

`EvaluationRunner` performs deterministic checks and emits a structured result for each criterion plus an overall pass/fail. A model judge may be injected for advisory scoring, but it is never authoritative for policy, approval, budget, or schema enforcement. The included `feature_delivery_health_check.yaml` exercises the standard software-company feature-delivery workflow without API keys or external effects.

`ReplayService` replays events only in simulation mode, starting at an optional checkpoint. It requires mock tool adapters, preserves idempotency keys, and blocks events marked irreversible as well as known externally visible action classes. Replay must not deploy, install packages, send messages, modify permissions, delete data, or call real production adapters.

Run the focused suite with:

```powershell
python -m unittest discover -s tests\observability -v
```

An eval failure should identify the specific deterministic check. Fix the implementation or fixture; do not weaken security or governance assertions merely to make a score pass.
