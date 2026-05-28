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
| **T2** | Import smoke | `python -c "from X import Y"` for every import in SKILL.md code samples | Pin refresh PRs (MINOR/MAJOR) | `skill-test.yml` (pin-smoke job) |
| **T3** | E2E Azure | Deploy a real agent/resource, call Azure APIs, verify real responses | New skills that touch Azure, code sample rewrites, breaking SDK changes | `skill-test.yml` (e2e-azure job) + human validation for excluded skills |

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
  infrastructure (§ 9.7). Add a pytest file under `scripts/tests/` and
  wire it into the `e2e-azure` job in `skill-test.yml`.

### 2.8 Skills that connect to Azure MUST have E2E tests

This is a hard rule, not a suggestion. If SKILL.md tells consumers to
call an Azure endpoint, provision a resource, or authenticate with
`DefaultAzureCredential`, the catalog MUST prove that path works:

- ✅ Add `scripts/tests/test_e2e_<name>.py` with pytest tests that
  exercise real Azure connectivity (credential chain, endpoint
  reachability, API surface existence)
- ✅ Wire the test into `skill-test.yml` → `e2e-azure` job
- ✅ Tests run with OIDC credentials against `rg-awesome-gbb-ci` (§ 9.7)
- ❌ **"pip install + import" is NOT sufficient** for Azure skills — it
  proves the SDK exists, not that the Azure connection works
- ❌ **"I tested locally" is NOT sufficient** — CI must reproduce it

**Exceptions** (too complex for CI, manually validated only):
`citadel-hub-deploy`, `citadel-spoke-onboarding`, `foundry-vnet-deploy`.
These require multi-resource deployments that exceed CI budget. Document
manual validation in the PR description.

**For skills that don't deploy but connect remotely** (e.g.,
`foundry-voice-live` connecting to Azure Voice Live WSS): prove the
credential chain and API surface work. You don't need to deploy
infrastructure, but you MUST prove the client can construct and
authenticate.

See `test_e2e_prompt_agents.py` and `test_e2e_voice_live.py` for
patterns.

---

## 3 · Editing checklist (run before every commit)

Mechanical checks. Most are now CI-enforced (§ 9.6), but running them
locally before push catches issues faster than waiting for CI.

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

Rule: if `validation.requires` includes anything beyond `github_only`
or `pypi`, `automation_tier` MUST be `issue_only`. Enforced by
[`scripts/validate-skills.py`](scripts/validate-skills.py).

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
| 🟠 HIGH | `impact:high` | Package MINOR bump, upstream KI closed |
| 🟡 MEDIUM | `impact:medium` | SHA drift, validation age > 180 days |
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
3. **Update audit trail**:
   - `last_validated: <today>`
   - `validated_by: <handle>` (or `copilot-bot`)
4. **Bump SKILL.md `metadata.version` PATCH** (X.Y.Z → X.Y.(Z+1)).
   Per § 5, pin refresh is PATCH — not MINOR.
5. **Open PR** touching ONLY `references/upstream-pin.md` and
   `SKILL.md` frontmatter. The
   [`automation-pr-gate.yml`](.github/workflows/automation-pr-gate.yml)
   workflow rejects anything else (unless the appropriate opt-in tag is
   in the commit message).

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

### 9.6 · Five CI gates that protect the catalog

| Gate | When | What it checks |
|------|------|---------------|
| [`skill-validation.yml`](.github/workflows/skill-validation.yml) | Every PR touching `skills/**`, `plugin.json`, or `.github/plugin/**` | Frontmatter parses, description ≤ 1024, valid SemVer, no forbidden strings, pin files conform to schema v2, **plugin.json + marketplace.json valid and version-consistent** |
| [`automation-pr-gate.yml`](.github/workflows/automation-pr-gate.yml) | Every PR touching `skills/**` | The § 4 mass-edit invariants — see that section |
| [`pin-validation.yml`](.github/workflows/pin-validation.yml) | Every PR touching `skills/*/references/upstream-pin.md` | **Re-runs `validation.script` on the runner** for auto-tier pin files; asserts every `expected_output` substring. No "trust me, I tested" path. |
| [`skill-freshness.yml`](.github/workflows/skill-freshness.yml) | Weekly cron + on-demand | Detection (no PR gating) — opens issues for drift |
| [`skill-test.yml`](.github/workflows/skill-test.yml) | Push to main + weekly cron + on-demand | **Comprehensive test suite**: unit tests, catalog lint, all-pin smoke test, and **E2E Azure tests** (deploys, API calls, model inference against real Azure resources in `rg-awesome-gbb-ci`) |

The first three run on every PR. The fourth detects drift autonomously.
The fifth runs on push to main and weekly, with E2E Azure tests on
schedule and manual dispatch.

### 9.7 · Azure CI credentials and E2E infrastructure

The repo has OIDC-federated Azure credentials and dedicated E2E
infrastructure for CI use in `rg-awesome-gbb-ci` (Sweden Central):

**OIDC identity:**

| Secret | Purpose |
|--------|---------|
| `AZURE_CLIENT_ID` | UAMI `uami-awesome-gbb-ci` in `rg-awesome-gbb-ci` |
| `AZURE_TENANT_ID` | `fruocco` tenant |
| `AZURE_SUBSCRIPTION_ID` | `ME-MngEnvMCAP979166-fruocco-2` |

**E2E infrastructure:**

| Resource | Name | Purpose |
|----------|------|---------|
| AI Services | `aif-awesome-gbb-ci` | Foundry host for agent/eval/memory tests |
| Model deployment | `gpt-5.4-mini` | Cheapest model for smoke tests |
| Container Registry | `acrawesomegbbci` | Container image builds |
| Container App Environment | `cae-awesome-gbb-ci` | ACA deploy tests |

