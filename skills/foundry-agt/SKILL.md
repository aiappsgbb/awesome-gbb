---
name: foundry-agt
description: >
  AGT 4.1 in-process message-policy and tool-governance middleware for
  Microsoft Agent Framework (MAF) agents on Foundry. Loads YAML policies
  (default / PII-deny, inbound message text only) into a PolicyEvaluator;
  AuditTrailMiddleware and GovernancePolicyMiddleware are always in the
  canonical policy path. CapabilityGuardMiddleware — the deterministic
  per-tool-call allow/deny gate — is added only when allowed_tools or
  denied_tools is configured. Exposes a tamper-evident AuditLog with
  integrity verification and CloudEvents export. `agt verify` is a toolkit
  self-assessment, not a certification. USE FOR: agent action/tool
  governance, AGT, agent-governance-toolkit, MAF middleware, capability
  allow/deny, policy enforcement, audit trail, deterministic tool gating,
  agt verify, agt doctor. DO NOT USE FOR: Foundry agent deployment (use
  foundry-hosted-agents), message/content moderation (use Azure AI Content
  Safety), eval scoring (use foundry-evals), telemetry pipeline wiring
  (use foundry-observability).
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
| Action / tool-call plane — may the agent invoke this named tool at all? | **This skill (AGT)** | Deterministic, in-process, pre-execution by tool name. Argument validation remains the caller's / tool-body's responsibility. |
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
- You need tamper-evident evidence, independent of what the model's
  own transcript claims: `AuditTrailMiddleware` always writes a
  hash-chained agent-invocation start/complete entry into `AuditLog`
  for every run. `CapabilityGuardMiddleware`, when explicitly configured
  with `allowed_tools` / `denied_tools`, additionally writes a
  tool-invoked or tool-blocked entry to the same `AuditLog` for every
  gated tool call — that per-tool coverage is not automatic.

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

`create_governance_middleware(...)` assembles two always-on middleware
in this skill's canonical snippet and proved path, which passes
`enable_rogue_detection=False`; a third middleware is conditional on
caller-configured capability gating.
`contract_probe.py::build_factory_stack` proves middleware-type
*membership* for a configured stack — it does not assert ordering;
`contract_probe.py::check_snippet_import` is the probe that proves the
factory's `AuditTrail -> GovernancePolicy -> CapabilityGuard` order is
preserved end-to-end through `build_governed_agent(...)`, alongside
`allowed_tools=None` / `denied_tools=None` default (no-guard) semantics
passthrough.

1. **`AuditTrailMiddleware`** *(always)* — hash-chains one
   agent-invocation start entry and one agent-invocation complete
   entry into `AuditLog` per run; it hooks the agent invocation, not
   individual tool calls.
2. **`GovernancePolicyMiddleware`** *(always)* — evaluates the loaded
   YAML policy set against a flat `{agent, message, timestamp, stream,
   message_count}` context built from the *message text*; ALLOW / DENY
   per message. It has no visibility into `tool_name` or `tool_args` —
   see "Policy YAML" below for what that means for policy authoring.
3. **`CapabilityGuardMiddleware`** *(conditional)* — the factory adds
   this middleware to the stack only when `allowed_tools` or
   `denied_tools` is not `None`; explicit allow/deny lists on
   `tool_name` are, in that configuration, the deterministic
   tool-action gate (not YAML policy). When configured, it also
   hash-chains a tool-invoked or tool-blocked entry into the same
   `AuditLog` for every gated tool call — in addition to the allow/deny
   gate itself.

Both `allowed_tools=None` and `denied_tools=None` (the snippet's
default) mean **no capability guard at all**: with no
`CapabilityGuardMiddleware` in the stack, every tool call is allowed
(nothing is left to deny it), and none of them get a tool-invoked or
tool-blocked entry in `AuditLog` — tools still execute normally
through the runtime's own dispatch, they are simply not guard-audited
at the tool level. `AuditTrailMiddleware`'s agent-invocation
start/complete entries still fire regardless, since that middleware is
always present. Passing `allowed_tools=[]` is not the same as `None`:
an empty list is not `None`, so it turns the guard on, and an empty
allowlist matches no tool — deny-all. The canonical snippet,
[`references/maf-middleware-snippet.py`](references/maf-middleware-snippet.py),
passes `allowed_tools` / `denied_tools` straight through to the
factory — never coerced with `or []` — so it preserves whichever of
these the caller actually asked for.

