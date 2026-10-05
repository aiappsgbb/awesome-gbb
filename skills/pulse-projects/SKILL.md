---
name: pulse-projects
description: >
  Persistent per-customer project memory: one curated YAML file per engagement in
  the user's OneDrive Pulse folder, tracking status, risk, stakeholders,
  commitments, timeline, artifacts and teammate context. USE FOR: the user
  mentions a customer, deal, engagement, initiative or stakeholder by name;
  describes a meeting, email or conversation that affects a known engagement;
  asks about commitments, status, or who-said-what for named work; creating,
  updating, curating or auto-archiving engagement records. DO NOT USE FOR:
  deadline or task tracking (commitments are never deadlines), CRM or pipeline
  system-of-record updates, or one-off notes with no named engagement.
metadata:
  version: "1.0.0"
---

# Pulse Projects

Persistent project memory: one YAML file per customer engagement, stored in OneDrive. The schema, the file location, and the rules for what's worth tracking.

## Path

`<PULSE_HOME>` is the Pulse folder under the user's OneDrive `Documents/`. Resolve once at start, picking the first existing path for the user's OS:

**Windows (PowerShell):**
```powershell
if ($env:OneDriveCommercial) { "$env:OneDriveCommercial\Documents\Pulse" } elseif ($env:OneDrive) { "$env:OneDrive\Documents\Pulse" } else { "$env:USERPROFILE\Documents\Pulse" }
```

**macOS (zsh/bash):**
```bash
# Modern (macOS 12.3+): OneDrive for Business under Library/CloudStorage
ls -d "$HOME/Library/CloudStorage/OneDrive-"*/Documents 2>/dev/null | head -1
# Older convention
ls -d "$HOME/OneDrive - "*/Documents 2>/dev/null | head -1
# Personal OneDrive
[ -d "$HOME/OneDrive/Documents" ] && echo "$HOME/OneDrive/Documents"
# Last resort
echo "$HOME/Documents"
```
Take the first non-empty result, append `/Pulse`.

**Linux:** `$HOME/OneDrive/Documents/Pulse` if it exists, else `$HOME/Documents/Pulse`.

If none exists, create under the last-resort path. Path examples in this skill use Windows-style `\` — on macOS/Linux, use `/` instead.

Files live at `<PULSE_HOME>\projects\<slug>.yaml`. Slug is lowercase-hyphenated. **One file per customer** — workshops, reviews, sub-meetings are timeline entries, never separate files.

## Schema

```yaml
project: "Human-readable name"          # required
involvement: lead                        # lead | contributor | observer (default: observer)
status: active                           # active | blocked | on-hold | completed
risk_level: medium                       # low | medium | high | critical
summary: "1–2 sentences current state"
last_verified: "2026-05-05"
stakeholders:                            # max 6
  - {name, role, org?, last_interaction?}
commitments:                             # follow-ups and next steps, NOT deadlines
  - what: "Send pricing proposal"
    who: "<name>"                        # actual owner; "You" ONLY if the user explicitly volunteered it
    to: "<recipient>"
    date_mentioned: "2026-05-12"         # optional context only — never a deadline or target
    status: open                         # open | done | cancelled
    source: "<artifact reference>"
timeline:                                # max 10 entries
  - {date, event, source}
related_artifacts:                       # max 6
  - {type, path, description}
team_context:                            # max 5 entries — what teammates' Pulses know
  - from: jane                           # teammate handle
    relevance: high                      # high | low | none | pending
    summary: "Working on similar architecture with another customer. Has shared assets."
    last_updated: "2026-05-05"
watch_queries: ["customer", "person"]    # max 3
tags: ["industry", "tech"]               # max 4
notes: |
  Free-form context.
