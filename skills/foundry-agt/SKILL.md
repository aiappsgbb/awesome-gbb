---
name: foundry-agt
description: >
  Wrap Microsoft's Agent Governance Toolkit (AGT) 4.1 around a Foundry
  hosted or custom agent's Microsoft Agent Framework (MAF) runtime:
  in-process middleware that deterministically allows or denies each
  tool call before it executes. Loads YAML policies (default / HITL-gate
  / PII-deny) into a PolicyEvaluator, wires AuditTrailMiddleware,
  GovernancePolicyMiddleware, and CapabilityGuardMiddleware onto the
  agent, and exposes a tamper-evident AuditLog with integrity
  verification and CloudEvents export. `agt verify` is a toolkit
  self-assessment, not a certification. USE FOR: agent action/tool
  governance, AGT, agent-governance-toolkit, MAF middleware, capability
  allow/deny, policy enforcement, audit trail, deterministic tool
  gating, agt verify, agt doctor. DO NOT USE FOR: Foundry agent
  deployment (use foundry-hosted-agents), message/content moderation
  (use Azure AI Content Safety), eval scoring (use foundry-evals),
  telemetry pipeline wiring (use foundry-observability).
metadata:
  version: "2.0.0"
---

# foundry-agt — Microsoft Agent Governance Toolkit, in-process (Path A)

> **Status:** AGT 4.1.0 (Public Preview, MIT) + selective Microsoft Agent
> Framework (MAF) packages. Exact pinned versions, the released-source
> SHA, and the executable validation script are the single source of
> truth in [`references/upstream-pin.md`](references/upstream-pin.md) —
> re-run its `validation.script` before trusting any re-pin (AGENTS.md
> § 9).
>
> AGT 4.1 is Public Preview. `agt verify` is toolkit self-assessment,
> not certification, an independent audit, or a guarantee that a
> workload meets every organizational or regulatory control.

---

## Why action governance matters

A system-prompt instruction like "never call `delete_account`" is a
*request to the model*, not an enforcement point — a jailbroken or
mis-routed turn can still emit the tool call. AGT moves that check out
of the model and into **middleware that runs before the tool function
executes**: `CapabilityGuardMiddleware` inspects the real
`FunctionInvocationContext` for every tool invocation and decides
allow/deny deterministically, in-process, before `call_next()` (the
actual tool body) ever runs. A denied call raises
`MiddlewareTermination` and the tool body never executes at all — this
is proven locally by
[`references/python/contract_probe.py`](references/python/contract_probe.py),
not just asserted from upstream documentation.

---

## Scope & ownership

