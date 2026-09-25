# Compaction and selective recovery

Keep durable execution state separate from the runtime's conversation summary.
The ledger makes recovery possible; it does not control the summarizer or
remove tokens from an already loaded context. No hooks or watchdogs are needed.

## Native controls and limits

The [GitHub Copilot CLI context guide](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/context-management)
documents these interactive commands (checked 2026-09-23):

| Control | Purpose |
|---|---|
| `/context` | Inspect usage split across messages, instructions and tool definitions |
| `/compact` | Request manual conversation compaction |
| `/session checkpoints` | List native compaction summaries |
| `/session checkpoints N` | Inspect one relevant summary when a detail is missing |

These are user-facing CLI commands, not shell commands or tools available to
every agent. Verify support in the current host before recommending them.
Do not assume Copilot App or VS Code exposes the CLI controls. If the agent
has no supported compaction action, ask the user to use the host control;
report it unavailable if the host provides none. Never spawn a nested Copilot
process, inject keystrokes, or edit runtime-managed history/checkpoint files.

The guide describes background compaction around 80% usage and waiting around
95% if compaction has not finished; these are approximate runtime defaults,
not thresholds this skill can set. The
[Copilot SDK documentation](https://github.com/github/copilot-sdk/blob/main/dotnet/README.md)
exposes `BackgroundCompactionThreshold` and `BufferExhaustionThreshold` for
applications that create SDK sessions. They are not portable CLI/App settings.
Changing when compaction starts does not control summary size or fidelity.

Compaction mainly compresses conversation history. If instructions or tool
definitions dominate `/context`, repeated compaction will not remove that fixed
cost. Report the measured breakdown and ask for an authorized configuration
review; do not disable tools or rewrite global instructions automatically.

## Prepare once at a useful boundary

For delegated work, first apply [children.md](children.md): reconcile returned
results into the parent's ledger without forwarding transcripts. Keep active child
handles, dependency gates, ownership and unaccepted receipts in the latest snapshot.
Preserve blocker `blocks`/`does_not_block` boundaries, any declared limits,
accepted change IDs and the affected evidence delta, not copies of unchanged proofs.
Do not compact away the only copy of a receipt before its parent write is read back.

1. Prefer a phase boundary or actual context pressure, not a timer or every turn.
   Capture usage before compaction if the host exposes it; otherwise mark it
   unknown. Do not infer exact token counts from text length.
2. Append one complete snapshot using the existing store and work ID. Keep
   `goal`, `done_when`, `plan_ref`, `plan_revision`, current `context`, verified
   results and evidence references, `avoid`, `pending_operations`, and
   `next_action`. Include binding user decisions/constraints in the relevant
   fields; preserve unresolved uncertainty and retry conditions.
3. Read back that revision. Leave a small recovery pointer in the existing
   plan/handoff: actual store location/type, work ID, revision and the next
   action. No second mutable state document. Protect private paths from public
   commits. For session SQL, record the owning session; it may not be accessible
   from another session.
4. If an external operation is still running, preserve its real handle and
   supported status lookup. A compaction does not cancel it, prove it failed,
   or authorize a replacement. Do not interrupt a mutation just to compact.

Use `observation` or `pause` for preparation, not `progress`: bookkeeping and
compaction alone do not advance the deliverable or reset the no-progress budget.

## Compact, then restore selectively

Use one supported native compaction request. Do not claim success without the
host's completion signal. A stuck compaction is a runtime blocker; the skill
cannot preempt it. Do not loop on requests or treat an initial wait as a timeout.

After completion (or when recovering from an automatic compaction):

1. Read the **latest** snapshot for the work ID, not just the revision in an old
   pointer. The fallback command below omits historical events:

   ```bash
   python3 "$SKILL_ROOT/scripts/ledger.py" \
     --db "$SESSION/files/progress-guard.sqlite" read --work EXISTING-TODO-ID --recent 0
   ```

   Resolve `SKILL_ROOT` and `SESSION` as in [storage.md](storage.md).
   With native SQL, query `progress_guard_current` for that work ID only.
2. Check current user intent, actual branch/commit and working-tree changes,
   plan revision, and unresolved operations through their supported read paths.
   Preserve failed attempts and active-work accounting; offline/user waiting
   time is not active effort. A summary never overrides newer user instructions.
3. Load only evidence needed for the next decision. If a specific fact is
   missing, retrieve the relevant event/file range or one native checkpoint.
   Do not dump all events, full logs or every checkpoint into the new context.
   The snapshot is a claim to verify, not proof of the referenced result.
4. Resume the next bounded action. If usage is observable, compare before/after
   with the same model and context capacity. If not, report token savings as
   unknown. Fewer tokens alone are not success if essential decisions were lost.

One consolidation can cover several already-returned children; do not wait for
unrelated children just to compact, or run a compaction per progress message.
Losing repeated narration is desirable; losing a live assignment or safety gate
is not. "Aggressive" means minimal sufficient recovery context, not undocumented
runtime settings or repeated compaction calls.

## When a fresh session is safer

If summaries repeatedly lose critical constraints or compaction fails without
useful recovery, stop that branch and propose a fresh-session handoff. Do not
create one automatically or clear the current conversation.

On user approval, transfer a compact snapshot with parent work/revision,
evidence references, failed hypotheses and unresolved operation handles. Confirm
the receiver can actually access needed evidence; do not assume session files
are copied, synced or readable across hosts. The receiver uses its own ledger,
revalidates state and carries the remaining recovery budget, rather than sharing
the parent's writable database or starting exhausted attempts over.
If the ledger is unavailable, disclose degraded recovery and use the existing
plan/checkpoint; never invent missing history.

## Acceptance, not a performance promise

Use synthetic data in a disposable session. Fix the task and acceptance criteria
before the trial. Record runtime/version/model, available controls, before/after
usage if exposed, the actual completion signal, the readback and next action.
Check that user constraints, failed attempts and unknown operations survive
without reloading the full history or duplicating work. Compare against the same
scenario without this protocol when claiming an improvement.

The [scenario list](../tests/scenarios.md) is not executed evidence. Local helper
tests prove output selection, not native compaction, agent compliance, or speed.
