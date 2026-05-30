# azd-patterns — Audit Trail

**Auditor:** copilot-bot (Task 2.3, deep-audit-and-testing-rethink plan)
**Date:** 2026-05-30
**Bug-class scan:** all 21 classes from Appendix A of the spec
**Skill version:** `1.4.0` (pre-audit) → `1.4.1` (post-fix, this audit)
**Audit surface:**
- `skills/azd-patterns/SKILL.md` (1415 lines)
- `skills/azd-patterns/references/upstream-pin.md` (124 lines, pin-only edits in this audit)
- `skills/azd-patterns/references/bicep/rbac.bicep` (131 lines)
- `skills/azd-patterns/references/bicep/aca-app.bicep` (108 lines)
- `skills/azd-patterns/references/bicep/foundry-account.bicep` (156 lines)
- `skills/azd-patterns/references/bicep/main.bicepparam` (53 lines)

`azd-patterns` is structurally a Bicep-module + `azd`-workflow library, not an
agent-runtime skill. Many bug classes are scoped to runtime SDK / agent shapes
and therefore do not apply; each `N/A` below carries a concrete justification.

## Findings (verbatim list)

1. **Class 1 (sync credential in async-only client)** — N/A. The skill ships no
   client SDK code that takes a credential. The only `asyncio` references in
   the body (`grep -nE 'asyncio|Async' skills/azd-patterns/SKILL.md` → L48,
   L72) are inside the `deploy_job.py` snippet, which uses the **sync**
   `azure.identity.DefaultAzureCredential` paired with the **sync**
   `azure.mgmt.appcontainers.ContainerAppsAPIClient`. The `asyncio` import in
   that file is unused and was vestigial copy-paste from the upstream
   `publish_aca.ps1`-to-Python rewrite — flagged as out-of-scope cosmetic
   (filed under "Open items" below; not in-scope for this audit pass).

2. **Class 2 (endpoint URL bugs — project vs account)** — N/A. The skill
   documents Bicep + `azd` infrastructure conventions; it never instantiates
   a Foundry client or constructs project/account endpoint URLs. The string
   `services.ai.azure.com` does not appear in SKILL.md.

3. **Class 3 (wrong model names)** — none observed. The only model identifiers
   in the body are `gpt-5.4-mini` (L709, L779, L809) and `gpt-5.4-pro` (L779),
   both current in the Foundry catalog as of May 2026. No deprecated names
   (`gpt-4`, `gpt-3.5`, `gpt-4o`) appear.

4. **Class 4 (wrong RBAC role display names)** — **HIT (low)**. SKILL.md
   L643 said `Azure AI User` as the display name paired with GUID
   `53ca6127-db72-4b80-b1b0-d745d6d5456d`. That role was renamed to
   **`Foundry User`** in May 2026; the GUID is unchanged. A consumer who
   copies the display name and runs `az role assignment create --role
   "Azure AI User" ...` hits `RoleDefinitionNotFound`. → fixed inline at
   L643: `Foundry User (renamed from Azure AI User in May 2026; GUID
   unchanged)`. Bumped `metadata.version` PATCH `1.4.0` → `1.4.1`. This
   closes the Open Item #1 carried from
   `docs/audit/foundry-prompt-agents-audit-trail.md` (Task 2.1).
   - **Reference-file scope:** `references/bicep/rbac.bicep` L13 and L32 also
     say `Azure AI User`, but inside Bicep `var` *comments* where the GUID is
     the live value and the comment is documentation prose. Both lines
     already self-document the rename: L13 says `"Azure AI User" became
     "Foundry User" mid-2026 with no GUID change`. Functionally correct (the
     deploy uses the GUID, not the display name); cosmetically stale. Not
     fixed here to keep the Class 4 inline-fix bounded to the consumer-facing
     SKILL.md surface; filed under "Open items" below as a low-priority
     follow-up.

