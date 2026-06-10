# Task 2.1 — `foundry-prompt-agents` Pilot Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Task 2.1 of the deep-audit + testing-rethink master plan
([`2026-05-30-deep-audit-and-testing-rethink.md`](2026-05-30-deep-audit-and-testing-rethink.md))
end-to-end: a 21-bug-class audit of `foundry-prompt-agents`, a Copilot-CLI
consumer-prompt fixture that exercises the skill against real Azure, a
`copilot-cli-matrix` CI job that drives it, and 5 consecutive green CI
runs proving stability.

**Architecture:** This task is **pure validation infrastructure**, not a
code change. The audit-trail file documents what we scanned. The
consumer-prompt fixture is the executable test (a Copilot CLI agent reads
SKILL.md, executes its instructions against real Foundry, self-verifies).
The matrix job in `skill-test.yml` drives one runner per fixture-bearing
skill. The existing `pin-smoke` + `e2e-azure` jobs are NOT touched here
— Phase 4 of the master plan deletes them after the new matrix proves
itself across the catalog.

**Tech Stack:** Bash + GitHub Actions matrix, Copilot CLI 1.0.57-2 (`npm
install -g @github/copilot`, `copilot -p`), Azure OIDC federated UAMI
(`AZURE_CLIENT_ID` / `AZURE_TENANT_ID` / `AZURE_SUBSCRIPTION_ID`), Foundry
endpoint at `AZURE_AI_ENDPOINT` (account-host shape per AGENTS.md §9.7),
`gpt-5.4-mini` deployment in `<ci-resource-group>`, Python 3.11 for
`scripts/build-test-matrix.py`.

**Branch & PR:** All commits land on local `unsafecode/solid-disco`,
pushed to `origin unsafecode/pr-review` (PR #185, draft, base `main`,
HEAD `b79ad8c`). Sibling worktree at `unsafecode-ubiquitous-telegram`
holds `unsafecode/pr-review` directly — that's fine; we push by ref-spec
`solid-disco:pr-review`, never check out the PR branch here.

**Mandate (hard requirement):** No pytest. No `pip install + python -c
"import X"`. Validation = Copilot CLI agent reads SKILL.md, executes its
instructions against real Azure, self-verifies. The existing pin-smoke +
e2e-azure jobs in `skill-test.yml` are deleted in Phase 4 — do not extend
them here.

