---
name: progress-guard
description: >
  Execution memory and bounded recovery without planning bureaucracy. USE FOR:
  long-running or multi-phase work, repeated failed attempts, stalled tools, plan
  changes, resumption after compaction, handoffs, stopping rabbit holes, reviewing
  real progress, or maintaining an execution ledger. DO NOT USE FOR: straightforward
  short tasks, autonomous supervision, or interrupting in-flight tool calls.
metadata:
  version: "1.1.0"
---

# Progress guard

Make useful progress, not more process. This is an execution-memory and recovery
protocol, not a planner, autonomous supervisor, or tool-call watchdog.

## Start small

1. Reuse the current plan and todo IDs. Do not create a competing plan, launch
   agents, or interview the user just to initialize this skill.
2. For complex work, choose one store using [storage.md](references/storage.md).
   Read the current snapshot if present. If absent, seed it from confirmed facts
   and mark unknowns; never reconstruct a fictional history.
3. Record the requested outcome, completion evidence, plan revision, relevant
   environment/commit, verified results, blocker, next action and abandon condition.
   Then execute. The first useful action must not wait for a perfect ledger.

Simple tasks need no ledger. Activate later if they become complex or stall.
Follow existing authorization, policy and safety requirements; this skill grants
no permission to bypass checks, edit protected repos or interrupt other work.

## Evidence, not activity

Progress is a verified deliverable increment, a reproducible failure, or a
discriminating observation that eliminates an hypothesis and changes the next action.
Reference the actual test output, file, operation ID or observed result and its context.

Not progress: another plan, rephrased hypothesis, status message, retry, agent launch,
log entry, commit without demonstrated value, or an unchanged "running" status.
Never mark a whole task done because one partial check passed.

Keep **delivery progress** distinct from **diagnostic learning** in verified entries.
At phase boundaries ask whether learning is still converging on delivery. Several
interesting discoveries can still be a rabbit hole.

## Record only meaningful boundaries

Append one event and a compact complete snapshot when:
- a test changes what is known, or an approach fails;
- a user decision changes scope, priorities or the plan;
- a milestone is verified, a blocker appears, or work pauses/hands off;
- starting a long-running or externally mutating operation.

Before a risky/long operation, record intent, context and recovery lookup. After
launch record the tool's operation/session ID. After interruption, unresolved intent
means **unknown outcome**, not failure: inspect the real system before retrying.
Do not claim the ledger write and an external operation are atomic.

Reuse the native history for routine calls. No screenshots, transcripts, secrets,
tokens, or large logs inside the ledger; store local evidence references.
Keep the current snapshot roughly within 1,000 tokens; retrieve relevant older events
by work ID when needed instead of loading everything.

## Read before acting

Read the snapshot after resume/compaction, before repeating an attempt, at a phase
boundary, after a material user correction, and before completion or handoff.
No mandatory reread before every tool call.

- Check applicable "do not retry unless" findings.
- Check context freshness: changed commits, identities, environments or requirements
  may invalidate conclusions. Preserve history and append a correction.
- Compare the actual plan with plan_ref/plan_revision. Reconcile user edits; never
  rewrite the plan to justify work already performed.
- Distinguish verified, implemented-but-unverified, pending, blocked and superseded
  work using existing todos plus snapshot facts.
- Latest user requirements and current evidence outrank a stale snapshot.

## Compaction and selective recovery

When context pressure or repeated summarization threatens continuity, follow
[the compaction protocol](references/compaction.md): save verified state, use
the host's native control if available, then read only the current snapshot
and evidence needed for the next action. Preserve decisions, user constraints,
failed approaches and unresolved operation handles, not whole transcripts.

The ledger is external memory, not a context-window control. Writing it does
not evict loaded messages, configure runtime thresholds, or guarantee a faithful
summary. Do not compact repeatedly without measured benefit or claim to have
compacted merely because a snapshot was written.

## Stall triggers

Review the approach as soon as any of these occurs:
- Two failed attempts of the same underlying hypothesis without new evidence.
- Re-reading, re-planning, or rerunning checks without a decision-changing result.
- Work drifting from the requested outcome, even while local tests pass.
- An external operation exceeds its expected bound with no observable advancement.
- About 15 minutes of active work without meaningful progress.

Time is a secondary backstop, not a demand to abandon healthy long jobs.
Estimate active no-progress time from actual timestamps; exclude time waiting for
the user or an inactive session. Include unproductive execution/waiting while work
was meant to proceed. Disclose unknown timing; use behavioral triggers instead.
Do not infer continuous work from time since the last event.

## Recovery: one short decision, then action or stop

Compare the requested result with the last verified state. Identify the assumption
keeping this approach alive. Choose ONE:
1. Run the cheapest bounded test that can disprove it.
2. Switch to a genuinely different, authorized approach.
3. Ask for the missing decision, scope tradeoff or access.
4. Stop with a blocker and a useful partial handoff.

State the expected evidence and the condition for abandoning the recovery.
No new research program, review panel, replacement agent or planning recursion.
If this recovery produces no useful evidence, stop this branch and ask the user.
Also escalate by about 30 active minutes without progress, or an earlier user limit.
If no answer channel is available, mark needs_decision and stop this branch.
Silence, autopilot mode, "continue", and old blanket authorization are not permission
to repeat exhausted attempts; resume them only with a concrete changed condition.

An explicitly bounded alternative approved by the user may proceed. Preserve the
failed history; do not reset a budget by renaming work or opening a child session.
Independent authorized work may continue if it cannot affect the blocked operation.

User-facing escalation, in the user's language:
"Blocked on X. Last verified result: Y. Tried A/B; evidence Z. I recommend C
because it tests D. Decision needed: [one concrete choice]."
Report elapsed time only if known. Never substitute "still working" for this.

## Tools and children

Use real operation deadlines where supported. A tool's initial wait/async response
is NOT a timeout or cancellation. Follow tool-specific waiting rules; no polling
loops, duplicate long calls, or rediscovery of known agent IDs.

An in-flight MCP call can block this protocol: no file, skill, or SQL trigger can
preempt it. Report that limit at the next opportunity. Never route around an excluded
tool. Stop only known owned processes when safe/authorized; do not cancel a cloud
mutation just because a timer elapsed.

One coordinator owns a work item's consolidated state. Children return bounded
outcomes and evidence, with inherited failed hypotheses and budgets. Do not share
one writable snapshot between agents. Verify child claims before marking completion.
Do not delegate merely to satisfy this skill.

## Finish

Verify against done_when and the current user-approved plan. Append completion with
evidence, or a partial/blocked handoff with unresolved operations and the next decision.
Do not introduce new infrastructure to perfect this bookkeeping.

Scope limits: the ledger preserves claims and provenance, not truth automatically.
Triggers protect storage consistency, not LLM compliance. No automatic hooks,
timers, background watchers or recurring sessions are installed by this skill.
