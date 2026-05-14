---
name: compose-org
description: >
  Fork an agentic substrate into a customer-flavoured digital clone
  using an org-brief YAML (from research-company) + the matching
  industry primer. Clones the substrate to a sibling repo, rebrands
  literal tokens, repacks the data-fabric generators against the
  brief's subsidiaries + named ELT, swaps the Kuzu entity-kind
  tables per the primer, extends the domain registry with the
  primer's workflow library, generates personae (ELT named from the
  brief, archetypes from the primer), seeds cadenced rituals +
  narrative arcs, and scaffolds Node MCP mocks for the brief's stack
  overrides. Local-only fork by default; no GitHub push. Refuses
  dirty trees, idempotent re-runnable.
  USE FOR: fork the substrate for a named customer (Telco, FSI,
  Airline, Retail, OEM, …), produce a digital-clone-grade demo repo.
  DO NOT USE FOR: incrementally adding one domain (use compose-domain
  inside the fork), authoring a new substrate from scratch, pitch
  decks.
metadata:
  version: "1.0.0"
---

# compose-org

Fork the agentic substrate into a **customer-flavoured digital
clone** by joining a thin org-brief with the matching industry
primer.

```
research-company  →  briefs/<slug>-org-brief.yaml
                                  ↓
                  industry-primers/<vertical>.md
                                  ↓
                          compose-org (this skill)
                                  ↓
                  <substrate>-<slug>/  (local fork)
                                  ↓
                          make up  (operator)
```

## When to use

Invoke after `research-company` has produced an org-brief whose
`meta.status` is `ready` and whose `meta.primer` points at an
existing industry primer.

## Inputs

1. **Brief path** — absolute path or path relative to cwd to the
   org-brief produced by `research-company` (e.g.
   `briefs/<slug>-org-brief.yaml` if you ran the catalog-clone flow,
   or `<cwd>/briefs/<slug>-org-brief.yaml` if you ran the
   remote-bootstrap flow per RUNBOOK.md).
2. **Substrate source** (optional) — one of:
   - A **local path** to an existing substrate clone (e.g.
     `../zava-control-plane`).
   - A **git URL** to clone from (e.g.
     `https://github.com/arturcrmbot/zava-control-plane`).
   - **Omitted** — defaults to cloning from
     `https://github.com/arturcrmbot/zava-control-plane`.
3. **Fork target path** (optional) — where to write the fork.
   Defaults to `<cwd>/zava-control-plane-<slug>` (a sibling of the
   `briefs/` directory inside cwd).

## Output

A new local git repo at the fork-target path containing the rebranded
+ customised substrate. **No GitHub remote** is configured. Operator
runs `gh repo create` later if they want to push.

## Pre-flight (refuse to proceed if any fail)

| Check | Failure mode |
|---|---|
| Brief file exists and parses as YAML | Stop; ask operator. |
| `brief.meta.status == ready` | Stop; tell operator to sign off the brief first. |
| `brief.meta.primer` resolves to an existing primer | Stop; offer to graduate a stub primer or pick a different vertical. |
| Substrate source available — either the supplied local path is a clean git tree on default branch, OR the supplied/default URL is reachable via `git ls-remote` | Stop; refuse to clone from a dirty state or a network failure. |
| Fork target path does not already exist | Stop. To re-run, the operator removes the target dir first (or uses `--allow-overwrite` flag explicitly — see § "Idempotent re-runs"). |
| `git`, `python3 ≥ 3.11`, `node ≥ 20`, `npm` available | Stop; install hint per missing tool. |

## Substrate paths (Zava control plane reference)