**Commit hygiene:** Every commit MUST contain `[audit-2026-Q2]` (the
audit-trail gate at `scripts/automation-pr-gate.py` lines 313–325 requires
this tag for any PR that touches `skills/**` paired with audit-trail
files; the tag also bypasses the `[multi-skill]` + `[skill-rewrite]`
opt-ins for this PR per gate lines 156–162 / 217–220). Every commit MUST
include `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

---

## File Structure

| File | Action | Purpose |
|---|---|---|
| `docs/superpowers/plans/2026-05-30-task-2-1-foundry-prompt-agents-audit.md` | Create (this file) | The Task-2.1-specific plan |
| `docs/audit/foundry-prompt-agents-audit-trail.md` | Create | 21-class findings, evidence, deferred items |
| `skills/foundry-prompt-agents/test-fixture/consumer_prompt.md` | Create | The Copilot CLI fixture prompt (the executable test) |
| `skills/foundry-prompt-agents/SKILL.md` | Modify (if drift found) | Fix any audit findings + PATCH version bump |
| `.github/workflows/skill-test.yml` | Modify | Add `build-matrix` + `copilot-cli-matrix` jobs at end |

**Files we do NOT touch in this task** (Phase 4 work):
- `scripts/tests/test_e2e_prompt_agents.py` (slated for deletion in Phase 4)
- The existing `pin-smoke` and `e2e-azure` jobs in `skill-test.yml`
- `.github/workflows/copilot-cli-foundry-auth-smoke.yml` (locked-in
  ground-truth pattern; do NOT modify)

---

## Phase A — 21-Class Audit Scan

**Goal:** Produce `docs/audit/foundry-prompt-agents-audit-trail.md` with
a finding for each of the 21 bug classes from
[spec Appendix A](../specs/2026-05-30-deep-audit-and-testing-rethink-design.md#appendix-a).
"None observed" is a valid finding **only if you actually scanned**. "TODO"
is never valid. Cite file:line for any hit.

### Task A.1: Re-read inputs end-to-end

**Files:**
- Read: `skills/foundry-prompt-agents/SKILL.md` (462 lines)
- Read: `skills/foundry-prompt-agents/references/upstream-pin.md` (115 lines)
- Read: `docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md` (Appendix A — the 21 classes)

- [ ] **Step 1: View SKILL.md in full**

```bash
view skills/foundry-prompt-agents/SKILL.md
```

- [ ] **Step 2: View the pin file**

```bash
view skills/foundry-prompt-agents/references/upstream-pin.md
```

- [ ] **Step 3: View Appendix A of the spec**

```bash
view docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md  # focus L381-403
```

### Task A.2: Scan each of the 21 classes against SKILL.md + references

For each class below, search the skill artifacts and record a finding.
Use the rg/grep patterns listed as starting points; expand to manual
read where the pattern is fuzzy.

| # | Bug class | Suggested scan |
|---|---|---|
| 1 | Sync credential in async-only client | `rg -n "AzureCliCredential\|DefaultAzureCredential" skills/foundry-prompt-agents/` — check each call-site's `async`/`await` context |
| 2 | Wrong endpoint URL (project vs account) | `rg -n "endpoint\|services.ai.azure.com\|cognitiveservices.azure.com\|ai.azure.com" skills/foundry-prompt-agents/` |
| 3 | Wrong model names | `rg -n "gpt-\|model_name\|deployment" skills/foundry-prompt-agents/` — cross-check against `gpt-5.4-mini` in CI infra (AGENTS.md §9.7) |
| 4 | Wrong RBAC role names | `rg -n "role\|Role\|RBAC\|Foundry User\|Cognitive Services" skills/foundry-prompt-agents/` |
| 5 | Wrong API scopes | `rg -n "az account get-access-token\|--resource\|--scope" skills/foundry-prompt-agents/` — line 95 already flagged as a candidate; functionally verify |
| 6 | Wrong env-var names | `rg -n "AZURE_AI_ENDPOINT\|AZURE_AI_PROJECT\|FOUNDRY_" skills/foundry-prompt-agents/` |
| 7 | Hardcoded GUIDs | `rg -nE "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" skills/foundry-prompt-agents/` |
| 8 | Deprecated SDK calls | manual scan; cross-check `azure-ai-projects~=2.1.0` API surface — KI-002 and KI-003 already document gotchas |
| 9 | Bicep module drift | `rg -n "\.bicep\|module" skills/foundry-prompt-agents/` (likely n/a — wrapper skill) |
| 10 | Bicep param mismatches | n/a unless A.9 finds Bicep |
| 11 | Cross-skill contradictions | `rg -n "foundry-mcp-aca\|foundry-vnet-deploy\|microsoft-foundry\|azure-tenant-isolation" skills/foundry-prompt-agents/` — verify referenced contracts |
| 12 | Container probe misconfiguration | n/a (no container) |
| 13 | Wrong region defaults | `rg -n "swedencentral\|westus\|location\|region" skills/foundry-prompt-agents/` |
| 14 | JSON/YAML escaping in agent prompts | manual scan; especially `description:` frontmatter + any prompt strings |
| 15 | Reference ↔ SKILL.md drift | **Known hit: line 175 stray ` ``` ` closing nothing.** Also: cross-check `references/upstream-pin.md` `known_issues[]` ↔ SKILL.md §6 (KI-001/002/003) |
| 16 | Missing `dependsOn` (RBAC race) | n/a unless A.9 finds Bicep |
| 17 | Tool wrapper type mismatches (dict vs Pydantic) | manual scan; check `WebSearchTool`, `CodeInterpreterTool`, `FileSearchTool`, `MCPTool`, `OpenApiTool` instantiations |
| 18 | Bot/webhook signature bugs | n/a (not a bot skill) |
| 19 | Logging exposure (secrets, PII) | `rg -n "print\|log\|logger\|token\|key" skills/foundry-prompt-agents/` — check none leak agent IDs/keys |
| 20 | Async/sync mismatches beyond credentials | manual scan for `async def` ↔ sync SDK calls (and vice versa) |
| 21 | Outdated package pins | cross-check pin file `azure-ai-projects~=2.1.0` against PyPI latest (already covered by freshness loop; record current status) |

- [ ] **Step 1: Run the rg scans**

```bash
rg -n "AzureCliCredential|DefaultAzureCredential" skills/foundry-prompt-agents/
rg -n "endpoint|services\.ai\.azure\.com|cognitiveservices\.azure\.com|ai\.azure\.com" skills/foundry-prompt-agents/
rg -n "gpt-|model_name|deployment" skills/foundry-prompt-agents/
rg -n "role|Role|RBAC|Foundry User|Cognitive Services" skills/foundry-prompt-agents/
rg -n "az account get-access-token|--resource|--scope" skills/foundry-prompt-agents/
rg -n "AZURE_AI_ENDPOINT|AZURE_AI_PROJECT|FOUNDRY_" skills/foundry-prompt-agents/
rg -nE "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" skills/foundry-prompt-agents/
rg -n "\.bicep|module" skills/foundry-prompt-agents/
rg -n "foundry-mcp-aca|foundry-vnet-deploy|microsoft-foundry|azure-tenant-isolation" skills/foundry-prompt-agents/
rg -n "swedencentral|westus|location|region" skills/foundry-prompt-agents/
rg -n "print\(|log\.|logger|token|key" skills/foundry-prompt-agents/
```

- [ ] **Step 2: Manual scan for classes 14, 17, 20**

