---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Tier-B package wrapper around microsoft/agent-framework. The source was
    audited at Python tag python-1.14.0, immutable commit
    ae7fa3389c8f70b3ed702b0e04b85a3ee62b1bd1. Package drift is detected
    through the PyPI versions below; the tag and SHA remain audit evidence.

packages:
  - name: agent-framework
    source: pypi
    version: "1.14.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
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
      Exact prerelease pin for the Agent Server Responses 2.x storage model;
      do not replace with a compatible-release range.
  - name: azure-ai-agentserver-core
    source: pypi
    version: "2.1.0b1"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-core/#history
    notes: Exact beta pin paired with the b260813 Foundry hosting adapter.
  - name: azure-ai-agentserver-responses
    source: pypi
    version: "2.1.0b1"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-responses/#history
    notes: Exact beta pin paired with the b260813 Foundry hosting adapter.
  - name: azure-ai-agentserver-invocations
    source: pypi
    version: "1.1.0b1"
    upstream_changelog: https://pypi.org/project/azure-ai-agentserver-invocations/#history
    notes: Exact beta pin paired with the b260813 Foundry hosting adapter.
  - name: agent-framework-tools
    source: pypi
    version: "1.0.0b260730"
    upstream_changelog: https://pypi.org/project/agent-framework-tools/#history
    notes: Exact prerelease pin for optional shell tooling.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history

docs_to_revalidate:
  - https://learn.microsoft.com/agent-framework/agents/harness
  - https://learn.microsoft.com/agent-framework/agents/skills
  - https://learn.microsoft.com/agent-framework/agents/conversations/storage#persisting-sessions-across-restarts
  - https://learn.microsoft.com/azure/foundry/how-to/develop/framework-hosted-agents
  - https://pypi.org/project/agent-framework-foundry-hosting/

known_issues:
  - id: KI-001
    description: FileAccessProvider remains experimental and upstream is still improving its Harness contract; treat its controls as access UX, not sandboxing.
    upstream_url: https://github.com/microsoft/agent-framework/issues/6770
    status: open
    workaround_location: SKILL.md § "Default, opt-in, and experimental feature matrix"
  - id: KI-002
    description: BackgroundAgentsProvider needed a bounded API to cancel tasks and release per-session runtime state; Python 1.14.0 adds release_session(session, cancel_running=True, timeout=30.0).
    upstream_url: https://github.com/microsoft/agent-framework/issues/7385
    status: closed_upstream_fixed
    workaround_location: SKILL.md § "Default, opt-in, and experimental feature matrix"
  - id: KI-003
    description: Released Python 1.14.0 still runs after-call compaction per AgentLoopMiddleware iteration; the fix is merged upstream after the 1.14.0 tag and must be revalidated at the next stable release.
    upstream_url: https://github.com/microsoft/agent-framework/issues/7236
    status: closed_upstream_fixed
    workaround_location: SKILL.md § "Safe plan-to-execute pattern"
  - id: KI-004
    description: Upstream added Harness file-memory, shell, and code-execution samples; agent-framework-tools remains prerelease and workdir or deny lists are not sandboxing.
    upstream_url: https://github.com/microsoft/agent-framework/issues/6448
    status: closed_upstream_fixed
    workaround_location: SKILL.md § "Failure modes and security callouts"

validation:
  runnable: true
  requires:
    - github_only
    - pypi
  script: |
    set -euo pipefail
    : "${PIN_VALIDATION_REPO_ROOT:?PIN_VALIDATION_REPO_ROOT must point to the canonical checkout}"
    VENV="$PWD/agent-framework-harness-pin-venv"
    rm -rf -- "$VENV"
    python -m venv "$VENV"
    VENV_PYTHON="$VENV/bin/python"
    VENV_PIP="$VENV/bin/pip"
    "$VENV_PIP" install --quiet \
      "agent-framework-core~=1.14.0" \
      "agent-framework-foundry~=1.11.0" \
      "agent-framework-foundry-hosting==1.0.0b260813" \
      "azure-ai-agentserver-core==2.1.0b1" \
      "azure-ai-agentserver-responses==2.1.0b1" \
      "azure-ai-agentserver-invocations==1.1.0b1" \
      "agent-framework-tools==1.0.0b260730" \
      "azure-identity~=1.25.3"
    "$VENV_PYTHON" \
      "$PIN_VALIDATION_REPO_ROOT/skills/agent-framework-harness/references/python/test_harness_contract.py"
  expected_output:
    - "HARNESS_SIGNATURE_OK"
    - "HARNESS_RELEASE_OK"
    - "HARNESS_DEFAULTS_OK"
    - "HARNESS_COMPACTION_OK"
    - "HARNESS_CONSTRUCTION_OK"
    - "HARNESS_RECOVERY_OK"
    - "HOSTING_IMPORT_OK"
  failure_signatures:
    - "AssertionError"
    - "ImportError"
    - "ModuleNotFoundError"
    - "FileNotFoundError"

last_validated: 2026-08-21
validated_by: copilot-bot
known_issues_count: 4
---

# Upstream pin — `agent-framework-harness`

This Tier-B pin is the machine-readable runtime contract for the canonical
offline harness smoke.

## Stable 1.14.0 factory baseline

The factory contract was source-audited at Python tag `python-1.14.0`
(`ae7fa3389c8f70b3ed702b0e04b85a3ee62b1bd1`) and validated with
`agent-framework-core` 1.14.0 plus `agent-framework-foundry` 1.11.0.
The broad `agent-framework` meta-package remains release context only and is
not part of the canonical hosted dependency set. PyPI versions drive drift
detection.

## Exact beta hosting and tools pins

`agent-framework-foundry-hosting==1.0.0b260813` and the optional shell-tooling
package `agent-framework-tools==1.0.0b260730` are exact prerelease pins.
Prerelease refreshes require an explicit revalidation rather than cap drift.
The b260813 hosting adapter uses the Agent Server Responses 2.x storage model
with exact core, Responses, and Invocations beta dependencies listed above.

## Verified signature defaults and ordering

The audited factory defaults set the six disable flags (`compaction`, `todo`,
`mode`, `file_memory`, `web_search`, and `tool_auto_approval`) to `False`.
`file_access_store`, `skills_provider`, `skills_paths`, `background_agents`,
`shell_executor`, and `loop_should_continue` default to `None`;
`loop_max_iterations` defaults to `10`.

Provider order is history, conditional compaction, todo, mode, file memory,
optional file access, optional skills, optional background agents, optional
shell, then caller providers. Middleware order is optional loop, tool approval,
message injection, then caller middleware.

Python 1.14.0 also accepts a single caller middleware object directly in
addition to a sequence. `BackgroundAgentsProvider.release_session(...)`
defaults to task cancellation with a bounded 30-second timeout.

## MINOR-refresh rechecks

Every MINOR refresh must re-check web-search capability detection and empty
approval-rule behavior in addition to the signature and ordering assertions.

## Hosted Agents lifecycle tracking

Track the Hosted Agents service lifecycle independently from the Python
hosting adapter's semver; a green adapter import does not establish service
lifecycle compatibility.

## Latest offline smoke

Validated on 2026-08-21 with the canonical reference smoke:

```text
HARNESS_SIGNATURE_OK
HARNESS_RELEASE_OK
HARNESS_DEFAULTS_OK
HARNESS_COMPACTION_OK
HARNESS_CONSTRUCTION_OK
HARNESS_RECOVERY_OK
HOSTING_IMPORT_OK
```