The skill assumes the target substrate follows the
[`zava-control-plane`](https://github.com/arturcrmbot/zava-control-plane)
layout. The phases below reference these paths verbatim. If you fork
this skill for a different substrate, update the path table here.

| Concept | Path in substrate |
|---|---|
| Subsidiary seed list | `api/server/data_fabric/employee_gen.py` (`SUBSIDIARIES` tuple) |
| Client/Brand generator | `api/server/data_fabric/client_brand_gen.py` |
| Cadenced rituals seed | `api/server/data_fabric/cadenced_rituals.py` |
| Narrative arcs seed | `api/server/data_fabric/narrative_arcs.py` |
| Kuzu entity schema | `api/server/services/entity_graph.py` |
| Function registry | `api/shared/functions.py` |
| Persona registry | `api/shared/personas.py` + `api/server/personae/<role>/` |
| Domain registry | `api/shared/domains.py` |
| Node mocks | `mocks/<id>/` |
| Rebrand playbook | `plan/archive/refactor-rebrand-zava-1.md` |

## The ten phases

### Phase 0 — Pre-flight

Run every check in the table above. Print a green/red summary. Stop
on any red.

### Phase A — Acquire the substrate

Either clone fresh from a git URL, or copy from a local path,
depending on what was supplied:

```bash
# Default — fresh clone from the public substrate repo
git clone https://github.com/arturcrmbot/zava-control-plane <fork-target>

# OR — if a local substrate path was supplied
git clone <local-substrate-path> <fork-target>

cd <fork-target>
git remote remove origin            # no remote — local-only
git checkout -b main                # ensure clean main
```

Phase A always re-points `origin` to nothing — the fork is
local-only by default. The operator runs `gh repo create` later
if they want to push.

### Phase B — Rebrand (literal find-and-replace)

The substrate already ships a rebrand playbook —
[`plan/archive/refactor-rebrand-zava-1.md`](../../zava-control-plane/plan/archive/refactor-rebrand-zava-1.md) —
that documents every literal token to swap. Follow it verbatim with
the mappings derived from the brief:

| Old token | New token (derived from brief) |
|---|---|
| `Zava Control Plane` | `<brief.identity.short_name> Control Plane` |
| `zava-control-plane` | `zava-control-plane-<brief.identity.slug>` |
| `Zava ` (literal, with trailing space) | `<brief.identity.short_name> ` |
| `Zava-` | `<brief.identity.short_name>-` |
| `zava.skill`, `zava.tool.*`, `zava.fleet_manager.*` | `<brief.identity.slug>.skill`, `<brief.identity.slug>.tool.*`, `<brief.identity.slug>.fleet_manager.*` |
| `Zava` (standalone, last) | `<brief.identity.short_name>` |

**Tight allowlist of file extensions:** `.md`, `.py`, `.ts`, `.tsx`,
`.js`, `.jsx`, `.yml`, `.yaml`, `.json`, `.toml`, `.sh`, `.css`,
`.html`, `Dockerfile`, `Makefile`.

**Forbidden paths** — never edit (would corrupt binary assets or
break tests with cosmetic changes): `**/*.png`, `**/*.jpg`,
`**/*.avif`, `**/*.svg`, `**/*.mp4`, `**/azurite-data/**`,
`**/data/portal/**/*.kuzu`, `**/data/.eval/**`, `**/__pycache__/**`,
`**/.venv/**`, `**/node_modules/**`, `**/.git/**`.

Commit the rebrand as one atomic commit:
`chore: literal rebrand <substrate> → <substrate>-<slug>`.

### Phase C — Repack the data fabric

#### C.1 — `SUBSIDIARIES` tuple

Replace the `SUBSIDIARIES` tuple at the top of
`api/server/data_fabric/employee_gen.py` with rows derived from
`brief.subsidiaries[]`. Format (per existing convention):

```python
SUBSIDIARIES: tuple[str, ...] = (
    # one entry per brief.subsidiaries[].name
    "<Subsidiary 1 name>",
    "<Subsidiary 2 name>",
    ...
)
```

If the brief has fewer than 5 subsidiaries, pad with placeholder
opcos drawn from the primer's regulator countries (e.g.
`<short_name> Singapore Pte Ltd`) to keep the substrate's data-volume
expectations intact.

#### C.2 — Client/Brand generator

Replace `api/server/data_fabric/client_brand_gen.py` with the
primer's vertical-equivalent. For telco, that means generating
`Customer` rows (enterprise accounts) and `Service` SKUs instead of
`Client` rows and `Brand` rows. Seed customer names from
`brief.customers_or_segments`; seed Service catalogue from the
primer's typical Service list.

