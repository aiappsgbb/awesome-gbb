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
├── THREADLIGHT.md            # End-to-end pipeline + customer-workshop runbook
├── AGENTS.md                 # ← you are here
└── skills/
    └── <skill-name>/
        ├── SKILL.md          # Skill definition (frontmatter + instructions)
        ├── README.md         # Optional extended docs
        ├── references/       # Optional: scaffolds, templates, canon data
        │   └── …             # SemVer-stable; consumed by the SKILL at runtime
        └── templates/        # Optional: copy-paste templates (Bicep, Dockerfile, …)
```

There is **no monorepo build step**. Each skill is a self-contained markdown
contract. The runtime (Copilot CLI, Cursor, Cowork, Clawpilot, etc.) loads
`SKILL.md` and follows its instructions.

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

### 2.5 Threadlight skills reinforce each other — don't break the chain

Skills under `threadlight-*` (and `foundry-*` consumed by them) form a
**pipeline** documented in [THREADLIGHT.md](THREADLIGHT.md):

```
threadlight-design → threadlight-local-test → threadlight-deploy →
threadlight-safe-check (gate) → foundry-evals + foundry-observability
```

Cross-skill contracts to preserve:
- `threadlight-design` writes SPEC.md § 11c (kebab-case selectors); `threadlight-deploy`
  reads them; `threadlight-safe-check` re-validates them. **Selector vocabulary is
  the contract** — if you add a selector to one, add it to all three.
- `azd-patterns` owns the Bicep module library; `threadlight-deploy` Phase 6
  is the composer. **Don't fork the module shapes** in deploy — extend
  `azd-patterns`.
- `foundry-observability` owns the 3-layer telemetry pattern (Bicep → AppIn
  account connection → `configure_azure_monitor()`). **Every** ACA workload
  in every other skill must pass through this — don't write parallel
  telemetry init.

If your edit changes a contract, update **all** consumers in the same PR.

---

## 3 · Editing checklist (run before every commit)

Mechanical checks. None of these are CI-enforced yet (see § 8).

- [ ] **YAML parses** — `python -c "import yaml,pathlib; [yaml.safe_load(p.read_text().split('---')[1]) for p in pathlib.Path('skills').rglob('SKILL.md')]"`
- [ ] **Description ≤ 1024 chars** on every touched SKILL.md
- [ ] **No customer / PoC / private-repo names** introduced (grep your diff
      for likely offenders)
- [ ] **No real GUIDs or ARM IDs** introduced (grep for `subscriptions/[0-9a-f]{8}-`)
- [ ] **`metadata.version` present** on every SKILL.md you touched, and
      bumped per § 5 if the change is user-facing
- [ ] **Cross-skill links resolve** — if you renamed a section header, grep
      the rest of the repo for stale `#section-name` anchors
- [ ] **Sync to user scope mirror** if you test locally (see § 6)

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

There is no automation that enforces version bumps. If you forget, the next
contributor catches it in code review.

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

---

## 7 · References & shared data

### Canonical reference data lives in two skills

- **`threadlight-design/references/data-realism/`** — industry shorthand
  for ID formats, units, currencies, regional norms (FSI, MFG, Retail,
  Telco). Used by the design skill to keep generated SPEC § 5 sample data
  realistic to the SME reviewer.
- **`threadlight-demo-data-factory/references/generators/`** — synthetic
  data generation patterns (per-domain seeds, Cosmos reset scripts).

Both are **canon** (see § 2.2). Edits require citing the original spec
(IRS publication, ISO standard, regulator URL).

### Bicep modules

Live in **`azd-patterns/`** (the composable module library). `threadlight-deploy`
Phase 6 is the only composer that includes them. Do not fork module shapes
in other skills — extend the library.

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

# 2. Forced-text diff inspection of every modified file
git --no-pager diff -a HEAD~1

# 3. Smell-check for forbidden strings
git --no-pager diff HEAD~1 | Select-String -Pattern "kyc-poc|card-dispute-investigation|threadlight-v[123]|ricchi"
```

There is no CI yet — these checks run on the contributor's machine. We
will add a GitHub Action when the catalog stabilizes; until then,
discipline is the gate.

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

Each drift event opens its own GitHub issue (`label: freshness,automation`).
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

### 9.6 · Three CI gates that protect the catalog

| Gate | When | What it checks |
|------|------|---------------|
| [`skill-validation.yml`](.github/workflows/skill-validation.yml) | Every PR touching `skills/**` | Frontmatter parses, description ≤ 1024, valid SemVer, no forbidden strings, pin files conform to schema v2 |
| [`automation-pr-gate.yml`](.github/workflows/automation-pr-gate.yml) | Every PR touching `skills/**` | The § 4 mass-edit invariants — see that section |
| [`skill-freshness.yml`](.github/workflows/skill-freshness.yml) | Weekly cron + on-demand | Detection (no PR gating) — opens issues for drift |

The first two run on every PR. The third runs autonomously.

---

## 10 · See also

- [README.md](README.md) — public catalog and install instructions
- [THREADLIGHT.md](THREADLIGHT.md) — end-to-end pipeline narrative
- Each `skills/<skill>/SKILL.md` — the canonical contract for that skill
- Each `skills/<skill>/README.md` (if present) — extended docs / changelog
- Each `skills/<skill>/references/upstream-pin.md` (wrapper skills) — machine-readable freshness contract
- [`scripts/templates/upstream-pin.template.md`](scripts/templates/upstream-pin.template.md) — canonical pin template (schema v2)
- [`.github/copilot-setup-steps.md`](.github/copilot-setup-steps.md) — GHCP coding agent contract for autonomous refresh

---

## 11 · License & code of conduct

This project is [MIT-licensed](LICENSE) and follows the
[Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
By contributing, you agree both apply to your contribution.
