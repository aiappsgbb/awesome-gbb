# Deep Audit + Testing Rethink — Design Spec

**Date:** 2026-05-30
**Status:** Approved (design phase). Implementation plan pending via writing-plans.
**Branch:** `unsafecode/pr-review`

---

## 1 · Problem

The `aiappsgbb/awesome-gbb` catalog (27 skills) ships SKILL.md files that consumers copy-paste into real Azure work. Two recent failures show the current quality bar is inadequate:

1. **Latent bug class survived CI for months.** Six MID-I bugs in `foundry-hosted-agents` (sync `AzureCliCredential()` paired with async `FoundryChatClient`) shipped to consumers and stayed in the catalog through three PR cycles. They were caught by hand during a deep review of PR #184, not by any CI gate.
2. **Parallel test code drifts from SKILL.md.** `scripts/tests/test_e2e_foundry_toolbox.py` L41-49 instantiates `FoundryChatClient` with a sync credential — exactly the bug the catalog's own lint catches inside `skills/` but ignores in `scripts/tests/`. The test passes. It proves the SDK imports. It does not prove the SKILL works. This is the **smoking gun**: hand-written test code that mirrors but contradicts the SKILL.

Both failures share a root cause: the catalog's testing surface is **shaped like a library's**, not shaped like the catalog's actual product (instructions humans copy verbatim). Pytest files, AST lints, and pin-validation scripts answer "does the SDK import?" — they cannot answer "if a consumer follows this SKILL, does the documented outcome happen?"

The catalog has 27 skills. A bug like the smoking gun could live in any of them. We have no systematic way to find them.

---

## 2 · Goals + Non-Goals

**Goals**
- Find latent bugs across all 27 skills via a deep, one-shot review.
- Replace the testing mechanism with one that validates **consumer outcomes** — a simulated consumer follows the SKILL and either achieves the documented result or doesn't.
- Make the new testing mechanism the sole runtime test surface. No parallel hand-written test code.
- Land the audit fixes and the new test harness in production within the constraints of the existing CI infrastructure (`rg-awesome-gbb-ci`, OIDC UAMI, weekly cron).

**Non-Goals**
- Not adding more pytest files anywhere. None. Ever.
- Not adding an LLM-as-judge layer.
- Not rebuilding `skill-freshness.yml`, `skill-validation.yml`, or the audit-tag enforcement in `automation-pr-gate.yml` — they keep working.
- Not changing the source-of-truth model (`plugin.json` + `skills/` auto-discovery).

---

## 3 · Macro Architecture (two parallel sub-projects)

The work splits cleanly into two sub-projects that proceed in parallel and converge at a pilot gate.

```
                      Sub-Project A (one-shot)             Sub-Project B (recurring)
                      ┌────────────────────────┐           ┌────────────────────────┐
                      │ DEEP AUDIT             │           │ TESTING REBUILD        │
                      │ 25 skills via agent    │           │ Copilot-CLI-as-test    │
                      │ army (2 stay manual)   │           │ + pre-pilot smoke      │
                      └────────────┬───────────┘           └────────────┬───────────┘
                                   │                                    │
                                   │   converges at pilot (3 skills)    │
                                   ▼                                    ▼
                      ┌──────────────────────────────────────────────────────────────┐
                      │ PILOT: foundry-prompt-agents, foundry-hosted-agents,         │
                      │         azd-patterns. Each gets audit AND new Copilot-CLI    │
                      │         test. If pilot green → full rollout. If red → halt.  │
                      └──────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
                      ┌──────────────────────────────────────────────────────────────┐
                      │ ROLLOUT WAVES                                                │
                      │ Remaining 22 skills via audit-agent army. Each agent owns    │
                      │ one skill end-to-end (audit + fix + test fixture + PR).      │
                      │ Capped at 5 concurrent PRs.                                  │
                      └──────────────────────────────────────────────────────────────┘
```