Read SKILL.md inline; for class 14 examine frontmatter `description:` +
all prompt-string literals; for class 17 examine every `*Tool()`
constructor invocation against the
[azure-ai-projects 2.1.0 surface](https://learn.microsoft.com/en-us/python/api/azure-ai-projects/)
to confirm dict-vs-typed-arg consistency; for class 20 cross-check every
`async def` body for sync-SDK calls and every sync helper for `await`.

- [ ] **Step 3: Confirm the line 175 stray ` ``` ` finding**

```bash
sed -n '170,180p' skills/foundry-prompt-agents/SKILL.md
```

Expected: line 175 contains exactly ` ``` ` on its own with nothing
opening a fence above it within that block. This is the orphan code-fence
flagged in pre-read.

- [ ] **Step 4: Verify line 95 audience claim functionally (deferred)**

The REST equivalent at line 95 uses `--resource https://ai.azure.com`.
The auth-smoke workflow uses `--resource https://cognitiveservices.azure.com`.
Both may be valid (Foundry data plane vs Cognitive Services control
plane) — record the candidacy in the audit trail, classify as Bug Class
5 IF the consumer fixture proves the REST call fails, otherwise mark
"none observed (both audiences are valid against Foundry; SDK path is
not affected)".

### Task A.3: Author the audit-trail file

**Files:**
- Create: `docs/audit/foundry-prompt-agents-audit-trail.md`

- [ ] **Step 1: Write the audit-trail file conforming to `docs/audit/README.md` schema**

```markdown
# foundry-prompt-agents — Audit Trail

**Auditor:** copilot-cli + ricchi
**Date:** 2026-05-30
**Bug-class scan:** all 21 classes from Appendix A of
[`docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md`](../superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md)

**Skill version under audit:** SKILL.md `metadata.version: 1.0.2`
(pre-audit), pin file v1.0.1, `azure-ai-projects~=2.1.0`.

**Findings (verbatim list):**

1. Class 1 (sync credential in async client) — <finding from A.2>
2. Class 2 (endpoint URL bugs) — <finding from A.2>
3. Class 3 (wrong model names) — <finding from A.2>
4. Class 4 (wrong RBAC roles) — <finding from A.2>
5. Class 5 (wrong API scopes) — <finding from A.2 + line 95 verification>
6. Class 6 (wrong env-var names) — <finding from A.2>
7. Class 7 (hardcoded GUIDs) — <finding from A.2>
8. Class 8 (deprecated SDK calls) — <finding from A.2>
9. Class 9 (Bicep module drift) — n/a (wrapper skill, no Bicep)
10. Class 10 (Bicep param mismatches) — n/a (see Class 9)
11. Class 11 (cross-skill contradictions) — <finding from A.2>
12. Class 12 (container probe misconfiguration) — n/a (no container)
13. Class 13 (wrong region defaults) — <finding from A.2>
14. Class 14 (JSON/YAML escaping in agent prompts) — <finding from A.2>
15. Class 15 (Reference ↔ SKILL.md drift) — **HIT:** line 175 stray ` ``` ` orphan code-fence. Fix in Phase B.
16. Class 16 (missing `dependsOn`) — n/a (see Class 9)
17. Class 17 (Tool wrapper type mismatches) — <finding from A.2>
18. Class 18 (bot/webhook signature bugs) — n/a (not a bot skill)
19. Class 19 (logging exposure) — <finding from A.2>
20. Class 20 (async/sync mismatches beyond credentials) — <finding from A.2>
21. Class 21 (outdated package pins) — `azure-ai-projects~=2.1.0` last validated by copilot-bot 2026-05-29 (freshness loop owns this). No action.

**Fixture:** [`../../skills/foundry-prompt-agents/test-fixture/consumer_prompt.md`](../../skills/foundry-prompt-agents/test-fixture/consumer_prompt.md)

**CI matrix run that proved the fix:** _<filled in during Phase E after the first green run>_

**Open items (deferred):**
- <any class-21 freshness-loop items or follow-up items>
```

- [ ] **Step 2: Commit Phase A**

```bash
git add docs/audit/foundry-prompt-agents-audit-trail.md
git commit -m "audit(foundry-prompt-agents): 21-class scan baseline

Records findings from the Phase 2 deep audit per spec 2026-05-30
Appendix A. Each of the 21 bug classes has a finding cited from the
SKILL.md / references scan; 'none observed' findings are backed by
explicit grep patterns (recorded in the Task-2.1 plan).

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

> **Note:** The PR gate at `scripts/automation-pr-gate.py` gate
> `gate_audit_tag_requires_audit_trail` requires that whenever
> `[audit-2026-Q2]` is in the commit log AND any `skills/<name>/` file
> changes, the same diff includes `docs/audit/<name>-audit-trail.md`.
> Phase A creates only the audit-trail (no `skills/**` change) so the
> commit passes by virtue of no skill touch yet. Phase B's SKILL.md fix
> + Phase C's fixture both rely on this audit-trail file already being
> in the diff.

