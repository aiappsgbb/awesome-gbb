---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: Azure-Samples/ai-hub-gateway-solution-accelerator
  ref: citadel-v1
  pinned_sha: 26b8c6edb01bdfdc278a4dc2d465bba6b5f45ac4
  pinned_commit_message: |
    Merge pull request #117 from mohamedsaif/citadel-v1
  license: MIT
  notes: |
    This pin tracks the spoke-side Access Contract and Foundry integration artifacts on the citadel-v1 branch. Validation is schema/file based and does not deploy or call APIM.
packages: []
docs_to_revalidate:
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1/bicep/infra/citadel-access-contracts
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/bicep/infra/citadel-access-contracts/citadel-access-contracts-policy.md
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/entraid-auth-validation.md
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/openai-compatible-api-guide.md
known_issues: []
validation:
  requires:
    - github_only
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    PINNED_SHA="${PINNED_SHA:-26b8c6edb01bdfdc278a4dc2d465bba6b5f45ac4}"
    REPO_URL="https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator"
    REF="citadel-v1"
    WORK=".upstream-pin-smoke/citadel-spoke-onboarding"
    CONTRACT_DIR="bicep/infra/citadel-access-contracts"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
    actual="$(git -C "$WORK/repo" rev-parse HEAD)"
    test "$actual" = "$PINNED_SHA"
    echo "pinned SHA verified: ${PINNED_SHA}"

    test -f "$WORK/repo/$CONTRACT_DIR/main.bicep"
    test -f "$WORK/repo/$CONTRACT_DIR/main.bicepparam"
    test -f "$WORK/repo/$CONTRACT_DIR/policies/default-ai-product-policy.xml"
    test -f "$WORK/repo/$CONTRACT_DIR/citadel-access-contracts-policy.md"
    grep -R "param services" "$WORK/repo/$CONTRACT_DIR" >/dev/null
    grep -R "apiNameMapping" "$WORK/repo/$CONTRACT_DIR" >/dev/null
    grep -R "endpointSecretName" "$WORK/repo/$CONTRACT_DIR" >/dev/null
    echo "access contract schema ok"

    curl -fsSI -L "$REPO_URL/tree/$REF/$CONTRACT_DIR" >/dev/null
    curl -fsSI -L "$REPO_URL/blob/$REF/$CONTRACT_DIR/citadel-access-contracts-policy.md" >/dev/null
    echo "policy docs link check ok"
  expected_output:
    - "pinned SHA verified"
    - "access contract schema ok"
    - "policy docs link check ok"
  failure_signatures: []
last_validated: 2026-06-18
validated_by: copilot-bot
known_issues_count: 0
---

# Upstream pin — `citadel-spoke-onboarding` skill

This file is the **machine-readable validation contract** for the
`citadel-spoke-onboarding` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `Azure-Samples/ai-hub-gateway-solution-accelerator` |
| **Branch / tag** | `citadel-v1` |
| **Pinned SHA** | `f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4` |
| **Pinned commit subject** | `Merge pull request #117 from mohamedsaif/citadel-v1` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-15` |

Refresh procedure:
```bash
git ls-remote https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator citadel-v1
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

No package is pinned for this Tier-A wrapper. Validation reads Access Contract
source files and public GitHub docs only.

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them identical. The
> agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="${PINNED_SHA:-f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4}"
REPO_URL="https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator"
REF="citadel-v1"
WORK=".upstream-pin-smoke/citadel-spoke-onboarding"
CONTRACT_DIR="bicep/infra/citadel-access-contracts"

rm -rf "$WORK"
mkdir -p "$WORK"
git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$WORK/repo"
actual="$(git -C "$WORK/repo" rev-parse HEAD)"
test "$actual" = "$PINNED_SHA"
echo "pinned SHA verified: ${PINNED_SHA}"

test -f "$WORK/repo/$CONTRACT_DIR/main.bicep"
test -f "$WORK/repo/$CONTRACT_DIR/main.bicepparam"
test -f "$WORK/repo/$CONTRACT_DIR/policies/default-ai-product-policy.xml"
test -f "$WORK/repo/$CONTRACT_DIR/citadel-access-contracts-policy.md"
grep -R "param services" "$WORK/repo/$CONTRACT_DIR" >/dev/null
grep -R "apiNameMapping" "$WORK/repo/$CONTRACT_DIR" >/dev/null
grep -R "endpointSecretName" "$WORK/repo/$CONTRACT_DIR" >/dev/null
echo "access contract schema ok"

curl -fsSI -L "$REPO_URL/tree/$REF/$CONTRACT_DIR" >/dev/null
curl -fsSI -L "$REPO_URL/blob/$REF/$CONTRACT_DIR/citadel-access-contracts-policy.md" >/dev/null
echo "policy docs link check ok"
```

**Expected output** must contain (substring match):

- `pinned SHA verified`
- `access contract schema ok`
- `policy docs link check ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Pinned branch | ✅ | `pinned SHA verified` |
| Access Contract schema | ✅ | `access contract schema ok` |
| Policy docs | ✅ | `policy docs link check ok` |

Captured at `last_validated: 2026-05-15` by `ricchi`.

---

## 5. Known issues at this pin

No known issues are tracked for this pin.

---

## 6. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator citadel-v1
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

- <https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1/bicep/infra/citadel-access-contracts>
- <https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/bicep/infra/citadel-access-contracts/citadel-access-contracts-policy.md>
- <https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/entraid-auth-validation.md>
- <https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/openai-compatible-api-guide.md>

---

## 8. Cross-references worth bookmarking

- `bicep/infra/citadel-access-contracts/main.bicep` — Access Contract schema.
- `main.bicepparam` — contract template base.
- `policies/default-ai-product-policy.xml` — default product policy.
- `guides/entraid-auth-validation.md` — JWT validation behavior used by spoke onboarding.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. Run `validation.script`; it performs no live Azure, APIM, or Foundry calls.
> 2. If it passes, update the pin and PATCH-bump `SKILL.md` only.
> 3. If it fails, comment with the failure output and do **not** open a PR.
> 4. Never edit `references/data-realism/**`.
