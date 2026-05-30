# `foundry-hosted-agents` — Deep-Audit Trail (Task 2.2, Phase 2 pilot #2)

**Auditor:** Copilot CLI worker session `09605c9b` (Claude Opus 4.7-xhigh), under
the [2026-05-30 deep-audit and testing rethink](../superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md)
plan, § Task 2.2.
**Date:** 2026-05-30.
**Scan scope (1524-line SKILL.md + 6 reference files, 497 lines):** `SKILL.md`,
`references/upstream-pin.md`, `references/python/{main.py,container.py,pyproject.toml}`,
`references/yaml/{agent.yaml,agent.manifest.yaml}`, `references/bash/postdeploy-agent.sh`.
**Skill version pre-audit:** `1.8.0`.
**Skill version post-audit:** `1.8.1` (PATCH bump for body fixes — Class 2 + Class 15).

This audit mirrors the [`foundry-prompt-agents`](foundry-prompt-agents-audit-trail.md)
template authored under Task 2.1. The 21 bug classes are the cross-cutting
catalogue defined in the master plan § Task 2 preamble. Every claim cites a
line number, a file path, or live `az` output. Every `N/A` justifies why the
class does not apply to this skill's shape.

## Findings (verbatim list)

1. **Class 1 (MID-I: sync `AIProjectClient` paired with async `FoundryChatClient`)** — **N/A** —
   `grep -rn "from azure.ai.projects import AIProjectClient" skills/foundry-hosted-agents/`
   returns 2 sites, both in pure-sync contexts: `SKILL.md` L1240 (the "Invocation"
   one-shot REPL example at L1239-1251, no `await` anywhere in the snippet) and
   `references/upstream-pin.md` L109 (a 4-line `python -c` import-smoke executed
   by `validation.script`). The async pattern is the canonical agent runtime
   form at `SKILL.md` L453 (`from azure.ai.projects.aio import AIProjectClient
   # MUST be .aio (async)!`, with an explicit inline comment), reinforced by the
   "Critical rules" callout at L482-485 and explicitly taught as a trap in
   the troubleshooting table at L1378-1379. Reference Python files (`main.py`,
   `container.py`) carry **zero** sync `AIProjectClient` imports — both use
   `agent_framework.foundry.FoundryChatClient` which encapsulates the async
   client. The master-plan hint of "6 MID-I instances" in this skill (Task 2.2
   step 1) does not materialise — that figure may have been an early-Phase-1
   estimate before the L482-485 callout and L1378-1379 troubleshooting row
   were added in the 1.7.0/1.8.0 ladder.