---

## Phase B — Fix Drift Found in Phase A

**Goal:** Resolve audit findings (at minimum the line 175 orphan code-fence)
and bump `metadata.version` PATCH (1.0.2 → 1.0.3).

### Task B.1: Apply audit fixes

**Files:**
- Modify: `skills/foundry-prompt-agents/SKILL.md`

- [ ] **Step 1: Inspect lines 165-185 of SKILL.md to identify the orphan fence's context**

```bash
view skills/foundry-prompt-agents/SKILL.md  # range 165-185
```

Expected: code block at L161-169 (Python `mcp_tool` snippet) closes with
` ``` ` on line 169. The blockquote at L171-174 is `> ...` prose. Line
175 is a bare ` ``` ` — an orphan that does not close anything and that
visibly breaks downstream rendering at the `> **MCP servers for prompt
agents**` blockquote that follows.

- [ ] **Step 2: Delete the orphan fence**

Use `edit` to remove line 175's ` ``` ` (and the preceding blank line if
appropriate). Preserve all other content byte-for-byte.

- [ ] **Step 3: Apply any additional fixes from Phase A findings**

For each non-n/a, non-"none observed" finding in the audit trail, apply
a surgical edit to SKILL.md or the referenced file. Update the audit
trail's finding line to cite the fix commit SHA.

- [ ] **Step 4: PATCH-bump SKILL.md `metadata.version`**

Edit frontmatter: `metadata.version: "1.0.2"` → `"1.0.3"`.

> Per AGENTS.md § 5, prose clarifications and small fixes are PATCH.
> No description change → no risk of breaching the 1024-char cap.

- [ ] **Step 5: Verify YAML still parses + description ≤ 1024 chars**

```bash
python -c "
import yaml, pathlib, sys
p = pathlib.Path('skills/foundry-prompt-agents/SKILL.md')
fm = p.read_text(encoding='utf-8').split('---')[1]
d = yaml.safe_load(fm)
assert d['metadata']['version'] == '1.0.3', d['metadata']['version']
assert len(d['description']) <= 1024, len(d['description'])
print(f'OK — version={d[\"metadata\"][\"version\"]} desc={len(d[\"description\"])} chars')
"
```

Expected: `OK — version=1.0.3 desc=<N> chars` (N ≤ 1024).

- [ ] **Step 6: Update audit-trail file with fix-commit citations**

After the next commit lands, update each "HIT" finding in
`docs/audit/foundry-prompt-agents-audit-trail.md` to cite
"→ fix in commit `<sha>`". The Class 15 line 175 finding is the
mandatory minimum.

- [ ] **Step 7: Commit Phase B**

```bash
git add skills/foundry-prompt-agents/SKILL.md docs/audit/foundry-prompt-agents-audit-trail.md
git commit -m "audit(foundry-prompt-agents): fix line 175 orphan fence + version PATCH

Class 15 (Ref ↔ SKILL.md drift): remove stray code-fence on line 175
that breaks downstream blockquote rendering. Bump metadata.version
1.0.2 → 1.0.3. Update audit trail with fix-commit citation.

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

> **Gate sanity:** Touches `skills/foundry-prompt-agents/SKILL.md`
> (body change) → would normally need `[skill-rewrite]`. But
> `[audit-2026-Q2]` is in the commit message and the audit-trail file
> is in the same diff (touched in Step 6), so `gate_skill_md_body`
> (script L208-225) and `gate_audit_tag_requires_audit_trail`
> (L294-322) both pass.

---

## Phase C — Author the Copilot CLI Consumer Fixture

**Goal:** Create
`skills/foundry-prompt-agents/test-fixture/consumer_prompt.md` — the
single fixture that, when piped to `copilot -p`, makes a Copilot CLI
instance read SKILL.md, execute its instructions against real Foundry
(`gpt-5.4-mini` in `<ci-foundry-account>`), and self-verify by printing a
machine-checkable success/failure line.

### Task C.1: Write the fixture

**Files:**
- Create: `skills/foundry-prompt-agents/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Write the fixture**

```markdown
<!-- skills/foundry-prompt-agents/test-fixture/consumer_prompt.md -->

You are a Copilot CLI agent driving an end-to-end smoke test of the
`foundry-prompt-agents` skill. The repo containing the skill is at
your current working directory (`$GITHUB_WORKSPACE`). The skill file
is `skills/foundry-prompt-agents/SKILL.md` — read it once, then
execute its happy path verbatim. No mocked clients. No stubs. Real
Azure calls only.

## Environment you can rely on

- `AZURE_AI_ENDPOINT` is set to the Foundry account host
  (`https://<ci-foundry-account>.cognitiveservices.azure.com/`).
- Azure CLI is logged in via OIDC (UAMI `<ci-uami-name>` has
  `Cognitive Services OpenAI User` + `Foundry User` on the account).
