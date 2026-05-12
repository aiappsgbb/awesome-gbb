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
metadata:
  version: "1.0.0"
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

## Standard HITL panels (drop-in templates)

Three standard panels live in `references/hitl-panels/` — they're
**shape-agnostic** (drop into the right pane of `case-list`, `inbox`,
`kanban`; the center of `console`; or as a drawer triggered from
`dashboard` / `map`). Every workspace pilot needs all three; do not
ship a workspace without them.

| Panel | File | Purpose |
|-------|------|---------|
| **Decision pane** | `references/hitl-panels/decision-pane.html` | Agent recommendation + evidence + citations side-by-side |
| **Action toolbar** | `references/hitl-panels/action-toolbar.html` | BR-XXX-derived action gates (`approve / edit / reject / escalate`) with reason capture |
| **Audit viewer** | `references/hitl-panels/audit-viewer.html` | Read-only immutable audit log with CSV/PDF export |

**Shared data contract.** All three panels read from a single global
`window.threadlight` object (`activeCase`, `recommendation`,
`actions`, `audit`, `onAction`). Wire that object once from the seed
JSON or the agent's MCP server and all three panels light up.
See `references/hitl-panels/README.md` for the full contract +
"Drop-in instructions" + the demo stub. Vanilla HTML / CSS / JS — no
React, no build step; renders straight from `file://` for early
demos and stays clean inside an nginx ACA container for production.

**Why mandatory.** Recent pilots shipped without these panels and
got caught with a "workspace" that was a static file dump — no
analyst-facing decision surface, no action gates, no audit. The
remediation pass took ~30 min per panel using these templates. That
remediation is the last time we want to do this work; future pilots
copy these three files first, then style them per process accent.

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

### Step 5.5: Document the state model + identity boundary

Two surfaces that ALWAYS need spelling out — they're the two questions
the customer's lead engineer asks within the first 10 minutes of opening
this workspace:

**State model (in-memory + URL session anchor)**

Generate the workspace as a stateless front-end backed by an in-memory
store rebuilt from `specs/sample-data/*.json` on page load. Persist a
single anchor — the demo's "session" — in the URL query string:

```
/index.html?session=<uuid-v4>
```

That session ID:
- seeds RNG for any UI-side randomness so a refresh shows the same case
  ordering / shuffle
- scopes the `localStorage` key for in-progress action drafts
  (`workspace:<sessionId>:drafts`) so two demo browser tabs don't
  fight each other
- gets logged into every audit record this workspace writes (see below)

When the SPEC § 8b includes a `reset_demo` action, the button generates
a fresh UUID, replaces the URL with `history.replaceState`, and triggers
the seed-data reload. There is NO server-side session; persistence is
the customer's job in their rebuild.

**Identity / audit-actor boundary**

The workspace MUST surface the human actor on every audit-writing
action — never write `actor: "demo"` or anonymous. Two patterns to ship:

1. **Behind Easy Auth (default for ACA-hosted demo)**: the platform
   injects `X-MS-CLIENT-PRINCIPAL` (Base64-JSON) into every request.
   The workspace reads it via a tiny `/.auth/me` proxy or by decoding
   the header in the page-loading HTML wrapper. Map
   `claims.preferred_username` (or `email`, or `oid` as fallback) into
   a global `currentActor` object surfaced to the audit writer.

2. **Public demo (no Easy Auth)**: ship a one-line MSAL.js loader that
   prompts for AAD sign-in on first load using the customer's tenant
   (or a Microsoft tenant for internal-only demos). Block all
   audit-writing actions until `currentActor` is populated.

Either way, the SHAPE the audit writer expects is:

```json
{
  "actor": {
    "kind": "human",
    "id": "<oid|upn>",
    "display": "<full name>",
    "tenant": "<tenant-id>",
    "session": "<sessionId from URL>"
  }
}
```

Sample-data filtering: any record returned from the in-memory store MUST
strip the wrapper `_meta` block (per `threadlight-demo-data-factory`'s
`{"_meta", "records"}` shape) before binding to the UI — the meta block
is for traceability, not display. A single `loadEntity(name)` helper at
the data-access boundary should do this once.

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
✅ Playwright screenshot at HIGH-RES — see "Playwright validation: high-res
   screenshot mandate" below
