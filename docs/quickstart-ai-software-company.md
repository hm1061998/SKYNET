# AI Software Company quickstart

## Offline setup

Use Python 3.11 or newer. The demo uses only the standard library and repository code; do not install provider SDKs, system tools, or Docker.

```powershell
Copy-Item config.example.json config.json
python company_cli.py validate-release
python company_cli.py validate-organization
python demo\run_demo.py
python company_cli.py run-evals
python -m unittest discover -s tests -v
```

`config.example.json` starts in legacy UI/runtime mode with organization disabled and dry-run execution. The offline demo invokes the organization workflow explicitly without changing that deployment default.

## CLI command map

| Purpose | Command |
|---|---|
| Legacy interactive | `python agent.py` |
| Legacy one-shot | `python agent.py "resize image fixture.png to 800x600"` |
| Organization offline demo | `python company_cli.py offline-demo` |
| Create template copy | `python company_cli.py create-default-organization path/to/org.yaml` |
| Validate release set | `python company_cli.py validate-release` |
| Validate organization | `python company_cli.py validate-organization` |
| Start dashboard | `python server.py` |
| Run eval | `python company_cli.py run-evals` |
| List Work Orders | `python company_cli.py list-work-orders` |
| List artifacts | `python company_cli.py list-artifacts` |
| List approvals/exact hashes | `python company_cli.py list-approvals` |
| Inspect task | `python company_cli.py inspect-task task-code_review` |
| Approve/reject exact action | `python company_cli.py decide-approval rejected --action-hash <hash>` |
| Export delivery | `python company_cli.py export-delivery-report output/final-report.json` |
| Preview memory migration | `python company_cli.py migrate-memory memory/facts.jsonl data/runtime.db` |

Obtain the exact approval hash from the dashboard approval projection. A stale or modified hash is rejected. CLI approval state is an MVP in-process projection; it is not a durable production approval console.

## Inspect the demo

Open `demo/output/demo-summary.json`. Verify `status=completed`, eight DAG stages, simulated approval, valid audit chain, eight trace spans, zero external effects and zero cost units. Then inspect each exported Markdown/patch artifact and its content hash/provenance entry.
