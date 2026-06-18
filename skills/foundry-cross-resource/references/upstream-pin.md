---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: microsoft-foundry/foundry-samples
  ref: main
  pinned_sha: f5021de7365779e6901f6fc1c4099e85c7f8de5d
  pinned_commit_message: |
    Add C# observability hosted-agent sample (#390)
  license: MIT
  notes: |
    This skill depends on the Foundry APIM connection Bicep/sample docs. Validation is doc-and-source only; it does not call APIM, Foundry, or Azure.
packages: []
docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/how-to/ai-gateway
  - https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview
  - https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/01-connections/apim
  - https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/test_apim_connection.py
known_issues: []
validation:
  requires:
    - github_only
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    PINNED_SHA="${PINNED_SHA:-f5021de7365779e6901f6fc1c4099e85c7f8de5d}"
    REPO_URL="https://github.com/microsoft-foundry/foundry-samples"
    REF="main"
    WORK=".upstream-pin-smoke/foundry-cross-resource"
    APIM_DIR="infrastructure/infrastructure-setup-bicep/01-connections/apim"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
    actual="$(git -C "$WORK/repo" rev-parse HEAD)"
    test "$actual" = "$PINNED_SHA"
    echo "pinned SHA verified: ${PINNED_SHA}"

    test -f "$WORK/repo/$APIM_DIR/connection-apim.bicep"
    test -f "$WORK/repo/$APIM_DIR/modules/apim-connection-common.bicep"
    test -f "$WORK/repo/$APIM_DIR/APIM-Connection-Objects.md"
    test -f "$WORK/repo/$APIM_DIR/test_apim_connection.py"
    grep -R "metadata" "$WORK/repo/$APIM_DIR" >/dev/null
    python -m py_compile "$WORK/repo/$APIM_DIR/test_apim_connection.py"
    echo "apim module contract ok"

    curl -fsSI -L "https://learn.microsoft.com/azure/foundry/agents/how-to/ai-gateway" >/dev/null
    curl -fsSI -L "https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview" >/dev/null
    echo "docs link check ok"
  expected_output:
    - "pinned SHA verified"
    - "apim module contract ok"
    - "docs link check ok"
  failure_signatures: []
last_validated: 2026-06-18
validated_by: copilot-bot
field_test_scope: github_pypi_docs
known_issues_count: 0
---

# Upstream pin — `foundry-cross-resource` skill

This file is the **machine-readable validation contract** for the
`foundry-cross-resource` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `microsoft-foundry/foundry-samples` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `34881107721a3bb34875df1ca0d936fb8e09cb9f` |
| **Pinned commit subject** | `Add C# observability hosted-agent sample (#390)` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-30` |

Refresh procedure:
```bash
git ls-remote https://github.com/microsoft-foundry/foundry-samples main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

No package is pinned for this Tier-A wrapper. The validation script uses only
GitHub source, Learn URLs, and Python standard-library syntax checks.

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them identical. The
> agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="${PINNED_SHA:-34881107721a3bb34875df1ca0d936fb8e09cb9f}"
REPO_URL="https://github.com/microsoft-foundry/foundry-samples"
REF="main"
WORK=".upstream-pin-smoke/foundry-cross-resource"
APIM_DIR="infrastructure/infrastructure-setup-bicep/01-connections/apim"

rm -rf "$WORK"
mkdir -p "$WORK"
git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
actual="$(git -C "$WORK/repo" rev-parse HEAD)"
test "$actual" = "$PINNED_SHA"
echo "pinned SHA verified: ${PINNED_SHA}"

test -f "$WORK/repo/$APIM_DIR/connection-apim.bicep"
test -f "$WORK/repo/$APIM_DIR/modules/apim-connection-common.bicep"
test -f "$WORK/repo/$APIM_DIR/APIM-Connection-Objects.md"
test -f "$WORK/repo/$APIM_DIR/test_apim_connection.py"
grep -R "metadata" "$WORK/repo/$APIM_DIR" >/dev/null
python -m py_compile "$WORK/repo/$APIM_DIR/test_apim_connection.py"
echo "apim module contract ok"

curl -fsSI -L "https://learn.microsoft.com/azure/foundry/agents/how-to/ai-gateway" >/dev/null
curl -fsSI -L "https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview" >/dev/null
echo "docs link check ok"
```

**Expected output** must contain (substring match):

- `pinned SHA verified`
- `apim module contract ok`
- `docs link check ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Pinned GitHub branch | ✅ | `pinned SHA verified` |
| APIM source contract | ✅ | `apim module contract ok` |
| Learn docs | ✅ | `docs link check ok` |

Captured at `last_validated: 2026-05-30` by `copilot-bot` via OIDC `e2e-azure` job on PR #182.

---

## 5. Known issues at this pin

No known issues are tracked for this pin.

---

## 6. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/microsoft-foundry/foundry-samples main
   ```
2. **Update front-matter** with the new SHA and commit subject.
3. **Run the validation script**:
   ```bash
   PINNED_SHA=<new-sha> bash -c "$(yq '.validation.script' upstream-pin.md)"
   ```
4. **Verify expected output** from § 3.
5. **Update audit trail** (`last_validated`, `validated_by`, issue counts).
6. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
7. **Open PR** touching only this file and `SKILL.md`.

---

## 7. URLs to re-validate (link-rot detector input)

- <https://learn.microsoft.com/azure/foundry/agents/how-to/ai-gateway>
- <https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview>
- <https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/01-connections/apim>
- <https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/test_apim_connection.py>

---

## 8. Cross-references worth bookmarking

- `infrastructure/infrastructure-setup-bicep/01-connections/apim/connection-apim.bicep` — top-level APIM connection module.
- `modules/apim-connection-common.bicep` — common connection metadata shape.
- `APIM-Connection-Objects.md` — source object schema notes.
- `test_apim_connection.py` — upstream offline validator entry point; this pin only syntax-checks it.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. Run `validation.script`; it intentionally avoids live APIM/Foundry calls,
>    so `automation_tier: auto` is safe.
> 2. If it passes, update the pin and PATCH-bump `SKILL.md` only.
> 3. If it fails, comment with the failure output and do **not** open a PR.
> 4. Never edit `references/data-realism/**`.
