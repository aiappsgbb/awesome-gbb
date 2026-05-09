---
name: threadlight-hitl-patterns
description: >
  Generate Teams Adaptive Card flows + bot UX components for the seven
  canonical action gates (approve, edit-and-approve, reject, escalate,
  signoff, audit-view, request-info) declared in spec § 8 Human Interaction
  Points. Pairs with foundry-teams-bot for delivery.
  USE FOR: human-in-the-loop, approval cards, Teams Adaptive Cards for
  agent decisions, action gate UX, edit-and-approve flow, escalation
  card, signoff flow, threadlight HITL.
  DO NOT USE FOR: bot infrastructure (use foundry-teams-bot), workspace
  UI (use threadlight-workspace-ui), agent runtime logic (use
  threadlight-deploy).
---

# Threadlight HITL Patterns

Generate **Teams Adaptive Cards** + bot integration for the seven canonical
action gates declared in `specs/SPEC.md` § 8 Human Interaction Points.

> **Why a separate skill from `foundry-teams-bot`?** `foundry-teams-bot`
> handles the bot **infrastructure** (manifest, ACA, UAMI, MsalConnectionManager,
> messaging extension routing). This skill handles the **gate UX** — the
> Adaptive Card content, the Action.Submit handlers, the audit-trail wiring.
> One bot, many gates; the bot doesn't know what the gates mean.

## When to Use

