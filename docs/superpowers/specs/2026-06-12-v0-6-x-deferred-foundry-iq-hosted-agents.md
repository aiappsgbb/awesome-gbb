# v0.6.x Deferred — foundry-iq PE-posture audit + foundry-hosted-agents thread retention

> **Status:** Deferred from v0.6.0 critical path. Light spec only — no
> implementation plan in this document. Promote to a full plan when v0.6.0
> ships and v0.6.x cycle opens.
>
> **Parent spec:** [`docs/superpowers/specs/2026-06-12-v0-6-0-critical-path-design.md`](2026-06-12-v0-6-0-critical-path-design.md) §4.6.

## Why deferred

Per the threadlight-skills v0.6.0 tracker
([aiappsgbb/threadlight-skills#35](https://github.com/aiappsgbb/threadlight-skills/issues/35))
both issues are **Order-8 / "Pick up opportunistically"**:

- They flip MDL-010 (PE-posture) and MDL-011 (thread retention) from
  `kind: manual` to `kind: sibling-skill` in
  `threadlight-production-ready/maintenance-decision-log.yaml` — useful
  flips, but the manual rows are already documented and customer-acceptable.
- Neither is on the gating path to "credible customer-pilot ready". The five
  v0.6.0 slices (extensions sweep, citadel-spoke probe, rbac-audit,
  alert-baseline, backup+diagnostics) cover the must-flip set.
- Both are small extensions to existing skills (foundry-iq, foundry-hosted-agents)
  with no plugin-level changes — easy to ship as patch releases in v0.6.1 or
  v0.6.2 once v0.6.0 lands without disturbing the critical path.

Promoting them to v0.6.0 would force a sixth slice (or bloat slice 1) for
marginal threadlight gain. Holding them keeps slice 1's extension sweep
focused on the three highest-ROI flips (#245, #247, #248) per the tracker's
"hidden multipliers > new skill builds" signal.

## Item 1 — #269 foundry-iq PE-posture audit method

**Host skill:** `skills/foundry-iq/` (v1.3.2 → v1.4.0 MINOR)
**Threadlight callback:** MDL-010 — verify private-endpoint posture matches
declared topology for hub/spoke deployments.

### Contract

Importable Python module + CLI shim:

- `skills/foundry-iq/scripts/pe_posture_audit.py`
  - Exposes `audit_pe_posture(*, subscription_id, resource_group, expected_topology="hub-spoke"|"isolated"|"public") -> dict`
  - Returns the standard NEW-skill envelope (see umbrella spec §3.3):
    ```json
    {
      "skill": "foundry-iq",
      "skill_version": "1.4.0",
      "probed_at": "<ISO-8601>",
      "inputs": {"subscription_id": "...", "resource_group": "...", "expected_topology": "hub-spoke"},
      "result": {
        "pe_count": 3,
        "pe_inventory": [{"name": "...", "service": "cognitiveservices", "subnet": "..."}],
        "vnet_links": [{"private_dns_zone": "...", "linked_vnets": ["..."]}],
        "posture_matches_expectation": true,
        "deviations": []
      },
      "confidence": "high",
      "missing_perms": [],
      "errors": []
    }
    ```
- CLI: `python -m foundry_iq.pe_posture_audit --subscription-id <sub> --resource-group <rg> --expected-topology hub-spoke`
  emits the envelope to stdout (one JSON object, no preamble).

### How the probe works

1. `az network private-endpoint list -g <rg>` — inventory PEs in the RG.
2. For each PE, resolve the target service (Foundry / KeyVault / Storage / Cog)
   and the subnet ID.
3. `az network private-dns zone list -g <rg>` + `az network private-dns
   link vnet list` — map zones to linked VNets.
4. Compare against `expected_topology`:
   - `hub-spoke`: expect PEs in a spoke RG, zones linked to a hub VNet
   - `isolated`: expect PEs in same RG as workload, zones linked locally
   - `public`: expect zero PEs (deviation if any are present)
5. Populate `deviations` with any mismatch (e.g., zone linked to wrong VNet,
   missing PE for a documented service).
6. `confidence: "low"` if no PEs found AND `expected_topology != "public"`
   (could be probe missing perms OR genuinely no PEs).

### Files when promoted to plan

- Create: `skills/foundry-iq/scripts/__init__.py` (if not already present)
- Create: `skills/foundry-iq/scripts/pe_posture_audit.py`
- Create: `skills/foundry-iq/scripts/requirements.txt` (`azure-identity`, `azure-mgmt-network`, `azure-mgmt-privatedns`)
- Create: `skills/foundry-iq/tests/test_pe_posture_audit.py` (≥5 unit tests covering hub-spoke match, hub-spoke deviation, isolated match, public match, az failure)
- Create: `skills/foundry-iq/test-fixture/consumer_prompt.md` (≤ 8 KB, probe-style, soft-PASS on empty PE inventory — see Pattern 13)
- Modify: `skills/foundry-iq/SKILL.md` — add `## PE-posture audit` section (~60 lines), bump `metadata.version` to `1.4.0`
- Modify: `skills/foundry-iq/references/upstream-pin.md` — bump audit trail, refresh `last_validated`
- Modify: `.github/skill-deps.yml` — register foundry-iq fixture (or confirm registration if already present from prior fixture work)
- Modify: `AGENTS.md` §12.5 — no skill count change (extension, not new skill)

### Risks

- foundry-iq is a wrapper around the Foundry SDK; PE inventory is at the
  Azure RM layer, not the Foundry layer. This means the helper has to load
  TWO different SDK families (`azure-identity` + `azure-mgmt-network` for
  the probe, in addition to whatever the existing skill imports). Confirm
  upstream-pin doesn't need a new `package` row.
- Hub-spoke detection by RG-name pattern is fragile. The helper accepts
  `expected_topology` from the caller rather than inferring — that pushes
  the heuristic out to the consumer (threadlight) where it belongs.

### Commit tag policy

- One commit per task per § "Files when promoted to plan" structure.
- Final commit message includes `[skill-rewrite]` (SKILL.md body touched).
- No `[multi-skill]` (single skill).

## Item 2 — #270 foundry-hosted-agents thread retention reader

**Host skill:** `skills/foundry-hosted-agents/` (v1.11.0 → v1.12.0 MINOR)
**Threadlight callback:** MDL-011 — read agent thread retention windows so
the conversational-memory model is auditable.

### Home decision

**Lives in `foundry-hosted-agents`**, not `foundry-memory`. Rationale:

- Thread CRUD belongs to the hosted-agent client — agents own threads,
  memory consumes them.
- `foundry-memory` is the higher-level "agent memory" SDK wrapper; its
  job is semantic + episodic memory consolidation, not raw thread inventory.
- Cross-reference: add a `DO NOT USE FOR` clause to `foundry-memory`
  description pointing to `foundry-hosted-agents` for thread inventory.

This decision is **default — open question #3** in the umbrella spec §5
asks the human to ratify before promotion.

### Contract

Importable Python module + CLI shim:

- `skills/foundry-hosted-agents/scripts/thread_retention.py`
  - Exposes `read_thread_retention(*, project_endpoint, agent_id=None) -> dict`
  - When `agent_id` is `None`: scans all agents in the project, returns
    per-agent retention summary.
  - When `agent_id` is specified: returns single-agent detail.
  - Returns the standard NEW-skill envelope:
    ```json
    {
      "skill": "foundry-hosted-agents",
      "skill_version": "1.12.0",
      "probed_at": "<ISO-8601>",
      "inputs": {"project_endpoint": "...", "agent_id": null},
      "result": {
        "agents_probed": 3,
        "agents": [
          {
            "agent_id": "asst_...",
            "name": "...",
            "thread_count": 47,
            "retention_policy": "default|custom",
            "retention_days": null,
            "oldest_thread_age_days": 12,
            "newest_thread_age_days": 0
          }
        ]
      },
      "confidence": "high",
      "missing_perms": [],
      "errors": []
    }
    ```
- CLI: `python -m foundry_hosted_agents.thread_retention --project-endpoint <url> [--agent-id <id>]`
  emits the envelope to stdout (one JSON object).

### How the probe works

1. Build `AIProjectClient(project_endpoint, DefaultAzureCredential())`.
2. If `agent_id` is `None`: `client.agents.list_agents()` → iterate.
3. For each agent: `client.agents.threads.list(agent_id=...)` → count + age.
4. Read `agent.metadata.get("retention_days")` if hosted agents support
   a custom retention metadata key (TBD when promoted — confirm against
   azure-ai-agents SDK at promotion time; if not supported, leave the
   field `null` with note "default platform retention").
5. Per-agent counts + age summary into envelope.

### Files when promoted to plan

- Create: `skills/foundry-hosted-agents/scripts/thread_retention.py`
- Create: `skills/foundry-hosted-agents/scripts/__init__.py` (if absent)
- Create: `skills/foundry-hosted-agents/scripts/requirements.txt` (`azure-identity`, `azure-ai-projects`, `azure-ai-agents`)
- Create: `skills/foundry-hosted-agents/tests/test_thread_retention.py` (≥5 unit tests: single-agent path, all-agents path, empty project, SDK auth failure, missing metadata key)
- Modify: `skills/foundry-hosted-agents/SKILL.md` — add `## Thread retention inspection` section (~80 lines), bump `metadata.version` to `1.12.0`
- Modify: `skills/foundry-hosted-agents/references/upstream-pin.md` — bump audit trail
- Modify: `skills/foundry-memory/SKILL.md` — add `DO NOT USE FOR` cross-ref (thread inventory belongs to hosted-agents), bump `metadata.version` PATCH (e.g. 1.2.1 → 1.2.2)
- Modify: `AGENTS.md` §12.5 — no skill count change

### Risks

- Test-fixture cost: hosted-agents already has the heaviest fixture in the
  catalog (~226K tokens per agent message, see § 9.7 Pattern 19 addendum
  v2). Adding thread-retention inventory to that fixture would push it past
  the 545K TPM ceiling. **Mitigation:** ship the retention probe as its own
  Bash-tool-driven smoke in the EXISTING fixture, NOT a new fixture. Re-use
  the agent the fixture already provisions, query its threads, validate
  envelope shape, write marker. Adds ~5K tokens, not a new full fixture.
- SDK retention-days metadata key may not exist in azure-ai-agents. If
  promoted and the key isn't supported, ship with `retention_days: null`
  + note in SKILL.md "platform default — no per-agent override surface yet".

### Commit tag policy

- One commit per task.
- Final commit message includes `[skill-rewrite]` (SKILL.md body touched).
- Add `[multi-skill]` (foundry-memory cross-ref bump).

## When to promote these from spec to plan

| Trigger | Action |
|---|---|
| v0.6.0 ships (all 5 slices merged + threadlight flips) | Open a `v0.6.x` planning session, promote this spec to two plan files in `docs/superpowers/plans/` |
| Customer pilot requests PE-posture or thread-retention auditing explicitly | Promote immediately, jump the v0.6.x queue |
| Six months pass without promotion | Re-evaluate: customer demand may have moved on, retire spec or rebuild from current SDK surfaces |

## Cross-references

- Umbrella v0.6.0 spec: [`2026-06-12-v0-6-0-critical-path-design.md`](2026-06-12-v0-6-0-critical-path-design.md) §4.6 (deferred items index)
- Threadlight v0.6.0 tracker: [aiappsgbb/threadlight-skills#35](https://github.com/aiappsgbb/threadlight-skills/issues/35)
- Upstream issues:
  - #269 — foundry-iq PE-posture audit method
  - #270 — foundry-hosted-agents thread retention reader
- Sibling-skills-map.md (threadlight): MDL-010 and MDL-011 rows
- Repo conventions: `AGENTS.md` §5 (SemVer), §2.6 (azd default), §9.7 Pattern 19 addendum v2 (TPM ceiling)