updated_at: "<ISO timestamp>"            # set on every write
```

## Discovery — when to create a NEW project

ALL THREE conditions must be met:
1. **3+ mentions** of the customer/initiative across user data
2. **2+ different source types** (transcript + email — not two emails from the same thread)
3. **At least one actionable element** — deliverable, meeting series, or explicit ask directed at the user

Passive mentions and CC'd emails do NOT meet the threshold.

Before creating, search existing slugs. If a file already exists, **update it**. Default `involvement: observer` unless the user clearly owns it.

## Team context broadcast — automatic on key events

Teammates running their own Pulse may have relevant context on the same customer. On qualifying events, fan out a query to every reachable teammate and let their Pulses respond asynchronously. Replies arrive minutes or hours later through `/agent-inbox`. When a reply has a `project_id`, update that project's `team_context` entry for the sender.

This section is **optional** and requires an `agent-inbox` skill for agent-to-agent messaging. If none is installed, skip it silently and leave `team_context` empty.

**When to broadcast:**
- **Always on new project creation** (discovery threshold met for a customer not yet tracked)
- On **major updates**: status escalation to `blocked`, `risk_level` raised to `high`/`critical`, project moves from `on-hold` back to `active`
- **7-day cooldown** per project — don't re-broadcast on minor changes (timeline entries, refresh, stakeholder pruning)

**How:**

1. Pick the teammates to ask (the user's usual team, or anyone they name).
2. Send **one** `agent_request` to all of them using `/agent-inbox`'s Ask flow, with `project_id` set to this project's slug and this task:

   ```yaml
   task: |
     New engagement: <Customer> / <Initiative>.
     Have you had activity on this in the LAST 30 DAYS? Looking for: ongoing meetings,
     commitments, key contacts, anything pertinent right now.
     Context (1 line): <summary>
   ```

3. Seed a `team_context` entry per teammate in the project YAML:

   ```yaml
   team_context:
     - from: <handle>
       relevance: pending
       summary: "Asked <today>, no response yet."
       last_updated: "<today>"
   ```

4. Continue creating/updating the project. **Don't block** waiting for replies.

If no teammates are reachable, skip silently — leave `team_context` empty.

## Read-before-write

Always: list directory → read existing file → merge new info → apply curation limits → set `updated_at` → write the full file. Never overwrite blindly.

## Curation limits (HARD)

Stakeholders ≤6 · Timeline ≤10 · Tags ≤4 · Watch queries ≤3 · Artifacts ≤6 · `team_context` ≤5 · Summary ≤2 sentences. When exceeded, **prune oldest low-value entries first** — never the newest.

## Commitment lifecycle

The user has **no deadlines or targets**. Commitments are a record of who said they'd follow up on what, nothing more.

- There is **no `overdue` status**. Never mark, report, or count anything as overdue, late, missed, or past due — including customer or teammate actions.
- A passed `date_mentioned` changes nothing: no status change, no `risk_level` change, no `blocked`, no flag in the report.
- Attribute to the real owner. Use `who: "You"` only when the user explicitly volunteered the action in their own words; attendance, CCs, or being on an invite never make it theirs.
- Mark `done` with completion source when fulfilled. Mark `cancelled` with `cancelled_reason` only when a source says it was dropped or superseded.
- If an existing file has `status: overdue`, `due`, `due_confidence`, or `by` fields, rewrite them to `status: open` and `date_mentioned` on the next write.

## Auto-archive observer projects

`involvement: observer` + `status: active` + no activity in 14+ days → set `status: completed` with timeline entry `[AUTO-ARCHIVED] No activity in 14+ days and involvement is observer`. Observer projects must prove they're worth tracking.

## Never

- Invent dates, names, amounts, or commitments — only persist what's explicit in source
- Create a second file for the same customer
- Mark `lead` from a single email or meeting attendance
- Mark or report anything as overdue, late, or missed, or treat any date as the user's deadline or target
- Delete history when uncertain — add a `[STALE]` or `[INFO]` timeline entry instead
- Broadcast on minor updates — that spams teammates
