# Trigger receiver scaffolds — placeholder index

Each subdirectory holds a polished, copy-paste-ready scaffold for one
receiver type. SKILL.md inlines the essential code shape; these directories
will hold the full working scaffolds.

| Scaffold | When to use | Status |
|----------|-------------|--------|
| `aca-job-cron/` | Periodic batch (nightly KPI rollup, hourly reconciliation, SLA watcher) | 📋 Placeholder |
| `aca-job-manual/` | Manual REST trigger (workflow step, on-demand replay) | 📋 Placeholder |
| `function-http/` | Lightweight HTTP webhook receiver (consumption billing) | 📋 Placeholder |
| `function-servicebus/` | Service Bus queue/topic consumer (binding-driven) | 📋 Placeholder |
| `function-eventgrid/` | Event Grid event handler (binding-driven) | 📋 Placeholder |
| `aca-consumer/` | High-throughput SB / Event Hubs consumer with KEDA scaler | 📋 Placeholder |

## Canonization order (during pilots)

1. **Future operations pilot** — canonize `function-http` (webhook from source
   system) AND `aca-job-cron` (SLA watcher for stuck items)
2. **KYC pilot** — canonize `aca-job-cron` (SLA watcher for awaiting-approval cases)
3. **Supplier Risk pilot** — canonize `function-eventgrid` (news event ingestion)
4. **PIM pilot** — canonize `aca-job-manual` (replay enrichment for a SKU range)

Each canonized scaffold ships with:
- `receiver.py` — entry point
- `pyproject.toml` — uv-managed deps
- `Dockerfile` — for ACA receivers
- `host.json` + `function.json` — for Function receivers
- `local.test.py` — test the receiver locally with synthetic input
- `README.md` — idempotency notes, DLQ wiring, replay instructions
