# Prompt caching for MAF hosted agents

Companion to [Prompt caching and inference efficiency](../SKILL.md#prompt-caching-and-inference-efficiency).
**Public-source review: 2026-09-16. No live caching validation.** The canonical
runtime, dependencies, and [upstream pin](upstream-pin.md) are unchanged.
Existing hosted-runtime validation does not certify cache hits, savings, or
breakpoint support for this composition.

## Ownership and the baseline

The path is `ResponsesHostServer -> Agent + SkillsProvider ->
FoundryChatClient -> model service`. Foundry manages hosting and native
session persistence; MAF assembles context and executes the tool/inference
loop; the model service manages the temporary key/value (KV) cache of
processed input tokens. It is not an application response cache.
Keep the [single-agent runtime](python/main.py) or
[SkillsProvider runtime](python/container.py); no manual model-call or
tool-loop implementation is needed for automatic caching.

Start with these content decisions, not new inference parameters:

1. Remove redundant instructions, unused tool definitions, and unnecessary
   tool-output content before optimizing cache reuse. A smaller useful
   prompt is preferable to padding that merely reaches a caching threshold.
2. Keep reusable baseline instructions, skill names/descriptions/order, tool
   schemas/order, and structured-output schemas deterministic for the same
   authorized configuration. Avoid timestamps, random IDs, and per-request
   values in that prefix. Do not freeze permissions or advertise unauthorized
   skills/tools to preserve a cache hit.
3. Preserve `SkillsProvider` progressive disclosure: advertise metadata,
   load a skill body on demand, then read resources/run scripts only when
   needed. Do not also concatenate those bodies into `Agent.instructions`.
   Skill loading can cause another model inference; optimize the complete
   turn, not just the initial prompt size.
4. Keep user input, retrieved documents, memory, and tool results after
   stable content where the framework's assembly permits. Do not reorder
   conversation history or change message roles to manufacture a prefix.
   Compaction, catalog changes, or injected context can change cache matching.

Sources: [MAF hosting][hosting], [Agent Skills][skills], and
[Azure OpenAI prompt caching][caching].

## Configure the internal inference, not just the outer request

The external client invokes the **hosted agent endpoint**. The container's
`Agent` and `FoundryChatClient` make the subsequent model requests. Put any
compatible inference defaults on that internal Agent/client (the canonical
Agent already uses `default_options`); do not assume an option sent by the
external caller propagates to every internal inference. No `azure.yaml`
flag or hosted deployment switch is prescribed for caching.

For supported models/deployments, `prompt_cache_options` selects a
request-wide policy, whereas `prompt_cache_breakpoint` marks a specific
content boundary. Setting mode to `implicit` uses the service's automatic
latest-message breakpoint plus any explicitly supplied breakpoints. It
does **not** identify or mark "the end of baseline instructions plus the
SkillsProvider catalog." Setting mode to `explicit` uses only supplied
breakpoints; with none, eligible Standard requests do not read/write the
prompt cache. Do not enable explicit-only mode before verifying the marker
survives the entire serialization path.

`prompt_cache_key` helps matching/routing for requests sharing a prefix;
use a stable, non-sensitive, opaque key for an appropriate configuration
cohort if supported. It is **not an authorization or tenant-isolation
control**, and does not grant access to cached content. Enforce identity,
tool/skill permissions, and data boundaries independently. Do not insert
credentials or personal data into keys.

## Compatibility: service support is not pinned SDK support

The following is the documented Azure OpenAI service contract as of the
review date, not a guarantee for every model reachable through Foundry.
Check the actual model family/version, deployment type, API, and resolved
SDK versions before selecting optional parameters.

| Path | Documented service behavior | Operational boundary |
|---|---|---|
| Automatic caching | Enabled by default on supported models; the in-memory support statement covers Azure OpenAI GPT-4o and newer with eligible inference operations. A cacheable prefix needs at least 1,024 identical initial tokens. | No breakpoint adapter required. A supported model and sufficiently long prefix still do not guarantee a hit on a particular inference. No padding. |
| GPT-5.6 family and later, Standard pay-as-you-go | Responses and Chat Completions support `prompt_cache_options` and explicit `prompt_cache_breakpoint` content markers. Cache writes can be billed separately; reads are discounted. | Earlier model families reject these two parameters with HTTP 400. Do not make them mandatory for the skill's existing model choices. |
| Provisioned Throughput managed (PTU-M) | Prompt caching remains supported, but explicit breakpoints and `cache_write_tokens` reporting are not supported. | Do not transfer the Standard breakpoint recipe to PTU-M or interpret a missing write counter as no cache use. |

For the supported breakpoint path, Responses accepts markers on
`input_text`, `input_image`, and `input_file` blocks. A marker includes
that block and the content before it, not just the marked text. The service
allows up to four new writes per request; implicit mode consumes one slot
for the latest message, leaving up to three explicit writes. See
[the service limits][caching] before designing multiple breakpoints.

Retention is also model-specific. For GPT-5.6 and later,
`prompt_cache_options.ttl` has the sole supported/default value `30m`
(minimum lifetime), not a selection of storage policy. For earlier models,
`prompt_cache_retention` selects a maximum-retention policy where supported;
extended retention is not supported by every model. Do not copy a `24h`
setting to all deployments or infer KV lifetime from session lifetime.
Use [the current retention and residency requirements][caching].

**What the repository actually constrains.** The
[canonical dependency file](python/pyproject.toml) specifies
`agent-framework-core~=1.14.0`, `agent-framework-foundry~=1.11.0`,
`agent-framework-foundry-hosting==1.0.0b260813`, and
`azure-ai-projects~=2.3.0`, alongside exact Agent Server betas and the other
documented dependencies. These are a coherent hosted-runtime cohort, not
a declaration of support for the latest caching API.

Public package metadata/source inspection (no install or execution) found:

- [Foundry 1.11.0][foundry-release] delegates Responses handling to
  `RawOpenAIChatClient` and requires `agent-framework-openai>=1.10.0,<2`.
  The skill does not directly pin that transitive package or `openai`.
- [OpenAI integration 1.10.0][openai-release], the declared minimum, exposes
  `prompt_cache_key`/`prompt_cache_retention` and maps cache reads, but lacks
  the new explicit-breakpoint transport and cache-write mapping. Its
  `openai>=1.99.0,<3` bound does not itself ensure a sufficiently new SDK.
  This is a lower-bound inspection, **not** a claim about the versions
  resolved in an existing container.
- [Current MAF OpenAI documentation][openai-docs] describes
  `Content.additional_properties["prompt_cache_breakpoint"]` and normalized
  cache usage. In the [Responses client source][main-client] at `main`
  snapshot `5391d56de5799a97a6b2891879961880bf38853c`, serialization attaches
  supported content markers and maps cache reads/writes. The source requires
  `openai>=2.45.0` for `prompt_cache_options`. This is upstream source
  evidence, **not** a new pin, a sufficient end-to-end requirement, or
  proof that the skill's pinned cohort supports the feature.

Do not upgrade packages or force raw `extra_body` fields merely to make
this guide appear executable. Record the actual resolved cohort and verify
option acceptance, content serialization, Foundry project routing, and
usage reporting together in a separately authorized integration exercise.

## Advanced integration: ChatMiddleware, not a replacement loop

[ChatMiddleware][middleware] is the documented interception point **inside**
MAF's function invocation loop. It sees messages, options, and results for
each model call, including calls after tool results. This makes it an
extension point for inference policy/measurement without implementing a
second agent loop. Its existence is not a ready-made prefix adapter.

**This skill has no verified adapter that places a breakpoint after the
entire stable prefix assembled by Agent and SkillsProvider.** A candidate
integration must identify the complete rendered prefix, including how
`instructions`, provider messages, and tool definitions are serialized.
Some instructions may be represented separately from `ChatContext.messages`.
Do not assume the last system/developer message is the boundary: it may
contain memory, user-specific context, or other changing provider content.
A marker caches everything before it too; a stable-looking final block does
not make earlier content stable.

Before adopting an adapter, validate on synthetic, non-sensitive inputs
that it preserves the message roles/order, tool schemas, native history,
and streaming behavior; marks only an identified stable boundary; and
survives provider serialization on every applicable internal inference.
Then, in a separately authorized live test, verify the actual service
reads/writes and latency/cost. Offline request-shape checks alone cannot
prove a KV cache hit. Until then, keep automatic caching as the baseline
and treat breakpoint integration as unvalidated, not canonical code.

## Keep history and other caches separate

The canonical `default_options={"store": False}` disables downstream
response storage, **not prompt caching**. Keep it in the existing runtime.
Do not add a `HistoryProvider` that loads a second copy of history, or
downstream `conversation`, `conversation_id`, or `previous_response_id`
continuation management to the default `ResponsesHostServer` path.
Outer Responses/session continuation remains the host's responsibility.

Current [hosting documentation][hosting] names the default non-workflow
history source `agent_server` and describes safeguards against duplicate
history. That newer API description is not an instruction to retrofit host
arguments onto the pinned hosting beta.

Persisted session state restores application context, skill-source caches
avoid repeated discovery/content fetches, and a warm container avoids
startup work. None is the model's KV cache; none guarantees that cached
model computations remain resident or that the next inference hits.

## Observe each inference, then the whole turn

One user-visible agent turn can include several model inferences around
`load_skill`, other tools, and follow-up reasoning. Correlate individual
inference spans with the agent turn; do not substitute the outer HTTP
status, resumed session, aggregate token count, or fast container readiness
for cache-hit evidence.

| Signal | What to inspect |
|---|---|
| Cache reads | Responses model usage: `input_tokens_details.cached_tokens`. Chat Completions uses `prompt_tokens_details.cached_tokens`. Current MAF normalizes reads as `cache_read_input_token_count`. |
| Cache writes | On supported Standard GPT-5.6+ Responses, `input_tokens_details.cache_write_tokens`; Chat Completions uses `prompt_tokens_details.cache_write_tokens`. Current MAF normalizes writes as `cache_creation_input_token_count`. Missing/unsupported fields are unknown, not measured zero. |
| Telemetry | Current MAF documents `gen_ai.usage.cache_read.input_tokens` and `gen_ai.usage.cache_creation.input_tokens`. Verify the resolved provider/instrumentor actually exports them; a type or property in current docs is not proof of pinned-stack telemetry. |
| Cost | Compare uncached input, cached reads, billable cache writes, output, and total internal inference count using the selected model/SKU's current rates. For PTU-M, assess capacity/throughput economics separately from pay-as-you-go token charges. |
| Latency | Measure per-inference time to first token (TTFT) for streaming and total latency, then end-to-end agent-turn latency. Keep cold-container startup and tool execution separate; a faster turn alone does not prove a cache hit. |

For a later authorized comparison, hold model/version, deployment, runtime
cohort, stable catalog/tool schema, and workload shape constant; compare
first-use and repeated-prefix requests, then intentionally vary the prefix.
Record observed counters and TTFT distributions rather than asserting the
second request must hit. Successful session resume or HTTP 200 only proves
that another part of the system worked.

Use correlation IDs, version identifiers, token counts, and timings.
**Do not enable sensitive-data capture or log prompts, skill bodies, tool
arguments/results, or model outputs for cache diagnosis.** Follow the
existing [observability skill](../../foundry-observability/SKILL.md) for
telemetry ownership; no new instrumentation runtime is introduced here.

[hosting]: https://learn.microsoft.com/agent-framework/hosting/foundry-hosted-agent?pivots=programming-language-python
[skills]: https://learn.microsoft.com/agent-framework/agents/skills?pivots=programming-language-python
[middleware]: https://learn.microsoft.com/agent-framework/agents/middleware?pivots=programming-language-python
[caching]: https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching
[openai-docs]: https://learn.microsoft.com/agent-framework/integrations/by-component/model-providers/openai?pivots=programming-language-python
[main-client]: https://github.com/microsoft/agent-framework/blob/5391d56de5799a97a6b2891879961880bf38853c/python/packages/openai/agent_framework_openai/_chat_client.py
[foundry-release]: https://pypi.org/project/agent-framework-foundry/1.11.0/
[openai-release]: https://pypi.org/project/agent-framework-openai/1.10.0/
