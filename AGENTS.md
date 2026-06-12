# AGENTS.md — Contributor & Sub-Agent Guide

> Rules for **anyone** (human or AI) who edits this repo. Read this **before**
> opening a PR, asking a sub-agent to refactor a skill, or running a mass
> scrub / sync pass. Violating an invariant here breaks downstream consumers
> in subtle ways that won't fail CI.

This repo is the canonical home of the **`awesome-gbb`** skill catalog. The
[README](README.md) covers what each skill does. This file covers **how to
safely change them**.

---

## 1 · Repo layout (what lives where)

```
awesome-gbb/
├── README.md                 # Public catalog (skills index, install instructions)
├── AGENTS.md                 # ← you are here
├── plugin.json               # Single plugin manifest ("skills": "skills/")
├── skills/                   # SOURCE OF TRUTH for every skill
│   └── <skill-name>/
│       ├── SKILL.md          # Skill definition (frontmatter + instructions)
│       ├── README.md         # Optional extended docs
│       ├── references/       # Optional: scaffolds, templates, canon data
│       │   └── …             # SemVer-stable; consumed by the SKILL at runtime
│       └── templates/        # Optional: copy-paste templates (Bicep, Dockerfile, …)
└── .github/plugin/
    └── marketplace.json      # Lists the plugin for `copilot plugin marketplace add`
```

There is **no monorepo build step for individual skills** — each
`skills/<name>/SKILL.md` is a self-contained markdown contract loaded
directly by the runtime (Copilot CLI, Copilot Desktop App, VS Code agent
mode, Claude Code, etc.).

The repo IS the plugin — `plugin.json` at the repo root declares
`"skills": "skills/"`, so the CLI auto-discovers all skills. No copies,
no sync step, no `plugins/` directory.

---

## 2 · Core invariants (do not break these)

These rules govern every edit, however small. If you can't satisfy all of
them, **do not commit** — open a discussion first.

### 2.1 Skills are agnostic

A skill is a **reusable building block**. It must read sensibly to a stranger
who has never seen the PoC, customer, or repo it was last used in.

- ❌ **NO customer names** (real or pseudonymous) anywhere — frontmatter, body,
  references, examples, commit messages
- ❌ **NO PoC names** (`kyc-poc`, `card-dispute-investigation`, `threadlight-v3`)
- ❌ **NO repo names that aren't `awesome-gbb`** (don't reference your fork,
  your customer's org, or sibling private repos)
- ❌ **NO real GUIDs**, real subscription IDs, real tenant IDs, real ARM
  resource IDs in examples — use placeholders (`<sub-id>`, `<rg>`, `<account>`)
- ✅ Generic placeholders, role names, archetype customers (`<example-cardholder>`,
  `<insurer>`, `Contoso Bank`) are fine
- ✅ Industry names (FSI, MFG, Retail, Telco, Healthcare, Utilities) are fine
- ✅ Microsoft product / SKU / region names are fine

If a piece of expertise feels too tied to one PoC to express agnostically,
the right home is your **session checkpoint** or a private **AGENTS.md** in
your customer repo — not a public skill in `awesome-gbb`.

### 2.2 Reference data files are canon — do **NOT** normalize them

Files under `skills/<skill>/references/data-realism/` (FSI, MFG, Retail,
Telco) are **deliberate published-shorthand** documentation maintained by
the skill author. They cite IRS Pub. 1635, UK Payments Association, NANPA,
ISO standards, etc.

If you see something that "looks wrong" — like a single-digit EIN prefix
or a 3-digit central-office code — **STOP**. The shorthand is correct per
the cited spec; do not normalize it to a uniform width or pad with leading
zeros. Open a discussion if you genuinely believe the source is wrong.

> **Real example we paid for:** A scrub sub-agent rewrote `prefixes 0, 7-9, …`
> to `prefixes 00, 07-09, …` thinking it was "fixing inconsistent formatting".
> That is not how IRS Pub. 1635 documents EIN prefixes. The fix took a full
> turn to detect and revert. **Don't.**

### 2.3 Description ≤ 1024 chars

The `description:` field in SKILL.md frontmatter is what the runtime uses
to decide when to surface a skill. Most loaders cap it at **1024 characters**
(some at 512). The catalog already runs at 900–1022 chars on the heaviest
skills — there is **no margin** for casual additions.

When editing a description: count chars. If the new description is over
1024, find something to drop (usually a redundant `DO NOT USE FOR` clause
or a duplicate trigger phrase).

### 2.4 SKILL.md frontmatter shape is fixed

Every `SKILL.md` MUST start with this exact YAML frontmatter shape:

```yaml
---
name: <kebab-case-skill-name>
description: >
  <Folded multi-line summary, 200-1024 chars, including USE FOR / DO NOT USE FOR clauses>
metadata:
  version: "<semver>"
---
```

Rules:
- `name` is the directory name under `skills/` — **never rename without
  bumping major version and updating every cross-reference**
- `description: >` (folded scalar) — preserves trigger phrases for
  fuzzy-match loaders without forcing one giant line
- `metadata.version` is **required** (see § 5 for SemVer rules)
- No other top-level frontmatter keys are recognized — if you add one, no
  loader will read it

### 2.5 Threadlight skills live in a separate repo

The eight `threadlight-*` skills have moved to
[`aiappsgbb/threadlight-skills`](https://github.com/aiappsgbb/threadlight-skills).
They cross-reference `foundry-*`, `azd-patterns`, and `citadel-*` skills in
this repo via absolute URLs. If you change a cross-referenced contract here
(e.g., Bicep module shapes in `azd-patterns`, telemetry init in
`foundry-observability`), check whether the threadlight-skills repo needs
a corresponding update.

### 2.6 `azd` is the default for any skill that deploys infrastructure

Any skill that provisions Azure resources or deploys containers **MUST**
use `azd` (Azure Developer CLI) as the deployment model unless there is a
documented, compelling reason not to (e.g., the upstream project is an ARM
template-only accelerator with no azd support).

Concretely:
- ✅ Ship `azure.yaml` + Bicep (`infra/main.bicep`) — never hand-rolled
  `az deployment` / `az acr build` / `az containerapp create` sequences
- ✅ Use `azd up` (provision + deploy) or `azd provision` / `azd deploy`
  as the documented workflow — never multi-step `az` CLI scripts
- ✅ Follow `azd-patterns` for Bicep module shapes, hooks, and env-var
  conventions (see that skill for the canonical library)
- ✅ Tag every ACA resource with `azd-service-name: <service>` so `azd
  deploy` can discover the container app
- ✅ Use placeholder images in Bicep (`containerapps-helloworld:latest`) —
  `azd deploy` swaps them to the real ACR image automatically
- ❌ **NO hand-rolled Docker builds + `az acr build` + `az containerapp
  update`** — this is the pattern `azd deploy` replaces
- ❌ **NO VM-based deployments** — all workloads run on ACA (or Azure
  Functions where appropriate)
- ❌ **NO `az account set` without `azure-tenant-isolation`** — see that
  skill for the mandatory two-layer guard

The `azd-patterns` skill is the **single source of truth** for Bicep
module conventions. If your skill needs a new module shape (e.g., a new
Azure resource type), extend the library in `azd-patterns` — don't fork
it in your skill.

### 2.7 Skills must be tested

Every skill change requires testing proportional to the change's risk.
The catalog defines four tiers — each subsumes the tiers below it.

| Tier | Name | What it proves | When required | Enforced by |
|------|------|----------------|---------------|-------------|
| **T0** | Lint | Frontmatter parses, description ≤ 1024, no forbidden strings, deprecated API scan passes | Every PR | `skill-validation.yml` (CI) |
| **T1** | Pin validation | `validation.script` runs, every `expected_output` substring present | Pin file changes | `pin-validation.yml` (CI) |
| **T2** | Import smoke | `pip install` + `python -c "from X import Y"` for the changed pin (runs inside `validation.script`) | Pin file changes (PR-gated) | `pin-validation.yml` |
| **T3** | E2E Azure | A Copilot CLI agent reads SKILL.md and executes its fixture against real Azure resources, either succeeding or failing | New skills that touch Azure, code sample rewrites, breaking SDK changes | `skill-test.yml` (`copilot-cli-matrix` job) + § 2.9 manual evidence for excluded skills |

Rules:
- **T0 is always required.** CI enforces it; your PR will not merge without it.
- **T1 is required when the pin file changes.** CI re-runs the validation
  script on the runner — there is no "trust me, I tested" path.
- **T2 is required for MINOR/MAJOR upstream bumps.** The freshness system
  classifies impact and the issue body specifies which imports to verify.
  For `automation_tier: auto` skills, the coding agent runs T2 on the CI
  runner. For `issue_only` skills, a human must run T2 locally.
- **T3 is required when a skill tells consumers to connect to Azure.**
  The CI runner has OIDC-federated Azure credentials and dedicated E2E
  infrastructure (§ 9.7). Add a Copilot-CLI fixture at
  `skills/<name>/test-fixture/consumer_prompt.md` and register the skill
  in `.github/skill-deps.yml` — it auto-enrolls in the `copilot-cli-matrix`
  job in `skill-test.yml`. (Legacy `scripts/tests/test_e2e_*.py` was
  retired; see the header comment on `.github/workflows/skill-test.yml`.)

### 2.8 Skills that connect to Azure MUST be live-tested

This is a hard rule, not a suggestion. If SKILL.md tells consumers to
call an Azure endpoint, provision a resource, or authenticate with
`DefaultAzureCredential`, the catalog MUST prove that path works:

- ✅ Add a Copilot-CLI fixture at
  `skills/<name>/test-fixture/consumer_prompt.md` that drives a real
  Copilot CLI agent to read SKILL.md and execute its instructions
  against live Azure (credential chain, endpoint reachability, API
  surface, model inference)
- ✅ Register the skill in `.github/skill-deps.yml` so the
  `copilot-cli-matrix` job auto-enrolls it on the next PR
- ✅ Fixtures run with OIDC credentials against `<ci-resource-group>` (§ 9.7)
- ❌ **"pip install + import" is NOT sufficient** for Azure skills — it
  proves the SDK exists, not that the Azure connection works
- ❌ **"I tested locally" is NOT sufficient** — CI must reproduce it,
  OR § 2.9 evidence must be pasted into the PR body
- ❌ **`scripts/tests/test_e2e_*.py` is NOT the mechanism** — the
  legacy pytest E2E framework was retired in favour of
  `copilot-cli-matrix` (see the header comment on
  `.github/workflows/skill-test.yml`)

**Exceptions** (too complex for CI fixtures, manually validated only):
`citadel-hub-deploy`, `foundry-vnet-deploy`.
These require multi-resource deployments that exceed CI budget. Document
manual validation per § 2.9 in the PR description.

**For skills that don't deploy but connect remotely** (e.g.,
`foundry-voice-live` connecting to Azure Voice Live WSS): prove the
credential chain and API surface work. You don't need to deploy
infrastructure, but the fixture (or § 2.9 evidence) MUST prove the
client can construct and authenticate.

See existing fixtures under `skills/*/test-fixture/consumer_prompt.md`
(e.g. `foundry-prompt-agents`, `foundry-hosted-agents`, `azd-patterns`)
for the canonical patterns.

### 2.9 Nothing lands on main unless tested on Azure

This is the single most important rule in the catalog.

**Every PR that touches a skill MUST be tested live against Azure before
merging.** No exceptions, no "I'll test after merge", no "CI lint passed
so it's fine". Lint (T0) proves YAML parses. Pin validation (T1) proves
imports resolve. Neither proves the skill **actually works** when a
consumer follows its instructions against real Azure resources.

What "tested on Azure" means, by change type:

| Change type | Minimum live test |
|-------------|-------------------|
| New skill that touches Azure | Deploy or connect per the skill's instructions; verify the happy path end-to-end |
| Code sample change (SDK call, Bicep, CLI command) | Run the changed sample against a real Azure resource and verify the response |
| Guidance change (new warning, anti-pattern, workaround) | Reproduce the scenario the guidance describes; confirm the fix works |
| Description / trigger-phrase only | T0 lint is sufficient — no Azure test needed |
| Pin file refresh (version bump) | Run `validation.script`; if the script calls Azure, that counts |

**Who tests:**
- **Human contributors** test locally or in a dev subscription before
  opening the PR. Document what you tested in the PR description.
- **AI agents (Copilot, sub-agents)** MUST run the skill's Copilot-CLI
  fixture (via `copilot-cli-matrix` CI) OR execute the equivalent live
  commands manually and paste the evidence into the PR body before
  committing. If the change touches Azure paths and no fixture exists,
  the agent MUST either author one or **stop and ask the human to
  test** — it cannot self-approve.
- **Reviewers** verify the PR description includes evidence of live
  testing. No evidence → no merge.

**The cost of skipping this rule** is a broken skill that a customer or
peer copies verbatim and gets a 401, a wrong-subscription deploy, or a
silent failure. That destroys the catalog's credibility — the one thing
§ 12.1 says we cannot afford.

> **Rationalisation prevention:** "I reviewed the diff carefully" is not
> testing. "The other terminal already tested it" is not testing unless
> the PR description links to evidence. "It's just a clarification" — if
> it changes what a consumer would type into a terminal, it must be
> tested. When in doubt, test.

---

## 3 · Editing checklist (run before every commit)

Mechanical checks. Most are now CI-enforced (§ 9.6), but running them
locally before push catches issues faster than waiting for CI.

- [ ] **🔴 TESTED ON AZURE** — if any touched skill involves Azure (SDK
      calls, Bicep, CLI commands, credential chains, API endpoints), you
      have run the changed code/commands against a real Azure resource and
      verified the result. Description-only changes are exempt. See § 2.9.
      **This is the first check, not the last. Nothing else matters if
      the skill doesn't work.**
- [ ] **YAML parses** — `python -c "import yaml,pathlib; [yaml.safe_load(p.read_text().split('---')[1]) for p in pathlib.Path('skills').rglob('SKILL.md')]"`
- [ ] **Description ≤ 1024 chars** on every touched SKILL.md
- [ ] **No customer / PoC / private-repo names** introduced (grep your diff
      for likely offenders)
- [ ] **No real GUIDs or ARM IDs** introduced (grep for `subscriptions/[0-9a-f]{8}-`)
- [ ] **`metadata.version` present** on every SKILL.md you touched, and
      bumped per § 5 if the change is user-facing
- [ ] **Cross-skill links resolve** — if you renamed a section header, grep
      the rest of the repo for stale `#section-name` anchors
- [ ] **Rebuild the docs site** — `python3 scripts/build-site.py --out docs/`
      and commit the generated files. GitHub Pages serves `docs/` as static
      files — there is **no server-side build**. If you skip this step, the
      live site at `aiappsgbb.github.io/awesome-gbb` will be stale.
- [ ] **Sync to user scope mirror** if you test locally (see § 6)
- [ ] **azd is the deploy model** for any skill with infra — no hand-rolled
      `az` CLI deploy scripts (see § 2.6)

---

## 4 · Mass-edit / scrub playbook (sub-agent safety rails)

Mass edits — scrubbing PoC references, bumping versions, inserting a
metadata block — are the highest-risk operation in this repo. The scrub
that produced commit `182bfbf` damaged exactly one file (`fsi.md`) outside
its mandate, and the damage was invisible to `git diff --stat` because the
file is em-dash-heavy and got flagged as binary. **Treat every mass edit as
hostile until proven otherwise.**

### Before launching a sub-agent for a mass edit

1. **State the mandate in one sentence.** "Replace every occurrence of
   `<old-string>` with `<new-string>` and add `metadata.version: "1.0.0"`
   to frontmatter. Period."
2. **Enumerate the explicit allow-list of file types** the agent may touch
   (e.g., `**/SKILL.md`, never `references/data-realism/*.md`).
3. **Forbid normalization.** Add: "Do NOT change capitalization, whitespace,
   number formatting, or any prose unrelated to the literal find-and-replace.
   Reference data is canonical published shorthand — preserve it byte-for-byte."
4. **Require a per-file change summary** in the agent's output: file name,
   number of replacements, no other categories of change.

### After the sub-agent reports completion

5. **Inspect every modified file with `git diff -a`** (forced text — `--stat`
   alone WILL hide damage in UTF-8-heavy files):
   ```bash
   git diff -a --name-only HEAD~1 | xargs -I{} git --no-pager diff -a HEAD~1 -- {}
   ```
6. **Walk the diff line by line.** If you see ANY change that doesn't match
   the mandate, revert that file and re-run with a tighter prompt.
7. **Spot-check the heaviest diffs first.** Files with the largest line
   counts in `git diff --stat` are most likely to hide collateral damage.

### Anti-patterns we've actually seen

| What the sub-agent did | Why it's wrong |
|---|---|
| Normalized `prefixes 0, 7-9, …` to `prefixes 00, 07-09, …` | Reference canon is single-digit per IRS Pub. 1635 |
| Padded `7-00-93` to `07-00-93` | UK Payments Association documents the unpadded form |
| "Corrected" `1XX = 100-199` to `01XX = 0100-0199` | NANPA reserves `555-0100..555-0199`, the `1XX` is the line range, not a 4-digit code |
| Renamed `microsoft-foundry` → `foundry-hosted-agents` in only some skills | Inconsistent cross-references break navigation |
| Self-reported "24 files scrubbed, 181 references" without per-file summary | No way to verify scope without re-reading every diff |

### When in doubt: do it yourself

For edits to fewer than 5 files, just edit them yourself. Sub-agent setup
+ verification cost more context than the edits would.

