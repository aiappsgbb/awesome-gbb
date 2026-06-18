---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: microsoft/agent-framework
  ref: main
  pinned_sha: b3f8aaa9d7e662c2c433b722e63a1b6d10f63b75
  pinned_commit_message: |
    Bumped to SHA b3f8aaa9d7e662c2c433b722e63a1b6d10f63b75
  license: MIT
  notes: |
    foundry-iq primarily wraps Azure AI Search Knowledge Base / agentic retrieval docs. The only GitHub upstream referenced by SKILL.md is microsoft/agent-framework for hosted-MCP behavior; validation also pins the Azure AI Search Python SDK.
packages:
  - name: azure-search-documents
    source: pypi
    version: "12.0.0"
    upstream_changelog: https://pypi.org/project/azure-search-documents/
    notes: |
      Used for import-only smoke validation of Azure AI Search client types. No Azure service calls are made.
docs_to_revalidate:
  - https://learn.microsoft.com/azure/search/search-agentic-retrieval-concept
  - https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-create
  - https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-retrieve
  - https://pypi.org/project/azure-search-documents/
known_issues: []
validation:
  requires:
    - github_only
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    PINNED_SHA="${PINNED_SHA:-b3f8aaa9d7e662c2c433b722e63a1b6d10f63b75}"
    PINNED_VERSION="${PINNED_VERSION:-12.0.0}"
    WORK=".upstream-pin-smoke/foundry-iq"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    remote="$(git ls-remote https://github.com/microsoft/agent-framework main | awk '{print $1}')"
    test "$remote" = "$PINNED_SHA"
    echo "pinned SHA verified: ${PINNED_SHA}"

    python -m venv "$WORK/.venv"
    . "$WORK/.venv/bin/activate"
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet "azure-search-documents~=${PINNED_VERSION}"
    python - <<'PY'
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.models import VectorizedQuery
    assert SearchClient and SearchIndexClient and VectorizedQuery
    PY
    echo "azure-search-documents import smoke ok: ${PINNED_VERSION}"

    curl -fsSI -L "https://learn.microsoft.com/azure/search/search-agentic-retrieval-concept" >/dev/null
    curl -fsSI -L "https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-create" >/dev/null
    curl -fsSI -L "https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-retrieve" >/dev/null
    echo "Foundry IQ docs link check ok"
  expected_output:
    - "pinned SHA verified"
    - "azure-search-documents import smoke ok"
    - "Foundry IQ docs link check ok"
  failure_signatures: []
last_validated: 2026-06-18
validated_by: copilot-bot
field_test_scope: github_pypi_docs
known_issues_count: 0
---

# Upstream pin — `foundry-iq` skill

This file is the **machine-readable validation contract** for the `foundry-iq`
skill. The YAML front-matter above is parsed by `scripts/check-freshness.py`
weekly; the prose below is the human audit trail. Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `microsoft/agent-framework` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `b3f8aaa9d7e662c2c433b722e63a1b6d10f63b75` |
| **Pinned commit subject** | `Bumped to SHA b3f8aaa9d7e662c2c433b722e63a1b6d10f63b75` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-06-18` |

Refresh procedure:
```bash
git ls-remote https://github.com/microsoft/agent-framework main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Pinned packages (Tier B / mixed only)

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-search-documents` | PyPI | **12.0.0** | Import-only smoke for Azure AI Search client types; no live service calls. |

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: this section's `bash` block is what
> `validation.script` in the front-matter expands to. Keep them identical. The
> agent will run this script verbatim.

```bash
#!/usr/bin/env bash
set -euo pipefail

PINNED_SHA="${PINNED_SHA:-b3f8aaa9d7e662c2c433b722e63a1b6d10f63b75}"
PINNED_VERSION="${PINNED_VERSION:-12.0.0}"
WORK=".upstream-pin-smoke/foundry-iq"

rm -rf "$WORK"
mkdir -p "$WORK"
remote="$(git ls-remote https://github.com/microsoft/agent-framework main | awk '{print $1}')"
test "$remote" = "$PINNED_SHA"
echo "pinned SHA verified: ${PINNED_SHA}"

python -m venv "$WORK/.venv"
. "$WORK/.venv/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet "azure-search-documents~=${PINNED_VERSION}"
python - <<'PY'
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
assert SearchClient and SearchIndexClient and VectorizedQuery
PY
echo "azure-search-documents import smoke ok: ${PINNED_VERSION}"

curl -fsSI -L "https://learn.microsoft.com/azure/search/search-agentic-retrieval-concept" >/dev/null
curl -fsSI -L "https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-create" >/dev/null
curl -fsSI -L "https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-retrieve" >/dev/null
echo "Foundry IQ docs link check ok"
```

**Expected output** must contain (substring match):

- `pinned SHA verified`
- `azure-search-documents import smoke ok`
- `Foundry IQ docs link check ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| GitHub reference | ✅ | `pinned SHA verified` |
| SDK import smoke | ✅ | `azure-search-documents import smoke ok` |
| Learn docs | ✅ | `Foundry IQ docs link check ok` |

Captured at `last_validated: 2026-06-18` by `copilot-bot` via pin-validation CI on issue #192.

---

## 5. Known issues at this pin

No known issues are tracked for this pin.

---

## 6. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/microsoft/agent-framework main
   ```
2. **Update front-matter** with the new SHA and commit subject. If the SDK
   validation should move too, update `packages[0].version` and use
   `PINNED_VERSION=<new-version>` for the smoke.
3. **Run the validation script**:
   ```bash
   PINNED_SHA=<new-sha> PINNED_VERSION=<version> bash -c "$(yq '.validation.script' upstream-pin.md)"
   ```
4. **Verify expected output** from § 3.
5. **Update audit trail**.
6. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
7. **Open PR** touching only this file and `SKILL.md`.

---

## 7. URLs to re-validate (link-rot detector input)

- <https://learn.microsoft.com/azure/search/search-agentic-retrieval-concept>
- <https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-create>
- <https://learn.microsoft.com/azure/search/search-agentic-retrieval-how-to-retrieve>
- <https://pypi.org/project/azure-search-documents/>

---

## 8. Cross-references worth bookmarking

- `azure-search-documents` — Azure AI Search Python SDK imported by the smoke.
- `microsoft/agent-framework` PR references — source of hosted-MCP behavior called out in the troubleshooting table.
- Learn agentic retrieval pages — canonical docs for Knowledge Bases and retrieval calls.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. Run `validation.script`; it uses public GitHub and PyPI only.
> 2. Do not add `az`, Foundry SDK live calls, or an Azure subscription requirement
>    unless you also change `automation_tier` to `issue_only`.
> 3. If the smoke passes, update the pin and PATCH-bump `SKILL.md` only.
> 4. Never edit `references/data-realism/**`.
