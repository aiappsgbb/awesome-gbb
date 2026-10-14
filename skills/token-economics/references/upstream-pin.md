---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi_package
  notes: |
    Wraps the Responses API tool-search surface (`tool_search` tool,
    `defer_loading`, `namespace` tools) plus prompt caching, compaction and
    service-tier parameters, called through the `openai` Python SDK against
    Azure OpenAI v1 endpoints with Entra ID. Tool definitions are sent as
    plain dicts, so the SDK only needs Responses passthrough support.

packages:
  - name: openai
    source: pypi
    version: "3.26.0"
    upstream_changelog: https://github.com/openai/openai-python/releases
    notes: |
      Live-validated version for tool_search on Azure (2026-10-14).
  - name: azure-identity
    source: pypi
    version: "1.26.0"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      DefaultAzureCredential / AzureCliCredential + get_bearer_token_provider.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/openai/how-to/tool-search
  - https://developers.openai.com/api/docs/guides/tools-tool-search
  - https://learn.microsoft.com/azure/foundry/openai/how-to/prompt-caching
  - https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning
  - https://learn.microsoft.com/azure/foundry/openai/how-to/responses
  - https://learn.microsoft.com/azure/foundry/openai/how-to/flex-processing
  - https://learn.microsoft.com/microsoft-cloud/dev/dev-proxy/concepts/llm-rate-limits

known_issues:
  - id: KI-001
    title: "tool_search returns HTTP 400 on models before gpt-5.4"
    description: |
      Requests that include {"type": "tool_search"} fail with
      "Tool 'tool_search' is not supported with <model-version>" on gpt-5-mini
      and gpt-4.1 (observed 2026-10-14). There is no fallback to eager loading.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § Support and failure mode (verified).
  - id: KI-002
    title: "Deferred prefixes cache less reliably than large eager prefixes"
    description: |
      In live runs the short deferred prefix produced cache reads only
      intermittently, while the eager tool catalog cached reliably once warm.
      Money savings therefore depend on the eager cache-hit ratio.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § Break-even.

validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv-token-economics
    . .venv-token-economics/bin/activate
    pip install --quiet "openai~=3.26.0" "azure-identity~=1.26.0"
    SKILL_PY="$PIN_VALIDATION_REPO_ROOT/skills/token-economics/references/python"
    PYTHONPATH="$SKILL_PY" python -c "
    import measure_tool_search as m
    print('import ok: measure_tool_search')
    cat = m.build_demo_catalog()
    d = m.to_deferred(cat)
    assert d[-1] == {'type': 'tool_search'}
    assert all(f.get('defer_loading') for ns in d[:-1] for f in ns['tools'])
    assert not any('defer_loading' in ns for ns in d[:-1])
    assert not any(f.get('defer_loading') for ns in cat for f in ns['tools'])
    print('contract ok: namespace members deferred, tool_search appended, input untouched')
    assert m.openai_base_url('https://a.services.ai.azure.com/api/projects/p') == 'https://a.services.ai.azure.com/openai/v1/'
    assert m.openai_base_url('https://a.openai.azure.com/') == 'https://a.openai.azure.com/openai/v1/'
    print('contract ok: endpoint normalization')
    "
  expected_output:
    - "import ok: measure_tool_search"
    - "contract ok: namespace members deferred, tool_search appended, input untouched"
    - "contract ok: endpoint normalization"

last_validated: 2026-10-14
validated_by: ricchi
---

## Audit trail

### 2026-10-14 — Initial pin (v1.0.0)

- Live runs of `references/python/measure_tool_search.py` (Entra ID,
  Sweden Central, Global Standard deployments, `openai` 3.26.0):
  - gpt-5.4-mini (2026-03-17), 30 functions / 5 namespaces: −64.7% input,
    deferred variant called `get_shipping_record` after loading `shipping`.
  - gpt-5.4 (2026-03-05), 30 functions: −65.7% input; 160 functions /
    20 namespaces: about −85% input per complete tool turn.
  - gpt-5-mini and gpt-4.1: HTTP 400 (KI-001), script exit code 2.
- No Azure resources were created; existing deployments were used.