AGT 4.1's factory default for `enable_rogue_detection` is `True`;
omitting the flag adds `RogueDetectionMiddleware` as a third
unconditional member (fourth when a tool list is also configured —
see the upstream pin's four-case table in
[`references/upstream-pin.md`](references/upstream-pin.md)).
The canonical snippet intentionally overrides this to `False` until
the caller has established a capability profile to compare against.

### Policy YAML

Two starter policies ship in
[`references/policies/`](references/policies/):

| File | Purpose |
|---|---|
| `default.yaml` | Conservative default — blocks destructive SQL / shell-exec patterns, caps message length |
| `pii-deny.yaml` | Regex PII guardrail (SSN, credit card, IBAN) on **inbound message text only** |

`pii-deny.yaml`'s `block-us-ssn` rule accepts hyphen, space, dot, or no
separator at all between digit groups. That last, unseparated form is
indistinguishable from any other standalone 9-digit number
(order/invoice IDs). An ordinary hyphenated ZIP+4 also matches because
the first separator is optional and the second accepts its hyphen, so it
can false-positive/false-deny on either. This is not cosmetic: a
deny terminates the message path (`GovernancePolicyMiddleware.process`
raises `MiddlewareTermination` before the agent ever sees it), and
`load_policies(...)` loads every file in the default policy directory
— including pii-deny.yaml — so this rule is active by default the
moment you load the starter policies. Tune or drop `block-us-ssn`
before production and pair it with a real classifier / Azure AI
Content Safety rather than relying on this regex alone.

`GovernancePolicyMiddleware`'s evaluation context is the flat
`{agent, message, timestamp, stream, message_count}` dict described
above — it is built from the inbound *message text*, never from
`tool_name` or `tool_args`. A policy rule with a `field: tool_name` or
`field: tool_args.<key>` condition, or a `field: response` condition
targeting the assistant's outgoing reply, can never match against the
real middleware in this release; such rules are permanently inert
regardless of how they read in YAML. Deterministic tool-action gating
(which tool may or may not run) is `CapabilityGuardMiddleware`'s
explicit `allowed_tools` / `denied_tools` lists — not a YAML policy
field. See "Deterministic capability allow/deny hook" below.

Load every policy file in the directory at once:

```python
from agent_os.policies import PolicyEvaluator

evaluator = PolicyEvaluator()
evaluator.load_policies("skills/foundry-agt/references/policies")
```

