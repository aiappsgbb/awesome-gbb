---
name: token-economics
description: >
  Reduce LLM token cost, TPM pressure and context size for Responses API apps and agents
  without degrading task success. Ordered optimization ladder: prompt/tool-output diet,
  deferred tool loading with tool_search + defer_loading (gpt-5.4+), prompt-cache prefix
  design, reasoning effort/verbosity/max_output_tokens, compaction, model right-sizing,
  Flex/Batch/Priority tiers. Live-measured eager-vs-deferred script and cache break-even
  math. USE FOR: token economics, token optimization, reduce token usage, LLM cost
  optimization, tool_search, defer_loading, deferred tools, tool namespaces, too many
  tools, large MCP catalog, prompt caching hit rate, cached_tokens, TPM 429 from large
  prompts, reasoning effort cost, context compaction, flex processing, cost per task.
  DO NOT USE FOR: PAYG-vs-PTU sizing (use paygo-ptu-cost-analyzer), Foundry spend
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
| **Throughput (TPM/429s)** | Total tokens per minute | Treat TPM headroom as driven by total input, cached or not, plus the output reservation. Azure and OpenAI count `max_output_tokens` against the limit at admission, even if fewer tokens are generated ([source][ratelimits]). |
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

| # | Lever | Typical effect | Watch out for |
|---|---|---|---|
| 1 | **Diet**: remove dead instructions, duplicated policy, verbose few-shots; trim tool **outputs** to the fields the model needs; paginate | Cuts `U` everywhere, every turn | Tool outputs accumulate in history on every later turn — they are often the largest line item |
| 2 | **Defer tool definitions** with `tool_search` (gpt-5.4+) | −65% to −85% input in the measurements below | Can lose to a *warm* eager cache on money; see break-even |
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
6. Different features: Foundry **Toolbox** tool search (`foundry-toolbox`) discovers
   tools in a versioned Toolbox; the OpenAI **Agents API** auto-defers MCP tools.
   The rules here apply to declared tools in Responses API requests.

### Measured evidence (2026-10-14, Sweden Central, Global Standard)

Synthetic catalog; one complete tool turn = first inference + follow-up after a
synthetic function output; `reasoning.effort=low`, `store=False`. Values are
`input / cached` tokens per inference. The deferred model loaded only `shipping`.

| Model | Catalog | Eager | Deferred | Raw input change |
|---|---|---|---|---|
| gpt-5.4-mini | 30 fn / 5 ns | 5,041/4,864 → 5,157/4,864 | 1,684/0 → 1,920/0 | **−64.7%** (+152 output) |
| gpt-5.4 | 30 fn / 5 ns | 5,041/4,864 → 5,138/4,992 | 1,682/0 → 1,772/1,536 | **−65.7%** (+61 output) |
| gpt-5.4 | 160 fn / 20 ns | 27,190/0 → 27,286/27,136 (cold); 27,190/27,008 → 27,294/27,136 (warm) | 4,033–4,058/0 → 4,127–4,206/0–1,024 | **−85%** (+70–200 output) |

Observations to plan around:

- Deferred requests add **output** (the search step plus extra reasoning) — this is
  the expensive token class. Searches may run twice (e.g. `paths` + `query`).
- The eager prefix cached reliably once warm; the shorter deferred prefix cached
  only intermittently. Cache hits are best-effort, never guaranteed.

### Break-even: when deferring saves money

With `c = p_cached / p_in`, `r = p_out / p_in`, eager per-task input-equivalent cost
`E(h) = E_in·(1 − h·(1 − c)) + r·E_out` for an eager cache-hit ratio `h`, and
deferred cost `D = D_U + c·D_C + r·D_out`, deferring saves money when
`h < (E_in + r·E_out − D) / (E_in·(1 − c))` (i.e. `E(h) > D`).

Worked example, 160-function row with **illustrative** ratios `c = 0.1`, `r = 8`
(replace with your current rates): eager with no cache hits ≈ 55.2k, eager fully
warm ≈ 6.5k, deferred ≈ 9.5k input-equivalent per task. Deferred wins on money only
below an eager hit ratio of roughly **93%**; it always wins on TPM (≈54k → ≈8k
input tokens per task) and context size.