**Load-bearing assumption:** Copilot CLI in GHA can authenticate to a Foundry-hosted `gpt-5.4-mini` deployment (Cognitive Services OpenAI User RBAC on `aif-awesome-gbb-ci`) and act as its own brain. If this is false, the entire design collapses. A pre-pilot smoke workflow validates this before pilot scope is touched.

---

## 4 · Sub-Project A — Deep Audit

### 4.1 · Mandate

For every skill in scope (25 of 27 — `citadel-hub-deploy` and `foundry-vnet-deploy` are too large for the agent to safely refactor and stay manual), one `general-purpose` sub-agent is dispatched with a single end-to-end mandate:

1. Read the skill and all its `references/`
2. Cross-check SKILL.md against every external citation (PyPI versions, GitHub SHAs, Azure docs URLs)
3. Identify all bugs from the **21-item bug-class catalog** (see Appendix A)
4. Apply fixes directly to SKILL.md and references — surgical, no normalization
5. Write the test fixture `skills/<name>/test-fixture/consumer_prompt.md`
6. Open a PR scoped to `skills/<that-skill>/` + `docs/audit/<that-skill>-audit-trail.md`
7. Pass all CI gates including the new Copilot-CLI test on the audited skill

The agent owns the skill from discovery through PR-merge-ready. No separate "discovery → human triage → fix" handoff.

### 4.2 · Anti-Damage Safety Gates

The audit agent operates inside a fenced playground. Every gate is enforced by CI, not by trust.

| Gate | Enforced by | What it prevents |
|---|---|---|
| **Single-skill diff scope** | `automation-pr-gate.yml` extension | Agent touching any file outside its assigned skill |
| **Anti-normalization clause** in agent prompt (verbatim) | Prompt + reviewer eyeball | Repeat of the `fsi.md` IRS-prefix scrub disaster |
| **Audit-trail file required** | `automation-pr-gate.yml` | Hidden / undocumented changes |
| **PR commit tags `[skill-rewrite] [audit-2026-XX]`** | `automation-pr-gate.yml` | Bypass of the multi-skill-edit gate |
| **`metadata.version` PATCH bump per AGENTS.md §5** | `skill-validation.yml` | Version drift |
| **Copilot-CLI test green** | `skill-test.yml` (replacement matrix job) | Bugs the agent introduced or missed |

### 4.3 · Audit-Trail Schema

Every audit PR ships `docs/audit/<skill-name>-audit-trail.md` with one entry per finding:

```yaml
- finding_id: <skill>-001
  bug_class: <one of the 21>
  severity: low | medium | high
  evidence_url: https://github.com/.../blob/<sha>/...
  fix_summary: <one paragraph>
  fixed_in_commit: <sha>
```

This is the post-merge audit record. It is read by humans when something regresses, and by the next audit cycle to know what was checked.

### 4.4 · Concurrency Cap

At most **5 audit-agent PRs open at any time**. New agents start as earlier ones merge. This bounds reviewer load and CI runner consumption without artificially serializing the work.

---

## 5 · Sub-Project B — Testing Rebuild

### 5.1 · The Hard Rule

**One mechanism. The Copilot CLI run IS the test. It is the only judge of success.**

No pytest. No Python assertion helpers. No YAML post-condition runner. No external "did resource X get created" checker. If Copilot CLI can follow the SKILL and produce the documented outcome, the SKILL works. If not, it doesn't.

### 5.2 · Per-Skill Test Harness

For each skill in scope, exactly one new file ships:

```
skills/<name>/test-fixture/consumer_prompt.md
```

This file contains a single prompt that Copilot CLI receives. Pattern:

```markdown
You are a developer consuming the `<skill-name>` skill from the awesome-gbb catalog.

Follow that skill's instructions to accomplish: <one specific consumer task>

When you finish, self-verify:
- Did the documented outcome occur?
- Are there any errors or unexpected behavior?
- Did you create resources? If yes, tear them down before exiting.

If everything worked, exit 0.
If anything failed, exit non-zero with a one-line reason.
```

