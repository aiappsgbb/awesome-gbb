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
    title: "Deferral can cost more than a warm eager cache on small catalogs"
    description: |
      Every family from gpt-5.4 to gpt-6.1-sol: on a warm 30-function catalog
      (~3.4k tokens) raw input fell 57-76% but input-equivalent cost rose
      +24% to +171%; on 160 functions it fell -37% to -68% (gpt-5.5 warm
      independent +1%, gpt-6.1-sol -12% because cached reads cost 0.05x).
      Re-measure when model families or cache pricing change.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § Measured evidence and § Decide with your own numbers.
  - id: KI-003
    title: "responses.input_tokens.count returns HTTP 400 on Azure"
    description: |
      "This model is not supported by Responses API" for gpt-5.4,
      gpt-5.4-mini and gpt-5-mini deployments (2026-10-14). Measure with
      real usage instead of a pre-flight counter.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § Measure before and after.
  - id: KI-004
    title: "allowed_tools rejects namespace members and namespaces"
    description: |
      tool_choice allowed_tools accepts top-level functions only; a namespaced
      function is "not found" and a namespace entry or a namespace field is
      rejected with HTTP 400. Changing the allowed subset kept cache reads.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § Other levers.
  - id: KI-005
    title: "GPT-5.6+ implicit cache mode re-writes the latest message every request"
    description: |
      cache_write_tokens is a subset of input_tokens. With the default implicit
      mode a new 2k prefix wrote ~2,009 tokens once and then ~11 tokens (the
      latest message) on every request; explicit mode with one breakpoint
      wrote once and then only read (gpt-5.6-luna, gpt-6-luna).
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § Other levers and § Measure first.

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
    assert m.input_equivalent({'input_tokens': 1000, 'cached_tokens': 800, 'output_tokens': 10}, 0.1, 6) == 340.0
    print('contract ok: input-equivalent cost')
    assert m.input_equivalent({'input_tokens': 1000, 'cached_tokens': 600, 'cache_write_tokens': 300, 'output_tokens': 10}, 0.1, 6, 1.25) == 595.0
    print('contract ok: cache-write cost')
    "
  expected_output:
    - "import ok: measure_tool_search"
    - "contract ok: namespace members deferred, tool_search appended, input untouched"
    - "contract ok: endpoint normalization"
    - "contract ok: input-equivalent cost"
    - "contract ok: cache-write cost"

last_validated: 2026-10-14
validated_by: ricchi
---

## Audit trail

### 2026-10-14 — Current model families (v1.1.0)

- Temporary GlobalStandard deployments (gpt-5.5, gpt-5.6-terra, gpt-5.6-luna,
  gpt-6-sol, gpt-6-luna, gpt-6.1-sol, gpt-6-astra) in an owner-controlled
  account; deleted after the run and absence verified via deployment list.
- Two full runs per model (cold, then warm) with retail short-context ratios;
  results in SKILL.md § Measured evidence. Script now models cache writes,
  tracks loaded tools and `found_not_called`, and sets client timeouts.
- First run exposed a benchmark artefact: write cases omitted required fields
  and newer models asked instead of calling; cases now supply all fields.

### 2026-10-14 — Initial pin (v1.0.0)

- Live runs of `references/python/measure_tool_search.py` (Entra ID,
  Sweden Central, Global Standard deployments, `openai` 3.26.0):
  - gpt-5.4-mini (2026-03-17), 30 functions / 5 namespaces: −64.7% input,
    deferred variant called `get_shipping_record` after loading `shipping`.
  - gpt-5.4 (2026-03-05), 30 functions: −65.7% input; 160 functions /
    20 namespaces: about −85% input per complete tool turn.
  - gpt-5-mini and gpt-4.1: HTTP 400 (KI-001), script exit code 2.
- Adversarial review pass (same day): multi-case/session measurement on
  gpt-5.4 with retail ratios c=0.1, r=6 showed deferral +72%/+44% cost on
  30 functions and -62%/-37% on 160 functions (KI-002); deferred MCP
  (-28% input), client-executed search, allowed_tools cache retention
  (KI-004) and the Azure token-count 400 (KI-003) were verified live.
- No Azure resources were created; existing deployments were used.