| Concern | Owner | Notes |
|---|---|---|
| Action / tool-call plane — is the agent *allowed* to invoke this tool with these arguments? | **This skill (AGT)** | Deterministic, in-process, pre-execution. |
| Message / token content — is this text safe to send or show? | [Azure AI Content Safety](https://learn.microsoft.com/azure/ai-services/content-safety/) | A different plane entirely; pair with AGT, don't substitute for it. |
| Edge auth, rate limiting, product policy | APIM / gateway — see [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md) | Gates the HTTP edge; AGT gates inside the tool loop. |
| Network isolation (VNet, private endpoints) | [`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md) | Network plane, not policy plane. |
| Quality / task-adherence evaluation | [`foundry-evals`](../foundry-evals/SKILL.md) | AGT governs the safety of actions, not answer quality. |
| Telemetry plumbing (App Insights, OTel exporters) | [`foundry-observability`](../foundry-observability/SKILL.md) | AGT **emits** CloudEvents; this skill owns the pipe they flow through. |

Any workload with both chat content and side-effecting tools needs
Content Safety **and** AGT — never treat one as a stand-in for the
other.

---

## When to use this skill

- A Foundry hosted or custom agent, built on Microsoft Agent Framework,
  that calls one or more **side-effecting** tools (write / send /
  delete / transfer — not just read-only lookups).
- You need a deterministic, pre-execution allow/deny decision that
  holds even when the model tries to route around it.
- You need a tamper-evident record of every tool call the agent made,
  independent of what the model's own transcript claims.

## When NOT to use this skill

- **Pure offline eval / batch scoring.** No runtime tool calls fire —
  use [`foundry-evals`](../foundry-evals/SKILL.md) instead.
- **Content moderation only** (toxicity, self-harm, jailbreak detection
  at the message level). That's
  [Azure AI Content Safety](https://learn.microsoft.com/azure/ai-services/content-safety/)'s
  job, not AGT's.
- **Read-only, single-tool agents** (e.g. a chat agent that only calls
  `web_search`). There's no destructive-action surface to gate yet; the
  policy/middleware ceremony isn't worth it until a second,
  write-capable tool shows up.
- **You need a GA, SLA-backed governance product today.** AGT is
  **Public Preview** — production-quality and Microsoft-signed, but
  breaking changes remain possible before GA.

---

## Upstream sources

- Repo: <https://github.com/microsoft/agent-governance-toolkit>
- Release tag pinned here: <https://github.com/microsoft/agent-governance-toolkit/releases/tag/v4.1.0>
- Docs site: <https://microsoft.github.io/agent-governance-toolkit>
- `agent-governance-toolkit` on PyPI: <https://pypi.org/project/agent-governance-toolkit/>
- `agent-framework-core` on PyPI: <https://pypi.org/project/agent-framework-core/>
- `agent-framework-foundry` on PyPI: <https://pypi.org/project/agent-framework-foundry/>
- `agent-framework-openai` on PyPI: <https://pypi.org/project/agent-framework-openai/>

This skill is a thin wrapper — it does not re-document upstream. Follow
a link rather than trust a paraphrase, and read
[`references/upstream-pin.md`](references/upstream-pin.md) for the
exact, live-re-verified API surface.

---

## Install (selective, bounded)

Pin the specific sub-packages this skill actually imports — not the
broad `agent-framework` meta-package:

```bash
pip install \
  "agent-governance-toolkit[full]~=4.1.0" \
  "agent-framework-core~=1.13.0" \
  "agent-framework-foundry~=1.10.4" \
  "agent-framework-openai~=1.12.0" \
  "azure-identity~=1.25.3"
```

---

## Wiring snippet

> **MUST:** Copy verbatim from
> [`references/maf-middleware-snippet.py`](references/maf-middleware-snippet.py).
> Do NOT redefine `build_governed_agent(...)` inline — the validator
> enforces single-source-of-truth. That file is the canonical MAF
> middleware wiring, re-verified live against AGT 4.1.0 + Agent
> Framework Core 1.13.0.

Drop `build_governed_agent(...)` into your hosted-agent module and pass
it the chat client your project constructs (see "Foundry composition"
below).

### Middleware factory stack

`create_governance_middleware(...)` assembles the following three
middleware (`contract_probe.py` proves membership and types, not
ordering):

1. **`AuditTrailMiddleware`** — every tool call becomes a hash-chained
   entry in `AuditLog`.
2. **`GovernancePolicyMiddleware`** — evaluates the loaded YAML policy
   set; ALLOW / DENY per action.
3. **`CapabilityGuardMiddleware`** — explicit allow/deny lists on
   `tool_name`.

A fourth middleware, `RogueDetectionMiddleware`, exists upstream, but
this skill keeps `enable_rogue_detection=False` by default — it needs a
baselined capability profile this skill has not established, not
because the factory errors without one. Enable it explicitly once your
agent has a behavioral baseline to compare against.

### Policy YAML

Three starter policies ship in
[`references/policies/`](references/policies/):

| File | Purpose |
|---|---|
| `default.yaml` | Conservative default — blocks destructive SQL / shell-exec patterns, caps message length |
| `hitl-gate.yaml` | Routes high-impact tool calls (write / send / transfer) to a `HITL_REQUIRED:*` deny reason your app treats as an approval ticket, not a failure |
| `pii-deny.yaml` | Regex PII guardrail (SSN, credit card, IBAN) on inbound and outbound text |

Load every policy file in the directory at once:

```python
from agent_os.policies import PolicyEvaluator

evaluator = PolicyEvaluator()
evaluator.load_policies("skills/foundry-agt/references/policies")
```

`load_policies(...)` is the only loader this skill exercises and pins —
[`references/python/contract_probe.py`](references/python/contract_probe.py)
proves this exact call against the three starter policies above.

---

## Deterministic capability allow/deny hook

`CapabilityGuardMiddleware.process(context, call_next)` receives the
real `FunctionInvocationContext` for the invoked `FunctionTool`:

- **Allowed** tool → `process` calls `call_next()` exactly once; the
  tool body executes.
- **Denied** tool → `process` raises `MiddlewareTermination` *before*
  `call_next()` runs; the tool body never executes.

This is not prose — it's exercised by
[`references/python/contract_probe.py`](references/python/contract_probe.py)'s
`check_capability_hook`, which asserts the allowed function runs
exactly once and the denied function runs zero times against the real,
installed middleware class.

---

## Audit trail

`AuditLog.log(...)` appends a hash-chained entry for every governed
action, allowed or denied. `audit_log.verify_integrity()` recomputes
the chain and confirms nothing was altered after the fact — this is
**self-assessment evidence for your own audit trail**, not a
third-party certification of anything upstream or downstream.
`audit_log.export_cloudevents()` emits an OTel-compatible CloudEvents
list; wire it into the App Insights pipeline
[`foundry-observability`](../foundry-observability/SKILL.md) already
provisions rather than inventing parallel telemetry plumbing.

---

## Foundry composition

Construct a real `FoundryChatClient` and pass it straight into the
snippet's factory:

```python
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import DefaultAzureCredential

chat_client = FoundryChatClient(
    project_endpoint="https://<project>.services.ai.azure.com/api/projects/<project-name>",
    model="<model-deployment-name>",
    credential=DefaultAzureCredential(),
)

agent = build_governed_agent(
    name="my-governed-agent",
    instructions="...",
    chat_client=chat_client,
    policy_dir="skills/foundry-agt/references/policies",
    allowed_tools=["web_search"],
    denied_tools=["delete_account"],
)
```

The exact `FoundryChatClient` constructor signature and the
`Agent.run(...)` response shape this composes with are exercised live
by
[`references/python/contract_probe.py`](references/python/contract_probe.py)
(`check_stub_foundry_construction`, `check_stub_response_shape`)
against a stub credential — no network call required to validate the
shape.

---

## Local validation

Run the pinned validation flow rather than trusting this prose:

```bash
python3 skills/foundry-agt/references/python/contract_probe.py
```

or run the equivalent `validation.script` in
[`references/upstream-pin.md`](references/upstream-pin.md), which first
pins a throwaway venv to the exact package set above. A clean run ends
in `CONTRACT_PROBE=PASS`, with every intermediate marker
(`STUB_FOUNDRY_CONSTRUCTION=PASS`, `CAPABILITY_HOOK=PASS`, …) printed
along the way.

Two `agt` CLI quirks are **cosmetic** and should only be treated as
informational *after* `contract_probe.py` passes cleanly:

- `agt doctor` undercounts installed packages — it still checks
  pre-4.1.0-split distribution names.
- `agt verify` self-reports a stale internal `Toolkit:` schema version,
  independent of the installed package version.

Full detail: [`references/upstream-pin.md`](references/upstream-pin.md)
KI-002 / KI-003. `agt verify` itself is a **toolkit self-assessment** —
a useful local signal, not an external check.

---

## Using the canonical capability detector

When you need a programmatic read of a repo's AGT posture (version
pinned, intervention points present, policy YAML discovered, audit
fields in a verifier JSON, CI action SHA-pinned), call the canonical
helper:

Copy `references/python/capability_detector.py` verbatim into your
consumer repo and put its containing directory on `PYTHONPATH` (or your
equivalent package path) before importing it — the module ships as a
standalone file, not an installable package:

```python
from capability_detector import detect

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

The return dict ALWAYS contains every key listed above and NEVER
raises — on filesystem errors or partial data it returns the default
shape with `detection_confidence: 0.0`.

---

## Verification status

| Surface | Status | Evidence |
|---|---|---|
| Package install at the exact pinned versions | ✅ locally proved | `contract_probe.py::check_versions` |
| Public symbol imports (`Agent`, `FoundryChatClient`, the three middleware classes, `AuditLog`, `PolicyEvaluator`, …) | ✅ locally proved | `contract_probe.py::check_imports` |
| Factory / constructor signatures this prose depends on | ✅ locally proved | `contract_probe.py::check_signatures` |
| Stub `FoundryChatClient` construction + `Agent.run` response shape | ✅ locally proved | `contract_probe.py::check_stub_*` |
| Policy evaluation (default / HITL-gate / PII-deny, all four SSN separator forms) | ✅ locally proved | `contract_probe.py::check_policies` |
| `AuditLog.verify_integrity()` + `export_cloudevents()` | ✅ locally proved | `contract_probe.py::check_audit_log` |
| Middleware factory stack assembly (3 middleware types) | ✅ locally proved | `contract_probe.py::build_factory_stack` |
| `CapabilityGuardMiddleware.process` allow/deny hook | ✅ locally proved | `contract_probe.py::check_capability_hook` |
| `build_governed_agent(...)` snippet import + wiring | ✅ locally proved | `contract_probe.py::check_snippet_import` |
| Live Foundry inference through a real deployed model | 📖 not yet proved at this pin | pending a live probe run against a real project |

---

## See Also

- [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) —
  primary consumer; deploys the Foundry hosted agent this skill's
  middleware wires into.
- [`foundry-evals`](../foundry-evals/SKILL.md) — quality / task-adherence
  evaluation; complements, does not replace, action governance.
- [`foundry-observability`](../foundry-observability/SKILL.md) — owns
  the App Insights pipe `AuditLog.export_cloudevents()` exports to.
- [`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md) — network
  isolation; a different plane entirely.
- [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md) —
  edge-level auth / rate-limit / product policy via APIM.

---

## GBB Changelog

- **v2.0.0** — Breaking narrowing to a single, fully-local-proved
  contract: **Path A (in-process MAF middleware) only.** Re-pinned to
  AGT's **released `v4.1.0` source tag** (not `main` HEAD), plus
  selective, bounded MAF packages (`agent-framework-core` /
  `-foundry` / `-openai`) instead of the broad `agent-framework`
  meta-package the prior pin used. The `CapabilityGuardMiddleware`
  allow/deny hook is now proven against the real
  `FunctionInvocationContext` / `FunctionTool` classes — allow executes
  the tool exactly once, deny raises `MiddlewareTermination` before the
  tool body runs — rather than asserted from documentation. Removed all
  active guidance for surfaces this skill had not proved locally: the
  ACA sidecar path and its Bicep fragment, the AGT-native Citadel
  adapter, the MCP Security Scanner and PromptDefense Evaluator CLI
  commands, and language that overstated what a Public Preview
  self-assessment tool guarantees (fixed red-team percentages,
  "CI-gateable proof" framing for `agt verify --evidence ...
  --strict`). Live Foundry inference against a real deployed model
  (tracked separately as T3) remains pending until it lands with
  exact-head evidence.
- **v1.2.0** — MAF 1.8.0 compat refresh. Bumped `agent-framework` pin
  `1.7.0` → `1.8.0` (PyPI release 2026-06-04). AGT pin held at `3.7.0`
  — the AGT 4.0.0 GA package-reorg (5 distributions replacing 45
  sub-packages) was deferred to a dedicated future PR so that PR stayed
  reviewable. The four-layer middleware stack (`AuditTrail`,
  `GovernancePolicy`, `CapabilityGuard`, `RogueDetection`) still hooked
  `FunctionInvocationContext` the same way it did at 1.7.0;
  `create_governance_middleware(...)` factory signature and the
  `Agent(client, instructions, *, name, middleware, tools, ...)` ctor
  shape were unchanged.
- **v1.0.6** — CI E2E smoke landed
  ([run 26745982162](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26745982162/job/78821489441),
  Linux + Python 3.12 + AGT 3.7.0 + MAF 1.7.0). Refreshed prose version
  strings across SKILL.md, `references/upstream-pin.md`, and
  `references/maf-middleware-snippet.py` to match the actual pinned
  wheels. Fixed `references/policies/default.yaml` — the
  `cap-message-length` rule used a `length_gt` operator that does not
  exist in the AGT `PolicyOperator` enum, so the policy silently failed
  to load; replaced with a `matches` regex the CI smoke confirmed is
  enforced end-to-end.
- **v1.0.1** — Clarification pass (no API or policy changes). Added a
  "Why this matters" section contrasting prompt-only versus
  deterministic middleware enforcement, and an ASCII flow diagram of
  where AGT sits. Split the capability description into a "what AGT
  does" matrix and a "what AGT isn't — use this instead" mapping. Added
  an explicit "when not to use AGT at all" section and a
  stakeholder-by-role reading guide.
- **v1.0.0** — Initial wrapper. Pinned to AGT 3.6.0 + MAF 1.3.0.
  Live-smoke Path A on Windows + Python 3.13.13. Three starter
  policies, a working middleware factory snippet, an ACA sidecar Bicep
  fragment, and field-tested Known Issues captured from that testing
  pass.
