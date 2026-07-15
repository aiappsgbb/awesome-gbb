---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: microsoft/agent-framework
  ref: main
  pinned_sha: b3f2e5392350d32835a40455d5069c18cac47a97
  pinned_commit_message: |
    .NET: [BREAKING] Graduate ToolApprovalAgent and add ToolAutoApprovalRuleContext (#7107)
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
  - https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq
  - https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview
  - https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate
  - https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve
  - https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01
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

    PINNED_SHA="${PINNED_SHA:-b3f2e5392350d32835a40455d5069c18cac47a97}"
    PINNED_VERSION="${PINNED_VERSION:-12.0.0}"
    WORK=".upstream-pin-smoke/foundry-iq"

    rm -rf "$WORK"
    mkdir -p "$WORK"
    remote="$(git ls-remote https://github.com/microsoft/agent-framework main | awk '{print $1}')"
    # #302: informational drift check only — do NOT hard-fail on SHA drift.
    # Upstream `main` moves continuously; a hard `test` flapped the
    # validate-pins gate on unrelated/docs-only PRs and drove perpetual
    # refresh-PR churn. SHA drift is detected + issue-filed by
    # skill-freshness.yml, which is the correct mechanism. The hard gate
    # for this pin is the import smoke + docs-link checks below.
    if [ "$remote" = "$PINNED_SHA" ]; then
      echo "upstream SHA in sync: ${PINNED_SHA}"
    else
      echo "upstream SHA drift (informational, non-fatal): pinned=${PINNED_SHA} remote=${remote}"
    fi
    echo "upstream SHA drift check ok"

    python3 -m venv "$WORK/.venv"
    . "$WORK/.venv/bin/activate"
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet "azure-search-documents~=${PINNED_VERSION}"
    python3 - <<'PY'
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndexFieldReference,
        SearchIndexKnowledgeSource,
        SearchIndexKnowledgeSourceParameters,
    )
    from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
    from azure.search.documents.knowledgebases.models import (
        KnowledgeBaseRetrievalRequest,
        KnowledgeRetrievalSemanticIntent,
        SearchIndexKnowledgeSourceParams,
    )
    from azure.search.documents.models import VectorizedQuery
    assert all((
        SearchClient,
        SearchIndexClient,
        SearchIndexFieldReference,
        SearchIndexKnowledgeSource,
        SearchIndexKnowledgeSourceParameters,
        KnowledgeBaseRetrievalClient,
        KnowledgeBaseRetrievalRequest,
        KnowledgeRetrievalSemanticIntent,
        SearchIndexKnowledgeSourceParams,
        VectorizedQuery,
    ))
    PY
    echo "azure-search-documents import smoke ok: ${PINNED_VERSION}"
    echo "knowledgebases import smoke ok: ${PINNED_VERSION}"

    curl -fsSI -L "https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq" >/dev/null
    curl -fsSI -L "https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview" >/dev/null
    curl -fsSI -L "https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate" >/dev/null
    curl -fsSI -L "https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve" >/dev/null
    curl -fsSI -L "https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01" >/dev/null
    echo "Foundry IQ docs link check ok"
  expected_output:
    - "upstream SHA drift check ok"
    - "azure-search-documents import smoke ok"
    - "knowledgebases import smoke ok"
    - "Foundry IQ docs link check ok"
  failure_signatures: []
