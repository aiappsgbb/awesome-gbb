---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Microsoft Copilot SDK 2.0 (`microsoft-copilot-sdk`,
    formerly `github-copilot-sdk`) + azure-ai-agentserver-invocations stack,
    on the GA unified `azure.yaml` hosted-agent deploy shape shared with
    `foundry-hosted-agents`. Version-pinned via PyPI.

    SDK 2.0 API surface grounded against microsoft/copilot-sdk tag `v2.0.1`
    (commit `3ce61458503b6b27ebd1f674a980f4d9596d9b22`):
    `docs/v2-breaking-changes.md`, `docs/setup/multi-tenancy.md`,
    `docs/setup/azure-managed-identity.md`, `docs/setup/in-process-runtime.md`,
    `python/README.md` (§ Runtime) and the Python sources
    (`python/copilot/client.py`, `session.py`, `_mode.py`).

    Deploy-model grounding carried forward from the GA migration:
    microsoft-foundry/foundry-samples commit
    `22b2c89c676bddb107ea370330d6341e25ff674b` (official GHCP invocations
    sample `azure.yaml` shape) and Azure/azure-dev reference commit
    `9efebd953104414cf58eb78098729519b184bb6b` with merged PRs #8941, #8866
    and #8981, which retired KI-001 to KI-004.

packages:
  - name: microsoft-copilot-sdk
    source: pypi
    version: "2.0.1"
    upstream_changelog: https://github.com/microsoft/copilot-sdk/releases
    notes: |
      Renamed from `github-copilot-sdk` at 2.0.0. The legacy distribution
      still receives 1.x releases, so this pin tracks the new name. Both
      distributions install the `copilot` import package: uninstall
      `github-copilot-sdk` first.
  - name: azure-ai-agentserver-invocations
    source: pypi
    version: "1.3.0"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-invocations/#history
  - name: azure-ai-agentserver-core
    source: pypi
    version: "2.3.0"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-core/#history
    notes: |
      Transitive dep of azure-ai-agentserver-invocations 1.3.0, which declares
      `azure-ai-agentserver-core>=2.3.0,<3.0.0`. Capped with `~=2.3.0` in
      references/pyproject.toml.
  - name: azure-identity
    source: pypi
    version: "1.27.0"
    upstream_changelog: https://pypi.org/project/azure-identity/#history

docs_to_revalidate:
  - https://github.com/microsoft/copilot-sdk/blob/main/docs/v2-breaking-changes.md
  - https://github.com/microsoft/copilot-sdk/blob/main/docs/setup/multi-tenancy.md
  - https://github.com/microsoft/copilot-sdk/blob/main/docs/setup/azure-managed-identity.md
  - https://github.com/microsoft/copilot-sdk/blob/main/python/README.md
  - https://pypi.org/project/microsoft-copilot-sdk/
  - https://pypi.org/project/azure-ai-agentserver-invocations/
  - https://learn.microsoft.com/azure/foundry/agents/how-to/manage-hosted-sessions

known_issues:
  - id: KI-007
    description: |
      Breaking changes in microsoft-copilot-sdk 2.0: `CopilotClient(mode=...)`
      is mandatory ("coding-agent" or "empty"); session options are nested
      (`inference`, `tools`, `permissions`, `events`, `hooks`, `mcp`,
      `skills`, `github`, ...); the singular `provider` option and
      `ProviderConfig` are replaced by named `inference.providers`
      (`NamedProviderConfig`) plus `inference.models`. In Python a legacy
      `provider=` keyword raises `TypeError`; the issue reporter observed the
      TypeScript SDK silently ignoring it. `mode="empty"` requires
      `base_directory`/`session_fs` on the client and `tools.available_tools`
      on every create and resume.
    upstream_url: https://github.com/microsoft/copilot-sdk/blob/main/docs/v2-breaking-changes.md
    status: documented_in_skill
    workaround_location: SKILL.md § "Migrating from SDK 1.x" + references/container.py

  - id: KI-008
    description: |
      Microsoft Agent Framework Copilot adapters are not compatible with SDK
      2.0: `agent-framework-github-copilot` requires
      `github-copilot-sdk<2.0,>=1.0.16`, and both SDK distributions install the
      same `copilot` package. Keep MAF + Copilot adapter apps on SDK 1.x until
      compatible adapters ship.
    upstream_url: https://github.com/microsoft/copilot-sdk/blob/main/docs/integrations/microsoft-agent-framework.md
    status: open
    workaround_location: SKILL.md § "Migrating from SDK 1.x" (staying on 1.x)

  - id: KI-009
    description: |
      SDK 2.0 Python wheels do not bundle the native runtime; it is downloaded
      on first use into ~/.cache unless pre-staged. Foundry hosted agents run
      with HOME=/home/session, so a build-time ~/.cache is not found and
      `COPILOT_SKIP_CLI_DOWNLOAD=1` then fails with "Copilot runtime bundle is
      not cached ... and automatic downloads are disabled". Stage into a fixed
      `COPILOT_CLI_EXTRACT_DIR` at build time.
    upstream_url: https://github.com/microsoft/copilot-sdk/blob/main/python/README.md#runtime
    status: documented_in_skill
    workaround_location: references/Dockerfile + SKILL.md § "Dockerfile"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip uninstall --quiet --yes github-copilot-sdk || true
    pip install --quiet \
      "microsoft-copilot-sdk~=2.0.1" \
      "azure-ai-agentserver-invocations~=${PINNED_VERSION:-1.3.0}" \
      "azure-identity~=1.27.0"
    python - <<'PY'
    import inspect
    from copilot import CopilotClient, RuntimeConnection, define_tool
    from copilot.session import NamedProviderConfig, PermissionHandler
    from copilot.session_events import SessionEventType
    from azure.ai.agentserver.invocations import InvocationAgentServerHost
    print('ok ghcp-hosted-agents imports')

    import copilot
    assert not hasattr(copilot, 'ProviderConfig'), 'ProviderConfig should not be a root export in 2.0'
    assert 'provider' not in inspect.signature(CopilotClient.create_session).parameters
    assert 'provider' not in inspect.signature(CopilotClient.resume_session).parameters
    print('ok singular provider option removed (KI-007)')

    try:
        CopilotClient()
        raise AssertionError('CopilotClient() without mode must fail on 2.0')
    except TypeError:
        print('ok mode is required')

    try:
        CopilotClient(mode='empty', runtime=RuntimeConnection.for_inprocess())
        raise AssertionError('empty mode without base_directory must fail')
    except ValueError:
        print('ok empty mode requires base_directory or session_fs')

    p = NamedProviderConfig(name='foundry', type='openai', wire_api='responses',
                            base_url='https://example.services.ai.azure.com/openai/v1/',
                            bearer_token_provider=lambda _args: 'dummy')
    assert p['name'] == 'foundry'
    assert SessionEventType.SESSION_IDLE.value == 'session.idle'
    print('ok NamedProviderConfig with bearer_token_provider')
    PY
  expected_output:
    - "ok ghcp-hosted-agents imports"
    - "ok singular provider option removed (KI-007)"
    - "ok mode is required"
    - "ok empty mode requires base_directory or session_fs"
    - "ok NamedProviderConfig with bearer_token_provider"

