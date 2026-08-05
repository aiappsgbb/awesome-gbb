---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: >
    Tier-B package wrapper around microsoft/agent-framework. The source was
    audited at Python tag python-1.13.0, immutable commit
    e39a8a2e79c8c8987a0b9082d3ccb8665734b897. Package drift is detected
    through the PyPI versions below; the tag and SHA remain audit evidence.

packages:
  - name: agent-framework
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
  - name: agent-framework-core
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
  - name: agent-framework-foundry
    source: pypi
    version: "1.10.4"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260730"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
    notes: Exact prerelease pin; do not replace with a compatible-release range.
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
    description: BackgroundAgentsProvider can retain per-session tasks and child sessions; keep host-owned cancellation and cleanup explicit.
    upstream_url: https://github.com/microsoft/agent-framework/issues/7385
    status: open
    workaround_location: SKILL.md § "Default, opt-in, and experimental feature matrix"
  - id: KI-003
    description: CompactionProvider currently runs after each AgentLoopMiddleware iteration; use explicit caps and verify compaction behavior on refresh.
    upstream_url: https://github.com/microsoft/agent-framework/issues/7236
    status: open
    workaround_location: SKILL.md § "Safe plan-to-execute pattern"
  - id: KI-004
    description: Shell and code-execution Harness samples remain incomplete while agent-framework-tools is prerelease; workdir or deny lists are not sandboxing.
    upstream_url: https://github.com/microsoft/agent-framework/issues/6448
    status: open
    workaround_location: SKILL.md § "Failure modes and security callouts"

validation:
  runnable: true
  requires:
    - github_only
    - pypi
  script: |
    set -euo pipefail
    python3 -m venv /tmp/agent-framework-harness-pin
    /tmp/agent-framework-harness-pin/bin/pip install --quiet \
      "agent-framework~=1.13.0" \
      "agent-framework-core~=1.13.0" \
      "agent-framework-foundry~=1.10.4" \
      "agent-framework-foundry-hosting==1.0.0b260730" \
      "agent-framework-tools==1.0.0b260730" \
      "azure-identity~=1.25.3"
    /tmp/agent-framework-harness-pin/bin/python \
      skills/agent-framework-harness/references/python/test_harness_contract.py
  expected_output:
    - "HARNESS_SIGNATURE_OK"
    - "HARNESS_DEFAULTS_OK"
    - "HARNESS_COMPACTION_OK"
    - "HARNESS_CONSTRUCTION_OK"
    - "HOSTING_IMPORT_OK"
  failure_signatures:
    - "AssertionError"
    - "ImportError"
    - "ModuleNotFoundError"
    - "FileNotFoundError"

last_validated: 2026-08-05
validated_by: copilot-bot
known_issues_count: 4
---

# Upstream pin — `agent-framework-harness`

This Tier-B pin is the machine-readable runtime contract for the canonical
offline harness smoke.

## Stable 1.13.0 factory baseline

The factory contract was source-audited at Python tag `python-1.13.0`
(`e39a8a2e79c8c8987a0b9082d3ccb8665734b897`) and validated with
`agent-framework` and `agent-framework-core` 1.13.0 plus
`agent-framework-foundry` 1.10.4. PyPI versions drive drift detection.

## Exact beta hosting and tools pins

`agent-framework-foundry-hosting==1.0.0b260730` and the optional shell-tooling
package `agent-framework-tools==1.0.0b260730` are exact prerelease pins.
Prerelease refreshes require an explicit revalidation rather than cap drift.

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

## MINOR-refresh rechecks

Every MINOR refresh must re-check web-search capability detection and empty
approval-rule behavior in addition to the signature and ordering assertions.

## Hosted Agents lifecycle tracking

Track the Hosted Agents service lifecycle independently from the Python
hosting adapter's semver; a green adapter import does not establish service
lifecycle compatibility.

## Latest offline smoke

Validated on 2026-08-05 with the canonical reference smoke:

```text
HARNESS_SIGNATURE_OK
HARNESS_DEFAULTS_OK
HARNESS_COMPACTION_OK
HARNESS_CONSTRUCTION_OK
HOSTING_IMPORT_OK
```
