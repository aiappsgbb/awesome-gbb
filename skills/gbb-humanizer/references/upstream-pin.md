---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: blader/humanizer
  ref: main
  pinned_sha: 225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8
  pinned_commit_message: |
    Merge pull request #300 from blader/changelog-readme (tag v3.1.0)
  license: MIT
  notes: |
    The skill body vendors the upstream v2.5.1 prompt and 29-pattern catalog
    (MIT, attributed). This pin is the audited upstream baseline: v3.1.0
    restructured the catalog into 26 patterns in lettered groups A-F. The
    restructure was reviewed on 2026-10-05 and the vendored snapshot was kept,
    because GBB sections cite its pattern numbers. Validation fetches the pinned
    SHA directly and checks the v3 structure and reference URLs only.
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

    PINNED_SHA="${PINNED_SHA:-225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8}"
    REPO_URL="https://github.com/blader/humanizer"
    WORK=".upstream-pin-smoke/gbb-humanizer"

    rm -rf "$WORK"
    mkdir -p "$WORK/repo"
    git -C "$WORK/repo" init --quiet
    git -C "$WORK/repo" remote add origin "$REPO_URL"
    git -C "$WORK/repo" fetch --quiet --depth 1 origin "$PINNED_SHA"
    git -C "$WORK/repo" checkout --quiet FETCH_HEAD
    actual="$(git -C "$WORK/repo" rev-parse HEAD)"
    test "$actual" = "$PINNED_SHA"
    echo "pinned SHA verified: ${PINNED_SHA}"

    test -f "$WORK/repo/SKILL.md"
    test -f "$WORK/repo/README.md"
    test -f "$WORK/repo/LICENSE"
    grep -q "^## How to work" "$WORK/repo/SKILL.md"
    grep -q "^## When not to act" "$WORK/repo/SKILL.md"
    count="$(grep -Ec '^### [0-9]+\.' "$WORK/repo/SKILL.md")"
    test "$count" -ge 26
    echo "humanizer pattern catalog ok"

    curl -fsSI -L "$REPO_URL" >/dev/null
    curl -fsSI -L "https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing" >/dev/null
    echo "reference URL check ok"
  expected_output:
    - "pinned SHA verified"
    - "humanizer pattern catalog ok"
    - "reference URL check ok"
  failure_signatures: []
last_validated: 2026-10-05
validated_by: ricchi
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
| **Branch / tag** | `main` (tag `v3.1.0`) |
| **Pinned SHA** | `225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8` |
| **Pinned commit subject** | `Merge pull request #300 from blader/changelog-readme` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Vendored catalog** | upstream `v2.5.1` (29 patterns), kept intentionally — see § 5 |
| **Last re-validated** | `2026-10-05` |

Refresh procedure:
```bash
git ls-remote https://github.com/blader/humanizer main
# Compare first column to pinned_sha in front-matter. The validation script
# fetches the pinned SHA directly, so upstream moving past the pin does not
# break CI; the freshness detector reports the drift instead.
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

PINNED_SHA="${PINNED_SHA:-225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8}"
REPO_URL="https://github.com/blader/humanizer"
WORK=".upstream-pin-smoke/gbb-humanizer"

rm -rf "$WORK"
mkdir -p "$WORK/repo"
git -C "$WORK/repo" init --quiet
git -C "$WORK/repo" remote add origin "$REPO_URL"
git -C "$WORK/repo" fetch --quiet --depth 1 origin "$PINNED_SHA"
git -C "$WORK/repo" checkout --quiet FETCH_HEAD
actual="$(git -C "$WORK/repo" rev-parse HEAD)"
test "$actual" = "$PINNED_SHA"
echo "pinned SHA verified: ${PINNED_SHA}"

test -f "$WORK/repo/SKILL.md"
test -f "$WORK/repo/README.md"
test -f "$WORK/repo/LICENSE"
grep -q "^## How to work" "$WORK/repo/SKILL.md"
grep -q "^## When not to act" "$WORK/repo/SKILL.md"
count="$(grep -Ec '^### [0-9]+\.' "$WORK/repo/SKILL.md")"
test "$count" -ge 26
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
| Pinned GitHub commit | ✅ | `pinned SHA verified` |
| Pattern catalog shape | ✅ | `humanizer pattern catalog ok` |
| Reference URLs | ✅ | `reference URL check ok` |

Captured at `last_validated: 2026-10-05` by `ricchi` (local run of the § 3 script).

---

## 5. Known issues at this pin

No upstream defect is tracked for this pin. One intentional divergence:

- **Vendored catalog is the v2.5.1 snapshot, not v3.1.0.** Upstream v3 replaced
  "PERSONALITY AND SOUL" and "CONTENT PATTERNS" with "How to work", lettered
  groups A-F, "When not to act", and 26 patterns ordered strongest first.
  GBB sections and downstream skills cite the vendored numbers (for example
  § 25, § 26, § 28), so renumbering would break those references.
- **Re-audit, 2026-10-05.** Tells new in v3 are mostly covered by the vendored
  catalog or the GBB short-copy guidance: v3 § 4 staged run-up (vendored § 28),
  § 9 stacked qualifiers (vendored § 24), § 10 hyphenated pairs (vendored § 26),
  § 17 borrowed authority (vendored § 27). Not yet adopted: v3 § 3 sayings
  that sound deep, § 5 arguing with no one, § 7 repeated sentence openings,
  § 24 heading repeated in the first sentence, § 25 writing about the document
  instead of its subject, § 26 re-explaining what the reader knows, and the
  "weak alone" calibration. Adopting them is a separate `[skill-rewrite]`
  change, not a pin refresh.

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
>    the skill body unless the issue explicitly opts into a skill rewrite. Update
>    the structural greps in § 3 and record the review in § 5 instead.
> 3. If the smoke passes, update this pin and PATCH-bump `SKILL.md` only.
> 4. Never edit `references/data-realism/**`.
