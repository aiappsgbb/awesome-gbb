# Foundry Insights monitors (`agent_insight_monitors`)

Insights turns an agent's production traces into grouped, severity-ranked
findings (title, category, severity, linked traces, likely cause, proposed fix).
It reads the same Application Insights traces this skill wires up, and it runs a
GPT judge deployment that you pay for per token.

Labels used below: **Documented** (official docs, linked), **Tested** (live run,
conditions stated), **Arithmetic** (derived from the numbers shown), **Advice**
(our recommendation).

Primary source: [Find recurring issues with insights](https://learn.microsoft.com/azure/foundry/observability/how-to/agent-insights).

---

## 1 · Prerequisites (Documented)

| Requirement | Detail |
|---|---|
| SDK | `azure-ai-projects` **2.11.0 or later** — `project_client.agent_insight_monitors` |
| Region | One of 31 supported regions (incl. `swedencentral`, `italynorth`, `westeurope`, `eastus2`, `uksouth`) — full list on the docs page |
| Judge model | GPT-only, **GPT-5 or newer**. Mini and nano variants are supported; larger variants give better insight quality |
| Telemetry | Project connected to the Application Insights resource holding the agent's traces (Layer 2 of this skill) |
| Agent | Registered agent with recent traces in the lookback window. External agents must emit `gen_ai.agent.id` equal to their registered `otel_agent_id` |

### RBAC (Documented)

| Identity | Role | Scope |
|---|---|---|
| Caller (user or app) | **Foundry User** (Prompt agents) / **Foundry Project Manager** (Hosted agents, interactive) | Project or parent account |
| **Project managed identity** | **Cognitive Services OpenAI User** (model access) | Account hosting the judge deployment |
| **Project managed identity** | **Monitoring Reader** — or **Privileged Monitoring Data Reader** if `AppGenAIContent` is protected (it includes normal query access) | Connected Application Insights resource (or linked LAW for workspace-scoped queries) |

Analysis runs as the **project's managed identity**, not the caller. Caller
roles do not flow to it; assign both and allow time for propagation.
Troubleshooting codes: `404` = insights not enabled for the subscription
context; `403` = caller lacks insights permissions or the project MI lacks
model/telemetry access.

---

## 2 · Lifecycle

> **MUST:** Copy the create / stop-and-delete helpers from
> [`python/insights_monitors.py`](python/insights_monitors.py). Do NOT
> redefine them inline.

```text
create(enabled=False)  →  begin_create_run(lookback_hours=…)  →  list_insights(include_details=True)
        │                                                              │
        └── update(enabled=True, run_interval_hours=6)  ← only after review, opt-in recurring cost
teardown: update(enabled=False) → cancel_run(active) → delete(monitor) → get() == 404 → delete agent
```

| Call | Notes |
|---|---|
| `create(agent_name, model_deployment_name, enabled=False, priorities=AgentInsightPriorities(categories=[], instructions=…))` | `categories=[]` uses the built-in categories. Create **disabled** so nothing runs until you ask |
| `get(monitor_id)` / `list()` | Reuse an existing monitor instead of creating a new one; deleting a monitor also removes its runs and insights (Documented) |
| `begin_create_run(monitor_id, lookback_hours=3, operation_id=str(uuid4()))` | LRO; `poller.details["run_id"]`; `poller.result()` exposes `traces_in_window`, `traces_analyzed`, `insights_created/updated/reopened`, `token_usage` |
| `list_insights(monitor_id, statuses=[AgentInsightStatus.ACTIVE], include_details=True)` | `details.recommended_actions.proposed_fix` (`kind`, `text`) |
| `update_insight(monitor_id, insight_id, status=AgentInsightStatus.RESOLVED)` | Records a review decision; it does **not** apply the fix |
| `update(monitor_id, model_deployment_name=…)` | Swap the judge on an existing monitor (Tested, field) |
| `update(monitor_id, enabled=True, run_interval_hours=6)` | Enables the 6-hour schedule. **Documented:** can start a run immediately, keeps running after your session ends and can incur model charges |
| `update(monitor_id, enabled=False)` | Stops future scheduled runs; **does not cancel a running run** — use `list_runs` + `cancel_run` |
| `reset(monitor_id)` | Resets the monitor's generated summary, checkpoint and active insight state (SDK docstring). The docs advise not to reset or re-enable while a run is active |

Retrieval from a coding agent (read-only, no scan started): Foundry MCP tool
`agent_insights_get` with `projectEndpoint`, `agentName`, `includeDetails=true`,
`order=desc`, paging via `has_more` / `last_id` (Documented).

---

## 3 · Judge capacity sizing

| Run | Window | Judge | TPM | Outcome |
|---|---|---|---|---|
| Tested (field, Nov 2026, internal subscription, Italy North) | 294 traces | gpt-5.4 GlobalStandard | 50K | `TooManyRequests` |
| same | 294 traces | gpt-5.4 GlobalStandard | 300K | `TooManyRequests` — Azure Monitor showed ~471K prompt tokens in one minute, ~22K per request |
| same | 294 traces | gpt-5.4 GlobalStandard | **800K** | Succeeded in 11 min, 1.72M tokens, 3 insights |
| Tested (this PR, 2026-11-21, MCAPS subscription, Italy North) | 10 traces | gpt-5.4 GlobalStandard | 800K | Succeeded in 62 s, 75,970 tokens (71,448 in / 4,522 out), 1 HIGH `security_risk` insight over 8 traces |

**Advice.** The judge bursts many parallel requests at the start of a run, so
TPM — not total tokens — is the limiting factor. For windows of hundreds of
traces provision **≥ 800K TPM**. On GlobalStandard, `sku.capacity` is only a
per-minute rate ceiling: you pay per token, so a large ceiling costs nothing
while idle. Use a **dedicated** judge deployment so a run cannot throttle the
agent's own production traffic, and delete or shrink it when you stop
analysing. Smaller windows below 800K TPM were not tested.

---

## 4 · Cost

**Documented:** insights charges are the judge model deployment's token charges.
The portal **View metrics** panel shows token usage and estimated cost per run.

**Arithmetic** (formula):

```text
run_cost ≈ input_tokens × input_price + output_tokens × output_price      (from poller.result().token_usage)
monthly_scheduled_cost ≈ run_cost × 4 runs/day × 30                        (6-hour schedule)
```

Public list price used below: gpt-5.4 Global **USD 2.50 / 1M input**, **USD 15 / 1M
output** ([Azure Retail Prices API](https://prices.azure.com/api/retail/prices),
meters `5.4 inp Gl` / `5.4 opt Gl`, retrieved 2026-11-21). Prices change; re-query.

| Run | Tokens | Arithmetic cost | Per trace |
|---|---|---|---|
| 10 traces (this PR) | 71,448 in + 4,522 out | 0.179 + 0.068 ≈ **USD 0.25** | ≈ USD 0.025 |
| 294 traces (field) | 1.72M total (split not recorded) | ≈ **USD 3.9** as reported by the field test | ≈ USD 0.013 |

Per-trace cost falls with larger windows (fixed per-run overhead), so measure
your own agent with one on-demand run before enabling the schedule.

---

## 5 · Traffic hygiene

- **Tested (field):** evaluation and optimizer draft traffic (agent IDs like
  `<agent>:draft-<epoch>`) falls inside the analysed window and can produce
  findings about drafts, not production. Keep eval/optimizer runs out of the
  lookback window, or use a separate agent identity for them.
- **Documented:** the first analysis uses a 7-day lookback. Missing agent/version
  identity, content, tool arguments or results reduces grouping and fix quality.
- **Tested (this PR):** an account-level `AppInsights` connection with
  `authType: ApiKey` on a new Italy North account returned its connection string
  through `project_client.telemetry.get_application_insights_connection_string()`.
  Accounts affected by gap O-012 still need the SKILL.md workaround.

---

## 6 · Proposed fixes are untrusted input

**Documented:** results can be incomplete or incorrect; concrete prompt/code
diffs exist only for supported Prompt and code-based Hosted agents, otherwise
the fix is general guidance. **Tested:** both runs returned `kind: "prose"`.

**Advice:** treat every proposed fix as untrusted text — review it against the
highlighted traces, healthy control traces, security policy and your evals, and
ship it through normal code review. Never pipe a proposed fix into an agent
definition or a shell automatically. `update_insight(status=RESOLVED)` only
records a decision.

---

## 7 · Teardown (MUST)

1. `update(monitor_id, enabled=False)` — no more scheduled runs.
2. `list_runs` → `cancel_run` for every `queued` / `in_progress` run (retry on
   `ResourceExistsError` while runs settle).
3. `delete(monitor_id)` and confirm `get(monitor_id)` raises `ResourceNotFoundError`.
4. Delete the agent only after the monitor is gone.
5. Delete or shrink the temporary judge deployment.
6. Ingested telemetry stays in Application Insights under its normal retention.

`stop_and_delete_monitor()` in [`python/insights_monitors.py`](python/insights_monitors.py)
implements steps 1–3. **Tested (this PR):** two runs left no monitor and no agent
(both `get` calls returned 404).

### Troubleshooting seen live

| Symptom | Tested meaning | Action |
|---|---|---|
| `HttpResponseError (ServiceUnavailable)`: "content referenced by some traces was not returned after retries" | First run started ~10 min after the project-MI role assignments; `AppGenAIContent` was empty (content lived in span attributes). An identical run ~3 min later succeeded | Treat as transient (likely RBAC propagation); retry once with a new `operation_id` before changing roles |
| Spans not queryable for ~4 min after export | App Insights ingestion lag | Wait for ingestion before `begin_create_run`; the lookback window must contain the traces |
