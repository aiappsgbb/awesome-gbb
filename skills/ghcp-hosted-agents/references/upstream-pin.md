---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the GitHub Copilot SDK + azure-ai-agentserver-invocations preview stack.
    Version-pinned via PyPI; no git SHA tracking.

    Verified end-to-end against a Foundry test project (`<test-rg>`) on 2026-05-17:
    `azd ai agent init` -> `azd up` -> direct invocations curl returned an
    assistant.message with the expected text in <8s on gpt-5.4-mini.

packages:
  - name: github-copilot-sdk
    source: pypi
    version: "1.0.1"
    upstream_changelog: https://pypi.org/project/github-copilot-sdk/#history
  - name: azure-ai-agentserver-invocations
    source: pypi
    version: "1.0.0b4"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-invocations/#history
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
  - name: python-dotenv
    source: pypi
    version: "1.2.2"
    upstream_changelog: https://pypi.org/project/python-dotenv/#history

docs_to_revalidate:
  - https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/publish-copilot
  - https://pypi.org/project/github-copilot-sdk/
  - https://pypi.org/project/azure-ai-agentserver-invocations/
  - https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/bring-your-own/invocations/github-copilot

known_issues:
  - id: KI-001
    description: |
      May 2026 Foundry data-plane rename: `azd ai agent` postdeploy hook assigns
      "Foundry User" (GUID 53ca6127-db72-4b80-b1b0-d745d6d5456d) to the agent
      identity at PROJECT scope only. The BYOK provider call inside the container
      requires Foundry User at ACCOUNT scope (CognitiveServices) as well. Without
      it the container reports a silent SSE error event:
      "Authentication failed with provider ... (HTTP 401). Check your
      COPILOT_PROVIDER_API_KEY or COPILOT_PROVIDER_BEARER_TOKEN." Add an account-
      scope role assignment for both `instance_identity.principal_id` AND
      `blueprint.principal_id` (visible in `azd ai agent show`).
    upstream_url: https://learn.microsoft.com/azure/ai-foundry/concepts/rbac-azure-ai-foundry
    status: open
    workaround_location: SKILL.md § "Identity & RBAC for hosted agents"

  - id: KI-002
    description: |
      `azd ai agent invoke` (azure.ai.agents extension 0.1.31-preview) sends a
      body the official Microsoft container template rejects with HTTP 400
      "Request body must be a JSON object with a non-empty \"input\" string".
      The CLI does NOT wrap user input in `{"input": "<text>"}` before posting.
      Workaround: invoke via curl/Python with the correct body shape — see
      SKILL.md § "Invoking the Agent".
    upstream_url: https://github.com/Azure/azure-dev/issues
    status: open
    workaround_location: SKILL.md § "Invoking the Agent" -> curl recipe

  - id: KI-003
    description: |
      `azd ai agent init` does NOT add a `services:` block to azure.yaml.
      Without one, `azd deploy` says "deployed in <1s" and ships nothing.
      Caller must add the services entry pointing at the project root with
      `host: azure.ai.agent` and `docker.remoteBuild: true`.
    upstream_url: https://learn.microsoft.com/azure/developer/azure-developer-cli/reference#azd-ai-agent-init
    status: open
    workaround_location: SKILL.md § "azure.yaml (required for azd deploy)"

  - id: KI-004
    description: |
      `azd deploy` postdeploy hook for `azd ai agent` requires `AZURE_TENANT_ID`
      to be set in the azd environment. Failure mode: "AZURE_TENANT_ID is not
      set" mid-deploy. Fix: `azd env set AZURE_TENANT_ID <tenant-guid>` once
      after `azd env new`.
    upstream_url: https://learn.microsoft.com/azure/developer/azure-developer-cli/reference#azd-env-set
    status: open
    workaround_location: SKILL.md § "azure.yaml (required for azd deploy)" -> AZURE_TENANT_ID note

  - id: KI-005
    description: |
      Provider shape (as of github-copilot-sdk 1.0 GA): prefer
      `ProviderConfig(type="azure", base_url=<bare project endpoint>,
      wire_api="responses", bearer_token=<token>)` over the legacy dict form
      `{"type": "openai", "base_url": ".../openai/v1/", ...}`. The legacy form
      still works (backward-compatible) but is 2-3x slower per query.
      The combination `type="openai" + bare endpoint` (without /openai/v1/) is
      GENUINELY BROKEN — yields "Missing required query parameter: api-version".
    upstream_url: https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/hosted-agents/bring-your-own/invocations/github-copilot/main.py
    status: open
    workaround_location: SKILL.md § "BYOK Authentication Deep Dive" -> provider shape decision matrix

  - id: KI-006
    description: |
      Breaking change in github-copilot-sdk 1.0 GA: the `SubprocessConfig`
      wrapper class is REMOVED from the public surface, and the
      `auto_start` kwarg is REMOVED from `CopilotClient.__init__`. The 1.0
      constructor is flat: `CopilotClient(github_token=...)`
      (no wrapper) for GitHub-token mode, `CopilotClient()` for BYOK mode,
      and `await client.start()` is mandatory before creating sessions.
      0.x code `CopilotClient(SubprocessConfig(github_token=...),
      auto_start=False)` raises `ImportError` on 1.0.0+ at import time.
    upstream_url: https://pypi.org/project/github-copilot-sdk/1.0.0/
    status: documented_in_skill
    workaround_location: SKILL.md § "CopilotClient Session Parameters" + container.py reference (callout in version-drift note)

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "github-copilot-sdk~=1.0.0" \
      "azure-ai-agentserver-invocations==1.0.0b4" \
      "azure-identity~=1.25.3" \
      "python-dotenv~=1.2.2"
    python -c "
    from copilot import CopilotClient
    from copilot.session import PermissionHandler, ProviderConfig
    from copilot.generated.session_events import SessionEventType
    from azure.ai.agentserver.invocations import InvocationAgentServerHost
    print('ok ghcp-hosted-agents imports')

    # KI-006 regression assert: SubprocessConfig MUST be gone (removed in 1.0 GA).
    try:
        from copilot import SubprocessConfig  # noqa: F401
        raise AssertionError('SubprocessConfig should NOT be importable on 1.0 GA')
    except ImportError:
        print('ok SubprocessConfig removed in 1.0 GA (KI-006)')

    # ProviderConfig is a TypedDict — returns a plain dict at runtime.
    # The meaningful contract is that type='azure' is accepted (the recommended
    # shape against the post-rename Foundry data plane).
    p = ProviderConfig(type='azure', base_url='https://example/api/projects/p',
                      wire_api='responses', bearer_token='dummy')
    assert isinstance(p, dict), 'ProviderConfig should be a TypedDict (dict at runtime)'
    assert p['type'] == 'azure', 'ProviderConfig.type=azure should be accepted'
    print('ok ProviderConfig type=azure accepted')

    # Assert flat CopilotClient(github_token=...) shape works (1.0 GA replacement).
    c = CopilotClient(github_token='dummy')
    assert c is not None
    print('ok CopilotClient(github_token=...)')
    "
  expected_output:
    - "ok ghcp-hosted-agents imports"
    - "ok SubprocessConfig removed in 1.0 GA (KI-006)"
    - "ok ProviderConfig type=azure accepted"
    - "ok CopilotClient(github_token=...)"