> **CI enforcement (added with the freshness lifecycle — see § 9).**
> As of `.github/workflows/automation-pr-gate.yml`, the mass-edit
> invariants in this section are enforced as a CI gate on every PR
> (Copilot-authored or human-authored). The gate rejects multi-skill
> body edits, normalization of reference data, non-PATCH version bumps
> for metadata-only changes, and description-length regressions beyond
> 1024 chars. The opt-in commit-message tags `[multi-skill]`,
> `[scrub-canon]`, and `[skill-rewrite]` bypass specific gates and
> make the human intent explicit in `git log` — they are required for
> legitimate cross-cutting work.

---

## 5 · Versioning (`metadata.version`)

Every `SKILL.md` carries `metadata.version: "X.Y.Z"` (SemVer 2.0.0).

| Bump | When |
|---|---|
| **MAJOR** (1.0.0 → 2.0.0) | Renamed skill, removed a documented section, removed a `USE FOR` trigger phrase, broke a downstream skill's contract |
| **MINOR** (1.0.0 → 1.1.0) | New documented section, new template/reference file, new `USE FOR` trigger, new optional capability |
| **PATCH** (1.0.0 → 1.0.1) | Typo fix, clarified wording, expanded an example, replaced a deprecated flag with the new one, fixed a broken link |

Bump rules:
- A scrub that doesn't change semantics (PoC name → generic placeholder) is
  **PATCH** at most — often no bump needed if the resulting prose is
  effectively identical
- Adding the `metadata.version` block itself the first time was the seed
  `1.0.0` (already done across the catalog as of `182bfbf`)
- **Never set `0.x.y`** — every skill in this repo is production-ready or it
  doesn't ship
- One PR can bump multiple skills, but the **commit message** must list each
  bumped skill and the bump category

### 5.1 Plugin versioning (`plugin.json` `version`)

The root `plugin.json` follows SemVer. Since the plugin auto-discovers
all skills via `"skills": "skills/"`, version bumps track **catalog-level**
changes — adding/removing skills, changing the plugin description or
keywords.

| Bump | When |
|---|---|
| **MAJOR** | Renamed plugin, restructured the repo (e.g. 3→1 plugin collapse), broke install path |
| **MINOR** | Added a new skill to `skills/`, new keyword/category, expanded the description |
| **PATCH** | Tightened wording in the description, fixed a typo |

Marketplace.json **must** be updated whenever the plugin's version
bumps — both `version` fields must match.

There is no automation that enforces plugin version bumps (same as
skills). Reviewers catch missing bumps.

---

## 6 · The user-scope mirror

Most contributors keep a working copy at `~/.copilot/skills/<skill-name>/`
so the runtime picks up edits without re-installing. Two places, one truth:

| Location | Role | Updated by |
|---|---|---|
| `C:\Users\<u>\Repos\awesome-gbb\skills\<skill>\` | **Source of truth** — what gets pushed to GitHub | All edits land here first |
| `C:\Users\<u>\.copilot\skills\<skill>\` | **Runtime mirror** — what Copilot CLI actually loads | Manually synced from source |

### Sync workflow (after editing in the repo)

```powershell
$repo = "C:\Users\<u>\Repos\awesome-gbb\skills\<skill>"
$user = "$env:USERPROFILE\.copilot\skills\<skill>"
robocopy $repo $user /MIR /XD .git /NFL /NDL /NJH /NJS
# Verify parity:
Get-FileHash $repo\SKILL.md, $user\SKILL.md -Algorithm SHA256
```

### Sync workflow (after editing in user scope)

If you iterated on the runtime mirror first (typical when debugging a
running agent), mirror back to the repo with the same `robocopy /MIR` in
the reverse direction, then commit.

> **Don't let drift accumulate.** Two-way drift is hard to reconcile —
> always sync in one direction at a time, then verify with SHA256.

### Plugin testing (local marketplace)

Register the repo as a local marketplace to test the plugin:

```bash
# Unix
copilot plugin marketplace add /absolute/path/to/awesome-gbb
copilot plugin install awesome-gbb@awesome-gbb
```

```powershell
# Windows
copilot plugin marketplace add 'C:\Users\<u>\Repos\awesome-gbb'
copilot plugin install awesome-gbb@awesome-gbb
```

This consumes the actual `plugin.json` at the repo root. If you edit
a skill under `skills/<name>/`, run `copilot plugin update awesome-gbb@awesome-gbb`
to pick up the change.

After your PR lands and you want to switch to the canonical remote:

```bash
copilot plugin marketplace remove awesome-gbb       # the local one
copilot plugin marketplace add aiappsgbb/awesome-gbb # the canonical one
copilot plugin update awesome-gbb@awesome-gbb
```

---

## 7 · References & shared data

### Canonical reference data

The threadlight-design and threadlight-demo-data-factory reference data
(industry shorthand, synthetic data generators) now live in
[`aiappsgbb/threadlight-skills`](https://github.com/aiappsgbb/threadlight-skills).
The § 2.2 "do NOT normalize" rule still applies there.

### Bicep modules

Live in **`azd-patterns/`** (the composable module library). Do not fork
module shapes in other skills — extend the library.

### Templates

Per-skill `templates/` directories hold copy-paste artifacts (Dockerfiles,
pyproject.toml, container.py, etc.). When updating a template, also update
the prose in `SKILL.md` that explains it — the two must stay in sync.

### Per-skill `references/` directories — SSOT for non-trivial code

When a SKILL has a `references/<lang>/` directory, each file there is the
**single source of truth** for the snippet it represents. SKILL.md MUST NOT
duplicate that code body inline. Use a one-line cross-link instead:

```markdown
> **MUST:** Copy verbatim from [`references/python/main.py`](references/python/main.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.
> That file is the canonical FoundryChatClient bootstrap for hosted agents.
```

Keep inline ONLY:
- Configuration *fragments* that show a single key/value in context
  (e.g. `dependsOn: [rbac]` wiring snippets, hardcoded-UUID demos that
  intentionally differ in shape from the env-var-driven reference)
- Subset / shape-variant examples that are **short (≤ 20 lines), explicitly
  incomplete, and prose-annotated to call out how they differ from the
  canonical reference.** A truncated example without an explicit "this is
  a structural excerpt — full version in …" callout is a duplication
  violation, not a variant.

Forbidden:
- Re-pasting a function/class body that exists in `references/`
- "Canonical reference files: see also..." callouts that list 6 files
  by hand. Use an imperative table mapping each file to the SKILL.md
  § it documents (see `foundry-hosted-agents/SKILL.md` for the pattern).
- Truncating the canonical block (removing imports / a few cases) and
  dropping it inline as an "excerpt". That is the duplication anti-pattern
  the validator was added to catch — the excerpt drifts, then ships wrong.

Header convention inside each reference file (validator-enforced):

```python
"""Canonical <one-line description>.

Source of truth for the prose example in `../../SKILL.md § <Section Title>`.
...
"""
```

The validator (`scripts/validate-skills.py`) checks:
1. Every `.py`/`.sh`/`.yaml`/`.json`/`.bicep` under `references/` parses /
   compiles cleanly (catches drift from the inline snippet that used to
   ship in SKILL.md).
2. Every `§ <Section Title>` in a reference-file header resolves to a
   matching `##` / `###` heading in the sibling SKILL.md (catches the
   "renamed the section but forgot the header" silent drift).

Python helpers under `references/` — invoked by Copilot-CLI fixtures
(via Bash tool calls) or by any future test code — MUST be imported as
real Python modules (package layout, `sys.path` injection, or
`PYTHONPATH` — whatever fits the host fixture), never redefined inline.
See existing `skills/<name>/references/python/*` modules paired with
their `skills/<name>/test-fixture/consumer_prompt.md` files for the
pattern.

---

## 8 · Pre-push validation

Run these in the repo root before `git push`:

```powershell
# 1. YAML parses on every SKILL.md
python -c "
import yaml, pathlib, sys
ok = True
for p in pathlib.Path('skills').rglob('SKILL.md'):
    try:
        fm = p.read_text(encoding='utf-8').split('---')[1]
        d = yaml.safe_load(fm)
        if not d.get('name') or not d.get('description'):
            print(f'MISSING name/description: {p}'); ok = False
        if not d.get('metadata', {}).get('version'):
            print(f'MISSING metadata.version: {p}'); ok = False
        if len(d['description']) > 1024:
            print(f'DESCRIPTION TOO LONG ({len(d[\"description\"])}): {p}'); ok = False
    except Exception as e:
        print(f'PARSE ERROR {p}: {e}'); ok = False
sys.exit(0 if ok else 1)
"

# 2. Rebuild the docs site (GitHub Pages has NO server-side build)
python3 scripts/build-site.py --out docs/

# 3. Forced-text diff inspection of every modified file
git --no-pager diff -a HEAD~1

# 4. Smell-check for forbidden strings
git --no-pager diff HEAD~1 | Select-String -Pattern "kyc-poc|card-dispute-investigation|threadlight-v[123]|ricchi"
```

These checks are also enforced by CI (§ 9.6) — `skill-validation.yml`
covers YAML parsing, description length, forbidden strings, and SemVer.
Running them locally before push catches failures faster.

> **🔴 Before you push: did you test on Azure?** Steps 1–4 above are
> lint. They do NOT prove the skill works. If your changes touch Azure
> paths (SDK calls, Bicep, CLI commands, credential chains), you MUST
> have tested live before pushing. See § 2.9.

---

## 9 · Skill freshness lifecycle

Every wrapper skill in the catalog declares a **machine-readable upstream
pin** so the catalog can detect drift over time without humans manually
checking 32 README files every quarter.

### 9.1 · Three freshness tiers

| Tier | Marker file | What's tracked |
|------|-------------|----------------|
| **A** — SHA-pinned wrapper | `references/upstream-pin.md` with `freshness_tier: A` | github SHA via `git ls-remote` + commits-since-pin |
| **B** — SDK / preview-API wrapper | `references/upstream-pin.md` with `freshness_tier: B` | PyPI version + upstream issue closure |
| **C** — internal IP | `references/last_validated.yaml` (lightweight) | days since human validation (cutoff: 180 days) |

Schema reference: [`scripts/templates/upstream-pin.template.md`](scripts/templates/upstream-pin.template.md).
The pin file's YAML front-matter is the contract; the prose below is the
human audit trail. Keep them in sync.

### 9.2 · Automation tier

Each pin file declares an `automation_tier`:

- **`auto`** — drift opens an issue **assigned to `@Copilot`**. The
  GitHub Copilot coding agent autonomously executes the pin file's
  `validation.script`, opens a PR, and the standard CI gates review
  it. A human reviews and merges.
- **`issue_only`** — drift opens an unassigned issue. Validation requires
  credentials (Azure subscription, Foundry project) that we don't ship
  to the coding agent. A human authors the refresh.

**Rules** (enforced by [`scripts/validate-skills.py`](scripts/validate-skills.py)):

- If `validation.requires` is restricted to safe categories (`github_only`,
  `pypi`) and `validation.runnable: true`, the pin runs in **every** CI run
  (both standard and Azure-credentialed modes of `pin-validation.yml`).
- If `validation.requires` includes credentialed resources (`azure_subscription`,
  `foundry_project`):
  - `automation_tier: auto` + `validation.runnable: false` → pin runs **only**
    under `run-pin-validation.py --include-azure` (Azure-credentialed CI
    mode). The coding agent edits the pin; CI validates it live against
    Azure.
  - `automation_tier: issue_only` + `validation.runnable: false` → pin is
    **never** auto-executed; refresh is human-driven via an issue.
  - `validation.runnable: true` with credentialed requires is **rejected** —
    the agent has no way to actually run it. Set `runnable: false` and pick
    one of the two tiers above.

### 9.3 · The weekly loop

[`.github/workflows/skill-freshness.yml`](.github/workflows/skill-freshness.yml)
runs every Monday 07:00 UTC and on-demand via `workflow_dispatch`.
For each skill it runs five drift detectors:

1. **SHA drift** — `git ls-remote <repo> <ref>` vs `pinned_sha`
2. **Package version drift** — PyPI JSON API vs `packages[*].version`
3. **Upstream issue closure** — GitHub API on `known_issues[*].upstream_url`
4. **Link rot** — HEAD on each `docs_to_revalidate[*]` URL
5. **Validation age** — `today - last_validated > 180 days`

Signals are **consolidated per skill** — one issue per skill, listing all
drift signals with an impact classification:

| Impact | Label | Typical signals |
|--------|-------|-----------------|
| 🔴 CRITICAL | `impact:critical` | Package MAJOR bump, deprecated API in code |
| 🟠 HIGH | `impact:high` | Upstream KI closed (workaround removal opportunity) |
| 🟡 MEDIUM | `impact:medium` | Package MINOR bump, SHA drift, validation age > 180 days |
| 🟢 LOW | `impact:low` | Link rot, package PATCH bump (auto-covered by `~=`) |

Issue title format: `🔄 Refresh \`<skill>\` — <N> signal(s), impact: <level>`.
Auto-tier issues are assigned to `@Copilot`. The coding agent reads
[`.github/copilot-setup-steps.md`](.github/copilot-setup-steps.md) for
its setup contract.

### 9.4 · Re-pin procedure (manual or coding agent)

When upstream advances:

1. **Update front-matter** in the pin file:
   - `upstream.pinned_sha` → new SHA (for SHA drift)
   - `packages[*].version` → new version (for PyPI drift)
   - `known_issues[*].status` → `closed_upstream_fixed` (for closure)
2. **Run `validation.script`** with the new pin value. Each
   `expected_output[*]` substring must appear in stdout.
3. **🔴 If the skill touches Azure → TEST LIVE (§ 2.9).** The
   validation script (step 2) proves imports resolve. It does NOT prove
   the skill works against real Azure resources. Before proceeding, run
   the skill's Copilot-CLI fixture via `copilot-cli-matrix` OR
   manually verify with real Azure API calls (credential chain, endpoint
   reachability, model inference) and paste the output into the PR body.
   **pip + import is necessary but NOT sufficient.** Skip this step
   only for skills that never connect to Azure (e.g., `gbb-humanizer`,
   `ghcp-cli-config`).
4. **Update audit trail**:
   - `last_validated: <today>`
   - `validated_by: <handle>` (or `copilot-bot`)
5. **Bump SKILL.md `metadata.version` PATCH** (X.Y.Z → X.Y.(Z+1)).
   Per § 5, pin refresh is PATCH — not MINOR.
6. **Open PR** touching ONLY `references/upstream-pin.md` and
   `SKILL.md` frontmatter. The
   [`automation-pr-gate.yml`](.github/workflows/automation-pr-gate.yml)
   workflow rejects anything else (unless the appropriate opt-in tag is
   in the commit message).
7. **PR description MUST include evidence of live testing** — link to
   CI run, paste of test output, or screenshot. Reviewers reject PRs
   without evidence (§ 2.9).

### 9.5 · Authoring a pin file from scratch

For a new wrapper skill, copy
[`scripts/templates/upstream-pin.template.md`](scripts/templates/upstream-pin.template.md)
to `skills/<name>/references/upstream-pin.md` and fill every
`<placeholder>`. The most important fields:

- `validation.script` — must be a **copy-paste runnable bash script**.
  The coding agent reads this as the executable spec. Narrative
  steps ("verify the agent works") are forbidden — write real shell.
- `validation.expected_output` — substrings the script prints on
  success. The agent greps these to decide pass/fail.
- `known_issues[*].upstream_url` — for each documented workaround,
  link to the upstream issue/PR. The detector polls these weekly; when
  the upstream issue closes, the skill is flagged for re-validation
  WITHOUT the workaround.

#### 🔒 Pin/cap policy on `validation.script` pip installs

Every `pip install` in `validation.script` MUST use a **bounded
specifier**. There are exactly three accepted patterns:

| Pattern | When to use |
|---------|-------------|
| `~=X.Y.Z` (PEP 440 compatible release) | Default for stable releases. Equivalent to `>=X.Y.Z, <X.(Y+1).0`. Patch upgrades inside the cap window are auto-covered, no PR needed. |
| `==X.Y.ZaN` / `==X.Y.ZbN` / `==X.Y.ZrcN` | Pre-releases (alpha/beta/rc/dev). Cap math doesn't survive across pre-release boundaries, so exact pin is the only safe choice. |
| `~=X.Y` | Library where the maintainer commits to backward-compat across the minor — only with explicit author justification in `notes:`. |

Forbidden patterns:
- Bare `==X.Y.Z` for stable releases (caught the foundry-agt 1.3.0 → 1.4.0
  refresh — `pin-validation.yml` rejects unbounded auto-bumps).
- Bare `>=X.Y.Z` (no cap → next major can break silently).
- Unpinned package name (`pip install pkg`).

This policy is enforced both by the cap-aware
[`pin-validation.yml`](.github/workflows/pin-validation.yml) gate (which
re-runs the script on the runner) and by reviewer eyeball.

### 9.6 · Six CI gates that protect the catalog

