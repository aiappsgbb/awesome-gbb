---
name: token-economics
description: >
  Cut cost per successful task, TPM pressure and context size for Responses API
  apps and agents: prompt/tool-output diet, deferred tool loading (tool_search +
  defer_loading, gpt-5.4+), cache-friendly prefixes, allowed_tools, reasoning effort,
  compaction, right-sizing, model router economics, Flex/Batch/Priority. Live-measured
  scripts price eager vs deferred tools and router modes vs fixed models. USE FOR: token
  economics, token optimization, reduce token usage, LLM cost,
  tool_search, defer_loading, deferred tools, tool namespaces, too many tools, large
  MCP catalog, prompt caching hit rate, cached_tokens, TPM 429 from large prompts,
  reasoning effort cost, context compaction, flex processing, model router cost,
  routing fee, model auto savings. DO NOT
  USE FOR: PAYG-vs-PTU sizing (use paygo-ptu-cost-analyzer), Foundry spend
  dashboards/budgets (use foundry-cost-monitoring), Foundry Toolbox tool search (use
  foundry-toolbox), hosted-agent cache breakpoints (use foundry-hosted-agents).
metadata:
  version: "1.2.0"
---

# Token economics

Optimize **cost per successful task**, not tokens per request. One user task can
include several inferences (tool search, tool calls, follow-ups, retries); a lever
that shrinks the first request but adds a second inference, more reasoning, or a
lower success rate can lose money. Measure, change one lever, measure again.

## The cost model

For every inference in a task:

```
cost = U·p_in + C·p_cached (+ W·p_write on GPT-5.6+) + O·p_out        (× tier multiplier)
U = uncached input tokens   C = cached input tokens   W = cache-write tokens
O = output tokens, INCLUDING hidden reasoning tokens
```

Three independent budgets are in play, and levers trade them against each other:

| Budget | Driven by | Notes |
|---|---|---|
| **Money** | `U`, `C`, `W`, `O` × current rates | Cached input is discounted, not free. Output is several times the input price on most models. |
| **Throughput (TPM/429s)** | Total tokens per minute | Treat TPM headroom as driven by total input, cached or not, plus the output reservation. Azure's admission estimate counts `max_tokens`/`max_output_tokens` in full, even if fewer tokens are generated ([source][az429]). |
| **Context window / latency** | Total input + reasoning | Large tool catalogs and histories raise time-to-first-token and can reduce tool-selection accuracy. |

Never hardcode prices. Use the current [Azure OpenAI pricing][pricing] for the
exact model, deployment type and region.

## Measure first (usage fields)

| Field (Responses API) | Meaning |
|---|---|
| `usage.input_tokens` | All input tokens of this inference |
| `usage.input_tokens_details.cached_tokens` | Cache reads (discounted) |
| `usage.input_tokens_details.cache_write_tokens` | Cache writes (GPT-5.6+ Standard); a **subset** of `input_tokens`, billed at the write rate (1.25× input on current price sheets). Missing ≠ zero |
| `usage.output_tokens` | Output including reasoning |
| `usage.output_tokens_details.reasoning_tokens` | Hidden reasoning share of output |

Sum these **per task** across all inferences. Record counts, model/deployment,
tool-catalog version and timings; **never log prompts, tool arguments or outputs**
for cost diagnosis. For production telemetry use `foundry-observability`; for spend
dashboards use `foundry-cost-monitoring`.

## The optimization ladder

Work top-down. Earlier rungs are cheaper to adopt and rarely reduce quality.
Judge every rung by cost per successful task (money **and** latency), never by
raw `input_tokens` alone.