- Process spec § 8 declares one or more action gates
- Process needs human approval/escalation/signoff in Teams
- Edit-and-approve flow (operator can amend the agent's proposal before approving)

## When NOT to Use

- Process is fully autonomous (no § 8)
- Operator works in a workspace UI only (use `threadlight-workspace-ui`);
  but note that a workspace can still embed action gates locally

---

## Input contract / Output artifacts

**Input contract**:

- `specs/SPEC.md` § 8 — for each interaction:
  - `Action gate`: one of the seven canonical gates (see below)
  - `Linked business rules` (BR-XXX list)
  - `Data Presented`: which fields the human sees
  - `Options`: what actions the human can take
  - `Timeout/SLA`: how long before escalation
- `specs/SPEC.md` § 4 — entity field schemas (for the card data binding)
- `AGENTS.md` — for the agent identity that calls the gate

**Output**:

```
src/agent/skills/{skill-using-gate}/cards/
├── {gate-name}.json           # Adaptive Card template
└── {gate-name}-handler.py     # Action.Submit response handler
src/bot/cards/
├── card_router.py             # Routes incoming Action.Submit to the right handler
├── audit_trail.py             # Writes gate outcomes to Cosmos (or AppInsights)
└── card_registry.json         # Map of card name → handler module
```

---

## The seven canonical gates

Aligned with the action-gate taxonomy in `threadlight-design` SPEC § 8.

### 1. `approve` — yes/no

**When**: agent proposes a low-risk action; human confirms.

**Card shape**: Title + summary card + two buttons (`Approve` / `Decline`).

```jsonc
{
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {"type": "TextBlock", "text": "${title}", "size": "large", "weight": "bolder"},
    {"type": "FactSet", "facts": "${summaryFacts}"},
    {"type": "TextBlock", "text": "Linked rules: ${linkedRules}", "isSubtle": true, "size": "small"}
  ],
  "actions": [
    {"type": "Action.Submit", "title": "Approve", "data": {"gate": "approve", "decision": "approved", "case_id": "${caseId}"}, "style": "positive"},
    {"type": "Action.Submit", "title": "Decline", "data": {"gate": "approve", "decision": "declined", "case_id": "${caseId}"}, "style": "destructive"}
  ]
}
```

**Audit fields written**: `gate=approve`, `decision`, `case_id`, `actor`, `timestamp`,
`linked_rules`, `agent_proposal_summary`.

### 2. `edit-and-approve` — amend before commit

**When**: agent's proposal is mostly right but the human may want to tweak
fields before committing.

**Card shape**: editable Input fields prefilled with agent's proposal +
`Approve as edited` and `Cancel`.

```jsonc
{
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {"type": "TextBlock", "text": "${title}", "size": "large", "weight": "bolder"},
    {"type": "Input.Text", "id": "field1", "label": "Field 1", "value": "${proposed.field1}"},
    {"type": "Input.ChoiceSet", "id": "field2", "label": "Field 2", "value": "${proposed.field2}", "choices": "${field2Choices}"},
    {"type": "Input.Text", "id": "rationale", "label": "Why edit?", "isMultiline": true}
  ],
  "actions": [
    {"type": "Action.Submit", "title": "Approve as edited", "data": {"gate": "edit-and-approve", "case_id": "${caseId}"}, "style": "positive"},
    {"type": "Action.Submit", "title": "Cancel", "data": {"gate": "edit-and-approve", "decision": "cancelled", "case_id": "${caseId}"}}
  ]
}
```

**Audit fields**: includes `proposed_diff` (the delta between agent proposal
and human-edited values) for traceability.

### 3. `reject` — refuse with reason

**When**: human declines and must record why (regulatory or quality reasons).

**Card shape**: reason picker (ChoiceSet from the linked rules) + free-text +
single `Reject` button.

### 4. `escalate` — route to higher authority

**When**: case exceeds the human's authority; routes to a queue or named role.

**Card shape**: role/queue picker + reason + `Escalate` button. After submit,
post a NEW card to the escalation target.

### 5. `signoff` — attest review (no veto)

**When**: regulator requires human attestation but human has no veto power
(read-and-acknowledge).

**Card shape**: full case detail + `I have reviewed and acknowledge` single
button. Records signature trail (actor + timestamp + content hash).

### 6. `audit-view` — read-only inspection

**When**: human (auditor, compliance) inspects a case without taking action.

**Card shape**: full case detail with NO action buttons. Generates an audit
event ("viewed by X at T") for compliance.

### 7. `request-info` — ask for more data

**When**: agent can't proceed without more input from the customer or an
external party.

**Card shape**: templated message composer (subject + body, optionally with
attachment slots). Submit posts the templated message via the configured
channel (Teams chat, email via Logic App, etc.).

---

## Generation procedure

### Step 1: Walk spec § 8

For each interaction:

```python
gate = interaction["action_gate"]
linked_rules = interaction["linked_business_rules"]
fields = interaction["data_presented"]
sla = interaction["timeout_sla"]
```

### Step 2: Generate the card template

- Pick the canonical card shape from this skill's `references/cards/{gate}.json`
- Substitute `${title}`, `${summaryFacts}`, `${linkedRules}`, etc. with spec data
- For `edit-and-approve`: generate Input fields from the entity schema in spec § 4
- For `escalate`: derive the role list from the AGENTS.md skill actor table

### Step 3: Generate the handler

```python
# {gate}-handler.py
async def handle({decision_kwargs}):
    """Handles Action.Submit for this gate."""
    # 1. Validate caller's identity (Teams provides it via Bot Framework)
    # 2. Load the case from Cosmos (via MCP call or direct SDK)
    # 3. Apply the gate decision (write back to Cosmos, fire downstream action)
    # 4. Write audit trail (gate, decision, actor, timestamp, linked_rules, ...)
    # 5. Return updated card (success or error message)
    pass
```

### Step 4: Wire into the bot

Update `src/bot/cards/card_router.py` to map gate names to handlers:

```python
HANDLERS = {
    "approve": "skills.kyc_decision.cards.approve_handler",
    "edit-and-approve": "skills.kyc_decision.cards.edit_and_approve_handler",
    # ... one per gate ...
}

async def route(activity):
    gate = activity.value.get("gate")
    if not gate or gate not in HANDLERS:
        return error_card("unknown gate")
    handler = importlib.import_module(HANDLERS[gate]).handle
    return await handler(**activity.value)
```

### Step 5: Generate the audit-trail writer

`src/bot/cards/audit_trail.py` writes every gate outcome to Cosmos with this schema:

```json
{
  "id": "audit-{uuid}",
  "case_id": "...",
  "gate": "approve | edit-and-approve | reject | escalate | signoff | audit-view | request-info",
  "decision": "approved | declined | cancelled | escalated_to | acknowledged | viewed | requested",
  "actor": {"upn": "...", "displayName": "..."},
  "timestamp": "ISO 8601",
  "linked_rules": ["BR-001", "BR-007"],
  "agent_proposal": {...},
  "human_edits": {...},     // only for edit-and-approve
  "rationale": "..."        // only for reject / edit-and-approve
}
```

This audit trail powers:
- The workspace UI's audit viewer (see `threadlight-workspace-ui`)
- The continuous-eval KPIs (see `foundry-evals` continuous loop)
- Regulator-facing reports (compliance team queries Cosmos directly)

### Step 6: SLA timeouts

For gates with a `Timeout/SLA` in spec § 8:

- Generate a scheduled ACA job (via `threadlight-event-triggers`) that scans
  for un-acted-on cases past their SLA
- The job posts an `escalate` card to the escalation target
- Records a "SLA breach" audit event

---

## Card content rules

- **One card = one decision.** Don't bundle approve+edit+reject in one card.
- **Always show linked BR-XXX.** Auditor needs to see which rules drive
  this decision point.
- **Never include free-form chat in an action card.** That's a different
  surface (chat inside Teams).
- **Always include case-id.** The handler needs to round-trip it.
- **Use Adaptive Cards 1.5+.** Older versions lack `Input.ChoiceSet`'s
  `wrap` and `Action.Submit`'s `data` shape we depend on.

---

## SLA + escalation pattern

Gates with SLAs need a follow-up watcher:

```
spec § 8 says: "Approve within 4h, otherwise escalate to manager"
       ↓
ACA Job (cron */15 min): scan Cosmos for cases where:
  status='awaiting_approval' AND created_at < now() - 4h
       ↓
For each match:
  1. Write audit event "SLA breach"
  2. Post `escalate` card to manager (using the same gate plumbing)
  3. Mark case as 'escalated'
```

The watcher is generated by `threadlight-event-triggers` based on the SLA
declarations harvested by this skill.

---

## Reference files

| File | Purpose |
|------|---------|
| `references/cards/approve.json` | Canonical approve card template |
| `references/cards/edit-and-approve.json` | Canonical edit-and-approve card template |
| `references/cards/reject.json` | Canonical reject card template |
| `references/cards/escalate.json` | Canonical escalate card template |
| `references/cards/signoff.json` | Canonical signoff card template |
| `references/cards/audit-view.json` | Canonical audit-view card template |
| `references/cards/request-info.json` | Canonical request-info card template |
| `references/audit-schema.md` | Full audit-trail JSON schema |
| `references/sla-watchers.md` | How SLA watchers wire to `threadlight-event-triggers` |

---

## Anti-patterns

- ❌ **Don't put business logic in the card.** Cards are display + intent
  capture. Logic lives in the handler module.
- ❌ **Don't skip audit trail** — even for `audit-view` (the act of viewing
  is itself auditable).
- ❌ **Don't reuse one card for multiple gates** — each gate has different
  field requirements and audit semantics.
- ❌ **Don't ship without SLA watcher** when spec § 8 declares an SLA. A
  card without a watcher is a card that silently misses its deadline.
- ❌ **Don't hardcode actor lists for `escalate`** — read them from
  AGENTS.md or a config file so they evolve with the org.

---

## See Also

| Skill | Use When |
|-------|----------|
| [`threadlight-design`](../threadlight-design/) | Produces the spec § 8 + § 8b that drive gate selection |
| [`foundry-teams-bot`](../foundry-teams-bot/) | Hosts the bot infrastructure that delivers cards |
| [`threadlight-workspace-ui`](../threadlight-workspace-ui/) | Renders the same gates inside the operator workspace |
| [`threadlight-event-triggers`](../threadlight-event-triggers/) | Generates the SLA watcher ACA job |
| [`foundry-evals`](../foundry-evals/) | Reads the audit trail to compute continuous-loop KPIs |
