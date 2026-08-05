---
schema_version: 2
freshness_tier: A
automation_tier: auto

upstream:
  type: github_repo
  repo: microsoft/agent-governance-toolkit
  ref: main
  pinned_sha: b3c899675e8f76a263f3f1f22a7a29137d84fe03
  pinned_commit_message: |
    feat(sdks): host-side telemetry and OpenTelemetry export across Python,
    Rust, Node, and .NET (#3190)
  license: MIT
  notes: |
    Wrapper skill around the AGT meta-package. The skill body documents
    the in-process middleware path (create_governance_middleware factory)
    against AGT 4.1.0 — re-validate API signatures on every minor bump.

packages:
  - name: agent-governance-toolkit
    source: pypi
    version: "4.1.0"
    upstream_changelog: https://github.com/microsoft/agent-governance-toolkit/releases
    notes: |
      Meta-package; install with `[full]` extra to pull all 6 sub-packages.
  - name: agent-framework
    source: pypi
    version: "1.10.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      Required for the in-process middleware integration path.
      The 1.10.0 meta-package's `agent-framework-core[all]` dependency does
      not resolve cleanly. Validation installs the bounded core package first,
      then installs the matching meta-package with `--no-deps`; this preserves
      the declared distribution pin while proving the middleware factory against
      the required runtime API.
  - name: agent-framework-core
    source: pypi
    version: "1.10.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
    notes: |
      Runtime package installed before the matching meta-package to avoid the
      1.10.0 `[all]` resolver conflict.

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
    : "${PIN_VALIDATION_REPO_ROOT:?PIN_VALIDATION_REPO_ROOT must point to the canonical checkout}"
    python -m venv .venv-agt
    . .venv-agt/bin/activate
    pip install --quiet "agent-governance-toolkit[full]~=${PINNED_VERSION:-4.1.0}" "agent-framework-core~=${PINNED_AGENT_FRAMEWORK_VERSION:-1.10.0}"
    pip install --quiet --no-deps "agent-framework~=${PINNED_AGENT_FRAMEWORK_VERSION:-1.10.0}"
    agt --version
    agt doctor
    agt verify
    python - <<'PY'
    import os
    from pathlib import Path
    from agent_os.integrations.maf_adapter import create_governance_middleware
    from agentmesh.governance import AuditLog

    policy_dir = (
        Path(os.environ["PIN_VALIDATION_REPO_ROOT"])
        / "skills"
        / "foundry-agt"
        / "references"
        / "policies"
    )
    stack = create_governance_middleware(
        policy_directory=policy_dir,
        allowed_tools=[],
        denied_tools=[],
        agent_id="pin-smoke",
        enable_rogue_detection=False,
        audit_log=AuditLog(),
    )
    assert [type(item).__name__ for item in stack] == [
        "AuditTrailMiddleware",
        "GovernancePolicyMiddleware",
        "CapabilityGuardMiddleware",
    ]
    print("factory ok")
    PY
  expected_output:
    - "OWASP ASI 2026"
    - "factory ok"

last_validated: 2026-08-05
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
| `agent-governance-toolkit` | PyPI (`pip install agent-governance-toolkit[full]`) | **4.1.0** | Meta-package; `[full]` pulls the consolidated core, integrations, CLI, and protocols distributions |
| `agent-governance-toolkit` repo | <https://github.com/microsoft/agent-governance-toolkit> | main `b3c89967...` | Public Preview, MIT, Microsoft-owned |
| `agent-framework` (MAF) | PyPI (`pip install agent-framework`) | **1.10.0** | Required for the in-process middleware path. Install bounded `agent-framework-core` first, then the matching meta-package with `--no-deps`, because the 1.10.0 `[all]` dependency does not resolve cleanly (see `packages[*].notes`). |

Consolidated distributions installed by `agent-governance-toolkit[full]`:

- `agent-governance-toolkit`
- `agent-governance-toolkit-core`
- `agent-governance-toolkit-integrations`
- `agent-governance-toolkit-cli`
- `agent-governance-toolkit-protocols`

`agt doctor` 4.1.0 still scans the retired pre-consolidation distribution
names and reports `1/8 packages installed`; use `agt verify` plus the
middleware factory import as the validation contract. `agt verify` self-reports
`Toolkit: 3.2.2` because the verifier's compliance schema versions
independently from the 4.1.0 meta-package.

---

## Verification checklist (run for every re-pin)

Throwaway venv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = "1"               # MANDATORY on Windows — see Known Issues
pip install "agent-governance-toolkit[full]~=4.1.0" "agent-framework-core~=1.10.0"
pip install --no-deps "agent-framework~=1.10.0"
agt --version
agt doctor                          # 4.1.0 currently reports legacy 1/8 names
agt verify                          # expect 10/10 OWASP ASI 2026
python -c "from agent_os.integrations.maf_adapter import create_governance_middleware; print('factory ok')"
```

If `agt doctor` or `agt verify` raises `UnicodeEncodeError`, you forgot
`PYTHONUTF8=1` (see Known Issues #1). The skill's quickstart bakes this in.

---

## Live smoke results (last verified)

| Check | Result | Evidence |
|-------|--------|----------|
| Bounded AGT + MAF install | ✅ | AGT 4.1.0, `agent-framework-core` 1.10.0, and `agent-framework` 1.10.0 |
| `agt doctor` | ✅ | Command completes; its legacy package scan reports 1/8 after package consolidation |
| `agt verify` | ✅ | OWASP ASI 2026: **10/10 PASSED** |
| `create_governance_middleware(...)` factory | ✅ | Returns audit, policy, and capability middleware for the canonical policy-directory path |
| Middleware signature inspection | ✅ | 4.1.0 signatures below match `inspect.signature(...)` |

---

## Verified API surface (4.1.0)

These are the **actual** signatures from `inspect.signature(...)`. The
upstream `docs/deployment/azure-foundry-agent-service.md` page documents
older / aspirational kwargs that no longer exist (see Known Issues #2).
Use these:

```python
from agent_os.integrations.maf_adapter import (
    GovernancePolicyMiddleware,    # (evaluator=None, audit_log=None, *, kernel=None, agent_id="maf-agent")
    CapabilityGuardMiddleware,     # (allowed_tools=None, denied_tools=None, audit_log=None, *, kernel=None, agent_id="maf-agent")
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
