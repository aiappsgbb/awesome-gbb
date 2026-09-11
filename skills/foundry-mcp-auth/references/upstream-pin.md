---
schema_version: 2
freshness_tier: B
automation_tier: auto
upstream:
  type: pypi
  notes: |
    Unreleased delegated-auth candidate; detailed evidence is in the validation notes.
    Resource-server, management and Hosted environments
    are separate. Import validation never certifies real delegated OAuth.
    Connection definitions target azure.ai.connections 1.0.0-beta.6 (azd >=1.27.1).
packages:
  - name: fastmcp
    source: pypi
    version: "2.14.7"
    upstream_changelog: https://pypi.org/project/fastmcp/#history
    hold_below: "3.0.0"
    hold_reason: KI-001
  - name: mcp
    source: pypi
    version: "1.29.0"
    upstream_changelog: https://pypi.org/project/mcp/#history
    hold_below: "2.0.0"
    hold_reason: KI-001
  - name: PyJWT
    source: pypi
    version: "2.10.1"
    upstream_changelog: https://pypi.org/project/PyJWT/#history
  - name: azure-ai-projects
    source: pypi
    version: "2.6.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: Management only. Hosted separately uses ~=2.3.0 due to the Foundry provider's <2.4 constraint.
  - name: azure-mgmt-resource
    source: pypi
    version: "23.1.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-resource/#history
    notes: Standard ARM client for the live-verified 2026-05-01 OAuth connection contract.
  - name: agent-framework-core
    source: pypi
    version: "1.16.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
  - name: agent-framework-openai
    source: pypi
    version: "1.14.1"
    upstream_changelog: https://pypi.org/project/agent-framework-openai/#history
    notes: Provider 1.10 lacks _feature_usage despite satisfying the declared lower bound.
  - name: agent-framework-foundry
    source: pypi
    version: "1.10.4"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260730"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
  - name: azure-ai-agentserver-core
    source: pypi
    version: "2.0.0b7"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-core/#history
  - name: azure-ai-agentserver-responses
    source: pypi
    version: "1.0.0b8"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-responses/#history
  - name: azure-ai-agentserver-invocations
    source: pypi
    version: "1.0.0b6"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-invocations/#history
docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/how-to/mcp-authentication
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-authentication
  - https://learn.microsoft.com/agent-framework/integrations/by-component/tools/foundry-toolbox
  - https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks
  - https://learn.microsoft.com/entra/identity-platform/v2-oauth2-on-behalf-of-flow
known_issues:
  - id: KI-001
    description: Hosting requires MCP <2; the resource-server adapter targets FastMCP 2.14. Keep the independent jobs cohort unchanged.
    upstream_url: https://pypi.org/project/agent-framework-foundry-hosting/1.0.0b260730/
    status: open
    workaround_location: SKILL.md Local recipe
  - id: KI-002
    description: Native Hosted/direct caller propagation and late Toolbox consent/revocation are not certified by this pinned cohort.
    upstream_url: https://learn.microsoft.com/agent-framework/integrations/by-component/tools/foundry-toolbox
    status: open
    workaround_location: SKILL.md Released support and remaining acceptance
  - id: KI-003
    description: Custom OAuth creation can fail when the generated connector definition does not meet DirectInvoke OpenAPI 3 requirements; recovery evidence is recorded separately.
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/mcp-authentication
    status: closed_upstream_fixed
    workaround_location: SKILL.md Connection setup
validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv server
    server/bin/pip install --quiet "fastmcp~=2.14.7" "mcp~=1.29.0" "PyJWT[crypto]~=2.10.1"
    server/bin/python -c "from fastmcp.server.auth import RemoteAuthProvider, TokenVerifier; from jwt import PyJWKClient; print('ok auth server imports LOCAL ONLY')"
    python -m venv management
    management/bin/pip install --quiet "azure-ai-projects~=2.6.0" "azure-identity~=1.25.3" "azure-mgmt-resource~=23.1.0"
    management/bin/python -c "from azure.ai.projects.models import MCPTool, MCPToolboxTool; assert MCPTool(server_label='demo', server_url='https://mcp.example.com/mcp', project_connection_id='demo').as_dict()['project_connection_id'] == 'demo'; print('ok auth management imports LOCAL ONLY')"
    python -m venv hosted
    hosted/bin/pip install --quiet "agent-framework-core~=1.16.0" "agent-framework-openai~=1.14.0" "agent-framework-foundry~=1.10.4" "agent-framework-foundry-hosting==1.0.0b260730" "azure-ai-agentserver-core==2.0.0b7" "azure-ai-agentserver-responses==1.0.0b8" "azure-ai-agentserver-invocations==1.0.0b6" "azure-ai-projects~=2.3.0" "azure-identity~=1.25.3" "mcp~=1.29.0"
    hosted/bin/python -c "from agent_framework.foundry import FoundryChatClient; from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer; print('ok auth hosted imports LOCAL ONLY')"
    server/bin/pip check
    management/bin/pip check
    hosted/bin/pip check
  expected_output:
    - "ok auth server imports LOCAL ONLY"
    - "ok auth management imports LOCAL ONLY"
    - "ok auth hosted imports LOCAL ONLY"
last_validated: 2026-09-11
validated_by: copilot-bot
known_issues_count: 2
---

# Dependency contract and separate live evidence

The manifests are independently resolved. Local policy/HTTP tests use locally
generated signing keys; the pin script itself uses no Entra tokens, resource
access or OAuth grants. See the
[validation notes](../../../docs/maintenance/foundry-mcp-auth-validation.md)
for live results, source binding and remaining gates. Machine-readable
validation dates and issue states above are freshness metadata, not release approval.

The inspected newer release (core 1.17 / hosting 1.0.0b260903 / Projects 2.6)
does not close all four user-context/consent paths. The runtime intentionally
uses the locally importable compatible cohort above, not an override of the
provider's SDK upper bound. This is not a silent fallback at runtime.

Release evidence:
[Toolbox transport](https://github.com/microsoft/agent-framework/blob/python-1.13.0/python/packages/foundry_hosting/agent_framework_foundry_hosting/_toolbox.py),
[newer initialization-only consent handler](https://github.com/microsoft/agent-framework/blob/python-1.17.0/python/packages/foundry_hosting/agent_framework_foundry_hosting/_responses.py#L557-L615),
[SDK bridge retaining static authorization](https://github.com/Azure/azure-sdk-for-python/blob/azure-ai-projects_2.6.0/sdk/ai/azure-ai-projects/samples/agents/tools/sample_toolboxes_with_search.py#L68-L103).