```

### Playwright validation: high-res screenshot mandate

The workspace screenshot is a **slide-deck deliverable** — it lands in
exec briefings, partner decks, and release readouts. A 1280×720 viewport
at DPR 1 (default Playwright) produces ~92 DPI bitmaps that look
**fuzzy** when projected on a meeting-room screen, and unusable when
sized down to a quarter-slide thumbnail.

**Required.** Every workspace Playwright capture MUST use:

- **Viewport**: ≥ **1920 × 1080** (1080p). Bigger is fine — 2560 × 1440
  is the sweet spot for a workspace UI with sidebar + detail-pane.
- **deviceScaleFactor**: **2** (Retina-equivalent). This makes text
  pixel-perfect and SVG icons crisp.
- **fullPage: true** when the workspace scrolls below the fold; the
  reviewer can crop, but the artifact must capture the entire UI.

```python
# scripts/capture_workspace_screenshot.py
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},   # 1080p minimum
        device_scale_factor=2,                       # Retina equivalent
    )
    page = context.new_page()
    page.goto("http://localhost:8000/?session=demo-001")
    page.wait_for_selector("[data-testid='case-list']")
    page.locator("[data-case-id='CASE-<id>']").click()  # open detail pane
    page.wait_for_selector("[data-testid='detail-pane']")
    page.screenshot(
        path="docs/screenshots/workspace.png",
        full_page=True,
    )
    browser.close()
```

Or the equivalent `npx playwright` flag if you're scripting in TS:

```bash
npx playwright screenshot \
  --viewport-size=1920,1080 \
  --device-scale-factor=2 \
  --full-page \
  http://localhost:8000/?session=demo-001 docs/screenshots/workspace.png