`load_policies(...)` is the only loader this skill exercises and pins —
[`references/python/contract_probe.py`](references/python/contract_probe.py)
proves this exact call against the two starter policies above.

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
| Public symbol imports (`Agent`, `FoundryChatClient`, the three middleware classes, `AuditLog`, `PolicyEvaluator`, `AgentContext`, …) | ✅ locally proved | `contract_probe.py::check_imports` |
| Factory / constructor signatures this prose depends on | ✅ locally proved | `contract_probe.py::check_signatures` |
| Stub `FoundryChatClient` construction + `Agent.run` response shape | ✅ locally proved | `contract_probe.py::check_stub_*` |
| Isolated `PolicyEvaluator.evaluate(...)` coverage (default / PII-deny inbound, all four SSN separator forms) — evaluator-level only, not the middleware's real dispatch path | ✅ locally proved | `contract_probe.py::check_policies` |
| Real `GovernancePolicyMiddleware.process(...)` message path: benign text calls `call_next()` once; a destructive-SQL message and an inbound-SSN message each raise `MiddlewareTermination` and call `call_next()` zero times | ✅ locally proved | `contract_probe.py::check_policy_middleware` |
| `AuditLog.verify_integrity()` + `export_cloudevents()` | ✅ locally proved | `contract_probe.py::check_audit_log` |
| Middleware factory stack assembly (AuditTrail + GovernancePolicy + CapabilityGuard membership once capability gating is configured; sequence not claimed here) | ✅ locally proved | `contract_probe.py::build_factory_stack` |
| `CapabilityGuardMiddleware.process` allow/deny hook | ✅ locally proved | `contract_probe.py::check_capability_hook` |
| `build_governed_agent(...)` snippet import + wiring: with **both** `allowed_tools` and `denied_tools` omitted (the function's true default), the stack is exactly `AuditTrailMiddleware` -> `GovernancePolicyMiddleware`, with no `CapabilityGuardMiddleware` at all; once capability gating is configured, `allowed_tools=None` is preserved as no-allowlist (not coerced to deny-all) and the factory's `AuditTrail -> GovernancePolicy -> CapabilityGuard` order holds | ✅ locally proved | `contract_probe.py::check_snippet_import` |
| Live Foundry inference through a real deployed model (T3) | 🔒 required before merge — exact-head CI gate, not a standing proof | `references/python/live_t3_probe.py` run against a real Foundry project in the CI `copilot-cli-matrix` fixture; merge acceptance requires a successful run at the exact-head commit whose downloaded artifact at `/tmp/foundry-agt-smoke-evidence` a reviewer inspects line-for-line before approving — see [`test-fixture/consumer_prompt.md`](test-fixture/consumer_prompt.md) |

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
  --strict`). **Final-review remediation (this release):** the real
  `GovernancePolicyMiddleware` evaluation context is a flat `{agent,
  message, timestamp, stream, message_count}` dict built from message
  text only, so `hitl-gate.yaml`'s `tool_name` / `tool_args.amount`
  rules and `pii-deny.yaml`'s outbound `field: response` rule could
  never match in the real runtime — `hitl-gate.yaml` is deleted and
  `pii-deny.yaml` is now documented as inbound-message-text-only.
  `pii-deny.yaml`'s `block-us-ssn` rule also broadened from a
  hyphen-only match to accept hyphen, space, dot, or no separator at
  all between digit groups; this release adds an explicit disclosure,
  in both the policy file and this skill's "Policy YAML" section, that
  the unseparated form false-positives/false-denies on any standalone
  9-digit number (order/invoice IDs) and on ZIP+4 codes, and that the
  rule should be tuned or dropped before production and paired with a
  real classifier / Azure AI Content Safety.
  `maf-middleware-snippet.py`'s `allowed_tools` / `denied_tools`
  handling no longer coerces `None` (no allowlist) to `[]` (deny-all)
  via `or []`, and the factory's `GovernancePolicyMiddleware` is spliced
  back in at its original stack index instead of `insert(0, ...)`, so
  `AuditTrailMiddleware` stays outermost. `contract_probe.py` now drives
  the real `GovernancePolicyMiddleware.process(...)` with a real
  `AgentContext` instead of asserting against synthetic evaluator
  dicts. Live Foundry inference against a real deployed model (T3) is
  part of this release: `references/python/live_t3_probe.py` runs in
  the CI `copilot-cli-matrix` fixture, and merge acceptance requires a
  successful run at the exact-head commit whose downloaded artifact a
  reviewer inspects — a required gate on every PR, not a standing
  proof already banked for whatever commit is HEAD right now.
  `contract_probe.py::check_snippet_import` also now constructs
  `build_governed_agent(...)` with both `allowed_tools` and
  `denied_tools` omitted (not just `allowed_tools=None`) and asserts
  the resulting stack is exactly `AuditTrailMiddleware` ->
  `GovernancePolicyMiddleware` with no `CapabilityGuardMiddleware` —
  the factory's true no-argument default, previously only exercised
  with `denied_tools` configured.
  **Rogue-detection factory-default correction:** the opening
  "always assembles two middleware when a policy_directory is supplied"
  claim was unqualified — it was only true for the snippet's proved
  path (which passes `enable_rogue_detection=False`). AGT 4.1's
  factory default for `enable_rogue_detection` is `True`; omitting the
  flag adds `RogueDetectionMiddleware` as a third unconditional member.
  The canonical snippet intentionally overrides this to `False` until
  the caller establishes a capability profile (see the upstream pin's
  four-case table).
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
