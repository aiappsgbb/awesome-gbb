---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Microsoft Foundry hosted-agents container-deploy GA
    SDK stack — version-pinned, no git SHA tracking. Container deploy
    (Dockerfile + unified azure.yaml + azd) is GA; source-code
    (--deploy-mode code) deploy remains a separate preview surface,
    documented in isolation in SKILL.md's preview appendix.
    Direct-copy brownfield `azd deploy` requires the active azd environment
    to carry FOUNDRY_PROJECT_ENDPOINT, the full AZURE_AI_PROJECT_ID ARM ID,
    and bare AZURE_CONTAINER_REGISTRY_ENDPOINT. Azure/azure-dev PR #8981
    wires the registry during `azd ai agent init -m <azure.yaml>
    --deploy-mode container`; copying files and skipping init does not.

packages:
  - name: agent-framework-core
    source: pypi
    version: "1.12.1"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
  - name: agent-framework-foundry
    source: pypi
    version: "1.10.3"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260722"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
    notes: |
      Alpha pre-release pinned EXACT per AGENTS.md § 9.5. PEP 440 treats
      ~=1.0.0aN as >=1.0.0aN, <1.1 — pip drifts to later alphas
      (a260609, a260618, …). Pinned EXACT on a260709 (latest alpha as of
      2026-07-09). The validation.script below previously used `~=` for
      this package — a policy bug fixed in this refresh (AGENTS.md § 9.5
      requires exact pins for alpha pre-releases). Do NOT change the
      specifier shape from ==1.0.0aN to ~= without a corresponding
      AGENTS.md § 9.5 amendment.
  - name: azure-ai-projects
    source: pypi
    version: "2.3.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      2.3.0 is the stable SDK release that ships `AgentEndpointConfig`,
      `ProtocolConfiguration`, `ResponsesProtocolConfiguration`,
      `ContainerConfiguration`, and the stable `project.agents.update_details`
      method used for traffic routing (replacing the preview
      `project.beta.agents.patch_agent_details`, which no longer exists in
      this version — `BetaAgentsOperations` only covers `AgentsOptimization`
      operations now).
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
  - name: mcp
    source: pypi
    version: "1.28.1"
    upstream_changelog: https://pypi.org/project/mcp/#history
  - name: python-dotenv
    source: pypi
    version: "1.2.2"
    upstream_changelog: https://pypi.org/project/python-dotenv/#history

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents
  - https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent
  - https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent-code
  - https://learn.microsoft.com/azure/foundry/agents/how-to/author-azure-yaml
  - https://learn.microsoft.com/azure/foundry/agents/concepts/azure-yaml-reference
  - https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions
  - https://learn.microsoft.com/azure/foundry/agents/how-to/install-cli-foundry-extensions
  - https://github.com/Azure/azure-dev/pull/8981
  - https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python
  - https://pypi.org/project/agent-framework-core/
  - https://pypi.org/project/agent-framework-foundry/
  - https://pypi.org/project/agent-framework-foundry-hosting/
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/mcp/