```

> **Quality check.** Open the captured PNG in a viewer at 100% — text
> should read crisply, no anti-aliasing fuzz. If it looks soft, you
> shipped at DPR 1; redo with `device_scale_factor=2`. The PNG file
> for a fully-rendered workspace at 1920×1080 DPR-2 should be
> **≥ 600 KB** — anything smaller is a red flag.

---

## Hosting: ACA-mandatory for any non-trivial workspace

> **A workspace that exists only as `file:///.../index.html` opened
> from the analyst's laptop is NOT a deployed PoC.** It is a
> developer-mode preview. PoCs that ship without ACA hosting cannot
> demonstrate Easy Auth, MSAL sign-in, multi-user audit, or the
> "click the URL we sent you" demo flow ` and they fail the
> `threadlight-deploy` Phase 3.5 post-deploy completeness gate
> (workspace ACA missing from `az resource list`).

### When ACA hosting is REQUIRED

Any of these triggers mandate ACA:

- SPEC § 8b Workspace UX is non-empty (case-list, inbox, dashboard, console, kanban, map ` any of them).
- SPEC § 8 lists "Analyst Workspace" or any web-channel as a Human Interaction channel.
- SPEC's `deployment_manifest.module_selectors.workspace-ui` is `yes`.
- Any audit-writing action runs from the workspace (Easy Auth or MSAL is the only way to populate the actor identity ` `file://` cannot).

### When file:// preview is acceptable

Only:
- One-shot stakeholder mock-ups with no audit, no MCP calls, no auth.
- Internal grooming of UX shape **before** wiring into the deploy pipeline.

If this is your case, mark it explicitly in SPEC § 8b ("demo-only static
preview, no ACA hosting") so the deploy gate doesn't flag it.

### Required ACA-deployment artifacts

When ACA hosting is required, ship all of these in the same commit
as `index.html` ` not as a follow-up:

```
src/workspace/
+- index.html                # the workspace SPA (single page)
+- seed-data.js              # generated from sample-data
+- components/               # reusable HTML partials (if extracted)
+- assets/                   # css/js/images (no CDN)
+- Dockerfile                # MANDATORY ` see template below
+- nginx.conf                # MANDATORY ` see template below
+- .dockerignore             # excludes node_modules, dist/, screenshots/
```

Minimal `Dockerfile` (nginx-alpine, ~12 MB, sub-second cold start):

```dockerfile
# src/workspace/Dockerfile
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html  /usr/share/nginx/html/
COPY seed-data.js /usr/share/nginx/html/
COPY components/ /usr/share/nginx/html/components/
COPY assets/    /usr/share/nginx/html/assets/
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/ || exit 1
```

Minimal `nginx.conf`:

```
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    location /health { return 200 "ok\n"; add_header Content-Type text/plain; }
    location / { try_files $uri $uri/ /index.html; }
}
```

### Wiring into `azure.yaml`

The deploy skill's Phase 3 `src/`-orphan check requires this entry:

```yaml
# azure.yaml
services:
    workspace:
        project: ./src/workspace
        host: containerapp
        language: docker
        docker:
            remoteBuild: true
```

And the corresponding Bicep wiring in `infra/main.bicep`:

```bicep
module workspaceAca 'core/host/container-app.bicep' = {
  name: 'workspace-aca'
  scope: rg
  params: {
    name: '${abbrs.appContainerApps}workspace-${resourceToken}'
    location: location
    containerAppEnvironmentId: acaEnvironment.outputs.id
    targetPort: 80
    userAssignedIdentityId: sharedUami.outputs.id
    containerRegistryEndpoint: ai.outputs.acrLoginServer
    image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'   // overridden by `azd deploy workspace`
    env: [
      // workspace is static + reads `/api/*` from `bot` ACA via Easy Auth-forwarded headers
    ]
  }
}
```

### Easy Auth: the right default for ACA-hosted workspaces

Postprovision hook turns on AAD auth so the workspace gets
`X-MS-CLIENT-PRINCIPAL` for the audit-actor pattern documented above:

```bash
# scripts/postprovision/enable_easy_auth.sh
WORKSPACE_FQDN=$(az containerapp show -g "$RG" -n "$WORKSPACE_NAME" --query properties.configuration.ingress.fqdn -o tsv)
az containerapp auth update -g "$RG" -n "$WORKSPACE_NAME" \
   --enabled true --action RedirectToLoginPage \
   --redirect-provider AzureActiveDirectory
az containerapp auth microsoft update -g "$RG" -n "$WORKSPACE_NAME" \
   --client-id "$ENTRA_APP_ID" --tenant-id "$TENANT_ID"
```

> **Why nginx and not the Python http.server?** ACA cold-starts a
> nginx container in <1s; Python takes 3-5s and burns more CPU.
> Reviewers click the link and expect snappy. Use nginx.

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
| `references/hitl-panels/README.md` | Drop-in HITL panels — shared data contract + instructions |
| `references/hitl-panels/decision-pane.html` | Agent recommendation + evidence + citations panel |
| `references/hitl-panels/action-toolbar.html` | BR-XXX-derived action gates with reason capture |
| `references/hitl-panels/audit-viewer.html` | Immutable audit log drawer with CSV/PDF export |
| `references/shapes/case-list/` | Polished case-list reference |
| `references/shapes/inbox/` | Polished inbox reference |
| `references/shapes/dashboard/` | Polished dashboard reference |
| `references/shapes/console/` | Polished console reference |
| `references/shapes/kanban/` | Polished kanban reference |
| `references/shapes/map/` | Polished map reference |
| `references/palettes.md` | Per-process accent color palette catalog |
| `references/framework-rebuild.md` | Detailed React/Angular/Vue/Blazor port notes |

> The HITL panel templates are shipped in this commit and are
> production-grade vanilla HTML/CSS/JS. The shapes/ subdirectories are
> seeded as empty placeholders; each gets fleshed out as the corresponding
> future pilots land customer-grade references. Future pilots will canonize
> `case-list/`, `console/` (or `kanban/`), `dashboard/` (and possibly
> `map/`), and `inbox/`.

---

## Anti-patterns (DO NOT do)

- ❌ **Ship more than one framework version**. We ship pattern, not framework.
- ❌ **Reuse the experience.html cinematic for the workspace**. Different
  intent — cinematic sells, workspace works.
- ❌ **Bake real customer data into the seed**. Always use the synthetic
  data from `specs/sample-data/` (which is governed by
  `threadlight-demo-data-factory`).
- ❌ **Skip the audit viewer**. Even if § 8b says `none`, every workspace
  must show *some* indication of "what just happened" — drop the
  `references/hitl-panels/audit-viewer.html` panel at minimum.
- ❌ **Ship a workspace without the 3 HITL panels** (decision-pane +
  action-toolbar + audit-viewer). Recent pilots made this mistake
  and shipped a static file dump with no decision surface.
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
| [`threadlight-safe-check`](../threadlight-safe-check/) | Probes the static-site / Easy Auth wiring generated here (post-deploy reachability gate) |