The function signature `generate_clients_and_brands(...)` stays the
same (callers in `pack.py` don't change); only the implementation
swaps. Add a one-line module docstring noting the source primer.

#### C.3 — Cadenced rituals seed

Append to `api/server/data_fabric/cadenced_rituals.py` one row per
ritual in the primer's "Canonical cadenced rituals" table. The
substrate's ritual schema is `{id, display_name, cadence,
owner_function}` — read the file's existing format and match.

#### C.4 — Narrative arcs seed

Append to `api/server/data_fabric/narrative_arcs.py` one row per
`brief.strategic_themes[]`. The substrate's narrative-arc schema is
`{id, headline, summary, function_focus, timeline_hint}`.

### Phase D — Schema swap (Kuzu entity kinds)

Edit `api/server/services/entity_graph.py` to:

1. **Rename** the agency-specific node tables per the primer's
   "Canonical vertical entity kinds" table. Telco mapping:
   - `Brand` → `Service`
   - `Campaign` → `Circuit`
   - `Pitch` → `Quote`
   - `MediaPlan` → `CapacityPlan`
2. **Add** the new-kind tables the primer introduces (telco:
   `Site`, `PointOfPresence`, `Customer`, `Incident`, `Ticket`,
   `NetworkElement`, `IPPrefix`, `BGPPeering`, `CrossConnect`,
   `Licence`, `Spectrum`).
3. **Update** the projection mapping in
   `api/server/services/entity_projections.py` so existing code
   that wrote to `Brand` now writes to `Service`, etc. Mechanical
   find-and-replace inside that file ONLY.

> Respect the stored Kuzu schema-syntax constraints — inline
> `LIMIT` ints, backtick reserved words, trailing
> `PRIMARY KEY (id)`, no `SET n += $map`.

### Phase E — Functions & personae

#### E.1 — Function registry

Replace `api/shared/functions.py` with rows derived from the
primer's "Canonical functions" table. Each function gets:

```python
Function(
    id="<id>",
    display_name="<display_name>",
    importance="<hero|core|support>",
)
```

#### E.2 — Persona folders

For each row in `brief.leadership[]`, ensure a folder exists at
`api/server/personae/<role>/` with a `SKILL.md` whose frontmatter
includes the real name + title + function from the brief. If the
folder already exists in the substrate (e.g. `ceo`, `cfo`, `coo`),
**edit** the frontmatter — don't overwrite the persona logic.

For each persona archetype in the primer's "Org chart archetypes"
section that does NOT correspond to a brief-named leader, generate
a folder at `api/server/personae/<id>/` with a stub `SKILL.md`. The
`decision_policy` block can be a minimal default; archetype names
get expanded by faker in `employee_gen.py` at boot.

Update `api/shared/personas.py` to register every new persona.

### Phase F — Domain composition

Append rows to `api/shared/domains.py` for each entry in the
primer's "Proposed-domains starter library". Use the substrate's
`Domain(...)` constructor signature verbatim:

```python
Domain(
    workflow_type="<workflow_type>",
    display_name="<display_name>",
    workflow_id_prefix="<UPPER-PREFIX>-",
    orchestrator_name="<PascalCase>Orchestrator",
    operator_surface="...",
    phases=(...),
    hitl_gates=(...),
    skills=(...),
    function="<function-id>",
    realistic_interval_seconds=<int>,
    stub=True,    # all new domains start as stubs
),
```

Mark every newly-added domain as `stub=True` — the operator
graduates them one at a time via `compose-domain` inside the new
fork. **Do not generate orchestrator files / graphs / skills here.**
That's compose-domain's job.

Tag each new domain with the brief's strategic-theme overrides:
domains whose function is in any `brief.strategic_themes[].function_focus[]`
get `importance: hero`; the rest `importance: supporting` (subject
to ≤ 3 hero cap).

### Phase G — Stack mocks

For each row in `brief.stack_overrides[]`, scaffold a Node mock
under `mocks/<id>/`:

- `mocks/<id>/server.ts` — minimal FastMCP-style mock, ~80 lines,
  copies the shape of an existing mock under `mocks/` (e.g.
  `workday`, `concur`).
- `mocks/<id>/package.json` — one entry in `mocks/<id>/package.json`
  referencing the same parent deps as existing mocks.
- Port assignment: next free port in the 4200–4299 range (read
  existing mocks/* to find used ports).

Generic Zava mocks (workday, concur, etc.) stay in place — the
overrides are additive, not replacing.

### Phase H — Re-seed the data fabric

Run the substrate's snapshot regeneration:

```bash
cd <fork-target>
make funcvenv         # one-time, Windows-friendly
uv sync
python -m api.server.data_fabric.pack --regenerate-snapshot
```

This rebuilds the Kuzu snapshot under `data/snapshots/` so a
cold-start `make up` reads the new entity-kind tables + new
subsidiaries.

### Phase I — Smoke test

```bash
make test            # substrate's existing test suite
```

If anything fails:

- **Test failures referencing literal `Zava` strings** — incomplete
  rebrand; re-run Phase B with the failed-test paths added to the
  allowlist.
- **Kuzu schema errors** — Phase D mistake; check primer's relations
  list and the substrate's `_VALID_RELS`.
- **Persona registry mismatch** — Phase E.2 missed a row; cross-check
  `personas.py` against `api/server/personae/` folder list.

Do NOT proceed to hand-off with red tests. Fixes are a tight loop
between the agent and the operator.

### Phase J — Hand off

Print to operator:

```
✅ Fork ready: <fork-target>

   git log --oneline       # one rebrand commit + N compose commits
   cd <fork-target>
   make up                 # boots Azurite, mocks, FastAPI, control-plane UI

   Visit http://localhost:5273 (control plane)
        http://localhost:5275 (blueprint microsite)

   To promote a stub domain to live:
     copilot
     > Run compose-domain on `<workflow_type>` (inside this fork)

   To push to GitHub later:
     gh repo create zava-control-plane-<slug> --private
     git remote add origin <url>
     git push -u origin main
