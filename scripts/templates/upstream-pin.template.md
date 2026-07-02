<!--
  ╔═══════════════════════════════════════════════════════════════════════╗
  ║  CANONICAL UPSTREAM-PIN TEMPLATE — schema_version: 2                   ║
  ║                                                                       ║
  ║  ⚠️  DELETE THIS ENTIRE HTML COMMENT BLOCK after copying.              ║
  ║      The pin file MUST start with `---` on line 1 — the YAML          ║
  ║      front-matter is the machine-readable contract that powers the   ║
  ║      weekly freshness detector. `scripts/validate-skills.py` will    ║
  ║      reject any pin file that does not start with `---`.              ║
  ║                                                                       ║
  ║  Copy this file to:                                                   ║
  ║    skills/<skill-name>/references/upstream-pin.md                     ║
  ║                                                                       ║
  ║  Fill every <placeholder>. Remove sections marked OPTIONAL if they    ║
  ║  don't apply. Keep the YAML front-matter (between `---` markers)      ║
  ║  parseable — see AGENTS.md § 9 for the full lifecycle convention.     ║
  ║                                                                       ║
  ║  YAML gotcha: any value containing `:` MUST be quoted as a string.    ║
  ║  Examples that bite agents:                                           ║
  ║    description: Use the header `X-Foo: Bar`   ← UNQUOTED, breaks       ║
  ║    description: "Use the header `X-Foo: Bar`" ← OK                    ║
  ╚═══════════════════════════════════════════════════════════════════════╝
-->
---
# ──────────── schema (do not edit on a per-skill basis) ────────────
schema_version: 2

# ──────────── freshness signal classification ──────────────────────
# A = SHA-pinned wrapper of a github repo
# B = SDK / preview-API wrapper (no git SHA, version-pinned only)
# C = internal IP (no upstream — use references/last_validated.yaml instead)
freshness_tier: A

# ──────────── automation policy ────────────────────────────────────
# auto        = drift opens issue assigned to @Copilot; coding agent runs
#               validation.script autonomously and opens a PR
# issue_only  = drift opens unassigned issue; human authors the refresh
#               (use this when validation.requires includes azure_subscription
#               or foundry_project — we don't ship credentials to GHCP)
automation_tier: auto

# ──────────── upstream identity ────────────────────────────────────
upstream:
  type: github_repo            # github_repo | pypi | docs_only
  repo: <org>/<repo>           # e.g. microsoft/agent-governance-toolkit
  ref: main                    # branch or tag
  pinned_sha: <40-char SHA>    # `git ls-remote https://github.com/<repo> <ref>` → first column
  pinned_commit_message: |
    <commit subject line at the pinned SHA, for human review of weekly diffs>
  license: MIT                 # MIT | Apache-2.0 | proprietary
  notes: |
    <optional — fork relationship, vendoring decision, etc.>

# ──────────── pinned packages (Tier B mostly) ──────────────────────
# OPTIONAL for Tier-A skills that don't pin specific PyPI versions.
# REQUIRED for Tier-B skills.
packages:
  - name: <pypi-package-name>
    source: pypi
    version: "<X.Y.Z>"
    upstream_changelog: https://github.com/<repo>/releases
    # OPTIONAL — KI-backed major-version hold. Use when a skill must stay below
    # a known-breaking major until a documented gotcha is revalidated. While the
    # referenced known_issue is `status: open`, the freshness detector suppresses
    # drift signals for releases that reach/cross `hold_below`, so the weekly
    # auto-refresh cannot re-bump past the ceiling. The hold releases
    # automatically when the KI is closed. Fail-open: if hold_reason names no
    # OPEN known_issue, the hold is ignored and drift fires normally.
    # hold_below: "<next-major>.0.0"   # e.g. "3.0.0" to hold below 3.x
    # hold_reason: KI-00N              # id of the OPEN known_issue below
    notes: |
      <optional — preview status, version-skew quirks, etc.>

# ──────────── documentation URLs (link-rot detector input) ─────────
# Every public URL the skill body relies on. The detector runs
# `curl --head` against each one weekly; 4xx/5xx opens an issue.
docs_to_revalidate:
  - https://learn.microsoft.com/<docs-path>
  - https://github.com/<repo>/blob/main/<doc>.md
  - https://pypi.org/project/<package>/

# ──────────── known issues at this pin ─────────────────────────────
# For each documented workaround / gotcha, link to the upstream tracker
# (issue / PR / discussion). The detector polls upstream status weekly;
# when an upstream issue is closed, it flags this skill for re-validation
# without the workaround.
known_issues:
  - id: KI-001
    description: <one-line summary of the workaround>
    upstream_url: https://github.com/<repo>/issues/<n>
    status: open              # open | closed_upstream_needs_revalidation | closed_upstream_fixed
    workaround_location: SKILL.md § "Known Issues" item N

# ──────────── machine-runnable validation contract ─────────────────
# This is the SPEC the GHCP coding agent executes when refreshing this
# pin. Make it copy-paste runnable, idempotent, and deterministic.
validation:
  # What credentials/runtime the script needs:
  #   github_only           — git + curl, no auth
  #   pypi                  — pip install from public PyPI, no auth
  #   azure_subscription    — `az` CLI with a logged-in tenant
  #   foundry_project       — live Foundry project + agent runtime
  #
  # Tier matrix (enforced by scripts/validate-skills.py):
  #   safe only + runnable=true                      → runs in every CI run
  #   {az_sub|foundry} + auto + runnable=false       → runs only with --include-azure
  #   {az_sub|foundry} + issue_only + runnable=false → human-only refresh
  #   {az_sub|foundry} + runnable=true               → REJECTED (agent can't run it)
  requires:
    - github_only
    - pypi

  # Whether validation.script can run without human intervention.
  # Set false for any pin that needs Azure/Foundry creds — CI will execute
  # it via `run-pin-validation.py --include-azure` when automation_tier=auto.
  runnable: true

  # Copy-paste shell — what the coding agent executes.
  # Substitute ${PINNED_VERSION} / ${PINNED_SHA} at runtime; the detector
  # passes the candidate new value as the env var.
  #
  # 🔒 Pin/cap policy: ALL pip installs MUST use a bounded specifier.
  # Use PEP 440 compatible-release (`~=X.Y.Z` ≡ `>=X.Y.Z,<X.(Y+1).0`)
  # for stable releases. For pre-releases (a/b/rc/dev), use exact `==`
  # because pre-release semantics don't survive cap math.
  # NEVER use bare `>=` or unpinned package names — the freshness
  # contract assumes every install is reproducible within a cap window.
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    # Example for a Tier-B PyPI wrapper:
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "<package>~=${PINNED_VERSION}"
    python -c "import <module>; print(<module>.__version__)"
    # ... skill-specific smoke commands ...

  # Substrings that must appear in the script's stdout for validation
  # to be considered successful. The coding agent grep's these out.
  expected_output:
    - "<exact substring proving the smoke passed>"

  # OPTIONAL: an explicit non-success signal (e.g. an error message that
  # means "upstream broke something"). Detector reports this distinctly.
  failure_signatures: []

# ──────────── re-pin audit trail ───────────────────────────────────
last_validated: <YYYY-MM-DD>   # date of the most recent successful validation
validated_by: <handle>         # human handle OR `copilot-bot`
known_issues_count: 0          # count of known_issues[] with status: open
---

# Upstream pin — `<skill-name>` skill

This file is the **machine-readable validation contract** for the
`<skill-name>` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human
audit trail. Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `<org>/<repo>` |
| **Branch / tag** | `<ref>` |
| **Pinned SHA** | `<40-char SHA>` |
| **Pinned commit subject** | `<subject>` |
| **License** | `<MIT \| Apache-2.0 \| …>` |
| **First authored against** | `<YYYY-MM-DD>` |
| **Last re-validated** | `<YYYY-MM-DD>` |

