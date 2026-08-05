# Plan: foundry-mcp-aca refresh 1.2.4

**Design:** [specs/foundry-mcp-aca-refresh-1.2.4.md](../specs/foundry-mcp-aca-refresh-1.2.4.md)
**Status:** Complete

## Steps

1. **Pin script validation** — add `mcp~=1.29.0` explicit install, importlib.metadata version assertion, JobsOperations.get/begin_create_or_update method assertions, new expected_output markers
2. **KI-001 expansion** — broaden to cover coordinated fastmcp 3.x + mcp 2.0 migration hold
3. **SKILL.md agnostic rewrites** — remove engagement-specific phrases (pilot-grade, fresh PoC, Threadlight pilots, pilot forensics)
4. **SemVer** — 1.2.3 → 1.2.4 (PATCH per AGENTS.md §5)
5. **Fixture: azd up conversion** — replace `az acr build` + `azd provision` with `azd up`; add placeholder image default to Bicep
6. **Fixture: MCP session conformance** — capture `mcp-session-id` from initialize response headers, replay for tools/list and tools/call
7. **Fixture: tools/call** — add nontrivial tools/call exercising search_orders_filtered and asserting non-empty result.content
8. **Local validation** — validate-skills.py, build-plugins.py --check, pin validation, build-site.py
9. **Push + CI** — exact-head copilot-cli-matrix green
10. **Update PR body** — factual evidence with run/job IDs

## Files changed

- `skills/foundry-mcp-aca/SKILL.md` — version bump + agnostic rewrites
- `skills/foundry-mcp-aca/references/upstream-pin.md` — pin script + KI-001 expansion
- `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` — azd up + session-id + tools/call
- `docs/superpowers/specs/foundry-mcp-aca-refresh-1.2.4.md` — this design
- `docs/superpowers/plans/foundry-mcp-aca-refresh-1.2.4.md` — this plan
- `docs/` — rebuilt static site