```

## Idempotent re-runs

Re-running compose-org against an existing fork target is supported
via `--allow-overwrite`. The skill:

1. Checks the existing fork's `git status` is clean.
2. Discards uncommitted changes only if the operator confirms.
3. Re-applies every phase as if from a fresh clone.

If the operator has hand-edited the fork, the safest path is to
delete the fork dir and re-run from scratch — the brief is the
source of truth.

## Safety rails

- **No `gh repo create` automatic push.** Forks are local-only by
  default; pushing to GitHub is an explicit operator action.
- **Rebrand allowlist is tight.** Binary assets, `.git/`,
  `node_modules/`, `.venv/`, `azurite-data/`, `data/.eval/` are
  never edited.
- **No `.png` / `.mp4` / avatar regeneration.** Demo media is
  intentionally inherited — the rebrand is text-only.
- **Refuses to overwrite without explicit flag.** First failure mode
  for accidentally re-running is a no-op.
- **Per-phase commit boundaries.** Every phase commits atomically
  so `git revert <sha>` rolls back one phase cleanly.

## Output budget

A first-run compose-org against a Tier-1 vertical produces:

- ~30–40 commits
- ~150–250 files modified by the rebrand
- ~10–15 new files (mocks, persona folders)
- ~5,000–10,000 lines of diff total

If diff exceeds 20,000 lines, the rebrand allowlist is probably too
broad — re-check the forbidden-paths list.

## Iterating the skill

When a generated fork looks wrong:

- Per-phase issues: **fix the phase prose in this SKILL.md**, then
  re-run with `--allow-overwrite`.
- Primer issues: **fix the matching primer file**, then re-run.
- Brief issues: **fix the brief**, re-run.

Two runs against the same brief + primer should diff to nothing
meaningful except commit timestamps.

## Downstream

After compose-org finishes, the operator's typical next steps:

1. **Verify** — `make up`, walk the control plane UI, confirm domain
   names, persona names, KPIs match expectations.
2. **Graduate a stub domain** — pick a hero domain (e.g.
   `quote-to-circuit` for telco) and run `compose-domain` on it
   inside the new fork. That fleshes out orchestrator / phase graphs
   / agent skills / personae.
3. **Demo prep** — boot, time-warp scrub, capture a 30-min
   walkthrough.