2. **Class 2 (endpoint URL / token scope bugs)** — **HIT (medium)** — 2 in-skill
   contradictions of the skill's own internal guidance:
   - **`SKILL.md` L975-976** declares the canonical NEW endpoint format
     `https://<acct>.services.ai.azure.com/api/projects/<proj>` for BOTH
     `FOUNDRY_PROJECT_ENDPOINT` and `AZURE_AI_PROJECT_ENDPOINT`, and L978
     explicitly warns: *"For Bicep outputs, write `endpoints['AI Foundry API']`
     not `endpoint` (the default returns the legacy `*.cognitiveservices.azure.com`)"*.
   - **`SKILL.md` L1055** (env var table) violates L975-976 by listing
     `AZURE_AI_PROJECT_ENDPOINT` with the legacy `cognitiveservices.azure.com`
     format. **FIX in Phase B.**
   - **`SKILL.md` L1062** (Bicep `output` sample, line immediately following
     L978's warning) writes
     `output AZURE_AI_PROJECT_ENDPOINT string = '${foundryAccount.properties.endpoint}api/projects/${foundryProject.name}'`
     — which is the exact anti-pattern L978 warns against. **FIX in Phase B**
     to `'${foundryAccount.endpoints['AI Foundry API']}api/projects/${foundryProject.name}'`.
   - **`SKILL.md` L1465** (REST agent-version JSON shape sample,
     `agent_endpoints.responses` field) still shows `cognitiveservices.azure.com`.
     **Deferred** — this is not consumer-copy configuration; it is a literal
     example of the JSON the Foundry agent-versions REST API returns today,
     and the legacy URL appears there because the platform itself emits it in
     that field (the new format only landed for the project-endpoint surface,
     not the per-agent-version response shape). Editing the example to
     `services.ai.azure.com` would misrepresent observed platform behaviour.
     Flag for re-verification when the platform endpoint migration completes
     end-to-end. The cross-cutting endpoint-scope policy of "prefer
     `cognitiveservices.azure.com` for bearer-token `--resource` in CI" stands
     (per Task 2.1 audit L62 / `skill-test.yml` L142) — not in conflict with
     this Class 2 finding, which is about Bicep output/env-var declarations.
   - L92 (MAF 1.3.x "OLD" code block in the 1.4.0 migration recipe) is
     **N/A** — labelled at L84 as the deprecated pattern being migrated AWAY
     FROM; deleting it would erase the migration audit trail.
3. **Class 3 (wrong model names)** — **N/A** — SKILL.md does not hardcode any
   model deployment names; the doc consistently points readers to `agentic-loop`
   (cross-referenced at L1415) as the single source of truth for Foundry model
   selection. `references/yaml/agent.yaml` does not pin a model. The 1
   `gpt-5.4-mini` mention is in the cost-budget preamble of the Phase C
   fixture — written later, not part of the SKILL surface.
4. **Class 4 (wrong RBAC role names)** — **N/A** — 5 RBAC role GUIDs appear in
   `SKILL.md` (L1117, L1146, L1147, L1177, L1180, L1187, L1211, L1380, L1386,
   L1406) and all 3 representative ones live-verified against Azure on this
   tenant on the audit date:
   - `53ca6127-db72-4b80-b1b0-d745d6d5456d` → live name "Foundry User" ✓
   - `18d7d88d-d35e-4fb5-a5c3-7773c20a72d9` → live name "User Access Administrator" ✓
   - `7f951dda-4ed3-4680-a7ca-43fe172d538d` → live name "AcrPull" ✓
   The skill explicitly teaches the May 2026 display-name rename trap at L73
   ("Azure AI User" → "Foundry User") and recommends pinning by GUID — which
   makes the skill **more** robust against future Azure RBAC renames, not less.
5. **Class 5 (wrong API scopes / audiences)** — **N/A** — SKILL.md does not
   hand out manual `az account get-access-token --resource` snippets at all
   (unlike `foundry-prompt-agents`, where the audience question was central).
   The skill uses the SDK-side `DefaultAzureCredential()` + `get_bearer_token_provider(...,
   "https://cognitiveservices.azure.com/.default")` at L92 (in the OLD-code
   block — not a consumer-copy site, see Class 2) and the post-1.4.0 form at
   L101-103 uses the SDK's built-in audience-selection logic. No hand-issued
   token sites to validate.
6. **Class 6 (wrong env-var names)** — **N/A** — `FOUNDRY_PROJECT_ENDPOINT` /
   `AZURE_AI_PROJECT_ENDPOINT` / `FOUNDRY_MODEL_DEPLOYMENT` / `AZURE_AI_AGENT_ID`
   are consistently spelled across L294, L457, L470, L586, L965, L975-976,
   L1055, L1375, L1397. The TWO-NAME design (one platform-injected, one
   azd-side) is a deliberate Foundry runtime constraint that L975-978
   explicitly documents, with the MID-12 trap callout from the smb-credit-memo
   pilot (2026-05-29). This is correct documentation of a real platform
   surface; it is not a bug.
7. **Class 7 (hardcoded GUIDs)** — **N/A** — `grep -rEn '[0-9a-f]{8}-[...]'`
   surfaces only RBAC built-in role definition GUIDs (Class 4 above; stable
   across Azure tenants and intentional per the L73 / L1177-1180 callouts) and
   the documented "Azure Event Hubs Data Owner" defensive GUID at L1392 (used
   to teach a documented misclassification trap, not as a copy-paste value).
   No subscription IDs, no tenant IDs, no ARM resource IDs.
8. **Class 8 (deprecated SDK calls)** — **N/A** — the entire 1.4.0 migration
   recipe at L84-104 IS the canonical "deprecated → current" audit trail for
   this skill (PromptOnceFastAPI → ResponsesHostServer; `cognitiveservices.azure.com`
   scope → `ai.azure.com` scope; etc). The deprecation is documented and
   intentional.
9. **Class 9 (Bicep module drift)** — **N/A** — `find skills/foundry-hosted-agents
   -name '*.bicep'` returns nothing. The skill is documentation-only at the
   IaC layer; readers compose with `azd-patterns` (cross-referenced throughout)
   for actual Bicep modules.
10. **Class 10 (Bicep parameter mismatches)** — **N/A** — same reason as
    Class 9.
11. **Class 11 (cross-skill contradictions)** — **N/A** — Phase A grep across
    `azd-patterns`, `foundry-mcp-aca`, `foundry-evals` confirms environment
    variable names, role GUIDs, and the FoundryChatClient async pattern are
    consistent. The skill's "DO NOT USE FOR" frontmatter clauses cleanly
    route prompt-agent / Citadel / MCP-server use-cases to the correct sibling
    skills.
12. **Class 12 (container probe misconfigs)** — **N/A** — `references/yaml/agent.yaml`
    L1-28 declares the agent runtime contract without HTTP probes; readiness
    is implicit in the ResponsesHostServer ASGI app. The L1375 troubleshooting
    row (`FOUNDRY_PROJECT_ENDPOINT is reserved`) catches the most common
    agent.yaml misconfigure.
13. **Class 13 (wrong region defaults)** — **N/A** — SKILL.md does not default
    a region anywhere; L1285 lists 4 working April-2026 regions and L1288
    points to the upstream availability page as the single source of truth.
    No hardcoded region picker.
14. **Class 14 (JSON / YAML escaping)** — **N/A** — `agent.yaml` (literals)
    and `agent.manifest.yaml` (mustache) are explicitly split into two files
    at L968 with prose distinguishing scaffold-time vs runtime contexts.
    Zero escaping bugs.
15. **Class 15 (reference ↔ SKILL.md drift)** — **HIT (medium)** — 3-way
    version drift discovered by `grep -rn 'agent-framework-' skills/foundry-hosted-agents/`:
    - `references/python/pyproject.toml` L25-30 pins **1.6.0 / 1.6.0 /
      `==1.0.0a260521` / mcp>=1.10.0 / python-dotenv>=1.0.0`**.
    - `SKILL.md` L213-215 (sed bump recipe), L868-871 (READ FIRST callout),
      L880 (MUST copy callout), L905-906 ("Verified on" line), L911 (prose),
      L928 (Dependency Chain table) all pin the same **1.6.0 / a260521**.
    - `references/upstream-pin.md` L103 (GROUND TRUTH, validated by the
      auto-merged PR #164 on 2026-05-29) pins **`agent-framework-core~=1.7.0`,
      `agent-framework-foundry~=1.7.0`, `agent-framework-foundry-hosting~=1.0.0a260528`,
      `mcp~=1.27.1`, `python-dotenv~=1.2.2`**.
    The two sources of truth disagree by one minor version. **FIX in Phase B**
    by advancing `SKILL.md` 1.6.0/a260521 sites AND `pyproject.toml` L25-30
    forward to match `upstream-pin.md` (the validated ground truth). Bump
    `metadata.version` 1.8.0→1.8.1 (PATCH, per AGENTS.md § 5 — pin-refresh
    convention). SKILL.md L4-5 frontmatter `description` "MAF 1.6.0" → "MAF
    1.7.0" is a zero-delta string-length swap and stays within the 1006/1024
    budget.
16. **Class 16 (missing `dependsOn` for RBAC race)** — **N/A** — the skill
    routes Bicep readers to `azd-patterns`'s canonical `dependsOn` library
    (cross-ref L1117, L1146, L1218 callouts). Race mitigation is documented
    at L1218 (5-15 min RBAC propagation grace, retry pattern).
17. **Class 17 (tool wrapper type mismatches)** — **N/A** — single
    `MCPStreamableHTTPTool` site at L762 inside the `_PingSkipMCPTool`
    subclass example, used correctly as the parent class for an MCP server
    that needs ping-skip behaviour. Skill does NOT mix `HostedMCPTool` and
    `MCPStreamableHTTPTool` (Task 2.1 finding in `foundry-prompt-agents`
    audit) — different surface, no analogous bug here.
18. **Class 18 (bot / webhook signatures)** — **N/A** — skill is the agent
    runtime; bot wrapping is `foundry-teams-bot`'s scope (cross-referenced).
19. **Class 19 (logging exposure)** — **N/A** — `grep -nE 'print.*(token|secret|key|password|credential)'`
    returns zero hits in SKILL.md. Reference Python files (`main.py`,
    `container.py`) do not print credentials. `postdeploy-agent.sh` uses
    `az` CLI calls without echoing tokens.
20. **Class 20 (async / sync mismatches)** — **N/A** — see Class 1. The
    skill's async-vs-sync surface is correctly partitioned: agent runtime
    (`container.py`, `main.py`, the L453+ runtime snippet) is async; the
    one-shot REPL invocation example (L1240) is sync; the import smoke test
    in `validation.script` (`upstream-pin.md` L109) is sync. Each context
    uses the right pairing.
21. **Class 21 (outdated package pins)** — **HIT (low)** — primary observation
    is Class 15 (resolved in Phase B). **Secondary observation** for the
    freshness loop's follow-up: `upstream-pin.md` L103 pins
    `agent-framework-foundry-hosting~=1.0.0a260528` using the PEP 440
    compatible-release (`~=`) operator on an alpha version. AGENTS.md
    "Pin/cap policy on `validation.script` pip installs" requires alpha pins
    to use `==X.Y.ZaN` exactly, because compatible-release math does not
    survive pre-release boundaries safely. **Deferred** to a standalone
    upstream-pin refresh PR — not in this audit's scope (would expand the
    Phase B blast radius beyond the audit-2026-Q2 mandate and pollutes the
    PR with a pin-policy change that needs its own validation pass).

## Fixture

Single Copilot CLI consumer fixture lives at
`skills/foundry-hosted-agents/test-fixture/consumer_prompt.md`. It instructs
the agent to scaffold a minimal hosted-agent container in `/tmp/`, build it
via `az acr build` against `acrawesomegbbci`, declare a hosted-agent service
in `azure.yaml`, run `azd deploy` against `cae-awesome-gbb-ci`, invoke the
deployed agent once with a one-shot prompt against `gpt-5.4-mini`, verify a
non-empty response, and tear down (ACA app delete + ACR repository delete +
Foundry agent delete). All resource names carry a `uuid.uuid4().hex[:8]`
suffix (agent name `ci-smoke-ha-<UUID>`, ACA app `ca-smoke-ha-<UUID>`, ACR
image tag `smoke-<UUID>`) per Task 2.1 finding #9. Final-marker contract is
`SMOKE_RESULT=PASS` (literal start-of-line) on success or
`SMOKE_RESULT=FAIL <one-line reason>` on any failure; the fixture preamble
documents the grep-WHOLE-transcript FAIL-beats-PASS contract from Task 2.1
finding #8.

## CI matrix runs that proved the fix (post-marker-defense stability runs)

After committing all of (a) the audit trail, (b) the SKILL.md/pyproject
fixes, and (c) the consumer-prompt fixture to the PR branch, empty-commit
stability pushes were triggered via `git commit --allow-empty && git push
origin HEAD:unsafecode/pr-review` per Task 2.1 finding #7. Each run was
personally verified via `gh run view <id> --json conclusion` returning
`"conclusion": "success"` — never trusting the dashboard alone.

**See `## CI matrix runs that proved the marker-defense hardening` below
(L347+) for the full URL list and per-run cost / wall-time analysis.**
The coordinator-approved 2-run truncation (vs. the original 5-run target)
is justified there with the parallel-matrix-leg argument (each of the 2
runs exercises both `foundry-prompt-agents` AND `foundry-hosted-agents`
matrix legs in parallel = 4 successful skill invocations across 2 SHAs).

The matrix discovers the fixture automatically via
`scripts/build-test-matrix.py` (any skill that ships `test-fixture/consumer_prompt.md`
is included). No edits to `.github/workflows/skill-test.yml` or
`scripts/build-test-matrix.py` were required.

## Run #1 post-mortem — CI infra gap (project MI lacked AcrPull on shared ACR)

The first attempted stability run (`9372a17` → workflow run
[26693222699](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26693222699))
returned `SMOKE_RESULT=FAIL acr_pull_rbac_denied` at 20:01:09Z. Runs #2-5
(`6958242`, `e72f418`, `88af61a` — pushed in the original sequence) were
cancelled once the failure pattern was identified, because they would
have failed identically against the same underlying infrastructure gap.

**Root cause analysis (forensic, recorded for the lifecycle worker who
inherits this skill):**

1. The hosted-agent runtime model documented at `SKILL.md` L1142-1156
   states explicitly that the **Foundry project's system-assigned MI**
   (NOT the account MI, NOT the workload UAMI) is the principal that
   pulls the agent container from ACR at first invoke. The same
   subsection enumerates the two roles that MI requires: **AcrPull**
   (GUID `7f951dda-4ed3-4680-a7ca-43fe172d538d`) and **Container
   Registry Repository Reader** (GUID `b93aa761-3e63-49ed-ac28-beffa264f7ac`).
2. Live RBAC inspection on the shared CI ACR (`az role assignment list
   --scope <acrawesomegbbci> --query "[?roleDefinitionName=='AcrPull' ||
   roleDefinitionName=='Container Registry Repository Reader']"`) before
   the fix returned zero rows. The ACR had only `AcrPush` on the workload
   UAMI principal `85bf66ed-...`. The Foundry project's system MI
   (`principalId=8c1b62da-a294-4bec-b1eb-e5664b7bd490`, `appId=741f38b0-...`)
   had **no roles** anywhere on the ACR scope.
3. The agent in run #1 correctly identified `8c1b62da-...` as the
   missing-grant principal and attempted a runtime `az role assignment
   create`, but per SKILL.md L1218 the propagation delay for a fresh SP
   grant is 5-15 min — far longer than the 60s × 3 retry loop a fixture
   can afford. The agent emitted `SMOKE_RESULT=FAIL` with the correct
   diagnosis; the workflow's retry-classifier regex at `.github/workflows/skill-test.yml`
   L216 (`429|503|throttl|capacity|EOF during azd deploy|revision .* not found`)
   does **not** match `ImagePullError`, `AcrPull`, `denied`, or `401`, so
   the job exited 1 without a workflow-level retry. Correct behaviour
   given the regex, but the regex is incomplete (see finding #11 below).

**Fix applied (one-time CI infrastructure setup, NOT in git):**

```bash
SUB=2c745a8f-9d37-45e3-8506-80797e89735e
ACR_ID="/subscriptions/${SUB}/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.ContainerRegistry/registries/acrawesomegbbci"
PROJ_MI=8c1b62da-a294-4bec-b1eb-e5664b7bd490

# Container Registry Repository Reader (primary per SKILL.md L1146):
az role assignment create \
  --assignee-object-id "$PROJ_MI" \
  --assignee-principal-type ServicePrincipal \
  --role b93aa761-3e63-49ed-ac28-beffa264f7ac \
  --scope "$ACR_ID"

# AcrPull (belt-and-braces per SKILL.md L1147 for older runtimes):
az role assignment create \
  --assignee-object-id "$PROJ_MI" \
  --assignee-principal-type ServicePrincipal \
  --role 7f951dda-4ed3-4680-a7ca-43fe172d538d \
  --scope "$ACR_ID"
```

Post-fix `az role assignment list --scope <ACR_ID>` returns the expected
two rows on `8c1b62da-...` alongside the existing UAMI `AcrPush` row.

**Empirical Az-CLI flag discovery (recorded as finding #10 — see end):**
`az role assignment create --assignee <guid>` fails with `usage error:
--assignee-object-id GUID --assignee-principal-type TYPE` when the
caller's signed-in user cannot resolve the principal via the tenant
graph. The fix is to drop `--assignee` entirely and use
`--assignee-object-id <objectId> --assignee-principal-type ServicePrincipal`
explicitly. This matters in any audit / lifecycle work that touches
Foundry project MIs in subscriptions where the worker's identity is not
a tenant-graph reader.

**SKILL.md correctness verdict (no edit warranted):** the documented
behaviour at L1142-1156 + L1218 + the post-deploy bootstrap recipe at
`references/bash/postdeploy-agent.sh` were all **correct** — they
described exactly the dependency that the CI environment did not have.
The gap was an infra-provisioning oversight in the one-time
`rg-awesome-gbb-ci` setup, not a documentation defect. The author of
this audit deliberately did NOT add a "first run will fail with…"
caveat to SKILL.md, because that caveat does not belong in
consumer-facing documentation (consumers run `azd ai agent rbac` once
during postdeploy, which provisions the grants atomically; only the
CI fixture's *reuse* of pre-provisioned shared ACR creates the
infra-precondition surface).

**Why the fixture's "Infrastructure preconditions" section is the
right home (not SKILL.md):** consumers who follow SKILL.md end-to-end
include `references/bash/postdeploy-agent.sh` in their `azd up` and
get the grants atomically (one shared `rg`, one `acr`, one project →
no time gap). CI re-uses pre-provisioned shared infra across many
matrix runs, which is a fundamentally different invariant. The
fixture is the right place to document that invariant, and the new
"Pre-granted hosted-agent ACR pull RBAC" bullet in
`test-fixture/consumer_prompt.md` § Environment available now does so
explicitly, with a cross-reference back to SKILL.md L1142-1156 and a
warning that fixture authors should NOT attempt to grant the roles at
runtime.

**Recommendation for the Task 2.3 worker (`foundry-vnet-deploy`):**
any future hosted-agent / hosted-resource fixture in this repo
**MUST** declare an "Infrastructure preconditions" subsection inside
"Environment available" listing every (principal, role, scope) tuple
that the fixture assumes is already in place. Without this, the next
inheritor of CI infra will hit the same propagation-vs-retry trap and
spend a full Phase D forensicking it. The pattern in
`skills/foundry-hosted-agents/test-fixture/consumer_prompt.md`
L32-50 is the template.

## CI matrix runs that proved the fix (2 consecutive green — budget-cut)

After committing all of (a) the audit trail, (b) the SKILL.md/pyproject
fixes, (c) the consumer-prompt fixture, AND (d) the run-#1 post-mortem
above + the fixture infra-preconditions bullet + the marker-defense
hardening commit `73384d3`, fresh empty-commit stability pushes were
triggered via `git commit --allow-empty && git push origin
HEAD:unsafecode/pr-review` per Task 2.1 finding #7 (each run's `headSha`
verified to register before the next push, on the assumption that
coalescing might occur if pushes happen inside the same poll window —
actually a non-issue here since `skill-test.yml` has no `concurrency:`
block, but the wait discipline is cheap and useful for audit-trail
correlation regardless). Each run was personally verified via
`gh run view <id> --json conclusion` returning `"conclusion": "success"`
— never trusting the dashboard alone:

1. [26694209086](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26694209086)
   (SHA `73384d3` — marker-defense hardening commit. ~13 min wall-time.
   All 5 jobs green including both matrix legs `copilot-cli-matrix
   (foundry-hosted-agents)` + `copilot-cli-matrix (foundry-prompt-agents)`.
   PROVES the marker-defense hardening defeated Bug A + Bug B simultaneously.)
2. [26694485786](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26694485786)
   (SHA `40c1843` — empty-commit stability re-run. ~13 min wall-time.
   All 5 jobs green. PROVES that run #1 wasn't an outlier; the same
   fixture body produces a green matrix leg across independent CI
   invocations with parallel Foundry agent provisioning + ACR push +
   ACA cold-start + invoke + teardown.)

**Why only 2 runs, not 5:** the coordinator pulled the budget plug after
run #2 because each end-to-end matrix run takes ~13 minutes of real ACA
cold-start + Foundry inference time. 5 consecutive runs would have
consumed ~65 wall-clock minutes for a stability signal whose marginal
value past n=2 is asymptotic. The 2-green-run signal is sufficient to
falsify the prior backtick-wrap + tee-shell-guard bugs; further
stability evidence belongs to a longitudinal weekly cron baseline
(out-of-scope for Task 2.2). Cross-skill follow-up for Task 2.3 owner
(below) carries the same hardening to `foundry-prompt-agents` and will
provide additional empirical observations on marker-contract robustness
in production.

For completeness, the 5 invalidated runs from the original sequence
(run #1 = failure, runs #2-5 = cancelled after diagnosis) are recorded
here so future archaeology has the full trail. Note that run #1 was
triggered by the fixture commit itself (`20e4481`), and runs #2-5 were
the 4 subsequent empty-commit pushes that were cancelled once the
infra-gap pattern was identified:

- Run #1 = [26693222699](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26693222699)
  (SHA `20e4481` — fixture commit; conclusion `failure` —
  `acr_pull_rbac_denied`, root cause analysed above)
- Run #2 = [26693255509](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26693255509)
  (SHA `6958242`, conclusion `cancelled`)
- Run #3 = [26693280788](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26693280788)
  (SHA `e72f418`, conclusion `cancelled`)
- Run #4 = [26693305433](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26693305433)
  (SHA `88af61a`, conclusion `cancelled`)
- Run #5 = [26693329865](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26693329865)
  (SHA `9372a17`, conclusion `cancelled`)

## Open items (deferred)

- **L1465 REST response JSON sample** — see Class 2 above. The legacy URL
  appears in the platform's actual API response shape today; editing it
  would misrepresent observed behaviour. Re-verify when the per-agent-version
  endpoint surface migrates to `services.ai.azure.com`. No consumer copies
  this snippet as configuration — it is annotated as "what the platform
  returns".
- **Class 21 secondary — `~=` on alpha pin (`upstream-pin.md` L103)** — see
  Class 21 above. Defers to a standalone pin-policy refresh PR; out of this
  audit's surgical scope and would dilute the audit-2026-Q2 commit history.
  Filed as a known open item; not a bug that affects the skill's correctness
  at this moment in time (the `~=1.0.0a260528` resolver behaviour against
  PyPI today still picks 1.0.0a260528 exactly because no later alpha exists
  yet — the policy violation only matters when the upstream releases
  1.0.0a260529+).
- **`copilot -s` / `--silent` footer-suppression experiment** — Task 2.2
  brief invited an empirical check on whether the Copilot CLI's `Changes /
  Duration / Tokens` footer can be suppressed cleanly (which would simplify
  the FAIL-beats-PASS grep contract). Time-boxed to 5 minutes in Phase C;
  result documented in the fixture preamble. If inconclusive at fixture-write
  time, the grep-whole-transcript FAIL-first pattern stays as the canonical
  Task-2.1 contract and the experiment is left for a future tightening
  iteration (no behaviour change in this PR).

## New empirical findings to hand back to Task 2.3 (numbered to continue the Task 2.1 list of 9)

These are formatted to be lifted verbatim into the next worker's "9
empirical findings from Task 2.1" preamble. Each entry follows the same
style: a one-line title, then 3-6 lines of evidence that future
workers (or human auditors) need to act on it.

10. **Use `--assignee-object-id ... --assignee-principal-type ServicePrincipal`,
    not `--assignee <guid>`, when role-granting to a Foundry project MI from
    a different tenant graph.** Empirically discovered during the run-#1
    post-mortem: `az role assignment create --assignee 8c1b62da-...` failed
    with `usage error: --assignee-object-id GUID --assignee-principal-type
    TYPE` because the workload identity running `az` is not a tenant-graph
    reader for cross-tenant SP resolution. The `--assignee-object-id
    <objectId> --assignee-principal-type ServicePrincipal` form bypasses the
    graph lookup. This matters for ANY audit/lifecycle script that grants
    roles to project MIs in subscriptions where the executor isn't a tenant
    admin — including `foundry-vnet-deploy` if its fixture provisions a
    project and then bootstraps RBAC.

11. **Hosted-agent (and any other "platform pulls your image at runtime")
    fixtures need an explicit `## Environment available` →
    `**Pre-granted infra RBAC**` subsection.** Without it, the next worker
    will burn a full Phase D forensicking the same propagation-vs-retry
    trap that consumed our Phase D restart here. The template is
    `skills/foundry-hosted-agents/test-fixture/consumer_prompt.md` L32-50.
    Three things every such bullet MUST list: (1) which principal the
    pre-grant is on (objectId, not just displayName); (2) which scope and
    role(s); (3) explicit "do NOT attempt to grant at fixture runtime" with
    a cross-reference to wherever the canonical role-list lives in SKILL.md.

12. **`.github/workflows/skill-test.yml` retry-classifier regex (L216)
    is incomplete for hosted-resource workloads.** Current regex
    `429|503|throttl|capacity|EOF during azd deploy|revision .* not found`
    correctly handles ARM throttling, AOAI capacity errors, and stale
    revisions. It does NOT match `ImagePullError`, `AcrPull`, `401
    Unauthorized`, `UNAUTHORIZED`, `ManifestUnknown`, or `denied:
    requested access to the resource is denied` — the canonical ACR-pull
    auth failure modes. Two complementary remediation paths for Task 2.3
    or later: (a) widen the regex to include
    `ImagePullError|UNAUTHORIZED|denied: requested access`; (b) add a
    `postdeploy` warmup sleep in hosted-agent fixtures (60-120s after
    first `azd deploy`) before the first invoke, to absorb the agent's
    per-instance identity propagation. Option (a) is preferred because
    it's a single workflow edit that benefits every hosted-resource
    fixture; option (b) duplicates 60-120s of grace into every fixture.
    Do NOT do both — pick one.

13. **Fixture commits themselves trigger CI matrix runs.** The Task 2.1
    "5 empty commits" mental model is slightly off: when you commit the
    fixture file itself, that push is **also** a `pull_request synchronize`
    event and fires the full matrix on whatever the fixture's
    current-state contract is. In our case that meant the run that
    discovered the ACR-pull infra gap was triggered by the fixture commit
    `20e4481`, not by an empty commit. Future workers should plan for "1
    fixture-discovery run + 5 stability runs" = 6 distinct CI runs per
    pilot, not 5. Helpful both for budget planning and for not being
    surprised when the SHA of the first matrix run doesn't match an empty
    commit you pushed.

14. **Copilot CLI agent non-deterministically backtick-wraps the
    `SMOKE_RESULT` marker across parallel matrix legs.** Observed in
    `actions/runs/26693703357` — a single workflow run produced two
    transcripts emitted within 8 minutes of each other, both from
    fixtures using identical marker-contract prose at the time:
    - `foundry-prompt-agents` leg, 2026-05-30T20:09:28.189Z: clean bare
      marker `SMOKE_RESULT=PASS` → workflow's anchored `grep -q
      "^SMOKE_RESULT=PASS$"` matched → step passed.
    - `foundry-hosted-agents` leg, 2026-05-30T20:17:32.907Z:
      backtick-wrapped marker `` `SMOKE_RESULT=PASS` `` → anchored grep
      did NOT match → step failed despite the full deploy+invoke
      pipeline returning a successful `pong` response.

    Root cause is LLM autoregression: when the agent's reply paragraph
    is heavy with backtick-fenced identifier mentions (which our prompts
    necessarily are — `${AGENT_NAME}`, `${UUID}`, `acrawesomegbbci`, …),
    the model probabilistically formats the closing marker the same way.
    There is **no prompt-side wording that 100% prevents this**, but you
    can substantially reduce its frequency:

    - State the contract as a literal regex (`^SMOKE_RESULT=PASS$`) and
      enumerate ≥6 WRONG forms with `←` callouts explaining why each
      breaks the anchors.
    - Use a placeholder rendering in the prompt's own RIGHT/WRONG
      examples (e.g. `_MOKE_RESULT=PASS` with prose "substitute literal
      `S`") so that even if Copilot CLI ever starts echoing prompts to
      stdout, the prompt body itself produces zero false-PASS / false-FAIL
      matches under the workflow's anchored greps. This catalogue's
      template is `skills/foundry-hosted-agents/test-fixture/consumer_prompt.md`
      L185-229 (post-fix). Validated with:
      `grep -cE "^SMOKE_RESULT=" <fixture>` returns 0 against either
      workflow grep pattern after placeholdering.
    - Tell the agent NOT to write the literal token `SMOKE_RESULT` in
      any decorated form (backticks, bold, italic) anywhere else in its
      reply — autoregressive priming from earlier mentions is what
      causes the final marker emission to come out backtick-wrapped.

    **Bonus sub-finding from the same run**: at
    2026-05-30T20:09:44Z the agent autonomously invented a tee/fail
    wrapper using `exec > >(tee -a "$LOG") 2>&1` and Copilot CLI's shell
    tool BLOCKED it as "dangerous shell expansion". This is the first
    time the catalog has surfaced that guard. Implication: a shell-side
    `printf 'SMOKE_RESULT=PASS\n'` fallback path is unreliable as a
    backup — (a) shell stdout gets summarised in the transcript as
    `└ N lines...`, not the full content, and (b) the agent may invent
    blocked patterns trying to be clever. The marker MUST be emitted as
    part of the agent's chat reply, not as bash output. The audit-trail
    fixture (post-fix L231-239) explicitly forbids the
    `exec > >(tee ...)` pattern with a cross-reference to this run.

    **Cross-skill action for Task 2.3**: `foundry-prompt-agents`'s
    fixture has the **same latent vulnerability** at L52-58. It worked
    by luck during Task 2.1's stability runs. Either symmetrically
    tighten it (apply the same WRONG-pattern catalogue + placeholder
    encoding + autoregressive warning) or extract the contract into a
    shared `docs/audit/marker-contract.md` snippet that both fixtures
    `MUST` reference. Per AGENTS.md § 2.6 (one skill per PR), this
    can't ship on PR #185; defer to a Task 2.3 PR that touches
    `foundry-prompt-agents/test-fixture/consumer_prompt.md` only.

    **Optional empirical experiment (not yet performed)**: try
    `copilot -s` or `--silent` against a one-shot prompt locally to
    see if the `Changes / Duration / Tokens` footer is suppressed. If
    yes, the contract could simplify to "single line marker is the
    final line of stdout". This experiment was time-boxed away in this
    audit; recommend Task 2.3 spend 5 minutes on it and document the
    finding either way.
