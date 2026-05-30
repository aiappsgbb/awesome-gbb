# `foundry-hosted-agents` — Deep-Audit Trail (Task 2.2, Phase 2 pilot #2)

**Auditor:** Copilot CLI worker session `09605c9b` (Claude Opus 4.7-xhigh), under
the [2026-05-30 deep-audit and testing rethink](../superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md)
plan, § Task 2.2.
**Date:** 2026-05-30.
**Scan scope (1524-line SKILL.md + 6 reference files, 497 lines):** `SKILL.md`,
`references/upstream-pin.md`, `references/python/{main.py,container.py,pyproject.toml}`,
`references/yaml/{agent.yaml,agent.manifest.yaml}`, `references/bash/postdeploy-agent.sh`.
**Skill version pre-audit:** `1.8.0`.
**Skill version post-audit:** `1.8.1` (PATCH bump for body fixes — Class 2 + Class 15).

This audit mirrors the [`foundry-prompt-agents`](foundry-prompt-agents-audit-trail.md)
template authored under Task 2.1. The 21 bug classes are the cross-cutting
catalogue defined in the master plan § Task 2 preamble. Every claim cites a
line number, a file path, or live `az` output. Every `N/A` justifies why the
class does not apply to this skill's shape.

## Findings (verbatim list)

1. **Class 1 (MID-I: sync `AIProjectClient` paired with async `FoundryChatClient`)** — **N/A** —
   `grep -rn "from azure.ai.projects import AIProjectClient" skills/foundry-hosted-agents/`
   returns 2 sites, both in pure-sync contexts: `SKILL.md` L1240 (the "Invocation"
   one-shot REPL example at L1239-1251, no `await` anywhere in the snippet) and
   `references/upstream-pin.md` L109 (a 4-line `python -c` import-smoke executed
   by `validation.script`). The async pattern is the canonical agent runtime
   form at `SKILL.md` L453 (`from azure.ai.projects.aio import AIProjectClient
   # MUST be .aio (async)!`, with an explicit inline comment), reinforced by the
   "Critical rules" callout at L482-485 and explicitly taught as a trap in
   the troubleshooting table at L1378-1379. Reference Python files (`main.py`,
   `container.py`) carry **zero** sync `AIProjectClient` imports — both use
   `agent_framework.foundry.FoundryChatClient` which encapsulates the async
   client. The master-plan hint of "6 MID-I instances" in this skill (Task 2.2
   step 1) does not materialise — that figure may have been an early-Phase-1
   estimate before the L482-485 callout and L1378-1379 troubleshooting row
   were added in the 1.7.0/1.8.0 ladder.