| # | Lever | Typical effect | Watch out for |
|---|---|---|---|
| 1 | **Diet**: remove dead instructions, duplicated policy, verbose few-shots; trim tool **outputs** to the fields the model needs; paginate | Cuts `U` everywhere, every turn | Tool outputs accumulate in history on every later turn — they are often the largest line item |
| 2 | **Defer tool definitions** with `tool_search` (gpt-5.4+) | Large catalogs: −37% to −68% money, ~−90% input, on all current families (measured) | Small catalogs with a warm cache: **+24% to +171% money** on every family — eager wins |
| 3 | **Cache-friendly prefix**: stable instructions/tools first, variable content last, append-only history | Up to ~all of the stable prefix billed at the cached rate | ≥1,024 identical leading tokens; one-character change = miss |
| 4 | **Reasoning effort, verbosity, `max_output_tokens`** | Cuts `O` (the expensive side) | Lower effort can reduce success; oversized `max_output_tokens` wastes TPM |
| 5 | **Compaction** of long conversations/agent loops | Bounds `U` growth over long sessions | Opaque item; do not prune when chaining with `previous_response_id` |
| 6 | **Right-size the model** (`-mini`/`-nano` for routing, extraction, classification), or let **model router** pick per request | Large rate difference | Validate with evals, not anecdotes (`foundry-evals`); the router adds a fee per input token (see [Model router economics](#model-router-economics)) |
| 7 | **Service tier**: Flex (−50%, preview), Batch (−50%, ≤24h), Priority (premium, steadier latency), PTU | Multiplier on everything | Flex can 429 with no Standard fallback; PTU sizing is `paygo-ptu-cost-analyzer` |

## Deferred tool loading: `tool_search` + `defer_loading`

Sources: [Azure OpenAI tool search][az-toolsearch], [OpenAI tool search][oai-toolsearch].

### What it is

Without it, every tool's name, description and full JSON schema is sent on every
inference. With it, the model initially sees only searchable **surfaces** and loads
full definitions on demand. Loaded tools are injected at the **end** of the context,
so the earlier prefix stays cache-stable.

| Surface | What the model sees before searching | Savings |
|---|---|---|
| `namespace` with deferred functions (**preferred**) | Namespace name + description only | Highest |
| MCP server with `defer_loading: true` | Server name + description only | Highest |
| Individual deferred `function` | Function name + description; **only the parameter schema is deferred** | Lower |

Models are primarily trained to search namespaces and MCP servers. Keep each
namespace **under 10 functions**, give it a short purpose-level description, and put
rich detail in the deferred function descriptions (loaded only when needed).

### Support and failure mode (verified)

- Supported on **gpt-5.4 and later** in the Responses API (Azure and OpenAI). Verified
  live on Azure (2026-10-14): gpt-5.4, gpt-5.4-mini, gpt-5.5, gpt-5.6-terra,
  gpt-5.6-luna, gpt-6-sol, gpt-6-luna, gpt-6.1-sol and gpt-6-astra.
- Earlier models fail hard: `HTTP 400 — Tool 'tool_search' is not supported with
  gpt-5-mini-2025-08-07` (also observed for `gpt-4.1`). There is **no silent
  fallback** — gate the feature on the deployment's model family, do not try/except
  into a different tool list at runtime without logging it.
- Verified on Azure: hosted search over namespaces, deferred MCP servers
  (`"type": "mcp"` + `defer_loading: true`) and client-executed search.
- `defer_loading` on a namespace member applies to the function, not the namespace.
  A namespace may mix eager (always callable) and deferred functions.

### Hosted vs client-executed search

| Mode | Configure | Use when |
|---|---|---|
| **Hosted** (default) | `{"type": "tool_search"}`; the service searches the deferred tools you declared and returns `tool_search_call` + `tool_search_output` in the **same response** (`execution: "server"`, `call_id: null`) | Full inventory known at request time |
| **Client** | `{"type": "tool_search", "execution": "client", "description": ..., "parameters": {...}}`; the model emits `tool_search_call` and stops; you return `tool_search_output` with the **same `call_id`** and the tools to load | Tool availability depends on tenant/project/permissions or an external registry |

Minimal hosted request (Entra ID; full runnable version is the measurement script):

```python
response = client.responses.create(
    model="<gpt-5.4-or-later-deployment>",
    input="List open orders for customer CUST-12345.",
    tools=[
        {"type": "namespace", "name": "crm",
         "description": "CRM tools for customer lookup and order management.",
         "tools": [{"type": "function", "name": "list_open_orders",
                    "description": "List open orders for a customer ID.",
                    "defer_loading": True,
                    "parameters": {"type": "object",
                                   "properties": {"customer_id": {"type": "string"}},
                                   "required": ["customer_id"],
                                   "additionalProperties": False}}]},
        {"type": "tool_search"},
    ],
    parallel_tool_calls=False,
)
```

### Rules that keep the savings

1. **Return complete, trusted definitions only** in client mode. Tools absent from
   `tool_search_output.tools` are not callable. Never echo definitions sourced from
   user input or untrusted registries — it is a tool-injection path.
2. **Keep loaded tools stable.** In client mode a tool loaded once stays callable in
   later turns; do not reload it. Removing or changing a loaded tool breaks the cache
   from that point forward.
3. **Round-trip output items verbatim** (including `tool_search_call`/`_output` and,
   with `store=False`, encrypted reasoning via
   `include=["reasoning.encrypted_content"]`). For tools added outside the search
   flow use an `additional_tools` input item and preserve its position.
4. **Authorization is separate.** Deferring a tool hides its schema, not its
   existence or callability. Do not declare tools the caller is not allowed to use.
5. **Make required parameters honest.** Newer models (observed on gpt-6-astra and
   gpt-6.1-sol) load the right deferred tool, then ask the user for missing required
   fields instead of inventing them; with eager loading the same models sometimes
   called write tools anyway. Mark only truly mandatory fields as required and treat
   "found but asked" separately from "not found" in evals.
6. **Keep always-needed tools eager.** A tool used on most turns is cheaper as an
   eager definition than as a search every time.
7. **Verify the wire request through frameworks.** Agent frameworks and SDK
   wrappers may not serialize `namespace`, `defer_loading` or `tool_search`, or may
   drop unknown fields; deferral then silently becomes eager (or a 400). Check one
   real request or the `tool_search_call` items in the output before trusting savings.
8. Different features: Foundry **Toolbox** tool search (`foundry-toolbox`) discovers
   tools in a versioned Toolbox; the OpenAI **Agents API** auto-defers MCP tools.
   The rules here apply to declared tools in Responses API requests.

### Measured evidence (2026-10-14, Sweden Central, Global Standard)

Synthetic catalogs (30 functions in 5 namespaces ≈ 3.4k tokens; 160 in 20 ≈ 22k),
the six [demo cases](references/demo_cases.jsonl), complete tool loops,
`reasoning.effort=low`, `store=False`. **Money** = input-equivalent cost
`U + c·C + w·W + r·O` with each model's retail Global Standard short-context
ratios that day. Values are the deferred-vs-eager **cost change** (negative = deferral
cheaper). *Warm* = the eager prefix was already cached (steady traffic); *cold* =
first use, the eager catalog is written to cache. *Indep.* = each case is a new
conversation; *session* = the six cases are turns of one conversation.

| Model | c / w / r | 30 fn warm indep. / session | 160 fn warm indep. / session | Cold indep. 30 fn / 160 fn |
|---|---|---|---|---|
| gpt-5.5 | 0.1 / — / 6 | +171% / +103% | +1% / −41% | +164% / −34% |
| gpt-5.6-terra | 0.1 / 1.25 / 6 | +57% / +51% | −37% / −49% | −3% / −65% |
| gpt-5.6-luna | 0.1 / 1.25 / 6 | +66% / +24% | −37% / −68% | +11% / −62% |
| gpt-6-sol | 0.1 / 1.25 / 5 | +55% / +56% | −38% / −50% | −2% / −67% |
| gpt-6-luna | 0.1 / 1.25 / 5 | +58% / +59% | −41% / −50% | +6% / −69% |
| gpt-6.1-sol | **0.05** / 1.25 / 5 | +126% / +35% | −12% / −58% | +21%† / −66%† |
| gpt-6-astra | 0.1 / 1.25 / 5 | +59% / +7% | −54% / −67% | −5%† / −74%† |
| gpt-5.4 (earlier run) | 0.1 / — / 6 | +72% / +44% | −62% / −37% | — |

`c`, `w`, `r` = cached, cache-write and output price relative to uncached input.
Raw input fell 57–94% in every row. Tool selection was 6/6 for both variants on
all models with the final cases. † Cold-run cases did not yet give every required
field; on write cases gpt-6-astra and gpt-6.1-sol loaded the right tool but asked
for the missing values instead of calling (4/6 and 5/6), which lowers deferred cost.
Single runs, synthetic tools: treat ±10–15 points as noise.

Also verified: a deferred **MCP** server (Microsoft Learn MCP, 3 tools) cut input
9,508 → 6,878 (−28%) with the same answer on gpt-5.4; `mcp_list_tools` still runs.
Client-executed search worked end to end.

What the numbers say:

- **Raw input is the wrong metric.** Deferral always cut input by >55%, yet on a
  warm small catalog it **raised cost on every model**: the eager prefix is ~98%
  cached (billed at 5–10%), while deferral adds search output (billed 5–6×) and a
  shorter, partly uncached prefix.
- **Large catalogs save on every current family** (−37% to −68%) except gpt-5.5
  in warm independent traffic (+1%): its deferred prefixes got **no** cache hits.
  GPT-5.6+/6.x cached 5–15k tokens of the deferred prefix.
- **Cheaper cache reads shrink the win.** gpt-6.1-sol reads cache at 0.05×, so a
  warm 160-function eager catalog costs little and deferral saved only 12% there.
- **Cold starts favour deferral on GPT-5.6+** because the eager catalog must first
  be written at 1.25×: small catalogs are roughly neutral (−5% to +21%), large ones
  save 62–74%. Bursty or per-tenant catalogs live mostly in this regime.
- **Latency** had no consistent winner on GPT-5.6+/6.x; small catalogs were usually
  slower deferred. Single requests occasionally took 3–6 minutes on both variants —
  set explicit client timeouts.
- Searches may run twice per task (`paths`, then `query`).

### Decide with your own numbers

Per task, deferral pays when

```
  T_cat · n · (1 − h_E·(1 − c))  +  T_cat · m · (w − 1)   >   ΔO · r  +  Δcache
  T_cat  = catalog tokens removed per inference   n = inferences per task
  h_E    = eager cache-hit ratio                   m = eager cache writes of the catalog
  w      = cache-write ratio (1.25 on GPT-5.6+)    ΔO = extra output (search + reasoning)
  Δcache = cost of cache hits the shorter deferred prefix loses
```

With a warm cache (`h_E ≈ 0.98`, `c = 0.05–0.1`) each removed catalog token is worth
only 0.07–0.12 uncached tokens, so a small `T_cat` cannot pay for search output
priced at `r` = 5–6×. Every cold write of the eager catalog (`m`) adds `w − 1` in
deferral's favour. Rules of thumb from the data, not guarantees:

- **Defer** when the catalog is a large share of the request (≈10k+ tokens), the tool
  set varies per user/tenant (eager cache already broken), traffic is bursty (the
  in-memory cache usually expires after 5–10 idle minutes), TPM 429s hurt, or
  selection accuracy drops with catalog size.
- **Stay eager** for catalogs of a few thousand tokens with steady traffic, or tools
  used on most turns — on every current model family. On gpt-5.5 prefer eager unless
  the catalog is large *and* conversations are long. To restrict tools per turn
  without breaking the cache, use `tool_choice: allowed_tools` (below) instead of
  editing the `tools` array.
- Run the script with `--cases` and your real catalog and price ratios; it prints
  `input_equivalent_cost` for both variants. Then compare the eager `cached_tokens`
  ratio with **production** telemetry, not a warm benchmark loop.

## Measure before and after

> **MUST:** Copy verbatim from [`references/python/measure_tool_search.py`](references/python/measure_tool_search.py).
> Do NOT redefine inline. It runs the same task eager vs deferred as a complete tool
> turn and prints usage counters only.

```bash
pip install "openai>=3.26,<4" "azure-identity>=1.25,<2"
python references/python/measure_tool_search.py \
  --endpoint https://<resource>.openai.azure.com \
  --model <gpt-5.4-or-later-deployment> \
  [--tenant <tenant-id>] [--tools-file tools.json] \
  [--cases references/demo_cases.jsonl] [--session] \
  [--cached-ratio 0.1 --output-ratio 6 --cache-write-ratio 1.25]
```

- `--endpoint` also accepts a Foundry project endpoint (`…/api/projects/<p>`).
- Identity needs **Cognitive Services OpenAI User** on the resource; token scope is
  `https://ai.azure.com/.default`.
- `--tools-file` takes your real catalog (a JSON array of Responses tools) and
  derives the deferred variant (`defer_loading` on functions, namespace members and
  MCP servers, plus `tool_search`). Supply `--expect-tool <name>` or `--cases`.
- `--cases` (JSON Lines `{"prompt", "expect_tool"}`) measures selection success
  per variant; `--session` chains the cases as turns of one conversation;
  `--cached-ratio`/`--output-ratio`/`--cache-write-ratio` (from the current price
  sheet; write ratio 1.0 where writes are not billed separately) add an
  `input_equivalent_cost` comparison. Latency is reported as `elapsed_s`.
- `found_not_called` counts cases where the expected tool was **loaded** by search
  but not called — usually the model asking for missing required inputs, not a
  discovery failure. Inspect those before calling it a selection regression.
- Run warm **and** cold: the first run against a new catalog/deployment pays cache
  writes on GPT-5.6+; repeated runs show steady state. Report both.
- Exit `0` = deferred variant called every expected tool, `1` = it missed one
  (selection regression), `2` = API/config/input error (e.g. the HTTP 400 above).
- Run each variant several times and report distributions. There is no usable
  pre-flight token counter on Azure: `responses.input_tokens.count` returned HTTP
  400 (`This model is not supported by Responses API`) for gpt-5.4, gpt-5.4-mini
  and gpt-5-mini — measure with real `usage`.

## Model router economics

Sources: [model router][router], [how it chooses capacity][router-how],
[per-request controls][router-controls], [monitoring][router-monitor],
[AI Gateway][router-gateway], [Retail Prices API][retail-api]. Labels:
**[Documented]** = official docs, **[Tested]** = measured live, **[Analysis]** = derived.

### What you pay

- **[Documented]** A routing fee per 1M **input** tokens plus the selected model's
  usage at that model's rates. It applies to Auto (`model: "auto"`), to model router
  deployments and to requests your own deployments serve: your own pay-as-you-go
  deployment → its usage + fee; your own PTU deployment of an OpenAI model → fee only.
  AI Gateway automatic model selection has **no** router fee while it is in preview
  (gateway charges apply).
- **[Tested]** Retail Prices API, Sweden Central, effective 2026-01-01 (read 2026-11-20):
  meter `Model Routers GL 1M Tokens` **$0.14** (Global) and `Model Routers DZ 1M Tokens`
  **$0.154** (Data Zone). Fetch it, do not hardcode it.
- **Not documented:** whether cached input tokens are exempt from the fee. The script
  charges all input by default; `--fee-excludes-cached` shows the other case. Settle
  it with billed meters in Cost Management (filter tag **Deployment**).

### The fee against the model it picks

**[Analysis]** Fee as a share of each model's Global Standard input price
(Retail Prices API, Sweden Central, 2026-11-20):

| Model | Input $/1M | Fee vs input | Fee vs cached input |
|---|---|---|---|
| gpt-5-nano | 0.05 | 280% | 2,800% |
| gpt-6-luna | 0.10 | 140% | 1,400% |
| gpt-5.6-luna | 0.20 | 70% | 700% |
| gpt-5-mini | 0.25 | 56% | 560% |
| gpt-5.4-mini | 0.75 | 19% | 187% |
| gpt-6.1-sol | 2.00 | 7% | 140% |
| gpt-5.4 | 2.50 | 5.6% | 56% |
| gpt-6-astra | 10.00 | 1.4% | 14% |

On a modern small model the fee costs more than the input it routes; on a frontier
model it is noise. Routing pays only when it moves traffic **away from an expensive
baseline**, not when the alternative is already a cheap modern model:

```
router wins  ⇔  Σ_requests [cost(baseline) − cost(chosen)]  >  f · Σ input tokens
f = routing fee per token        (and quality must hold on your evals)
```

Price per token is not price per task: reasoning models spend hidden output tokens.

### Measured evidence (2026-11-20, Sweden Central, Global Standard)

**[Tested]** `model-router` version `2025-11-18` (full pool, Balanced) and Auto, Responses
API, Entra ID; 12 graded cases (8 easy: Q&A, extraction, a small RAG policy, JSON;
4 hard: arithmetic word problem, policy reasoning, code output, logic) × 2 repeats,
deterministic regex graders. gpt-5.6-luna, gpt-5.4-mini and gpt-5-nano were also
deployed in the same resource, so the router could serve them from those deployments.
gpt-6-luna could not be deployed as a baseline (no quota). Costs are estimates (usage ×
list price + fee), not billed amounts; DeepSeek and Grok prices were mapped by hand
(`--price-file`). One small run: treat differences under ~20% as noise.

| Arm | Passed | $ per 1k tasks | Fee share | Top answering models |
|---|---|---|---|---|
| Fixed gpt-5.6-luna | 23/24 | **0.040** | — | gpt-5.6-luna |
| Router, Cost mode | 24/24 | 0.044 | 27% | gpt-6-luna 42%, grok-4-1-fast-reasoning 25% |
| Router, deployment (Balanced) | 23/24 | 0.050 | 17% | gpt-5.6-luna 58%, deepseek-v4.1-flash 25% |
| Auto (Balanced) | 24/24 | 0.051 | 17% | same mix as the deployment |
| Fixed gpt-5.4-mini | 21/24 | 0.064 | — | gpt-5.4-mini (missed 3 hard) |
| Fixed gpt-5-nano | 24/24 | 0.121 | — | gpt-5-nano (reasoning output) |
| Router, Quality mode | 24/24 | 0.390 | 1.7% | gpt-5.4 42%, gpt-5.6-sol 17% |

What the numbers say:

- Against a **modern small model** that already passes, the router was not cheaper:
  Cost, Balanced and Auto cost 10–28% more than fixed gpt-5.6-luna, and the fee was
  17–27% of their spend. Against gpt-5.4-mini or gpt-5-nano they were cheaper and as
  accurate. The baseline you compare with decides the verdict.
- **Quality** mode cost about 8× Balanced on this mix for one more passed case in 24.
- Request parameters change the choice **[Tested]**: on the same hard prompt,
  `reasoning.effort` `minimal` → DeepSeek-V3.2, `low`/`high` →
  grok-4-1-fast-reasoning, `xhigh` → gpt-6-luna; `temperature` with
  `routing_config.require_parameters: true` → gpt-4.1-nano. Treat effort as a routing
  lever, and pin parameters only when they matter.

### Decide

| Situation | Choose |
|---|---|
| One modern small model passes your evals on almost all traffic | Call it directly: no fee |
| Mixed difficulty and today's baseline is a frontier model | Router deployment, Balanced or Cost; measure against that baseline |
| A few critical steps need the best model | Cheap default; per-request `routing_config.mode: "quality"` only on those steps |
| Traffic already goes through AI Gateway | Automatic model selection (no router fee in preview) |
| You own PTU of pool models in the same resource | Router serves from your PTU first; you pay the fee only |
| Data must stay in the data zone | Data Zone Standard router deployment (fee 10% higher) |

Rules that keep it honest:

1. **Use a curated subset of at least two modern models** (`properties.routing.models`).
   Failover stays inside the subset; a single-model subset still pays the fee
   **[Documented]**. New models are not added to a subset automatically.
2. **Your deployments of subset models serve routed traffic first** (exact name and
   version, same resource) **[Documented]**: PTU, then pay-as-you-go, then router-managed
   capacity. Their quota and rate limits apply.
3. **Send a `session_id`** for conversations (`routing_config.session_affinity`, or
   the `x-ms-session-id` header) so turns stay on a model with a warm cache. Every
   `routing_config` field needs the `Foundry-Features: ModelRouterControls=V1Preview`
   header; without it the router ignores them silently.
4. **If ≥90% of traffic lands on one model, call that model directly** — you are paying
   its price plus the fee. The script prints this advice.
5. **Compare with single-model baselines** on the deployment's **Monitor** tab
   (estimates) and with Cost Management (billed). Entra callers need **Foundry User**.

### Measure the router on your workload

> **MUST:** Copy verbatim from [`references/python/measure_router.py`](references/python/measure_router.py).
> Do NOT redefine inline. It runs graded cases through router arms and fixed baselines,
> prices them from the Retail Prices API and prints counts only.

```bash
pip install "openai>=3.26,<4" "azure-identity>=1.25,<2"
python references/python/measure_router.py \
  --endpoint https://<resource>.services.ai.azure.com \
  --router <model-router-deployment|auto> --modes deployment,cost,quality \
  --baseline <small-model-deployment> [--baseline <current-model-deployment>] \
  --cases references/router_cases.jsonl --repeats 2 \
  --region <region> [--zone datazone] [--price-file prices.json] [--fee-excludes-cached]
python references/python/measure_router.py --prices-only --models gpt-5.4-mini,gpt-6-luna
```

- `--modes`: `deployment` sends no override (the deployment's mode, Balanced for
  Auto); `balanced`/`cost`/`quality` add the preview header and `routing_config.mode`.
- `--cases` (JSON Lines `{"id", "tier", "prompt", "expect", "reasoning_effort"?}`):
  `expect` is a regex on the answer. Replace the demo [cases](references/router_cases.jsonl)
  with your own prompts and graders.
- Output per arm: quality (overall and by tier), `usd_per_1k_tasks`, `fee_share_pct`,
  answering-model distribution, and the fee-vs-price table for every answering model.
- Prices come from `https://prices.azure.com/api/retail/prices` with a finite timeout.
  Meters are matched strictly (standard tier only); models without an unambiguous meter
  (often non-OpenAI pool models) are reported as `unpriced_models` and exit `1` — supply
  `--price-file` (`{"<model>": {"input", "cached", "output"}}` in USD per 1M).
- Exit `0` = all arms ran and were priced, `1` = some answering model unpriced (cost is
  a lower bound), `2` = configuration, price lookup or API error.

## Other levers (concise)

**Prompt cache.** Stable content first, dynamic content last, append-only history,
consistent `prompt_cache_key` per shared prefix (≈15 rpm per prefix+key before
misses; partition hot prefixes across keys). Structured-output schemas and tool
definitions are part of the cached prefix — keep their order deterministic. GPT-5.6+
adds billable cache writes and explicit breakpoints (`prompt_cache_options`,
`prompt_cache_breakpoint`); earlier models return HTTP 400 for those fields.
Measured on gpt-5.6-luna and gpt-6-luna with a new 2k-token prefix: the default
`implicit` mode wrote 2,009 tokens on first use, then **re-wrote the latest message
on every request** (11 tokens here); `explicit` mode with a breakpoint after the stable
prefix wrote once (1,995) and then only read. For long, variable user turns the
implicit per-request write is billed at 1.25× — prefer explicit breakpoints once the
stable boundary is known. Details:
[prompt caching][caching] and `foundry-hosted-agents` `references/prompt-caching.md`.

**Restrict tools per turn without breaking the cache.** Keep the full `tools`
array stable and pass `tool_choice={"type": "allowed_tools", "mode": "auto",
"tools": [{"type": "function", "name": "..."}]}`. Measured on gpt-5.4: a different
allowed subset on the next request still read 4,736 of 4,899 input tokens from cache.
It accepts top-level functions only — namespace members and namespaces were rejected
with HTTP 400 — so it complements, not combines with, namespaced deferral.

**Fewer round trips.** Every inference re-sends the whole prefix and history. Let
independent tool calls run in parallel (`parallel_tool_calls`, default true), return
compact tool results, cap built-in tool loops (`max_tool_calls`), limit retrieval
results, and use `detail: "low"` for images that do not need fine detail.

**Server-side state is not a token discount.** `previous_response_id` and stored
conversations save bandwidth and code, but all prior input in the chain is still
billed as input ([source][convstate]). Only caching, compaction and smaller context
reduce the bill.

**Reasoning and output.** `reasoning={"effort": ...}` (allowed values vary by model —
check the [reasoning models table][reasoning]); `text={"verbosity": "low"}` for terse
answers; set `max_output_tokens` close to the real need: Azure's admission estimate
counts it in full against TPM, and rejected (400) requests can count too
([source][az429]). For classification/extraction try the lowest supported effort first
and accept only if evals hold.

**Compaction.** Server-side: `context_management=[{"type": "compaction",
"compact_threshold": <tokens>}]` on `responses.create` (works with `store=False`);
or explicit `client.responses.compact(...)`. With stateless chaining you may drop
items before the latest compaction item; with `previous_response_id` do not prune.
See [Responses compaction][compact].

**Service tiers.** `service_tier="flex"` per request on Global Standard (preview,
50% off, variable latency, HTTP 429 when capacity is unavailable, **no automatic
Standard fallback** — retry explicitly with `default` if acceptable). Batch: separate
deployment, 50% off, 24-hour target. Priority: lower, steadier latency at a premium.
See [Flex processing][flex]. PTU vs PAYG economics: `paygo-ptu-cost-analyzer`.

## Anti-patterns

- Padding prompts to reach the 1,024-token caching threshold.
- Judging a lever by one request's `input_tokens` instead of cost per successful task.
- Assuming `tool_search` always saves money: on a small, warm catalog it measured
  +44–72% cost and slower turns.
- Editing the `tools` array per turn to restrict tools (breaks the cache) instead
  of `allowed_tools`.
- Believing `previous_response_id` makes earlier turns free.
- Enabling `tool_search` on a pre-5.4 deployment and catching the 400 silently.
- Injecting timestamps, request IDs or per-user data at the top of instructions.
- Dumping full API payloads as tool outputs; they are re-sent on every later turn.
- Setting `max_output_tokens` to the model maximum "just in case".
- Adopting model router (or `model: "auto"`) for savings without measuring it against
  the modern small model you would otherwise call; the fee can exceed its input price.
- Logging prompts or tool payloads to diagnose cost.

[pricing]: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
[az429]: https://learn.microsoft.com/microsoft-cloud/dev/dev-proxy/concepts/azure-openai-429-token-rate-limit
[convstate]: https://developers.openai.com/api/docs/guides/conversation-state
[az-toolsearch]: https://learn.microsoft.com/azure/foundry/openai/how-to/tool-search
[oai-toolsearch]: https://developers.openai.com/api/docs/guides/tools-tool-search
[caching]: https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching
[reasoning]: https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning
[compact]: https://learn.microsoft.com/azure/foundry/openai/how-to/responses#compact-a-response
[flex]: https://learn.microsoft.com/azure/foundry/openai/how-to/flex-processing
[router]: https://learn.microsoft.com/azure/foundry/openai/concepts/model-router
[router-how]: https://learn.microsoft.com/azure/foundry/openai/concepts/model-router-how-it-works
[router-controls]: https://learn.microsoft.com/azure/foundry/openai/how-to/model-router-routing-controls
[router-monitor]: https://learn.microsoft.com/azure/foundry/openai/how-to/monitor-model-router
[router-gateway]: https://learn.microsoft.com/azure/foundry/openai/how-to/model-router-ai-gateway
[retail-api]: https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices
