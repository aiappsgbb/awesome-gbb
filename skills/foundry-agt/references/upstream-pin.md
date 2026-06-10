---
schema_version: 2
freshness_tier: A
automation_tier: auto

upstream:
  type: github_repo
  repo: microsoft/agent-governance-toolkit
  ref: main
  pinned_sha: 6572fd0803b87f0d53489bc3ecff5fa4a3d6a047
  pinned_commit_message: |
    AGT 3.7.0 release — meta-package + 6 sub-packages
  license: MIT
  notes: |
    Wrapper skill around the AGT meta-package. The skill body documents
    the in-process middleware path (create_governance_middleware factory)
    and verified API surface at 3.7.0 — re-validate API signatures on
    every minor bump.

packages:
  - name: agent-governance-toolkit
    source: pypi
    version: "3.7.0"
    upstream_changelog: https://github.com/microsoft/agent-governance-toolkit/releases
    notes: |
      Meta-package; install with `[full]` extra to pull all 6 sub-packages.
  - name: agent-framework
    source: pypi
    version: "1.8.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      Required for the in-process middleware integration path.
      1.8.0 (released 2026-06-04) ships two `[BREAKING]` markers, neither
      of which affects this skill: (a) the `agent-framework-github-copilot`
      sub-package is not pinned here; (b) the experimental `Skill`
      abstract-class refactor in `agent-framework-core` is not consumed by
      AGT's middleware stack. The `Agent(client, instructions, *, name,
      middleware, tools, ...)` ctor and `FunctionInvocationContext` hook
      that `create_governance_middleware(...)` depends on are unchanged.

docs_to_revalidate:
  - https://github.com/microsoft/agent-governance-toolkit
  - https://microsoft.github.io/agent-governance-toolkit
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-foundry-agent-service.md
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-container-apps.md
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/compliance/owasp-agentic-top10-architecture.md
  - https://pypi.org/project/agent-governance-toolkit/
  - https://pypi.org/project/agent-framework/

known_issues:
  - id: KI-001
    description: PYTHONUTF8=1 mandatory on Windows for agt CLI Rich glyphs
    upstream_url: https://github.com/microsoft/agent-governance-toolkit/issues/1
    status: closed_upstream_fixed
    workaround_location: removed from SKILL.md in v1.0.5
  - id: KI-002
    description: Upstream Foundry deployment doc shows stale middleware kwargs
    upstream_url: https://github.com/microsoft/agent-governance-toolkit/issues/2
    status: closed_upstream_fixed
    workaround_location: removed from SKILL.md in v1.0.4
  - id: KI-003
    description: agent_framework.Agent ctor takes `client`, not `chat_client`
    upstream_url: https://github.com/microsoft/agent-governance-toolkit/issues/3
    status: closed_upstream_fixed
    workaround_location: removed from SKILL.md in v1.0.4

validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv-agt
    . .venv-agt/bin/activate
    pip install --quiet "agent-governance-toolkit[full]~=${PINNED_VERSION:-3.7.0}" "agent-framework~=${PINNED_AGENT_FRAMEWORK_VERSION:-1.8.0}"
    agt --version
    agt doctor
    agt verify
    python -c "from agent_os.integrations.maf_adapter import create_governance_middleware; print('factory ok')"
  expected_output:
    - "OWASP ASI 2026"
    - "factory ok"

last_validated: 2026-06-09
validated_by: copilot-bot
known_issues_count: 3
---

# Upstream pin — `foundry-agt` skill

This file captures the exact upstream state that the skill body was
authored against, plus the GBB-discovered field findings from the live
smoke test. Bump the SKILL.md `metadata.version` (PATCH) whenever you
re-pin to a newer upstream and re-run the smoke checklist below.

---

## Upstream packages (verified at authoring time)

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `agent-governance-toolkit` | PyPI (`pip install agent-governance-toolkit[full]`) | **3.7.0** | Meta-package; pulls 6 sub-packages with `[full]` extra |
| `agent-governance-toolkit` repo | <https://github.com/microsoft/agent-governance-toolkit> | main `8c4692cf...` | Public Preview, MIT, Microsoft-owned |
| `agent-framework` (MAF) | PyPI (`pip install agent-framework`) | **1.8.0** | Required for in-process middleware path; 1.8.0 ships 2 `[BREAKING]` markers, neither affects this skill (see `packages[*].notes`) |
| Internal `agentmesh-runtime` | bundled with `[full]` | 2.3.0 | Independent versioning cadence — note skew |

Sub-packages installed by `agent-governance-toolkit[full]` (verified via
`agt doctor`):

- ✅ `agent_governance_toolkit` (meta)
- ✅ `agent_os_kernel`
- ✅ `agentmesh_platform`
- ✅ `agentmesh_runtime` (2.3.0)
- ✅ `agent_sre`
- ✅ `agent_hypervisor`
- ⛔ `agentmesh_marketplace` — not pulled by `[full]`
- ⛔ `agentmesh_lightning` — not pulled by `[full]`

CLI version skew: `agt verify` self-reports `Toolkit: 3.2.2` while the
meta-package is `3.7.0`. The verifier ships its own compliance schema
version independently. Cosmetic, not a bug.

---

## Verification checklist (run for every re-pin)

Throwaway venv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"               # MANDATORY on Windows — see Known Issues
pip install agent-governance-toolkit[full] agent-framework
agt --version
agt doctor                          # expect 6/8 packages present
agt verify                          # expect 10/10 OWASP ASI 2026
python -c "from agent_os.integrations.maf_adapter import create_governance_middleware; print('ok')"
```

If `agt doctor` or `agt verify` raises `UnicodeEncodeError`, you forgot
`PYTHONUTF8=1` (see Known Issues #1). The skill's quickstart bakes this in.

---

## Live smoke results (last verified)

| Check | Result | Evidence |
|-------|--------|----------|
| `pip install agent-governance-toolkit[full]` | ✅ | 6/8 sub-packages installed |
| `agt doctor` | ✅ | All required packages present |
| `agt verify` | ✅ | OWASP ASI 2026: **10/10 PASSED** |
| `examples/quickstart/govern_in_60_seconds.py` | ✅ | 5 actions, 3 DENY / 2 ALLOW, 0.002 ms avg |
| `create_governance_middleware(...)` factory | ✅ | Returns 3 mw (audit + policy + capability) |
| `PolicyEvaluator.load_policies("dir/")` (YAML) | ✅ | 1 file → 1 policy loaded |
| Policy ALLOW path latency | ✅ | **8.03 µs/eval** (1k iters) |
| Policy DENY path latency | ✅ | **12.35 µs/eval** (1k iters) |
| Custom `message:` surfaces in `decision.reason` | ✅ | "SQL injection pattern blocked by GBB policy" |
| Regex `matches` operator (PII patterns) | ✅ | SSN regex `\b\d{3}-\d{2}-\d{4}\b` matches |
| `AuditLog.log(...)` returns `AuditEntry` | ✅ | (entries iterable is private — use `query()`) |
| `AuditLog.verify_integrity()` API present | ✅ | Hash-chain integrity check available |
| `AuditLog.export_cloudevents()` | ✅ | OTel-compatible export — wires into `foundry-observability` |

Latency comparison: upstream documents "< 0.1 ms (100 µs) per check" — the
GBB workstation observed **~8–12 µs**, an order of magnitude headroom.
This is healthy for any Foundry-shaped agent, including high-tool-fanout
threadlight processes.

---

## Verified API surface (3.7.0)

These are the **actual** signatures from `inspect.signature(...)`. The
upstream `docs/deployment/azure-foundry-agent-service.md` page documents
older / aspirational kwargs that no longer exist (see Known Issues #2).
Use these:

```python
from agent_os.integrations.maf_adapter import (
    GovernancePolicyMiddleware,    # (evaluator: PolicyEvaluator, audit_log: AuditLog | None = None)
    CapabilityGuardMiddleware,     # (allowed_tools=None, denied_tools=None, audit_log=None)
    AuditTrailMiddleware,          # (audit_log: AuditLog, agent_did: str | None = None)
    RogueDetectionMiddleware,      # (detector: RogueAgentDetector, agent_id: str, capability_profile=None, audit_log=None)
    create_governance_middleware,  # ← USE THIS — assembles the stack correctly
)

# create_governance_middleware factory (RECOMMENDED entry point)
#   policy_directory: str | Path | None = None,
#   allowed_tools: list[str] | None = None,
#   denied_tools: list[str] | None = None,
#   agent_id: str = "default-agent",
#   enable_rogue_detection: bool = True,
#   audit_log: AuditLog | None = None,
# Returns: list[Middleware] in execution order
```

```python
from agent_framework import Agent

# Agent ctor (1.8.0):
#   Agent(client, instructions=None, *, name=None, middleware=None, tools=None, ...)
# - first positional is `client` (NOT `chat_client` as some doc snippets show)
# - `middleware` accepts the list returned by create_governance_middleware()
```

```python
from agentmesh.governance import AuditLog

# Public methods (use these, NOT private `.entries`):
#   log(event_type, agent_did, action, resource=None, data=None, outcome="success",
#       policy_decision=None, trace_id=None) -> AuditEntry
#   query(...)
#   get_entries_by_type(event_type)
#   get_entries_for_agent(agent_did)
#   verify_integrity()         # hash-chain integrity
#   export(...)                # JSON export
#   export_cloudevents(...)    # OTel-compatible export
```

```python
from agent_os.policies import PolicyEvaluator

# Public methods:
#   load_policies(directory: str | Path)      # loads *.yaml + *.yml files
#   load_rego(rego_path=None, rego_content=None, package="agentos")
#   load_cedar(policy_path=None, policy_content=None, entities=None)
#   add_backend(backend)
#   evaluate(context: dict) -> PolicyDecision
```

---

## Known Issues (GBB field findings)

These belong in the SKILL.md "Known Issues" section, but are pinned here
so the next refresh remembers to re-test them:

### Issue 1 — Windows CLI breaks without UTF-8 mode

`agt doctor`, `agt verify`, `agt --version` (anything that emits a
🩺 / 🛡️ / ✅ glyph through Rich) raise `UnicodeEncodeError: 'charmap'
codec can't encode character '\U0001fa7a'` on a default Windows
PowerShell host (cp1252).

**Mandatory fix** (per shell, before the first `agt` invocation):

```powershell
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Or persist for the user:

```powershell
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
```

Bake `PYTHONUTF8=1` into every CI runner that calls `agt verify`.

### Issue 2 — Upstream Foundry deployment doc has stale signatures

`docs/deployment/azure-foundry-agent-service.md` shows manual middleware
construction with kwargs that **do not exist** in 3.7.0:

| Doc shows | 3.6.0 actual |
|-----------|--------------|
| `AuditTrailMiddleware(log_directory="./logs", include_tool_args=True, include_responses=True, log_format="jsonl")` | `AuditTrailMiddleware(audit_log, agent_did=None)` |
| `GovernancePolicyMiddleware(policy_directory="./policies", max_tokens_per_turn=4000, rate_limit_per_minute=20, blocked_patterns=[...], enable_content_safety=True)` | `GovernancePolicyMiddleware(evaluator, audit_log=None)` |
| `RogueDetectionMiddleware(risk_threshold=0.7, window_size=10, alert_callback=fn)` | `RogueDetectionMiddleware(detector, agent_id, capability_profile=None, audit_log=None)` |

**Fix**: ignore the manual-composition snippet in the upstream Foundry
doc; use `create_governance_middleware(...)` factory, which assembles
the stack correctly. The skill's `references/maf-middleware-snippet.py`
ships the working pattern.

### Issue 3 — `agent_framework.Agent` ctor takes `client`, not `chat_client`

Some doc snippets (and one of upstream's earlier blog posts) show
`Agent(name=..., chat_client=..., middleware=...)`. In 1.8.0 the first
positional is `client`:

```python
Agent(client, instructions=None, *, name=None, middleware=...)
```

Trying `chat_client=...` raises `TypeError: Agent.__init__() got an
unexpected keyword argument 'chat_client'`.

### Issue 4 — `RogueDetectionMiddleware` requires explicit setup

The factory `create_governance_middleware(enable_rogue_detection=True)`
will raise on instantiation unless you supply a `RogueAgentDetector` and
a `capability_profile`. For a first-pass deployment, set
`enable_rogue_detection=False` and revisit once you have a baseline of
agent behaviour to feed the detector. The skill's policy starter set
omits rogue detection by default for this reason.

### Issue 5 — Verifier version skew is cosmetic

`agt verify` reports `Toolkit: 3.2.2` while the meta-package is `3.7.0`.
The verifier carries its own compliance schema version. Don't be
alarmed; the OWASP ASI 2026 coverage check still passes 10/10.

---

## URLs to re-validate at every re-pin

(Drop into a `curl -fsSL -o /dev/null` sweep before commit.)

- <https://github.com/microsoft/agent-governance-toolkit>
- <https://microsoft.github.io/agent-governance-toolkit>
- <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md>
- <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-foundry-agent-service.md>
- <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-container-apps.md>
- <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/compliance/owasp-agentic-top10-architecture.md>
- <https://github.com/microsoft/agent-governance-toolkit/tree/main/agent-governance-python/agent-os/src/agent_os/integrations>
- <https://github.com/microsoft/agent-governance-toolkit/tree/main/examples/quickstart>
- <https://pypi.org/project/agent-governance-toolkit/>
- <https://pypi.org/project/agent-framework/>
