---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Microsoft Foundry hosted-agents preview SDK stack — version-pinned, no git SHA tracking.

packages:
  - name: agent-framework-core
    source: pypi
    version: "1.7.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
  - name: agent-framework-foundry
    source: pypi
    version: "1.7.0"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0a260528"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
  - name: azure-ai-projects
    source: pypi
    version: "2.1.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
  - name: mcp
    source: pypi
    version: "1.27.1"
    upstream_changelog: https://pypi.org/project/mcp/#history
  - name: python-dotenv
    source: pypi
    version: "1.2.2"
    upstream_changelog: https://pypi.org/project/python-dotenv/#history

docs_to_revalidate:
  - https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python
  - https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview
  - https://pypi.org/project/agent-framework-core/
  - https://pypi.org/project/agent-framework-foundry/
  - https://pypi.org/project/agent-framework-foundry-hosting/
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/mcp/

known_issues:
  - id: KI-001
    description: |
      agent.yaml resources and scale blocks may be accepted by schema but dropped by the deployment path.
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview
    status: open
    workaround_location: SKILL.md § "Gotchas & Field Debugging Matrix"
  - id: KI-002
    description: |
      MAF 1.4.0 cutover (May 2026): SDK requests ai.azure.com token audience instead of cognitiveservices.azure.com; pinned-by-sha256 orchestrator images on 1.3.x get 401 on every Responses call after Foundry data-plane rename completes. Re-build with 1.4.0 and re-import every agent version.
    upstream_url: https://pypi.org/project/agent-framework-core/1.4.0/
    status: open
    workaround_location: SKILL.md § "MAF 1.4.0 breaking changes (May 2026)"
  - id: KI-003
    description: |
      MAF 1.4.0: AzureOpenAIChatClient removed from agent_framework.azure; companion services (eval judges, sidecars, direct-AOAI code paths) must migrate to OpenAIChatClient(azure_endpoint=..., model=..., credential=...) from agent_framework.openai.
    upstream_url: https://pypi.org/project/agent-framework-core/1.4.0/
    status: open
    workaround_location: SKILL.md § "MAF 1.4.0 breaking changes (May 2026)" → AzureOpenAIChatClient → OpenAIChatClient migration
  - id: KI-004
    description: |
      Azure renamed the data-plane role "Azure AI User" → "Foundry User" (GUID 53ca6127-db72-4b80-b1b0-d745d6d5456d unchanged). az role assignment create --role "Azure AI User" now fails with RoleDefinitionNotFound; pin assignments by GUID. Also: Foundry Account Owner no longer implies Foundry User on companion-service UAMIs — must grant explicitly on the CognitiveServices account scope.
    upstream_url: https://learn.microsoft.com/azure/ai-foundry/concepts/rbac-azure-ai-foundry
    status: open
    workaround_location: SKILL.md § "Identity & RBAC" → Workload UAMI row + Manual RBAC Assignment

  - id: KI-005
    description: |
      MAF 1.4.0: SkillsProvider(skill_paths=...) keyword constructor removed. Causes TypeError at container startup → sticky session_not_ready on every invocation (container never becomes ready). Use SkillsProvider.from_paths(...) classmethod instead.
    upstream_url: https://pypi.org/project/agent-framework-core/1.4.0/
    status: open
    workaround_location: SKILL.md § "Skill Loading — SkillsProvider" → Constructor variants
  - id: KI-006
    description: |
      ACR layer caching produces identical per-job image digests when only the base image changed (domain files same). Foundry deduplicates create_version → new base image code never reaches the container. Fix: no_cache=True on DockerBuildRequest + ARG BUILD_TS with RUN echo $BUILD_TS.
    upstream_url: https://learn.microsoft.com/azure/container-registry/container-registry-tasks-reference-yaml
    status: open
    workaround_location: SKILL.md § "ACR layer cache trap"
  - id: KI-007
    description: |
      Foundry create_version deduplication: even with a different image tag/digest, create_version returns the existing version when env vars + metadata are identical. New base image code never reaches the container. SEPARATE from KI-006 (image-level vs version-level). Fix: add a changing env var (_BUILD_TS=timestamp) to environment_variables in create_version().
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview
    status: open
    workaround_location: SKILL.md § "MAF 1.6.0 update" → create_version deduplication trap

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "agent-framework-core~=1.7.0" "agent-framework-foundry~=1.7.0" "agent-framework-foundry-hosting~=1.0.0a260528" "azure-ai-projects~=2.1.0" "azure-identity~=1.25.3" "mcp~=1.27.1" "python-dotenv~=1.2.2"
    python -c "
    from agent_framework import Agent, SkillsProvider, tool, MCPStreamableHTTPTool
    from agent_framework.foundry import FoundryChatClient
    from agent_framework_foundry_hosting import ResponsesHostServer
    from agent_framework.openai import OpenAIChatClient  # NEW in 1.4.0 — replaces removed AzureOpenAIChatClient
    from azure.ai.projects import AIProjectClient
    print('ok foundry-hosted-agents imports')
    # Assert breaking change: AzureOpenAIChatClient must NOT be importable from agent_framework.azure
    try:
        from agent_framework.azure import AzureOpenAIChatClient  # noqa: F401
        raise SystemExit('FAIL: AzureOpenAIChatClient unexpectedly still importable on MAF 1.6.0')
    except ImportError:
        print('ok AzureOpenAIChatClient correctly removed in 1.4.0+')
    # Assert microsoft-opentelemetry bundled via agentserver-core (transitive: hosting → agentserver-core → microsoft-opentelemetry)
    # API renamed in microsoft-opentelemetry 1.3.0: configure_azure_monitor → use_microsoft_opentelemetry
    from microsoft.opentelemetry import use_microsoft_opentelemetry as _umo
    print('ok microsoft-opentelemetry bundled via agentserver-core')
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
    print('ok opentelemetry-instrumentation-openai-v2 bundled')
    "
  expected_output:
    - "ok foundry-hosted-agents imports"
    - "ok AzureOpenAIChatClient correctly removed in 1.4.0+"
    - "ok microsoft-opentelemetry bundled via agentserver-core"
    - "ok opentelemetry-instrumentation-openai-v2 bundled"

last_validated: 2026-05-29
validated_by: copilot-bot
known_issues_count: 7
---

# Upstream pin — `foundry-hosted-agents` skill

This Tier-B pin captures the PyPI package stack for the Microsoft Foundry hosted-agent wrapper.