last_validated: 2026-07-15
validated_by: copilot-bot
field_test_scope: github_pypi_docs_live_search_rest
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
| **Pinned SHA** | `b3f2e5392350d32835a40455d5069c18cac47a97` |
| **Pinned commit subject** | `.NET: [BREAKING] Graduate ToolApprovalAgent and add ToolAutoApprovalRuleContext (#7107)` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-07-15` |

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

PINNED_SHA="${PINNED_SHA:-b3f2e5392350d32835a40455d5069c18cac47a97}"
PINNED_VERSION="${PINNED_VERSION:-12.0.0}"
WORK=".upstream-pin-smoke/foundry-iq"

rm -rf "$WORK"
mkdir -p "$WORK"
remote="$(git ls-remote https://github.com/microsoft/agent-framework main | awk '{print $1}')"
# #302: informational drift check only — do NOT hard-fail on SHA drift.
# Upstream `main` moves continuously; a hard `test` flapped the
# validate-pins gate on unrelated/docs-only PRs and drove perpetual
# refresh-PR churn. SHA drift is detected + issue-filed by
# skill-freshness.yml, which is the correct mechanism. The hard gate
# for this pin is the import smoke + docs-link checks below.
if [ "$remote" = "$PINNED_SHA" ]; then
  echo "upstream SHA in sync: ${PINNED_SHA}"
else
  echo "upstream SHA drift (informational, non-fatal): pinned=${PINNED_SHA} remote=${remote}"
fi
echo "upstream SHA drift check ok"

python3 -m venv "$WORK/.venv"
. "$WORK/.venv/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet "azure-search-documents~=${PINNED_VERSION}"
python3 - <<'PY'
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndexFieldReference,
    SearchIndexKnowledgeSource,
    SearchIndexKnowledgeSourceParameters,
)
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalSemanticIntent,
    SearchIndexKnowledgeSourceParams,
)
from azure.search.documents.models import VectorizedQuery
assert all((
    SearchClient,
    SearchIndexClient,
    SearchIndexFieldReference,
    SearchIndexKnowledgeSource,
    SearchIndexKnowledgeSourceParameters,
    KnowledgeBaseRetrievalClient,
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalSemanticIntent,
    SearchIndexKnowledgeSourceParams,
    VectorizedQuery,
))
PY
echo "azure-search-documents import smoke ok: ${PINNED_VERSION}"
echo "knowledgebases import smoke ok: ${PINNED_VERSION}"

curl -fsSI -L "https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq" >/dev/null
curl -fsSI -L "https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview" >/dev/null
curl -fsSI -L "https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate" >/dev/null
curl -fsSI -L "https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve" >/dev/null
curl -fsSI -L "https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01" >/dev/null
echo "Foundry IQ docs link check ok"
```

**Expected output** must contain (substring match):

- `upstream SHA drift check ok`
- `azure-search-documents import smoke ok`
- `knowledgebases import smoke ok`
- `Foundry IQ docs link check ok`

**Failure signatures** (treat as upstream regression — report distinctly):

- None.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| GitHub reference | ✅ | `upstream SHA drift check ok` |
| SDK import smoke | ✅ | `azure-search-documents import smoke ok` |
| Learn docs | ✅ | Foundry IQ overview, availability matrix, migration guide, and stable `2026-04-01` REST reference returned success |
| Live Azure AI Search | ✅ | Stable `searchIndex` knowledge-source PUT with `Prefer: return=representation` returned `201`, GET returned `200`, billing was `knowledgeRetrieval=standard`, and cleanup left zero UUID-scoped objects |

Captured at `last_validated: 2026-07-15` by `copilot-bot` via the executable
pin contract plus the `foundry-iq` Copilot-CLI fixture contract against a
real keyless Azure AI Search service.

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

- <https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq>
- <https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview>
- <https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate>
- <https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve>
- <https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01>
- <https://pypi.org/project/azure-search-documents/>

---

## 8. Cross-references worth bookmarking

- `azure-search-documents` — Azure AI Search Python SDK imported by the smoke.
- `microsoft/agent-framework` PR references — source of hosted-MCP behavior called out in the troubleshooting table.
- Learn Foundry IQ, availability, and migration pages — canonical GA-versus-preview boundary.
- Stable Search Service `2026-04-01` REST reference — canonical knowledge-source wire contract.

---

## 9. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. Run `validation.script`; it uses public GitHub and PyPI only.
> 2. Do not add `az`, Foundry SDK live calls, or an Azure subscription requirement
>    unless you also change `automation_tier` to `issue_only`.
> 3. If the smoke passes, update the pin and PATCH-bump `SKILL.md` only.
> 4. Never edit `references/data-realism/**`.
