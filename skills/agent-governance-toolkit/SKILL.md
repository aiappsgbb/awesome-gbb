---
name: agent-governance-toolkit
description: >
  Use when adding Microsoft Agent Governance Toolkit (AGT) to an agentic
  workload, when an agent codebase has tool calls but no deterministic
  policy enforcement, cryptographic audit chain, per-agent identities,
  or operator kill switch, or when an auditor wants reproducible evidence
  (`agt verify`) of agent behaviour. Stacks: Python FastAPI / Azure
  Functions / LangChain / LangGraph / Foundry hosted agents / Semantic
  Kernel (.NET / Python) / MCP server.
  USE FOR: add agt, governance kernel, policy bundle, policy compiler,
  hash-chained audit ledger, ed25519 agent identity, jws audit receipt,
  agt verify/mcp-scan/lint-policy/discover/red-team, kill switch,
  OWASP Agentic Top 10 evidence, reversibility gate,
  log-only to enforce flip, application-layer policy enforcement.
  DO NOT USE FOR: prompt-injection / content safety (Azure AI Content
  Safety); Entra Agent ID / Microsoft Agent 365 provisioning; central
  AI gateway governance (use citadel-spoke-onboarding); OTel wiring (use
  foundry-observability).
metadata:
  version: "1.0.0"
---

# Agent Governance Toolkit (AGT) — Onboarding Recipe