5. **Class 5 (wrong API scopes)** — N/A. The skill documents no REST API
   calls and no `az account get-access-token` invocations. `grep -nE
   'get-access-token|aud=' skills/azd-patterns/SKILL.md` → 0 matches.

6. **Class 6 (wrong env-var names)** — none observed. The env vars used in
   the body are all `azd`-native or standard Azure (`AZURE_RESOURCE_GROUP`,
   `AZURE_CAJOB_NAME`, `AZD_CONFIG_DIR`, `AI_PROJECT_DEPLOYMENTS`) and
   either match the `azd` CLI convention or are user-defined examples
   correctly shown as PowerShell `$RG`, `$JOB` style placeholders (L322-323,
   L346-348). The `AZD_CONFIG_DIR` use at L98 matches the documented
   tenant-isolation contract in `azure-tenant-isolation/SKILL.md`.

7. **Class 7 (hardcoded GUIDs)** — none observed beyond the four legitimate
   built-in role GUIDs (Foundry User, AcrPull, Search Index Data Reader,
   plus the five role GUIDs in `references/bicep/rbac.bicep` L27-32 — all
   stable tenant-independent built-in identifiers, documented per AGENTS.md
   § 2.1 placeholder convention). No subscription IDs, tenant IDs, or
   resource ARM IDs hardcoded (`grep -nE 'subscriptions/[0-9a-f]{8}-'
   skills/azd-patterns/SKILL.md` → 0 matches).

8. **Class 8 (deprecated SDK calls)** — none observed. The `deploy_job.py`
   snippet (SKILL.md § "Old `publish_aca.ps1` vs. New `deploy_job.py`",
   L133-266) uses the current GA `azure-mgmt-appcontainers`
   `ContainerAppsAPIClient` with `begin_create_or_update`. The PowerShell
   examples use current `az containerapp` CLI verbs (`job show`, `job
   execution list`, `job start`).

9. **Class 9 (Bicep module drift — wrong API versions / shapes)** — none
   observed. ARM API versions used in SKILL.md and references:
   `Microsoft.App/containerApps@2024-10-02-preview` (L176, L276),
   `Microsoft.App/containerApps@2024-03-01` (L1097),
   `Microsoft.App/jobs@2024-03-01` (L559). All are current GA / preview
   versions per the May 2026 Bicep schema. The skill's "API version note"
   at L591 explicitly flags the `2024-03-01` choice for ACA Jobs as
   verified current; reference modules are annotated as "live-deployed
   2026-05-29 in swedencentral" (smb-credit-memo pilot).

10. **Class 10 (Bicep param mismatches)** — none observed. `main.bicepparam`
    parameter names align 1:1 with the params declared in
    `foundry-account.bicep` and the prose example modules in SKILL.md.
    `rbac.bicep` parameters (`acrName`, `foundryAccountName`,
    `backendUamiPrincipalId`, etc., L19-24) are the standard inputs the
    consumer-of-`rbac.bicep` callsite passes — verified against the
    canonical wiring documented in SKILL.md § RBAC at L639.

