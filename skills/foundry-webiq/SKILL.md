---
name: foundry-webiq
description: >
  Integration guidance for grounding a Foundry hosted agent on Microsoft
  Web IQ — Microsoft's AI-native web grounding service (web/news/images/
  video; MCP-native via JSON-RPC 2.0, also REST; citation-ready structured
  JSON). Covers the MCP tool connection (API-key static header + Microsoft
  Entra bearer auth), the consumer MCPStreamableHTTPTool pattern with
  runtime tool auto-discovery, a REST fallback, and citation/provenance
  mapping. Web IQ is limited-access (aka.ms/webiq-waitlist); the endpoint,
  key header, and Entra scope are consumer-supplied — never hardcoded.
  USE FOR: web iq, web grounding, real-time web context, fresh web data,
  agent web search, citation grounding, news/image/video grounding, MCP
  grounding tool, JSON-RPC grounding. DO NOT USE FOR: internal-doc RAG /
  knowledge bases (use foundry-iq), Grounding with Bing web_search (use
  foundry-toolbox), deploying your own MCP server (use foundry-mcp-aca),
  the hosted agent runtime (use foundry-hosted-agents).
metadata:
  version: "1.0.2"
---

# Microsoft Web IQ Grounding for Foundry Agents — Reference Guide

Integration guidance for grounding a **Foundry hosted agent** on
**Microsoft Web IQ** — Microsoft's AI-native web grounding service that
returns citation-ready structured JSON (titles, URLs, snippets,
timestamps, provenance) across web / news / images / video, with
passage-level retrieval optimized for direct context-window injection.

This skill is **integration guidance only** — there is nothing to deploy.
You wire Web IQ into an *existing* hosted agent as a grounding tool. The
recommended path is Web IQ's **native MCP endpoint** registered as an MCP
tool; a **REST** fallback is documented for teams that prefer it.