Refresh procedure:
```bash
git ls-remote https://github.com/<org>/<repo> <ref>
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

OPTIONAL — remove this section for pure Tier-A wrappers that don't
pin PyPI versions.

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `<package>` | PyPI | **<X.Y.Z>** | <notes> |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them
> identical. The agent will run this script verbatim.

```bash
<copy of validation.script, with placeholders expanded as inline
comments showing the substitution>
```

**Expected output** must contain (substring match):

- `<expected_output[0]>`
- `<expected_output[1]>`

**Failure signatures** (treat as upstream regression — report distinctly):

- `<failure_signatures[0]>` (if any)

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `<command 1>` | ✅ | `<output line proving success>` |
| `<command 2>` | ✅ | `<output line>` |

Captured at `last_validated: <YYYY-MM-DD>` by `<validated_by>`.

---

## 5. Known issues at this pin

For each `known_issues[]` entry in the front-matter, document the
workaround prose here. When upstream closes the linked issue, the
detector will open a refresh issue asking the coding agent to re-run
validation WITHOUT the workaround.

### KI-001 — `<one-line summary>`

**Upstream tracker:** <https://github.com/<repo>/issues/<n>>
**Status:** open

`<prose explanation of the symptom>`

**Workaround:**

```<lang>
<workaround code or config>
```

**When upstream fixes this**: re-run `validation.script` after removing
the workaround. If green, update the front-matter:
```yaml
known_issues:
  - id: KI-001
    status: closed_upstream_fixed
```
and remove the workaround from `SKILL.md`.

---

## 6. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/<org>/<repo> <ref>
   ```
2. **Update front-matter**: set `upstream.pinned_sha` to the new value
   and `upstream.pinned_commit_message` to the new commit subject.
3. **Run the validation script**:
   ```bash
   PINNED_SHA=<new-sha> bash -c "$(yq '.validation.script' upstream-pin.md)"
   # (or copy the script from § 3 above)
   ```
4. **Verify expected output**: each `expected_output[]` substring must
   appear in the script's stdout.
5. **Update audit trail**:
   - `last_validated: <today>`
   - `validated_by: <handle>`
   - increment any KI counts if new issues were found
6. **Bump SKILL.md `metadata.version` PATCH** (e.g., `1.0.1` → `1.0.2`)
   per AGENTS.md § 5. NOT MINOR — pin refresh is not a new feature.
7. **Open PR**: title `chore(<skill>): re-pin upstream → <short-sha>`.
   Touch ONLY `references/upstream-pin.md` and `SKILL.md` frontmatter.
   The `automation-pr-gate.yml` workflow enforces this.

---

## 7. URLs to re-validate (link-rot detector input)

The detector runs `curl --head` against each URL weekly; 4xx/5xx
responses surface as a refresh issue.

- <https://github.com/<org>/<repo>>
- <https://github.com/<org>/<repo>/blob/main/<key-doc>.md>
- <https://pypi.org/project/<package>/>
- <https://learn.microsoft.com/<docs-path>>

---

## 8. Cross-references worth bookmarking

OPTIONAL — drop key upstream pointers here so the next refresh
remembers where the canon lives.

- `<upstream-path/README.md>` — <what it documents>
- `<upstream-path/CHANGELOG.md>` — release notes

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. The `validation.script` in the front-matter is your spec. Run it.
> 2. If it passes, update front-matter (`pinned_sha`, `last_validated`,
>    `validated_by: copilot-bot`) and bump SKILL.md `metadata.version`
>    PATCH. Touch nothing else.
> 3. If it fails, comment on the issue with the failure output and
>    **do NOT open a PR**.
> 4. For body changes to SKILL.md (e.g. removing a workaround note
>    after upstream fixes a bug), the issue body must explicitly
>    instruct you to include `[skill-rewrite]` in the commit message —
>    otherwise the `automation-pr-gate.yml` workflow will reject your PR.
> 5. NEVER edit `references/data-realism/**` — those are canon files
>    per AGENTS.md § 2.2 and the gate will reject any PR that touches
>    them without `[scrub-canon]` opt-in.