known_issues:
  - id: KI-001
    description: |
      GA migration (container deploy): the two-file `agent.yaml` +
      `agent.manifest.yaml` contract is retired — a single unified
      `azure.yaml` (`azure.ai.project` + `azure.ai.agent` services) is now
      the source of truth. The Responses protocol version bumped from the
      historical "v1" / "1.0.0" preview values to the current GA "2.0.0".
      Traffic-routing moved from the preview
      `project.beta.agents.patch_agent_details(agent_endpoint=AgentEndpoint(...))`
      call (which required the `Foundry-Features: AgentEndpoints=V1Preview`
      header) to the stable `project.agents.update_details(agent_endpoint=
      AgentEndpointConfig(...))` — no preview header. The agent identity now
      has implicit access to model inferencing + session storage by default;
      no postdeploy RBAC-grant step or `Foundry User` account-scope grant is
      required for the standard case (see hosted-agent-permissions doc).
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/concepts/azure-yaml-reference
    status: open
    workaround_location: SKILL.md § "azure.yaml (unified hosted-agent configuration)" + § "Identity & RBAC" + § "Version rollout patterns (blue-green / canary / rollback)"
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
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/concepts/azure-yaml-reference
    status: open
    workaround_location: SKILL.md § "MAF 1.6.0 update" → create_version deduplication trap
  - id: KI-008
    description: |
      MAF 1.8.0 (June 2026) ships two [BREAKING] markers AND triggers two
      sibling correctness improvements landing in the same MAF 1.8 refresh
      PR (alpha-pin discipline fix + FoundryAgent stale-warning correction):

      (1) MAF 1.8 breaking markers — non-impact analysis:
        - agent-framework-github-copilot sub-package internal rename — not
          pinned/imported by this skill. N/A.
        - Experimental Skill abstract-class refactor in agent-framework-core —
          this skill uses the high-level SkillsProvider.from_paths(...) facade,
          not the experimental Skill ABC directly. No direct imports of
          agent_framework._skills.Skill or SkillResource from this skill's
          reference code. Hosted-agent containers don't import either symbol
          directly. Callers who want clean production logs can filter via
          warnings.filterwarnings("ignore", category=ExperimentalWarning).

      (2) Alpha-pin discipline fix (bonus, landed alongside MAF 1.8 bump):
        agent-framework-foundry-hosting was previously specified as
        ~=1.0.0a260528 in this pin's validation.script — which PEP 440 treats
        as >=1.0.0a260528, <1.1, allowing pip to drift to later alphas.
        Corrected to exact pins per AGENTS.md § 9.5 alpha pre-release rule
        (current exact pin: ==1.0.0a260709, see the package notes above).
        Do NOT change the specifier shape from ==1.0.0aN to ~= without
        amending AGENTS.md § 9.5.

      (3) FoundryAgent stale-warning correction (bonus, landed alongside
          MAF 1.8 bump): SKILL.md previously carried two v1.1.1-era warnings
          marking FoundryAgent as broken (hardcoded extra_body={"agent_reference":
          ...}). FoundryAgent has been rehabilitated as of MAF 1.8.0:
          __init__ takes project_endpoint + agent_name + agent_version
          directly; extra_body is opt-in via default_options only. Exact
          version of rehabilitation between 1.1.1 and 1.8.0 not determined.
          Both stale warnings reframed as "Historical (MAF 1.1.1)" notes
          with current-version guidance.
    upstream_url: https://pypi.org/project/agent-framework-core/1.8.1/
    status: open
    workaround_location: SKILL.md § "MAF 1.8.0 update (June 2026)" → breaking markers non-impact analysis

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet --pre "agent-framework-core~=1.12.1" "agent-framework-foundry~=1.10.3" "agent-framework-foundry-hosting==1.0.0b260722" "azure-ai-projects~=2.3.0" "azure-identity~=1.25.3" "mcp~=1.28.1" "python-dotenv~=1.2.2"
    python -c "
    from agent_framework import Agent, SkillsProvider, tool, MCPStreamableHTTPTool
    from agent_framework.foundry import FoundryChatClient
    from agent_framework_foundry_hosting import ResponsesHostServer
    from agent_framework.openai import OpenAIChatClient  # NEW in 1.4.0 — replaces removed AzureOpenAIChatClient
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        AgentEndpointConfig,
        ProtocolConfiguration,
        ResponsesProtocolConfiguration,
        ContainerConfiguration,
        HostedAgentDefinition,
        ProtocolVersionRecord,
    )
    print('ok foundry-hosted-agents imports')
    # Assert breaking change: AzureOpenAIChatClient must NOT be importable from agent_framework.azure
    try:
        from agent_framework.azure import AzureOpenAIChatClient  # noqa: F401
        raise SystemExit('FAIL: AzureOpenAIChatClient unexpectedly still importable')
    except ImportError:
        print('ok AzureOpenAIChatClient correctly removed in 1.4.0+')
    # Assert microsoft-opentelemetry bundled via agentserver-core (transitive: hosting → agentserver-core → microsoft-opentelemetry)
    from microsoft.opentelemetry import use_microsoft_opentelemetry as _umo
    print('ok microsoft-opentelemetry bundled via agentserver-core')
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
    print('ok opentelemetry-instrumentation-openai-v2 bundled')
    # Assert stable, GA update_details is present on the top-level (non-beta) agents surface
    from azure.ai.projects.operations import AgentsOperations
    assert 'update_details' in dir(AgentsOperations), 'update_details missing from stable AgentsOperations'
    print('ok stable project.agents.update_details present')
    # Assert the old preview patch_agent_details is gone from the beta agents surface
    from azure.ai.projects.operations import BetaAgentsOperations
    assert not hasattr(BetaAgentsOperations, 'patch_agent_details'), 'patch_agent_details unexpectedly still present on beta surface'
    print('ok patch_agent_details absent from beta surface')
    "
  expected_output:
    - "ok foundry-hosted-agents imports"
    - "ok AzureOpenAIChatClient correctly removed in 1.4.0+"
    - "ok microsoft-opentelemetry bundled via agentserver-core"
    - "ok opentelemetry-instrumentation-openai-v2 bundled"
    - "ok stable project.agents.update_details present"
    - "ok patch_agent_details absent from beta surface"

last_validated: 2026-07-23
validated_by: copilot-bot
known_issues_count: 7
---

# Upstream pin — `foundry-hosted-agents` skill

This Tier-B pin captures the PyPI package stack for the Microsoft Foundry hosted-agent GA container-deploy wrapper.