- `gpt-5.4-mini` is deployed on the account.
- The skill uses `DefaultAzureCredential`, which picks up the
  workflow's `azure/login@v2` token automatically.

## What you MUST do (in order)

1. Read `skills/foundry-prompt-agents/SKILL.md` end-to-end. Note the
   Python create / invoke / list / delete patterns and the KI-001,
   KI-002, KI-003 gotchas in § 6.
2. Derive the Foundry **project endpoint** from `AZURE_AI_ENDPOINT`
   per KI-001 (account-host → project-host conversion is documented
   in the skill).
3. In a Python invocation (use `python3 -c '<inline>'` or a tempfile),
   import the skill's canonical SDK surface
   (`from azure.ai.projects import AIProjectClient`,
   `from azure.identity import DefaultAzureCredential`) and:
   1. Create a prompt agent named
      `ci-smoke-pa-<8-char-uuid>` using deployment `gpt-5.4-mini`
      with instructions exactly: `"Reply with the single word OK and
      nothing else."`
   2. Send a single user message `ping` via the Conversations API
      pattern documented in § 3 of SKILL.md.
   3. Print the agent's reply.
   4. List agents (KI-002 path — exercise the pagination quirk
      documented in the skill) and confirm the new agent is in the
      list.
   5. Delete the agent by name (KI-003 path — uses the
      delete-by-name signature documented in the skill).
   6. List agents again and confirm the agent is NOT in the list.
4. Print exactly one of these two lines as the LAST line of output:
   - On success: `SMOKE_RESULT=PASS`
   - On failure: `SMOKE_RESULT=FAIL <one-line reason>`

## Hard constraints

- Do NOT modify any file under `skills/foundry-prompt-agents/`.
- Do NOT add new pip dependencies; the runner already has the
  packages declared in the skill's pin file
  (`references/upstream-pin.md` → `packages[]`).
- If any step throws, print `SMOKE_RESULT=FAIL <step N>: <exception
  type + message>` and exit non-zero.
- If `SMOKE_RESULT=PASS` is the last line of stdout, the matrix job
  marks the run green; any other last line is treated as failure.

Begin now.
```

- [ ] **Step 2: Verify the fixture is matrix-discoverable**

```bash
python scripts/build-test-matrix.py --repo-root .
```

Expected: `{"skill": ["foundry-prompt-agents"]}`.

- [ ] **Step 3: Commit Phase C**

```bash
git add skills/foundry-prompt-agents/test-fixture/consumer_prompt.md
git commit -m "audit(foundry-prompt-agents): consumer-prompt fixture for CI matrix

The fixture drives a Copilot CLI instance to execute SKILL.md's
create+invoke+list+delete happy path against real Foundry
(gpt-5.4-mini in <ci-foundry-account>), exercising KI-001 (project
endpoint derivation), KI-002 (list pagination), KI-003 (delete-by-
name). Success contract: SMOKE_RESULT=PASS as last line of stdout.

Picked up by scripts/build-test-matrix.py automatically.

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase D — Wire the `copilot-cli-matrix` CI Job

**Goal:** Add `build-matrix` + `copilot-cli-matrix` jobs to
`.github/workflows/skill-test.yml` using the **auth-smoke ground-truth
pattern** (v1 audience NO `/.default`, `copilot -p` non-interactive flag,
`npm install -g @github/copilot`). The existing `pin-smoke` and
`e2e-azure` jobs are preserved (Phase 4 deletes them).

### Task D.1: Inspect current `skill-test.yml` structure

**Files:**
- Read: `.github/workflows/skill-test.yml`

- [ ] **Step 1: View the file**

```bash
view .github/workflows/skill-test.yml
```

Confirm:
- `name: skill-test`
- `on:` includes `pull_request`, `push: branches: [main]`, `schedule:`, `workflow_dispatch`
- existing jobs: `unit-tests`, `catalog-lint`, `pin-smoke`, `e2e-azure`
- top-level `permissions: id-token: write, contents: read`

### Task D.2: Append `build-matrix` + `copilot-cli-matrix` jobs

**Files:**
- Modify: `.github/workflows/skill-test.yml` (append at end of `jobs:`)

- [ ] **Step 1: Append the new jobs**

Use `edit` to add the following at the end of the `jobs:` block. **Do
not modify any existing job.** This is the master plan's Step 4 block,
with the L782 audience bug corrected to match the auth-smoke ground
truth (`--resource https://cognitiveservices.azure.com` — NO `/.default`):