The fixture is the only per-skill testing surface. Anything that needs to be checked must be checkable by Copilot CLI itself from inside the SKILL.

### 5.3 · The CI Matrix Job

`skill-test.yml` gains one new job, `copilot-cli-matrix`, that fans out across all skills with a `test-fixture/consumer_prompt.md`. The job's body is one bash invocation per skill:

```yaml
- name: Run Copilot CLI consumer test for ${{ matrix.skill }}
  env:
    # Exact env-var names depend on Copilot CLI's Foundry-routing config;
    # nailed down during implementation against the released CLI version.
    COPILOT_MODEL_ENDPOINT: ${{ secrets.AZURE_AI_ENDPOINT }}
    COPILOT_MODEL_DEPLOYMENT: gpt-5.4-mini
  run: |
    copilot plugin marketplace add .
    copilot plugin install awesome-gbb@awesome-gbb
    timeout 20m copilot run --prompt-file skills/${{ matrix.skill }}/test-fixture/consumer_prompt.md
```

The CI checks **only the process exit code**. The full transcript is archived as a build artifact for human forensics. No script parses it.

### 5.4 · Pre-Pilot Auth Smoke

Before any pilot skill runs, `copilot-cli-foundry-auth-smoke.yml` validates the load-bearing assumption (Copilot CLI authenticates to Foundry-hosted model):

```yaml
- run: |
    copilot run --prompt "What is 2 + 2? Respond with just the number, then exit 0."
```

If this is red, the pilot cannot proceed. The Foundry-model-routing path either works or it doesn't, and we need to know before burning weeks of design assuming it does.

### 5.5 · What Stays, What Goes

**Deleted:**
- `scripts/tests/test_e2e_prompt_agents.py`
- `scripts/tests/test_e2e_foundry_toolbox.py` (the smoking gun itself)
- `scripts/tests/test_e2e_voice_live.py`
- `skill-test.yml` `e2e-azure` job (replaced by `copilot-cli-matrix`)
- `skill-test.yml` `pin-smoke` job (covered by `pin-validation.yml`, which is the deps-pinning exception)

**Survives — different layer, not a parallel test:**
- `pin-validation.yml` — re-runs `validation.script` (pip install + import). This is **pin freshness**, the user-accepted deps-pinning exception. It does not validate the SKILL; it validates that the pinned upstream is still resolvable.
- AST lints in `scripts/validate-skills.py` (including `validate_no_sync_cred_in_foundry_chat_client` and any future ones) — **pre-flight filters** that catch known bug classes before burning Copilot-CLI-on-Azure cycles. They are statically-analyzed guardrails, not runtime tests.
- `skill-validation.yml` (frontmatter parse, description ≤ 1024, forbidden strings) — structural lint.
- `skill-freshness.yml` weekly drift detection.
- `automation-pr-gate.yml` mass-edit invariants.

**The smoking gun's lesson, codified for the future:** any proposal to "add a Python test that exercises the SDK directly" is rejected by reference to `test_e2e_foundry_toolbox.py` L41-49. Hand-written test code drifts from SKILL.md and provides false confidence. The only test that proves the SKILL works is the SKILL being followed.

---

## 6 · Pilot Scope

Three skills validate the entire design before any rollout:

