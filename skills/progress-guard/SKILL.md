---
name: progress-guard
description: >
  Execution memory and bounded recovery without planning bureaucracy. USE FOR:
  long-running or multi-phase work, repeated failed attempts, stalled tools, plan
  changes, resumption after compaction, child-session coordination, handoffs, stopping rabbit holes, reviewing
  real progress, or maintaining an execution ledger. DO NOT USE FOR: straightforward
  short tasks, autonomous supervision, or interrupting in-flight tool calls.
metadata:
  version: "2.1.0"
---

# Progress guard

Execution memory and bounded recovery, not a planner, supervisor or tool watchdog.
This skill grants no authority and installs no hooks, timers or background work.

## Start small

Ordinary solo work stays direct; loading this skill never requires a child.
Simple tasks need no ledger. For complex/stalled work, reuse the plan/todos and
one existing snapshot; initialize from confirmed facts only if absent.
Use [storage.md](references/storage.md) for the store and optional fields.
Do not delay useful work to perfect bookkeeping or create a competing plan.

If native discovery fails, read an accessible canonical SKILL.md once and record
the failure, fallback path/version and owning runtime. File loading is not native
discovery. Reuse that route after compaction.
Retry native discovery only after a concrete runtime/catalog change.
Children verify their own loading, not the parent's. Never route around a policy
denial; if no permitted source is available, report the blocker.

## Evidence, not activity

Progress is a verified deliverable increment, reproducible failure or observation
that changes the next action. Reference its source/context; distinguish delivery
from diagnostic learning and check that learning still advances the outcome.
Plans, retries, pings, launches, bookkeeping and unchanged status are not progress.
A passing component or child milestone is not usable end-to-end delivery.

## Record only meaningful boundaries

Append one event with a complete compact snapshot at meaningful decisions,
changed knowledge/failure, blocks, delivery, pause/handoff and uncertain external
operation boundaries. Reuse native history for routine calls; keep logs/artifacts
outside the ledger and store pointers, not transcripts or secrets.

Before long/risky operations, preserve intent, context and recovery lookup; retain
the returned handle. After interruption, UNKNOWN is not failure: reconcile actual
effects before retrying. Ledger writes and external effects are not atomic.
A successful append receipt is sufficient; no compulsory full readback after
every append. Read when recovery or uncertainty requires it, not as a ritual.

## Read before acting

Read current state after resume/compaction, before a retry, on changed inputs or
material user corrections, and for final acceptance/handoff. Reuse already-current
state within uninterrupted work. Check actual plan, role, ownership, decisions,
failed hypotheses/retry conditions and unresolved handles.
New user intent/evidence outranks stale state. Reuse accepted proof until affected
inputs change or inconsistency appears; check the relevant canonical index once
before declaring context missing. Do not hunt credentials or reread all artifacts.

## Compaction and selective recovery

Follow [compaction.md](references/compaction.md) when context pressure warrants it.
Preserve decisions, failures, active ownership and handles; restore only current
state and evidence needed for the next decision. A ledger write does not compact
history or control runtime thresholds. Do not repeat compaction without benefit.

## Stall triggers

Review after two failed attempts of the same hypothesis without new evidence,
repeated planning/reads without a changed decision, drift from the outcome, or a
long operation with no observable advancement past its expected bound.
Use about 15 active no-progress minutes to review and 30 to escalate. Exclude
user/offline inactivity; disclose unknown timing. These are no-progress backstops,
not task expiry, phase quotas or reasons to stop a healthy advancing operation.
Never invent token, turn or task budgets; explicit limits and real deadlines bind.

## Recovery: one short decision, then action or stop

Identify the blocking assumption. Choose one bounded discriminating test, a
different authorized approach, the missing user decision, or a blocked handoff.
State expected evidence and abandon condition; no replacement-agent/research loop.
If recovery adds no useful evidence, stop that branch and ask; if no answer channel
exists, record needs_decision. Silence, autopilot or "continue" cannot renew an
exhausted attempt. Resume only on concrete changed conditions/authorized alternative,
preserving failure history and cumulative declared limits, even across sessions.

An effect-free input/command correction may use the existing ONE bounded recovery
inside its mandate without a new phase approval. A missing operation ID alone
does not prove nothing happened. Reconcile UNKNOWN before replay.
Never override explicit retry/spend/time limits, permissions or exhausted recovery.
Escalate with the precise blocker, last verified result, attempted hypotheses,
evidence, recommended next action and one needed decision; elapsed time only if known.

## Tools and children

Match operation, target/increment and effect to the current mandate before asking
approval. Covered work proceeds; a genuinely new effect needs a decision.
See [approval reconciliation](references/children.md#reconcile-approval-before-asking)
at that boundary, not on every step. No duplicate phase approvals; silence is not
consent and implementation does not imply merge/cloud/release.

Initial waits are not timeouts. Follow native waiting/notification rules; no
duplicate calls or status polling merely to stay busy. A skill cannot interrupt
an in-flight MCP call: report that limit at the next opportunity. Never bypass
excluded tools or stop unknown/unowned operations; a timer does not authorize
cancelling a cloud mutation.

For authorized delegation, load [children.md](references/children.md), the sole
detailed assignment/receipt protocol. Persist coordinator/executor role.
A coordinator routes end-to-end assignments and decisions, accepts terminal
evidence and maintains the consolidated ledger; it does not implement, build/test,
deeply debug, integrate/merge or deploy. Route direct-work requests to a suitable
authorized executor, not a new child per step. Explicit role changes reconcile
live ownership and UNKNOWN first. Preserve one-process end-to-end constraints.

Children return one completed, failed or blocked result per assignment execution;
ordinary recovery and intermediate findings stay local. Genuine block resolution
and explicit resume permit a new terminal revision, not repeated unchanged reports.
Safety incidents, urgent cancellation and required permission/input gates remain
immediate exceptions; host-generated notifications cannot be suppressed.
Serialize actual shared writes/dependencies/capacity, not all service use.
UNKNOWN fences its effects and interfering work, not demonstrably independent
authorized tasks.

## Finish

Accept against the current user-approved outcome, not activity. Distinguish
implemented, locally verified, deployed and verified usable results. Append
completion evidence or a precise partial/blocked handoff with unresolved handles
and next decision. Coordinators assess relevant final proof, not duplicate execution.
Missing/inconsistent proof needs targeted clarification, not blind acceptance.
The ledger preserves claims and provenance; shape checks do not prove truth,
agent compliance or runtime behavior.