> **⚠️ Web IQ is limited-access (preview).** Request access at
> [`aka.ms/webiq-waitlist`](https://aka.ms/webiq-waitlist). The full
> technical documentation (auth header name, Entra scope, MCP endpoint
> URL, JSON-RPC tool names, REST routes, response schema) lives behind an
> Entra sign-in at <https://webiq.microsoft.ai/documentation/>. **This
> skill never hardcodes those values** — they are *consumer-supplied
> config* you read from your own Web IQ docs / Playground and pass via
> environment variables / a Foundry connection. The Web IQ docs site
> itself ships an explicit note telling automated agents not to fabricate
> routes or permissions. Honor it: copy the real values from your tenant,
> do not guess them.

---

## When to use foundry-webiq

Use this skill when an agent needs **fresh, cited, open-web context** at
inference time and you want **structured, developer-controlled grounding
data** (not a black-box answer). Web IQ is positioned as the next-gen
successor to Grounding with Bing: you get the ranked passages + provenance
and decide how to inject them.

There are three adjacent "web / grounding" surfaces in this catalog. Pick
the right one:

| You want… | Use | Not this skill because… |
|-----------|-----|-------------------------|
| Real-time **open-web** grounding with structured citations, via MCP/REST, model-agnostic | **foundry-webiq** (this skill) | — |
| The managed **Grounding with Bing** hosted `web_search` tool inside the Foundry Toolbox | [`foundry-toolbox`](../foundry-toolbox/SKILL.md) | Toolbox `web_search` is a different, managed Bing tool — not the standalone Web IQ API |
| RAG over **your own documents** in an Azure AI Search Knowledge Base (incl. its "Web IQ knowledge source" type) | [`foundry-iq`](../foundry-iq/SKILL.md) | foundry-iq is enterprise RAG over indexed corpora, not the standalone Web IQ grounding service |
| To **deploy your own** MCP server | [`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md) | Web IQ is a Microsoft-hosted MCP endpoint you *consume*, not one you build |
| The **hosted agent runtime** itself (deploy, identity, RBAC) | [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) | This skill assumes the agent already exists and only adds the grounding tool |

> **Disambiguation note — two things share the name "Web IQ".** This skill
> is the **standalone Web IQ grounding service** (`webiq.microsoft.ai`).
> `foundry-iq` separately exposes a **"Web IQ knowledge source"** *type*
> inside an AI Search Knowledge Base (public-web grounding folded into a
> RAG index). They are different integration surfaces. If your agent
> calls the grounding API directly → here. If public web is one source in
> a larger Knowledge Base → `foundry-iq`.

---

## What you must capture from your Web IQ docs

Before wiring anything, open your gated Web IQ documentation / Playground
and record the following values. Everything in this skill is parameterized
on them — you never paste them as literals into committed code, and you
never invent them.

| Value | Env var this skill uses | Where to find it |
|-------|-------------------------|------------------|
| MCP endpoint URL (streamable HTTP) | `WEBIQ_MCP_ENDPOINT` | Web IQ docs → MCP / "Connect via MCP" |
| API key / subscription secret | `WEBIQ_API_KEY` | Web IQ Playground → keys, or your APIM subscription |
| **Header name** the key goes in | `WEBIQ_API_KEY_HEADER` | Web IQ auth docs (e.g. a subscription-key or `x-api-key` style header — confirm the exact name) |
| Entra **scope / resource** for bearer auth | `WEBIQ_ENTRA_SCOPE` | Web IQ auth docs → "Microsoft Entra" (an `api://<app-id>/.default` or resource URI) |
| REST base URL (fallback only) | `WEBIQ_REST_ENDPOINT` | Web IQ docs → REST reference |
| Response field names for citations | (mapped in code) | Web IQ response schema — confirm the exact JSON keys for title / url / snippet / timestamp / provenance |

> The **only** genuinely-gated bits are the header *name*, the Entra
> *scope*, the REST *route*, and the response *field names*. Auth values
> (key, tenant) are secrets you already hold. Tool/method names are
> **discovered at runtime** (see Native MCP path) so you do not need to
> know them up front.

---

## Prerequisites

- **Web IQ access** — approved via the waitlist; a usable credential
  (API key *or* an Entra app/identity authorized for the Web IQ scope).
- **A Foundry hosted agent** already deployed (see
  [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md)). This
  skill adds a tool to it; it does not create it.
- **A Foundry project connection** for the credential (recommended) so the
  key/identity is managed centrally rather than baked into container env.
  See Microsoft Learn, *"Set up MCP server authentication"* for Foundry.
- Python deps already present in a hosted-agent container:
  `agent-framework` (MAF), `httpx`, and — for Entra auth —
  `azure-identity`.

---

## Auth wiring

Web IQ supports two credential models. Document/choose one; both flow into
the same MCP or REST call.

### API-key auth — static header

Simplest path, and the right default when Web IQ is an **external,
non-AAD** MCP server. The key rides as a static request header whose
**name you confirm from the Web IQ docs** (`WEBIQ_API_KEY_HEADER`) and
whose value is the secret (`WEBIQ_API_KEY`). In Foundry, create a
**key-based** MCP tool connection so the key is stored as a project
connection secret, not in container env.

Because the header is static and identical on every request — including
the MCP `initialize` / `tools/list` bootstrap — set it as a default header
on an `httpx.AsyncClient` passed via `http_client=`. (Current MAF
`MCPStreamableHTTPTool` exposes **no** `headers=` parameter — it is accepted
but silently ignored — and a per-call `header_provider=` misses the
bootstrap, exactly as in the Entra caveat below.) See
`build_webiq_mcp_tool_apikey()` in
[`references/python/webiq_mcp_grounding.py`](references/python/webiq_mcp_grounding.py).

### Microsoft Entra auth — bearer token

When Web IQ is fronted by Microsoft Entra (OAuth2), mint a bearer for the
Web IQ **scope** (`WEBIQ_ENTRA_SCOPE`) and send `Authorization: Bearer
<token>`. Use the **agent's managed identity** (or a project
managed-identity connection) so no secret is stored.

> **Critical bootstrap caveat (inherited from foundry-hosted-agents).** If
> the MCP server requires auth on the **`initialize` / `tools/list`
> bootstrap** (not just `tools/call`), a per-call `header_provider=`
> callback is **not enough** — it only covers `call_tool()` and the
> handshake 401s. The robust pattern is an `httpx.AsyncClient` whose
> `auth=` mints the bearer for *every* request (bootstrap included),
> passed via `http_client=`. Do **not** combine `header_provider=` and
> `http_client=`. Full rationale and the static-vs-bootstrap matrix live
> in [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) §
> "MCP Tools". This skill reuses that pattern — see
> `build_webiq_mcp_tool_entra()` in
> [`references/python/webiq_mcp_grounding.py`](references/python/webiq_mcp_grounding.py).

---

## Native MCP path

**Recommended.** Register Web IQ's hosted MCP endpoint
(`WEBIQ_MCP_ENDPOINT`) as an MCP tool on the hosted agent. The MAF
`MCPStreamableHTTPTool` performs the JSON-RPC 2.0 `initialize` +
`tools/list` handshake and **auto-discovers** Web IQ's grounding tools at
runtime — so you do **not** hardcode Web IQ's JSON-RPC method/tool names.
The model sees whatever grounding tools Web IQ advertises and calls them
itself.

Key wiring decisions, all reused from the consumer MCP pattern in
[`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) (do not
duplicate that code — import/copy the canonical helper):

- `approval_mode="never_require"` so grounding calls don't block on
  human-in-the-loop.
- `parse_tool_results=<extractor>` to unwrap MCP `CallToolResult.content[]`
  into clean text + citations, avoiding the `[<Content object>]` repr leak.
  Web IQ's structured fields are mapped here.
- `request_timeout` generous enough for live web retrieval (Web IQ targets
  ~164 ms P95, but allow headroom for cold paths).

The full, runnable wiring (both auth variants + the citation extractor)
is the single source of truth in
[`references/python/webiq_mcp_grounding.py`](references/python/webiq_mcp_grounding.py).
The declarative connection/env plumbing for `agent.yaml` is sketched in
[`references/agent.yaml.sample`](references/agent.yaml.sample).

---

## REST fallback path

For teams who prefer REST over MCP, wrap a single `httpx` call to
`WEBIQ_REST_ENDPOINT` as an in-process agent tool. You lose runtime tool
auto-discovery (you own the request/response shape), so this path requires
you to confirm the REST route, query params, and response schema from your
Web IQ docs. The defensive, env-driven template is in
[`references/python/webiq_rest_grounding.py`](references/python/webiq_rest_grounding.py)
— it sends the API-key header, calls `raise_for_status()`, and returns
parsed citations with explicit "confirm these JSON keys" markers.

---

## Citation handling

Web IQ returns provenance per passage. Map its fields into your agent's
citation/annotation surface so sources reach both the model (for grounded
reasoning) and the end user (for verifiable links). The extractor in
`webiq_mcp_grounding.py` collects `title / url / snippet / timestamp /
provenance` into a normalized list — **confirm the exact source JSON keys
against your Web IQ response schema** and adjust the mapping; the code
marks each assumed key with a `# CONFIRM:` comment so nothing ships as an
invented field name. Surface the URLs as annotations/footnotes, and keep
the snippet + timestamp so the model can reason about recency.

---

## Token-efficiency notes

Web IQ's value proposition is **passage-level, citation-ready retrieval**
— you inject ranked snippets, not whole pages. To keep context lean:

- Shape queries narrowly; prefer the structured query params Web IQ
  exposes (freshness window, result count, content type) over broad
  natural-language dumps.
- Inject only the top-ranked passages + their URLs/timestamps; drop
  low-score results before they reach the context window.
- Let the model cite by URL rather than re-embedding full snippets in its
  answer.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `401 Unauthorized` on first call | Wrong API-key **header name**, or expired/empty key | Confirm `WEBIQ_API_KEY_HEADER` exactly matches the Web IQ docs; verify the key in the Playground |
| `401/403` only on bootstrap (`initialize`/`tools/list`) under Entra | `header_provider=` used for an AAD-gated bootstrap | Switch to the `http_client=` + `httpx.Auth` variant (`build_webiq_mcp_tool_entra`) so the handshake is authenticated |
| `403` with a valid token | Bearer minted for the wrong **scope/audience** | Set `WEBIQ_ENTRA_SCOPE` to the resource Web IQ documents (e.g. `api://<app-id>/.default`); confirm the identity is authorized |
| MCP handshake hangs / times out | Wrong `WEBIQ_MCP_ENDPOINT`, or transport mismatch (SSE vs streamable HTTP) | Verify the endpoint URL and that it speaks streamable HTTP JSON-RPC 2.0 |
| Tool list empty after handshake | Access not yet provisioned / region gating | Confirm waitlist approval; check Web IQ status for your tenant |
| Results return but `[<Content object>]` leaks into the answer | Missing `parse_tool_results` extractor | Wire `parse_tool_results=` per the reference (`_webiq_result_parser`) |
| Citations missing fields | Response schema keys differ from the assumed mapping | Update the `# CONFIRM:` keys in the extractor to match your Web IQ response schema |
| Empty grounding results | Over-broad/over-narrow query, or freshness filter too tight | Re-shape the query params per *Token-efficiency notes* |

---

## Validation evidence

The Web IQ contract is Entra-gated, so the skill's Web-IQ-specific values
(endpoint, header name, Entra scope, response field names) remain
`# CONFIRM:` placeholders and are **not** yet proven against a live Web IQ
endpoint (see the dormant fixture note below). What **was** validated live on
Azure (2026-06-18) is the **wiring mechanism** this skill depends on, by
pointing the *same* `MCPStreamableHTTPTool` + `_webiq_result_parser` code at a
public no-auth streamable-HTTP MCP grounding server (Microsoft Learn MCP) as a
stand-in, plus a real Azure model call:

1. **Runtime tool discovery** — `tools/list` over the JSON-RPC handshake
   returned the grounding tools at runtime (never hardcoded), exactly as the
   Native MCP path claims.
2. **Envelope unwrap** — the committed `_webiq_result_parser` (imported from
   the reference file, not copied) unwrapped a genuine MCP `CallToolResult`
   into clean, citation-bearing text.
3. **End-to-end on Azure** — a real Azure OpenAI deployment (`gpt-5.4-mini`,
   AAD / `disableLocalAuth`) ran a tool-calling loop, invoked the grounding
   tool, and produced a grounded answer citing live sources.

Reproduce with [`references/validate_mcp_wiring.py`](references/validate_mcp_wiring.py)
(`SMOKE_RESULT=PASS`). This validates the MCP wiring + citation-unwrap +
Azure model tool-calling — **not** Web IQ's gated specifics, which still
require the live fixture below.

**API-key auth path (structural).** Current MAF `MCPStreamableHTTPTool`
exposes no `headers=` parameter (it is accepted but silently ignored), so the
API-key builder attaches the static header to an `httpx.AsyncClient` passed
via `http_client=` — the same bootstrap-safe mechanism as the Entra path.
Verified live (no-auth stand-in) that the header is set on the underlying
client and that `tools/list` discovery completes through it. The auth *value*
itself is still unverified against a gated Web IQ endpoint (see the dormant
fixture below).

## Reference files

Single source of truth — copy from these, do not re-paste their bodies
inline (validator-enforced, AGENTS.md § 7).

| File | Documents § | Purpose |
|------|-------------|---------|
| [`references/python/webiq_mcp_grounding.py`](references/python/webiq_mcp_grounding.py) | Native MCP path | `MCPStreamableHTTPTool` wiring (API-key static-header + Entra `httpx.Auth` bootstrap variants) and the `_webiq_result_parser` citation extractor |
| [`references/python/webiq_rest_grounding.py`](references/python/webiq_rest_grounding.py) | REST fallback path | Env-driven `httpx` REST grounding call wrapped as an in-process `@tool`, with confirm-the-schema markers |
| [`references/agent.yaml.sample`](references/agent.yaml.sample) | Native MCP path | Declarative Foundry connection + env plumbing for the Web IQ MCP tool (placeholders only) |
| [`references/upstream-pin.md`](references/upstream-pin.md) | (freshness) | Machine-readable freshness contract — `docs_only`, `issue_only`, watches the Web IQ doc URLs |
| [`references/validate_mcp_wiring.py`](references/validate_mcp_wiring.py) | Validation evidence | Live Azure harness — proves the MCP wiring mechanism (`tools/list` discovery + `_webiq_result_parser` envelope unwrap + Azure model tool-calling) against a public MCP grounding stand-in; **not** a Web IQ contract test |

> **Live testing is pending a CI secret.** Web IQ requires a real key the
> CI environment does not yet hold, so the live Copilot-CLI fixture for
> this skill is authored but **dormant** (see
> [`test-fixture/ACTIVATION.md`](test-fixture/ACTIVATION.md)). Per
> AGENTS.md § 2.9 this skill is **not** yet proven on a live Web IQ
> endpoint; activation steps (provision `WEBIQ_API_KEY`, confirm the
> gated contract, enroll in `skill-deps.yml`) are documented there.
