# `foundry-agt` — deep audit trail

| Field | Value |
|------|------|
| Skill | `foundry-agt` |
| SKILL.md version at audit | `1.0.5` |
| Audit date | 2026-05-31 |
| Audit type | First systematic deep audit (post Phase 4 / PR #187 infra) |
| Scope | All 21 bug classes from Appendix A of [`2026-05-30-deep-audit-and-testing-rethink-design.md`](../superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md#L381) |
| Auditor | Copilot Sonnet 4.5 (autopilot), reviewed by maintainer |
| Companion PR | `foundry-agt: add E2E fixture + deep audit trail` |
| Predecessor PR | #187 (Phase 4 infra plumbing) |

This audit was performed as part of the **1-PR-per-skill cadence**
shake-down after PR #187 merged. It is the cheapest possible E2E
shake-down in the catalog: `foundry-agt` is **in-process MAF
middleware** — no ACA, no model deploy, no Azure dataplane — so the
audit can focus on prose / API / version correctness without
deployment-shape concerns.

Findings are organised by the 21 bug classes from the design spec
appendix. Each finding has a one-line disposition: **HIT** (real
issue, action required), **none observed** (audit ran the check,
found nothing), or **N/A** (the bug class does not apply to this
skill's surface — explained).

---

## Findings

### C1 — Hardcoded secrets / GUIDs / customer identifiers

**Status:** none observed.

Scanned SKILL.md for GUID pattern (`[0-9a-f]{8}-...-{12}`) — zero
hits. No customer names, no real subscription IDs, no real tenant
IDs, no real resource IDs. The skill's examples use placeholders
(`<sub-id>`, `<rg>`, `Contoso`). All forbidden-string CI gates
(§ 2.1 of AGENTS.md) pass.

### C2 — Bicep / Azure provisioning shape drift

**Status:** N/A.

`foundry-agt` is in-process middleware with an optional ACA Sidecar
variant. The Sidecar Bicep at L320-345 is illustrative (referencing
`mcr.microsoft.com/agentmesh/enforcer:3.6.0` and `azd-service-name`
tag). It does not ship a deployable Bicep file; consumers compose
the policy mount + sidecar into their own `azd-patterns`-based
deployment. There is no `infra/main.bicep` for this skill to
drift against.

### C3 — Tool / CLI install drift (Pattern 15)

**Status:** none observed.

The skill installs `agent-governance-toolkit[full]` and
`agent-framework` via `pip` in the consumer's environment. No
system CLIs are required at runtime. The companion fixture
follows Pattern 15 strictly: workflow already has Python; the
fixture pip-installs Python wheels only. No `apt-get`, no
`curl | bash`, no `aka.ms/install-*-script-*` patterns.

### C4 — OIDC / federated-credential TTL boundary (Pattern 25)

**Status:** N/A.

No Azure dataplane calls, no `azd auth login`, no
`azure/login@v2`-dependent calls in the skill or its fixture. The
fixture's Step 0 `az account show` is show-don't-assert
inventory (Pattern 17), not an authenticated call. There is no
teardown phase — process exit cleans up in-process state.

### C5 — Preview-CLI flag surfaces (Pattern 16)

**Status:** none observed.

`agt` CLI surfaces used in the skill (`agt verify`, `agt doctor`,
`agt red-team`) are GA-stable per the upstream README. The skill
does not document preview azd extensions (`azd ai agent` family)
or `az` preview commands. SKILL.md does not branch on flag
detection ("prefer X if subcommand exists; else Y") — every
example is a single canonical invocation.

### C6 — `azd` ↔ ACA Jobs gap (Pattern 18)

**Status:** N/A.

`foundry-agt` does not deploy ACA Jobs. The optional Sidecar
variant (Path B) is an ACA Service (Container App), where
`azd deploy` works correctly.

### C7 — Foundry SDK shape drift (sync vs async, client constructors)

**Status:** none observed.

The skill does not call `AIProjectClient`, `AgentRunner`,
`FoundryChatClient`, or any other Foundry SDK constructor. Its
integration surface is `agent_framework.Agent(...)` with
`middleware=` kwarg, which is an in-process MAF concern. No
`AsyncDefaultAzureCredential`, no `.aio.` namespace, no `asyncio`
event loop wrangling.

### C8 — Deprecated SDK APIs / removed parameters

**Status:** **HIT — fix-in-PR via commit 3 (`[skill-rewrite]` tag).**

Stability-run-1 against AGT 3.7.0 surfaced a **policy operator
drift** in the canonical reference policy file
`references/policies/default.yaml`. The `cap-message-length` rule
used `operator: length_gt` with `value: 16000` — an operator that
**does not exist** in the AGT 3.7.0 `PolicyOperator` enum. The
canonical enum is defined in
[`agent_os/policies/policy_schema.json`](https://github.com/microsoft/agent-governance-toolkit/blob/main/agent-governance-python/agent-os/src/agent_os/policies/policy_schema.json)
as exactly:

```
["eq", "ne", "gt", "lt", "gte", "lte", "in", "not_in", "matches", "contains"]
```

`length_gt` is not in that set. `PolicyEvaluator._match_condition`
silently skips conditions with unknown operators, so the cap-rule
was a no-op against AGT 3.7.0 — a textbook "valid YAML, dead
policy" failure mode that neither the pin's `validation.script`
nor the prose review caught.

**How the audit caught it:** the fixture's Step 3 attempts to
load `references/policies/default.yaml` via
`PolicyEvaluator.load_policies(...)`. On the GREEN run
[`26745982162` (leg `78821489441`)](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26745982162/job/78821489441)
the agent grep'd the file (run log L418, L425-441), identified
the bogus operator, self-healed the file with the canonical
`operator: matches` + a regex value (run log L468), and proceeded.
The self-heal proved the fix; commit 3 of this PR persists it
in the repo.

**Fix C (now applied to `references/policies/default.yaml`):**

```yaml
- name: cap-message-length
  priority: 10
  condition:
    field: message
    operator: matches
    value: "[\\s\\S]{16001,}"
  action: deny
  message: Message exceeds 16k chars; refusing to forward to model.
```

`[\s\S]` (not `.`) because `_match_condition` calls
`re.search(...)` without `DOTALL` — `.` would not match newlines,
making the cap a hole on multi-line payloads. Verified locally
against `PolicyEvaluator` on 4 inputs (benign greeting → allow ✓,
SQL `DROP TABLE` → deny ✓, 17001-char w/ embedded newline → deny ✓,
100-char → allow ✓).

**Signature evidence (the original C8 lower-bound check, still
clean):** The fixture's Step 3 prints `inspect.signature()` for
the six load-bearing call sites: `create_governance_middleware`,
`PolicyEvaluator.evaluate`, `AuditLog.log`,
`AuditLog.export_cloudevents`, `Agent.__init__`,
`GovernancePolicyMiddleware.__init__`. The first GREEN CI run on
this PR (cited in v1.0.6 changelog) is the evidence that:

- `create_governance_middleware(policy_directory=..., enable_rogue_detection=...)` accepts those kwargs against AGT 3.7.0
- `PolicyEvaluator.evaluate(context)` accepts a context dict on 3.7.0
- `AuditLog.log(event_type=..., agent_id=..., action=..., payload=...)` accepts those kwargs on 3.7.0
- `Agent.__init__` exposes a `middleware` parameter on MAF 1.7.0

If any signature surface drifts on a future bump, the fixture
emits a `SMOKE_RESULT=FAIL` with the exact import or signature
that broke, and the new failure is added to this finding.

### C9 — RBAC propagation race (Pattern 7)

**Status:** N/A.

No Azure resource is created by the skill or its fixture. No
RBAC is involved.

### C10 — Region capacity / SKU quirk (Pattern 21)

**Status:** N/A.

No model deployment is required. The fixture exercises the
policy middleware purely in-process; the middleware fires
**before** model dispatch on a denied capability, which is the
cheapest possible verification path.

### C11 — Cross-skill reference drift

**Status:** **observed, no action.**

SKILL.md `See Also` at L457-475 lists 9 cross-references:

| # | Target | Path | Resolved? |
|---|---|---|---|
| 1 | `foundry-hosted-agents` | local | ✅ |
| 2 | `threadlight-deploy` | external (`aiappsgbb/threadlight-skills`) | ✅ syntax-valid, not curl-verified in this audit |
| 3 | `citadel-spoke-onboarding` | local | ✅ |
| 4 | `foundry-mcp-aca` | local | ✅ |
| 5 | `foundry-toolbox` | local | ✅ |
| 6 | `foundry-evals` | local | ✅ |
| 7 | `foundry-observability` | local | ✅ |
| 8 | `azd-patterns` | local | ✅ |
| 9 | `threadlight-safe-check` | external (`aiappsgbb/threadlight-skills`) | ✅ syntax-valid, not curl-verified in this audit |

All 7 local refs target existing `skills/<name>/SKILL.md` files in
this repo. Both external refs target the separate
`aiappsgbb/threadlight-skills` repo per AGENTS.md § 2.5 — these
are intentional cross-repo references and not stale.

**Backlinks-from-consumers** (other skills' `See Also` blocks
pointing back into `foundry-agt`) are explicitly documented as
deferred at SKILL.md L477-479 ("kept out of this PR for
reviewability") — this is a pre-existing follow-up, not a new
gap. No action required in this PR.

**Sub-finding (cosmetic):** The Upstream Reference section
L488-491 lists "MAF adapter source" and "Citadel adapter source"
pointing to the **same** URL
(`agent-governance-python/agent-os/src/agent_os/integrations`).
Both adapters live in that directory, so this is structurally
correct but the prose could be more precise. Not raised in this
PR — cosmetic only.

### C12 — Link rot in Upstream Reference URLs

**Status:** none observed.

`curl -I -L --max-time 10` on all 11 unique URLs at SKILL.md
L482-502 returned **HTTP 200** at audit time (2026-05-31). The
12 listed URLs include one duplicate (MAF + Citadel adapter
sources point to the same `integrations/` tree, see C11 sub-
finding), giving 11 distinct targets — all reachable:

- `github.com/microsoft/agent-governance-toolkit` (repo)
- `microsoft.github.io/agent-governance-toolkit` (docs site)
- `pypi.org/project/agent-governance-toolkit/`
- `pypi.org/project/agent-framework/`
- 3 × `docs/{quickstart,deployment/azure-{foundry-agent-service,container-apps}}.md`
- 1 × `agent-governance-python/agent-os/src/agent_os/integrations` (tree)
- 1 × `examples/quickstart` (tree)
- 1 × `docs/compliance/owasp-agentic-top10-architecture.md`
- 1 × `docs/BENCHMARKS.md`

### C13 — Telemetry / observability wiring drift

**Status:** none observed.

The skill documents two telemetry surfaces, both correctly
delegated:

- `AuditLog.export_cloudevents()` for OTel-shaped event export
  (cited as the Foundry observability integration point at L470)
- App Insights connection ownership is explicitly pointed at
  `foundry-observability` (L469-471), not redefined in this skill

The fixture exercises `export_cloudevents()` in-process (returns
an iterable of CloudEvent shapes); it does not push to App
Insights. That is the correct boundary: `foundry-observability`
owns the wiring, `foundry-agt` produces the events.

### C14 — Snippet → reference-file duplication (AGENTS.md § 7)

**Status:** none observed.

The skill's canonical reference file is
`references/maf-middleware-snippet.py` (103 lines, the
"FoundryChatClient bootstrap"-equivalent for AGT middleware).
SKILL.md does **not** re-paste that snippet inline. It instead
shows:

- A 4-line import block at L262-267 (subset of the imports the
  reference file uses — clearly truncated for narrative)
- An imperative reference at L283 ("Copy verbatim from
  `references/maf-middleware-snippet.py`")
- A function-name table at L425-440 mapping reference files to
  SKILL.md sections

This is the correct shape per AGENTS.md § 7 (single source of
truth in `references/`, prose link in SKILL.md). No duplication.

### C15 — Cross-file drift (SKILL.md ↔ references/ ↔ pin)

**Status:** none observed *for fence-count-style drift*. Version-
string drift across files reclassified under C21 (see below).

SKILL.md has 12 code fences; `references/upstream-pin.md` has
16. The 4-fence delta is the pin's two **validation script
blocks** (the `validation.script` body + its expected_output
demo) and two diff/install code blocks unique to the pin — none
of which duplicate SKILL.md prose. This is structurally correct.

The version-number drift (SKILL.md prose says 3.6.0/1.3.0 while
the pin's `packages[*].version` says 3.7.0/1.7.0) is a real
issue but properly belongs under **C21 — version drift**, not
under "cross-file drift" semantics. See C21.

### C16 — RBAC propagation race (separate from C9)

**Status:** N/A.

No RBAC grants are performed by the skill or its fixture. The
optional Sidecar variant (Path B) does require RBAC, but that
deployment shape is owned by `azd-patterns` + `foundry-mcp-aca`
and audited under those skills.

### C17 — Markdown rendering / backtick corruption (Pattern 12)

**Status:** none observed.

The skill uses standard inline-code backticks throughout. No
literal `SMOKE_RESULT` token appears anywhere in SKILL.md (the
marker is fixture-side only). The fixture follows Pattern 12
strictly: marker is written via Bash tool's `printf` into a
file — never emitted as agent prose — so backtick-decoration
risk is structurally eliminated.

### C18 — Validation-script gate (Pattern 17 of testing tiers)

**Status:** **observed gap — closed by this PR's fixture.**

The pin's `validation.script` at L60-77 of `upstream-pin.md`
runs `agt --version`, `agt doctor`, `agt verify`, and a Python
import-smoke. `expected_output: ["OWASP ASI 2026", "factory ok"]`
greps both the `agt verify` OWASP-tag output and the import-
smoke's success line.

**The gap:** the pin script never actually **loads** the canonical
`references/policies/default.yaml` against `PolicyEvaluator` and
asserts a deny on a synthetic payload. That's how the
`length_gt` operator drift (see C8) survived undetected through
the most recent pin refresh — the policy file's YAML parsed
cleanly, the evaluator silently skipped the unknown operator, and
`agt verify` (which checks compliance schema coverage, not policy
runtime behaviour) reported all green.

The fixture in this PR is **strictly more exhaustive**:

- Loads `references/policies/default.yaml` via
  `PolicyEvaluator.load_policies(...)` and asserts both the SQL
  DENY rule rejects `DROP TABLE` **and** the benign greeting is
  not denied (using a version-tolerant `decision_text(decision)`
  helper)
- Asserts `Agent.__init__` exposes a `middleware` parameter
- Exercises `AuditLog` round-trip (`log()` × 2 →
  `verify_integrity()` → `export_cloudevents()`)

The pin remains a correct lower-bound gate for CLI smoke + import
resolution; the fixture is the upper-bound gate for runtime policy
behaviour. The two complement each other and together would have
caught `length_gt` on the first refresh.

### C19 — Governance / forbidden-string regressions

**Status:** none observed.

`skill-validation.yml` already gates this. The SKILL.md body
contains no customer names, no PoC names, no private-repo
names. The Sidecar example at L320-345 uses
`mcr.microsoft.com/agentmesh/enforcer:3.6.0` — a public MCR
image path (generic), not a customer-specific registry.

### C20 — Concurrency / parallelism shape drift (Pattern 22)

**Status:** N/A.

The skill is **in-process** middleware. No concurrent Azure
calls, no model fan-out, no matrix-shape concerns. The fixture
runs in one matrix leg under the workflow's `max-parallel: 2`
ceiling — no fixture-side concurrency.

### C21 — Version drift (prose vs pin vs snippet)

**Status:** **HIT — fix-in-PR via commit 3 (`[skill-rewrite]`
tag).**

The skill has version-string drift across three files:

| File | Line | Says | Should say |
|---|---|---|---|
| `SKILL.md` | L8 (description) | `AGT 3.6.0` | `AGT 3.7.0 + MAF 1.7.0` |
| `SKILL.md` | L19 (metadata.version) | `1.0.5` | `1.0.6` (PATCH bump) |
| `SKILL.md` | L219 (Legend) | `AGT 3.6.0` | `AGT 3.7.0 + MAF 1.7.0` |
| `SKILL.md` | L282 (snippet preamble) | `AGT 3.6.0 + MAF 1.3.0` | `AGT 3.7.0 + MAF 1.7.0` |
| `SKILL.md` | L426 (matrix table) | `AGT 3.6.0` | `AGT 3.7.0` |
| `maf-middleware-snippet.py` | L2-3, L7 (header) | `AGT 3.6.0 + MAF 1.3.0` | `AGT 3.7.0 + MAF 1.7.0` |
| `upstream-pin.md` | L165 (header) | `(3.6.0)` | `(3.7.0)` |
| `upstream-pin.md` | L198 (Agent ctor) | `(1.3.0)` | `(1.7.0)` |

Meanwhile, `upstream-pin.md` `packages[*].version` is already
`agent-governance-toolkit ~=3.7.0` + `agent-framework ~=1.7.0`,
and the **fixture** in commit 1 of this PR installs from those
caps. So the prose lags the actual installed surface.

**Left UNCHANGED** (out of scope per plan):

- `SKILL.md` L336 sidecar image
  `mcr.microsoft.com/agentmesh/enforcer:3.6.0` — there is no
  evidence in MCR that a `3.7.0` tag has been published; the
  fixture does not exercise the sidecar path, so we cannot
  empirically verify a 3.7.0 sidecar works
- `SKILL.md` L451 subpackage-skew context narrative
  (cites `3.2.2` as the verifier subpackage version for a
  meta-package vs subpackage skew explanation — this is
  historical/explanatory and remains accurate)
- The historical `v1.0.0` and `v1.0.1` changelog entries
  (append-only)

**Resolution:** Commit 3 of this PR (after stability-run-1
GREEN) edits the 8 sites above, bumps `metadata.version` to
`1.0.6`, and appends a `v1.0.6` changelog entry citing the
stability-run-1 URL as evidence for the 3.7.0 / 1.7.0
signature surface.

---

## Fixture

| Field | Value |
|------|------|
| Path | `skills/foundry-agt/test-fixture/consumer_prompt.md` |
| Pattern compliance | P1, P12, P15, P17, P20, P22, P24, P25 |
| Wall-clock budget | < 3 min (no Azure resources, no model invoke) |
| Azure cost | $0 (in-process only) |
| Success signal | Pattern 12 file marker at `/tmp/foundry-agt-smoke-result` |
| Teardown | None (in-process; process exit cleans up) |

The fixture installs `agent-governance-toolkit[full]~=3.7.0` and
`agent-framework~=1.7.0`, then runs a single Python heredoc that:

1. Imports the canonical surfaces (`create_governance_middleware`,
   `PolicyEvaluator`, `AuditLog`, MAF `Agent`); import failure →
   FAIL
2. Prints `inspect.signature()` for 6 surfaces (the C8 evidence
   above)
3. Asserts `Agent.__init__` exposes a `middleware` parameter
4. Loads `references/policies/default.yaml`, asserts the SQL DENY
   rule rejects `DROP TABLE` AND the benign greeting is not
   denied, using a version-tolerant `decision_text(decision)`
   helper that introspects multiple possible attribute names so
   an allow/no-op object cannot silently pass
5. Calls `create_governance_middleware(policy_directory=...,
   enable_rogue_detection=False)` (per Known Issue #4) and asserts
   the result is a `list` of length ≥ 2
6. Exercises `AuditLog`: `log()` × 2 → `verify_integrity()` truthy
   → `export_cloudevents()` returns iterable of length 2

Step 0 uses **show-don't-assert** auth (Pattern 17): prints
`AZURE_*=set` inventory + `az account show || echo "(...)"` as
audit-log context. None of these are gating preconditions for
this fixture — the skill makes **no Azure resource, dataplane,
model, or ACA calls**.

---

## CI matrix runs

| # | SHA | Run / leg | Outcome | Notes |
|---|---|---|---|---|
| 1 | `ece4b18` | [`26745982162` / `78821489441`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26745982162/job/78821489441) | ✅ GREEN (3m6s copilot wall-clock; 3m37s job total) | Captures `inspect.signature()` evidence (C8); discovered + self-healed the `length_gt` operator drift in `references/policies/default.yaml` (run log L425-441 grep, L468 self-heal). Self-heal persisted in repo by commit 3. |
| 2 | `<pending>` | `<pending>` | `<pending>` | Stability-run-2 — ≥ 45 s after #1 (P1); validates self-heal persists across runs |
| 3 | `<pending>` | `<pending>` | `<pending>` | Stability-run-3 — ≥ 45 s after #2 (P1); proves ≥ 3 GREEN before ready-for-review |

Update this table after each empty-commit stability push.

---

## Open items

- **Backlinks-from-consumers** into `foundry-agt` (deferred at
  SKILL.md L477-479 to a follow-up PATCH-bump PR) — out of scope
  for this PR
- **Sidecar (Path B) image-tag refresh** to `enforcer:3.7.0` —
  requires evidence the 3.7.0 tag exists in MCR; out of scope
- **Cosmetic** improvement to Upstream Reference labels
  ("MAF adapter source" + "Citadel adapter source" point to the
  same URL; could be one entry labelled "Integrations source
  tree, used by both MAF and Citadel adapters")

---

## Audit closure

This audit was performed against SKILL.md @ `1.0.5`. After
commit 3 lands (`1.0.5` → `1.0.6` with the C21 fix-in-PR), the
next deep-audit pass should be triggered on the next MINOR/MAJOR
upstream bump (per `references/upstream-pin.md` freshness
contract) or on any cross-skill ref drift detection.
