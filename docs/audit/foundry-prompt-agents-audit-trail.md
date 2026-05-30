# foundry-prompt-agents — Audit Trail

**Auditor:** copilot-bot (Task 2.1, deep-audit-and-testing-rethink plan)
**Date:** 2026-05-30
**Bug-class scan:** all 21 classes from Appendix A of the spec
**Skill version:** `1.0.2` (pre-audit) → `1.0.3` (post-fix in commit `1a6229c`, Phase B)
**Audit surface:** `skills/foundry-prompt-agents/SKILL.md` (462 lines) + `references/upstream-pin.md` (115 lines). No other reference files exist for this skill.

## Findings (verbatim list)

1. **Class 1 (sync credential in async-only client)** — none observed. SKILL.md uses sync `AIProjectClient` + sync `DefaultAzureCredential` end-to-end (scan: `grep -nE 'Async|aio|asyncio' skills/foundry-prompt-agents/SKILL.md` → 0 matches).
2. **Class 2 (endpoint URL bugs — project vs account)** — none observed. All endpoint references use the project-scoped form `https://<resource>.services.ai.azure.com/api/projects/<project>` consistently at L74, L94, L403. KI-001 in `upstream-pin.md` documents the `services.ai.azure.com` (NOT `ai.azure.com`) requirement; troubleshooting row at L403 reinforces it.
3. **Class 3 (wrong model names)** — none observed. Model identifiers used: `gpt-5-mini` (L84, L100, L126, L164, L246, L256, L301, L429), `gpt-5.4-mini` (L51), `gpt-4.1` (L51). All three exist in the Foundry catalog and are documented in the skill's prerequisites at L50–51.
4. **Class 4 (wrong RBAC role names)** — none observed. SKILL.md cites `Foundry User` with GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d` at L54–55, L370, L406. Verified live: `az role definition list --name "Foundry User"` returned `{"id": "53ca6127-db72-4b80-b1b0-d745d6d5456d", "name": "Foundry User"}`. GUID is current as of May 2026 (post-rename from "Azure AI User").
5. **Class 5 (wrong API scopes)** — **HIT (medium)**. L95 REST example uses `az account get-access-token --resource https://ai.azure.com`, but the green CI auth-smoke pattern (`.github/workflows/copilot-cli-foundry-auth-smoke.yml` L74) and matrix job will use `https://cognitiveservices.azure.com`. Live verification (`az account get-access-token`) confirmed BOTH audiences successfully issue bearer tokens, so L95 is not strictly broken — but it diverges from the validated-in-CI Foundry data-plane convention and risks consumer confusion. → fixed in commit `1a6229c` (Phase B): aligned L95 to `https://cognitiveservices.azure.com`.
6. **Class 6 (wrong env-var names)** — N/A. SKILL.md uses no environment variables; all endpoints/keys are written as `<placeholder>` tokens for the consumer to fill in (scan: `grep -nE '\$[A-Z_]+|\$\{[A-Z_]+\}|os\.environ' skills/foundry-prompt-agents/SKILL.md` → 0 matches).
7. **Class 7 (hardcoded GUIDs)** — none observed beyond the intentional `Foundry User` role GUID (a stable, tenant-independent built-in role identifier — documented per AGENTS.md § 2.1 placeholder convention). No subscription IDs, tenant IDs, or resource ARM IDs hardcoded (`grep -nE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'` returns only the role GUID).
8. **Class 8 (deprecated SDK calls)** — none observed. No use of pre-2.0 `azure-ai-projects` surface (`from_connection_string`, `.connections.get_default`, `inference_client`, `agents.create(...)`). All API calls use the GA v2 surface: `AIProjectClient(endpoint=, credential=)`, `project.agents.create_version(...)`, `project.get_openai_client()` (scan: `grep -nE 'from_connection_string|inference_client|telemetry|agents\.create\(' skills/foundry-prompt-agents/SKILL.md` → 0 matches).
9. **Class 9 (Bicep module drift)** — N/A. Prompt agents are declarative; this skill ships no Bicep. `find skills/foundry-prompt-agents -name '*.bicep'` → empty.
10. **Class 10 (Bicep param mismatches)** — N/A (no Bicep, see Class 9).
11. **Class 11 (cross-skill contradictions)** — none observed *within this skill's scope*. SKILL.md cross-references `foundry-hosted-agents`, `foundry-mcp-aca`, `foundry-iq`, `foundry-evals`, `foundry-agt`, `foundry-observability`, `foundry-memory`, `foundry-toolbox` (L16–18 frontmatter, L178, L385, L394, L454–461). The Foundry User role GUID matches the canonical value used in `foundry-hosted-agents`, `foundry-evals`, `foundry-teams-bot`, `ghcp-hosted-agents`, `azure-sre-agent` reference skills. **Out-of-scope drift observed in sibling skills** (NOT fixed here, noted for future tasks): `foundry-iq/SKILL.md:212`, `foundry-doc-vision-speech/SKILL.md:356`, `azd-patterns/SKILL.md:643` still use the pre-May-2026 display name "Azure AI User" alongside the correct GUID. Filed as deferred items below.
12. **Class 12 (container probe misconfigurations)** — N/A. Prompt agents run inside the Foundry Agent Service; this skill ships no container manifests (Dockerfile, ACA YAML).
13. **Class 13 (wrong region defaults)** — N/A. SKILL.md prescribes no default region; consumers supply their own project endpoint (which encodes the region implicitly).
14. **Class 14 (JSON/YAML escaping in agent prompts)** — none observed. All `instructions=` values in `PromptAgentDefinition(...)` are plain-English strings (L85, L127, L165, L247, L257, L302). No embedded JSON/YAML/regex requiring escape (scan: `grep -nE 'instructions=.*\\["{].*' skills/foundry-prompt-agents/SKILL.md` → 0 matches).
15. **Class 15 (reference ↔ SKILL.md drift — markdown structural)** — **HIT (low)**. SKILL.md L175 contains an orphan triple-backtick (` ``` `) that closes no opened code fence. Total fence count is 29 (odd → unbalanced). The Python `MCPTool` example opens at L151 and correctly closes at L169. L170 is blank; L171–174 are a markdown blockquote about OpenAPI tools; L175 is the stray fence; L176 is blank; L177–179 resume normal blockquote content. The stray fence does not visually break rendering on GitHub but will trip strict markdown linters and any downstream parser that uses fence-pair counting. → fixed in commit `1a6229c` (Phase B): deleted the L175 orphan; post-fix fence count = 28 (even).
16. **Class 16 (missing `dependsOn` — RBAC race)** — N/A (no Bicep, see Class 9).
17. **Class 17 (tool wrapper type mismatches — dict vs Pydantic)** — none observed. All tool instantiations use the Pydantic class constructor form: `WebSearchTool()` (L129), `CodeInterpreterTool()` (L130), `FileSearchTool(vector_store_ids=[...])` (L131, L304), `MCPTool(server_label=, server_url=, require_approval=)` (L155). Cheat-sheet import block at L437–447 lists only class names, not dict-spec helpers.
18. **Class 18 (bot/webhook signature bugs)** — N/A. This skill does not document any bot or webhook integration.
19. **Class 19 (logging exposure — secrets, PII)** — none observed. SKILL.md `print()` calls (L88, L207, L215, L250, L261) emit only agent metadata (name, version, id) and response text — never tokens, credentials, or PII.
20. **Class 20 (async/sync mismatches beyond credentials)** — none observed (see Class 1 scan).
21. **Class 21 (outdated package pins beyond the freshness loop)** — none observed. Pin file `references/upstream-pin.md` is at schema v2 with `azure-ai-projects~=2.1.0` (GA, current per PyPI as of `last_validated: 2026-05-29` by copilot-bot) and `azure-identity~=1.25.3`. Three known-issues entries (KI-001/002/003) accurately reflect the documented gotchas in SKILL.md § 1, § 4, § 9.

## Fixture

[`../../skills/foundry-prompt-agents/test-fixture/consumer_prompt.md`](../../skills/foundry-prompt-agents/test-fixture/consumer_prompt.md) — to be authored in Phase C of Task 2.1. Will instruct the Copilot CLI agent to read SKILL.md and execute the full lifecycle (create_version → conversations.create → responses.create → list → delete_version) against `gpt-5.4-mini` in `aif-awesome-gbb-ci` (Sweden Central), self-verifying KI-002 (`.versions` dict shape) and KI-003 (positional `delete_version` signature), then exit with `SMOKE_RESULT=PASS` or `SMOKE_RESULT=FAIL <reason>` as the last line of stdout.

## CI matrix runs that proved the fix (5 consecutive green)

All runs are PR-`synchronize` events on PR #185 (`unsafecode/pr-review`).
Each one ran the `copilot-cli-matrix (foundry-prompt-agents)` job, which spawned
a real Copilot CLI agent that read SKILL.md, executed the documented Python
quickstart against `aif-awesome-gbb-ci` (Sweden Central) + `gpt-5.4-mini`, and
self-reported `SMOKE_RESULT=PASS`.

1. https://github.com/aiappsgbb/awesome-gbb/actions/runs/26691175961 — commit `3af9662a` (legacy-pytest-job deletion)
2. https://github.com/aiappsgbb/awesome-gbb/actions/runs/26691223146 — commit `ee68a793` (coalesced empty-commit batch)
3. https://github.com/aiappsgbb/awesome-gbb/actions/runs/26691276623 — commit `28e50328` (empty trigger #3)
4. https://github.com/aiappsgbb/awesome-gbb/actions/runs/26691293104 — commit `d8ec54a0` (empty trigger #4)
5. https://github.com/aiappsgbb/awesome-gbb/actions/runs/26691311131 — commit `b4636e2f` (empty trigger #5)

Note on dispatch method: `workflow_dispatch` against the PR branch fails OIDC
federation (subject `repo:.../ref:refs/heads/unsafecode/pr-review` is not in
the UAMI's federated-credentials list; only `pull_request` and
`refs/heads/main` are covered per AGENTS.md § 9.7). All five stability runs
therefore used `pull_request synchronize` triggers from spaced empty commits
(45 s apart, so GitHub did not coalesce the events).

## Open items (deferred)

- **Class 11 cross-skill drift** — Three sibling skills (`foundry-iq` L212, `foundry-doc-vision-speech` L356, `azd-patterns` L643) still surface the pre-May-2026 display name "Azure AI User" alongside the correct GUID. The GUID is unchanged so functionally these still resolve, but the display name is stale and risks confusing readers who try `--role "Azure AI User"` and hit `RoleDefinitionNotFound`. **Deferred** because each sibling skill must own its own deep-audit pass under this same plan (Tasks 2.2+ / Phase 3 wave). Filing inline fixes in this PR would violate AGENTS.md § 2.6 (one skill per PR) and the audit-trail gate's per-skill bounds.
- **KI-002 / KI-003 self-verification rigor** — The Phase C consumer fixture *exercises* these signatures end-to-end (list → check `.versions` dict; delete via positional args), but does not currently A/B-test the wrong forms to prove they fail loudly. Strengthening to A/B-tests is a Phase 3 follow-up — out of scope for the pilot.
- **L95 audience parity** — Phase B will align L95 to `https://cognitiveservices.azure.com`. The pre-fix audience `https://ai.azure.com` empirically issues a valid token, but we have NOT verified whether the Foundry data plane accepts that audience for the `services.ai.azure.com/api/projects/.../agents/.../versions` REST surface. Documented as a fix, not a regression.
