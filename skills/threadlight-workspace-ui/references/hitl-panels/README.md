# HITL panel templates

Three drop-in panel templates that every analyst workspace needs,
regardless of shape (`case-list`, `inbox`, `dashboard`, `console`,
`kanban`, `map`). These templates were captured from the card-dispute
v3 PoC remediation pass after the original v3 ship was caught with
zero analyst-facing decision UI — the agent ran headless and the
"workspace" was a static file dump.

## Why panels (not full apps)

The shapes (`case-list` etc.) define the **outer layout** — what the
operator sees in the left/center/right zones. The HITL panels define
the **action surface** that lives inside one of those zones (typically
the right pane or a drawer). Same panel; many shapes.

Every workspace pilot needs all three panels:

| Panel | Where it lives | What it does |
|---|---|---|
| **decision-pane** | Right pane (case-list, inbox, kanban) OR center (console) | Surface the agent's recommendation + evidence + citations side-by-side, so the operator can make the BR-XXX call without leaving the workspace |
| **action-toolbar** | Top of decision-pane (always visible) | Render the BR-XXX-derived gates as buttons — `approve / edit / reject / escalate` — wired to the agent's writeback endpoint |
| **audit-viewer** | Drawer or modal (triggered from any case row) | Read-only view of the immutable audit log — every decision, every actor, every timestamp, exportable as CSV/PDF for compliance |

## Drop-in instructions

1. Copy the three `.html` files into `src/workspace/components/`.
2. Each template ships a vanilla `<style>` block and a tiny vanilla-JS
   controller. NO React / NO Vue / NO build step. They render straight
   from `file://` and stay clean inside an nginx container.
3. Wire each panel's `data-` attributes to your seed JSON (see the
   "Data contract" section in each file).
4. Recolor by setting `--accent` on the panel root — nothing else.
5. Drop them inside whichever shape's right-pane / drawer slot the
   spec § 8b picks.

## Data contract (shared)

All three panels read from a single global object the parent
workspace populates from the agent's MCP server (or a stub):

```js
window.threadlight = {
  // Active case context (set when operator selects a row)
  activeCase: {
    id: "DC-2026-001",
    entity: "Mei-Lin Chen",
    status: "AWAITING_REVIEW",
    sla: { hoursRemaining: 7.2, hardDeadline: "2026-05-12T17:00:00Z" }
  },
  // Agent's current recommendation for the active case
  recommendation: {
    summary: "Recommend provisional credit; BR-005 timer at risk",
    confidence: 0.84,
    evidence: [ /* see decision-pane Data contract */ ],
    citations: [ /* see decision-pane Data contract */ ]
  },
  // BR-XXX action map
  actions: [
    { id: "approve",  label: "Approve recommendation", br: "BR-007", needsReason: false },
    { id: "edit",     label: "Edit + approve",         br: "BR-007", needsReason: true  },
    { id: "reject",   label: "Reject",                 br: "BR-008", needsReason: true  },
    { id: "escalate", label: "Escalate to supervisor", br: "BR-010", needsReason: true  }
  ],
  // Immutable audit log for the active case
  audit: [ /* see audit-viewer Data contract */ ],
  // Submit handler — POSTs to the agent
  onAction: async (actionId, payload) => { /* implementation */ }
};
```

A stub implementation that returns realistic fixtures is fine for
demos; the same contract drives a real Cosmos-backed deployment.

## What's intentionally NOT here

- **Case-list / inbox / dashboard / etc. are shape-level**; their
  references live in `references/shapes/<shape>/`. The HITL panels
  drop INTO them.
- **The Teams adaptive-card side** of human-in-loop lives in
  `threadlight-hitl-patterns` (a different skill). The two are
  designed to share the same data contract above so an action gated
  via Teams shows up in the workspace audit-viewer with no extra
  translation.
- **No framework rebuild** — these are intentionally vanilla. If the
  customer wants React, point them at
  `references/framework-rebuild.md` for the port recipe.

## Verified-against

- `card-dispute-investigation` v3 PoC remediation pass (May 2026):
  fixed the "workspace UI lacks any decision surface" gap by dropping
  these three panels into `src/workspace/`. Took ~30 minutes per
  panel; same shape works for KYC analyst console + Order Fallout
  BSS console + supplier-risk control room.
