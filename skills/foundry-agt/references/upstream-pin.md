---
schema_version: 2
freshness_tier: A
automation_tier: issue_only

upstream:
  type: github_repo
  repo: microsoft/agent-governance-toolkit
  ref: v4.1.0
  pinned_sha: 0de71ca6c95cf8b9b975ac96f48eaa7826bbe258
  pinned_commit_message: |
    v4.1.0 — released source tag. The meta-package now splits into
    agent-governance-toolkit-{core,integrations,cli,protocols}, all 4.1.0.
  license: MIT
  notes: |
    Pinned to the `v4.1.0` release tag, not `main` HEAD — this skill
    previously tracked `main` and was burned by an unreleased breaking
    change. automation_tier is issue_only because Agent Governance
    Toolkit is Public Preview and Microsoft Agent Framework (MAF) minor
    releases have changed this skill's factory/Agent contract before; a
    human must re-run the live-API verification pass below (or re-run
    `references/python/contract_probe.py` against the candidate version)
    before trusting any future auto-detected drift.

packages:
  - name: agent-governance-toolkit
    source: pypi
    version: "4.1.0"
    upstream_changelog: https://github.com/microsoft/agent-governance-toolkit/releases
    notes: |
      Meta-package; install with the `[full]` extra. The importable
      module surface this skill depends on (`agent_os.integrations.maf_adapter`,
      `agent_os.policies`, `agentmesh.governance`) is unchanged from the
      prior AGT 3.x pin despite the PyPI package split into
      agent-governance-toolkit-{core,integrations,cli,protocols} — all
      re-verified live against 4.1.0 in `contract_probe.py`.
  - name: agent-framework-core
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
    notes: |
      Selective, bounded MAF package — NOT the broad `agent-framework`
      meta-package the prior 3.x-era pin used. This skill only needs
      Agent / ChatResponse / Message / middleware plumbing, so pinning
      the specific sub-packages it imports (core, foundry, openai) keeps
      the candidate set small and auditable instead of dragging in the
      full MAF surface area on every refresh.
  - name: agent-framework-foundry
    source: pypi
    version: "1.10.4"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
    notes: |
      Provides `FoundryChatClient(project_endpoint, model, credential)`.
      Constructor signature re-verified live at 1.10.4 — the skill body's
      documented shape is unchanged.
  - name: agent-framework-openai
    source: pypi
    version: "1.12.0"
    upstream_changelog: https://pypi.org/project/agent-framework-openai/#history
    notes: |
      Transitive dependency of the `Agent.run` response-handling path
      this skill exercises; pinned explicitly (not left to resolver
      discretion) so a drifting transitive version can't silently change
      `ChatResponse` shape underneath the skill.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      Credential surface only. `AccessToken` itself imports from
      `azure.core.credentials`, not `azure-identity` — this pin only
      bounds the `DefaultAzureCredential`-shaped surface the skill's
      Foundry construction path documents.

docs_to_revalidate:
  - https://github.com/microsoft/agent-governance-toolkit
  - https://microsoft.github.io/agent-governance-toolkit
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-foundry-agent-service.md
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/compliance/owasp-agentic-top10-architecture.md
  - https://pypi.org/project/agent-governance-toolkit/
  - https://pypi.org/project/agent-framework-core/
  - https://pypi.org/project/agent-framework-foundry/
  - https://pypi.org/project/agent-framework-openai/

known_issues:
  - id: KI-001
    description: PYTHONUTF8=1 mandatory on Windows for agt CLI Rich glyphs
    upstream_url: https://github.com/microsoft/agent-governance-toolkit/issues/1
    status: closed_upstream_fixed
    workaround_location: removed from SKILL.md in v1.0.5
  - id: KI-002
    description: agt doctor's package table only recognizes pre-split legacy distribution names, so it undercounts a correctly installed 4.1.0 candidate set
    upstream_url: https://github.com/microsoft/agent-governance-toolkit/issues/2
    status: open_documented_workaround
    workaround_location: "See 'agt doctor legacy package-table lag' below — cosmetic, not a functional failure"
  - id: KI-003
    description: agt verify self-reports a stale Toolkit compliance-schema version independent of the installed meta-package version
    upstream_url: https://github.com/microsoft/agent-governance-toolkit/issues/3
    status: open_documented_workaround
    workaround_location: "See 'agt verify version skew' below — cosmetic, not a functional failure"

validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    REPO_ROOT="${PIN_VALIDATION_REPO_ROOT:-$(pwd)}"
    python3 -m venv .venv-agt-pin-check
    . .venv-agt-pin-check/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet \
      "agent-governance-toolkit[full]~=${PINNED_AGT_VERSION:-4.1.0}" \
      "agent-framework-core~=${PINNED_AF_CORE_VERSION:-1.13.0}" \
      "agent-framework-foundry~=${PINNED_AF_FOUNDRY_VERSION:-1.10.4}" \
      "agent-framework-openai~=${PINNED_AF_OPENAI_VERSION:-1.12.0}" \
      "azure-identity~=${PINNED_IDENTITY_VERSION:-1.25.3}"
    pip check
    python3 "$REPO_ROOT/skills/foundry-agt/references/python/contract_probe.py"
    agt --version
    agt doctor
    agt_verify_output="$(agt verify)"
    echo "$agt_verify_output"
    echo "$agt_verify_output" | grep -F "OWASP ASI 2026"
    deactivate
  expected_output:
    - "agent-governance-toolkit=4.1.0"
    - "STUB_FOUNDRY_CONSTRUCTION=PASS"
    - "STUB_RESPONSE_SHAPE=PASS"
    - "CAPABILITY_HOOK_ALLOW_EXECUTIONS=1"
    - "CAPABILITY_HOOK_DENY_EXECUTIONS=0"
    - "CAPABILITY_HOOK=PASS"
    - "HITL_POLICY=PASS"
    - "CONTRACT_PROBE=PASS"
    - "OWASP ASI 2026"

last_validated: 2026-08-06
validated_by: copilot-bot
known_issues_count: 3
---

# Upstream pin — `foundry-agt` skill

This file captures the exact upstream state the skill body is authored
against, plus the GBB-discovered field findings from live verification.
Bump the SKILL.md `metadata.version` (MAJOR, this is a breaking refresh)
whenever you re-pin, and re-run `references/python/contract_probe.py`
before trusting the new candidate set.

---

## Why a released source tag, not `main`

The prior AGT 3.x pin tracked `ref: main`. This refresh moves to the
`v4.1.0` release tag (SHA `0de71ca6c95cf8b9b975ac96f48eaa7826bbe258`) —
a released source snapshot is reproducible; `main` HEAD is not, and can
carry unreleased breaking changes between one CI run and the next.
`automation_tier` stays `issue_only`: AGT is Public Preview and MAF
minor releases have changed this skill's `Agent`/factory contract
before, so a human reviews every refresh rather than an autonomous
bump merging on green CI alone.

---

## Selective, bounded MAF packages

The prior 3.x-era pin installed the broad `agent-framework` meta-package.
This refresh pins the three sub-packages the skill actually imports
instead:

| Package | Pinned | What it provides for this skill |
|---------|--------|----------------------------------|
| `agent-framework-core` | 1.13.0 | `Agent`, `ChatResponse`, `Message`, `FunctionTool`, `FunctionInvocationContext`, `MiddlewareTermination` |
| `agent-framework-foundry` | 1.10.4 | `FoundryChatClient(project_endpoint, model, credential)` |
| `agent-framework-openai` | 1.12.0 | transitive dependency of the `Agent.run` response path |

Pinning the specific sub-packages (rather than the meta-package) keeps
the candidate set small, keeps `pip check` fast, and avoids dragging in
MAF extras (voice, realtime, etc.) this governance-focused skill never
touches.

---

## Upstream packages (verified live at authoring time)

| Package | Source | Pinned version |
|---------|--------|----------------|
| `agent-governance-toolkit` | PyPI (`pip install agent-governance-toolkit[full]`) | **4.1.0** |
| `agent-governance-toolkit` repo | <https://github.com/microsoft/agent-governance-toolkit> | tag `v4.1.0` (`0de71ca6...`) |
| `agent-framework-core` | PyPI | **1.13.0** |
| `agent-framework-foundry` | PyPI | **1.10.4** |
| `agent-framework-openai` | PyPI | **1.12.0** |
| `azure-identity` | PyPI | **1.25.3** |

`contract_probe.py` verifies each of these exact versions with
`importlib.metadata.version(...)` before touching any API surface —
if the installed candidate set drifts from the table above, the probe
fails before running a single behavioral check.

---

## `agt doctor` legacy package-table lag (cosmetic, not a functional failure)

Live output against a correctly installed 4.1.0 `[full]` candidate set:

```text
$ agt doctor
 1/8 packages installed
```

`agt doctor`'s package table still checks for the pre-split distribution
names (`agent_os_kernel`, `agentmesh_platform`, `agentmesh_runtime`,
`agent_sre`, `agentmesh_marketplace`, `agentmesh_lightning`,
`agent_hypervisor`) — none of which are separate installable
distributions any more under the 4.1.0 package split. Only the meta-package
itself (`agent_governance_toolkit`) matches, hence "1/8". This is a
**known, upstream-tracked cosmetic gap** (KI-002) in the doctor
subcommand, not evidence of a broken install: `contract_probe.py`'s
version and import checks are the authoritative signal for "is 4.1.0
actually installed and importable", and they pass.

## `agt verify` version skew (cosmetic, not a functional failure)

Live output against the same candidate set:

```text
$ agt verify
Agent Governance Toolkit — Verification PASSED ✅
OWASP ASI 2026 Coverage: 10/10 (100%)
Toolkit: 3.2.2
```

`agt verify` self-reports its own compliance-schema version
(`Toolkit: 3.2.2`), independent of the installed meta-package version
(4.1.0). This is a **known, upstream-tracked skew** (KI-003) between the
verifier's internal schema numbering and the package release cadence —
the OWASP ASI 2026 coverage result (10/10) is what this skill's
validation script actually gates on, and it is unaffected by the skew.