**Endpoint secrets:**

| Secret | Value |
|--------|-------|
| `AZURE_AI_ENDPOINT` | `https://aif-awesome-gbb-ci.cognitiveservices.azure.com/` |
| `ACR_LOGIN_SERVER` | `acrawesomegbbci.azurecr.io` |

**RBAC on UAMI:**
- Contributor on `rg-awesome-gbb-ci`
- AcrPush on `acrawesomegbbci`
- Cognitive Services OpenAI User on `aif-awesome-gbb-ci`
- Foundry User on `aif-awesome-gbb-ci`

Federated credentials cover both `pull_request` and `ref:refs/heads/main`
triggers. Workflows use `azure/login@v2` with OIDC — no stored secrets
or service principal passwords.

### 9.8 · Skill testing tiers

| Tier | Name | What | When required | Enforced by |
|------|------|------|---------------|-------------|
| **T0** | Lint | Frontmatter, desc ≤ 1024, forbidden strings, deprecated API scan | Every PR | `skill-validation.yml` |
| **T1** | Pin validation | `validation.script` runs, expected_output present | Pin file changes | `pin-validation.yml` |
| **T2** | Import smoke | `pip install` + `python -c "from X import Y"` for all auto-tier pins | Weekly + dispatch | `skill-test.yml` (pin-smoke job) |
| **T3** | E2E Azure | Call Azure APIs, verify credential chains + API surfaces work against real resources | Weekly + dispatch + new Azure-touching skills | `skill-test.yml` (e2e-azure job) |

**T3 is CI-automated** for skills with E2E test files under
`scripts/tests/test_e2e_*.py`. The CI runner has OIDC credentials and
real Azure infrastructure (§ 9.7). New skills that connect to Azure
MUST add an E2E test (§ 2.8).

**Excluded from CI** (too complex, manually validated only):
`citadel-hub-deploy`, `citadel-spoke-onboarding`, `foundry-vnet-deploy`.

The `--include-azure` flag on `run-pin-validation.py` unlocks T3 pins
(those with `azure_subscription` or `foundry_project` in
`validation.requires`) when the runner has Azure credentials via env vars.

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
3. **E2E test (skills that touch Azure):** add a pytest file under
   `scripts/tests/test_e2e_<name>.py` that verifies real Azure
   connectivity (credential chain, endpoint reachability, API surface).
   Wire it into `skill-test.yml` → `e2e-azure` job. Skills that only
   wrap PyPI packages without Azure calls may skip this, but the bar is:
   **if the skill tells consumers to connect to Azure, CI must prove
   that connection works.** See `test_e2e_prompt_agents.py` and
   `test_e2e_voice_live.py` for patterns.
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
8. Rebuild docs: `python3 scripts/build-site.py --out docs/`
9. Bump `plugin.json` version per § 5.1 (MINOR for an added skill)
10. Bump `marketplace.json` version to match
11. Update `AGENTS.md` § 12.5 skill counts
12. **Commit tags:** a new SKILL.md body requires `[skill-rewrite]` in a
    commit message. If cross-refs touch other skills, also add
    `[multi-skill]`. Both are required by `automation-pr-gate.yml`.
13. After merge, sync to user scope:
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
- **CI gates are real gates.** The five workflows in § 9.6 are not
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

### 12.3 Defense in depth — five CI gates, four testing tiers

No single gate catches everything. The catalog uses **five workflows**
(§ 9.6) and **four testing tiers** (§ 9.8) layered so that a regression
must slip through multiple independent checks to reach main.

```
PR opened
 ├─ skill-validation.yml      T0: lint (frontmatter, SemVer, forbidden strings)
 ├─ automation-pr-gate.yml    mass-edit invariants + unit tests
 └─ pin-validation.yml        T1: re-runs validation.script for changed pins
                                   (pip install + import; asserts expected_output)

Push to main / weekly cron
 ├─ skill-test.yml            T2: all-pin smoke (pip install + import for ALL auto-tier pins)
 └─ skill-test.yml            T3: E2E Azure (credential chains, API surfaces, model
                                   inference against real resources in rg-awesome-gbb-ci)

Weekly cron (detection only)
 └─ skill-freshness.yml       drift detection → consolidated issue → @Copilot auto-PR
```

**Current coverage (27 skills, 23 with upstream pins):**

| Category | Count | Coverage |
|----------|-------|----------|
| Auto-tier (`runnable: true`) | 18 pins | T0 + T1 + T2 in CI |
| Issue-only (Azure-dependent) | 7 pins | T0 in CI; T1–T3 via `--include-azure` on dispatch |
| Internal IP (no pin) | 4 skills | T0 only (manual validation) |
| E2E Azure tests | 2 skills | T3 in CI (`foundry-prompt-agents`, `foundry-voice-live`) |

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
| Total skills | 27 |
| Skills with upstream pins | 23 |
| Auto-tier (CI can refresh autonomously) | 18 |
| Issue-only (human / Azure creds needed) | 7 |
| Internal IP (no upstream) | 4 |
| CI workflows | 5 |
| Unit tests | 63 (18 PR gate + 38 skill validation + 7 E2E Azure) |
| Azure E2E resources | AI Services + ACR + CAE in `rg-awesome-gbb-ci` |
| Plugin installs | `copilot plugin install awesome-gbb@awesome-gbb` |

---

## 13 · License & code of conduct

This project is [MIT-licensed](LICENSE) and follows the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
By contributing, you agree both apply to your contribution.
