---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the GitHub Copilot SDK + azure-ai-agentserver-invocations
    stack, on the GA unified `azure.yaml` hosted-agent deploy shape shared
    with `foundry-hosted-agents`. Version-pinned via PyPI; no git SHA
    tracking for the packages themselves, but the deploy-model migration in
    this pin is grounded against two upstream sources with pinned commits:

    - microsoft-foundry/foundry-samples commit
      `22b2c89c676bddb107ea370330d6341e25ff674b` —
      `samples/python/hosted-agents/bring-your-own/invocations/github-copilot`
      is the official Microsoft sample for this exact SDK + protocol
      combination. Its `azure.yaml` confirms `requiredVersions.extensions.
      azure.ai.agents: '>=1.0.0-beta.4'`, `protocols: [{protocol:
      invocations, version: 2.0.0}]`, and `infra.provider: microsoft.foundry`.
      Its `main.py` confirms the GA public import surface:
      `from copilot import CopilotClient, PermissionHandler, ProviderConfig`
      and `from copilot.session_events import SessionEventType`.
    - Azure/azure-dev — three merged PRs retire the pre-GA known issues this
      pin used to carry:
      - PR #8941 (merge commit `19c231956388941ace7dbe3f697617198d25dff3`,
        merged 2026-07-03) — stops the `azure.ai.agents` extension from
        assigning a role to the per-agent managed identity after deploy;
        Foundry now grants the identity's required permissions internally.
        Retires KI-001.
      - PR #8866 (merge commit `a4cf4a909479583693e1b185d0a784e02068e885`,
        merged 2026-07-06) — removes `Foundry-Features: *=V1Preview`
        headers for GA; the endpoint API version literal is now `v1`.
        Retires the V1Preview-header prose that used to accompany KI-002.
      - PR #8981 (merge commit `635b011eebbf47c1efa59b37c7f08023b5ee8a54`,
        merged 2026-07-06) — wires the container registry automatically for
        `azd ai agent init -m <azure.yaml> --deploy-mode container` on an
        adopted (brownfield) project. Retires KI-003/KI-004's manual
        `services:`/`AZURE_TENANT_ID` wiring — the unified single-file
        `azure.yaml` plus guided init supersede both.

    Reference audit commit for this migration pass: Azure/azure-dev
    `9efebd953104414cf58eb78098729519b184bb6b` was supplied as the
    citation anchor for the beta.3/beta.5 GA-split behavior described
    above; the three PRs (#8941, #8866, #8981) are the specific merged
    changes that retire KI-001 through KI-004 and are cited by their own
    merge-commit SHAs for precision.

    KI-002's original claim ("`azd ai agent invoke` does not wrap user
    input") does not reproduce against the current GA CLI (`azd ai agent
    invoke <name> '{"input": "..."}' --protocol invocations` sends the
    literal JSON body positionally, matching the official README's
    documented usage) — retired as a pre-GA-only defect, not carried
    forward.

packages:
  - name: github-copilot-sdk
    source: pypi
    version: "1.0.1"
    upstream_changelog: https://pypi.org/project/github-copilot-sdk/#history
  - name: azure-ai-agentserver-invocations
    source: pypi
    version: "1.0.0b6"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-invocations/#history
  - name: azure-ai-agentserver-core
    source: pypi
    version: "2.0.0b7"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-core/#history
    notes: |
      Transitive dep of azure-ai-agentserver-invocations (which declares
      `azure-ai-agentserver-core>=2.0.0b7`, UNBOUNDED-UPPER). Pinned EXACTLY to
      `==2.0.0b7` in references/pyproject.toml to stop a future core b8+ from
      silently breaking fresh container builds. Grounded: a stale probe on
      invocations b4 + core b7 crash-looped with
      `ImportError: cannot import name 'CHAT_ISOLATION_KEY'` (2026-07-04). The
      current b6 + b7 combo is proven healthy live.
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
  - id: KI-005
    description: |
      Provider shape (as of github-copilot-sdk 1.0 GA): prefer
      `ProviderConfig(type="azure", base_url=<bare project endpoint>,
      wire_api="responses", bearer_token=<token>)` over the legacy dict form
      `{"type": "openai", "base_url": ".../openai/v1/", ...}`. The legacy form
      still works (backward-compatible) but is 2-3x slower per query.
      The combination `type="openai" + bare endpoint` (without /openai/v1/) is
      GENUINELY BROKEN — yields "Missing required query parameter: api-version".
    upstream_url: https://github.com/microsoft-foundry/foundry-samples/blob/main/samples/python/hosted-agents/bring-your-own/invocations/github-copilot/src/github-copilot-invocations/main.py
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
      "azure-ai-agentserver-invocations==${PINNED_VERSION:-1.0.0b6}" \
      "azure-identity~=1.25.3" \
      "python-dotenv~=1.2.2"
    python -c "
    from copilot import CopilotClient, PermissionHandler, ProviderConfig
    from copilot.session_events import SessionEventType
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

last_validated: 2026-07-14
validated_by: copilot-bot
known_issues_count: 2
---

# Upstream pin — `ghcp-hosted-agents` skill

This Tier-B pin captures the PyPI package stack for the GitHub Copilot SDK
hosted-agent wrapper (BYOK + Invocations protocol), now on the GA unified
`azure.yaml` deploy shape.

## Why pinned

The skill wraps two preview PyPI packages whose release cadences are not
coordinated:

- `github-copilot-sdk` — `1.0.1` is the current **GA** release; the 0.3.x
  series and the 1.0.0b1-b4 prereleases are superseded. The `~=1.0.0` cap
  covers PATCH bumps inside 1.0.x. Breaking changes vs 0.3.x: removed
  `SubprocessConfig` wrapper class, removed `auto_start` kwarg on
  `CopilotClient.__init__` (see KI-006). Existing skill code using
  `CopilotClient(SubprocessConfig(...), auto_start=False)` was updated to
  the flat `CopilotClient(github_token=...)` shape. Public import surface
  matches the official Microsoft sample:
  `from copilot import CopilotClient, PermissionHandler, ProviderConfig` +
  `from copilot.session_events import SessionEventType` (not the previous
  `copilot.session` / `copilot.generated.session_events` submodule paths).
- `azure-ai-agentserver-invocations` — `1.0.0b6` is the latest public
  beta (no GA release yet); pinned exact (`==`) because the cap pattern
  doesn't apply across pre-release boundaries. Matches the official
  sample's `requirements.txt` (`azure-ai-agentserver-invocations==1.0.0b6`).
- `azure-ai-agentserver-core` — transitive dep of `-invocations`, which
  declares `azure-ai-agentserver-core>=2.0.0b7` (UNBOUNDED-UPPER). The
  reference `pyproject.toml` now pins it EXACT (`==2.0.0b7`) so a future
  core `b8+` that renames a symbol cannot silently break fresh container
  builds. Grounded 2026-07-04: a stale `invocations b4 + core b7` probe
  crash-looped with `ImportError: cannot import name 'CHAT_ISOLATION_KEY'`
  (HTTP 424 before body-parse); the current `b6 + b7` combo is proven
  healthy live.

## GA deploy-model migration (v2.0.0, this refresh)

This refresh retires the skill's entire pre-GA deploy model in favor of the
same unified single-file `azure.yaml` (services graph, `azd ai agent init`
guided path + direct-copy brownfield path, bicep-less
`infra.provider: microsoft.foundry`) that `foundry-hosted-agents` uses,
adapted for `language: docker` + the Invocations protocol instead of MAF's
Responses protocol. The old two-file `agent.yaml` + hand-wired `azure.yaml`
contract, the `remoteBuild`/manual `services:` wiring, the
`AZURE_TENANT_ID` postdeploy-hook requirement, and the manual account-scope
`Foundry User` role grant are all removed — see SKILL.md § "azure.yaml
(unified GA deployment)" and § "Identity & RBAC for hosted agents".

**KI-001, KI-002, KI-003, and KI-004 are retired, not merely closed:**

- **KI-001** (manual account-scope `Foundry User` grant for the per-agent
  identity) — retired by Azure/azure-dev PR #8941
  (`19c231956388941ace7dbe3f697617198d25dff3`, merged 2026-07-03): the
  `azure.ai.agents` extension no longer assigns a role to the per-agent
  managed identity after deploy at all — Foundry grants the identity's
  required permissions internally. There is nothing left to work around.
- **KI-002** (`azd ai agent invoke` allegedly not wrapping user input in
  `{"input": "..."}`) — did not reproduce against the current GA CLI. The
  official sample's README documents `azd ai agent invoke '{"input": "..."}'`
  as the primary invocation path, and a local `azure.ai.agents`
  `1.0.0-beta.4` CLI's `--help` confirms `azd ai agent invoke [name]
  [message] --protocol invocations --output raw --timeout <seconds>` sends
  the literal positional message. Retired as a pre-GA-only defect.
- **KI-003** (`azd ai agent init` not adding a `services:` block) and
  **KI-004** (`AZURE_TENANT_ID` required before `azd deploy`) — retired by
  the unified single-file `azure.yaml` contract itself (no more separate
  manifest to hand-wire a `services:` block into) plus Azure/azure-dev
  PR #8981 (`635b011eebbf47c1efa59b37c7f08023b5ee8a54`, merged 2026-07-06),
  which wires the container registry automatically for
  `azd ai agent init -m <azure.yaml> --deploy-mode container` on an
  existing (brownfield) project.

KI-005 (provider shape decision matrix) and KI-006 (`SubprocessConfig`
removal) are unaffected by the deploy-model migration and remain open /
documented as before.

## Last validation

`2026-07-14` (copilot-bot) — GA deploy-model migration re-grounded against
two upstream sources: microsoft-foundry/foundry-samples commit
`22b2c89c676bddb107ea370330d6341e25ff674b` (the official sample's
`azure.yaml` + `main.py` confirm the unified single-file services-graph
shape and the GA `copilot` package import surface) and Azure/azure-dev
PRs #8941, #8866, #8981 (confirmed merged via the GitHub API, with the
merge-commit SHAs cited above). `references/container.py` imports updated
to the GA public surface
(`from copilot import CopilotClient, PermissionHandler, ProviderConfig` +
`from copilot.session_events import SessionEventType`) and verified against
a locally installed `github-copilot-sdk==1.0.1` venv. `references/agent.yaml`
deleted; `references/yaml/azure.yaml` added as the new canonical single-file
deploy manifest, byte-verified against the unified-shape assertions in
`scripts/tests/test_ghcp_hosted_agents_ga_contract.py`. Package version pins
(`github-copilot-sdk`, `azure-ai-agentserver-invocations`,
`azure-ai-agentserver-core`, `azure-identity`, `python-dotenv`) are
unchanged from the prior `2026-07-04` validation — only the deploy model
and known-issue set changed in this refresh. Live Azure E2E evidence for
this refresh is tracked separately via the skill's
`test-fixture/consumer_prompt.md` in CI (see AGENTS.md § 2.9); this pin
file records the package/API-surface grounding, not the CI run itself.

Prior validations:

`2026-07-04` (ricchi) — live re-grounding on a real Foundry deploy at
`azure.ai.agents` ext `1.0.0-beta.4`: rebuilt the container on the skill's
exact pins (`invocations b6` + `core b7`), confirmed the container is 100%
healthy on the then-current pre-GA deploy model.

`2026-06-10` (ricchi) — `github-copilot-sdk==1.0.1` adversarially diff'd
against `0.3.0` API surface on a clean Python 3.14 venv; every import in
`container.py` re-verified; `CopilotClient(github_token=...)` and
`CopilotClient()` constructors instantiated without error; KI-006
regression added to `validation.script` to assert `SubprocessConfig`
remains gone on future pins.

`2026-05-17` (ricchi) — original end-to-end validation on a Foundry test
project, on the pre-GA two-file deploy model this refresh retires.