Interpretation:

- **Defer** when the catalog is large relative to the rest of the prompt, the tool set
  varies by user/tenant (which already breaks the eager cache), traffic is bursty or
  low-volume (in-memory cache typically expires after 5–10 minutes idle), you hit TPM
  429s, or tool-selection accuracy drops with catalog size.
- **Stay eager** for small catalogs, tools used on most turns, or a single static
  catalog with steady high-volume traffic and measured hit ratios above break-even.
- Raising cache retention (`prompt_cache_retention: "24h"` on supported pre-5.6
  models, extended by default on gpt-5.5) raises `h` and moves break-even — measure.

## Measure before and after

> **MUST:** Copy verbatim from [`references/python/measure_tool_search.py`](references/python/measure_tool_search.py).
> Do NOT redefine inline. It runs the same task eager vs deferred as a complete tool
> turn and prints usage counters only.

```bash
pip install "openai>=3.26,<4" "azure-identity>=1.25,<2"
python references/python/measure_tool_search.py \
  --endpoint https://<resource>.openai.azure.com \
  --model <gpt-5.4-or-later-deployment> \
  [--tenant <tenant-id>] [--tools-file tools.json --prompt "..." --expect-tool <name>]
```

- `--endpoint` also accepts a Foundry project endpoint (`…/api/projects/<p>`).
- Identity needs **Cognitive Services OpenAI User** on the resource; token scope is
  `https://ai.azure.com/.default`.
- `--tools-file` takes your real catalog (a JSON array of Responses tools) and
  derives the deferred variant (`defer_loading` on functions, namespace members and
  MCP servers, plus `tool_search`).
- Exit `0` = deferred variant called the expected tool, `1` = it did not (selection
  regression), `2` = API/config error (e.g. the HTTP 400 above).
- Run each variant several times; report distributions and the eager cache-hit ratio
  of **production** traffic, not of a warm benchmark loop.

## Other levers (concise)

**Prompt cache.** Stable content first, dynamic content last, append-only history,
consistent `prompt_cache_key` per shared prefix (≈15 rpm per prefix+key before
misses; partition hot prefixes across keys). Structured-output schemas and tool
definitions are part of the cached prefix — keep their order deterministic. GPT-5.6+
adds billable cache writes and explicit breakpoints (`prompt_cache_options`,
`prompt_cache_breakpoint`); earlier models return HTTP 400 for those fields. Details:
[prompt caching][caching] and `foundry-hosted-agents` `references/prompt-caching.md`.

**Reasoning and output.** `reasoning={"effort": ...}` (allowed values vary by model —
check the [reasoning models table][reasoning]); `text={"verbosity": "low"}` for terse
answers; set `max_output_tokens` close to the real need because it is reserved
against TPM. For classification/extraction try the lowest supported effort first
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
- Assuming `tool_search` always saves money: it can lose to a warm static cache.
- Enabling `tool_search` on a pre-5.4 deployment and catching the 400 silently.
- Injecting timestamps, request IDs or per-user data at the top of instructions.
- Dumping full API payloads as tool outputs; they are re-sent on every later turn.
- Setting `max_output_tokens` to the model maximum "just in case".
- Logging prompts or tool payloads to diagnose cost.

[pricing]: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
[ratelimits]: https://learn.microsoft.com/microsoft-cloud/dev/dev-proxy/concepts/llm-rate-limits
[az-toolsearch]: https://learn.microsoft.com/azure/foundry/openai/how-to/tool-search
[oai-toolsearch]: https://developers.openai.com/api/docs/guides/tools-tool-search
[caching]: https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching
[reasoning]: https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning
[compact]: https://learn.microsoft.com/azure/foundry/openai/how-to/responses#compact-a-response
[flex]: https://learn.microsoft.com/azure/foundry/openai/how-to/flex-processing