last_validated: 2026-06-10
validated_by: ricchi
known_issues_count: 6
---

# Upstream pin — `ghcp-hosted-agents` skill

This Tier-B pin captures the PyPI package stack for the GitHub Copilot SDK
hosted-agent wrapper (BYOK + Invocations protocol).

## Why pinned

The skill wraps two preview PyPI packages whose release cadences are not
coordinated:

- `github-copilot-sdk` — `1.0.1` is the current **GA** release; the 0.3.x
  series and the 1.0.0b1-b4 prereleases are superseded. The `~=1.0.0` cap
  covers PATCH bumps inside 1.0.x. Breaking changes vs 0.3.x: removed
  `SubprocessConfig` wrapper class, removed `auto_start` kwarg on
  `CopilotClient.__init__` (see KI-006). Existing skill code using
  `CopilotClient(SubprocessConfig(...), auto_start=False)` was updated to
  the flat `CopilotClient(github_token=...)` shape.
- `azure-ai-agentserver-invocations` — `1.0.0b4` is the latest public
  beta (no GA release yet); pinned exact (`==`) because the cap pattern
  doesn't apply across pre-release boundaries.

## Last validation

`2026-06-10` (ricchi) — `github-copilot-sdk==1.0.1` adversarially diff'd
against `0.3.0` API surface on a clean Python 3.14 venv; every import in
`container.py` re-verified; `CopilotClient(github_token=...)` and
`CopilotClient()` constructors instantiated without error; KI-006
regression added to `validation.script` to assert `SubprocessConfig`
remains gone on future pins.

Prior end-to-end was `2026-05-17` (ricchi) on a Foundry test project:

- `azd ai agent init -t github-copilot` -> downloaded official MS sample
- Added `services:` block manually (KI-003)
- `azd env set AZURE_TENANT_ID <id>` (KI-004)
- `azd up` -> Foundry account + project + ACR + ManagedAgentIdentityBlueprint
- Added Foundry User at ACCOUNT scope to both agent identities (KI-001)
- `curl -X POST .../invocations -d '{"input":"..."}'` -> assistant.message in 7.4s
- `azd ai agent invoke` confirmed broken with HTTP 400 (KI-002)
