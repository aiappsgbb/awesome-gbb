---
name: threadlight-workspace-ui
description: >
  Generate a curated, framework-agnostic workspace UI reference for a
  threadlight process — case-list / inbox / dashboard / console / kanban /
  map shape with detail pane, action toolbar, audit viewer. Reads spec
  § 8b Human Interaction (Workspace UX) and produces ONE reference
  implementation the customer can rebuild in their preferred framework.
  USE FOR: workspace UI, case management UI, agent operator console,
  case list with detail pane, action toolbar, audit viewer, threadlight
  workspace, demo workspace, operator dashboard.
  DO NOT USE FOR: experience.html cinematic (use threadlight-design),
  Teams Adaptive Cards (use threadlight-hitl-patterns), real-time chat UI,
  framework-specific scaffolds (we ship pattern, not framework).
---

# Threadlight Workspace UI

Generate a curated, framework-agnostic **workspace UI** reference for a
designed threadlight process. The output is ONE polished example —
intentionally **shipped as pattern, not framework** — that the customer can
either drop into their preferred stack or rebuild faithfully.

> **Why framework-agnostic?** Customer constraint: web framework is
> irrelevant — the customer will rebuild in their stack (React, Angular,
> Vue, Blazor, native iOS, …). What matters is that the **shape** is
> right: the right filters, the right detail-pane sections, the right
> action toolbar, the right audit viewer placement. We ship that shape
> as one curated vanilla-JS+HTML reference plus a framework-mapping
> guide.

## When to Use

- After `threadlight-design` has produced `specs/SPEC.md` § 8b
- The process has a human operator who lives in this UI day-to-day
  (not just an approval card in Teams)
- Examples: KYC analyst workspace, Order Fallout NOC console, Supplier
  Risk control room, PIM enrichment editor

## When NOT to Use

- Process is fully autonomous (no human operator)
- Humans only interact via Teams approval card (use `threadlight-hitl-patterns` only)
- Customer provides their own UX (skip; just produce the action contract)

---

## Input contract / Output artifacts

**Input contract** — what this skill consumes:

- `specs/SPEC.md` § 8b **Human Interaction (Workspace UX)** — required
  - `Workspace shape`: `case-list` | `inbox` | `dashboard` | `console` | `kanban` | `map`
  - `Primary filters`
  - `Detail pane sections`
  - `Action toolbar` (subset of § 8 action gates)
  - `Audit viewer` placement
  - `Bulk operations`
- `specs/SPEC.md` § 4 **Data Models** — for entity field rendering
- `specs/SPEC.md` § 8 **Human Interaction Points** — action gate definitions
- `specs/sample-data/*.json` — to seed the demo with real-shaped data
- `AGENTS.md` — for the agent's name, identity, and skill catalog
- `specs/manifest.json` — for process name, traits, BR count

**Output artifacts** — what this skill produces:

```
src/workspace/
├── index.html                # Single-file reference (vanilla HTML+CSS+JS)
├── workspace.css             # Themed for the process
├── workspace.js              # Filter / detail / action toolbar logic
├── seed-data.js              # Loaded from specs/sample-data/ at build
├── README.md                 # How to rebuild in React/Angular/Vue/Blazor
└── components/               # Same components, broken out for copy-paste
    ├── case-list.html
    ├── detail-pane.html
    ├── action-toolbar.html
    └── audit-viewer.html
```

The reference is **opinionated** — one polished implementation per workspace
shape — not a flexible framework.

---

## Workspace shapes (the catalog)

Each shape has its own polished reference. Pick one (driven by spec § 8b).

### `case-list`

The default for case-managed processes (KYC, claims, credit decisions).

**Anatomy:**
- **Top bar**: agent identity + global search + user avatar + reset-demo button
- **Left rail**: filter pills (status / owner / age / risk-band / SLA)
- **Center**: case-list (sortable columns; selection toggles right pane)
- **Right pane** (when case selected):
  - Summary card (entity name, status badge, key fields)
  - Agent reasoning trace (collapsed by default — "show why")
  - Tool call log (collapsed — "show what the agent did")
  - Action toolbar (gates from § 8)
  - Audit viewer (drawer)

**Visual rules:**
- One accent color (per process)
- Status badges colorized by semantics (approved=green, declined=red,
  pending=amber, escalated=violet)
- SLA countdown chip turns red at <10 min
- Agent reasoning rendered as numbered steps with tool icons

**Examples in catalog:**
- KYC analyst workspace (FSI)
- SMB credit memo review (FSI)
- Adverse media case review (FSI)

### `inbox`

For processes where items arrive continuously and operators work top-of-queue.

**Anatomy:**
- **Top bar**: same as `case-list`
- **Left**: chronological feed (newest top), grouping by hour/day
- **Right**: detail pane (same shape as `case-list` right pane)
- **Bulk action bar** appears when ≥1 item is multi-selected

