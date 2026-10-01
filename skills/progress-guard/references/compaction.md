# Compaction and selective recovery

The ledger preserves execution state; it cannot control the runtime summarizer,
remove loaded tokens or guarantee faithful summaries. No hooks/watchdogs needed.

## Native controls and limits

The [Copilot CLI context guide](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/context-management)
documents `/context`, `/compact`, `/session checkpoints` and
`/session checkpoints N` (checked 2026-09-23). These are interactive CLI commands,
not shell commands or portable App/VS Code tools. Check the current host's support.
Without an agent action, ask for the user's supported control; if none exists,
report unavailable. Never spawn nested Copilot, inject keys or edit runtime history.

The guide's approximate 80% background/95% waiting defaults are not skill settings.
The [SDK thresholds](https://github.com/github/copilot-sdk/blob/main/dotnet/README.md)
apply to applications creating SDK sessions, not portable CLI/App configuration.
Compaction mainly compresses history, not fixed instructions/tools. If those
dominate measured usage, request authorized configuration review instead of repeated
compaction or automatic tool/global-instruction changes.

## Prepare once at a useful boundary

Prefer actual context pressure or a consolidation boundary, not a timer.
Persist one event and complete compact snapshot if current state is not already
recorded. Preserve goal/acceptance, plan revision, context, decisions/authority,
evidence pointers, failed hypotheses, retry conditions and unresolved handles.
Successful append confirmation suffices; do not require a full readback per write.
If persistence is uncertain, resolve it before discarding the only receipt.
Keep a recovery pointer (store/session, work ID, revision, next action) in the
existing plan/handoff, not a second mutable state document or public private path.

For delegation, preserve `execution_role`, all active handles/ownership, receipt
revisions/dispositions, accepted change IDs, blocker boundaries and next routing
decision. Restore these under [children.md](children.md), not a pasted protocol.
Compaction itself neither grants consent nor reopens an unchanged question,
resumes a stopped child, resets failure history or authorizes role change.
Running effects retain their handles/lookups; compaction neither cancels them nor
authorizes replacement. Preparation is observation/pause, not delivery progress.

## Compact, then restore selectively

Use one supported native request and its actual completion signal. A stuck call is
a runtime blocker, not a reason to loop or treat initial wait as timeout.
After manual or automatic compaction:

1. Read the latest snapshot, not only an old pointer's revision:

   ```bash
   python3 "$SKILL_ROOT/scripts/ledger.py" \
     --db "$SESSION/files/progress-guard.sqlite" read --work EXISTING-TODO-ID --recent 0
   ```

   Resolve paths as in [storage.md](storage.md); native SQL reads
   `progress_guard_current` for that work ID.
2. Restore the role and ownership before the next action. Reconcile actual user
   intent, plan/source changes, decisions and UNKNOWN through supported lookups.
   Preserve active-effort accounting; user/offline waiting is not work.
3. Retrieve only evidence needed for the next decision, using a relevant event,
   file range or checkpoint if missing. Snapshot claims are not automatic proof.
4. Resume the bounded action. Compare observed usage only with the same model and
   capacity; otherwise savings are unknown. Do not infer token counts from text
   length. Fewer tokens do not compensate for lost constraints or duplicate work.

Consolidate already-returned children together where useful; do not wait for
unrelated work or compact per message. No frequency or compression promises.

## When a fresh session is safer

If compaction fails without useful recovery or repeatedly loses critical facts,
stop that branch and propose an approved fresh-session handoff, not automatic
creation or history clearing. Transfer compact state, provenance, failures, limits
and unresolved handles. Verify receiver access to evidence; sessions/hosts may not
share files. The receiver owns its ledger and retains exhausted attempts, not a
fresh recovery budget. If the store is unavailable, disclose degraded recovery and
use retained plan/checkpoint evidence without inventing history.

## Acceptance, not a performance promise

The [scenarios](../tests/scenarios.md) are unexecuted behavioral criteria.
For an authorized trial, fix task/acceptance beforehand; record runtime/model,
controls, completion signal, recovered state/next action and actual usage if exposed.
Check retained authority, ownership, failures and UNKNOWN without duplicate work.
Use the same scenario for comparisons. Static/helper tests prove neither native
compaction, agent compliance nor speed.
