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
    version: "1.14.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
  - name: agent-framework-foundry
    source: pypi
    version: "1.11.0"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260813"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
    notes: |
      Beta pre-release pinned EXACT per AGENTS.md § 9.5. PEP 440 treats
      ~=1.0.0bN as >=1.0.0bN, <1.1 — pip drifts to later betas. Keep the
      exact ==1.0.0b260813 pin for this 2026-08-18 validation. This beta
      moves agentserver core + Responses together to >=2.1.0b1,<3 and
      agentserver invocations to >=1.1.0b1,<2. Do NOT change the specifier
      shape from ==1.0.0bN to ~= without a corresponding AGENTS.md § 9.5
      amendment.
  - name: azure-ai-agentserver-core
    source: pypi
    version: "2.1.0b1"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-core/#history
    notes: Exact beta pin required so uv admits the Agent Server 2.1 prerelease.
  - name: azure-ai-agentserver-responses
    source: pypi
    version: "2.1.0b1"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-responses/#history
    notes: Exact beta pin paired with core 2.1.0b1 and hosting b260813.
  - name: azure-ai-agentserver-invocations
    source: pypi
    version: "1.1.0b1"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-invocations/#history
    notes: Exact beta pin paired with the hosting b260813 release train.
  - name: azure-ai-projects
    source: pypi
    version: "2.3.0"
    hold_below: "2.4.0"
    hold_reason: KI-009
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      Hold below 2.4.0 (KI-009). The ceiling is intentionally a MINOR
      boundary because agent-framework-foundry 1.11.0 declares
      azure-ai-projects>=2.2,<2.4. Keep this as a direct pyproject
      dependency so the canonical container contract enforces the same
      limit outside transitive resolution.
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
    version: "1.29.0"
    hold_below: "2.0.0"
    hold_reason: KI-010
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
      PR (beta-pin discipline fix + FoundryAgent stale-warning correction):

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

      (2) Beta-pin discipline fix (bonus, refreshed alongside this
          coherent runtime pin): agent-framework-foundry-hosting is a beta
          pre-release. PEP 440 treats ~=1.0.0b260813 as >=1.0.0b260813, <1.1,
          allowing pip to drift to later betas. Keep the current exact pin
          ==1.0.0b260813 per AGENTS.md § 9.5 and the package note above; do
          NOT change the specifier shape from ==1.0.0bN to ~= without
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
  - id: KI-009
    description: agent-framework-foundry 1.11.0 requires azure-ai-projects>=2.2,<2.4; hosted agents prefer the current Foundry integration over Azure AI Projects 2.4-only Toolbox features.
    upstream_url: https://pypi.org/project/agent-framework-foundry/
    status: open
    workaround_location: SKILL.md § "Dependencies (pyproject.toml)"
  - id: KI-010
    description: agent-framework-foundry-hosting 1.0.0b260813 requires direct exact Agent Server core + Responses 2.1.0b1 and invocations 1.1.0b1 pins for uv prerelease admission, plus mcp>=1.24,<2.
    upstream_url: https://pypi.org/project/agent-framework-foundry-hosting/
    status: open
    workaround_location: SKILL.md § "Dependencies (pyproject.toml)"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python3 -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "agent-framework-core~=1.14.0" \
      "agent-framework-foundry~=1.11.0" \
      "agent-framework-foundry-hosting==1.0.0b260813" \
      "azure-ai-agentserver-core==2.1.0b1" \
      "azure-ai-agentserver-responses==2.1.0b1" \
      "azure-ai-agentserver-invocations==1.1.0b1" \
      "azure-ai-projects~=2.3.0" \
      "azure-identity~=1.25.3" \
      "mcp~=1.29.0" \
      "python-dotenv~=1.2.2" \
      "pyyaml~=6.0"
    python - <<'PY'
    import importlib.util
    import os
    import sys
    from pathlib import Path
    import tomllib
    import yaml
    from importlib.metadata import version
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient
    from agent_framework_foundry_hosting import ResponsesHostServer
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        ContainerConfiguration,
        HostedAgentDefinition,
        ProtocolVersionRecord,
    )
    from azure.ai.projects.operations import BetaAgentsOperations
    from microsoft.opentelemetry import use_microsoft_opentelemetry
    from mcp import McpError
    from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor

    canonical_dependencies = [
        "agent-framework-core~=1.14.0",
        "agent-framework-foundry~=1.11.0",
        "agent-framework-foundry-hosting==1.0.0b260813",
        "azure-ai-agentserver-core==2.1.0b1",
        "azure-ai-agentserver-responses==2.1.0b1",
        "azure-ai-agentserver-invocations==1.1.0b1",
        "azure-ai-projects~=2.3.0",
        "azure-identity~=1.25.3",
        "mcp~=1.29.0",
        "python-dotenv~=1.2.2",
    ]
    canonical_versions = {
        "agent-framework-core": "1.14.0",
        "agent-framework-foundry": "1.11.0",
        "agent-framework-foundry-hosting": "1.0.0b260813",
        "azure-ai-agentserver-core": "2.1.0b1",
        "azure-ai-agentserver-responses": "2.1.0b1",
        "azure-ai-agentserver-invocations": "1.1.0b1",
        "azure-ai-projects": "2.3.0",
        "azure-identity": "1.25.3",
        "mcp": "1.29.0",
        "python-dotenv": "1.2.2",
    }
    relative_pyproject = Path(
        "skills/foundry-hosted-agents/references/python/pyproject.toml"
    )
    relative_container = Path(
        "skills/foundry-hosted-agents/references/python/container.py"
    )
    relative_pin = Path("skills/foundry-hosted-agents/references/upstream-pin.md")

    repo_root = Path(
        os.environ.get("PIN_VALIDATION_REPO_ROOT", Path.cwd())
    ).resolve()
    pyproject_path = repo_root / relative_pyproject
    container_path = repo_root / relative_container
    pin_path = repo_root / relative_pin
    assert pyproject_path.exists(), f"missing canonical pyproject: {pyproject_path}"
    assert container_path.exists(), f"missing canonical container: {container_path}"
    assert pin_path.exists(), f"missing canonical pin: {pin_path}"

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    assert len(dependencies) == len(canonical_dependencies)
    for dependency in canonical_dependencies:
        assert dependency in dependencies, f"canonical dependency missing: {dependency}"

    pin_text = pin_path.read_text(encoding="utf-8")
    delimiter = "-" * 3
    frontmatter_lines = []
    for line in pin_text.splitlines():
        if not frontmatter_lines and line == delimiter:
            continue
        if line == delimiter:
            break
        frontmatter_lines.append(line)
    pin = yaml.safe_load("\n".join(frontmatter_lines))
    packages = {package["name"]: package for package in pin["packages"]}
    for package_name, expected_version in canonical_versions.items():
        assert packages[package_name]["version"] == expected_version, (
            f"{package_name} version drift: {packages[package_name]['version']}"
        )

    assert packages["azure-ai-projects"]["hold_below"] == "2.4.0"
    assert packages["azure-ai-projects"]["hold_reason"] == "KI-009"
    assert packages["mcp"]["hold_below"] == "2.0.0"
    assert packages["mcp"]["hold_reason"] == "KI-010"

    issues = {issue["id"]: issue for issue in pin["known_issues"]}
    assert issues["KI-009"]["status"] == "open"
    assert issues["KI-010"]["status"] == "open"
    assert pin["known_issues_count"] == 9
    assert len(pin["known_issues"]) == pin["known_issues_count"]

    container_spec = importlib.util.spec_from_file_location(
        "foundry_hosted_agents_container", container_path
    )
    assert container_spec and container_spec.loader, (
        f"unable to load canonical container spec: {container_path}"
    )
    container_module = importlib.util.module_from_spec(container_spec)
    sys.modules[container_spec.name] = container_module
    container_spec.loader.exec_module(container_module)
    assert container_module.Agent
    assert container_module.SkillsProvider
    assert container_module.MCPStreamableHTTPTool
    assert container_module.FoundryChatClient
    assert container_module.ResponsesHostServer
    assert callable(container_module.main)
    assert hasattr(container_module, "my_tool")
    print("ok canonical container import")

    class OfflineCredential:
        def get_token(self, *scopes, **kwargs):
            raise RuntimeError("network is outside the import smoke")
        def close(self):
            return None

    client = AIProjectClient(
        endpoint="https://example.services.ai.azure.com/api/projects/example",
        credential=OfflineCredential(),
    )
    assert callable(client.agents.update_details)
    assert not hasattr(BetaAgentsOperations, "patch_agent_details")
    try:
        from agent_framework.azure import AzureOpenAIChatClient  # noqa: F401
        raise AssertionError("FAIL: AzureOpenAIChatClient unexpectedly still importable")
    except ImportError:
        pass
    assert ContainerConfiguration and HostedAgentDefinition and ProtocolVersionRecord
    assert Agent and FoundryChatClient and ResponsesHostServer and McpError
    assert version("agent-framework-core").startswith("1.14.")
    assert version("agent-framework-foundry").startswith("1.11.")
    assert version("agent-framework-foundry-hosting") == "1.0.0b260813"
    assert version("azure-ai-agentserver-core") == "2.1.0b1"
    assert version("azure-ai-agentserver-responses") == "2.1.0b1"
    assert version("azure-ai-agentserver-invocations") == "1.1.0b1"
    assert version("azure-ai-projects").startswith("2.3.")
    assert version("azure-identity").startswith("1.25.")
    assert version("mcp").startswith("1.29.")
    assert version("python-dotenv").startswith("1.2.")
    client.close()
    assert callable(use_microsoft_opentelemetry)
    assert OpenAIInstrumentor
    print("ok hosted coherent stack")
    print("ok update_details")
    print("ok otel bundle")
    PY
  expected_output:
    - "ok canonical container import"
    - "ok hosted coherent stack"
    - "ok update_details"
    - "ok otel bundle"

last_validated: 2026-08-18
validated_by: copilot-bot
known_issues_count: 9
---

# Upstream pin — `foundry-hosted-agents` skill

This Tier-B pin captures the PyPI package stack for the Microsoft Foundry hosted-agent GA container-deploy wrapper.
