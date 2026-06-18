---
name: foundry-agt
description: >
  Wrap the Microsoft Agent Governance Toolkit (AGT) around Foundry hosted
  agents, MCP servers, and Citadel spokes. Adds deterministic policy
  enforcement, capability allow/deny, hash-chained audit, and OWASP ASI
  2026 coverage via in-process MAF middleware (8-12 µs/eval verified on
  Windows + Py 3.13 + AGT 3.7.0) or ACA sidecar. Ships 3 starter policies
  (default / HITL gate / PII deny), working create_governance_middleware
  snippet, ACA sidecar Bicep, and field-tested Known Issues (rogue detection
  setup). USE FOR: agent governance, AGT, agent-governance-toolkit,
  policy enforcement, capability guard, audit trail, OWASP ASI 2026, MAF
  middleware, MCP scanner, PromptDefense, Citadel adapter, agt verify, agt
  doctor, agt red-team, acs policy, guardrail decision, agt vs
  guardrailtool. DO NOT USE FOR: Foundry agent deployment (use
  foundry-hosted-agents), Citadel hub setup (use citadel-spoke-onboarding),
  App Insights wiring (use foundry-observability), eval scoring (use
  foundry-evals).
metadata:
  version: "1.3.0"
---

# foundry-agt — Microsoft Agent Governance Toolkit for GBB Foundry workloads

> **Status banner:** This skill wraps a **Public Preview, MIT** upstream
> (AGT) plus the **agent-framework** runtime. Concrete pinned versions and
> SHA live in [`references/upstream-pin.md`](references/upstream-pin.md)
> (single source of truth, refreshed by the automated freshness lifecycle —
> AGENTS.md § 9). Smoke-tested on Windows + Python 3.13.13. Latency observed:
> **~8 µs/eval ALLOW, ~12 µs/eval DENY** — order of magnitude under upstream's
> "<100 µs" claim. Public Preview = breaking changes possible; the SKILL.md
> `metadata.version` only changes when **this skill's prose** changes (or for
> PATCH refresh bumps), NOT when AGT bumps. Re-run the pin file's checklist
> whenever you re-pin.

---

## Why this matters (the 30-second version)

Most agents today are governed by **prompt-based safety** — instructions
in the system message that say "please don't do X". In red-team testing
this leaks at a **26.67 %** policy-violation rate ([upstream
benchmarks](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/BENCHMARKS.md)).
AGT moves the check **out** of the LLM and into a deterministic policy
engine that runs **before** the action executes — measured at **0.00 %**
violation under the same red team:

```
                          ┌──────────────────────┐
   Agent decides          │   AGT Policy Check   │   Allow → tool runs
   to call a tool ──────▶ │   (YAML / Rego /     │ ──────▶ Audit Log
                          │    Cedar evaluator)  │
                          └──────────────────────┘   Deny → tool blocked,
                              ~8–12 µs/eval                 reason logged,
                          (deterministic, not LLM)          HITL queue (opt)
```

What this buys you, concretely, in a Foundry hosted agent:

| Without AGT (prompt-based safety only) | With AGT (Path A in-process middleware) |
|---|---|
| Agent can be jailbroken into calling `delete_account` | `delete_account` is on the deny-list — physically can't fire |
| PII can leak into tool calls or model responses | Regex / classifier policy blocks the response before send |
| No tamper-evident record of "what the agent did" | Hash-chained `AuditLog`, exportable as CloudEvents to App Insights |
| "We covered OWASP ASI 2026" is a claim, not evidence | `agt verify --evidence ... --strict` is a CI-gateable proof |
| HITL gating is bespoke per agent, hard to audit | YAML-declared HITL policy, same shape across every agent in the catalog |

This is **defence-in-depth alongside** Azure AI Content Safety / APIM
gateway policies / Citadel product policies — not a replacement for any
of them. See "What AGT isn't (use these instead)" below for the
layer-by-layer mapping.

---

## What AGT does

The **Microsoft Agent Governance Toolkit** is a Microsoft-owned, MIT-licensed,
OpenSSF-Best-Practices-badged toolkit. It currently covers **10/10 OWASP
Agentic Security Initiative (ASI) 2026** controls, with **13 000+ tests**
in upstream CI, verifiable locally via `agt verify`.

The capability surface — every line of which is exercisable via the
`agt …` CLI or one of the language SDKs:

| Capability | What it does | Status here |
|---|---|---|
| **Policy Engine** | YAML / OPA-Rego / Cedar policies evaluated per-action; sub-millisecond, deterministic | ✅ tested (Path A) |
| **Capability Guard** | Explicit allow/deny lists for tool calls (`web_search` ✅, `delete_file` ❌) | ✅ tested |
| **Audit Trail** | Hash-chained tamper-evident log; OTel CloudEvents export; `verify_integrity()` API | ✅ tested |
| **MAF Middleware** | 4 stackable middleware classes auto-assembled by `create_governance_middleware()` | ✅ tested |
| **Zero-Trust Identity** | Ed25519 + quantum-safe ML-DSA-65 credentials, trust scoring 0–1000, SPIFFE/SVID | 📖 upstream |
| **Execution Sandboxing** | 4-tier privilege rings, saga orchestration, kill switch (for shell / code-interp tools) | 📖 upstream |
| **MCP Security Scanner** | Detects tool poisoning, typosquatting, hidden instructions in MCP tool defs | 📖 upstream |
| **PromptDefense Evaluator** | 12-vector adversarial test suite (injection, jailbreak, goal-hijack, …) | 📖 upstream |
| **Agent SRE** | SLOs, error budgets, replay debugging, chaos engineering, circuit breakers | 📖 upstream |
| **Contributor Reputation** | GitHub Action that screens PR/issue authors for credential laundering / spray patterns | 📖 upstream |
| **Shadow AI Discovery** | Scans an org for unregistered agents using your services | 📖 upstream |
| **OWASP self-attestation** | `agt verify --evidence ... --strict` — CI-gateable compliance proof | ✅ tested (10/10) |

**Polyglot reality.** Although this skill targets Foundry hosted agents
(Python / MAF), AGT itself ships SDKs for **Python, TypeScript, .NET,
Rust, and Go** with adapters for **20+ frameworks** (AWS Bedrock,
Google ADK, Azure AI, LangChain, CrewAI, AutoGen, OpenAI Agents…). If
you find yourself governing a non-Foundry GBB workload (a TypeScript
agent for a customer's React UI; a .NET MCP server; a Go data-plane
worker), reach for the same toolkit — only the wiring changes, the
policy YAML and the `agt verify` evidence shape don't.

---

## What AGT isn't (use these instead)

AGT is narrow on purpose. The right column is what to reach for when
you've mistaken the problem for an AGT one:

| Need | Reach for | Why |
|---|---|---|
| Prompt / completion content moderation (toxicity, self-harm, jailbreak detection at the **token** level) | [**Azure AI Content Safety**](https://learn.microsoft.com/azure/ai-services/content-safety/) | AGT governs **actions**, not LLM I/O. Pair the two — Content Safety on the message bus, AGT on the tool/action bus. |
| HTTP-edge gateway routing, auth, rate-limit, product policy | [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md) (APIM-based) | APIM gates the **edge**; AGT gates **inside** the agent's tool loop. Compose, don't replace. |
| Network isolation (private endpoints, VNet, capability host) | [`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md) | Different layer entirely — network plane, not policy plane. |
| Eval scoring (task adherence, intent resolution, custom judges) | [`foundry-evals`](../foundry-evals/SKILL.md) | AGT's PromptDefense covers **adversarial** regression; `foundry-evals` covers **quality** regression. Run both. |
| Telemetry plumbing (App Insights, OTel exporters) | [`foundry-observability`](../foundry-observability/SKILL.md) | AGT **emits** CloudEvents; the observability skill **owns** the pipe they flow through. |
| Authoring or deploying the Foundry agent itself | [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md), [`threadlight-deploy`](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-deploy/SKILL.md) | AGT plugs **into** the agent runtime. It does not provision, deploy, or version your agent. |
| Vector store / RAG / retrieval | [`foundry-iq`](../foundry-iq/SKILL.md) | AGT has no embeddings story — that's not its layer. |

---

## ACS as policy language — relationship to AGT

The "What AGT isn't" table above pairs Azure AI Content Safety (ACS)
with AGT as **message-bus vs action-bus**. The //build 2026 generation
of ACS expanded that picture: in addition to the classic categorical
filters (toxicity, self-harm, jailbreak), ACS now exposes a richer
**policy surface** — custom categories, prompt-shield rules, declarative
blocklists, structured policy artefacts. That puts ACS visibly closer
to AGT in shape (both look like "declarative policy → runtime enforcement
of deny / allow / escalate"), and teams sometimes pattern-match one as a
replacement for the other.

They are not interchangeable. They govern non-overlapping surfaces:

| Concern | **ACS** (Content Safety) | **AGT** (this skill) |
|---|---|---|
| Gates | Tokens — model input + model output | Actions — tool calls + capabilities |
| Runtime | Managed service call per turn (~50–200 ms) | In-process middleware (8–12 µs/eval) or ACA sidecar |
| Policy shape | Categories, blocklists, shield rules, custom classifiers — **content shape** | YAML allow/deny on `capability_id`, parameters, principal, context — **action shape** |
| Deny shape | Block or redact a message | Drop, sanitize, escalate (HITL), or audit-only an action |
| Audit | ACS service logs | Hash-chained `AuditLog` + CloudEvents export |

> **TL;DR.** ACS is your **content policy** — what the model is allowed
> to *say*. AGT is your **action policy** — what the agent is allowed
> to *do*. They share vocabulary (declarative YAML, deny/allow primitives,
> audit trails) precisely *because* they're orthogonal layers reusing
> the same mental model. Any workload that has BOTH chat content AND
> tool side effects needs BOTH — never pick one as a stand-in for the
> other.

---

## When NOT to use AGT at all

Most Foundry workloads benefit from at least Path A. But there are
situations where reaching for AGT is overkill or actively wrong:

- **Pure eval / offline batch runs.** No runtime to govern — tools never
  fire. Use [`foundry-evals`](../foundry-evals/SKILL.md) instead. AGT's
  policies will run, but you're paying setup cost for no enforcement value.
- **Single-tool, read-only agents** (e.g., a chat agent that only calls
  `web_search`). The destructive-action surface is empty. A short
  prompt-level instruction + Content Safety is usually enough; the YAML
  policy ceremony isn't worth it until you add a second, write-capable tool.
- **Hard-real-time constraints.** AGT adds 8–12 µs/eval — irrelevant for
  any tool call that hits a network. But on an inner loop running 100 k+
  evals/sec, you may want to bypass AGT for trusted internal calls and
  re-engage it at the agent boundary.
- **You need a GA, SLA-backed governance product, today.** AGT is
  **Public Preview**. Microsoft-signed, MIT, production-quality releases
  — but breaking changes are still possible before GA. For
  contractually-bound governance use APIM + Content Safety (both GA) and
  layer AGT in once your workload graduates from pilot.
- **You only need LLM input / output filtering** (toxicity, prompt
  injection at the message level). That is **Content Safety's** job.
  AGT's PromptDefense Evaluator is a regression test harness, not a
  runtime input filter.

If two or more of these apply, skip this skill and revisit when you
add tools or graduate from pilot.

---

## Stakeholder TL;DR

| You are… | You care about… | Read this first |
|---|---|---|
| **Engineer** wiring a Foundry hosted agent | "Show me the working snippet" | [`references/maf-middleware-snippet.py`](references/maf-middleware-snippet.py) — 90-line factory you drop into your agent module |
| **Solution architect** sizing a customer pilot | "Where does this sit; what does it own; how does it compose with APIM/VNet/Content Safety?" | "Why this matters" + "What AGT isn't" tables above; `Capability ↔ GBB scenario map` below |
| **Compliance / SME** doing a risk review | "What does it certify, and is the evidence machine-checkable?" | `agt verify --evidence ... --strict` (CI-gateable) + the [OWASP-COMPLIANCE.md](https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/compliance/owasp-agentic-top10-architecture.md) coverage matrix; pair with this skill's "CI gating" section |
| **Seller** building a demo | "Give me one slide and one demo step" | "Why this matters" 26.67 % vs 0.00 % stat (one slide); `python examples/quickstart/govern_in_60_seconds.py` (one demo step — 5 actions, 3 deny / 2 allow, 0.002 ms avg); follow with `agt verify` showing 10/10 OWASP ASI 2026 PASSED |
| **Pilot lead** on a threadlight engagement | "Where in the pipeline does this hook?" | Path A wires into [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) (deploy time, via [`threadlight-deploy`](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-deploy/SKILL.md)); `agt verify --strict` becomes a [`threadlight-safe-check`](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-safe-check/SKILL.md) gate before the demo |

---

## Upstream sources of truth

(All also referenced from `references/upstream-pin.md`.)

- Repo: <https://github.com/microsoft/agent-governance-toolkit>
- Docs site: <https://microsoft.github.io/agent-governance-toolkit>
- Quickstart: <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md>
- MAF adapter source: <https://github.com/microsoft/agent-governance-toolkit/tree/main/agent-governance-python/agent-os/src/agent_os/integrations>
- OWASP coverage: <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/compliance/owasp-agentic-top10-architecture.md>
- Benchmarks (the 26.67 % vs 0.00 % numbers): <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/BENCHMARKS.md>

This skill is a **thin wrapper** — it adds the GBB-specific scenario map,
working integration recipes, and field-tested Known Issues. It does **NOT**
re-document upstream. Always link.

---

## When to reach for this skill

| You're shipping… | Reach for… |
|---|---|
| A Foundry hosted agent (`foundry-hosted-agents`, `threadlight-deploy`) | **Path A** (in-process MAF middleware) — primary recipe |
| A non-MAF agent on ACA (custom framework, shell-out to vLLM, …) | **Path B** (ACA sidecar) — defence-in-depth |
| A Citadel spoke (`citadel-spoke-onboarding`) | **Path C** (Citadel adapter) — native plug |
| A custom MCP server (`foundry-mcp-aca`, `foundry-toolbox`) | **MCP scanner** — scan tool definitions for poisoning + hidden instructions |
| Pre-deploy gating in CI (`threadlight-safe-check`) | **`agt verify --evidence ... --strict`** in the safe-check stage |
| Eval coverage augmentation (`foundry-evals`) | **PromptDefense Evaluator** — 12-vector adversarial regression |
| Multi-agent peer-to-peer (rare in Foundry today) | **Zero-Trust Identity** (Ed25519 / ML-DSA-65) |
| Code-interpreter or shell-tool agents | **Execution Sandboxing** (4-tier rings + kill switch) |

---

## Capability ↔ GBB scenario map

| AGT capability | Slots into | Verification |
|----------------|------------|--------------|
| Policy Engine (YAML / Rego / Cedar) | every Foundry agent | ✅ tested |
| MAF Middleware (4 layers) | `foundry-hosted-agents`, `threadlight-deploy` | ✅ tested |
| ACA sidecar | `azd-patterns`, non-MAF agents | 📖 documented upstream |
| Citadel adapter | `citadel-spoke-onboarding` | 📖 documented upstream |
| MCP Security Scanner | `foundry-mcp-aca`, `foundry-toolbox` | 📖 documented upstream |
| PromptDefense Evaluator | `foundry-evals` | 📖 documented upstream |
| Zero-Trust Identity | multi-agent threadlight | 📖 documented upstream |
| Execution Sandboxing | code-interpreter / shell tools | 📖 documented upstream |
| Agent SRE (SLO / replay / chaos) | `foundry-observability` | 📖 documented upstream |
| Contributor Reputation (GH Action) | every catalog repo | 📖 documented upstream |
| `agt verify --evidence` (CI gate) | `threadlight-safe-check` | ✅ tested (10/10 OWASP ASI 2026) |
| Shadow AI Discovery | cross-cutting (find unregistered agents) | 📖 documented upstream |

**Legend:** ✅ verified by GBB live smoke test (CI: Linux + Python 3.12 + AGT 3.7.0;
original: Windows + Python 3.13 + AGT 3.6.0); 📖 documented by upstream, not yet
GBB-tested. Bump entries to ✅ as you validate.

---

## Quickstart (5 minutes, Path A)

> **Windows users — read this first.** AGT's CLI emits emoji through Rich.
> On a default PowerShell host (cp1252) every `agt` command crashes with
> `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001fa7a'`.
> **Mandatory** before the first `agt` invocation in every shell:
>
> ```powershell
> $env:PYTHONUTF8 = "1"
> [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
> ```
>
> Or persist it once: `[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")`.
> Bake `PYTHONUTF8=1` into every CI runner that calls `agt verify`.
> Full details: `references/upstream-pin.md` Known Issue #1.

```powershell
# 1. Throwaway venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 2. Install AGT [full] + MAF
pip install agent-governance-toolkit[full] agent-framework

# 3. Smoke-check
agt --version
agt doctor                          # expect 6/8 packages present
agt verify                          # expect 10/10 OWASP ASI 2026 PASSED

# 4. Run upstream's 60-second example
git clone --depth 1 https://github.com/microsoft/agent-governance-toolkit
python agent-governance-toolkit/examples/quickstart/govern_in_60_seconds.py
# → 5 actions evaluated, 3 DENY / 2 ALLOW, ~0.002 ms avg
```

If `agt doctor` reports < 6 packages, your `[full]` extra didn't resolve;
re-run `pip install agent-governance-toolkit[full]` with `-v`.

---

## Path A — In-process MAF middleware (RECOMMENDED for Foundry)

This is the path for every Foundry hosted agent. Latency overhead is
**~8–12 µs per eval** on a workstation; deploy without ceremony.

### The four-layer stack

`create_governance_middleware(...)` assembles the right list for you:

1. **AuditTrailMiddleware** — every action → hash-chained audit log
2. **GovernancePolicyMiddleware** — YAML policies → ALLOW / DENY decisions
3. **CapabilityGuardMiddleware** — explicit allow/deny lists for tool calls
4. **RogueDetectionMiddleware** — capability-profile drift detection (off by default — see Known Issue #2)

### Wiring snippet

The **working** snippet — verified end-to-end against AGT 3.7.0 + MAF 1.8.0
— is at [`references/maf-middleware-snippet.py`](references/maf-middleware-snippet.py).
Drop the `build_governed_agent(...)` helper into your hosted-agent module
and pass it the `FoundryChatClient` your azd-deployed project provides.

> **Why a snippet, not just a docs link?** The
> `create_governance_middleware(...)` factory is the shortest working
> Foundry-hosted integration path; the local snippet shows the exact
> pattern to drop into a hosted-agent module.

### Policy YAML

Three starter policies live in [`references/policies/`](references/policies/):

| File | Purpose |
|------|---------|
| `default.yaml` | Conservative default — block destructive SQL / shell exec, cap message length |
| `hitl-gate.yaml` | Route high-impact tool calls (write / send / transfer) to HITL approval queue |
| `pii-deny.yaml` | Regex-based PII guardrail (SSN, credit card, IBAN) on inbound + outbound |

Load all of them at once via:

```python
from agent_os.policies import PolicyEvaluator
ev = PolicyEvaluator()
ev.load_policies("path/to/foundry-agt/references/policies")  # all *.yaml + *.yml
```

You can also load Rego (`load_rego(...)`) or Cedar (`load_cedar(...)`).

### Telemetry export

`AuditLog` ships an **OTel-compatible CloudEvents export** —
`audit_log.export_cloudevents(...)`. Wire it into the App Insights
connection that `foundry-observability` already provisions. Cross-link
the [`foundry-observability`](../foundry-observability/SKILL.md) skill;
do not invent parallel telemetry plumbing.

---

## Path B — ACA sidecar (defence-in-depth, non-MAF agents)

Use when:

- Your agent code is not MAF (different framework, or shell-out to vLLM /
  llama.cpp / a custom model server)
- You want a second, out-of-process enforcement layer behind a MAF
  middleware (defence-in-depth)
- Multiple containerised agents in the same ACA env need a shared policy
  bundle mounted from Azure Files

The skill ships [`references/aca-sidecar-snippet.bicep`](references/aca-sidecar-snippet.bicep)
— a copy-paste ACA module with:

- Your agent container alongside `mcr.microsoft.com/agentmesh/enforcer:3.6.0`
- Policies mounted from an Azure Files share at `/policies`
- Sidecar listens on `localhost:8081`; agent posts every action via HTTP
- Liveness / readiness probes
- App Insights connection threaded through to both containers

**Compose with** `azd-patterns` for the resource group / Log Analytics /
ACA environment, and `foundry-observability` for the App Insights wiring.

**Status: 📖** documented upstream — NOT yet GBB-tested end-to-end.
Validate before customer rollout.

---

## Path C — Citadel adapter

Citadel spokes already centralise routing + auth + product policies via
APIM (see [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md)).
AGT's native Citadel adapter (`agent_os.integrations.citadel`) layers
**runtime policy enforcement** on top of that gateway-level governance —
the two compose cleanly: APIM gates the HTTP edge, AGT gates the
tool-call edge **inside** the spoke's hosted agent.

**Status: 📖** documented upstream. Not yet GBB-tested. Pin a Citadel hub
+ spoke pair to validate when one is on hand. Recipe will land here as
a follow-up PATCH bump.

---

## Decision table: when to use GuardrailTool vs AGT vs ACS

//build 2026 introduced `GuardrailTool` as a new prompt-agent tool
option (see [`foundry-prompt-agents`](../foundry-prompt-agents/SKILL.md)).
It surfaces server-side guardrail evaluation as a tool the model can
invoke mid-loop. That places it conceptually adjacent to both AGT and
ACS, but it is **not a replacement for either**. Use this matrix to
pick the right mechanism — or, more commonly, the right combination:

| Mechanism | Layer it gates | Owner | Reach for it when |
|---|---|---|---|
| **ACS** ([Azure AI Content Safety](https://learn.microsoft.com/azure/ai-services/content-safety/)) | LLM I/O — message content (tokens) | Microsoft GA service | You need declarative content filtering (toxicity, self-harm, jailbreak, custom categories, prompt shield) on user input or model output. No code to own; it's a managed call per turn. |
| **`GuardrailTool`** ([Foundry prompt agents](../foundry-prompt-agents/SKILL.md)) | Per-turn tool surface **inside** a prompt agent's loop | Microsoft Foundry built-in tool | You're building a prompt agent (declarative, no container) and want the model to **call out** to guardrail evaluation mid-conversation as a tool. The agent decides when to invoke; Foundry runs the rule. No middleware to wire, but enforcement is **opt-in** — the agent has to choose to call the tool. |
| **AGT** (this skill) | Tool/action plane — `capability_id`, parameters, principal, context | Microsoft + community, MIT, in-process | You need **deterministic, non-bypassable** policy enforcement on every tool call. You're on MAF / hosted-agent runtime. You need µs-latency evaluation, hash-chained audit, OWASP ASI 2026 coverage, red-team regression harness, and side-effects governance the agent itself cannot route around. |

### Composition — these stack, they do not compete

- **All three** for a regulated hosted-agent workload: ACS on the
  message bus → `GuardrailTool` for in-loop guardrail introspection
  the agent surfaces explicitly → AGT for non-bypassable action gates
  on every tool call. Each layer covers a surface the others
  structurally can't see.
- **ACS + AGT** for hosted-agent runtimes that don't expose tools to
  a prompt-agent loop (e.g., Path B/C sidecar deployments where the
  agent runtime owns the tool dispatch directly).
- **`GuardrailTool` + AGT** for a prompt agent that benefits from both
  opt-in guardrail introspection (model chooses when to ask) AND
  deterministic action gates (AGT decides what fires regardless).
- **AGT alone** for MCP server / ACA sidecar / non-LLM workloads where
  there is no chat content surface to govern in the first place.

> **The decision rule.** If you're governing what the **model says**,
> reach for ACS. If you're governing what the **agent invokes as a
> tool**, reach for `GuardrailTool` (opt-in, prompt-agent-resident) or
> AGT (non-bypassable, middleware-resident) — and prefer AGT whenever
> the policy must hold even when the model tries not to call the
> guardrail. The three compose into the only complete content +
> action governance story for Foundry hosted agents on the //build
> 2026 generation.

---

## CI gating (`threadlight-safe-check` integration)

Add an AGT verification step to the safe-check stage — fails the deploy
if OWASP ASI 2026 coverage drops below 10/10:

```yaml
# .github/workflows/safe-check.yml (excerpt)
- name: AGT compliance gate
  run: |
    pip install agent-governance-toolkit[full]
    agt verify --evidence ./agt-evidence.json --strict
  env:
    PYTHONUTF8: "1"     # MANDATORY on Windows runners (Known Issue #1)
```

Pair with `agt red-team scan ...` for prompt-injection regression — see
upstream `docs/red-team.md`.

Cross-link [`threadlight-safe-check`](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-safe-check/SKILL.md)
in your safe-check stage docs (NOT in this PR; deferred to follow-up
cross-skill bumps).

---

## MCP Security Scanner

Scan MCP tool definitions for tool poisoning, typosquatting, hidden
instructions, and excessive scope **before** they're loaded by a hosted
agent or toolbox:

```bash
agt mcp-scanner scan ./mcp-server-config.json
```

Wire into your MCP server build pipeline alongside
[`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md) and
[`foundry-toolbox`](../foundry-toolbox/SKILL.md). The scanner ships in the
`[full]` extra; no extra install.

**Status: 📖** documented upstream.

---

## PromptDefense Evaluator

Adversarial test suite covering 12 attack vectors (prompt injection, jailbreak,
goal hijack, …). Complements task-adherence / intent-resolution evaluators in
[`foundry-evals`](../foundry-evals/SKILL.md):

```bash
agt eval prompt-defense --agent ./agent.yaml --report ./pd-report.json
```

**Status: 📖** documented upstream.

---

## Verification status table

| Recipe | Status | Last verified |
|--------|--------|---------------|
| `pip install` + `create_governance_middleware` + `load_policies` + `AuditLog` (CI smoke) | ✅ | AGT 3.7.0 + MAF 1.8.0, Linux, Py 3.12 (CI run cited in [v1.2.0 changelog](#gbb-changelog); MAF 1.7.0 baseline historical run: [26745982162](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26745982162/job/78821489441)) |
| `pip install agent-governance-toolkit[full]` | ✅ | AGT 3.6.0, Win11, Py 3.13.13 |
| `agt doctor` | ✅ | same |
| `agt verify` → 10/10 OWASP ASI 2026 | ✅ | same |
| `examples/quickstart/govern_in_60_seconds.py` | ✅ | same |
| Path A — `create_governance_middleware(...)` factory | ✅ | same |
| Path A — `PolicyEvaluator.load_policies(yaml_dir)` | ✅ | same |
| Path A — Latency on workstation | ✅ | 8 µs ALLOW / 12 µs DENY (1k iters) |
| Path B — ACA sidecar Bicep | 📖 | not yet validated end-to-end |
| Path C — Citadel adapter | 📖 | not yet validated; needs hub on hand |
| MCP Security Scanner | 📖 | not yet validated |
| PromptDefense Evaluator | 📖 | not yet validated |
| `agt verify --evidence --strict` in CI | 📖 | not yet wired in safe-check |

---

## Known Issues (GBB field findings)

Full details + fixes: [`references/upstream-pin.md`](references/upstream-pin.md).

1. **`RogueDetectionMiddleware` requires a capability profile** — the
   factory's `enable_rogue_detection=True` will raise unless you also
   supply a `RogueAgentDetector` and a `capability_profile`. Default to
   `False` for first-pass; revisit after baselining.

2. **Verifier version skew is cosmetic** — `agt verify` reports
   `Toolkit: 3.2.2` while the meta-package is `3.7.0`. Verifier carries
   its own compliance schema version; OWASP ASI coverage check still
   passes 10/10.

---

## Using the canonical capability detector

When you need a programmatic read of the host repo's AGT posture
(version pinned, intervention points present, policy YAML discovered,
audit fields in the verifier JSON, CI action SHA-pinned), call the
canonical helper:

```python
from foundry_agt.capability_detector import detect

caps = detect(repo_root=".")
# caps["version_detected"]               → str | None
# caps["detection_confidence"]           → 0.0..1.0
# caps["package_pins"]                   → dict[str, str]
# caps["intervention_points_present"]    → bool
# caps["policy_yaml_path"]               → str | None   (relative POSIX path)
# caps["deny_path_present"]              → bool
# caps["audit_fields_in_verifier_json"]  → list[str]
# caps["ci_action_pinned"]               → bool
# caps["evidence_globs_scanned"]         → list[str]
```

> **MUST:** Copy verbatim from
> [`references/python/capability_detector.py`](references/python/capability_detector.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.
> That file is the canonical reshape of threadlight's
> `production_ready.py::_check_agt_static_v4` (V4_DIST_REGEX,
> V4_POLICY_REGEX, V4_DYNAMIC_REGEX) into a stable 9-key consumer-facing
> snapshot. Threadlight v0.5.1's `kind: sibling-skill` dispatch consumes
> this exact dict shape.

The return dict ALWAYS contains every key listed above. The helper
NEVER raises — on filesystem errors or partial data, it returns the
default shape with `detection_confidence: 0.0`.

---

## See Also

- [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) — primary
  consumer of Path A
- [`threadlight-deploy`](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-deploy/SKILL.md) — deploy stage
  that wires AGT middleware into hosted agents
- [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md) —
  pairs with Path C
- [`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md),
  [`foundry-toolbox`](../foundry-toolbox/SKILL.md) — consumers of MCP
  Security Scanner
- [`foundry-evals`](../foundry-evals/SKILL.md) — pairs with PromptDefense
- [`foundry-observability`](../foundry-observability/SKILL.md) — owner of
  the App Insights connection that `AuditLog.export_cloudevents()` exports to
- [`azd-patterns`](../azd-patterns/SKILL.md) — owner of the Bicep module
  library Path B composes with
- [`threadlight-safe-check`](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-safe-check/SKILL.md) — owner
  of the pre-deploy CI gate

> Cross-skill `See Also` pointers from those skills back to `foundry-agt`
> are deferred to a follow-up PATCH-bump PR (kept out of this PR for
> reviewability).

---

## Upstream references

- Repo (canonical): <https://github.com/microsoft/agent-governance-toolkit>
- Docs site: <https://microsoft.github.io/agent-governance-toolkit>
- Quickstart: <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md>
- Foundry deployment guide:
  <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-foundry-agent-service.md>
- ACA deployment guide:
  <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-container-apps.md>
- MAF adapter source (the four middleware classes):
  <https://github.com/microsoft/agent-governance-toolkit/tree/main/agent-governance-python/agent-os/src/agent_os/integrations>
- Citadel adapter source:
  <https://github.com/microsoft/agent-governance-toolkit/tree/main/agent-governance-python/agent-os/src/agent_os/integrations>
- Quickstart examples:
  <https://github.com/microsoft/agent-governance-toolkit/tree/main/examples/quickstart>
- OWASP compliance evidence:
  <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/compliance/owasp-agentic-top10-architecture.md>
- PyPI: <https://pypi.org/project/agent-governance-toolkit/>
- agent-framework PyPI: <https://pypi.org/project/agent-framework/>
- Benchmarks (the 26.67 % vs 0.00 % red-team numbers):
  <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/BENCHMARKS.md>

---

## GBB Changelog

- **v1.2.0** — MAF 1.8.0 compat refresh. Bumped `agent-framework` pin
  `1.7.0` → `1.8.0` (PyPI release 2026-06-04). AGT pin held at `3.7.0`
  — the AGT 4.0.0 GA package-reorg (5 distributions replacing 45
  sub-packages) is deferred to a dedicated future PR so this PR stays
  reviewable. MAF 1.8.0 ships two `[BREAKING]` markers, neither of which
  affects this skill: (a) the `agent-framework-github-copilot` sub-package
  is not pinned here; (b) the experimental `Skill` abstract-class refactor
  in `agent-framework-core` is not consumed by AGT's middleware stack.
  The four-layer middleware stack (`AuditTrail`, `GovernancePolicy`,
  `CapabilityGuard`, `RogueDetection`) still hooks `FunctionInvocationContext`
  the same way it did at 1.7.0; `create_governance_middleware(...)` factory
  signature and the `Agent(client, instructions, *, name, middleware, tools, ...)`
  ctor shape are unchanged. CI smoke run citation: TBD — added after the
  initial green.
- **v1.0.6** — CI E2E smoke landed
  ([run 26745982162](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26745982162/job/78821489441),
  3m6s wall-clock, Linux + Python 3.12 + AGT 3.7.0 + MAF 1.7.0). Refreshed
  prose version strings across SKILL.md, `references/upstream-pin.md`, and
  `references/maf-middleware-snippet.py` to match the actual pinned wheels
  (`agent-governance-toolkit~=3.7.0` + `agent-framework~=1.7.0`). Fixed
  `references/policies/default.yaml` — the `cap-message-length` rule used a
  bogus `length_gt` operator (not in the AGT `PolicyOperator` enum
  `[eq, ne, gt, lt, gte, lte, in, not_in, matches, contains]`); the policy
  silently failed to load. Replaced with `matches: "[\s\S]{16001,}"` which
  the CI smoke now confirms is enforced end-to-end. No API surface change;
  callers of `create_governance_middleware(...)` and `PolicyEvaluator.load_policies(...)`
  are unaffected. Note: L336 ACA sidecar image (`enforcer:3.6.0`) intentionally
  left unchanged — no evidence a 3.7.0 sidecar image exists in MCR; the in-process
  path is what this CI smoke validates.
- **v1.0.1** — Clarification pass (no API or policy changes). Added
  "Why this matters" section with the 26.67 % vs 0.00 % red-team stat
  and an ASCII flow diagram of where AGT sits. Refactored the
  IS/ISN'T table into two cleaner sections ("What AGT does" capability
  matrix; "What AGT isn't" → "use this instead" mapping). Added an
  explicit "When NOT to use AGT at all" section. Added "Stakeholder
  TL;DR" for engineer / architect / compliance / seller / pilot-lead
  fast skim. Surfaced the polyglot reality (Python/TS/.NET/Rust/Go,
  20+ frameworks). Added benchmarks URL to the upstream-references list.
- **v1.0.0** — Initial wrapper. Pinned to AGT 3.6.0 + MAF 1.3.0. Live-smoke
  Path A on Windows + Python 3.13.13. Three starter policies, working
  middleware factory snippet, ACA sidecar Bicep fragment, Known Issues
  (5 entries) captured from field testing.