last_validated: 2026-11-20
validated_by: ricchi
known_issues_count: 3
---

# Upstream pin — `ghcp-hosted-agents` skill

This Tier-B pin captures the PyPI stack for the Microsoft Copilot SDK 2.0
hosted-agent wrapper (BYOK + Invocations protocol) on the GA unified
`azure.yaml` deploy shape.

## Why pinned

- `microsoft-copilot-sdk` — `2.0.1` is the current release of the renamed
  SDK (2.0.0 shipped 2026-11-17). `~=2.0.1` covers 2.0.x patches. The pin
  tracks the new distribution because `github-copilot-sdk` keeps shipping
  1.x and would never surface the 2.0 line (#554).
- `azure-ai-agentserver-invocations` `1.3.0` and its dependency
  `azure-ai-agentserver-core` `2.3.0` — refreshed from `1.0.0b6` / `2.0.0b7`
  (#424). `azure-identity` refreshed to `1.27.0`. `python-dotenv` dropped:
  the template no longer imports it.

## SDK 2.0 migration (skill 4.0.0, this refresh)

KI-005 (1.x `ProviderConfig` shape matrix) and KI-006 (1.0 `SubprocessConfig`
removal) are retired: neither API exists in 2.0. KI-007 to KI-009 describe the
2.0 contract. The runtime contract was proven live on 2026-11-20 (below).

## Last validation

`2026-11-20` (ricchi) — live hosted agent on Foundry, internal test
subscription, Sweden Central, `gpt-5.4-mini` GlobalStandard, azd 1.37.3,
`azure.ai.agents` 1.2.0, remote ACR build, Invocations 2.0.0. Image built from
the canonical `references/` files with `microsoft-copilot-sdk` 2.0.1,
`azure-ai-agentserver-invocations` 1.3.0 / `-core` 2.3.0. Results:
`mode="empty"` client with in-process runtime started in 82–94 ms; turn 1
called `get_order` and returned its output; turn 2 resumed the SDK session from
its `$HOME` journal and recalled the tracking code without tool calls; turn 3
`issue_refund` was denied by the `onPreToolUse` hook (`code: denied`) before
its handler ran; after `azd ai agent sessions stop`, a cold container resumed
the same session and recalled the earlier context. The validation script was
checked against the v2.0.1 source tree; CI `pin-validation` runs it against
the published wheel.

Prior validations (SDK 1.x line, retired by this refresh):

`2026-08-05` (copilot-bot) — **instance-RBAC model-inference correction
(v2.0.9).** Controlled Azure tests established the minimum working contract
for real model inference by a hosted agent: grant the per-version
**instance** managed identity (not the blueprint identity) the `Foundry
User` role (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) at BOTH the Foundry
account scope AND the Foundry project scope before invocation. Project-only
failed (401), account-only failed (401), both together succeeded. A valid
dual-scope invocation may emit an initial 401 before an internal retry
succeeds, so validation inspects the full event stream rather than aborting
on the first transient event. The earlier "no agent role grant needed"
claim derived from an upstream echo-agent sample that never called a model;
it silently 401'd on live inference. No package pins, SHAs, or
`known_issues_count` changed in this correction — only the RBAC contract
prose (this file), SKILL.md § "Identity & RBAC for hosted agents", and the
fixture's grant/revoke steps. Do NOT add `transient_auth_error` (or any
authorization token) to the workflow retry classifier: this was a
persistent authorization regression, not a transient. Live GHCP T3 evidence
is tracked via the skill's `test-fixture/consumer_prompt.md` matrix leg.

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