```yaml
  build-matrix:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.build.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pyyaml
      - id: build
        run: echo "matrix=$(python scripts/build-test-matrix.py --repo-root .)" >> "$GITHUB_OUTPUT"

  copilot-cli-matrix:
    needs: build-matrix
    if: fromJSON(needs.build-matrix.outputs.matrix).skill[0] != null
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      max-parallel: 5
      matrix: ${{ fromJSON(needs.build-matrix.outputs.matrix) }}
    timeout-minutes: 30
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Install Copilot CLI
        # Node 22 is pre-installed on ubuntu-latest. npm install is the
        # documented install path; proven green by
        # .github/workflows/copilot-cli-foundry-auth-smoke.yml.
        # Do NOT use `curl … install.sh | bash` — no canonical URL exists.
        run: |
          npm install -g @github/copilot
          copilot --version

      - name: Install awesome-gbb plugin from this checkout
        run: |
          copilot plugin marketplace add "$GITHUB_WORKSPACE"
          copilot plugin install awesome-gbb@awesome-gbb

      - name: Get Foundry bearer token
        # `--resource` takes the v1 AAD audience identifier (NO `/.default`
        # suffix). Passing the v2 scope form to `--resource` produces
        # AADSTS500011 "resource principal not found". The auth-smoke
        # workflow (L63-75) documents this in detail and is the canonical
        # reference. `tr -d '\r\n'` defends against trailing newline from
        # `-o tsv` that would otherwise produce a cryptic 401 from Foundry.
        run: |
          set -euo pipefail
          TOKEN=$(az account get-access-token \
            --resource https://cognitiveservices.azure.com \
            --query accessToken -o tsv | tr -d '\r\n')
          echo "::add-mask::$TOKEN"
          echo "COPILOT_PROVIDER_BEARER_TOKEN=$TOKEN" >> "$GITHUB_ENV"

      - name: Run consumer prompt for ${{ matrix.skill }}
        id: run
        env:
          # BYOK routing → Foundry, identical to the auth-smoke workflow.
          # Env-var names verified against CLI 1.0.57-2 via `copilot help
          # providers` / `copilot help environment` (Task 1.0). Legacy
          # `COPILOT_MODEL_*` names DO NOT EXIST and would be silently
          # ignored.
          COPILOT_PROVIDER_TYPE: azure
          COPILOT_PROVIDER_BASE_URL: ${{ secrets.AZURE_AI_ENDPOINT }}
          COPILOT_PROVIDER_MODEL_ID: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_MODEL: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_API: responses
          COPILOT_ALLOW_ALL: "true"
          COPILOT_AUTO_UPDATE: "false"
          AZURE_AI_ENDPOINT: ${{ secrets.AZURE_AI_ENDPOINT }}
          ACR_LOGIN_SERVER: ${{ secrets.ACR_LOGIN_SERVER }}
        run: |
          set -euo pipefail
          PROMPT="skills/${{ matrix.skill }}/test-fixture/consumer_prompt.md"
          test -f "$PROMPT" || { echo "missing fixture: $PROMPT"; exit 2; }
          # `-p` is the released CLI's one-shot prompt form. `copilot run`
          # does not exist; `--prompt-file` does not exist. Inline the
          # fixture body with $(cat …). `--disable-builtin-mcps` drops the
          # GitHub MCP server so this test doesn't depend on github.com
          # reachability — fixtures opt back in to specific MCP servers
          # via `--allow-tool=mcp__…` flags.
          copilot -p "$(cat "$PROMPT")" \
                  --allow-all-tools \
                  --disable-builtin-mcps \
                  -C "$GITHUB_WORKSPACE" \
                  2>&1 | tee "/tmp/${{ matrix.skill }}-transcript.log"
          # Last-line contract: SMOKE_RESULT=PASS = success.
          tail -n 1 "/tmp/${{ matrix.skill }}-transcript.log" | grep -q "^SMOKE_RESULT=PASS$" \
            || { echo "fixture did not end with SMOKE_RESULT=PASS"; exit 1; }

      - name: Retry once on classified-transient failure
        if: failure() && steps.run.outcome == 'failure'
        env:
          COPILOT_PROVIDER_TYPE: azure
          COPILOT_PROVIDER_BASE_URL: ${{ secrets.AZURE_AI_ENDPOINT }}
          COPILOT_PROVIDER_MODEL_ID: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_MODEL: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_API: responses
          COPILOT_ALLOW_ALL: "true"
          COPILOT_AUTO_UPDATE: "false"
          AZURE_AI_ENDPOINT: ${{ secrets.AZURE_AI_ENDPOINT }}
          ACR_LOGIN_SERVER: ${{ secrets.ACR_LOGIN_SERVER }}
        run: |
          set -euo pipefail
          PROMPT="skills/${{ matrix.skill }}/test-fixture/consumer_prompt.md"
          if grep -qE "429|503|throttl|capacity|EOF during azd deploy|revision .* not found" "/tmp/${{ matrix.skill }}-transcript.log"; then
            echo "classified-transient — retrying once"
            copilot -p "$(cat "$PROMPT")" \
                    --allow-all-tools \
                    --disable-builtin-mcps \
                    -C "$GITHUB_WORKSPACE" \
                    2>&1 | tee "/tmp/${{ matrix.skill }}-retry.log"
            tail -n 1 "/tmp/${{ matrix.skill }}-retry.log" | grep -q "^SMOKE_RESULT=PASS$" \
              || { echo "retry also did not end with SMOKE_RESULT=PASS"; exit 1; }
          else
            echo "non-transient failure — not retrying"
            exit 1
          fi

      - name: Upload transcript (forensics)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: transcript-${{ matrix.skill }}
          path: /tmp/${{ matrix.skill }}-transcript.log
          retention-days: 7
