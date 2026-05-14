# compose-org

Fork an agentic-substrate repo into a customer-flavoured digital
clone, driven by an org-brief (produced by `research-company`)
paired with the matching industry primer.

See [`SKILL.md`](SKILL.md) for the canonical procedure.

## Pipeline position

```
┌───────────────────┐    ┌────────────────────┐    ┌──────────────────┐
│ research-company  │ →  │   compose-org      │ →  │  <substrate>-    │
│ (profile target)  │    │   (this skill)     │    │   <slug>/        │
│                   │    │                    │    │  (local fork)    │
│ briefs/<slug>-    │    │ + industry primer  │    │                  │
│   org-brief.yaml  │    │                    │    │  make up         │
└───────────────────┘    └────────────────────┘    └──────────────────┘
```

## Files

| File | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | The ten-phase procedure. Strict frontmatter (≤1024 char description, semver). |
| `references/` | (Reserved for future per-substrate path tables. Today the substrate paths are inlined in SKILL.md.) |

## What it does

1. **Pre-flight** — validate brief, find primer, check substrate
   path is clean, refuse if fork target exists.
2. **Clone** — `git clone <substrate>` → `<substrate>-<slug>` (no
   GitHub remote configured).
3. **Rebrand** — literal find-and-replace per the substrate's own
   rebrand playbook, with a tight file-extension allowlist.
4. **Data fabric repack** — `SUBSIDIARIES`, client/brand generator,
   cadenced rituals, narrative arcs, all derived from brief + primer.
5. **Kuzu schema swap** — rename `Brand`/`Campaign`/`Pitch`/
   `MediaPlan` tables to the primer's vertical equivalents; add
   new-kind tables.
6. **Functions & personae** — replace `functions.py` per primer;
   ensure persona folders exist for every brief-named ELT and every
   primer archetype.
7. **Domain composition** — extend `domains.py` with the primer's
   25+ proposed-domain library (all marked `stub=True`).
8. **Stack mocks** — scaffold one Node MCP mock per stack override
   in the brief.
9. **Re-seed** — regenerate the Kuzu snapshot under
   `data/snapshots/`.
10. **Smoke test + hand off** — `make test`; print operator's next
    steps.

## What it does NOT do

- **Push to GitHub.** Forks are local-only by default; operator
  runs `gh repo create` later if wanted.
- **Generate orchestrator/graphs/skills for new domains.** Those
  are `compose-domain`'s job — invoked inside the new fork to
  graduate stub domains one at a time.
- **Regenerate demo media** (avatars, recordings). The rebrand is
  text-only.
- **Mass-edit private engagement notes.** Briefs in `briefs/` are
  read; nothing under there is mutated.

## Output

A new local git repo at `<substrate-parent>/<substrate>-<slug>/`
containing the rebranded + customised substrate. Roughly:

- ~30–40 atomic commits (one per phase, optionally per sub-step)
- ~150–250 files modified by the rebrand
- ~10–15 new files (mocks, persona folders)
- ~5,000–10,000 lines of diff

After `compose-org` finishes, the operator runs `make up` in the
new fork to boot it.

## Changelog

- **1.0.0** — Initial version. Ten-phase procedure, tight rebrand
  allowlist, idempotent re-run support, per-phase commit boundaries.