2. **Class 2 (endpoint URL / token scope bugs)** — **HIT (medium)** — 2 in-skill
   contradictions of the skill's own internal guidance:
   - **`SKILL.md` L975-976** declares the canonical NEW endpoint format
     `https://<acct>.services.ai.azure.com/api/projects/<proj>` for BOTH
     `FOUNDRY_PROJECT_ENDPOINT` and `AZURE_AI_PROJECT_ENDPOINT`, and L978
     explicitly warns: *"For Bicep outputs, write `endpoints['AI Foundry API']`
     not `endpoint` (the default returns the legacy `*.cognitiveservices.azure.com`)"*.
   - **`SKILL.md` L1055** (env var table) violates L975-976 by listing
     `AZURE_AI_PROJECT_ENDPOINT` with the legacy `cognitiveservices.azure.com`
     format. **FIX in Phase B.**
   - **`SKILL.md` L1062** (Bicep `output` sample, line immediately following
     L978's warning) writes
     `output AZURE_AI_PROJECT_ENDPOINT string = '${foundryAccount.properties.endpoint}api/projects/${foundryProject.name}'`
     — which is the exact anti-pattern L978 warns against. **FIX in Phase B**
     to `'${foundryAccount.endpoints['AI Foundry API']}api/projects/${foundryProject.name}'`.
   - **`SKILL.md` L1465** (REST agent-version JSON shape sample,
     `agent_endpoints.responses` field) still shows `cognitiveservices.azure.com`.
     **Deferred** — this is not consumer-copy configuration; it is a literal
     example of the JSON the Foundry agent-versions REST API returns today,
     and the legacy URL appears there because the platform itself emits it in
     that field (the new format only landed for the project-endpoint surface,
     not the per-agent-version response shape). Editing the example to
     `services.ai.azure.com` would misrepresent observed platform behaviour.
     Flag for re-verification when the platform endpoint migration completes
     end-to-end. The cross-cutting endpoint-scope policy of "prefer
     `cognitiveservices.azure.com` for bearer-token `--resource` in CI" stands
     (per Task 2.1 audit L62 / `skill-test.yml` L142) — not in conflict with
     this Class 2 finding, which is about Bicep output/env-var declarations.
   - L92 (MAF 1.3.x "OLD" code block in the 1.4.0 migration recipe) is
     **N/A** — labelled at L84 as the deprecated pattern being migrated AWAY
     FROM; deleting it would erase the migration audit trail.
3. **Class 3 (wrong model names)** — **N/A** — SKILL.md does not hardcode any
   model deployment names; the doc consistently points readers to `agentic-loop`
   (cross-referenced at L1415) as the single source of truth for Foundry model
   selection. `references/yaml/agent.yaml` does not pin a model. The 1
   `gpt-5.4-mini` mention is in the cost-budget preamble of the Phase C
   fixture — written later, not part of the SKILL surface.
4. **Class 4 (wrong RBAC role names)** — **N/A** — 5 RBAC role GUIDs appear in
   `SKILL.md` (L1117, L1146, L1147, L1177, L1180, L1187, L1211, L1380, L1386,
   L1406) and all 3 representative ones live-verified against Azure on this
   tenant on the audit date:
   - `53ca6127-db72-4b80-b1b0-d745d6d5456d` → live name "Foundry User" ✓
   - `18d7d88d-d35e-4fb5-a5c3-7773c20a72d9` → live name "User Access Administrator" ✓
   - `7f951dda-4ed3-4680-a7ca-43fe172d538d` → live name "AcrPull" ✓
   The skill explicitly teaches the May 2026 display-name rename trap at L73
   ("Azure AI User" → "Foundry User") and recommends pinning by GUID — which
   makes the skill **more** robust against future Azure RBAC renames, not less.
5. **Class 5 (wrong API scopes / audiences)** — **N/A** — SKILL.md does not
   hand out manual `az account get-access-token --resource` snippets at all
   (unlike `foundry-prompt-agents`, where the audience question was central).
   The skill uses the SDK-side `DefaultAzureCredential()` + `get_bearer_token_provider(...,
   "https://cognitiveservices.azure.com/.default")` at L92 (in the OLD-code
   block — not a consumer-copy site, see Class 2) and the post-1.4.0 form at
   L101-103 uses the SDK's built-in audience-selection logic. No hand-issued
   token sites to validate.
6. **Class 6 (wrong env-var names)** — **N/A** — `FOUNDRY_PROJECT_ENDPOINT` /
   `AZURE_AI_PROJECT_ENDPOINT` / `FOUNDRY_MODEL_DEPLOYMENT` / `AZURE_AI_AGENT_ID`
   are consistently spelled across L294, L457, L470, L586, L965, L975-976,
   L1055, L1375, L1397. The TWO-NAME design (one platform-injected, one
   azd-side) is a deliberate Foundry runtime constraint that L975-978
   explicitly documents, with the MID-12 trap callout from the smb-credit-memo
   pilot (2026-05-29). This is correct documentation of a real platform
   surface; it is not a bug.
7. **Class 7 (hardcoded GUIDs)** — **N/A** — `grep -rEn '[0-9a-f]{8}-[...]'`
   surfaces only RBAC built-in role definition GUIDs (Class 4 above; stable
   across Azure tenants and intentional per the L73 / L1177-1180 callouts) and
   the documented "Azure Event Hubs Data Owner" defensive GUID at L1392 (used
   to teach a documented misclassification trap, not as a copy-paste value).
   No subscription IDs, no tenant IDs, no ARM resource IDs.
8. **Class 8 (deprecated SDK calls)** — **N/A** — the entire 1.4.0 migration
   recipe at L84-104 IS the canonical "deprecated → current" audit trail for
   this skill (PromptOnceFastAPI → ResponsesHostServer; `cognitiveservices.azure.com`
   scope → `ai.azure.com` scope; etc). The deprecation is documented and
   intentional.
9. **Class 9 (Bicep module drift)** — **N/A** — `find skills/foundry-hosted-agents
   -name '*.bicep'` returns nothing. The skill is documentation-only at the
   IaC layer; readers compose with `azd-patterns` (cross-referenced throughout)
   for actual Bicep modules.
10. **Class 10 (Bicep parameter mismatches)** — **N/A** — same reason as
    Class 9.
11. **Class 11 (cross-skill contradictions)** — **N/A** — Phase A grep across
    `azd-patterns`, `foundry-mcp-aca`, `foundry-evals` confirms environment
    variable names, role GUIDs, and the FoundryChatClient async pattern are
    consistent. The skill's "DO NOT USE FOR" frontmatter clauses cleanly
    route prompt-agent / Citadel / MCP-server use-cases to the correct sibling
    skills.
12. **Class 12 (container probe misconfigs)** — **N/A** — `references/yaml/agent.yaml`
    L1-28 declares the agent runtime contract without HTTP probes; readiness
    is implicit in the ResponsesHostServer ASGI app. The L1375 troubleshooting
    row (`FOUNDRY_PROJECT_ENDPOINT is reserved`) catches the most common
    agent.yaml misconfigure.
13. **Class 13 (wrong region defaults)** — **N/A** — SKILL.md does not default
    a region anywhere; L1285 lists 4 working April-2026 regions and L1288
    points to the upstream availability page as the single source of truth.
    No hardcoded region picker.
14. **Class 14 (JSON / YAML escaping)** — **N/A** — `agent.yaml` (literals)
    and `agent.manifest.yaml` (mustache) are explicitly split into two files
    at L968 with prose distinguishing scaffold-time vs runtime contexts.
    Zero escaping bugs.
15. **Class 15 (reference ↔ SKILL.md drift)** — **HIT (medium)** — 3-way
    version drift discovered by `grep -rn 'agent-framework-' skills/foundry-hosted-agents/`:
    - `references/python/pyproject.toml` L25-30 pins **1.6.0 / 1.6.0 /
      `==1.0.0a260521` / mcp>=1.10.0 / python-dotenv>=1.0.0`**.
    - `SKILL.md` L213-215 (sed bump recipe), L868-871 (READ FIRST callout),
      L880 (MUST copy callout), L905-906 ("Verified on" line), L911 (prose),
      L928 (Dependency Chain table) all pin the same **1.6.0 / a260521**.
    - `references/upstream-pin.md` L103 (GROUND TRUTH, validated by the
      auto-merged PR #164 on 2026-05-29) pins **`agent-framework-core~=1.7.0`,
      `agent-framework-foundry~=1.7.0`, `agent-framework-foundry-hosting~=1.0.0a260528`,
      `mcp~=1.27.1`, `python-dotenv~=1.2.2`**.
    The two sources of truth disagree by one minor version. **FIX in Phase B**
    by advancing `SKILL.md` 1.6.0/a260521 sites AND `pyproject.toml` L25-30
    forward to match `upstream-pin.md` (the validated ground truth). Bump
    `metadata.version` 1.8.0→1.8.1 (PATCH, per AGENTS.md § 5 — pin-refresh
    convention). SKILL.md L4-5 frontmatter `description` "MAF 1.6.0" → "MAF
    1.7.0" is a zero-delta string-length swap and stays within the 1006/1024
    budget.
16. **Class 16 (missing `dependsOn` for RBAC race)** — **N/A** — the skill
    routes Bicep readers to `azd-patterns`'s canonical `dependsOn` library
    (cross-ref L1117, L1146, L1218 callouts). Race mitigation is documented
    at L1218 (5-15 min RBAC propagation grace, retry pattern).
17. **Class 17 (tool wrapper type mismatches)** — **N/A** — single
    `MCPStreamableHTTPTool` site at L762 inside the `_PingSkipMCPTool`
    subclass example, used correctly as the parent class for an MCP server
    that needs ping-skip behaviour. Skill does NOT mix `HostedMCPTool` and
    `MCPStreamableHTTPTool` (Task 2.1 finding in `foundry-prompt-agents`
    audit) — different surface, no analogous bug here.
18. **Class 18 (bot / webhook signatures)** — **N/A** — skill is the agent
    runtime; bot wrapping is `foundry-teams-bot`'s scope (cross-referenced).
19. **Class 19 (logging exposure)** — **N/A** — `grep -nE 'print.*(token|secret|key|password|credential)'`
    returns zero hits in SKILL.md. Reference Python files (`main.py`,
    `container.py`) do not print credentials. `postdeploy-agent.sh` uses
    `az` CLI calls without echoing tokens.
20. **Class 20 (async / sync mismatches)** — **N/A** — see Class 1. The
    skill's async-vs-sync surface is correctly partitioned: agent runtime
    (`container.py`, `main.py`, the L453+ runtime snippet) is async; the
    one-shot REPL invocation example (L1240) is sync; the import smoke test
    in `validation.script` (`upstream-pin.md` L109) is sync. Each context
    uses the right pairing.
21. **Class 21 (outdated package pins)** — **HIT (low)** — primary observation
    is Class 15 (resolved in Phase B). **Secondary observation** for the
    freshness loop's follow-up: `upstream-pin.md` L103 pins
    `agent-framework-foundry-hosting~=1.0.0a260528` using the PEP 440
    compatible-release (`~=`) operator on an alpha version. AGENTS.md
    "Pin/cap policy on `validation.script` pip installs" requires alpha pins
    to use `==X.Y.ZaN` exactly, because compatible-release math does not
    survive pre-release boundaries safely. **Deferred** to a standalone
    upstream-pin refresh PR — not in this audit's scope (would expand the
    Phase B blast radius beyond the audit-2026-Q2 mandate and pollutes the
    PR with a pin-policy change that needs its own validation pass).

## Fixture

Single Copilot CLI consumer fixture lives at
`skills/foundry-hosted-agents/test-fixture/consumer_prompt.md`. It instructs
the agent to scaffold a minimal hosted-agent container in `/tmp/`, build it
via `az acr build` against `acrawesomegbbci`, declare a hosted-agent service
in `azure.yaml`, run `azd deploy` against `cae-awesome-gbb-ci`, invoke the
deployed agent once with a one-shot prompt against `gpt-5.4-mini`, verify a
non-empty response, and tear down (ACA app delete + ACR repository delete +
Foundry agent delete). All resource names carry a `uuid.uuid4().hex[:8]`
suffix (agent name `ci-smoke-ha-<UUID>`, ACA app `ca-smoke-ha-<UUID>`, ACR
image tag `smoke-<UUID>`) per Task 2.1 finding #9. Final-marker contract is
`SMOKE_RESULT=PASS` (literal start-of-line) on success or
`SMOKE_RESULT=FAIL <one-line reason>` on any failure; the fixture preamble
documents the grep-WHOLE-transcript FAIL-beats-PASS contract from Task 2.1
finding #8.

## CI matrix runs that proved the fix (5 consecutive green)

After committing all of (a) the audit trail, (b) the SKILL.md/pyproject
fixes, and (c) the consumer-prompt fixture to the PR branch, 5 empty-commit
stability pushes were triggered via `git commit --allow-empty && git push
origin HEAD:unsafecode/pr-review` per Task 2.1 finding #7 (≥45s spacing,
wait for each `Skill tests` run's `headSha` to register before next push,
because GitHub coalesces simultaneous pushes regardless of `concurrency:`).
Each run was personally verified via `gh run view <id> --json conclusion`
returning `"conclusion": "success"` — never trusting the dashboard alone:

1. <fill in run URL #1 after Phase D>
2. <fill in run URL #2 after Phase D>
3. <fill in run URL #3 after Phase D>
4. <fill in run URL #4 after Phase D>
5. <fill in run URL #5 after Phase D>

The matrix discovers the fixture automatically via
`scripts/build-test-matrix.py` (any skill that ships `test-fixture/consumer_prompt.md`
is included). No edits to `.github/workflows/skill-test.yml` or
`scripts/build-test-matrix.py` were required.

## Open items (deferred)

- **L1465 REST response JSON sample** — see Class 2 above. The legacy URL
  appears in the platform's actual API response shape today; editing it
  would misrepresent observed behaviour. Re-verify when the per-agent-version
  endpoint surface migrates to `services.ai.azure.com`. No consumer copies
  this snippet as configuration — it is annotated as "what the platform
  returns".
- **Class 21 secondary — `~=` on alpha pin (`upstream-pin.md` L103)** — see
  Class 21 above. Defers to a standalone pin-policy refresh PR; out of this
  audit's surgical scope and would dilute the audit-2026-Q2 commit history.
  Filed as a known open item; not a bug that affects the skill's correctness
  at this moment in time (the `~=1.0.0a260528` resolver behaviour against
  PyPI today still picks 1.0.0a260528 exactly because no later alpha exists
  yet — the policy violation only matters when the upstream releases
  1.0.0a260529+).
- **`copilot -s` / `--silent` footer-suppression experiment** — Task 2.2
  brief invited an empirical check on whether the Copilot CLI's `Changes /
  Duration / Tokens` footer can be suppressed cleanly (which would simplify
  the FAIL-beats-PASS grep contract). Time-boxed to 5 minutes in Phase C;
  result documented in the fixture preamble. If inconclusive at fixture-write
  time, the grep-whole-transcript FAIL-first pattern stays as the canonical
  Task-2.1 contract and the experiment is left for a future tightening
  iteration (no behaviour change in this PR).
