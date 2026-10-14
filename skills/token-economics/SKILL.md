---
name: token-economics
description: >
  Reduce cost per successful task, TPM pressure and context size for Responses API
  apps and agents. Ordered ladder: prompt/tool-output diet, deferred tool loading with
  tool_search + defer_loading (gpt-5.4+), cache-friendly prefixes, allowed_tools,
  reasoning effort/verbosity/max_output_tokens, compaction, model right-sizing,
  Flex/Batch/Priority. Live-measured script compares eager vs deferred cost, latency
  and tool selection; shows when deferral loses to a warm cache. USE FOR: token
  economics, token optimization, reduce token usage, LLM cost,
  tool_search, defer_loading, deferred tools, tool namespaces, too many tools, large
  MCP catalog, prompt caching hit rate, cached_tokens, TPM 429 from large prompts,
  reasoning effort cost, context compaction, flex processing. DO NOT
  USE FOR: PAYG-vs-PTU sizing (use paygo-ptu-cost-analyzer), Foundry spend
  dashboards/budgets (use foundry-cost-monitoring), Foundry Toolbox tool search (use
  foundry-toolbox), hosted-agent cache breakpoints (use foundry-hosted-agents).
metadata:
  version: "1.0.0"
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
| `usage.input_tokens_details.cache_write_tokens` | Cache writes; GPT-5.6+ Standard only. Missing ≠ zero |
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
| 2 | **Defer tool definitions** with `tool_search` (gpt-5.4+) | Large catalogs: −62% money, −91% input (measured) | Small catalogs: **+44–72% money**, slower — warm eager cache wins |
| 3 | **Cache-friendly prefix**: stable instructions/tools first, variable content last, append-only history | Up to ~all of the stable prefix billed at the cached rate | ≥1,024 identical leading tokens; one-character change = miss |
| 4 | **Reasoning effort, verbosity, `max_output_tokens`** | Cuts `O` (the expensive side) | Lower effort can reduce success; oversized `max_output_tokens` wastes TPM |
| 5 | **Compaction** of long conversations/agent loops | Bounds `U` growth over long sessions | Opaque item; do not prune when chaining with `previous_response_id` |
| 6 | **Right-size the model** (`-mini`/`-nano` for routing, extraction, classification) | Large rate difference | Validate with evals, not anecdotes (`foundry-evals`) |
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

- Supported on **gpt-5.4 and later** in the Responses API (Azure and OpenAI).
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
5. **Keep always-needed tools eager.** A tool used on most turns is cheaper as an
   eager definition than as a search every time.
6. **Verify the wire request through frameworks.** Agent frameworks and SDK
   wrappers may not serialize `namespace`, `defer_loading` or `tool_search`, or may
   drop unknown fields; deferral then silently becomes eager (or a 400). Check one
   real request or the `tool_search_call` items in the output before trusting savings.
7. Different features: Foundry **Toolbox** tool search (`foundry-toolbox`) discovers
   tools in a versioned Toolbox; the OpenAI **Agents API** auto-defers MCP tools.
   The rules here apply to declared tools in Responses API requests.

### Measured evidence (2026-10-14, gpt-5.4, Sweden Central, Global Standard)

Synthetic catalogs, the six [demo cases](references/demo_cases.jsonl) (different
domains), complete tool loops, `reasoning.effort=low`, `store=False`. Money is the
input-equivalent cost `U + c·C + r·O` with the retail gpt-5.4 Global ratios of that
day (`c = 0.1`: $0.25 vs $2.50 per 1M cached/uncached input; `r = 6`: $15 output).
*Independent* = each case is a fresh conversation (steady traffic on the same
prompt prefix); *session* = the six cases are turns of one conversation.

| Catalog (eager tokens/request) | Mode | Raw input | **Money** | Latency | Selection |
|---|---|---|---|---|---|
| 30 fn / 5 ns (≈3.4k) | independent | −65.8% | **+72.3%** | +56% | 6/6 both |
| 30 fn / 5 ns | session | −12.9% | **+44.4%** | +73% | 6/6 both |
| 160 fn / 20 ns (≈22k) | independent | −90.7% | **−61.7%** | −17% | 6/6 both |
| 160 fn / 20 ns | session | −83.0% | **−37.2%** | −7% | 6/6 both |