| Skill | Why it's in the pilot | Test fixture summary | Self-verify hook |
|---|---|---|---|
| **foundry-prompt-agents** | Simplest Azure surface — single API call, no container, no Bicep | "Create a `PromptAgentDefinition` named `gbb-pilot-${run_id}` in `aif-awesome-gbb-ci`, invoke once, delete." | Agent returned text + cleanup confirmed |
| **foundry-hosted-agents** | SSOT-heavy (canonical `FoundryChatClient`, container deploy via `azd`, the bug class that started this) | "Bootstrap a container agent using the canonical `FoundryChatClient`, `azd deploy` it to `cae-awesome-gbb-ci`, send one chat turn, `azd down`." | `azd deploy` exit 0 + non-empty response + clean teardown |
| **azd-patterns** | Pattern library, no runtime entry point — proves the fixture can exercise composable modules | "Provision a minimal ACA app composing the library's modules (placeholder image, `azd-service-name` tag, ACR Pull RBAC with `dependsOn`). HTTP probe. `azd down`." | `azd up` exit 0 + HTTP probe passes + clean teardown |

**Pilot exit criteria:** all three skills audit-clean (zero new bugs found OR all bugs fixed and re-tested), all three Copilot-CLI tests green for 5 consecutive runs (PR-gate, weekly cron, three manual dispatches). Only then does the rollout to the remaining 22 begin.

**Pilot wrinkle for `azd-patterns`:** because it's a pattern library (not a deployment recipe), the fixture prompt must include a minimal consumer scenario (a tiny ACA app + Bicep that composes the library's modules). The fixture proves the library's patterns are correctly documented by exercising them end-to-end.

---

## 7 · Rollout (after pilot is green)

22 skills remain (27 total − 3 pilot − 2 issue-only). Each goes through the **same audit agent** that did Sub-Project A's discovery, now extended with one more responsibility: write the test fixture for the skill being audited.

```
For each of 22 skills:
    Spawn 1 general-purpose agent with mandate:
        1. Audit the skill (Section 4 mandate)
        2. Write skills/<name>/test-fixture/consumer_prompt.md
        3. Open PR with all changes
        4. PR's copilot-cli-matrix job must run green for that skill
```

The audit agent and the fixture author are deliberately the same context. The agent that just spent hours understanding the skill writes the test for it — the per-skill investigation is reused, not thrown away.

**Concurrency cap: 5 open audit PRs at any time.** New agents start as earlier ones merge.

**Issue-only skills (`citadel-hub-deploy`, `foundry-vnet-deploy`):** stay manual. Their multi-resource greenfield deploys exceed both CI budget and the agent's safe-edit envelope. Status quo per AGENTS.md §9.8.

---

## 8 · Cost, Anti-Flake, Circuit Breaker

### 8.1 · Cost

- Per-skill hard timeout: **20 min** (covers `azd up` + a few model turns + `azd down`)
- Per-run Foundry token cap enforced at the deployment quota layer (not arbitrary code)
- Ephemeral resource naming convention: `${skill}-${run_id}` with `if: always()` teardown step
- Weekly cost telemetry issue opened by a new workflow `copilot-cli-cost-summary.yml` (token spend per skill, ACA minutes per skill)

### 8.2 · Run Cadence

- **PR-gated** on any PR touching `skills/<name>/**` → that skill's test runs
- **Weekly cron** on `main` → all skills run serially (catches upstream drift in SDKs and Azure APIs)
- **Manual dispatch** to re-run a quarantined skill after fix

### 8.3 · Anti-Flake (Pragmatic Stance)

When a Copilot-CLI run fails, the cause is one of:

1. Real SKILL bug → block merge (the system working as designed)
2. Transient Azure error (throttle, region capacity, slow propagation) → should not block
3. Foundry model hallucination → rare with low-temp + clear instructions, but real

**Policy:** 1 auto-retry on classified-transient failures only. Classification is a small regex set matched against the run's stderr / transcript tail. Initial set (extensible):

- `429\b` / `TooManyRequests` / `Throttle`
- `503\b` / `ServiceUnavailable`
- `Conflict.*provisioning` (concurrent ACA revision races)
- `capacity.*not available` (Foundry region capacity)
- `connection reset` / `EOF` during `azd deploy`

All other failures: no retry, surface immediately. Adding a new regex requires a PR (auditable).