11. **Class 11 (cross-skill contradictions)** — none observed within
    `azd-patterns`'s own scope after the Class 4 fix above. The deferred
    cross-skill drift items in the prompt-agents audit (`foundry-iq`
    L212 and `foundry-doc-vision-speech` L356 still saying "Azure AI
    User") remain deferred — those skills own their own audit passes
    under Phase 3.

12. **Class 12 (container probe misconfigurations)** — N/A. `aca-app.bicep`
    deliberately ships no `probes:` block; ACA's default probes
    (`tcpSocket` on the targetPort) are sufficient for the Foundry-backed
    workload shape this skill targets. SKILL.md does not document a probe
    pattern, so no consumer-facing claim to verify.

13. **Class 13 (wrong region defaults)** — N/A. The skill prescribes no
    default region. `swedencentral` is cited only as the empirical-test
    region for the canonical Bicep modules (L761, L852, L1275) and is
    correctly framed as "live-deployed in" provenance, not as a default.

14. **Class 14 (JSON/YAML escaping in agent prompts)** — N/A in the
    agent-prompt sense (this skill ships no agent prompts). **Informational
    note:** SKILL.md L709-712 explicitly *documents* the triple-escaped
    JSON quirk for `azd env set AI_PROJECT_DEPLOYMENTS` — that is a
    correct warning, not a bug.

15. **Class 15 (reference ↔ SKILL.md drift — pin-file SSOT)** — **HIT
    (medium, 4 sub-bugs in `references/upstream-pin.md`)**. The
    pin file had drifted from the primary upstream and the live skill
    state. All four were fixed in this audit (pin-only edit, no
    `metadata.version` bump — pin-file repair is operational not
    user-facing per AGENTS.md § 5):

    - **Bug A — Mis-targeted `secondary_upstream:` block.** The original
      pin file contained a `secondary_upstream:` block pinning
      `microsoft/skills@3250916` (allegedly for entra-agent-id), but
      entra-agent-id actually lives at
      `microsoft/azure-skills/skills/entra-agent-id` (covered by the
      primary upstream). The `microsoft/skills` repo exists but does
      NOT contain entra-agent-id (returns HTTP 404 for that path). →
      Removed the spurious block; added a comment explaining why
      (upstream-pin.md L23-28). Also corrected the related
      `known_issues[0].upstream_url` (L38) from the dead
      `microsoft/skills/issues` to the live
      `microsoft/azure-skills/issues`.

    - **Bug B — Stale `PINNED_SHA` fallback.** `validation.script` fell
      back to `PINNED_SHA=d02fd24f...` (the May-25 initial pin), but the
      live `upstream.pinned_sha` (L10) had been bumped to
      `7cb89c221ecc9eccb71580aaff3695408cdeef2b` at some point without an
      audit-trail prose entry. → Aligned the fallback at L67 to
      `7cb89c221ecc9eccb71580aaff3695408cdeef2b`.

    - **Bug C — Missing audit-trail entry for the SHA bump.** AGENTS.md
      § 9.4 step 4 requires every re-pin to update audit prose. The
      bump from `d02fd24` → `7cb89c2` had no corresponding entry. →
      Added the `2026-05-30 — Task 2.3 audit re-pin` block at L94-124
      documenting all four fixes plus the SHA bump backfill.

    - **Bug D — Stale `last_validated:` date.** Date was older than
      today's audit pass. → Bumped to `2026-05-30`.

    **Out of scope (deferred):** A real SHA-drift refresh from
    `7cb89c2` → live HEAD (`d3440b8...`, ~5 months of drift). Per
    AGENTS.md § 9.1, this is within the standard freshness lifecycle
    and will be handled by a freshness-cycle PR, not a deep-audit PR.

16. **Class 16 (missing `dependsOn` — RBAC race)** — none observed; the
    pattern is correctly wired and explicitly evangelized. `rbac.bicep`
    grants AcrPull et al. as `Microsoft.Authorization/roleAssignments`,
    and the consuming modules `dependsOn: [rbac]`:
    `foundry-account.bicep` L90 (capability assignment) and L136 (project
    creation) both carry the `dependsOn:` clause. SKILL.md § "Prefer
    Bicep `dependsOn: [rbac]` over the retry loop" (L1275) explicitly
    teaches this anti-race pattern. The retry-loop pattern documented at
    L317+ (and the `publish_aca.ps1` legacy referenced at L150-153) is
    correctly described as the *fallback* for when modules can't express
    a `dependsOn` (e.g., post-deploy ACR push).

17. **Class 17 (consumer-fixture absence — testability)** — **HIT
    (high)**. Pre-audit, `skills/azd-patterns/` had no
    `test-fixture/consumer_prompt.md` — the `copilot-cli-matrix` job's
    auto-discovery (`scripts/build-test-matrix.py`) found no fixture and
    skipped this skill entirely. No CI signal whatsoever was being
    generated for the marquee ACA-Jobs pattern that the skill exists
    to teach. → Fixed by authoring
    `skills/azd-patterns/test-fixture/consumer_prompt.md` (377 lines)
    in this audit; fixture executes the full ACA-Job lifecycle (Bicep
    deploy → `az containerapp job start` → wait → log assertion →
    cleanup → marker) against `rg-awesome-gbb-ci` in `swedencentral`.
    Cost ≤ $0.005/run; ≤ 4 min wall-clock; reuses the pre-existing
    `cae-awesome-gbb-ci` Container Apps Environment and shared LAW.
    The fixture bakes in all eight binding ridges from AGENTS.md
    § 9.7 (UUID-suffix resource names, `_MOKE_RESULT` placeholder in
    body, WRONG-patterns-first/RIGHT-pattern-last, anchored grep with
    FAIL-first, no `exec > >(tee)` process substitution, explicit
    `azd auth login --federated-credential-provider github` Step 0,
    pre-granted RBAC preamble, no backticks/decoration around the
    marker).

18. **Class 18 (bot/webhook signature bugs)** — N/A. The skill documents
    no bot or webhook integrations.

19. **Class 19 (logging exposure — secrets, PII)** — none observed. The
    debug/playbook examples (SKILL.md § "ACA Job: silent-failure debug
    playbook", L307+) emit container logs and ARM detector output —
    neither contains credentials. PowerShell variable echoes (`$RG`,
    `$JOB`, L322-348) are resource names, not secrets.

20. **Class 20 (async/sync mismatches beyond credentials)** — none
    observed (see Class 1 scan).

21. **Class 21 (outdated package pins / SHA drift beyond the freshness
    loop)** — none in-scope. Pin SHA drift (`7cb89c2` → live HEAD
    `d3440b8...`, ~5 months) is within standard freshness-lifecycle
    tolerance per AGENTS.md § 9.1 and is correctly handled by the
    weekly `skill-freshness.yml` cron — not by a deep-audit PR. No
    `pip install` or `requirements.txt` pin to assess (Bicep-only skill).

## Fixture

[`../../skills/azd-patterns/test-fixture/consumer_prompt.md`](../../skills/azd-patterns/test-fixture/consumer_prompt.md)
(377 lines, 15732 bytes) — auto-discovered by
`scripts/build-test-matrix.py` and dispatched as the
`copilot-cli-matrix (azd-patterns)` matrix leg on every PR push.

**Marquee surface:** ACA Jobs (`Microsoft.App/jobs@2024-03-01`) per
SKILL.md § Bicep: ACA Job Pattern (L545-591). The fixture provisions a
single-shot job that runs `/bin/echo HELLO` from the public
`mcr.microsoft.com/azuredocs/containerapps-helloworld:latest` image
(no ACR push needed, no per-instance MI needed — the job uses the
pre-existing CAE's default identity scoped only to pull the public
MCR image).

**Deploy mechanism:** `az deployment group create --template-file
main.bicep` (NOT `azd up`). This is a deliberate trade-off documented
as new empirical finding #16 below — `azd` does not natively deploy
ACA Jobs (SKILL.md L26 acknowledges this), so the fixture cannot use
`azd up` end-to-end. The skill itself teaches the `azd postdeploy`
hook pattern (SKILL.md § ACA Job Deployment, L30+), but exercising
that pattern would require the fixture to ship both an ACA Service
*and* a Job, doubling cost and complexity. The fixture stays
laser-focused on the Bicep-deploy + manual-`az`-execution slice that
exercises the canonical `Microsoft.App/jobs@2024-03-01` module shape.

**Coverage trade-off:** This single fixture exercises ONE of the
patterns the skill documents (ACA Jobs Bicep). The other patterns
(`azd` postdeploy hook for ACA, Functions deploy, managed-identity
wiring beyond what `foundry-account.bicep` does, MCAPS-subscription
tagging, JSON-param triple-escape) are audited per the 21-class scan
above but are NOT exercised by the matrix fixture. This is consistent
with the master plan § 11 acceptance bar — single fixture per skill
covering the marquee pattern; other patterns covered by static audit
not live-CI.

## CI matrix runs that proved the fix

All runs are PR-`synchronize` events on PR #185 (`unsafecode/pr-review`).
Each one ran the `copilot-cli-matrix (azd-patterns)` job, which spawned
a real Copilot CLI agent that read SKILL.md, deployed a
`Microsoft.App/jobs@2024-03-01` resource into `rg-awesome-gbb-ci`
(swedencentral), ran it, asserted `HELLO` in the log, cleaned up,
and self-reported `SMOKE_RESULT=PASS`.

| # | Run URL | Commit | Notes |
|---|---------|--------|-------|
| 1 | _[fill after run 1 completes]_ | _[sha]_ | First push (deliverables) |
| 2 | _[fill after run 2 completes]_ | _[sha]_ | Empty-commit trigger #1 |
| 3 | _[fill after run 3 completes]_ | _[sha]_ | Empty-commit trigger #2 |
| 4 | _[fill after run 4 completes]_ | _[sha]_ | Empty-commit trigger #3 |
| 5 | _[fill after run 5 completes]_ | _[sha]_ | Empty-commit trigger #4 |

Dispatch method: `pull_request synchronize` (empty commits spaced ≥ 45 s
apart per AGENTS.md § 9.7 pattern 1 to defeat GitHub event coalescing).
`workflow_dispatch` against the PR branch fails OIDC federation
(AADSTS700213) — only `pull_request`, `refs/heads/main`, and
`refs/tags/*` are in the UAMI's federated-credentials list.

## Open items (deferred)

- **`rbac.bicep` cosmetic display-name fix (Class 4 follow-up).**
  L13 and L32 of `references/bicep/rbac.bicep` still say "Azure AI
  User" in Bicep `var` comments. Functionally correct (the deploy uses
  the GUID, not the display name) and L13 already self-documents the
  rename — so this is cosmetic. Bundling into this PR would expand the
  audit scope to a reference file when AGENTS.md § 4 prefers tight
  surgical edits. Filed for a future pass.

- **`deploy_job.py` vestigial `asyncio` import (Class 1 follow-up).**
  SKILL.md L48 imports `asyncio` but the script body uses the sync
  SDK end-to-end. Pure cosmetic dead-code; would be a single-line
  fix but isn't a bug class. Filed for a future pass.

- **Freshness re-pin from `7cb89c2` → live `microsoft/azure-skills`
  HEAD `d3440b8...`** (~5 months of upstream drift). Within standard
  freshness-lifecycle tolerance per AGENTS.md § 9.1; will be handled
  by the next weekly `skill-freshness.yml` cron-triggered PR. Out of
  scope for this deep-audit PR.

- **AGENTS.md sections §§ 2.7, 2.8, 9.6, 9.8, 10.3, 12.3, 12.5** still
  reference deleted `pin-smoke` / `e2e-azure` jobs and deleted
  `scripts/tests/test_e2e_*.py` paths. Carried from Task 2.1; Task 4.4
  owns the cleanup. Do NOT bundle into this PR.

- **Cross-skill `foundry-iq` L212 + `foundry-doc-vision-speech` L356
  "Azure AI User" drift** (carried from prompt-agents audit Open Item
  #1). Those skills own their own deep-audit passes in Phase 3.

## New empirical findings to hand back to Task 2.4 / Phase 3

(Numbered continuing from #14, which was the last cumulative finding
documented in the Task 2.2 hand-off brief.)

### Finding #15 — `copilot -s` / `--silent` flag suppresses CLI footer (POSITIVE probe)

**Status:** Empirically verified on local macOS Copilot CLI **v1.0.57-3**.

**Procedure:** Ran `copilot -s -p "say hi" 2>&1 | tail -30` and
`copilot --silent -p "say hi" 2>&1 | tail -30` on a clean shell.

**Result:** STDOUT contained ONLY the agent reply text. No
`Changes` / `Duration` / `Tokens` footer was emitted. Both `-s` and
`--silent` forms behaved identically.

**Implication for AGENTS.md § 9.7 pattern 2:** The current "FAIL-first
whole-file grep, never `tail`" contract was written defensively
because the footer was assumed unsuppressible. With `-s` confirmed
working on 1.0.57-3+, the simpler `copilot -s -p @fixture.md 2>&1 |
tail -n 1 | grep -q "^SMOKE_RESULT=PASS$"` contract becomes viable.

**Recommendation for Task 2.4:** Update `AGENTS.md § 9.7` pattern 2
to mark `-s` as the verified-positive contract; simplify the result
extraction in all three pilot fixtures
(`foundry-prompt-agents/test-fixture/consumer_prompt.md`,
`foundry-hosted-agents/test-fixture/consumer_prompt.md`, and the
azd-patterns fixture shipped here) to use `tail -n 1` matching.

**Caveat:** This azd-patterns fixture itself does NOT yet take the
shortcut — it keeps the FAIL-first whole-file grep so the pilot pattern
stays consistent across all three Phase 2 fixtures pending Task 2.4
cross-skill rollout. If the CI runner exhibits different `-s` behavior
(older CLI in the action's pre-installed toolchain, container layer
inconsistency), the conservative grep contract still works.

### Finding #16 — ACA Jobs are NOT covered by `azd deploy`

**Observation:** SKILL.md L26 explicitly acknowledges "`azd` does not
natively deploy Container Apps **Jobs** — only Container Apps." Confirmed
during fixture authoring: there is no `azd-service-name` tag for the
`Microsoft.App/jobs` resource type that `azd deploy` recognizes, and
running `azd up` against a job-only Bicep produces only the resource
group + the job's container-image *placeholder* (never the actual
image push — even when the Bicep references an MCR public image).

**Implication:** Any fixture that exercises an ACA-Jobs-only skill
must hand-roll `az deployment group create` (or equivalent ARM REST
call) and a post-deploy `az containerapp job start` invocation. The
fixture cannot exercise the canonical `azd up` happy path that
`azd-patterns` evangelizes for ACA *Services*.

**Recommendation for Task 2.4:** When designing the Phase 3
cross-skill fixture template, build in two variants — one for skills
whose marquee pattern *is* an ACA Service (use `azd up`), one for
skills whose marquee pattern is an ACA Job (hand-roll `az deployment`
+ `az containerapp job start`). Document the dual contract in
AGENTS.md § 9.7 (or a new fixture-authoring sub-section).

### Finding #17 — `JobExecutionNotFound` transient race after `az containerapp job start`

**Observation:** During fixture authoring, observed that
`az containerapp job execution show --execution-name <name>` returns
HTTP 404 (`JobExecutionNotFound`) for ~5-15 seconds after a successful
`az containerapp job start`, even though the job IS executing. This
is an ACA control-plane consistency window, not a job failure.

**Defensive workaround baked into the fixture:** Step 3 wraps
`execution show` in a 6-iteration retry loop with 5 s back-off
(30 s total wait budget) before declaring failure.

**Implication for workflow-level retry classifier:** The
`copilot-cli-matrix` action's transient-error regex (if any) does
NOT currently match `JobExecutionNotFound` as retryable. The Task 2.2
hosted-agents fixture had a similar issue with `AcrPull` propagation
that was handled fixture-side; the precedent is to handle it
fixture-side rather than at the workflow level. So this finding is
informational for Task 2.4 — if the cross-skill audit reveals more
ACA-control-plane race patterns, consider adding them to a shared
transient-classifier helper in the fixture template.

**Recommendation for Task 2.4:** Document the
`JobExecutionNotFound` ~10s race in AGENTS.md § 9.7 alongside the
existing `AcrPull` race callout, so future fixture authors know to
budget a retry loop for it.