```

- [ ] **Step 2: Lint the workflow YAML locally**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/skill-test.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`.

- [ ] **Step 3: Commit Phase D**

```bash
git add .github/workflows/skill-test.yml
git commit -m "ci(skill-test): wire build-matrix + copilot-cli-matrix jobs

Adds two jobs at the end of skill-test.yml that drive
copilot-cli-matrix per spec 2026-05-30 §5.3:

  build-matrix       — emits {\"skill\": [...]} from
                       scripts/build-test-matrix.py
  copilot-cli-matrix — one runner per skill with a test-fixture
                       consumer_prompt.md; uses npm-installed Copilot
                       CLI 1.0.57+ with BYOK Foundry routing
                       (gpt-5.4-mini in <ci-foundry-account>).

Auth pattern mirrors copilot-cli-foundry-auth-smoke.yml exactly:
v1 audience (NO /.default suffix), tr -d '\r\n' on the bearer token,
copilot -p inline-fixture invocation (CLI has no --prompt-file flag).

Existing pin-smoke + e2e-azure jobs are NOT modified here — Phase 4
deletes them after the matrix proves itself across the catalog.

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

> **Gate sanity:** Touches only `.github/workflows/skill-test.yml`
> (not `skills/**`), so `automation-pr-gate.yml`'s `paths:` filter
> does not even run. The `[audit-2026-Q2]` tag is still present per
> commit-message hygiene rule.

---

## Phase E — Push, Watch, Stabilize

**Goal:** Push the branch to `origin/unsafecode/pr-review`, watch the
matrix run 5 times consecutively green (1 PR-gate run + 4 manual
dispatches), and update the audit trail with the matrix run URLs.

### Task E.1: Push and trigger the PR-gate run

- [ ] **Step 1: Confirm local branch state**

```bash
git status
git log --oneline -5
```

Expected: 4 new commits ahead of `origin/unsafecode/pr-review` (one per
Phase A/B/C/D), all carrying `[audit-2026-Q2]`, all with the Co-authored-by
trailer.

- [ ] **Step 2: Push to the PR branch by refspec**

```bash
git push origin unsafecode/solid-disco:unsafecode/pr-review
```

> Do NOT use HEAD-form rebases on this worktree (sibling-worktree
> conflict). Do NOT check out `unsafecode/pr-review` here — it is
> already checked out at `unsafecode-ubiquitous-telegram`. Push by
> refspec is the only safe path.

- [ ] **Step 3: Watch PR #185 checks**

```bash
gh pr checks 185 --watch
```

Expected: `build-matrix` succeeds, `copilot-cli-matrix
(foundry-prompt-agents)` succeeds. All other gates (`validate`,
`smoke`, `pin-smoke`, `e2e-azure`) remain green.

### Task E.2: Diagnose any first-run failure

- [ ] **Step 1: If `copilot-cli-matrix` fails, download the transcript**

```bash
gh run download <run-id> --name transcript-foundry-prompt-agents -D /tmp/triage
cat /tmp/triage/foundry-prompt-agents-transcript.log
```

- [ ] **Step 2: Classify and remediate**

| Symptom in transcript | Likely cause | Fix |
|---|---|---|
| AADSTS500011 | Audience mistake — should not happen given Phase D's pattern; re-check yaml | Re-verify `--resource https://cognitiveservices.azure.com` (NO `/.default`) |
| 401 from Foundry with token-shape complaint | Missing `tr -d '\r\n'` | Re-verify Phase D yaml |
| `copilot: command not found` | Missing npm install | Re-verify Phase D yaml |
| Fixture exits without `SMOKE_RESULT=` line | Fixture instructions too vague | Tighten the fixture (Phase C); add explicit `print('SMOKE_RESULT=...')` exemplars |
| `MissingAuthToken` from azure-ai-projects | DefaultAzureCredential failed to pick up the OIDC token | Add explicit `AZURE_USE_CLI_CREDENTIAL=true` or similar; document |
| 429 / 503 / "capacity" | Foundry throttling | Retry-once block should already handle; if not, expand the regex |
| KI-002 / KI-003 path mismatch | SDK behaviour drifted | Update SKILL.md + add fix-commit citation to audit trail |

Apply the smallest fix that addresses the symptom, commit with
`[audit-2026-Q2]`, push again, and re-run.

### Task E.3: Five consecutive green runs

- [ ] **Step 1: After the first PR-gate green, dispatch 4 more**

```bash
gh workflow run skill-test.yml --ref unsafecode/pr-review
gh workflow run skill-test.yml --ref unsafecode/pr-review
gh workflow run skill-test.yml --ref unsafecode/pr-review
gh workflow run skill-test.yml --ref unsafecode/pr-review
# Watch each:
gh run list --workflow=skill-test.yml --branch=unsafecode/pr-review --limit=5
```

Wait between dispatches if Foundry capacity is tight; the retry-once
should handle most throttles, but rate-limit avoidance helps.

- [ ] **Step 2: Confirm 5 consecutive successes**

```bash
gh run list --workflow=skill-test.yml --branch=unsafecode/pr-review --limit=5 --json conclusion,databaseId
```

Expected: 5 most recent runs all `"conclusion": "success"`.

- [ ] **Step 3: Update audit-trail with the run URLs**

Edit `docs/audit/foundry-prompt-agents-audit-trail.md`:

- Replace `**CI matrix run that proved the fix:** _<filled in during
  Phase E after the first green run>_` with a 5-line list of run URLs
  (`https://github.com/aiappsgbb/awesome-gbb/actions/runs/<id>`).

- [ ] **Step 4: Commit the audit-trail update**

```bash
git add docs/audit/foundry-prompt-agents-audit-trail.md
git commit -m "audit(foundry-prompt-agents): 5 consecutive green matrix runs

Adds CI run URLs to the audit trail per spec 2026-05-30 §6 pilot
success criteria.

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin unsafecode/solid-disco:unsafecode/pr-review
```

### Task E.4: Notify the user + exit

- [ ] **Step 1: Send a status message back to the creator chat**

```text
Task 2.1 complete. 4 deliverables landed on PR #185:

1. docs/audit/foundry-prompt-agents-audit-trail.md — 21-class scan with
   1 confirmed hit (Class 15: orphan code-fence at L175, fixed in
   <sha>) + N "none observed" findings.
2. skills/foundry-prompt-agents/test-fixture/consumer_prompt.md —
   exercises create+invoke+list+delete against gpt-5.4-mini in
   <ci-foundry-account>.
3. .github/workflows/skill-test.yml — build-matrix + copilot-cli-matrix
   jobs (auth-smoke pattern verbatim, master plan L782 audience bug
   corrected).
4. 5 consecutive green runs: <5 URLs>.

SKILL.md PATCH-bumped 1.0.2 → 1.0.3. Ready for Task 2.2.
```

(Send via the `send_session_message` tool to project session
`b9a5b076-be19-452c-b1ff-f60b0e1763a6`.)

---

## Self-Review

**Spec coverage (master plan L659-L894 + spec §6):**
- Deliverable 1 (audit trail) → Phase A ✓
- Deliverable 2 (consumer fixture) → Phase C ✓
- Deliverable 3 (matrix job) → Phase D ✓
- Deliverable 4 (5 green runs) → Phase E ✓
- 21-class scan → Phase A Task A.2 ✓ (all 21 classes enumerated)
- Auth-smoke pattern verbatim → Phase D explicit (master plan L782 bug
  corrected to match ground truth)
- `[audit-2026-Q2]` on every commit + Co-authored-by → noted on every
  commit step in all phases

**Placeholder scan:**
- No `TBD`, no `TODO`, no "fill in details" left in the plan. The two
  audit-trail entries that are filled in during execution
  (`<filled in during Phase E>` and `<finding from A.2>` per-class) are
  intentionally lazy-evaluated and have explicit execution steps that
  resolve them.

**Type consistency:**
- `consumer_prompt.md` path is consistent everywhere.
- `build-test-matrix.py` invocation is `--repo-root .` everywhere.
- Audit-trail filename is `foundry-prompt-agents-audit-trail.md`
  everywhere.
- `[audit-2026-Q2]` is the exact opt-in tag string per gate script
  (`OPT_IN_AUDIT` constant in `automation-pr-gate.py` L60).
- Plan filename matches the user's "save to
  `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`" convention.

**Branch model consistency:**
- Local branch: `unsafecode/solid-disco` (never renamed).
- Push target: `origin unsafecode/solid-disco:unsafecode/pr-review`.
- Never `git checkout unsafecode/pr-review` here (sibling worktree
  conflict).

**Gate-script reconciliation (`scripts/automation-pr-gate.py`):**
- `gate_one_skill_per_pr`: only one skill touched (`foundry-prompt-agents`) → passes regardless of opt-ins.
- `gate_no_canon_edits`: no `references/data-realism/` touch → passes.
- `gate_skill_md_body`: SKILL.md body change in Phase B → `[audit-2026-Q2]` opt-in covers (L217-220).
- `gate_patch_only_for_metadata_diff`: SKILL.md body change is real (not metadata-only) → gate skipped (L237).
- `gate_description_length`: no description change in Phase B → passes.
- `gate_audit_tag_requires_audit_trail`: `[audit-2026-Q2]` triggers → requires `docs/audit/foundry-prompt-agents-audit-trail.md` → present in all commits after Phase A.