How to drop the [Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
(AGT) into an agentic workload as the **runtime governance core**: a
deterministic, sub-millisecond policy evaluator that every tool call,
authority resolution, and inter-agent message routes through, plus a
cryptographic spine that turns audit trails from "trust me" into
auditor-reproducible evidence.

> **AGT version:** 3.4.x (Public Preview as of writing — see § Versioning).
> **License:** MIT. **Runtime:** in-process Python (other language bindings
> exist per upstream docs; this skill documents the Python recipe in
> detail and provides the architectural hooks needed to adapt to other
> runtimes — see § Runtime adaptation).
>
> **What AGT is not.** AGT is **application-layer policy enforcement**,
> not content safety. Prompt-injection defense, jailbreak detection, and
> harmful-content classification stay with **Azure AI Content Safety**.
> AGT decides whether *this actor* may invoke *this tool* with *these
> args* against *this resource* at *this value* — deterministically, from
> a declarative bundle.

---

## Key concepts

| Term | Meaning |
|------|---------|
| **GovernanceKernel** | A frozen, process-singleton policy evaluator. Constructed once at app startup. Mediates every tool call. Pure function of `(policy_bundle_hash, request_tuple)`; sub-millisecond; reentrant. |
| **Policy bundle** | An AGT YAML document compiled from your authority matrix + tool manifest + agent registry. Deterministic — same inputs produce byte-identical YAML. Bundle hash (sha256) is the `policy_version` recorded on every decision. |
| **Tool manifest** | A YAML file (`tools.yaml`) declaring every MCP / agent tool the workload uses, with `reversible: bool`, `requires_capability`, `requires_authority`, `value_field`. The **only** place reversibility is declared — never in agent SKILL.md prose. |
| **Agent registry** | A code-level enumeration of every machine agent that calls tools, with `agent_id`, `allowed_tools`, `max_value_gbp` (or your currency), `reversible_only`, `scope_function`. Single source of truth; no agent_id may appear in any ledger entry without being registered. |
| **Action ledger** | Per-workflow append-only audit blob. After AGT, every entry carries `prev_hash`, `entry_hash`, `actor_jws`, `decision_id`, `policy_version`, `enforcement_mode` — a hash-chained, signed chain. |
| **Decision** | The kernel's per-call output: `{allowed, decision_id, policy_version, rule_id, reason, enforcement_mode, evaluated_at, latency_us}`. Carried on the ledger entry. |
| **Reversibility gate** | A global high-priority policy rule denying any `tool.reversible == false` call below an `ENFORCE_FLOOR` priority. Only a closed HITL gate produces a high-enough priority ALLOW to break through. |
| **Kill switch** | Operator-toggleable per-`(agent_id, tool)` denial flag (with wildcard semantics). Consulted before policy evaluation. Sub-second; no redeploy. |
| **`agt verify`** | CLI command that re-walks an audit blob, validates every hash and every JWS, and resolves every `decision_id` back to the policy rule + bundle hash that produced it. Pure offline cryptographic proof. |

---

## Architectural invariants (the cross-runtime contract)

These hold regardless of language or framework. Violate at your peril.

1. **One kernel.** Exactly one process-level `GovernanceKernel` instance.
   Constructed at app startup; accessed via a `kernel()` getter. No DI
   framework. No per-request kernel; the policy bundle is shared, the
   evaluator is pure.

2. **One narrow AGT import surface.** Pick **one** module
   (e.g. `<app>/services/governance/__init__.py`) that re-exports
   everything the rest of the codebase needs (`Decision`,
   `GovernanceDenied`, `kernel()`). **All** other files import from that
   re-export; no other file imports `agent_os.*`, `agentmesh.*`,
   `agent_compliance.*` directly. AGT is in Public Preview and the
   surface can shift between minor versions — one re-export keeps the
   upgrade to a single-file diff.

3. **Two chokepoints, per side.** Whatever your runtime, identify **at
   most two** code paths through which tool calls flow, and call
   `kernel().evaluate_tool_call(...)` immediately before the network /
   dispatch hop in each. No third enforcement point is permitted; a code
   review rejects any new tool integration that doesn't route through
   one of the two.

4. **Bundle compiled at boot, not committed.** The compiler is a pure
   function of `(authority_matrix, tools.yaml, agent_registry)`. Same
   inputs → byte-identical YAML output. Compilation failure halts boot
   with a clear error pointing at the offending `rule_id`. The compiled
   YAML is **not** committed — the inputs are the source of truth.
   (Optional future step: commit the bundle for reproducibility audits.)

5. **Per-workflow hash chain, never global.** Each workflow's audit
   blob is its own chain. `prev_hash[0] = "0" * 64`. Parallel writes
   across different workflows are safe; cross-workflow correlation is
   the consumer's job, not the chain's.

6. **JWS Compact Serialization, EdDSA / Ed25519.** Receipts are
   `alg=EdDSA`, `kid=<agent_id>`. Verification is pure — public key +
   JWS + payload hash. No Key Vault round-trip in the hot path: public
   keys load once at boot.

7. **Two modes, one switch.** `log_only` records decisions without
   raising; `enforce` raises `GovernanceDenied` on `allowed=False`. The
   mode is recorded on every ledger entry as `enforcement_mode`. The
   switch is a single environment variable (canonically `AGT_ENFORCE=1`)
   — there is no per-call override and no env var that turns the kernel
   *off* once installed. To disable governance you uninstall AGT and
   remove the chokepoints.

8. **Fail closed.** A kernel failure (bundle compilation error at
   runtime, store unreachable, missing pubkey) is a fail-closed DENY,
   never a silent ALLOW. There is no try/except that swallows kernel
   exceptions.

9. **Public-private key isolation.** Private signing keys never appear
   in logs, audit blobs, or HTTP responses. The audit chain is verified
   with public keys only.

10. **No content-safety conflation.** AGT does not classify text. If a
    request fails a content-safety filter, that's an upstream concern
    that produces a DENY *input* to AGT, not a check inside the kernel.

---

## Runtime adaptation

The chokepoint pattern is language- and framework-agnostic. Identify the
**single** tool-dispatch point per side of your app, and wrap it.

| Stack | Chokepoint 1 (outbound MCP / tool calls) | Chokepoint 2 (in-process tool decorator) | Notes |
|------|------------------------------------------|------------------------------------------|-------|
| **Python FastAPI** | The function that issues `httpx.post(<mcp-endpoint>)` for outbound MCP calls. | The decorator wrapping every `@tool` / `@mcp_tool` function before its body runs (OTel trace decorator is the typical home — add the kernel call to the existing decorator, do not create a sibling). | Canonical recipe — most of this skill is written against it. |
| **Python Azure Functions** | The shared `call_mcp(...)` helper used by your Functions graphs. | If you don't have a tool decorator, add a thin wrapper around the dispatcher that loads tool callables from the registry. | Same kernel singleton boots from both the FastAPI app and the Functions worker; `init_governance()` is idempotent. |
| **LangChain / LangGraph (Python)** | The `BaseTool._run` override or a `RunnableLambda` placed in front of the tool node in the graph. | The `@tool` decorator from `langchain_core.tools` — subclass and inject the kernel check, or use `RunnableConfig.callbacks` to intercept `on_tool_start`. | Map LangChain tool names to your `tools.yaml` ids; the `agent_id` comes from the graph node name. |
| **Microsoft Foundry hosted agents** | The Foundry agent SDK's tool-invocation callback / `tools/call` MCP server-side handler. | Same — Foundry routes every tool call through one async handler per agent; wrap that handler. | See `foundry-hosted-agents` for the SDK shape. The kernel + chain still run in your own process (the Foundry runtime invokes your code; the kernel is a peer of your tool implementations). |
| **Semantic Kernel (.NET / Python)** | `Kernel.InvokeAsync` / function-filter middleware. The .NET SDK exposes `IFunctionInvocationFilter` which is the natural home. | Same filter — register once at kernel build time. | For .NET, consult upstream AGT docs for the corresponding NuGet package; the architectural contract (invariants 1–10 above) is unchanged. |
| **Pure MCP server** | The `tools/call` handler in your MCP server implementation. | (One chokepoint only — there is no separate dispatcher.) | Smallest possible footprint: server-side enforcement on the MCP side; clients see DENIES as MCP errors. |

> **Rule of thumb.** If you can list every code path that issues a tool
> call on one hand, you have ≤ 2 chokepoints and you're correct. If you
> can't, find them first — onboarding AGT against an N-chokepoint
> codebase is a refactor, not a wrap.

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python ≥ 3.11** (for the Python binding) | AGT 3.4.x targets 3.11 / 3.12. Other language bindings have their own version floors. |
| **An authority matrix** | A JSON / YAML file declaring who may approve what, at what value band, in what scope. If your workload doesn't have one yet, author it first — AGT compiles *from* it, not to it. A flat list of `{actor_role, action, scope, value_band, approver_role, priority}` rules is enough. |
| **A tool inventory** | A grep for every outbound tool call surfaces the canonical list. Audit before authoring `tools.yaml`. |
| **Per-workflow audit blob storage** | Append-blob or equivalent (Azure Storage append-blob, S3 object-lock, file-system append). Per-workflow, not global. |
| **OpenTelemetry** *(strongly recommended)* | Decisions emit OTel spans on the kernel evaluation; chokepoints attach `agt.decision_id`, `agt.policy_version`, `agt.rule_id` attributes. If your workload doesn't have OTel yet, wire it first (see `foundry-observability`). |
| **Key storage for production** | Azure Key Vault (or equivalent) for Ed25519 private keys. In dev, generated keys land on disk in a gitignored directory. |

---

## What gets created

| Artifact | Path (suggested) | Phase |
|----------|------------------|-------|
| **Governance package** | `<app>/services/governance/` (Python) or equivalent module | 1 |
| **AGT import re-export** | `<app>/services/governance/__init__.py` — the only file that imports `agent_os.*` / `agentmesh.*` | 1 |
| **Kernel** | `<app>/services/governance/kernel.py` — `GovernanceKernel`, `Decision`, `GovernanceDenied`, `kernel()` getter | 1 |
| **Boot hook** | `<app>/services/governance/boot.py` — `init_governance()` called once from app startup | 1 |
| **Tool manifest** | `data/policies/tools.yaml` | 2 |
| **Manifest loader** | `<app>/services/governance/manifest.py` — Pydantic model + cached `load_tools_yaml()` | 2 |
| **Policy compiler** | `<app>/services/governance/policy_compiler.py` — pure `compile_bundle(matrix, tools, agents) -> (PolicyDocument, version_sha)` | 2 |
| **Authority resolver** | Methods on `GovernanceKernel` — `resolve_approver(...)`, `check_authority(...)` | 3 |
| **Chained audit logger** | Mutation to your existing audit logger — `prev_hash` / `entry_hash` computation per workflow | 4 |
| **Verify endpoint** | `GET /api/governance/verify/{workflow_id}` returning `VerifyReport` | 4 |
| **Agent registry** | `<app>/shared/agents.py` — frozen dataclass + `AGENTS: dict[str, AgentRegistryEntry]` | 5 |
| **Identity store** | `<app>/services/governance/identity.py` — dev-mode keypair gen + prod-mode Key Vault load | 5 |
| **JWS signing** | `GovernanceKernel.sign_action(...)` + `verify_jws(...)` | 5 |
| **Kill switch store** | Methods on your state store — `add_kill`, `remove_kill`, `is_killed`, `list_kills` with TTL | 7 |
| **Kill switch routes** | `POST/DELETE/GET /api/governance/kill` | 7 |
| **CI workflow** | `.github/workflows/agt-governance.yml` — `agt mcp-scan` + `agt lint-policy` + `agt verify --strict` + `agt discover` | 8 |
| **Evidence aggregator** | A step that merges the four AGT JSON reports into one `agt-evidence.json` artifact | 8 |

---

## The eight-phase recipe

Phases are atomic. Each one ships green; existing tests stay passing.
The kernel runs **log-only** through Phase 5 so behavior is unchanged
while the chain matures; Phase 6 flips the enforce switch.

### Phase 1 — Bootstrap: kernel skeleton, smoke test

**Goal.** Get the AGT package installed and a no-op kernel constructed
at app startup. No call sites changed. Phase ends with `agt doctor` and
`agt verify` running green against an empty workspace.

1. **Pin the dependency.** Add `agent-governance-toolkit[full]>=3.4,<3.5`
   to your project manifest (`pyproject.toml`, `requirements.txt`,
   `csproj`, etc.). Pin to a minor band — AGT is Public Preview and
   patch releases happen often; bumping a minor is a deliberate act.
2. **Verify the AGT surface.** Confirm every symbol you intend to import
   is actually present in the installed version:
   ```bash
   .venv/bin/python -c "from agent_os.policies import PolicyEvaluator, PolicyDocument, PolicyRule, PolicyCondition, PolicyAction, PolicyOperator, PolicyDefaults; print('ok')"
   ```
   If anything is missing, halt — do **not** write a shim layer. AGT
   3.4.x is the floor for this recipe; older versions had different
   import paths.
3. **Create the package + re-export.** One file
   (`<app>/services/governance/__init__.py`) re-exports `Decision`,
   `GovernanceDenied`, `kernel`. Every other file in the codebase
   imports from there, never from `agent_os.*` directly.
4. **Author the kernel skeleton.** A `GovernanceKernel` class whose
   `evaluate_tool_call(actor, tool, args, workflow_id) -> Decision`
   returns `Decision(allowed=True, enforcement_mode="log_only", ...)`
   for everything. No policy loaded yet — this phase is wiring only.
5. **Boot hook.** `init_governance()` constructs the kernel once and
   logs `governance: kernel up, version=<agt-version>, git_sha=<sha>`.
   Idempotent — second call returns the existing instance. Call it from
   every app entry point (web app startup, worker startup, CLI entry).
6. **CLI smoke targets.**
   ```makefile
   agt-doctor:
   	.venv/bin/agt doctor
   agt-verify:
   	.venv/bin/agt verify
   ```
   Both should produce non-error output against an empty workspace.

**Exit criteria.** Existing tests still green. The kernel is importable
and instantiated at boot. `agt doctor` passes.

---

### Phase 2 — Tool manifest, policy compiler, log-only kernel at the chokepoints

**Goal.** Authour `tools.yaml`. Compile `(matrix, tools.yaml)` into an
AGT YAML `PolicyDocument` at boot. Wire the kernel into both
chokepoints in **log-only** mode — every call produces a `decision_id`
that lands on the audit entry; nothing is denied.

1. **Audit every tool call site.**
   ```bash
   # Outbound MCP / HTTP tool calls
   rg 'httpx\.(get|post).*mcp/call|httpx\.(get|post).*:41[0-9]{2}'
   # In-process tool decorators
   rg '@tool\b|@mcp_tool\b|@traced_tool\b'
   ```
   The union is your tool inventory. Cross-check against every
   subdirectory that ships tools (e.g. `mcp_tools/`, `tools/`,
   `skills/`). Every entry gets a row in `tools.yaml`.
2. **Author `data/policies/tools.yaml`.** Schema:
   ```yaml
   - id: <namespace>.<verb>_<noun>     # e.g. concur.submit_decision
     reversible: false                  # writes / submits / sends / cancels / deletes / creates
     requires_capability: <capability> | null
     requires_authority: true | false
     value_field: <json-path-into-args> | null   # e.g. claim.amount
     scope_function: <function-name>    # e.g. expense_approval
     description: <one-liner>
   ```
   **Reversibility convention** (non-negotiable):
   - `*.write_*`, `*.submit_*`, `*.send_*`, `*.cancel_*`, `*.delete_*`,
     `*.create_*`, `*.update_*` → `reversible: false`.
   - `*.list_*`, `*.get_*`, `*.search_*`, `*.lookup_*`, `*.query_*`,
     `*.read_*` → `reversible: true`.
   Reversibility is declared **only** in `tools.yaml`; agent SKILL.md
   prose or persona files MUST NOT carry duplicate flags.
3. **Manifest loader.** A Pydantic `ToolManifestEntry` and a cached
   `load_tools_yaml(path) -> dict[str, ToolManifestEntry]`. Caches at
   module load; raises with the offending `id` on schema mismatch.
4. **Policy compiler.** A pure function
   `compile_bundle(matrix, tools, agents={}) -> (PolicyDocument, sha256_hex)`.
   The sha256 is computed from the canonicalised YAML serialisation
   (sorted keys, fixed key order on rules, no timestamps) and is your
   `policy_version`. Same inputs → byte-identical YAML output → identical
   hash. This is the **deterministic** half of "deterministic, sub-ms"
   — if your compiler isn't pure, every reboot is a policy drift.
5. **Golden-file tests.** Snapshot the compiled YAML, snapshot the
   version hash, and assert byte-equality on every CI run. The compiler
   is the single highest-leverage piece of code in this whole recipe;
   it deserves rigorous tests.
6. **Wire the chokepoints (log-only).** At each of your two
   chokepoints, immediately before the dispatch/network hop:
   ```python
   from <app>.services.governance import kernel
   decision = kernel().evaluate_tool_call(
       actor=current_agent_id(),
       tool=tool_id,
       args=args,
       workflow_id=current_workflow_id(),
   )
   # Persist decision.decision_id on the existing tool-call event.
   # In log-only mode, do NOT raise on allowed=False — observe only.
   ```
   The `current_agent_id()` source depends on your runtime — for an OTel
   span attribute, pull `actor = span.attributes["app.agent.label"]`;
   for a graph executor, pass it in explicitly.

**Exit criteria.** Every tool call produces a decision. The audit
ledger entries carry `decision_id`. Existing tests stay green
(nothing is denied yet).

---

### Phase 3 — Fold the authority resolver into the kernel

**Goal.** Replace any out-of-process authority MCP / authority service
calls with an in-process kernel resolution against the same compiled
bundle. The external service stays in-tree as a fallback (engagement-POC
swap-in seam) but is no longer on the default startup path.

1. **Add `GovernanceKernel.resolve_approver(...)` and `check_authority(...)`.**
   Same return shapes your authority service uses today. Implementation
   walks the compiled `PolicyDocument` for matrix-derived rules with
   first-match semantics.
2. **Parity test.** For every canonical resolution your matrix covers
   (one per scope_function is the minimum), assert
   `kernel.resolve_approver(...)` returns byte-identical fields to the
   out-of-process service. Skip behind an env var
   (`AUTHORITY_MCP_LIVE=1`) so CI doesn't depend on the external
   process being up; nightly CI spins it up to run the parity test
   once.
3. **Switch the caller.** Modify the authority module to prefer the
   in-process kernel; fall back to HTTP only when `AUTHORITY_MCP_URL`
   is set in the environment. The OTel attributes the wrapper already
   emits (`app.authority.*`) are preserved; add a new
   `app.authority.backend = "in_process" | "http"` so dashboards
   can confirm the switch.
4. **Avoid recursion.** The chokepoint decorator will call the kernel
   recursively when it wraps the authority resolver itself. The kernel
   detects `tool == "<authority-namespace>.resolve_approver"` and
   short-circuits to `allowed=True` to avoid an infinite loop.
5. **Remove from default startup.** Update your boot script
   (`docker-compose.yml`, `boot-demo.sh`, etc.) to drop the external
   authority service from the default chain. Add an explicit
   `--with-authority-mock` flag for parity testing.

**Exit criteria.** Every authority resolution carries a `decision_id`
from the same kernel as tool calls. Existing persona / approval tests
stay green.

---

### Phase 4 — Hash-chained audit ledger + verify endpoint

**Goal.** Turn the action ledger into a per-workflow hash chain. Add an
endpoint that re-walks any chain and reports its integrity.

1. **Extend the ledger entry shape.** Add optional fields:
   `prev_hash: str | None`, `entry_hash: str | None`,
   `actor_jws: str | None`, `decision_id: str | None`,
   `policy_version: str | None`,
   `enforcement_mode: Literal["log_only", "enforce"] | None`. All
   optional with `None` default — back-compat with every existing test
   site that constructs entries.
2. **Per-workflow lock + chain.** In your audit logger's `log()`:
   ```python
   async with _per_workflow_lock(workflow_id):
       prev = await _tail_hash(workflow_id)        # "0" * 64 if first
       entry["prev_hash"] = prev
       entry["entry_hash"] = sha256(_canonicalise(entry)).hexdigest()
       await _append_blob(entry)
       _cache_tail(workflow_id, entry["entry_hash"])
   ```
   The lock is **per workflow**, never global — parallel writes across
   different workflows must not contend. Canonicalisation: sorted keys,
   compact JSON, UTF-8, no whitespace.
3. **`verify_chain(workflow_id) -> VerifyReport`.** Re-reads the blob,
   walks entries, validates `prev_hash[i] == entry_hash[i-1]`, returns
   `VerifyReport(chain_intact, broken_at, total_entries, ...)`.
4. **`GET /api/governance/verify/{workflow_id}`.** Operator-auth.
   Returns `VerifyReport` as JSON. The front end renders an "Evidence"
   chip beside any existing Authority / approval chip on the workflow
   detail page.
5. **Backfill script.** A one-shot tool that walks existing audit
   blobs and rewrites entries with `prev_hash` / `entry_hash` so
   historical workflows show as "intact" too. **Idempotent** —
   re-running is a no-op. Atomic write (`.bak` + `os.replace`) per
   blob. Use the *same* canonicalisation as `log()` — any drift here
   is a silent tamper signal forever.
6. **Tamper test.** Log 100 entries across N workflows in parallel,
   mutate one entry's body on disk, re-verify, assert `broken_at`
   points at the tampered entry. This test is the contract.

**Exit criteria.** Every new ledger entry is chained. The verify
endpoint returns `chain_intact: true` for every healthy workflow.

---

### Phase 5 — Per-agent identities + JWS-signed receipts

**Goal.** Enumerate every machine agent that calls tools in a registry.
Generate Ed25519 keypairs per agent (dev) or load from Key Vault
(prod). Sign every ledger entry with the actor's private key. The
verify endpoint now validates signatures, not just hashes.

1. **Audit which agents exist.** Grep your codebase for the field
   that identifies "who is acting" on a tool call — typically an OTel
   span attribute like `app.agent.label`, or an explicit
   `agent_id=` argument on a graph executor. The union is your agent
   roster. Document the audit at the top of `agents.py` as a comment.
2. **Author the registry.** `<app>/shared/agents.py`:
   ```python
   @dataclass(frozen=True)
   class AgentRegistryEntry:
       agent_id: str
       allowed_tools: tuple[str, ...]
       max_value_gbp: float | None
       reversible_only: bool
       scope_function: str
       description: str

   AGENTS: dict[str, AgentRegistryEntry] = {
       "intake-normaliser": AgentRegistryEntry(
           agent_id="intake-normaliser",
           allowed_tools=("doc.parse", "doc.classify"),
           max_value_gbp=None,
           reversible_only=True,
           scope_function="intake",
           description="Normalises raw intake payloads...",
       ),
       # ...
   }
   ```
   Helpers: `get(agent_id)`, `by_function(scope)`, `all_agent_ids()`.
3. **CI guardrails.** A test asserts: every `agent_id` appearing in any
   ledger entry (gathered from test fixtures) is in `AGENTS`; every
   tool listed in any agent's `allowed_tools` is in `tools.yaml`. Drift
   between the three files (matrix / tools / agents) is the most
   common bug in this whole skill.
4. **Identity store.** `<app>/services/governance/identity.py`:
   ```python
   class AgentIdentityStore:
       def __init__(self, dev_mode: bool, key_dir: Path | None,
                    keyvault_url: str | None): ...
       def private_key(self, agent_id: str) -> Ed25519PrivateKey: ...
       def public_key(self, agent_id: str) -> Ed25519PublicKey: ...
   ```
   - **Dev mode** (default, gated by `AGT_DEV_KEYS=1`): generate keypair
     at first use; persist to `<dev-key-dir>/<agent_id>.{pem,pub}`.
     Add `<dev-key-dir>/` to `.gitignore` — these are not committed.
   - **Prod mode**: load public keys from a committed directory
     (`data/governance/agent-pubkeys/<agent_id>.pub`), load private
     keys from a Key Vault secret `agt-<agent_id>-key` via
     `DefaultAzureCredential`.
5. **Sign every action.**
   `kernel().sign_action(agent_id, action, payload) -> jws_string`
   returns JWS Compact Serialization, `alg=EdDSA`, `kid=<agent_id>`,
   payload carries `iss=<agent_id>, action, payload_hash, iat`. Audit
   logger writes the result to `entry["actor_jws"]` **before**
   `entry_hash` is computed — the signature is part of the hashed
   payload.
6. **Verify signatures.** Extend `verify_chain` to also validate every
   `actor_jws`. `VerifyReport` grows `signatures_valid: bool` and
   `bad_signatures_at: list[int]`. The front-end Evidence chip turns
   red on any failure.
7. **Document key rotation.** A short
   `data/governance/README.md` describing the prod rotation
   procedure: rotate the Key Vault secret, bump an
   `agt-keys-rotation` annotation in `agents.py`, redeploy. The
   public key file under `data/governance/agent-pubkeys/` is updated
   in the same commit that rotates.

**Exit criteria.** Every ledger entry carries a verifiable JWS.
`agt verify` against a workflow blob reports
`chain_intact: yes, signatures_valid: N/N`.

---

### Phase 6 — Flip the enforce switch

**Goal.** Change the kernel default from `log_only` to `enforce` when
`AGT_ENFORCE=1`. Add the reversibility gate and capability check as
real DENYs. Every existing happy-path test must still pass — the
policy bundle must be permissive enough to allow every *legitimate*
call.

1. **Author the production policy bundle.** Hand-author
   `data/policies/agents.policy.yaml` with three rule classes:
   - **Per-agent allowed_tools.** One rule per agent:
     `condition: actor IN [<agent_id>] AND tool IN [<allowed_tools>]`
     → `action: ALLOW`.
   - **Reversibility gate.** Global high-priority:
     `condition: tool.reversible == false AND priority < ENFORCE_FLOOR`
     → `action: DENY`. Only a closed HITL ALLOW with
     `priority >= ENFORCE_FLOOR` breaks through.
   - **Authority threshold.** Auto-derived from the matrix by
     `policy_compiler` (no hand-edits here).
   Keep hand-authored rules in a separate file from matrix-derived
   rules so reviewers can tell them apart.
2. **`AGT_ENFORCE=1` in the default profile.** Add to your committed
   `local.settings.example.json` / `.env.example` / equivalent. The
   `AGT_ENFORCE=0` escape hatch exists but is **emergency-only** — not
   wired into any committed profile script.
3. **Raise on DENY in enforce mode.**
   ```python
   def evaluate_tool_call(self, ...) -> Decision:
       decision = self._evaluate(...)
       if self._mode == "enforce" and not decision.allowed:
           raise GovernanceDenied(decision)
       return decision
   ```
   Both chokepoints propagate the exception. Your existing
   graph-executor / workflow error handling renders it as a workflow
   exception (your "narrative exception" path, whatever you call it).
4. **Test coverage.** `tests/.../test_enforce_mode.py`: spin up the
   kernel in enforce, attempt a tool call (a) outside the agent's
   `allowed_tools`, (b) on an irreversible tool without a closed-HITL
   ALLOW, (c) above the agent's `max_value_gbp`, (d) from an unknown
   `agent_id` — assert `GovernanceDenied` and assert a `policy.deny`
   ledger entry is written.
5. **Triage false-positive denies.** Run your full smoke suite +
   autonomous loop with `AGT_ENFORCE=1`. Any deny that fires on a
   legitimate call indicates either a missing entry in
   `agents.py.allowed_tools` or a missing rule in the matrix. **Fix at
   the source.** Never by weakening the kernel.

**Exit criteria.** Existing tests + smoke loop pass with
`AGT_ENFORCE=1`. The kernel raises on illegitimate calls. The
narrative exception path renders denies correctly.

---

### Phase 7 — Operator surface: kill switch + verify chip

**Goal.** Operator can pause a misbehaving agent or block a tool
fleet-wide in sub-second, no redeploy. The workflow detail page
surfaces the verify result inline.

1. **Kill switch store.** Add to your existing state store
   (Redis / in-memory dict / Cosmos — whatever you have):
   ```python
   _kill_switches: dict[tuple[str, str], KillSwitch]
   # keyed by (agent_id, tool); "*" is the wildcard
   ```
   Methods: `add_kill`, `remove_kill`, `is_killed(agent_id, tool) -> KillSwitch | None`,
   `list_kills()`. `KillSwitch` carries `created_at`, `expires_at`,
   `reason`, `created_by`. Lazy expiry on read — no background sweeper
   required.
2. **Kernel consults the store.** In `evaluate_tool_call`, check
   `state_store.is_killed(actor, tool)` **before** policy evaluation.
   Kill matches return `Decision(allowed=False, rule_id=f"kill:{id}", reason=...)`.
3. **Routes.** All operator-auth:
   - `POST /api/governance/kill {agent_id, tool, ttl_seconds, reason}`
   - `DELETE /api/governance/kill/{kill_id}`
   - `GET /api/governance/kill`
   Wildcard semantics: `("*", "concur.submit_decision")` blocks the
   tool fleet-wide; `("finance-agent", "*")` pauses the agent across
   every tool.
4. **Front-end (optional but recommended).** A collapsible "Kill
   Switch" panel next to the agent list, showing active kills with
   countdown timers. Two per-row buttons: "Pause this agent (30 min)"
   and "Block this tool fleet-wide (30 min)". One inline chip on the
   workflow detail page next to any existing approval chip:
   `chain ✓ · signatures N/N · policy_version=<sha[:12]>`.
5. **e2e test.** Open a workflow, pause its agent, observe the next
   spawned workflow's call denied, observe the narrative-exception
   path render correctly.

**Exit criteria.** A kill switch toggle takes effect on the very next
tool call, no redeploy. The Evidence chip renders on every workflow.

---

### Phase 8 — CI ring + evidence aggregation

**Goal.** Lock in the discipline. Every PR runs the four AGT CLI gates;
their reports merge into one `agt-evidence.json` artifact that the
business stakeholder can read as "OWASP Agentic Top 10 — 10/10
covered".

1. **GitHub Actions workflow.** `.github/workflows/agt-governance.yml`,
   runs on `pull_request` + `push to main` + nightly cron:
   ```yaml
   jobs:
     agt-mcp-scan:
       # scans tool-server source for poisoned tool descriptions
       run: .venv/bin/agt mcp-scan <tool-server-dirs>
     agt-lint-policy:
       # detects dead rules, conflicting rules, unbound capabilities
       run: .venv/bin/agt lint-policy data/policies/
     agt-verify:
       # walks a smoke-spun fixture workflow's audit blob
       run: .venv/bin/agt verify --strict <fixture-blob>
     agt-discover:
       # finds unregistered agents
       run: .venv/bin/agt discover --root .
   ```
   Each job uploads its JSON output as a build artifact.
2. **Evidence merge.** A final job aggregates the four JSON outputs
   into `agt-evidence.json` with a stable shape:
   ```json
   {
     "policy_version": "<sha256>",
     "mcp_scan": { "asi_01_through_05": { ... } },
     "policy_lint": { "asi_06_07": { ... } },
     "chain_verify": { "asi_08": { ... } },
     "discover": { "asi_09_10": { ... } }
   }
   ```
   On `main`, publish to a stable URL (storage blob / static site) so
   stakeholders can consume it without GitHub auth.
3. **Pre-commit hook (opt-in).** `.github/hooks/pre-commit-agt` running
   `agt lint-policy data/policies/` against the working tree. Document
   the install step in your contributor docs.
4. **Red-team scan.** Run `agt red-team scan <persona-prose-dirs>` once
   per release. The goal is to detect any agent / persona prose whose
   decision policy can be jailbroken into changing its threshold via
   crafted context inputs. Review hits manually; add hardening notes
   inline.

**Exit criteria.** A PR that introduces a poisoned tool, a dead policy
rule, an unregistered agent, or a broken chain fails CI. The merged
`agt-evidence.json` is consumable by downstream cards.

---

## Verification: what `agt verify` actually proves

The whole point of this skill is that one CLI command, run by a
stakeholder with **no tenant access**, produces a deterministic proof:

```bash
agt verify --evidence <workflow-audit-blob-url> --pubkeys <pubkey-dir>
```

The command validates, in order:

1. **Chain integrity.** Every `prev_hash[i] == entry_hash[i-1]`. Any
   tamper anywhere in the chain shows as `broken_at: <index>`.
2. **Signatures.** Every `actor_jws` validates against the registered
   pubkey for that `agent_id`. Tampered payloads, wrong-key signatures,
   and missing pubkeys all surface.
3. **Decisions resolvable.** Every `decision_id` maps to a rule in the
   policy bundle whose hash matches `policy_version` on that entry.
   Decisions made against a now-deleted rule still verify because the
   bundle is reproduced by hash, not by name.
4. **Reversibility honoured.** Every entry that records an
   `enforcement_mode: enforce` DENY for an irreversible tool has a
   matching ALLOW entry preceded by a closed-HITL gate, OR no
   subsequent ALLOW (the DENY blocked execution).

The output is a one-page report. Pin it to the release notes.

---

## Anti-patterns / gotchas

| Pattern | Why it bites |
|--------|-------------|
| **Three or more chokepoints** | "Just one more wrapper for this new SDK" — and now every new tool integration is a five-place audit. Stop and consolidate before adding a third. |
| **`try / except: pass` around `kernel().evaluate_tool_call(...)`** | Silent ALLOW. The kernel is **only** safe because exceptions bubble. Fail closed is the security model. |
| **Committing the compiled YAML bundle** | Reviewers will hand-edit it ("just one rule") and the next compile silently overwrites their change. The bundle is generated; the inputs are the source of truth. (You may commit it for audit, but compile-and-diff in CI must enforce equality.) |
| **Single global chain lock** | Every workflow blocks every other. Per-workflow locks are PAT-003 for a reason. |
| **Per-call kernel construction** | Defeats the in-memory decision cache; every call re-parses the bundle. The kernel is a singleton. |
| **Reversibility flags on agent SKILL.md** | Two sources of truth. `tools.yaml` is the only place. CI greps SKILL.md for reversibility prose and rejects. |
| **`AGT_ENFORCE=0` in a committed profile script** | Smuggles enforce-off into the demo path. Only emergency runbooks set it; never a profile. |
| **Logging the private key path / contents** | Strip key paths from any structured log. `agt verify` should never need a private key. |
| **Skipping the parity test in Phase 3** | The most common silent regression. The in-process resolver and the external mock diverge on first-match semantics over time; nightly parity catches it. |
| **Mutable canonicalisation in `entry_hash`** | If the JSON serialisation isn't byte-stable (e.g. Python's default `json.dumps` without `sort_keys`), the same entry hashes differently on different machines. Pin canonicalisation in a single helper and test it on every supported platform. |