### 8.4 · Quarantine

After 3 consecutive failed runs on `main` for a single skill, GHA auto-opens an issue (`🔥 Quarantine: <skill>`) and disables that skill's matrix entry.

**Disable mechanism:** the matrix generator (a small `scripts/build-test-matrix.py` step that produces the `skills` list for the `copilot-cli-matrix` strategy) reads `.github/quarantine.yml` — a list of currently-quarantined skill names — and excludes them. The fixture file stays put. Re-enabling a skill is a one-line PR removing it from `quarantine.yml`. The quarantine issue links to that PR template.

---

## 9 · Component Inventory (what gets built / deleted)

### 9.1 · New files

| File | Purpose |
|---|---|
| `.github/workflows/copilot-cli-foundry-auth-smoke.yml` | Pre-pilot auth smoke |
| `.github/workflows/copilot-cli-cost-summary.yml` | Weekly cost telemetry issue |
| `skills/<name>/test-fixture/consumer_prompt.md` | One per skill in scope (25 total over pilot + rollout) |
| `docs/audit/<name>-audit-trail.md` | One per skill audited (25 total) |
| `docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md` | This document |

### 9.2 · Modified files

| File | Change |
|---|---|
| `.github/workflows/skill-test.yml` | Delete `pin-smoke` and `e2e-azure` jobs. Add `copilot-cli-matrix` job. |
| `.github/workflows/automation-pr-gate.yml` | Extend single-skill-scope check to recognize `[audit-2026-XX]` tag and audit-trail file requirement. |
| `AGENTS.md` | Rewrite §§ 2.7-2.9, 9.6, 9.8, 12.5 to reflect new testing model. Remove references to deleted artifacts (pytest tests, `e2e-azure` job, `pin-smoke` job, T2/T3 distinction). |
| `scripts/validate-skills.py` | No code change; add a section header confirming AST lints survive as pre-flight filters. |

### 9.3 · Deleted files

| File | Reason |
|---|---|
| `scripts/tests/test_e2e_prompt_agents.py` | Pytest replaced by Copilot-CLI fixture |
| `scripts/tests/test_e2e_foundry_toolbox.py` | Smoking gun. Pytest replaced by Copilot-CLI fixture. |
| `scripts/tests/test_e2e_voice_live.py` | Pytest replaced by Copilot-CLI fixture |
| `scripts/tests/` directory | Empty after deletions. Removed. |

---

## 10 · Data Flow (single test run)

```
PR opened touching skills/foundry-hosted-agents/SKILL.md
    │
    ▼
[skill-validation.yml]  ──►  Frontmatter, description, forbidden strings
    │                        AST lints (incl. sync-cred check)
    │
    ▼
[automation-pr-gate.yml]  ──►  Single-skill scope, commit tags, no normalization
    │
    ▼
[pin-validation.yml]  ──►  pip install + import succeeds (deps-pinning exception)
    │
    ▼
[skill-test.yml :: copilot-cli-matrix :: foundry-hosted-agents]
    │
    ├─►  azure/login@v2 OIDC                                      ↓
    ├─►  copilot plugin marketplace add . && copilot plugin install
    ├─►  copilot run --prompt-file skills/foundry-hosted-agents/test-fixture/consumer_prompt.md
    │       │
    │       ├─►  Copilot CLI reads SKILL.md
    │       ├─►  Copilot CLI executes per SKILL (deploys container, sends chat turn, tears down)
    │       └─►  Copilot CLI self-verifies and exits 0 or non-zero
    │
    ├─►  Transcript uploaded as artifact (forensics only)
    │
    ▼
exit 0 → PR mergeable
exit non-zero → retry once if classified transient, else surface failure
```

---