| Gate | When | What it checks |
|------|------|---------------|
| [`skill-validation.yml`](.github/workflows/skill-validation.yml) | Every PR touching `skills/**`, `plugin.json`, or `.github/plugin/**` | Frontmatter parses, description ≤ 1024, valid SemVer, no forbidden strings, pin files conform to schema v2, **plugin.json + marketplace.json valid and version-consistent** |
| [`automation-pr-gate.yml`](.github/workflows/automation-pr-gate.yml) | Every PR touching `skills/**` | The § 4 mass-edit invariants — see that section |
| [`pin-validation.yml`](.github/workflows/pin-validation.yml) | Every PR touching anything under `skills/<skill>/` | **Re-runs `validation.script` on the runner** for the pin file of every changed skill (any SKILL.md / `references/*` edit invalidates the skill's live contract until re-validated); asserts every `expected_output` substring. No "trust me, I tested" path. Skills without a pin file are silently skipped. |
| [`skill-freshness.yml`](.github/workflows/skill-freshness.yml) | Weekly cron + on-demand | Detection (no PR gating) — opens issues for drift |
| [`skill-test.yml`](.github/workflows/skill-test.yml) | Every PR + push to main + weekly cron | **Live execution suite**: unit tests, catalog lint, and `copilot-cli-matrix` (one runner per skill — a real Copilot CLI agent reads SKILL.md and executes its fixture against real Azure resources in `<ci-resource-group>`: deploys, API calls, model inference). Legacy pytest-based E2E + pin-import smoke were retired; see the header comment on the workflow. |
| [`auto-merge-copilot.yml`](.github/workflows/auto-merge-copilot.yml) | On check suite completion | **Auto-approves and merges** Copilot PRs when all CI gates pass — zero human intervention for routine pin refreshes |

The first three run on every PR. The fourth detects drift autonomously.
The fifth runs on every PR (including Copilot's) and on push/schedule.
The sixth closes the loop: when all checks pass on a Copilot PR, it
auto-approves and squash-merges without waiting for human review.

### 9.7 · Azure CI credentials and E2E infrastructure

The repo has OIDC-federated Azure credentials and a dedicated CI
resource group hosting persistent E2E infrastructure. The concrete
identifiers (subscription ID, resource group name, account names,
endpoint URLs) are NOT documented in this public repo — they live in
two places only:

1. **GitHub repo Secrets** (Settings → Secrets and variables → Actions)
   — consumed by `.github/workflows/skill-test.yml` at runtime
2. **`.env.ci`** (gitignored) — for local maintainer-side manual E2E
   runs; copy [`.env.ci.example`](.env.ci.example) and fill in the
   real values

If you need the real values, ask a maintainer. Below we describe the
shape of the infrastructure using placeholders so the documentation
stays useful without leaking inventory.

**OIDC identity:**

| Secret | Purpose |
|--------|---------|
| `AZURE_CLIENT_ID` | Client ID of `<ci-uami-name>` (UAMI in `<ci-resource-group>`) |
| `AZURE_TENANT_ID` | Entra tenant hosting the CI subscription |
| `AZURE_SUBSCRIPTION_ID` | Dedicated CI subscription (single-region, single-RG) |

**E2E infrastructure** (all in `<ci-resource-group>`, single region):

| Resource | Placeholder | Purpose |
|----------|------|---------|
| AI Services | `<ci-foundry-account>` | Foundry host for agent / eval / memory tests |
| Model deployment | `<model-deployment-name>` | Cheapest GPT-5 family SKU for smoke tests |
| Embedding deployment | `<embedding-deployment-name>` | `text-embedding-3-small` on `GlobalStandard` (Pattern 21) |
| Container Registry | `<ci-container-registry>` | Container image builds for hosted-agent / ACA tests |
| Container App Environment | `<ci-container-app-env>` | ACA deploy tests (services and Jobs) |

**Endpoint secrets:**

| Secret | Shape |
|--------|-------|
| `AZURE_AI_ENDPOINT` | `https://<ci-foundry-account>.cognitiveservices.azure.com/` |
| `FOUNDRY_PROJECT_ENDPOINT` | `https://<ci-foundry-account>.services.ai.azure.com/api/projects/<ci-foundry-project>` |
| `ACR_LOGIN_SERVER` | `<ci-container-registry>.azurecr.io` |

**RBAC on `<ci-uami-name>`:**
- Contributor on `<ci-resource-group>`
- AcrPush on `<ci-container-registry>`
- Cognitive Services OpenAI User on `<ci-foundry-account>`
- Foundry User on `<ci-foundry-account>`
- Role Based Access Control Administrator on `<ci-foundry-account>`,
  ABAC-constrained via `--condition` to only grant role GUID
  `53ca6127-db72-4b80-b1b0-d745d6d5456d` (Foundry User). Needed because
  the `ghcp-hosted-agents` fixture's Step 1c (per SKILL.md KI-001) must
  grant `Foundry User` at account scope to the **per-agent-instance
  MIs** that `azd ai agent` creates fresh on every `azd up`. Without
  this, the UAMI's `Contributor` does NOT include
  `Microsoft.Authorization/roleAssignments/write` (Azure RBAC design),
  the postdeploy grant fails with `AuthorizationFailed`, and the BYOK
  invoke returns 401 with the silent SSE error described in
  `ghcp-hosted-agents/SKILL.md` § "Identity & RBAC for hosted agents".
  The ABAC condition makes this strictly least-privilege: UAMI can ONLY
  hand out Foundry User on this single Foundry account scope and
  nothing else. Provision once:
  ```bash
  az role assignment create \
    --assignee-object-id "$UAMI_OBJECT_ID" \
    --assignee-principal-type ServicePrincipal \
    --role "f58310d9-a9f6-439a-9e8d-f62e7b41a168" \
    --scope "/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.CognitiveServices/accounts/$ACCT" \
    --condition "@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] ForAnyOfAllValues:GuidEquals {53ca6127-db72-4b80-b1b0-d745d6d5456d}" \
    --condition-version "2.0" \
    --description "ghcp-hosted-agents fixture KI-001 — least-privilege RBAC admin"
  ```

**Federated credentials are narrow — these are the ONLY allowed subjects:**

| Subject pattern | Why |
|-----------------|-----|
| `pull_request` | Every PR-triggered CI run |
| `ref:refs/heads/main` | `push: main` + `schedule:` runs |
| `ref:refs/tags/*` | Release tag pushes |

`workflow_dispatch` against a non-`main` branch (e.g. a PR feature branch)
fails with `AADSTS700213: No matching federated identity record found`,
because the OIDC token's `sub` claim becomes `ref:refs/heads/<feature>`
which isn't in the FIC list. Two consequences:

- **Stability re-runs for CI gate verification MUST trigger via
  `pull_request synchronize`,** not `workflow_dispatch`. Push an empty
  commit to the PR branch: `git commit --allow-empty -m "..." && git push`.
- **Cross-PR-branch dispatch is impossible without expanding the FIC
  list** (intentional — keeps the credential blast radius small).

Workflows use `azure/login@v2` with OIDC — no stored secrets or service
principal passwords.

#### CI fixture patterns (lessons from `foundry-prompt-agents` pilot)

Three patterns proved load-bearing during Task 2.1 of the
`2026-05-30-deep-audit-and-testing-rethink` plan. Future fixtures (Task
2.2, 2.3, and the Phase 3 rollout) MUST follow them:

1. **Empty-commit stability runs must be spaced ≥ 45 s apart, one push
   per run.** GitHub coalesces simultaneous pushes into a single
   `pull_request synchronize` event regardless of whether the target
   workflow has a `concurrency:` block — coalescing happens at the
   event-routing layer, not the workflow-scheduling layer. A 5-run
   stability series MUST be 5 separate `git push` invocations, each
   waiting for the previous CI run to start before the next is queued.

2. **Result contract on Copilot CLI transcripts is whole-file grep,
   FAIL beats PASS, never `tail`.** The CLI emits an unsuppressible
   footer (`Changes`, `Duration`, `Tokens`) AFTER the agent reply, so
   `tail -n 1 | grep 'SMOKE_RESULT=PASS'` always fails. The matrix job
   uses:

   ```bash
   if grep -q '^SMOKE_RESULT=FAIL' transcript.log; then
     echo "::error::Fixture reported FAIL"
     exit 1
   fi
   if grep -q '^SMOKE_RESULT=PASS$' transcript.log; then
     exit 0
   fi
   echo "::error::No SMOKE_RESULT marker"
   exit 1
   ```

   `copilot -s` / `--silent` is **present in the CLI** (`copilot --help`
   on 1.0.57-3 documents it as "Output only the agent response"). Task
   2.3's empirical probe on **macOS Copilot CLI 1.0.57-3** confirmed the
   footer IS suppressed — `copilot -s -p "say hi" 2>&1 | tail -30`
   emitted only the agent reply, no `Changes` / `Duration` / `Tokens`
   block; `-s` and `--silent` behaved identically. **Linux runner probe
   is still outstanding** (the GitHub-hosted runner's pre-installed CLI
   build is unverified). Until that confirmation lands, the
   grep-whole-transcript + FAIL-beats-PASS contract above is the
   canonical pattern. Task 2.4 owns the Linux probe + cross-fixture
   simplification rollout (`tail -n 1 | grep -q "^SMOKE_RESULT=PASS$"`
   shrinks each fixture's result-contract block by ~80 lines).

3. **Agent / resource names in fixtures MUST carry a UUID suffix.**
   Parallel matrix runners (and retries from the same SHA) collide on
   fixed names. Canonical pattern:

   ```python
   import uuid
   agent_name = f"ci-smoke-pa-{uuid.uuid4().hex[:8]}"
   ```

   ACA service names, ACR image tags, agent display names, environment
   names — all of these need short-UUID suffixes when authored in a
   fixture under `skills/<name>/test-fixture/`.

4. **Do NOT add a `concurrency:` block to `skill-test.yml`** (lesson
   from Task 2.2). Earlier coordinator diagnosis claimed the workflow
   was auto-cancelling overlapping runs — that was wrong. The 5
   apparent-cancellations on `06ea5ef..5d6b2ef` were either manual
   `gh run cancel` or GitHub's job-matrix supersede-on-newer-commit (a
   different mechanism, scoped per-matrix-leg, not workflow-level).
   `skill-test.yml` deliberately has no concurrency block so two
   overlapping PR pushes still both produce a green-or-red signal.
   The ≥ 45 s empty-commit spacing in pattern 1 above is for
   **audit-trail correlation hygiene** (one run = one SHA = one
   commit message), not to avoid auto-cancel.

5. **Autoregressive priming defeats anchored grep — `_MOKE_RESULT`
   placeholder is the standard defense.** In `actions/runs/26693703357`
   the same workflow run had the prompt-agents matrix leg emit the
   marker clean while the parallel hosted-agents leg emitted it
   wrapped in backticks (`` `SMOKE_RESULT=PASS` ``), defeating
   `^SMOKE_RESULT=PASS$`. Root cause: the fixture body discussed
   `SMOKE_RESULT` repeatedly in prose with backtick decoration, and
   the LLM's autoregression carried that decoration into the final
   marker emission. **Defense** (now baked into both Task 2.1 and
   Task 2.2 fixtures; MUST be the template for every future fixture):

   - In the fixture body, render the literal token as `_MOKE_RESULT`
     (substitute `_` for the leading `S`) so the prompt itself never
     ships an anchored-grep-matching string. The fixture explicitly
     tells the agent to substitute back to literal `S` in its own
     reply.
   - Enumerate WRONG patterns (`` `…` ``, `**…**`, leading whitespace,
     trailing punctuation, blockquote prefix, emoji) with `←` callouts
     so the agent has explicit negative examples.
   - Place the single RIGHT pattern LAST so it primes the continuation
     more strongly than any WRONG example.
   - Forbid backticks (or any decoration) around `SMOKE_RESULT`
     anywhere else in the agent's reply — preamble, intermediate
     status lines, summaries — because each prior decorated mention
     primes the final emission.
   - Forbid `exec > >(tee -a "$LOG") 2>&1` and any process-substitution
     pattern in shell heredocs. The Copilot CLI's shell wrapper blocks
     these as "dangerous shell expansion" (run `26693703357`,
     20:09:44Z). The runner already captures stdout — agents do not
     need to tee.

6. **Explicit `azd auth login` Step 0, not implicit OIDC pickup**
   (Task 2.2 finding to apply forward). When a fixture uses `azd`,
   make the federated-credential exchange explicit:

   ```bash
   azd auth login \
     --federated-credential-provider github \
     --client-id "$AZURE_CLIENT_ID" \
     --tenant-id "$AZURE_TENANT_ID"
   ```

   Current hosted-agents fixture relies on `azure/login@v2` writing
   `AZURE_FEDERATED_TOKEN_FILE` for azd's auto-detection. That path
   has two silent failure modes: (a) `azd` CLI < 1.5.0 doesn't
   auto-detect the file → hangs on interactive login → 30-min
   workflow timeout; (b) sub-shell env reset blanks the credential
   mid-run. ~2 s overhead per fixture run; mirrors what a customer
   reading SKILL.md verbatim would run on their own machine; surfaces
   credential failures up-front instead of buried inside `azd
   deploy`'s ACR push.

7. **Pre-granted-RBAC preamble pattern** (Task 2.2 finding). When a
   fixture exercises Azure resources whose RBAC is pre-provisioned in
   `<ci-resource-group>`, the fixture preamble MUST:

   - Explicitly list the pre-granted RBAC (subject + role + scope)
   - State "do NOT re-grant these — propagation takes 5-15 min and
     races your 30-min workflow timeout"
   - When two identities are involved (e.g., a Foundry project MI
     pre-granted at pull-time vs. a per-agent instance MI provisioned
     per-deploy), distinguish them by name and explain which retry
     loop owns each
   - Reserve any retry-with-backoff to the identity whose MI is
     created per-deploy (the per-agent-instance MI), not the
     pre-granted one

   The hosted-agents fixture (`skills/foundry-hosted-agents/test-fixture/consumer_prompt.md`
   L37-50) is the canonical template. The single biggest waste in
   the first `unsafecode/pr-review` cycle was a fixture re-granting
   AcrPull and racing propagation against the timeout.

8. **`azd deploy` does NOT cover ACA Jobs — hand-roll `az deployment
   group create` + `az containerapp job start`** (Task 2.3 finding).
   SKILL.md `azd-patterns` L26 documents this explicitly: there is no
   `azd-service-name` tag for `Microsoft.App/jobs` that `azd deploy`
   recognises. `azd up` against a job-only Bicep provisions the resource
   group + a placeholder image but never pushes the real image. Any
   fixture whose marquee surface is an ACA Job (the `azd-patterns`
   fixture; future fixtures for ACA-Job-variant skills like potential
   `foundry-mcp-aca` jobs / threadlight-skills jobs) MUST therefore
   build two variants of the canonical fixture template:

   - **Service variant** — `azd up` happy path (works for ACA Services)
   - **Job variant** — `az deployment group create` for the Bicep +
     `az containerapp job start` to execute, because `azd deploy`
     cannot trigger a job execution

   The `skills/azd-patterns/test-fixture/consumer_prompt.md` fixture is
   the canonical reference for the **Job variant**;
   `skills/foundry-hosted-agents/test-fixture/consumer_prompt.md` is the
   canonical reference for the **Service variant**.

9. **ACA control-plane consistency races are fixture-side retries, NOT
   workflow-level retry-classifier work** (Task 2.3 finding,
   generalising the Task 2.2 `AcrPull` precedent). Observed races so
   far, all 5–15 s windows:

   - `AcrPull` permission propagation after Bicep deploy (Task 2.2)
   - `JobExecutionNotFound` from `az containerapp job execution show`
     immediately after a successful `az containerapp job start` (Task
     2.3 — observed during fixture authoring, ~5-15 s window)
   - `Forbidden` from any dataplane call during RBAC propagation
   - `ResourceProvisioningInProgress` from concurrent ARM operations

   **Defense:** wrap the relevant CLI call in a bounded retry loop in
   the fixture itself (6 iterations × 5 s back-off = 30 s budget is the
   Task 2.3 pattern). Do NOT add these tokens to the workflow's
   transient-classifier regex — the precedent set by both Task 2.2 and
   2.3 is that ACA-control-plane races belong inside the fixture's
   "what success looks like" definition, not in workflow-level
   infrastructure. The cost of a fixture retry loop is bounded (~30 s
   per call) and visible in the transcript; a workflow-level retry
   re-runs the entire 8–15-min matrix leg.

   When you observe a NEW ACA-control-plane race that isn't in this
   list, add it here and document the retry budget. Do not assume a
   single shared retry helper — the back-off math is per-API.

10. **Marker-omission bug class — make marker emission a NUMBERED FINAL
    STEP, not a postscript** ⚠️ **SUPERSEDED by Pattern 12** (the
    numbered-final-step imperative was necessary but not sufficient —
    run [`26697592828`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26697592828)
    PA leg, 2026-05-30, emitted prose `"the smoke emitted \`SMOKE_RESULT=PASS\`"`
    despite a numbered-final-step imperative; the LLM stochastically
    decorated the marker in prose). **Keep this pattern's defenses in
    fixtures as belt-and-braces, but Pattern 12 below — file-write via
    Bash tool — is the load-bearing path.** Original Task 2.4 finding
    (root cause of `foundry-prompt-agents`
    leg in run [`26695861103`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26695861103)).

    Even with `_MOKE_RESULT` placeholder defense (Pattern 4) and an
    explicit "Result contract" section, an agent CAN declare success in
    prose and then stop without ever emitting the anchored
    `^SMOKE_RESULT=PASS$` line. The CI grep then fails on a fixture leg
    that did all the real work correctly — pure marker-omission, not
    skill failure.

    **Forensic signature** (run 1, PA leg): transcript contains
    "lifecycle complete", "all assertions held", explicit per-step
    confirmations — but NO marker line of any form (bare, backticked,
    placeholder). Agent emitted its prose summary, hit the CLI footer
    boundary, and exited. The result contract was treated as descriptive
    background instead of an executable terminal step.

    **Defense — copy the `azd-patterns` fixture's "Step 6 — Emit the
    result marker" pattern across every Copilot-CLI fixture:**

    1. The result contract MUST be the LAST major numbered step
       (e.g. "Step N — Emit the result marker"). Not a sidebar, not a
       trailing "Result contract" section, not a header above
       authoring notes. **It is work the agent has to perform.**
    2. Spell out the imperative: "Print exactly one line to stdout that
       matches `^SMOKE_RESULT=PASS$` (no backticks, no leading spaces,
       no prose after)."
    3. Add an explicit rule: "If you have already declared success in
       prose, you are not done. The run is not complete until you emit
       the marker line."
    4. The FINAL line of the fixture body should be that imperative —
       so the autoregressive continuation has marker-emission as the
       most recent priming context.
    5. Continue using `_MOKE_RESULT` placeholder in any explanatory
       prose ABOVE the final-step block (Pattern 4 still applies).

    **Don't relax the workflow grep** (`grep -q '^SMOKE_RESULT=PASS$'`
    against the whole transcript, FAIL-first). The grep is doing its
    job — it's the fixture that has to make marker emission
    non-skippable. A looser grep (e.g. `grep PASS`) buys flake in
    exchange for false positives on any prose mention of the word.

11. **Workflow env contract — explicit `AZURE_*` exports are mandatory,
    NOT defensive paranoia** (Task 2.4 finding; root cause of
    `foundry-hosted-agents` leg in run
    [`26695861103`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26695861103)).

    `azure/login@v2` (passed `client-id` / `tenant-id` / `subscription-id`
    as `with:` inputs) authenticates the Azure CLI's TOKEN CACHE. It
    does **NOT** automatically export `AZURE_CLIENT_ID`,
    `AZURE_TENANT_ID`, or `AZURE_SUBSCRIPTION_ID` into the workflow
    step env. Bash subprocesses that Copilot CLI spawns inherit the
    workflow step's env block — not the CLI cache. If a fixture
    references `$AZURE_CLIENT_ID` (for `azd auth login`,
    `azd env set AZURE_TENANT_ID`, or any explicit credential
    inventory), those variables are empty strings unless the workflow
    explicitly puts them in the env block.

    **Forensic signature** (run 1, HA leg): transcript contains a
    `printenv | grep AZURE` step that returns ~1 line
    (`AZURE_HTTP_USER_AGENT=…`), agent concludes "missing CI env vars
    in shell", emits `SMOKE_RESULT=FAIL`. This is NOT agent paranoia —
    the agent is correct. The env vars genuinely were missing.

    **Defense — TWO mandatory edits, both required:**

    - **Workflow side** (`.github/workflows/skill-test.yml` →
      `copilot-cli-matrix` job):

      Every step that runs a fixture (initial run AND retry step) MUST
      include `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and
      `AZURE_SUBSCRIPTION_ID` in its `env:` block, sourced from the
      same secrets that the `azure/login@v2` step uses:

      ```yaml
      env:
        # … existing COPILOT_*, AZURE_AI_ENDPOINT, ACR_LOGIN_SERVER …
        AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
        AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
        AZURE_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      ```

      The initial-run and retry env blocks must be byte-identical for
      the auth contract — otherwise a transient retry runs under a
      different env than the original attempt.

    - **Fixture side** — every Copilot-CLI fixture that calls Azure
      MUST open with a **non-secret inventory + auth-proof** Step 0
      before any work:

      ```
      ### Step 0 — verify CI auth contract

      Run these two commands first. Both MUST succeed before you
      proceed to any other step. If either fails, emit
      `SMOKE_RESULT=FAIL` immediately with the precise failure mode
      and stop.

      1. echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
         echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
         echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"

         Every line MUST print `…=set`. If any is empty, the workflow
         env contract is broken (see AGENTS.md § 9.7 Pattern 11) —
         that is a workflow bug, not a skill bug.

      2. az account show --output table

         MUST return a row whose `SubscriptionId` column matches
         `$AZURE_SUBSCRIPTION_ID`. If `az account show` errors with
         "Please run 'az login'", the `azure/login@v2` step failed —
         workflow bug.

      If both pass, you have a valid auth context. Do NOT invent
      additional credential checks (no `az ad sp show`, no
      `az role assignment list`, no `az login --service-principal`).
      Proceed to Step 1.
      ```

      For `azd`-based fixtures, Step 0 ALSO runs Pattern 6's explicit
      `azd auth login --federated-credential-provider github
      --client-id "$AZURE_CLIENT_ID" --tenant-id "$AZURE_TENANT_ID"`.
      The non-secret inventory above is what makes Pattern 6's
      failure mode (silent token-file pickup) visible BEFORE the
      `azd deploy` step buries it.

    **Don't make the agent re-discover this.** Without the inventory
    Step 0, an agent that hits a missing env var has two equally bad
    options: (a) panic on `printenv` and bail with vague language
    (the run-1 HA failure mode), or (b) silently fall through to
    DefaultAzureCredential and produce a misleading downstream error.
    Step 0 makes the auth contract explicit and the failure precise.

    **Cross-skill carry:** the existing `azd-patterns` fixture has
    Pattern 6 (explicit `azd auth login`) but not the Step 0 inventory
    — it passes 5/5 in CI today because `azd auth login` fails loudly
    if the vars are missing. Retrofit the inventory anyway for
    consistency; the cost is two `echo` lines and one `az account show`.

12. **Deterministic result marker via Bash tool file-write — the
    load-bearing path** (Task 2.4 finding; root cause of
    `foundry-prompt-agents` leg in run
    [`26697592828`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26697592828),
    2026-05-30 23:20:33Z).

    Pattern 10's numbered-final-step imperative reduces but does NOT
    eliminate marker mis-emission. In the failing run, the agent's
    final assistant reply was:

    > Verified end-to-end: the prompt agent was created, chatted with
    > via a conversation, listed, deleted, and the smoke emitted
    > `` `SMOKE_RESULT=PASS` ``.

    The anchored grep correctly rejected this because the marker is
    backtick-wrapped inside prose, not a bare line. Run #1 of the
    same fixture, same skill, different roll, **did** emit a bare line.
    Same prompt, opposite outcomes — pure LLM autoregressive
    stochasticity. No prose hardening can close this; only bypassing
    prose rendering entirely can.

    **Defense — file-based deterministic marker. Two coordinated edits:**

    - **Fixture side** — the final step is an explicit Bash tool
      invocation that writes the marker file. The fixture instructs
      the agent NOT to mention the marker token in prose at all:

      ```markdown
      Step N — Write the result marker (deterministic, MANDATORY).
      After step N-1 succeeds, your FINAL action is to invoke the Bash
      tool to run exactly this command. The file's literal byte content
      is what CI grades — NOT your assistant text reply.

          printf 'SMOKE_RESULT=PASS\n' > /tmp/<skill>-smoke-result

      If ANY prior step fails:

          printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/<skill>-smoke-result
      ```

      Per-skill marker path (matrix-leg isolation): `/tmp/${SKILL}-smoke-result`.

    - **Workflow side** (`.github/workflows/skill-test.yml` →
      `copilot-cli-matrix` job, BOTH the main "Run consumer prompt"
      step AND the "Retry once on classified-transient failure" step):

      ```bash
      set -euo pipefail
      SKILL="${{ matrix.skill }}"
      PROMPT="skills/${SKILL}/test-fixture/consumer_prompt.md"
      TRANSCRIPT="/tmp/${SKILL}-transcript.log"
      MARKER="/tmp/${SKILL}-smoke-result"
      test -f "$PROMPT" || { echo "missing fixture: $PROMPT"; exit 2; }
      rm -f "$TRANSCRIPT" "$MARKER"
      set +e
      copilot -p "$(cat "$PROMPT")" --allow-all-tools --disable-builtin-mcps \
        -C "$GITHUB_WORKSPACE" 2>&1 | tee "$TRANSCRIPT"
      COPILOT_STATUS=${PIPESTATUS[0]}
      set -e
      # Marker file is authoritative
      if [ -f "$MARKER" ]; then
        if grep -qE "^SMOKE_RESULT=FAIL" "$MARKER"; then
          echo "::error::Fixture reported FAIL"; cat "$MARKER"; exit 1
        fi
        if cmp -s "$MARKER" <(printf 'SMOKE_RESULT=PASS\n'); then
          exit 0
        fi
        echo "::error::Marker malformed"; cat "$MARKER"; exit 1
      fi
      # Legacy transcript fallback (retire after 10+ greens on Pattern 12)
      if grep -qE "^SMOKE_RESULT=FAIL" "$TRANSCRIPT"; then exit 1; fi
      if grep -q "^SMOKE_RESULT=PASS$" "$TRANSCRIPT"; then exit 0; fi
      echo "::error::No marker (file or transcript). copilot exit=$COPILOT_STATUS"
      tail -80 "$TRANSCRIPT"; exit 1
      ```

      Three non-obvious choices, all load-bearing:

      1. **`rm -f` BEFORE invocation** — a stale marker from a previous
         step (or, on a retry, the failed first attempt) would otherwise
         dominate the grade. Both main and retry steps clean the same
         path; retry uses the same fixture and same marker path.
      2. **`set +e` around the pipeline + `PIPESTATUS[0]` capture** —
         default GHA bash is `bash --noprofile --norc -eo pipefail`. With
         `-e` + `pipefail`, a non-zero `copilot` exit (timeout, internal
         error) terminates the step BEFORE marker evaluation runs. The
         `|| true` workaround corrupts `PIPESTATUS`, so toggling `-e`
         is the cleanest path to capturing the real copilot status
         while still evaluating the marker.
      3. **`cmp -s "$MARKER" <(printf 'SMOKE_RESULT=PASS\n')`** —
         byte-exact comparison. NOT `grep` — a marker file containing
         `SMOKE_RESULT=PASS\nleftover-prose\n` should FAIL malformed,
         not PASS on the first line match.

    **Marker-FAIL ALWAYS beats marker-PASS** (the order of the
    grep ladder), and the marker file is ALWAYS authoritative over
    the transcript — the transcript fallback exists only as a
    transition-window safety net. **Retirement schedule:** after 10
    consecutive green runs across all 3 pilot fixtures on Pattern 12,
    delete the transcript fallback. Until then keep it so a fixture
    that hasn't been migrated yet still has a chance to grade
    correctly during the rollout.

    **Cross-skill carry:** Pattern 12 is mandatory for every Copilot
    CLI fixture. Pattern 10's WRONG/RIGHT marker-emission rules in
    fixtures can be DELETED once Pattern 12 is in place — the file
    write bypasses the prose-rendering surface entirely, so the
    autoregressive-priming defenses (`_MOKE_RESULT` placeholder,
    no-backticks rule) become unnecessary noise in the fixture body.

    **Why this works.** Bash tool calls produce shell output — bytes
    on disk — not LLM continuations. The model decides to invoke the
    tool with a specific command string; the tool runtime executes
    that string verbatim. There is no markdown rendering layer
    between `printf 'SMOKE_RESULT=PASS\n'` and the bytes that hit
    `/tmp/<skill>-smoke-result`. The only remaining failure mode is
    the model invoking the tool with a DIFFERENT command (e.g.
    `printf 'SMOKE_RESULT=FAIL ...'` when steps actually succeeded)
    — and that surfaces as a fixture-level logic bug, not a stochastic
    rendering bug.

#### Pattern 13 — LAW ingestion lag MUST NOT fail the smoke (Finding #18)

> **Provenance.** First observed on Pattern 12 stability run #1/5 for
> azd-patterns ([`26697996194`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26697996194),
> 2026-05-30 23:54:17 UTC). The matrix leg FAIL'd with
> `SMOKE_RESULT=FAIL LAW latency >120s or HELLO not in console logs`
> — even though Step 3 (`az containerapp job execution show`) had
> already returned `Succeeded` 7 minutes earlier. Pattern 12's marker
> mechanism worked perfectly; the failure was content-side: the
> fixture's LAW polling budget (120 s) was unrealistic against
> documented Azure ingestion latency (p50 ~2 min, p95 ~5 min, p99
> ~10 min). Re-running the workflow was unlikely to help — LAW lag is
> physics, not a transient. Pattern 13 reframes the failure mode.

**The anti-pattern.** A fixture polls Log Analytics for an expected
log row and FAILs on empty result after a tight window (e.g. 60-120 s).
This conflates two distinct signals:

1. **Did the workload succeed?** (control-plane question, answerable
   synchronously: `az containerapp job execution show`, agent
   `status_code`, response body, etc.)
2. **Did the documented telemetry path work?** (observability question,
   answerable only after LAW ingestion has landed — best-effort)

The control-plane signal is **deterministic** (the platform reports
success or failure synchronously). The LAW probe is **best-effort
verification** (the platform reports success synchronously, then logs
arrive asynchronously through an agent pipeline with documented
variable latency). Conflating the two causes flaky failures whenever
LAW ingestion is on the slower end of its distribution.

**The fix.** Three rules for any fixture that probes LAW:

1. **Establish the control-plane success signal FIRST** (a `Succeeded`
   status from `az containerapp job execution show`, an `HTTP 200` +
   non-empty body from an agent invocation, etc.). This is the smoke's
   primary success criterion.
2. **Treat the LAW probe as best-effort verification with a generous
   budget** — minimum 300 s for ACA Job console logs (under typical
   warm-workspace conditions, p95 is comfortably inside this window).
3. **Soft-PASS on LAW lag.** If the control-plane signal is `Succeeded`
   AND the LAW row is empty after the budget, emit a clear NOTE to
   stdout (transcript captures it for audit) and STILL write
   `printf 'SMOKE_RESULT=PASS\n' > /tmp/<skill>-smoke-result`. The
   marker MUST remain byte-exact (Pattern 12's `cmp -s` contract);
   the lag-observed NOTE goes ONLY to the transcript, never to the
   marker file.

**Cross-skill carry.** Any future fixture that probes LAW or another
async telemetry pipeline (App Insights, Foundry traces, eventhub
forwards) needs the same soft-PASS contract. Stamp the rule into the
fixture-authoring checklist. If a customer-pilot E2E later wants a
strict "LAW row MUST appear within window" gate, that belongs in a
**dedicated observability smoke** with its own budget, NOT bolted
onto the skill smoke as a secondary FAIL condition.

**Why we don't just delete the LAW probe.** The documented SKILL.md
log-query pattern (azd-patterns L351-357) is something consumers
copy verbatim — verifying it works occasionally is valuable. The
soft-PASS keeps that verification in the loop without trading
deterministic CI for flaky CI. Frequency of NOTE emission can be
monitored across the matrix to decide whether SKILL.md needs an
explicit "expect LAW lag of N min" warning.

#### Pattern 14 — Job-level `timeout-minutes` MUST exceed observed p99 by ≥ 20% (Finding #19)

**Provenance.** Validating Pattern 13 (LAW soft-PASS) on run
`26698566215` (2026-05-31). The azd-patterns leg's smoke step emitted
`PASS via marker file (deterministic)` at `00:39:37.8348` — and the
runner killed the job 113 ms later at `00:39:37.8461` with
`##[error]The operation was canceled.` because `timeout-minutes: 30`
fired. Job conclusion ended up `cancelled`, masking what was
functionally a green run.

The Pattern 12 + 13 contract worked correctly: marker file written,
`cmp -s` byte-exact PASS, evaluator emitted the deterministic PASS
message. We just had no headroom — observed run time was 30 min 5 s
(setup + azure-login + npm install copilot + copilot prompt for
29 m 48 s including azd Bicep deploy + ACA Job create + execute +
LAW poll 300 s + agent's unsuppressible footer). The 30-min ceiling
left zero margin for the milliseconds-long tail of marker eval.

**Anti-pattern (DO NOT REVERT).**

```yaml
# WRONG — too tight for any leg whose p99 approaches the ceiling
jobs:
  copilot-cli-matrix:
    timeout-minutes: 30   # observed p99 = 30:05 → guaranteed cancellation
```

**Fix (3 rules).**

1. **`timeout-minutes` ≥ p99 × 1.2** (round up to whole minutes). PA
   leg p99 ≈ 5 min, HA leg p99 ≈ 15 min, azd-patterns leg p99 ≈ 30 min
   → the matrix-shared ceiling MUST be ≥ 36 min. Use **40 min** so the
   buffer absorbs npm install variance + GHA scheduler jitter.
2. **Do NOT split `timeout-minutes` per matrix leg.** Matrix legs
   share one job template; per-leg timeouts require duplicating the
   whole `steps:` block. Cost of giving PA/HA the same 40-min ceiling
   = 0 (they finish in 5/15 min, the timer is just an upper bound).
3. **Document the budget breakdown in a comment above the
   `timeout-minutes:` line** so the next sub-agent who sees "40 min,
   that's huge, let's tighten it" understands the floor before
   shaving.

**Cross-skill carry rule.** Any new Copilot-CLI matrix leg added in
the future inherits the 40-min ceiling. If a new leg's p99 grows past
36 min (e.g., a future fixture exercises a multi-resource deploy),
bump the shared ceiling — do NOT bisect this comment block.

**Diagnostic protocol.** If a leg gets `conclusion: cancelled`:
1. Pull the LAST 100 lines of the cancelled job's log
   (`gh run view <id> --log --job=<job-id> | tail -100`).
2. If `PASS via marker file (deterministic)` appears within the last
   ~500 ms before `##[error]The operation was canceled.`, the smoke
   actually passed and the job timed out at the wire. Increase
   `timeout-minutes` per Rule 1 and re-run.
3. If no PASS marker appears, the smoke genuinely failed or hung —
   diagnose the agent's tool-call sequence, NOT the timeout.

#### Pattern 15 — Tooling install belongs in the workflow, not the fixture (Findings #15+#16)

**Provenance.** Run [`26699177054`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26699177054)
HA + azd-patterns legs (SHA `84221eb`). Both legs' Copilot CLI agents
ran identical `command -v azd || find / -name azd` probes, both got
empty results, both fell back to downloading `azd-linux-amd64.tar.gz`
from `aka.ms/install-azd-script-linux`. HA leg burned ~5 min on the
tarball detour and still failed (on Bug C/B downstream, see Findings
#16/#17 in HA audit trail). azd-patterns leg burned ~3 min and barely
made it inside its (then 30 min) ceiling. **Task 2.3's 5/5 green was
luck, not correctness** — the fixture assumed azd was present; the
agent was silently remediating each run.

**Anti-pattern (DO NOT REVERT).**

```markdown
<!-- WRONG — fixture tries to "be portable" by detecting + installing tooling -->
# Step 0: Ensure azd is available
if ! command -v azd >/dev/null 2>&1; then
  curl -fsSL https://aka.ms/install-azd-script-linux | bash
fi
```

```yaml
# WRONG — workflow assumes ubuntu-latest pre-installs all Microsoft CLIs
runs-on: ubuntu-latest
steps:
  - run: azd auth login --federated-token "$AZURE_OIDC_TOKEN"   # ENOENT
```

**Fix (3 rules).**

1. **The workflow installs CLI tooling once, the fixture consumes it.**
   Use the official pinned action (e.g., `Azure/setup-azd@v2.3.0`,
   `Azure/setup-kubectl@v4`, `hashicorp/setup-terraform@v3`,
   `azure/setup-helm@v4`). Pin to a tag or SHA; never to `@main` or
   `@latest`. Place the install step immediately after Copilot CLI
   install so all subsequent `copilot prompt` invocations inherit the
   PATH.
2. **The fixture preamble explicitly forbids hunting/installing.**
   Use Pattern 7-style "infra preconditions" block: name the binary,
   name its install location (`/usr/local/bin/azd`), forbid both
   filesystem hunts (`find /`, `command -v`) and curl-installs
   (`aka.ms/install-azd-script-linux`). The agent treats this as a
   pre-granted capability, same as pre-granted RBAC.
3. **ubuntu-latest pre-installs ONLY a small set of CLIs.** The known
   pre-installed Microsoft CLIs are `az`, `gh`. **Everything else
   needs explicit install:** `azd`, `func`, `mcr`, `kubectl` (after
   v22 image roll), `helm`, `terraform`, plus all third-party tooling.
   When in doubt, install explicitly — the cost of a redundant install
   step is ~10 s; the cost of a fixture silently remediating is
   ~3-5 min per run × every run forever.

**Anti-pattern variant — "install in the agent prompt" (also wrong).**

```markdown
<!-- WRONG — even more wrong: makes every model invocation re-emit the install -->
Step 0: First, install azd with `curl -fsSL https://aka.ms/install-azd-script-linux | bash`.
Step 1: Then run `azd auth login --federated-token ...`
```

The model has to spend tokens reasoning about install before any
domain work. Tokens are not free, latency is not free, and the agent
may decide the install is "optional" if it can't run the command for
any reason. Workflow-level install removes the decision entirely.

**Cross-skill carry rule.** Any new fixture that wraps a CLI tool
checks:
- Is the tool in `{az, gh}`? → no workflow install needed.
- Is the tool elsewhere? → add the official setup action to
  `skill-test.yml` (alphabetical by binary name to keep diffs readable),
  AND add a fixture preamble line naming the tool + install location +
  forbidding hunts.
- Is the tool not yet packaged as a setup action? → `apt-get install`
  step in the workflow with a version pin. Document the pin in
  AGENTS.md § 9.7 alongside this pattern.

**Diagnostic protocol.** If a fixture leg fails with a tool-not-found
or tool-detour symptom:
1. Grep the leg's log for `command not found`, `aka.ms/install-`,
   `tarball`, `curl -fsSL.*\.(tar\.gz|sh)`.
2. If present, the workflow is missing an install step. Add the
   official setup action, pin to a tag or SHA, commit, and reset the
   stability cycle counter.
3. If absent, the binary is installed but failing for another reason
   (auth, env vars, ACA quota, etc.) — diagnose that instead.

**Cost / benefit.** A single `Azure/setup-azd@v2.3.0` step adds ~10 s
to every leg that runs on the matrix. The current matrix has 3 legs
(PA, HA, azd-patterns); at ~150 stability runs/year that's ~75 min
cumulative install time. The avoided cost is ~3-5 min/run × ~80 runs
that would have agent-side remediated = ~5 hours of wasted budget +
the actual failures masking real bugs (Finding #16's
`FOUNDRY_PROJECT_ENDPOINT` extension drift was only visible AFTER the
install detour stopped consuming budget).

#### Pattern 16 — Single-path invoke contract — never branch on preview-CLI flags (Finding #17)

**Provenance.** Run [`26701034360`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26701034360)
HA leg (SHA `2af039d`), 4th stability run on Patterns 12+13+14+15.
Fixture step 5 said:

> Prefer `azd ai agent invoke "${AGENT_NAME}" --message "ping"` if the
> extension version supports the subcommand; otherwise fall back to a
> Foundry data-plane Responses REST call …

The `azure.ai.agents` azd extension in the current build accepts
`azd ai agent invoke` (the **subcommand**) but rejects `--message`
(the **flag**) with `unknown flag: --message`. The model's literal
branch evaluation went: "subcommand exists → take CLI path → flag
fails → conclude broken → emit `SMOKE_RESULT=FAIL azd ai agent
invoke: unknown --message flag`". The fallback was reached **only on
subcommand absence**, not flag absence. Three prior runs had passed
because the model non-deterministically chose the REST fallback first.
SKILL.md L1264 actually documents `azd ai agent invoke "Hello!"` as
**positional** — the fixture invented the `--message` flag.

Same run had a second compounding bug: the preamble's
`az account show` assertion ("MUST return a row whose SubscriptionId
matches `$AZURE_SUBSCRIPTION_ID`") invited the model to write a
strict subscription-ID equality check, which failed twice on shell
quoting before the invoke step even ran.

**Anti-pattern (DO NOT REVERT).**

```markdown
<!-- WRONG — branch on preview-CLI flag presence -->
5. Prefer `azd ai agent invoke "${AGENT_NAME}" --message "ping"` if the
   extension version supports the subcommand; otherwise fall back to a
   Foundry data-plane Responses REST call …
```

```markdown
<!-- WRONG — strict-equality preamble assertion invites brittle compares -->
az account show MUST return a row whose SubscriptionId matches
`$AZURE_SUBSCRIPTION_ID`.
```

**Fix (3 rules).**

1. **For preview-unstable CLI surfaces, prescribe the GA SDK/REST
   path ONLY.** Preview CLI flag surfaces drift across versions
   (`--message` → `--prompt` → positional → removed). The Python SDK
   surface (`AIProjectClient(allow_preview=True).get_openai_client(agent_name=...).responses.create(input=...)`)
   is GA-stable. Document the SDK call inline in the fixture; never
   write `if CLI works, else fall back to SDK`. The model takes
   branch logic literally; partial CLI success without flag
   recognition will NOT trigger the fallback.
2. **Preamble assertions: "show, don't assert".** For workflow-
   provided context (subscription ID, OIDC token, env vars), the
   fixture should print the state for the run log only. The workflow
   has already validated the context before invoking the agent.
   Strict-equality compares (`[[ "$(... -o tsv)" == "$ENV_VAR" ]]`)
   in the fixture body invite the model to invent stale-quoting
   variants that false-FAIL. Only existence checks
   (`[[ -n "$ENV_VAR" ]]`) and "did the command error?" are allowed.
3. **One-shot fixture invokes use the SYNC SDK.** `AIProjectClient`
   has both sync and async variants. In-container code
   (`FoundryChatClient` etc.) uses async; one-shot fixture invokes
   should use sync (`from azure.ai.projects import AIProjectClient`,
   not `.aio`). Async-in-Bash-heredoc invites event-loop pitfalls.

**Cross-skill carry rule.** Any new fixture invoking an Azure
preview-CLI surface (azd extensions, `az` preview commands) checks:

- Is there a GA SDK / REST path that does the same thing? → use
  that exclusively. Add an explicit "Do NOT use `<cli-cmd>` — its
  flag surface is preview-unstable" rule.
- Is the CLI the only path? → pin the CLI flag set in the fixture
  preamble: name the exact flags + values + expected behaviour.
  Add a "if `<cli-cmd>` exits non-zero with `unknown flag`, the
  binary version on PATH has drifted from this fixture — bump the
  workflow's setup-action SHA and reset the stability counter"
  diagnostic.

**Diagnostic protocol.** If a fixture leg fails with `unknown flag`
or `unknown subcommand`:

1. Grep the failed agent's log for `unknown flag:|unknown subcommand:|unknown command:`.
2. Cross-reference the offending CLI invocation against the
   documented SKILL.md signature (the SKILL is the contract).
3. If the fixture invented the flag → fix the fixture (rewrite to
   the GA SDK path or correct the flag).
4. If the SKILL also has the wrong signature → the upstream CLI
   drifted. Bump the SKILL and the fixture together; reset the
   stability counter.

**Cost / benefit.** SDK-only invoke adds ~1 s for `pip install -q
azure-ai-projects azure-identity openai` (pre-cached on second run
of the stability cycle). Removed cost: the entire class of `unknown
flag`/`unknown subcommand` non-deterministic failures across every
preview-CLI fixture. The HA leg's flap rate (4 runs to first
failure × ~13 min per run = ~52 min wasted budget on Pattern 15
cycle alone) drops to zero under the SDK path.

#### Pattern 17 — Show-don't-assert on `az` CLI state (Finding #18)

**Provenance.** Run [`26703036366`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26703036366)
azd-patterns leg (SHA `d390033`), 4th stability run on Pattern 16
foundation. The fixture's Step 0 preamble asserted:

> If this errors with "Please run 'az login'", `azure/login@v2` failed
> upstream — FAIL with `az account show: not logged in`.

The agent's transcript:

> **Blocked:** the smoke couldn't proceed because `az account show`
> was not logged in in this shell, so the required Azure auth
> precondition was missing. I wrote the failure marker with that
> reason.

Wall-clock: ~6 min (vs the ~13 min expected for a real deploy) — the
fast-fail at Step 0 is the smoking gun. Three prior runs (`9a79d2a`,
`8dcc536`, `c2b4d50`) passed because the `~/.azure/azureProfile.json`
cache happened to be visible in the spawned shell; run #4 fell on the
wrong side of the race.

**Root cause.** This is the fixture-side enforcement of the contract
already documented in Pattern 11 (workflow env contract): copilot CLI
subprocesses **inherit the workflow step's `env:` block but NOT the
`az` CLI credential cache** at `~/.azure/`. The `azure/login@v2`
action writes its OIDC-exchanged credentials to that cache, but
whether the subshell sees the file depends on:

- shell-creation semantics (POSIX `bash -l` vs `bash` vs `sh`)
- whether the GHA runner's `$HOME` is preserved across the
  copilot-cli subprocess boundary
- the order in which the action's post-step credential cleanup runs
  relative to the in-progress subprocess

None of these are deterministic. Three of five recent runs got lucky;
one didn't. The fixture asserted on the lucky path and called the
unlucky one a failure.

The fixture itself runs `azd auth login --federated-credential-provider
github` **immediately after** the broken `az account show` assertion.
That command **is** the deterministic OIDC exchange — it consumes the
inherited `AZURE_*` env vars (which ARE deterministic per Pattern 11)
and produces a fresh `azd` token. The `az` cache check was redundant
to begin with, and adding a hard FAIL on its absence turned it from
"redundant" to "actively harmful".

**Anti-pattern (DO NOT REVERT).**

```markdown
<!-- WRONG — assert on inherited cache that may not be visible -->
- **Prove `az` is actually authenticated.**

  ```bash
  az account show --output table
  ```

  If this errors with "Please run 'az login'", `azure/login@v2`
  failed upstream — FAIL with `az account show: not logged in`.
```

**Fix.**

```markdown
- **Show-don't-assert: `az` CLI state.** Per Pattern 11, copilot CLI
  subprocesses inherit env vars but NOT `~/.azure/`. Cache visibility
  is non-deterministic. Print for the audit log; do NOT gate flow:

  ```bash
  az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
  ```

  **No assertion. `azd auth login` (next step) is the auth gate.**
```

**General rule (extends Pattern 16 rule 2).** "Show, don't assert"
applies to any workflow-provided credential or context that the
fixture re-reads:

| Asserted on | Anti-pattern | Pattern |
|------|------|------|
| Subscription-ID equality | `[[ "$(az account show ...)" == "$ENV_VAR" ]]` | 16 |
| `az` cache presence | `az account show \|\| FAIL` | 17 |
| `azd` cache presence | `azd auth login --check-only \|\| FAIL` | 17 |
| Inherited env-var values matching a *form* | `[[ "$ENV_VAR" =~ ^[a-f0-9-]{36}$ ]]` | 17 |
| OIDC token claim contents | jwt-decode + claim compare | 17 |

The only allowed assertion shape on workflow-provided context is
existence (`[[ -n "$VAR" ]]`) — for everything else, **print and move
on**. The actual cred validation happens when a real Azure call is
made (Foundry SDK, `azd up`, `az containerapp create`); let *those*
calls fail loudly and the agent will report the real error.

**Cross-skill carry rule.** All 3 pilot fixtures
(`foundry-prompt-agents`, `foundry-hosted-agents`, `azd-patterns`)
shipped the same anti-pattern and were patched in the same commit
that introduced Pattern 17. Any future fixture that touches `az` or
`azd` CLI state in its preamble MUST use the show-don't-assert form
from day one — there is no "first I'll get the assert version working
locally, then soften it" path; the assert version passes locally
because your `~/.azure/` is always populated.

**Diagnostic protocol.** If a fixture leg fails with a Step 0/precondition
error mentioning `az account show` or `azd auth login --check-only`:

1. Verify the run is fast (≤ 8 min vs ≥ 13 min for real deploy work).
   A fast-fail is the smoking gun for Pattern 17.
2. Grep the failed agent's transcript for `not logged in` or
   `Please run 'az login'`.
3. Confirm the workflow's `azure/login@v2` step succeeded (it almost
   always will — the failure is downstream of OIDC exchange).
4. Patch the fixture's preamble to the show-don't-assert form. Bump
   the SKILL.md PATCH version. Reset the stability counter to 0/5.

**Cost / benefit.** Show-don't-assert costs nothing (the `||
echo "(...)"` clause is < 50 ms). Removed cost: the entire class of
non-deterministic preamble false-FAILs across every Azure fixture.
The azd-patterns leg's flap rate (3 of 4 runs passed → 4th failed on
inheritance race) drops to zero — the only way the fixture can fail
on auth now is if `azd auth login` itself fails, which means the
workflow's OIDC exchange genuinely broke (a real signal worth FAILing
on).

#### Pattern 18 — Retry classifier covers ARM cross-resource cache lag (Finding #19)

**The bug.** Run `26704135920` (azd-patterns leg, SHA `c94d607`) failed
with `ManagedEnvironmentNotFound` for `<ci-container-app-env>` during
`az deployment group create`. The CAE existed at deploy time with
`provisioningState: Succeeded` (verified post-mortem from a local
`az containerapp env show`), and the **same agent**, in the **same
job**, reproduced the deployment as `Succeeded` via a direct
`az containerapp job create` after the Bicep path failed. This is an
ARM cross-resource index-rebuild race: the deployment engine's resolver
takes 30 s – 5 min to "see" newly-touched `Microsoft.App` resources
even after CRUD on the resource itself returns 200 OK.

**Why the pre-Pattern-18 retry regex missed it.** The classifier on
`skill-test.yml` L298 covered `429|503|throttl|capacity|EOF during
azd deploy|revision .* not found` — the dataplane/Foundry transients
the catalog had seen previously. `ManagedEnvironmentNotFound` is an
ARM **control-plane** transient and never landed in the regex because
no prior fixture had triggered it (the HA fixture uses `azd deploy`
which goes through its own retry layer; only the azd-patterns ACA-Jobs
fixture takes the raw `az deployment group create` path that exposes
the ARM resolver race).

**The fix.** Extend the classifier on `skill-test.yml` L298 to:

```
429|503|throttl|capacity|EOF during azd deploy|revision .* not found|ManagedEnvironmentNotFound|ResourceNotFound.*Microsoft\.App
```

The added alternatives are **anchored on `Microsoft.App`** — the
resource provider with the slowest ARM index-rebuild path. Generic
`ResourceNotFound` across all providers would mask real consumer-
written bugs (e.g., a typo in a resource name). The anchored form
catches the ARM-cache-lag class without false-positive risk.

**Detection in future failures.** If a fixture FAILs and the failure
log contains the literal token `ManagedEnvironmentNotFound`:

1. Verify the resource exists right now via
   `az containerapp env show -g <rg> -n <name>` — if `state: Succeeded`,
   the production resource is healthy.
2. Confirm the failure was during `az deployment group create`, not
   `azd deploy`. The latter has its own retry layer.
3. If both hold, the regex caught it (or should have) and the retry
   leg will pass.

**Cost / benefit.** The retry leg costs one extra `copilot` invocation
when triggered (~$0.005 + ~3 min wall-clock). The class of false-FAIL
this catches: any ARM cross-resource lookup against `Microsoft.App`
that hits the resolver in its pre-warmed window. Across the catalog,
that's every ACA-Jobs / ACA-Apps fixture that uses Bicep — currently
azd-patterns only, but threadlight-skills and any future ACA-on-Bicep
skill will benefit.

#### Pattern 19 — Retry classifier needs jittered cooldown for matrix-leg races (Finding #20)

**Provenance.** Run [`26711407035`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26711407035)
(SHA `cd5213a`), Phase 3 6-leg matrix. The `foundry-hosted-agents` leg
hit `CAPIError: 429 Too Many Requests` from the **Copilot CLI's own
backing model** (not the Foundry deployment under test) while
parallel matrix legs were spinning their own copilot processes.
Retry leg also hit 429 a few seconds later because both legs were
re-running in lockstep against the same shared CLI-backing-model
quota.

**The fix.** Extend the retry classifier on `skill-test.yml` to
include `CAPIError|Too Many Requests|Failed to get response from
the AI model|transient API error` AND space the retry by ≥ 30 s
random jitter (`sleep $(( RANDOM % 30 + 30 ))`) so concurrent legs
don't re-fire into the same throttle window. Combined with
Pattern 22's `max-parallel: 2` throttle, this collapses the 429
flap rate to zero on subsequent runs (verified
[`26711952364`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26711952364)
+ [`26714879734`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26714879734)).

**Cross-skill carry rule.** Any future fixture that calls a model
through Copilot CLI (i.e. every Copilot-CLI fixture) inherits this
class of failure. The retry classifier + jitter is workflow-side
and protects all legs automatically; no fixture-side change needed.

**🔄 ADDENDUM (2026-06-10, run [`27296618970`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/27296618970)).**
The "Copilot CLI's own backing model" framing above is **correct only
when CLI runs on its default backend**. The catalog's CI sets
`COPILOT_PROVIDER_TYPE=azure` + `COPILOT_PROVIDER_BASE_URL=
${secrets.AZURE_AI_ENDPOINT}` + `COPILOT_PROVIDER_MODEL_ID=gpt-5.4-mini`
in `skill-test.yml`, so every `copilot -p` invocation in CI calls
**our own `gpt-5.4-mini` deployment in `aif-awesome-gbb-ci`** — not
the GitHub-backed CAPI quota. Consequences:

1. `CAPIError 429` in CI now maps to **our TPM cap** (currently 545K
   = Sweden Central regional ceiling on `gpt-5.4-mini` GlobalStandard,
   shared with 455K of other allocations).
2. The jittered 90-180s cooldown was sized for GitHub's RPM windows.
   Azure OpenAI TPM throttle windows are minute-scale (60s rolling),
   but **deep saturation** (one large request followed by burst calls)
   can take 3-5 min to clear. See Pattern 26 for the second-retry leg
   that handles this case.
3. Per-request token cost matters now. Each fixture agent message
   counts ~200K+ tokens against TPM (prompt+context+tools+cached
   tokens count at full rate for rate-limiting). Cutting fixture
   prompt size (especially the SHARED CI HARDENING preamble — see
   `.github/ci-shared-preamble.md`) is the single biggest lever
   short of more quota.
4. `max-parallel: 2` (Pattern 22) was sized assuming the CAPI quota.
   On our Azure routing, that ceiling is now driven by deployment TPM
   and by the per-call burst, not by a per-account ceiling. A future
   experiment may raise this back to 3-5 after deployment-side
   quota work lands.

**TL;DR:** Pattern 19's retry-classifier regex is still correct
(matches CLI's surfaced 429s regardless of backend). The cooldown
math and `max-parallel` cap need re-tuning against actual TPM
consumption per fixture once Pattern 26 data accumulates.

**🔄 ADDENDUM v2 (2026-06-10, post-PR-#240 retries).** Run
`27300950746` (cost-monitoring + observability matrix at SHA
`76d2ddb`, sequential — not parallel) showed CAPI 429 on
cost-monitoring DESPITE no concurrent leg consuming TPM. Forensic:

- Cost-monitoring 19:32:06 → 19:36:58 (~5 min) — FAILED 429
- Observability   19:37:00 → 19:50:22 (~13 min) — PASSED

The cost-monitoring fixture had a `view skills/foundry-cost-monitoring/SKILL.md`
mandate (added to defeat audit-grep false-negatives). SKILL.md is
~23 KB → Copilot CLI's `view` tool reads it in 4 chunked turns →
each turn re-uploads the full conversation context (system prompt
~50K + tools ~20K + prior chunks ~50K each) → single agent turn
hit ~250-300K tokens uploaded. Foundry's gpt-5.4-mini deployment
in Sweden Central caps at 545K TPM (regional ceiling) → one such
turn consumes 46-55% of TPM → next CLI internal-retry within
seconds → 92%+ → CAPI 429 → CLI's 5 immediate retries all hit
the same 429 within 30 ms. The workflow's retry classifier
correctly fires Retry-1, but Retry-1 rebuilds the same massive
context and 429s again.

**Per-fixture token budget rule (mandatory):**

| Per-turn upload | Risk vs 545K TPM ceiling |
|---|---|
| ≤ 50K  | Safe at max-parallel: 2 |
| 50-150K | Safe sequential; risky parallel |
| 150-300K | One turn is 50%+ of TPM → CAPI 429 inevitable on a follow-up turn within the minute |
| > 300K | Saturation in a single turn → 429 immediately |

Fixtures that exceed 150K per-turn MUST be one of:
1. Reduced (don't read large repo files via the `view` tool;
   use targeted `view_range` if you must)
2. Rewritten to avoid loading SKILL.md into agent context
   entirely (use a lightweight `echo skills/foundry-X/SKILL.md`
   in a Bash step to satisfy audit-grep without context bloat —
   the cost-monitoring fixture's Step −1 v3 is the canonical pattern)
3. Moved to a dedicated single-leg matrix at `max-parallel: 1`
   with cooldown bumped to Pattern 26's 240-360s

**Why the audit-grep false-negative path matters.** The workflow's
post-hoc audit step greps the agent's transcript for `skill(name)`,
`SKILL.md`, or `skills/<name>/` to detect freelancing. If the agent
follows a fully-explicit fixture without ever uttering the skill
name path, audit fails even when every smoke step succeeded.
**The lightweight fix** (canonical pattern): the fixture's first
mandatory action is a single Bash `echo "skills/<skill-name>/SKILL.md"`
that produces the audit-grep evidence at ~50 tokens of context cost.
DO NOT mandate `view SKILL.md` — that's 5-10K+ tokens compounded
across chunked reads. See the cost-monitoring fixture
`Step −1 — Acknowledge skill contract` for the canonical form.

#### Pattern 20 — Copilot CLI cannot read `~/.copilot/installed-plugins/` for fixture skills (Finding #21)

**The bug.** Earlier Phase 3 attempts tried to ship the `awesome-gbb`
plugin to the CI runner via `gh skill install` so the fixture could
reference the very skill under test by name. The Copilot CLI's
plugin-resolution path only reads from its bundled marketplace
registry at startup, NOT from `~/.copilot/installed-plugins/` on the
runner. The agent had no awareness of any locally-installed skill,
so "use foundry-hosted-agents to deploy …" prompted from a fixture
would be treated as plain English, not a skill reference.

**The fix.** Fixtures MUST be **self-contained goal prompts** — they
state the task in plain English ("create a hosted agent that …") and
the agent is expected to know how to do it from its **general training
+ the SKILL.md content pasted into the prompt body via the existing
audit-step guard**. The fixture file is therefore the test surface,
not a `Use skill X` directive. This pattern is now load-bearing for
every Copilot-CLI fixture in the catalog (PA, HA, evals, memory,
toolbox, azd-patterns all follow it).

**Cross-skill carry rule.** Never write `Use the foundry-X skill`
in a fixture. Always state the goal directly. The agent will use
the SKILL.md context the workflow provides, not a plugin lookup.

#### Pattern 21 — Sweden Central requires `GlobalStandard` SKU for embedding deployments (Finding #22)

**The bug.** Earlier `foundry-memory` fixture iteration tried to
deploy `text-embedding-3-small` with the default `Standard` SKU in
Sweden Central. ARM rejected with `InvalidResourceProperties: Sku is
not supported in this region`. Sweden Central, our CI region, only
offers embeddings under `GlobalStandard`.

**The fix.** When provisioning embedding models in Sweden Central
(the CI region), the deployment SKU MUST be `GlobalStandard`. This
applies to the standing `text-embedding-3-small` deployment in
`<ci-foundry-account>` and to any future embedding deployment used
by a fixture. Chat completion models (`gpt-5.4-mini`, `gpt-5.4`)
work fine under `Standard` in Sweden Central — only embeddings
need `GlobalStandard`.

**Cross-skill carry rule.** Any fixture or skill that documents
embedding-deployment provisioning in Sweden Central MUST specify
`sku: { name: "GlobalStandard" }` in its Bicep / azd template.
Cross-check region capacity before changing region — other regions
(EastUS, EastUS2) accept `Standard` for embeddings.

#### Pattern 22 — Throttle matrix parallelism to ≤ 2 to avoid CLI-backing-model 429s (Finding #23)

**Provenance.** Run [`26711407035`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26711407035)
ran the 6-leg matrix at default GHA `max-parallel: 5` and
**deterministically** hit `CAPIError: 429 Too Many Requests` on
the heaviest leg (`foundry-hosted-agents`). The Copilot CLI's
backing model has per-account RPM quota that 5 parallel legs of
`copilot -p` consume in seconds. After fix
([`47112b2`](https://github.com/aiappsgbb/awesome-gbb/commit/47112b2)),
run [`26711952364`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26711952364)
ran 5/6 GREEN at `max-parallel: 2`; the only remaining failure was
Pattern 23 (different bug entirely).

**The fix.**

```yaml
# .github/workflows/skill-test.yml
copilot-cli-matrix:
  strategy:
    max-parallel: 2   # Pattern 22 — Copilot CLI's own backing model
                      # has tight RPM quota; 3+ parallel copilot -p
                      # invocations from the same runner-account hit
                      # CAPIError 429. 2 is the verified safe ceiling.
```

**Trade-off.** Wall-clock for a full 6-leg matrix grows from
~25 min (max-parallel=5, with retries) to ~30-35 min
(max-parallel=2, stable). The wall-clock cost is worth it — flap
rate goes from "first 429 within seconds" to zero across the next
two stability runs.

**Cross-skill carry rule.** Do NOT raise `max-parallel` above 2
without a quota-side change. If you need more throughput, the
correct path is to run smaller targeted matrices via the
change-gating in Pattern 24 (`build-test-matrix.py --changed-only`)
— not to fan out wider.

**🔄 ADDENDUM (2026-06-10).** See Pattern 19's addendum: in our CI
the 429 source is **our `gpt-5.4-mini` deployment in
`aif-awesome-gbb-ci`** (currently 545K TPM, Sweden Central regional
cap), not GitHub's CAPI quota. The `max-parallel: 2` ceiling still
applies — with 545K TPM and ~226K tokens per agent message,
3+ parallel legs trivially saturate. Raising this ceiling requires
either (a) more deployment TPM (cross-region GlobalStandard, or
PTU), or (b) fixture token diet (smaller prompts, less cached
context).

#### Pattern 23 — Foundry project MI is the THIRD identity, needs separate `Cognitive Services OpenAI User` grant (Finding #24)

**Provenance.** Run [`26711952364`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26711952364)
(SHA `47112b2`), `foundry-memory` leg job
[`78723651792`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26711952364/job/78723651792).
Memory store creation succeeded, but the **Foundry-internal memory
consolidation worker** returned 401 when calling the chat deployment
to extract semantic memories. Three rounds of forensic log capture
(596-line `/tmp/mem-job-78723651792.log`, lines 192, 418, 425) showed
the 401 came from the server-side worker hitting
`https://cognitiveservices.azure.com` with a token issued to an
identity that was NOT the CI UAMI used by every other passing leg.

**The three identities** in `<ci-foundry-account>`, NONE of which
overlap by default:

| # | Identity | Object ID | Default RBAC | Used by |
|---|---|---|---|---|
| 1 | **Account SAMI** | `fbe3089f-…` | Empty | Account-level system tasks (rarely used directly) |
| 2 | **Project `ci-test` SAMI** | `8c1b62da-…` | **Only ACR roles** | **Foundry server-side workers** (memory consolidation, hosted-agent runtime, evals graders) |
| 3 | **CI UAMI** | `ff405901-…` | Contributor + AcrPush + Cog OpenAI User + Foundry User | Every CI fixture's direct deployment calls |

The 5 passing legs (PA, HA, evals, toolbox, azd-patterns) all call
deployments **directly** with identity #3 (the UAMI) which has the
right roles. Memory uniquely triggers identity #2 because Foundry's
memory consolidation runs server-side as the **project** MI, NOT the
caller's UAMI.

**The fix.** Grant `Cognitive Services OpenAI User` AND `Cognitive
Services User` to the **project MI** at **account scope**:

```bash
SUB=<ci-subscription-id>
ACCT_SCOPE=/subscriptions/$SUB/resourceGroups/<ci-resource-group>/providers/Microsoft.CognitiveServices/accounts/<ci-foundry-account>
PROJECT_MI_OBJECT_ID=8c1b62da-a294-4bec-b1eb-e5664b7bd490  # from `az cognitiveservices account project show`

az role assignment create --assignee-object-id $PROJECT_MI_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services OpenAI User" --scope $ACCT_SCOPE
az role assignment create --assignee-object-id $PROJECT_MI_OBJECT_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services User" --scope $ACCT_SCOPE
```

Wait ≥ 5 min for AAD propagation, then re-trigger.
[`26714879734`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26714879734)
verified the fix: memory leg GREEN in 13 min after the grant.

**Cross-skill carry rule.** Any fixture that exercises a Foundry
server-side worker (memory, hosted-agent runtime callbacks, eval
graders running in the project, server-orchestrated retrievals) MUST
either (a) confirm the project MI already has the right Cog roles,
or (b) include a pre-fixture RBAC grant step in a CI bootstrap
script. The audit step must check identity #2's role assignments,
not just identity #3's.

**Diagnostic protocol.** When a fixture fails with 401 from an
Azure call:

1. Determine which identity the call ran as. If the SDK call was
   direct (your code) → identity #3 (UAMI). If the call was
   triggered by `AIProjectClient.beta.memory_stores.create(...)`,
   `AgentRunner.run(...)`, an eval grader invocation, etc.
   → identity #2 (project MI).
2. List role assignments on identity #2:
   `az role assignment list --assignee $PROJECT_MI_OBJECT_ID --all`.
3. If `Cognitive Services OpenAI User` or `Cognitive Services User`
   is missing on the account scope → Pattern 23. Grant + wait
   ≥ 5 min + retry.

**Why this lurks.** Identity #2 is created automatically when a
Foundry project is created; the create flow grants ACR roles
(needed for hosted-agent image pulls) but not Cog roles (because
the user might not deploy chat models). The catalog's CI used to
ride on identity #3 for everything, so this gap was invisible
until the first server-orchestrated workload (memory) landed.

#### Pattern 24 — Change-gated matrix saves 80% of CI cost on iterative PRs (Finding #25)

**Provenance.** Phase 3 matrix expansion (PA + HA + evals + memory
+ toolbox + azd-patterns = 6 legs × ~5-18 min each = ~75 min of
runner time per full PR push). Iterative debugging on a single skill
(e.g. 5 stability runs on memory alone) would burn ~375 min of CI
budget if the full matrix re-ran every time.

**The fix.** [`scripts/build-test-matrix.py`](scripts/build-test-matrix.py)
gained `--changed-only --base-ref <sha>` flags. The PR-triggered
workflow path computes `git diff $base_ref..HEAD`, maps changed
files to changed skills, applies **forward fanout** from
[`.github/skill-deps.yml`](.github/skill-deps.yml) (if A changed
and B `depends_on` A, run B too), and forces a full matrix on
**input-contract changes** (`.github/workflows/skill-test.yml`,
`.github/quarantine.yml`, `.github/ci-shared-preamble.md`). The
`push: main` and `schedule:` paths always run the full matrix.

**What's deliberately NOT in the force-full list:**

- `plugin.json` + `.github/plugin/marketplace.json` — metadata
  manifests. A new skill is detected via its own `skills/<name>/`
  paths in the natural diff; a pure version bump has zero per-leg
  test impact.
- `scripts/build-test-matrix.py` — the matrix builder itself.
  Decides WHICH legs run, not what they do. Logic regressions are
  caught by 12 unit tests in
  [`scripts/tests/test_build_test_matrix.py`](scripts/tests/test_build_test_matrix.py)
  + the push-to-main canary. Keeping it in FORCE_FULL caused a
  chicken-and-egg: every fix to the matrix logic fanned out the
  full matrix, costing ~30 min per iteration.
- `.github/skill-deps.yml` — read live by `_load_dep_map` for forward
  fanout. Adding a NEW entry (the common case when registering a
  new skill) is purely additive — it doesn't change existing fanout
  edges. Removals/renames are rare and covered by
  `validate-skills.py` (cycle + unknown-ref checks) + the
  push-to-main canary.

Treating any of these as infra (the original design) fired a full
14-leg matrix on PR #240's `4.14.0 → 4.15.0` plugin bump (1 line of
metadata) + on every subsequent matrix-builder iteration. Catch-rate
for structural drift is preserved by the weekly + push-to-main
full-matrix paths within ≤7 days.

**Cost / benefit.** A PR that touches only `foundry-memory/test-fixture/`
runs ONE leg (memory) instead of six. A new-skill PR like #240 runs
the new skill + its forward-fanout (2 legs) instead of 14. Wall-clock
for an iterative retry drops from ~30 min to ~13 min; budget cost
drops 5/6 on iterative PRs, ~12/14 on new-skill PRs. Catch rate is
preserved because the full matrix still runs on `main` and weekly,
and forward fanout protects against upstream-skill changes silently
breaking downstream consumers.

**Cross-skill carry rule.** When you add a new fixture, also add
an entry to `.github/skill-deps.yml` even if `depends_on: []`. The
matrix-builder's "all fixtured skills" set is derived from this
file; a missing entry → your fixture never runs in CI even when
its files change.

**Gotcha.** Change-gating diffs against `github.event.pull_request.base.sha`,
which is the **target branch's HEAD** (usually `main`). So iterative
retries on the SAME PR will still re-include every fixture that's
been touched anywhere in the PR's commit history, not just the
last commit. This is correct behaviour (the PR as a unit must
pass), but means the cost savings show on PRs that touch a
**subset** of skills, not on iterative-retry cycles.

#### Pattern 25 — Teardown is best-effort, NOT a success criterion (Finding #26)

**Provenance.** Run [`26714879734`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26714879734)
(SHA `e06ca76`, stability #1) HA leg passed in 15m27s — right AT the
OIDC federated-credential TTL boundary. Run
[`26715679675`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26715679675)
(SHA `72b77d8`, stability #2) HA leg `78733744851` failed at 17m22s
because teardown ran past that boundary. Forensic transcript:

> Deploy succeeded. Invoke returned `billing` (valid label). Then
> the agent spent ~7 minutes searching for an `azd ai agent delete`
> subcommand that does not exist in the current `azure.ai.agents`
> azd extension. By the time it pivoted to REST DELETE, the OIDC
> assertion had expired → 401. Wrote `SMOKE_RESULT=FAIL teardown
> blocked: federated auth expired before delete`.

The skill contract — `azd deploy` produces a working hosted agent,
agent answers correctly — was **proven** end-to-end. The fixture
then false-FAIL'd on cleanup of resources the SKILL.md doesn't
even guarantee a deterministic delete path for.

**Root cause.** Two compounding factors:

1. **Hosted-agent teardown is preview-CLI-unstable** (extends
   Pattern 16). The `azure.ai.agents` azd extension exposes
   `invoke` but not `delete`; the documented teardown path drifts
   across extension versions (data-plane REST one quarter, azd
   subcommand the next). An agent following the fixture goal
   literally will spend wall-clock budget discovering this gap.
2. **OIDC federated-credential TTL is bounded** (~5-10 min after
   `azd auth login`). Any teardown phase that exceeds that window
   401s on the next data-plane call. The TTL is **not** a per-token
   refresh — `azure/login@v2` exchanges ONCE per workflow step and
   that exchange has a fixed lifetime.

These compose: the longer teardown discovery takes, the more
likely it crosses the TTL. Stability #1 happened to land inside
the window (15m27s); stability #2 didn't (17m22s). Both runs
exercised the SKILL contract identically.

**Anti-pattern (DO NOT REVERT).**

```markdown
<!-- WRONG — hard FAIL when teardown fails -->
On ANY failure (auth, skill not found, azd deploy failure, invoke
error, invalid response, teardown failure):

    printf 'SMOKE_RESULT=FAIL <reason>\n' > /tmp/<skill>-smoke-result
```

```markdown
<!-- WRONG — no budget; agent hunts for delete path until OIDC dies -->
When you're done, tear down everything you created (the agent,
the ACA app, and the ACR repository).
```

**Fix — three rules.**

1. **Separate hard success criteria from best-effort hygiene.**
   The fixture's PASS marker MUST be conditioned ONLY on the
   skill-contract surfaces (deploy succeeded + invoke returned
   the expected shape). Teardown is hygiene; it goes in a
   separate sentence in the fixture goal with explicit
   best-effort framing. Pattern 13 (LAW soft-PASS) is the
   precedent — same shape applied to a different async surface.

2. **Bound teardown with a wall-clock budget.** Cap the teardown
   phase at 5 minutes (single-API fixtures) or 10 minutes
   (multi-resource fixtures like ACR repo + ACA app + agent
   version). Past the cap, the fixture STOPS hunting and writes
   the marker. The budget MUST be smaller than the OIDC TTL
   floor (~5 min observed) for single-API teardown, or the
   fixture MUST be re-architected to re-`azd auth login` if it
   genuinely needs a longer cleanup window. **Do NOT** chase
   token refresh in fixtures — it's an order-of-magnitude more
   complexity than the contract this catalog is testing.

3. **Soft-PASS with a transcript NOTE on teardown failure.**
   When deploy + invoke succeed but teardown fails or times out,
   emit a single NOTE line to stdout (transcript captures it for
   audit) describing what couldn't be cleaned up. STILL write
   `printf 'SMOKE_RESULT=PASS\n'` to the marker file. The NOTE
   makes orphan resources discoverable; the PASS marker keeps
   CI green on a passing contract.

**Cross-skill carry rule.** Any fixture that creates Azure
resources beyond the immediate skill-contract surface
(supporting ACR repos, ACA managed env children, RBAC role
assignments, side-deployed identities, agent versions,
Foundry threads/runs) inherits Pattern 25. The rule:

| Resource created for | Teardown FAIL classification |
|---|---|
| Direct skill contract output | Hard FAIL (the contract IS the resource) |
| Supporting infra the skill happens to need | Best-effort soft-PASS |
| Side artefacts (logs, traces, generated docs) | Soft-PASS (auto-prune in CI RG) |

If you can't decide which row a resource lives on, ask: "Would
a customer following SKILL.md verbatim consider this resource
part of what they asked for?" YES → hard. NO → best-effort.

**Janitor contract.** The `<ci-resource-group>` resource group
is the catch-all for orphaned fixture resources under Pattern
25. A periodic cron (manual today; automation deferred) prunes:

- ACR repositories matching `ci-smoke-*` older than 7 days
- Foundry agent versions matching `ci-smoke-*` older than 7 days
- ACA Container Apps matching `ci-smoke-*` older than 7 days
- Role assignments scoped to deleted principals

The janitor's existence is what lets fixtures soft-PASS without
unbounded resource leak. Do NOT use Pattern 25 in production
deployments — the janitor lives only in CI infrastructure.

**Diagnostic protocol.** If a fixture leg fails with a 401, an
"assertion expired", an "OIDC token" error, or any auth error
that surfaces AFTER the smoke's hard success criteria already
succeeded:

1. Grep the transcript for the first occurrence of the marker
   token `SMOKE_RESULT=`. If it appears AFTER the documented
   skill contract has succeeded (deploy ok, invoke ok, etc.) →
   Pattern 25 violation in the fixture.
2. Confirm by checking wall-clock: if total > 12 min and the
   skill contract is single-deploy + single-invoke, the leg is
   spending ≥7 min on teardown/cleanup.
3. Fix at the fixture, not the workflow: rewrite the marker
   contract to soft-PASS on teardown failure. Do NOT add OIDC
   token tokens to the retry classifier (Pattern 19) — a retry
   would just re-fail at teardown again, wasting another full
   leg's budget.

**Cost / benefit.** Pattern 25 adds zero CI cost on the green
path (NOTE is one stdout line). On the orphan-cleanup path,
the janitor cron is shared infra (~$0.02/day across all skills,
not per-leg). Removed cost: the entire class of "skill works
but cleanup is preview-unstable" false-FAILs. HA leg's flap
rate (1/2 stability runs failing on teardown) drops to 0/N
once the fixture rewrite lands.

**Cross-fixture audit (post-rollout).** After Pattern 25
proves stable on HA, audit other fixtures that create
side-resources:

- `azd-patterns` — creates an ACA Job + Bicep deployment;
  teardown is `az containerapp job delete` + `az group
  deployment delete`. Different shape, may or may not have
  the same OIDC vulnerability — defer audit until HA proven.
- `foundry-evals` — creates an evaluation + dataset on
  Foundry; teardown via SDK. Short-lived, likely safe.
- `foundry-memory` — creates a memory store + entries;
  teardown via SDK. Short-lived, likely safe.
- `foundry-toolbox` — registers in-process tools, no
  external resources to clean. Not applicable.
- `foundry-prompt-agents` — creates a prompt agent; teardown
  via SDK. Short-lived, likely safe.

Don't preemptively soft-PASS-teardown the safe ones — only
apply Pattern 25 when a fixture has demonstrated a real flap
attributable to teardown.

#### Pattern 27 — Forbid recursive `copilot` invocations from fixture Bash tools (Finding #28)

**Provenance.** Run [`27298061079`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/27298061079)
(SHA `01a5bdd`, PR #240) `foundry-cost-monitoring` leg job
[`80636049506`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/27298061079/job/80636049506).
The leg failed with a compound symptom that defeated Pattern 19's
retry classifier:

1. **Real CAPI 429** on the initial agent run: token usage from the
   transcript was `↑ 666.3k (634.4k cached) • ↓ 5.9k` in 1m50s,
   blowing through our 545K TPM cap. CLI internal retried 5 times
   ("Failed to get response from the AI model"), then surfaced the
   429.
2. **Agent freelanced into recursive `copilot`.** Reading the fixture's
   permissive intro ("Do whatever the skill tells you"), the agent
   went into meta-mode: ran a Bash tool that re-invoked `copilot`
   with `2>&1 | tee /tmp/foundry-cost-monitoring-transcript.log` —
   treating itself as the test harness. The nested `copilot` had no
   `COPILOT_GITHUB_TOKEN` (the workflow only sets the Azure
   provider bearer token, not GitHub auth), so it crashed with
   `Error: No authentication information found.`.
3. **Transcript clobber.** The nested `copilot`'s 8-line "No
   authentication" stub OVERWROTE the workflow's transcript at
   `/tmp/foundry-cost-monitoring-transcript.log`. The outer `tee`
   chain had completed before the nested call wrote.
4. **Pattern 19 retry defeated.** The retry step re-greps `$TRANSCRIPT`
   for the transient classifier. The clobbered 8-line stub contained
   neither `CAPIError` nor `Too Many Requests` nor `Failed to get
   response from the AI model` — so the classifier returned no match
   and the step exited "non-transient failure — not retrying".
5. **Audit-step false-negative.** The post-hoc audit step also greps
   the now-clobbered transcript for skill-usage evidence
   (`skill\\(${SKILL}\\)|SKILL.md|skills/${SKILL}/`). The stub has
   none, so it fires `::error::No evidence in transcript that agent
   loaded the '...' skill` — misleadingly suggesting a freelance
   failure when the agent DID load the skill but its transcript was
   wiped.

The combination is invisible to every existing CI gate: Pattern 12
marker file was never written (the agent crashed before reaching
its Step N marker), Pattern 19 retry didn't fire (transcript
clobbered), audit step misclassified (transcript clobbered).

**Fix (3 rules, all required).**

1. **Fixture intro MUST forbid recursive `copilot`.** Every
   Copilot-CLI fixture's preamble carries this verbatim block (or a
   skill-specific variant), placed AFTER the "execution smoke, not
   catalog inspection" guard from the earlier hardening:

   ```markdown
   **CRITICAL — never invoke `copilot` recursively from a Bash tool.**
   You ARE the running Copilot CLI process. Do NOT run
   `copilot -p ...`, `copilot --version`, `npm install -g @github/copilot`,
   or any other `copilot ...` invocation from inside a Bash tool call.
   Doing so spawns a nested CLI process WITHOUT GitHub auth (the workflow
   only sets `COPILOT_PROVIDER_BEARER_TOKEN` for our Foundry routing,
   NOT `COPILOT_GITHUB_TOKEN`), which will (a) crash with "No
   authentication information found" and (b) overwrite this run's
   transcript at `/tmp/<skill>-transcript.log`, defeating the workflow's
   retry classifier (Pattern 19 addendum). The workflow ALREADY captures
   your output via the outer `tee` — your job is to EXECUTE Steps
   directly in Bash tool calls, not to "run the smoke".
   ```

   The combination of "execution smoke, not catalog inspection"
   (forbids freelance into repo introspection) + "no recursive
   copilot" (forbids freelance into self-execution) is the canonical
   anti-freelance pair. Both are required; either alone is bypassable.

2. **Don't conflate the two failure modes in retry classifier.** The
   workflow's regex still correctly matches CAPI 429 surfaces. The
   recursive-copilot clobber is a SEPARATE root cause that the
   fixture-side guard must prevent. Adding "No authentication
   information found" to the retry classifier is WRONG — it would
   cause real auth bugs to silently retry forever instead of failing
   fast. The cure is fixture-side prohibition, not workflow-side
   regex broadening.

3. **Documentation in audit-step error.** The post-hoc audit message
   should mention recursive-copilot as a possible cause:

   ```bash
   echo "::error::No evidence in transcript that agent loaded the '${SKILL}' skill — \
   agent may have freelanced from training data, OR the transcript was clobbered \
   by a recursive 'copilot' invocation in a Bash tool (AGENTS.md § 9.7 Pattern 27)."
   ```

   This makes the failure mode obvious to the next coordinator
   without requiring a forensic deep-dive.

**Cross-skill carry rule.** Every existing Copilot-CLI fixture MUST
have the anti-recursive-copilot block before any future PR lands.
The rollout pattern matches the existing "execution smoke" hardening:
inject the block at fixture commit time when each fixture is next
touched, plus a one-shot sweep PR to retrofit any fixtures that
haven't been touched recently. Verify with:

```bash
for f in skills/*/test-fixture/consumer_prompt.md; do
  grep -q "never invoke \`copilot\` recursively" "$f" || echo "MISSING: $f"
done
```

**Diagnostic protocol.** When a fixture leg fails with the
audit-step error `No evidence in transcript that agent loaded the
'<skill>' skill`:

1. Download the transcript artifact.
2. Check its size: if < 1 KB, the transcript was likely clobbered.
3. Check for "No authentication information found" or "COPILOT_GITHUB_TOKEN"
   in the tail. If present → recursive-copilot clobber (Pattern 27).
4. Check the run log (not the artifact) for `CAPIError` /
   `Failed to get response from the AI model` BEFORE the agent's
   freelance recursion fired. If present → underlying root cause
   was TPM saturation (Pattern 19 addendum) and the recursive
   call masked it.
5. Fix at the fixture per Rule 1 above. Bump the SKILL.md PATCH
   version (the fixture is a SKILL.md asset).

**Cost / benefit.** Pattern 27 costs ~20 lines per fixture
preamble. Removed cost: the entire class of "TPM-throttle + agent
freelance into recursive copilot" failures that look like freelance
bugs but are actually TPM with a transcript-clobber masker. The
cost-monitoring leg in run `27298061079` is the proof point — it
should have been a clean Pattern 19 retry but instead burned a
full leg, a full audit-step false positive, and several minutes of
coordinator triage time.

#### Pattern 26 — Two-tier retry contract for BYOK Azure-routed CLI (Finding #27)

**Provenance.** Run [`27296618970`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/27296618970)
(SHA `f39759a`, PR #240 `foundry-cost-monitoring` + dep-fanout
`foundry-observability`). Both legs hit `CAPIError: 429 Too Many
Requests` on the initial run. Pattern 19's single retry leg
(90-180s cooldown) recovered `foundry-cost-monitoring` on the
manual rerun, but the in-line retry still failed because the deep
TPM saturation hadn't cleared in the original cooldown window. The
underlying issue (now documented in Patterns 19/22 addenda) is that
our CI routes the Copilot CLI through our own `gpt-5.4-mini`
deployment in `aif-awesome-gbb-ci` (Sweden Central, 545K TPM cap
shared with 455K of other Sweden Central tenant allocations) —
NOT a separate GitHub-side quota.

Per-request token math (measured from real run):
- ~226K input tokens per agent message (~210K cached + ~16K new)
- Cached tokens count at FULL rate for TPM rate-limiting
- 5-10 tool-call rounds per fixture → 1.1-2.2M tokens attempted
  per fixture invocation
- 545K TPM ceiling × 60s window → trivially saturated by a single
  heavy fixture, never mind 2+ in parallel

**The fix.** Add a SECOND retry step in `skill-test.yml` with a
longer cooldown (240-360s = 4-6 min). Two-tier escalation:

| Layer | Cooldown | Purpose |
|---|---|---|
| Main `run` | n/a | Initial attempt |
| `retry1` (Pattern 19) | 90-180s | Short-window throttle (RPM windows, mild TPM blip) |
| `retry2` (Pattern 26) | 240-360s | Deep TPM saturation (cleared only after the heavy 60s window fully rolls past) |

Both retry legs gate on the SAME transient classifier regex (so
genuine fixture bugs still fail fast). Same Pattern 12 marker
contract (deterministic `cmp -s`). Same Pattern 11 byte-identical
env block (so OIDC vars survive into the retry subshells). The
second retry only fires if the first retry ALSO matched the
transient classifier — preventing useless double-retries on
non-transient failures.

**Worked YAML** (paste-ready, anchored on Pattern 12/19/21/24
conventions):

```yaml
- name: Retry twice on classified-transient failure (Pattern 26)
  id: retry2
  if: steps.retry1.outcome == 'failure'
  env:
    # Mirror retry1's env exactly (Pattern 11 byte-identical contract).
    # Don't refactor into job-level env — Pattern 11 mandates per-step env.
    ... (copy from retry1)
  run: |
    set -euo pipefail
    SKILL="${{ matrix.skill }}"
    RETRY1_TRANSCRIPT="/tmp/${SKILL}-retry.log"
    RETRY2_TRANSCRIPT="/tmp/${SKILL}-retry2.log"
    MARKER="/tmp/${SKILL}-smoke-result"
    # Pattern 26 cooldown: 4-6 min so deep TPM saturation can clear.
    if grep -qE "429|503|throttl|capacity|EOF during azd deploy|revision .* not found|ManagedEnvironmentNotFound|ResourceNotFound.*Microsoft\.App|CAPIError|Too Many Requests|Failed to get response from the AI model|transient API error" "$RETRY1_TRANSCRIPT"; then
      COOLDOWN=$((240 + RANDOM % 120))
      sleep "${COOLDOWN}"
      rm -f "$RETRY2_TRANSCRIPT" "$MARKER"
      PREAMBLE=".github/ci-shared-preamble.md"
      set +e
      copilot -p "$(cat "$PREAMBLE" "skills/${SKILL}/test-fixture/consumer_prompt.md")" \
              --allow-all-tools --disable-builtin-mcps \
              -C "$GITHUB_WORKSPACE" 2>&1 | tee "$RETRY2_TRANSCRIPT"
      set -e
      # Marker file evaluation (FAIL-first, byte-exact PASS) — same as retry1.
      if [ -f "$MARKER" ]; then
        grep -qE "^SMOKE_RESULT=FAIL" "$MARKER" && { cat "$MARKER"; exit 1; }
        cmp -s "$MARKER" <(printf 'SMOKE_RESULT=PASS\n') && exit 0
      fi
      exit 1
    else
      exit 1
    fi
```

**Cross-skill carry rule.** The retry-2 leg is workflow-side and
applies to every Copilot-CLI fixture automatically — no per-fixture
change needed. The retry classifier regex is the union of all
known transients (Patterns 18 + 19); extending it adds new
recoverable failure modes without changing fixture code.

**Diagnostic protocol.** If a fixture FAILs with
`CAPIError 429 Too Many Requests` after the second retry leg:

1. Check current TPM cap on `aif-awesome-gbb-ci/gpt-5.4-mini`:
   `az cognitiveservices account deployment list -g
   rg-awesome-gbb-ci -n aif-awesome-gbb-ci
   --query "[?name=='gpt-5.4-mini'].sku.capacity" -o tsv`
2. Check Sweden Central regional headroom:
   `az cognitiveservices usage list -l swedencentral
   --query "[?contains(name.value, 'gpt-5.4-mini')].{name:name.value,
   used:currentValue, limit:limit}" -o table`
3. If regional ceiling hit (e.g. 1000K already allocated), deploy
   `gpt-5.4-mini` in a second region (eastus2 typically has 1000K
   free) and rotate `AZURE_AI_ENDPOINT` between regions OR shrink
   the fixture's prompt size.

**Cost / benefit.** Pattern 26 adds ~5 min per retry leg when it
fires (cooldown + retry execution). When it succeeds, it saves
the entire matrix leg's worth of human triage on a known-transient
failure (otherwise the PR author would manually rerun, wait,
rerun, etc.). Across the 14-leg matrix, even one retry-2 success
per week is net positive on coordinator time.

### 9.8 · Skill testing tiers

| Tier | Name | What | When required | Enforced by |
|------|------|------|---------------|-------------|
| **T0** | Lint | Frontmatter, desc ≤ 1024, forbidden strings, deprecated API scan | Every PR | `skill-validation.yml` |
| **T1** | Pin validation | `validation.script` runs, expected_output present | Pin file changes | `pin-validation.yml` |
| **T2** | Import smoke | `pip install` + `python -c "from X import Y"` for the changed pin | Pin file changes (PR-gated) | `pin-validation.yml` |
| **T3** | E2E Azure | A Copilot CLI agent runs the skill's fixture against real Azure resources (deploys, API calls, model inference) | Every PR + push to main + weekly cron | `skill-test.yml` (`copilot-cli-matrix` job) |

**T3 is CI-automated** for skills with a Copilot-CLI fixture at
`skills/<name>/test-fixture/consumer_prompt.md` registered in
`.github/skill-deps.yml`. The CI runner has OIDC credentials and real
Azure infrastructure (§ 9.7). New skills that connect to Azure MUST
add a fixture (§ 2.8). (Legacy pytest-based E2E under
`scripts/tests/test_e2e_*.py` was retired; see the header comment on
`.github/workflows/skill-test.yml`.)

**Excluded from CI** (multi-resource greenfield deploys; pin runs human-only):
`citadel-hub-deploy`, `foundry-vnet-deploy`. Both are
`automation_tier: issue_only` + `validation.runnable: false`.

The `--include-azure` flag on `run-pin-validation.py` unlocks T3 pins
(`automation_tier: auto` + `validation.runnable: false` +
`azure_subscription`/`foundry_project` in `validation.requires`) when the
runner has Azure credentials via env vars.

---

## 10 · Single plugin (`plugin.json` + marketplace.json)

The catalog ships a **single Copilot CLI plugin** (`awesome-gbb`) that
auto-discovers all skills under `skills/`. Install:

```bash
copilot plugin marketplace add aiappsgbb/awesome-gbb
copilot plugin install awesome-gbb@awesome-gbb
```

### 10.1 Why a single plugin

The catalog previously shipped three plugins (`awesome-gbb-basic`,
`awesome-gbb-azure`, `awesome-gbb-threadlight`) that physically copied
skills into each plugin directory — 17 duplicated skill trees, 336 files,
3.8 MB of waste. The Copilot CLI installs plugins by copying the plugin
directory to `~/.copilot/installed-plugins/`; relative `..` path-escape
doesn't work at install time, and symlinks break under `cp -R`. The only
zero-duplication solution is a single `plugin.json` at the repo root with
`"skills": "skills/"` — the repo IS the plugin.

Skills are still installable à la carte via
`gh skill install aiappsgbb/awesome-gbb <skill>`. The plugin is the
**one-command** alternative. Plugins also work in the
[Copilot Desktop App (preview)](https://github.com/github/app),
[VS Code Copilot Chat agent mode (preview)](https://code.visualstudio.com/docs/copilot/chat/chat-agent-mode),
and [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins)
via the same cross-runtime
[plugin spec](https://docs.github.com/en/copilot/reference/cli-plugin-reference).

### 10.2 Source-of-truth model

- `skills/<name>/` is the **source of truth** for every skill. Edit here.
- `plugin.json` at the repo root declares `"skills": "skills/"` — the CLI
  scans for subdirectories containing `SKILL.md`.
- `.github/plugin/marketplace.json` has one entry with `"source": "."`.
- `scripts/build-plugins.py --check` validates structural integrity (no
  `plugins/` directory needed, no copy step).
- CI gate `.github/workflows/skill-validation.yml` runs
  `python scripts/build-plugins.py --check` and fails on structural issues.

### 10.3 Adding a new skill

1. Author `skills/<name>/SKILL.md` following § 2.4 frontmatter shape
2. **Pin file (wrapper skills):** copy
   `scripts/templates/upstream-pin.template.md` to
   `skills/<name>/references/upstream-pin.md` and fill every placeholder
   (see § 9.5)
3. **Copilot-CLI fixture (skills that touch Azure):** author
   `skills/<name>/test-fixture/consumer_prompt.md` (a paste-ready prompt
   the CI agent will follow) and register the skill in
   `.github/skill-deps.yml`. The `copilot-cli-matrix` job in
   `skill-test.yml` auto-enrolls the skill on the next PR. Skills that
   only wrap PyPI packages without Azure calls may skip this, but the
   bar is: **if the skill tells consumers to connect to Azure, CI must
   prove that connection works.** See existing
   `skills/*/test-fixture/consumer_prompt.md` files (e.g.
   `foundry-prompt-agents`, `foundry-hosted-agents`, `azd-patterns`)
   for the canonical patterns. (Legacy `scripts/tests/test_e2e_*.py`
   was retired — see header on `.github/workflows/skill-test.yml`.)
4. **Cross-skill refs:** add `DO NOT USE FOR` entries in related skills
   (e.g., if your skill covers voice, add a cross-ref in
   `foundry-doc-vision-speech`). Bump those skills' version PATCH.
5. Add the skill to `CATEGORIES` in `scripts/build-site.py`
6. Verify with `python scripts/validate-skills.py`
7. **Adversarial review (wrapper skills):** diff SKILL.md against every
   upstream source file. Check config field names, function signatures,
   dependency lists, default values, and environment variables match the
   actual code. This catches bugs that CI cannot — wrong field names,
   incomplete catalogs, missing dependencies. Do it before opening the PR.
8. **🔴 TEST LIVE ON AZURE (§ 2.9).** If the skill touches Azure, run
   the Copilot-CLI fixture (`copilot-cli-matrix`) or manually verify
   with real Azure API calls. This is not optional. Include evidence
   in the PR description.
9. Rebuild docs: `python3 scripts/build-site.py --out docs/`
10. Bump `plugin.json` version per § 5.1 (MINOR for an added skill)
11. Bump `marketplace.json` version to match
12. Update `AGENTS.md` § 12.5 skill counts
13. **Commit tags:** a new SKILL.md body requires `[skill-rewrite]` in a
    commit message. If cross-refs touch other skills, also add
    `[multi-skill]`. Both are required by `automation-pr-gate.yml`.
14. After merge, sync to user scope:
    `cp -R skills/<name>/ ~/.copilot/skills/<name>/`

### 10.4 Renaming a skill

Renaming a skill changes its SKILL.md `name` field — which is the
dedup key runtimes use. Bump `plugin.json` to MAJOR. Avoid unless
strictly necessary.

### 10.5 Migration from old 3-plugin model (v2.0.0)

Users who had the old plugins installed must uninstall and reinstall:

```bash
copilot plugin uninstall awesome-gbb-basic@awesome-gbb
copilot plugin uninstall awesome-gbb-azure@awesome-gbb
copilot plugin uninstall awesome-gbb-threadlight@awesome-gbb
copilot plugin install awesome-gbb@awesome-gbb
```

---

## 11 · See also

- [README.md](README.md) — public catalog and install instructions
- [DEMOS.md](DEMOS.md) — demo guide for Foundry walkthroughs
- [Threadlight skills](https://github.com/aiappsgbb/threadlight-skills) — end-to-end pilot pipeline (8 skills, separate repo)
- [Zava constellation](https://github.com/aiappsgbb/zava-constellation) — digital-clone workspace (3 skills, separate repo)
- Each `skills/<skill>/SKILL.md` — the canonical contract for that skill
- Each `skills/<skill>/README.md` (if present) — extended docs / changelog
- Each `skills/<skill>/references/upstream-pin.md` (wrapper skills) — machine-readable freshness contract
- [`plugin.json`](plugin.json) — single plugin manifest
- [`.github/plugin/marketplace.json`](.github/plugin/marketplace.json) — plugin marketplace index
- [`scripts/build-plugins.py`](scripts/build-plugins.py) — structural validator for the single-plugin model
- [`scripts/templates/upstream-pin.template.md`](scripts/templates/upstream-pin.template.md) — canonical pin template (schema v2)
- [`scripts/run-pin-validation.py`](scripts/run-pin-validation.py) — CI-side validation.script runner (the gate that proves tests ran)
- [`.github/copilot-setup-steps.md`](.github/copilot-setup-steps.md) — GHCP coding agent contract for autonomous refresh

---

## 12 · Repo design philosophy

This catalog is built on three principles. Every process, workflow, and
CI gate traces back to one of them.

### 12.1 Quality is the only differentiator

The catalog is shared publicly with peers and customers. A single stale
import path, a broken code sample, or a wrong SDK version destroys
credibility instantly. Consequences:

- **Every skill is a contract.** Code samples in SKILL.md are not
  suggestions — they are the exact code a consumer will copy. If it
  doesn't run, the skill is broken.
- **Testing tiers are mandatory.** § 9.8 defines T0–T3. PRs that skip
  the appropriate tier are rejected, no exceptions.
- **CI gates are real gates.** The six workflows in § 9.6 are not
  advisory — they block merge. If CI can't prove a change is safe, the
  change doesn't land.

### 12.2 Self-healing freshness

Upstream SDKs move fast. Manual tracking doesn't scale past 10 skills.
The freshness lifecycle (§ 9) is the answer:

```
Weekly cron → drift detection → consolidated issue (per skill, impact-classified)
  → @Copilot auto-assigned → coding agent opens PR → CI gates validate
  → human reviews → merge
```

The loop is **closed**: detection → action → validation → merge, with
human review as the quality gate, not the bottleneck. Key design choices:

- **Consolidated issues, not per-signal spam.** One issue per skill with
  all signals and an impact label. Reduces noise from ~50 issues to ~15.
- **Impact classification drives priority.** CRITICAL (MAJOR SDK bumps)
  surfaces above LOW (link rot). Reviewers triage by label.
- **The coding agent reads `copilot-setup-steps.md`.** That file is the
  agent's instruction set — it tells the agent what to touch, what NOT
  to touch, and how to validate. Keep it precise and current.
- **`automation-pr-gate.yml` constrains agent scope.** The agent can
  bump pin files and frontmatter. It CANNOT rewrite SKILL.md body
  without `[skill-rewrite]` tag. This prevents accidental prose damage.

### 12.3 Defense in depth — six CI gates, four testing tiers

No single gate catches everything. The catalog uses **six workflows**
(§ 9.6) and **four testing tiers** (§ 9.8) layered so that a regression
must slip through multiple independent checks to reach main.

```
PR opened
 ├─ skill-validation.yml      T0: lint (frontmatter, SemVer, forbidden strings)
 ├─ automation-pr-gate.yml    mass-edit invariants + unit tests
 ├─ pin-validation.yml        T1: re-runs validation.script for changed pins
 │                                 (pip install + import; asserts expected_output)
 └─ skill-test.yml            T3 on PR: copilot-cli-matrix runs live agent fixtures
                                       for every changed skill

Push to main / weekly cron
 └─ skill-test.yml            T3: copilot-cli-matrix runs ALL fixtured skills
                              (live Copilot CLI agent + real Azure resources
                              in <ci-resource-group>: deploys, API calls,
                              model inference)

Weekly cron (detection only)
 └─ skill-freshness.yml       drift detection → consolidated issue → @Copilot auto-PR

On Copilot PR check-suite success
 └─ auto-merge-copilot.yml    auto-approves + squash-merges when all gates green
```

**Current coverage (27 skills, 23 with upstream pins):**

| Category | Count | Coverage |
|----------|-------|----------|
| Auto-tier (`runnable: true`) | 23 pins | T0 + T1 + T2 in CI |
| Auto-tier (`runnable: false`, CI-validated) | 3 pins | T0 in CI; T1–T3 via `--include-azure` on PR/schedule |
| Issue-only (complex multi-resource deploy) | 3 pins | T0 in CI; manual validation only |
| Internal IP (no pin) | 4 skills | T0 only (manual validation) |
| Copilot-CLI fixtures | 17 skills | T3 in CI (`copilot-cli-matrix`, see `.github/skill-deps.yml`) |

The `--include-azure` flag on `run-pin-validation.py` unlocks
issue-only pins when the runner has Azure credentials. The infra is
provisioned (§ 9.7); individual pin scripts are being upgraded from
pip+import to actual Azure API calls incrementally.

### 12.4 The repo IS the product

This is not a docs-only repository. The repo is a **Copilot CLI plugin**
(§ 10) — `plugin.json` at the root, `skills/` auto-discovered. Consumers
install it with one command and every skill is immediately available in
their CLI, Desktop App, VS Code, or Claude Code session.

Consequences:

- **No build step.** Skills are self-contained markdown contracts.
  Runtime reads SKILL.md directly. There is nothing to compile.
- **No duplication.** One `plugin.json`, one `skills/` directory, one
  source of truth. The old 3-plugin model that duplicated 17 skill trees
  is gone (§ 10.1).
- **Docs site is pre-built.** `scripts/build-site.py` generates static
  HTML into `docs/`. GitHub Pages serves it — there is no server-side
  build. If you change a skill, rebuild docs before pushing.
- **Pin files are machine-readable.** `upstream-pin.md` frontmatter is
  YAML, consumed by CI scripts. The prose below is human audit trail.
  Both must stay in sync.

### 12.5 Catalog at a glance

| Metric | Value |
|--------|-------|
| Total skills | 33 |
| Skills with upstream pins | 29 |
| Auto-tier (CI can refresh autonomously) | 26 |
| Issue-only (human / complex deploy) | 3 |
| Internal IP (no upstream) | 4 |
| CI workflows | 6 |
| Unit tests | 119 (37 PR gate + 59 skill validation + 23 probe units) |
| Azure E2E resources | AI Services + ACR + CAE in `<ci-resource-group>` |
| Plugin installs | `copilot plugin install awesome-gbb@awesome-gbb` |

---

## 13 · License & code of conduct

This project is [MIT-licensed](LICENSE) and follows the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
By contributing, you agree both apply to your contribution.
