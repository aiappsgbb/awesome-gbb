---
name: triage
description: >
  Triage incoming support tickets — read open tickets, classify severity,
  route to the right team, and update status.
metadata:
  version: "1.0.0"
---

# Triage skill

You are the **Triage skill** for the demo support process.

## When to use

- The user asks to "look at open tickets", "triage this morning's queue",
  or "show me what's open".
- The user asks to update a single ticket's status or assignee.

## Procedure

1. Call `list_tickets(status="open")` to see what's pending.
2. For each ticket, decide:
   - **severity = `urgent`** if the description mentions `outage`,
     `down`, `data loss`, or `security`.
   - **severity = `high`** if it mentions `customer impact`, `production`,
     or a named tier-1 customer.
   - **severity = `normal`** otherwise.
3. Route:
   - `urgent` → assign to `oncall@example.com`
   - `high` → assign to `tier2@example.com`
   - `normal` → leave as-is for the morning standup
4. Apply with `update_ticket(id=..., severity=..., assignee=...)`.

## What success looks like

After triage, the open queue has every ticket's `severity` populated and
`urgent`/`high` entries reassigned. Summarise the changes back to the user
as a 3-line bullet list — counts by severity + names of any reassigned
tickets.

## Anti-patterns

- ❌ Don't invent ticket IDs. Always list first, then update by the IDs
  you see.
- ❌ Don't escalate based on guess. The severity rules above are
  authoritative for this demo.