**Visual rules:**
- Cards stack with subtle shadows
- Read state visually distinct (faded after view)
- "Mark all as read" / "Assign to me" bulk actions

**Examples:**
- Returns triage operator inbox (Retail)
- Insurance FNOL adjuster inbox (FSI)

### `dashboard`

For processes where operators monitor KPIs and drill into anomalies.

**Anatomy:**
- **Top bar**: same
- **KPI tiles row**: 4-6 large numeric tiles with sparklines
- **Anomaly feed**: list of "things needing attention" (links to case detail)
- **Drill-down modal**: opens for a tile or anomaly → shows underlying cases

**Visual rules:**
- KPI tiles use the BR-XXX → KPI mapping from spec § 9
- Sparklines reflect last 7 days (or process-appropriate window)
- Color rules: green (target met), amber (within ±20%), red (alert threshold breached)

**Examples:**
- Supplier Risk control room (Mfg)
- PIM catalog enrichment progress dashboard (Retail)

### `console`

For live operations — operator watches events stream in, takes action immediately.

**Anatomy:**
- **Top bar**: same
- **Split view**:
  - Left: live event stream (newest top, auto-scroll with pause)
  - Right: focused-event detail + action toolbar
- **Bottom rail**: connection status + active operators + reset-demo

**Visual rules:**
- New events fade in from the top
- "Pause auto-scroll" button when operator is reading
- Action toolbar always visible (no need to scroll)

**Examples:**
- Telco Order Fallout NOC console
- Network-fault triage dispatch console

### `kanban`

For case lifecycle visibility — items flow through ordered stages.

**Anatomy:**
- **Top bar**: same
- **Columns**: one per case stage (from spec § 4 state machine)
- **Cards**: one per case, drag-and-drop between columns (with audit gate)
- **Right drawer**: opens when card clicked, same detail-pane shape

**Visual rules:**
- WIP limits shown per column (subtle warning at 80%, hard at 100%)
- Cards colorized by age (green ≤4h, amber ≤24h, red >24h)
- Drag triggers an action gate (spec § 8 `edit-and-approve`) before commit

**Examples:**
- Order Fallout pipeline view (Telco — alternative to console)
- Loan origination pipeline (FSI)

### `map`

For geographically-distributed processes.

**Anatomy:**
- **Top bar**: same
- **Map area**: dot density / heatmap / region polygons
- **Filter rail**: same as case-list, plus region selector
- **Bottom drawer**: list of items in current viewport
- **Click on dot/region**: opens detail pane

**Visual rules:**
- Use a subtle base map (no full-color satellite)
- Dot color = severity/risk
- Cluster at low zoom, expand at high zoom

**Examples:**
- Supplier Risk world map (Mfg)
- Multi-region telco fault map (Telco)

---

## Generation procedure

### Step 1: Read spec § 8b

```python
workspace_shape = spec["workspace_ux"]["shape"]
filters = spec["workspace_ux"]["primary_filters"]
detail_sections = spec["workspace_ux"]["detail_pane_sections"]
toolbar_gates = spec["workspace_ux"]["action_toolbar"]  # subset of § 8 gates
audit_placement = spec["workspace_ux"]["audit_viewer"]
bulk_ops = spec["workspace_ux"]["bulk_operations"]
```

If § 8b is missing or `none`, do NOT generate workspace UI — emit a note in
`README.md` saying "this process has no operator workspace; humans interact
only via Teams cards (see `threadlight-hitl-patterns`)".

### Step 2: Pick the shape's reference

Copy `references/shapes/{shape}/` into `src/workspace/`. Each shape ships a
polished, customer-grade vanilla HTML+CSS+JS implementation.

### Step 3: Tailor

Replace tokens in the copied files:

| Token | Source |
|-------|--------|
| `__PROCESS_NAME__` | `manifest.json.name` |
| `__AGENT_NAME__` | `AGENTS.md` |
| `__ACCENT_COLOR__` | per-process palette (see `references/palettes.md`) |
| `__FILTERS__` | spec § 8b filters |
| `__DETAIL_SECTIONS__` | spec § 8b detail sections |
| `__TOOLBAR_GATES__` | spec § 8b toolbar (each becomes a button rendering its action gate) |
| `__BULK_OPS__` | spec § 8b bulk operations |
| `__AUDIT_PLACEMENT__` | `inline` | `drawer` | `none` |
| `__ENTITY_FIELDS__` | spec § 4 main entity fields |
| `__SAMPLE_DATA_FILES__` | list of `specs/sample-data/*.json` |

### Step 4: Wire to mock data

`workspace.js` loads `specs/sample-data/*.json` at startup and renders the
case list / inbox / dashboard / etc. from real-shaped data.

> The customer's real backend will replace these JSON files with API calls
> in their framework rebuild. The shape contract — which fields are present,
> how they're rendered, what filters apply — is what we ship.

### Step 5: Generate framework-mapping README

Generate `src/workspace/README.md` with:

- One paragraph per major framework (React, Angular, Vue, Blazor) explaining:
  - Which file maps to which component in their framework
  - What state management pattern this assumes (Redux-style for React, etc.)
  - Where the API boundary lives

The point isn't to ship the React version — the customer's React expert can
re-implement in 1 day. The point is that the **shape is right**.

### Step 6: Validate

```
✅ index.html parses (HTMLParser)
✅ All filter pills clickable
✅ Detail pane opens on case selection
✅ Each toolbar button shows the right action gate behavior (links to
   threadlight-hitl-patterns adaptive card mock)
✅ Audit drawer opens/closes (or audit panel always visible per § 8b)
✅ No external CDN — fully self-contained
✅ Whitelabel deny-list grep returns zero hits
✅ Sample data loads without console errors
✅ Reset-demo button restores pristine state
```

---

## Framework-rebuild guidance

`README.md` includes copy-paste-ready snippets for the four most common
customer stacks. Each shows ONE entry point — the customer's lead
front-end engineer can extrapolate from there.

| Stack | Entry point | State | Routing |
|-------|-------------|-------|---------|
| **React** | `src/workspace.tsx` reads `seed-data.js` JSON; one root component matches `index.html` shape | Redux Toolkit / Zustand / TanStack Query | React Router |
| **Angular** | `WorkspaceComponent` ≈ `index.html` body; child components ≈ `components/*.html` | NgRx or signals | Angular Router |
| **Vue 3** | `WorkspaceView.vue` SFC matches `index.html` body | Pinia | Vue Router |
| **Blazor (Server / WASM)** | `Workspace.razor` page; child Razor components | built-in `[Parameter]` flow | Blazor router |

> **Don't ship more than one framework version.** If a customer asks for
> React specifically, regenerate from this skill with `--target=react`
> (future flag) or hand-port — but the canonical reference is the
> vanilla one. Maintaining 4 framework versions of every demo is the
> mistake we're explicitly avoiding.

---

## Visual/design conventions

These are the same as `threadlight-design`'s `experience.html` cinematic, so
the workspace and the cinematic feel like the same product:

- **Type**: Inter or system stack; tabular figures for numbers
- **Spacing**: 8px grid
- **Color**: 1 accent per process (see `references/palettes.md`); semantic
  status colors universal across processes
- **Density**: information-dense — operator workspaces, not marketing pages
- **Motion**: subtle (200ms ease-in-out for transitions); no parallax

> The workspace is the **everyday** UI. It's deliberately calmer than the
> cinematic `experience.html`. The cinematic sells; the workspace works.

---

## Reference files

| File | Purpose |
|------|---------|
| `references/shapes/case-list/` | Polished case-list reference |
| `references/shapes/inbox/` | Polished inbox reference |
| `references/shapes/dashboard/` | Polished dashboard reference |
| `references/shapes/console/` | Polished console reference |
| `references/shapes/kanban/` | Polished kanban reference |
| `references/shapes/map/` | Polished map reference |
| `references/palettes.md` | Per-process accent color palette catalog |
| `references/framework-rebuild.md` | Detailed React/Angular/Vue/Blazor port notes |

> The shapes/ subdirectories are seeded as empty placeholders in this commit;
> each gets fleshed out as the corresponding pilot lands a real customer-grade
> reference. The KYC pilot will canonize `case-list/`; the Order Fallout pilot
> will canonize `console/` (or `kanban/`, depending on demo direction); the
> Supplier Risk pilot will canonize `dashboard/` (and possibly `map/`); the PIM
> pilot will canonize `inbox/`.

---

## Anti-patterns (DO NOT do)

- ❌ **Ship more than one framework version**. We ship pattern, not framework.
- ❌ **Reuse the experience.html cinematic for the workspace**. Different
  intent — cinematic sells, workspace works.
- ❌ **Bake real customer data into the seed**. Always use the synthetic
  data from `specs/sample-data/` (which is governed by
  `threadlight-demo-data-factory`).
- ❌ **Skip the audit viewer**. Even if § 8b says `none`, every workspace
  must show *some* indication of "what just happened" — drop a minimal
  audit toast at minimum.
- ❌ **Generate a workspace UI when § 8b says `none`**. If humans only
  interact via Teams cards, generate ONLY `threadlight-hitl-patterns` output.
- ❌ **Hardcode colors** outside the palette catalog. One accent per process,
  semantic status colors universal.

---

## See Also

| Skill | Use When |
|-------|----------|
| [`threadlight-design`](../threadlight-design/) | Produces the spec § 8b that this skill consumes |
| [`threadlight-hitl-patterns`](../threadlight-hitl-patterns/) | The Teams Adaptive Card side of human interaction (action gates) |
| [`threadlight-deploy`](../threadlight-deploy/) | Wires the workspace into the deployable agent (static site behind the bot ACA) |
| [`threadlight-demo-data-factory`](../threadlight-demo-data-factory/) | Generates the seed JSON the workspace renders |