---

## Versioning

AGT 3.4.x is in **Public Preview** at the time of writing. Breaking
changes are possible before GA. Three discipline rules:

1. **Pin to a minor band** (`>=3.4,<3.5`). Minor bumps are deliberate
   acts, not Dependabot auto-merges.
2. **Keep the import surface narrow.** The
   `<app>/services/governance/__init__.py` re-export is the *only*
   place that imports `agent_os.*`, `agentmesh.*`, etc. A breaking
   change becomes a single-file diff.
3. **Re-run the Phase 1 surface check on every bump.** Before changing
   the pin, run the `python -c "from agent_os.policies import ..."`
   smoke from § Phase 1 step 2 against the new version. If any import
   path moves, fix the re-export — don't shim individual call sites.

---

## References

- **Upstream:** [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit) (MIT, Public Preview).
- **Bundle format:** AGT YAML (the native serialisation of
  `agent_os.policies.PolicyDocument`). Cedar / Rego are alternative
  policy DSLs supported by the broader ecosystem; AGT YAML round-trips
  cleanest with a matrix-shaped authority store.
- **JWS spec:** RFC 7515 Compact Serialization, `alg=EdDSA` per
  RFC 8037.
- **OWASP Agentic Top 10:** the four CI gates (`agt mcp-scan`,
  `agt lint-policy`, `agt verify --strict`, `agt discover`) cover ASI-01
  through ASI-10 with one report per category. Map your `agt-evidence.json`
  shape to the ASI rows in your downstream consumer card.
- **Related skills in this catalog:**
  - `citadel-spoke-onboarding` — APIM-fronted central AI gateway
    governance. Complements AGT (gateway tier vs. application tier);
    use both for defence in depth.
  - `foundry-observability` — the OTel + App Insights wiring that
    every AGT decision span flows through. Land it first.
  - `foundry-hosted-agents` — if your target runtime is Foundry hosted
    agents, the SDK shape is documented there; this skill's invariants
    still apply.
