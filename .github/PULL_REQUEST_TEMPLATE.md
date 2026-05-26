## Summary

<!-- Brief description of what this PR does. -->

## Skills touched

<!-- List each skill affected, with the version bump category. -->

- `skill-name`: X.Y.Z → X.Y.Z+1 (PATCH / MINOR / MAJOR)

## Testing

<!-- Check the highest tier you completed. Each tier subsumes the ones below. -->

- [ ] **T0 — Lint**: `python3 scripts/validate-skills.py` passes
- [ ] **T1 — Pin validation**: `validation.script` runs, expected output present
- [ ] **T2 — Import smoke**: verified imports in code samples against installed SDK
- [ ] **T3 — Deploy & invoke**: deployed agent/resource, invoked, verified response

<!-- For T2/T3, briefly describe what you tested: -->

**Test details:**


## Breaking changes

- [ ] This PR introduces no breaking changes
- [ ] This PR introduces breaking changes (describe below)

<!-- If breaking: what changed, what consumers need to do -->

## Checklist

- [ ] YAML frontmatter parses on all touched SKILL.md files
- [ ] Description ≤ 1024 chars on all touched SKILL.md files
- [ ] No customer / PoC / private-repo names introduced
- [ ] `metadata.version` bumped per [AGENTS.md § 5](AGENTS.md#5--versioning-metadataversion)
- [ ] Docs site rebuilt (`python3 scripts/build-site.py --out docs/`)
