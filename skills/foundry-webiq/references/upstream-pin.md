---
schema_version: 2

freshness_tier: B
automation_tier: issue_only

upstream:
  type: docs_only
  notes: |
    Integration guidance for grounding a Foundry hosted agent on Microsoft
    Web IQ. There is no public GitHub SHA or PyPI package to pin — Web IQ is
    a Microsoft-hosted, limited-access service whose technical contract
    (auth header name, Entra scope, MCP endpoint URL, JSON-RPC tool names,
    REST routes, response schema) lives behind an Entra sign-in at
    webiq.microsoft.ai. Freshness is driven by re-validating the public Web
    IQ documentation/marketing URLs for link-rot and by re-confirming the
    gated contract against the live Playground on each flagged review. The
    consumer-side MCP wiring this skill reuses (MCPStreamableHTTPTool +
    parse_tool_results) is owned by foundry-hosted-agents; drift there is
    tracked by that skill's own pin.

packages: []

docs_to_revalidate:
  - https://webiq.microsoft.ai/
  - https://webiq.microsoft.ai/documentation/
  - https://webiq.microsoft.ai/documentation/authentication/
  - https://webiq.microsoft.ai/documentation/mcp/

known_issues:
  - id: gated-contract
    description: |
      The exact Web IQ auth header name, Entra scope, MCP endpoint URL,
      JSON-RPC tool names, REST route, and response field names are NOT
      publicly retrievable (Entra-gated docs). The skill parameterizes all
      of them as consumer-supplied env vars and discovers MCP tool names at
      runtime, so no invented surface ships. Re-confirm these values against
      the live gated docs when provisioning the CI secret and before
      flipping the test fixture to live.
    status: open
    upstream_url: https://webiq.microsoft.ai/documentation/authentication/

validation:
  requires:
    - foundry_project
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY. The live proof for this skill is the (dormant)
    # Copilot-CLI fixture, which needs a real WEBIQ_API_KEY + the confirmed
    # gated contract. This script only checks that the public Web IQ doc
    # URLs still resolve (link-rot) and that the reused MCP helper exists.
    set -euo pipefail

    # 1. Public Web IQ doc surfaces still reachable (HEAD).
    for url in \
      "https://webiq.microsoft.ai/" \
      "https://webiq.microsoft.ai/documentation/authentication/"; do
      curl -fsSL -o /dev/null -I "$url" || { echo "link-rot: $url"; exit 1; }
    done

    # 2. The consumer MCP pattern this skill reuses still exists upstream.
    grep -q "MCPStreamableHTTPTool" \
      skills/foundry-hosted-agents/SKILL.md || {
        echo "foundry-hosted-agents MCP pattern missing"; exit 1; }

    echo "validation OK"
  expected_output:
    - "validation OK"

last_validated: 2026-06-10
validated_by: copilot-cli
---

# Upstream pin — `foundry-webiq` skill

This file is the **machine-readable freshness contract** for the
`foundry-webiq` skill. The YAML front-matter above is parsed by the weekly
freshness detector; the prose below is the human audit trail.

---

## 1. Why no PyPI / SHA pin

`foundry-webiq` is integration guidance for a Microsoft-hosted,
limited-access service. It wraps no SDK release and pins to no repository
SHA. The only drift vectors are (a) the public Web IQ documentation pages
being renamed/removed, and (b) the gated technical contract changing
(auth header, scope, endpoint, tool/route/response shapes).

## 2. What weekly freshness checks

The drift detector HEAD-checks each `docs_to_revalidate` URL. A 404 or a
stale `last_validated` flags the skill for human review. Because the real
contract is Entra-gated, the detector cannot validate it automatically —
that is what the `gated-contract` known issue tracks.

## 3. Human-driven validation cadence

Because `automation_tier: issue_only` + `validation.runnable: false`, the
coding agent will **not** auto-refresh this pin. On a flagged issue a human:

1. Re-reads the public Web IQ pages for positioning/link changes.
2. Signs into the gated docs / Playground and re-confirms the auth header
   name, Entra scope, MCP endpoint, JSON-RPC tool names, REST route, and
   response field names against what the skill parameterizes.
3. Runs the `validation.script` block above (link-rot + reused-pattern
   check).
4. If all pass, bumps `last_validated`, sets `validated_by`, and PATCH-bumps
   the skill's `metadata.version`.

## 4. Why the fixture is the live proof — once a secret exists

Per AGENTS.md § 2.8/§ 2.9, a skill that connects to a remote service must be
proven live. The live proof for this skill is the Copilot-CLI fixture at
`test-fixture/` — but it is currently **dormant** because CI does not yet
hold a `WEBIQ_API_KEY` secret. See `test-fixture/ACTIVATION.md` for the
steps to provision the secret, confirm the gated contract, enroll the skill
in `.github/skill-deps.yml`, and flip the fixture to live. Until then this
skill is **not** claimed as tested against a live Web IQ endpoint.