## 11 · Risks + Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Foundry-routing auth fails in GHA** | Medium | Catastrophic (kills the design) | Pre-pilot smoke workflow validates this first. If red, halt and rethink. |
| **Copilot CLI behavior non-deterministic, makes test flaky** | Medium | High | Pragmatic flake stance: 1 retry on transients, quarantine after 3 fails. Prompt fixtures use specific, single-task language. |
| **Audit agent introduces normalization damage despite verbatim clause** | Low | High (fsi.md repeat) | CI single-skill scope + reviewer eyeball + per-agent prompt repeats the §4 anti-normalization clause verbatim. |
| **20-min timeout insufficient for some skills** | Low | Medium | Per-skill timeout override via the matrix entry (`timeout-minutes` in `skill-test.yml`, capped at 30 min). If a skill genuinely needs more, that's a skill-design signal. |
| **22 simultaneous audit PRs saturate reviewer bandwidth** | Medium | Medium | Concurrency cap of 5 enforced via GHA matrix `max-parallel`. |
| **`azd-patterns` fixture can't exercise the whole pattern surface** | Medium | Low | Fixture covers the most-used patterns. Others audited but not fixture-tested in the first rollout wave. Add to backlog. |

---

## 12 · Open Questions (resolved during brainstorming)

For traceability:

1. ~~Combine audit + testing rebuild or sequence?~~ → Parallel sub-projects, pilot gate.
2. ~~Consumer-outcome bar vs structural?~~ → Consumer-outcome.
3. ~~Shared infra vs per-skill?~~ → Shared `rg-awesome-gbb-ci`.
4. ~~Sub-agent type?~~ → `general-purpose`, one per skill.
5. ~~Copilot CLI as test runner?~~ → Yes.
6. ~~Foundry-routing or GHCP entitlement?~~ → Foundry-hosted `gpt-5.4-mini`.
7. ~~Rollout sequence?~~ → Pilot 3 → waves of 5 → option C (agent owns end-to-end).
8. ~~Pytest belt-and-suspenders?~~ → No. Deleted outright.
9. ~~AST lints?~~ → Kept as pre-flight filters.
10. ~~Pre-pilot auth smoke?~~ → Yes.
11. ~~Anti-flake?~~ → Pragmatic.

---

## Appendix A · 21-Item Bug-Class Catalog (drives audit agent mandate)

1. Credential type bugs (MID-I) — sync credential in async-only client
2. Endpoint URL bugs (MID-G project vs account)
3. Wrong model names
4. Wrong RBAC role names
5. Wrong API scopes
6. Wrong env-var names
7. Hardcoded GUIDs
8. Deprecated SDK calls
9. Bicep module drift
10. Bicep param mismatches
11. Cross-skill contradictions
12. Container probe misconfigurations
13. Wrong region defaults
14. JSON/YAML escaping in agent prompts
15. Reference ↔ SKILL.md drift
16. Missing `dependsOn` (RBAC race)
17. Tool wrapper type mismatches (dict vs Pydantic)
18. Bot/webhook signature bugs
19. Logging exposure (secrets, PII)
20. Async/sync mismatches beyond credentials
21. Outdated package pins (beyond what the freshness loop catches)

---

## Appendix B · The Smoking Gun (Exhibit A — Why This Whole Spec Exists)

`scripts/tests/test_e2e_foundry_toolbox.py` L41-49:

```python
credential = AzureCliCredential()  # SYNC
client = FoundryChatClient(  # ASYNC-ONLY
    endpoint=ENDPOINT,
    credential=credential,
    deployment_name=DEPLOYMENT,
)
```

This is the same bug the catalog's own AST lint catches inside `skills/`. The lint scans `skills/`. It does not scan `scripts/tests/`. The test passes. It proves the SDK imports. It does not prove the SKILL works.

This file is the reason for the entire Sub-Project B rewrite. Hand-written test code that mirrors but contradicts the SKILL is worse than no test code, because it provides false confidence. The Copilot-CLI-as-test mechanism makes this class of drift structurally impossible: there is no parallel test code to drift from.
