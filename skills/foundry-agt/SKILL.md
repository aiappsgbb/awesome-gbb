---
name: foundry-agt
description: >
  Wrap the Microsoft Agent Governance Toolkit (AGT) around Foundry hosted
  agents, MCP servers, and Citadel spokes. Adds deterministic policy
  enforcement, capability allow/deny, hash-chained audit, and OWASP ASI
  2026 coverage via in-process MAF middleware (8-12 µs/eval verified on
  Windows + Py 3.13 + AGT 3.6.0) or ACA sidecar. Ships 3 starter policies
  (default / HITL gate / PII deny), working create_governance_middleware
  snippet, ACA sidecar Bicep, and field-tested Known Issues (Windows UTF-8
  CLI trap, stale upstream Foundry-doc kwargs, Agent ctor rename, rogue
  detection setup). USE FOR: agent governance, AGT, agent-governance-toolkit,
  policy enforcement, capability guard, audit trail, OWASP ASI 2026, MAF
  middleware, MCP scanner, PromptDefense, Citadel adapter, agt verify, agt
  doctor, agt red-team. DO NOT USE FOR: Foundry agent deployment (use
  foundry-hosted-agents), Citadel hub setup (use citadel-spoke-onboarding),
  App Insights wiring (use foundry-observability), eval scoring (use
  foundry-evals).
metadata:
  version: "1.0.0"
---

# foundry-agt — Microsoft Agent Governance Toolkit for GBB Foundry workloads

> **Status banner (re-pin every refresh, see `references/upstream-pin.md`):**
> Pinned to **AGT v3.6.0** (Public Preview, MIT) + **agent-framework v1.3.0**.
> Smoke-tested on Windows + Python 3.13.13. Latency observed: **~8 µs/eval ALLOW,
> ~12 µs/eval DENY** — order of magnitude under upstream's "<100 µs" claim.
> Public Preview = breaking changes possible; the SKILL.md
> `metadata.version` only changes when **this skill** changes, NOT when AGT
> bumps. Re-run `references/upstream-pin.md` checklist whenever you re-pin.

---

## What AGT is (and isn't)

The **Microsoft Agent Governance Toolkit** is a Microsoft-owned, MIT-licensed,
OpenSSF-Best-Practices-badged toolkit that adds **deterministic, sub-millisecond
policy enforcement** between an agent's reasoning loop and the actions it
takes. It currently covers **10/10 OWASP Agentic Security Initiative (ASI)
2026** controls — verifiable locally via `agt verify`.

| AGT IS | AGT ISN'T |
|--------|-----------|
| Runtime policy enforcement (allow / deny / HITL) | A model / chat client |
| Cryptographic identity for agents (Ed25519 / ML-DSA-65) | A vector store |
| Hash-chain-signed audit ledger | An eval harness (use `foundry-evals`) |
| MCP tool security scanner (poisoning, hidden instructions) | A prompt template library |
| Capability profiling + rogue-behaviour detection | An orchestration framework — it sits **inside** MAF / your runtime |
| OWASP ASI 2026 self-attestation (`agt verify --evidence ...`) | A replacement for Azure AI Content Safety — pair them |

**Upstream sources of truth** (all referenced from `references/upstream-pin.md`):

- Repo: <https://github.com/microsoft/agent-governance-toolkit>
- Docs site: <https://microsoft.github.io/agent-governance-toolkit>
- Quickstart: <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md>
- MAF adapter source: <https://github.com/microsoft/agent-governance-toolkit/tree/main/agent-governance-python/agent-os/src/agent_os/integrations>
- OWASP coverage: <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/OWASP-COMPLIANCE.md>

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

