---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: blader/humanizer
  ref: main
  pinned_sha: 523374dee72d67c7b2b5f858ea0094ffda49c3ac
  pinned_commit_message: |
    Add passive voice rule to humanizer (#80)
  license: MIT
  notes: |
    The skill body adapts the upstream humanizer prompt and pattern catalog. Validation checks the upstream prompt structure and reference URLs only.
packages: []
docs_to_revalidate:
  - https://github.com/blader/humanizer
  - https://github.com/blader/humanizer/blob/main/SKILL.md
  - https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
known_issues: []
validation:
  requires:
    - github_only
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    PINNED_SHA="${PINNED_SHA:-523374dee72d67c7b2b5f858ea0094ffda49c3ac}"
    REPO_URL="https://github.com/blader/humanizer"
    REF="main"
    WORK=".upstream-pin-smoke/gbb-humanizer"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
    actual="$(git -C "$WORK/repo" rev-parse HEAD)"
    test "$actual" = "$PINNED_SHA"
    echo "pinned SHA verified: ${PINNED_SHA}"

    test -f "$WORK/repo/SKILL.md"
    test -f "$WORK/repo/README.md"
    grep -q "PERSONALITY AND SOUL" "$WORK/repo/SKILL.md"
    grep -q "CONTENT PATTERNS" "$WORK/repo/SKILL.md"
    count="$(grep -Ec '^### [0-9]+\.' "$WORK/repo/SKILL.md")"
    test "$count" -ge 29
    echo "humanizer pattern catalog ok"

    curl -fsSI -L "$REPO_URL" >/dev/null
    curl -fsSI -L "https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing" >/dev/null
    echo "reference URL check ok"
  expected_output:
    - "pinned SHA verified"
    - "humanizer pattern catalog ok"
    - "reference URL check ok"
  failure_signatures: []
last_validated: 2026-07-23
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `gbb-humanizer` skill

This file is the **machine-readable validation contract** for the
`gbb-humanizer` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `blader/humanizer` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `a2ace14a88a6746f64f1f53ed8272d6788828038` |
| **Pinned commit subject** | `Add passive voice rule to humanizer (#80)` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-28` |

Refresh procedure:
```bash
git ls-remote https://github.com/blader/humanizer main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

No package is pinned for this Tier-A wrapper. Validation uses only upstream
GitHub source, `curl`, and shell checks.

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them identical. The
> agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="${PINNED_SHA:-9600f2b7241cb4eed6ad803abee5ea01d67fe8e4}"
REPO_URL="https://github.com/blader/humanizer"
REF="main"
WORK=".upstream-pin-smoke/gbb-humanizer"

rm -rf "$WORK"
mkdir -p "$WORK"
git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
actual="$(git -C "$WORK/repo" rev-parse HEAD)"
test "$actual" = "$PINNED_SHA"
echo "pinned SHA verified: ${PINNED_SHA}"

test -f "$WORK/repo/SKILL.md"
test -f "$WORK/repo/README.md"
grep -q "PERSONALITY AND SOUL" "$WORK/repo/SKILL.md"
grep -q "CONTENT PATTERNS" "$WORK/repo/SKILL.md"
count="$(grep -Ec '^### [0-9]+\.' "$WORK/repo/SKILL.md")"
test "$count" -ge 29
echo "humanizer pattern catalog ok"

curl -fsSI -L "$REPO_URL" >/dev/null
curl -fsSI -L "https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing" >/dev/null
echo "reference URL check ok"
```

**Expected output** must contain (substring match):

- `pinned SHA verified`
- `humanizer pattern catalog ok`
- `reference URL check ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Pinned GitHub branch | ✅ | `pinned SHA verified` |
| Pattern catalog shape | ✅ | `humanizer pattern catalog ok` |
| Reference URLs | ✅ | `reference URL check ok` |

Captured at `last_validated: 2026-05-15` by `ricchi`.

---

## 5. Known issues at this pin

No known issues are tracked for this pin.

---

## 6. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/blader/humanizer main
   ```
2. **Update front-matter** with the new SHA and commit subject.
3. **Run the validation script**:
   ```bash
   PINNED_SHA=<new-sha> bash -c "$(yq '.validation.script' upstream-pin.md)"
   ```
4. **Verify expected output** from § 3.
5. **Update audit trail**.
6. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
7. **Open PR** touching only this file and `SKILL.md`.

---

## 7. URLs to re-validate (link-rot detector input)

- <https://github.com/blader/humanizer>
- <https://github.com/blader/humanizer/blob/main/SKILL.md>
- <https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing>

---

## 8. Cross-references worth bookmarking

- `SKILL.md` — upstream prompt and pattern catalog.
- `README.md` — upstream usage notes.
- Wikipedia "Signs of AI writing" page — external reference cited by this skill.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. Run `validation.script`; it requires public GitHub and URL checks only.
> 2. If upstream adds, removes, or renumbers pattern headings, do **not** rewrite
>    the skill body unless the issue explicitly opts into a skill rewrite.
> 3. If the smoke passes, update this pin and PATCH-bump `SKILL.md` only.
> 4. Never edit `references/data-realism/**`.