Single-turn smokes reproduced the raw-input cut on gpt-5.4-mini (−64.7%, 30 fn).
A deferred **MCP** server (Microsoft Learn MCP, 3 tools) cut input 9,508 → 6,878
(−28%) with the same answer; `mcp_list_tools` still runs. Client-executed search
worked end to end on Azure.

What the numbers say:

- **Raw input is the wrong metric.** With a small catalog, deferral cut input by
  two thirds but **raised cost by 44–72% and latency by 56–73%**: the eager prefix
  was ~90% cached (billed at 10%), while deferral added search output (billed 6×)
  and a short, rarely cached prefix.
- With a large catalog the uncached catalog dominates and deferral wins on money,
  TPM and latency, even when eager traffic is fully warm.
- In sessions the loaded definitions stay in history and are re-sent every turn,
  so savings shrink; the cache then helps both variants.
- Searches may run twice per task (`paths`, then `query`). Selection accuracy was
  unchanged on these synthetic cases — verify on yours.

### Decide with your own numbers

Per task, deferral pays when

```
  T_cat · (1 − h_E·(1 − c)) · n   >   ΔO · r  +  Δcache
  T_cat = catalog tokens removed per inference   n = inferences per task
  h_E   = eager cache-hit ratio                   ΔO = extra output (search + reasoning)
  Δcache = cost of cache hits the shorter deferred prefix loses
```

With a warm cache (`h_E ≈ 0.9`, `c = 0.1`) each removed catalog token is worth only
≈0.19 uncached tokens, so a small `T_cat` cannot pay for search output priced at
`r` (6–8×). Rules of thumb from the data, not guarantees:

- **Defer** when the catalog is a large share of the request (≈10k+ tokens), the tool
  set varies per user/tenant (eager cache already broken), traffic is bursty (the
  in-memory cache usually expires after 5–10 idle minutes), TPM 429s hurt, or
  selection accuracy drops with catalog size.
- **Stay eager** for catalogs of a few thousand tokens with steady traffic, or tools
  used on most turns. To restrict tools per turn without breaking the cache, use
  `tool_choice: allowed_tools` (below) instead of editing the `tools` array.
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
  [--cached-ratio 0.1 --output-ratio 6]
```

- `--endpoint` also accepts a Foundry project endpoint (`…/api/projects/<p>`).
- Identity needs **Cognitive Services OpenAI User** on the resource; token scope is
  `https://ai.azure.com/.default`.
- `--tools-file` takes your real catalog (a JSON array of Responses tools) and
  derives the deferred variant (`defer_loading` on functions, namespace members and
  MCP servers, plus `tool_search`). Supply `--expect-tool <name>` or `--cases`.
- `--cases` (JSON Lines `{"prompt", "expect_tool"}`) measures selection success
  per variant; `--session` chains the cases as turns of one conversation;
  `--cached-ratio`/`--output-ratio` (from the current price sheet) add an
  `input_equivalent_cost` comparison. Latency is reported as `elapsed_s`.
- Exit `0` = deferred variant called every expected tool, `1` = it missed one
  (selection regression), `2` = API/config/input error (e.g. the HTTP 400 above).
- Run each variant several times and report distributions. There is no usable
  pre-flight token counter on Azure: `responses.input_tokens.count` returned HTTP
  400 (`This model is not supported by Responses API`) for gpt-5.4, gpt-5.4-mini
  and gpt-5-mini — measure with real `usage`.

## Other levers (concise)

**Prompt cache.** Stable content first, dynamic content last, append-only history,
consistent `prompt_cache_key` per shared prefix (≈15 rpm per prefix+key before
misses; partition hot prefixes across keys). Structured-output schemas and tool
definitions are part of the cached prefix — keep their order deterministic. GPT-5.6+
adds billable cache writes and explicit breakpoints (`prompt_cache_options`,
`prompt_cache_breakpoint`); earlier models return HTTP 400 for those fields. Details:
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
