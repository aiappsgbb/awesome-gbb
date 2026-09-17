---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: Azure-Samples/ai-hub-gateway-solution-accelerator
  ref: citadel-v1
  pinned_sha: 63f0f812474e713916dc909494d655246783a1d9
  pinned_commit_message: |
    Merge pull request #152 from mohamedsaif/citadel-v1
  license: MIT
  notes: |
    This pin shares the hub's exact source revision. Consumed interfaces were
    compared with both previous spoke pins; validation is source/file based,
    not live hub/spoke, JWT or Foundry runtime acceptance.
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

    PINNED_SHA="${PINNED_SHA:-63f0f812474e713916dc909494d655246783a1d9}"
    REPO_URL="https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator"
    WORK="$(mktemp -d)"
    trap 'rm -rf "$WORK"' EXIT
    CONTRACT_DIR="bicep/infra/citadel-access-contracts"

    git clone --quiet --filter=blob:none --no-checkout "$REPO_URL" "$WORK/repo"
    git -C "$WORK/repo" fetch --quiet --depth 1 origin "$PINNED_SHA"
    (cd "$WORK/repo" && git checkout --detach "$PINNED_SHA")
    actual="$(git -C "$WORK/repo" rev-parse HEAD)"
    test "$actual" = "$PINNED_SHA"
    echo "pinned source checkout ok"

    test -f "$WORK/repo/$CONTRACT_DIR/main.bicep"
    test -f "$WORK/repo/$CONTRACT_DIR/main.bicepparam"
    test -f "$WORK/repo/$CONTRACT_DIR/policies/default-ai-product-policy.xml"
    test -f "$WORK/repo/$CONTRACT_DIR/citadel-access-contracts-policy.md"
    grep -R "param services" "$WORK/repo/$CONTRACT_DIR" >/dev/null
    grep -R "apiNameMapping" "$WORK/repo/$CONTRACT_DIR" >/dev/null
    grep -R "endpointSecretName" "$WORK/repo/$CONTRACT_DIR" >/dev/null
    grep -q "scope: product.id" "$WORK/repo/$CONTRACT_DIR/modules/apimOnboardService.bicep"
    grep -q "param authType string = 'ApiKey'" "$WORK/repo/$CONTRACT_DIR/modules/foundryConnection.bicep"
    echo "access contract schema ok"

    curl -fsSI -L "$REPO_URL/tree/$PINNED_SHA/$CONTRACT_DIR" >/dev/null
    curl -fsSI -L "$REPO_URL/blob/$PINNED_SHA/$CONTRACT_DIR/citadel-access-contracts-policy.md" >/dev/null
    echo "policy docs link check ok"
  expected_output:
    - "pinned source checkout ok"
    - "access contract schema ok"
    - "policy docs link check ok"
  failure_signatures: []
last_validated: 2026-09-17
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
| **Pinned SHA** | `63f0f812474e713916dc909494d655246783a1d9` |
| **Pinned commit subject** | `Merge pull request #152 from mohamedsaif/citadel-v1` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last source re-validation** | `2026-09-17`; not live acceptance |

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

Run the frontmatter's `validation.script` verbatim; it is the single executable
definition. It materializes the declared SHA, not the moving branch. Branch
freshness still belongs to the freshness detector; branch drift does not change
the source being validated.

**Expected output** must contain (substring match):

- `pinned source checkout ok`
- `access contract schema ok`
- `policy docs link check ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Source comparison and acceptance boundary

| Check | Result | Evidence |
|-------|--------|----------|
| Exact pinned source | ✅ | `pinned source checkout ok` |
| Access Contract schema | ✅ | `access contract schema ok` |
| Policy docs | ✅ | `policy docs link check ok` |

The prior `08294f09a70833e282776a07fe7f97a6aead55b1` and
`6820ddb822730162858dfd6dc30eaab9e811a062` are both ancestors of the selected
hub pin, not newer fixes being rolled back. Their consumed Access Contract /
standalone Foundry integration trees are byte-identical to each other.
The comparison from `6820ddb` to `63f0f81` found:

| Consumed surface | Source delta |
|---|---|
| `modules/foundryConnection.bicep`, `foundry-integration/` | Unchanged. Connection auth remains ApiKey; category, target, discovery/auth metadata contract retained. |
| `main.bicep` / `main.bicepparam` | Existing input names and primary product/connection naming retained. Optional multi-gateway and key-rotation inputs/outputs added. Defaults use the primary gateway/key; rotation is disabled. |
| `modules/apimOnboardService.bicep` | Product/API association and `scope: product.id` retained. Optional rotation inputs and secondary/active-key outputs added; existing primary-key output remains. |
| Default LLM policy | Allowed models narrowed from `gpt-4o,deepseek-r1,gpt-4.1,gpt-5.4-mini` to `gpt-4.1,gpt-5.4-mini`. Review selected models; never overwrite an approved deployed policy automatically. |
| TOOL/AGENT/MULTI defaults | New asset-aware default policy; not equivalent to the LLM-only path and not accepted by this source comparison. |

This is source compatibility review of the documented LLM path, **not a live
compatibility claim**. The hub pin's lean gateway evidence and blocked positive
JWT test remain separate. The corrected probe and unified Hosted wiring need
owner-authorized live validation on the actual hub/spoke/runtime tuple; local
native-SDK transport tests do not close that gate.

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