`agt verify` is a **self-assessment** the toolkit runs against its own
policy/audit/capability surfaces — it is not an independent
certification, and this pin does not represent it as one.

---

## Verified API surface (4.1.0 / MAF 1.13.0)

These are the **actual** signatures from `inspect.signature(...)`,
re-verified live for this refresh. `contract_probe.py` is the
executable source of truth — this section is a human-readable summary,
not a substitute for running the probe.

```python
from agent_os.integrations.maf_adapter import (
    AuditTrailMiddleware,          # (audit_log: AuditLog, agent_did: str | None = None)
    CapabilityGuardMiddleware,     # (allowed_tools=None, denied_tools=None, audit_log=None)
    GovernancePolicyMiddleware,    # (evaluator: PolicyEvaluator, audit_log: AuditLog | None = None)
    create_governance_middleware,  # ← USE THIS — assembles the stack correctly
)

# create_governance_middleware factory (RECOMMENDED entry point)
#   policy_directory: str | Path | None = None,
#   allowed_tools: list[str] | None = None,
#   denied_tools: list[str] | None = None,
#   agent_id: str = "default-agent",
#   enable_rogue_detection: bool = False,
#   audit_log: AuditLog | None = None,
# Returns: list[Middleware] in execution order (4 items if
# enable_rogue_detection=True, 3 otherwise)
```

```python
from agent_framework import Agent

# Agent ctor (1.13.0):
#   Agent(client, instructions=None, *, name=None, middleware=None, tools=None, ...)
# - first positional is `client` (NOT `chat_client`)
# - `middleware` accepts the list returned by create_governance_middleware()
```

```python
from agent_framework.foundry import FoundryChatClient

# FoundryChatClient ctor (1.10.4):
#   FoundryChatClient(project_endpoint: str, model: str, credential, ...)
# - constructs with zero network calls; exposes the resolved model via
#   `.model` (NOT `.model_id`)
```

```python
from agentmesh.governance import AuditLog

# Public methods (use these, NOT private `.entries`):
#   log(event_type, agent_did, action, resource=None, data=None, outcome="success",
#       policy_decision=None, trace_id=None) -> AuditEntry
#   verify_integrity()         # hash-chain integrity
#   export_cloudevents(...)    # OTel-compatible export
```

```python
from agent_os.policies import PolicyEvaluator

# Public methods:
#   load_policies(directory: str | Path)      # loads *.yaml + *.yml files
#   evaluate(context: dict) -> PolicyDecision
```

---

## Known Issues (GBB field findings)

These belong in the SKILL.md "Known Issues" section, but are pinned
here so the next refresh remembers to re-test them.

### Issue 1 — Windows CLI breaks without UTF-8 mode

`agt doctor`, `agt verify`, `agt --version` (anything that emits a
Rich glyph) raise `UnicodeEncodeError: 'charmap' codec can't encode
character` on a default Windows PowerShell host (cp1252).

**Mandatory fix** (per shell, before the first `agt` invocation):

```powershell
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Bake `PYTHONUTF8=1` into every CI runner that calls `agt verify`.

### Issue 2 — `agt doctor` legacy package-table lag

See "`agt doctor` legacy package-table lag" above (KI-002). Do not
treat "N/8 packages installed" as a failed install; it only reflects
the pre-split package names the doctor subcommand still checks for.

### Issue 3 — Rogue detection needs an explicit opt-in, not an error

In the AGT 3.x pin, `enable_rogue_detection=True` was documented as
raising without an explicit `RogueAgentDetector` + `capability_profile`.
Re-verified live at 4.1.0: `create_governance_middleware(enable_rogue_detection=True)`
now constructs successfully and returns a 4th `RogueDetectionMiddleware`
in the stack — it does **not** raise. This skill's factory still
defaults to `enable_rogue_detection=False`, as a deliberate choice (a
freshly deployed agent has no behavioral baseline for the detector to
compare against yet), not because the toolkit errors without one.

### Issue 4 — `agt verify` version skew

See "`agt verify` version skew" above (KI-003).

---

## URLs to re-validate at every re-pin

(Drop into a `curl -fsSL -o /dev/null` sweep before commit.)

- <https://github.com/microsoft/agent-governance-toolkit>
- <https://microsoft.github.io/agent-governance-toolkit>
- <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/quickstart.md>
- <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/deployment/azure-foundry-agent-service.md>
- <https://github.com/microsoft/agent-governance-toolkit/blob/main/docs/compliance/owasp-agentic-top10-architecture.md>
- <https://github.com/microsoft/agent-governance-toolkit/tree/main/agent-governance-python/agent-os/src/agent_os/integrations>
- <https://pypi.org/project/agent-governance-toolkit/>
- <https://pypi.org/project/agent-framework-core/>
- <https://pypi.org/project/agent-framework-foundry/>
- <https://pypi.org/project/agent-framework-openai/>
