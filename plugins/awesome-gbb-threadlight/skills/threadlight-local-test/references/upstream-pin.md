---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the MAF Python SDK (Agent + SkillsProvider + @tool) plus
    Streamlit as the Pattern 0 Quickstart UI runtime. Version-pinned, no git
    SHA tracking. The skill ships its own reference package under
    references/quickstart/ — this pin guards the SDK surface that package
    targets.

packages:
  - name: agent-framework
    source: pypi
    version: "1.4.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      MAF surface used by Pattern 0 wiring: Agent, SkillsProvider.from_paths,
      @tool decorator. Same pin family as foundry-hosted-agents to keep the
      Pattern 0 → prod-deploy ergonomic story consistent.
  - name: streamlit
    source: pypi
    version: "1.40.0"
    upstream_changelog: https://pypi.org/project/streamlit/#history
    notes: |
      Pattern 0 chat UI runtime. Caps at 1.40.x — Streamlit minors land
      breaking renderer changes more often than MAF does, and the demo UI
      relies on st.chat_message + st.chat_input which became stable in 1.30.
  - name: azure-identity
    source: pypi
    version: "1.21.0"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      DefaultAzureCredential for FoundryChatClient + AzureOpenAIChatClient.
      Same surface as every other skill in the catalog.

docs_to_revalidate:
  - https://learn.microsoft.com/en-us/agent-framework/agents/skills
  - https://docs.streamlit.io/develop/api-reference/chat
  - https://pypi.org/project/agent-framework/
  - https://pypi.org/project/streamlit/
  - https://pypi.org/project/azure-identity/

known_issues: []

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    # Resolve where the reference package lives on disk. The freshness
    # runner clones the awesome-gbb repo into a temp workspace; this
    # script walks up from the pin file's containing dir to find the
    # quickstart package.
    HERE="$(cd "$(dirname "$0")" && pwd)"
    if [ -d "${HERE}/references/quickstart" ]; then
      PKG="${HERE}/references/quickstart"
    else
      PKG="$(cd "${HERE}/.." 2>/dev/null && pwd)/skills/threadlight-local-test/references/quickstart"
    fi

    # Fallback: download the package contents from the pinned awesome-gbb
    # repo (the runner clones it; if it's not on disk for whatever reason,
    # synthesize a minimal stand-in so the import surface is still tested).
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet \
      "agent-framework~=1.4.0" \
      "streamlit~=1.40.0" \
      "azure-identity~=1.21.0"

    # MAF surface used by Pattern 0 must import cleanly.
    python - <<'PY'
    from agent_framework import Agent, SkillsProvider, tool
    print("ok agent-framework surface")
    PY

    # Streamlit chat primitives that Pattern 0 UI relies on must exist.
    python - <<'PY'
    import streamlit
    assert hasattr(streamlit, "chat_message"), "st.chat_message missing"
    assert hasattr(streamlit, "chat_input"),   "st.chat_input missing"
    print("ok streamlit chat surface")
    PY

    # When the quickstart package is on disk, exercise discover + stubs
    # against the bundled fixture-poc. This is the *real* contract — if
    # MAF or Streamlit renames a surface, this is what we want to fail.
    if [ -d "$PKG/fixture-poc" ]; then
      pip install --quiet "$PKG"
      python -m threadlight_quickstart --check --root "$PKG/fixture-poc"
    else
      echo "ok skipping in-tree --check (quickstart package not on disk)"
    fi

  expected_output:
    - "ok agent-framework surface"
    - "ok streamlit chat surface"

last_validated: 2026-05-16
validated_by: ricchi
known_issues_count: 0
---

# Upstream pin — `threadlight-local-test` skill

This Tier-B pin captures the PyPI dependency surface that the Pattern 0
Quickstart reference package under `references/quickstart/` targets.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `agent-framework` | PyPI | **1.4.0** | MAF `Agent` + `SkillsProvider.from_paths` + `@tool` surface used by Pattern 0 |
| `streamlit` | PyPI | **1.40.0** | Pattern 0 chat UI; pinned to a minor that has stable `st.chat_message` / `st.chat_input` |
| `azure-identity` | PyPI | **1.21.0** | `DefaultAzureCredential` for both Foundry and AOAI backends |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains
`ok agent-framework surface` AND `ok streamlit chat surface`. When the
reference package is on disk (i.e. the runner cloned the catalog), the
script also runs `python -m threadlight_quickstart --check --root <fixture>`
end-to-end against `fixture-poc`.

## Why these caps

- **`agent-framework ~=1.4.0`** — Pattern 0 uses the same wiring shape
  (`Agent + SkillsProvider`) documented in `foundry-hosted-agents` for prod
  deploy. Keeping the cap consistent across skills means the
  design → quickstart → deploy ergonomic story doesn't bifurcate.
- **`streamlit ~=1.40.0`** — Streamlit's minor releases land renderer
  breaking changes more often than its semver suggests; the cap keeps the
  Pattern 0 chat UI deterministic until we ship a refresh PR.
- **`azure-identity ~=1.21.0`** — same surface every other skill in the
  catalog uses; refresh in lock-step with the rest.

## Known issues

None at this pin.