**Legend:** ✅ verified by GBB live smoke test on Windows + Python 3.13 + AGT 3.6.0;
📖 documented by upstream, not yet GBB-tested. Bump entries to ✅ as you validate.

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
4. **RogueDetectionMiddleware** — capability-profile drift detection (off by default — see Known Issue #4)

### Wiring snippet

The **working** snippet — verified end-to-end against AGT 3.6.0 + MAF 1.3.0
— is at [`references/maf-middleware-snippet.py`](references/maf-middleware-snippet.py).
Drop the `build_governed_agent(...)` helper into your hosted-agent module
and pass it the `FoundryChatClient` your azd-deployed project provides.

> **Why a snippet, not just a docs link?** Upstream's
> `docs/deployment/azure-foundry-agent-service.md` page documents
> manual middleware construction with kwargs that **no longer exist**
> in 3.6.0 (`AuditTrailMiddleware(log_directory=…)`,
> `GovernancePolicyMiddleware(policy_directory=…, max_tokens_per_turn=…)`,
> `RogueDetectionMiddleware(risk_threshold=…)`). Use the
> `create_governance_middleware(...)` factory; the snippet here does
> exactly that. See Known Issue #2.

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

Cross-link [`threadlight-safe-check`](../threadlight-safe-check/SKILL.md)
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
| `pip install agent-governance-toolkit[full]` | ✅ | AGT 3.6.0, Win11, Py 3.13.13 |
| `agt doctor` (with `PYTHONUTF8=1`) | ✅ | same |
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

1. **Windows CLI breaks without UTF-8 mode** — every `agt …` command
   crashes with `UnicodeEncodeError: 'charmap'` on a default PowerShell
   host. Set `PYTHONUTF8=1` (and `[Console]::OutputEncoding`) per shell;
   bake into CI runners. Will hit ~every Windows GBB user.

2. **Upstream Foundry deployment doc has stale middleware kwargs** —
   `docs/deployment/azure-foundry-agent-service.md` shows
   `AuditTrailMiddleware(log_directory=…)`,
   `GovernancePolicyMiddleware(policy_directory=…, max_tokens_per_turn=…)`,
   `RogueDetectionMiddleware(risk_threshold=…)` — **none of these kwargs
   exist in 3.6.0**. Use `create_governance_middleware(...)`; the skill's
   snippet does the right thing.

3. **`agent_framework.Agent` ctor takes `client`, not `chat_client`** —
   first positional. Some upstream snippets still show the old name and
   raise `TypeError: Agent.__init__() got an unexpected keyword argument
   'chat_client'`.

4. **`RogueDetectionMiddleware` requires a capability profile** — the
   factory's `enable_rogue_detection=True` will raise unless you also
   supply a `RogueAgentDetector` and a `capability_profile`. Default to
   `False` for first-pass; revisit after baselining.

5. **Verifier version skew is cosmetic** — `agt verify` reports
   `Toolkit: 3.2.2` while the meta-package is `3.6.0`. Verifier carries
   its own compliance schema version; OWASP ASI coverage check still
   passes 10/10.

---

## See Also

- [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md) — primary
  consumer of Path A
- [`threadlight-deploy`](../threadlight-deploy/SKILL.md) — deploy stage
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
- [`threadlight-safe-check`](../threadlight-safe-check/SKILL.md) — owner
  of the pre-deploy CI gate

> Cross-skill `See Also` pointers from those skills back to `foundry-agt`
> are deferred to a follow-up PATCH-bump PR (kept out of this PR for
> reviewability).

---

## Upstream references

- Repo (canonical): <https://github.com/microsoft/agent-governance-toolkit>
- Docs site: <https://microsoft.github.io/agent-governance-toolkit>
- Quickstart: <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md>
- Foundry deployment guide (read with Known Issue #2 in mind):
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
  <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/OWASP-COMPLIANCE.md>
- PyPI: <https://pypi.org/project/agent-governance-toolkit/>
- agent-framework PyPI: <https://pypi.org/project/agent-framework/>

---

## GBB Changelog

- **v1.0.0** — Initial wrapper. Pinned to AGT 3.6.0 + MAF 1.3.0. Live-smoke
  Path A on Windows + Python 3.13.13. Three starter policies, working
  middleware factory snippet, ACA sidecar Bicep fragment, Known Issues
  (5 entries) captured from field testing.
