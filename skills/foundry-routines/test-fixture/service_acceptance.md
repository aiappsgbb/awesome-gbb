# Additional Routines service acceptance

These are unexecuted acceptance cases, not permission to create or enable
schedules. Keep the existing 2.4 consumer fixture intact. Obtain project,
caller, cost/expiry, cleanup and event-owner approval before a live run.
Use uniquely owned UUID-suffixed names and record all created resources
privately before moving to the next mutation. No recursive Copilot invocation.

1. **Temporal delivery versus manual dispatch.** Use an approved existing
   agent with a deterministic harmless task. Create a one-shot timer at an
   agreed future instant (or a schedule no tighter than five minutes).
   Record creation, then wait for a real delivery without manually dispatching
   in that observation window. Inspect `list_runs` and retain the run source,
   trigger, timestamps and downstream correlation handle. Next perform a
   manual dispatch and match its returned `dispatch_id` to a distinct history
   record. Its source can be `queued_dispatch` rather than `manual_dispatch`;
   do not reject a matching completed run merely because of that source label.
   Use a pre-agreed finite observation window; expiry is an unproven
   temporal path, never a PASS inferred from manual enqueue.
2. **Delivery versus business completion.** For both runs, record terminal
   delivery state and separately check the expected downstream output or
   durable application side effect. A queued dispatch, `completed` delivery,
   response ID or inaccessible/404 response is not output verification.
3. **Typed creator identity.** Use SDK 2.6.1 in the isolated management
   environment. Import `references/creator_routine.py` as a real module and
   create disabled under the approved creator. Verify saved authorization and
   disabled state before enabling. Test a harmless delegated tool under that
   creator with prior consent; retain actual-principal evidence. Repeat denial
   or revocation only with explicit consent-owner approval; failure must not
   fall back to agent identity. A service-principal CI run cannot stand in for
   human delegated consent.
4. **External events.** GitHub and Teams require separate approved connector
   scopes and consent. Cause one controlled issue/channel event, correlate it
   to history and downstream output, and verify no unrelated event triggered
   the routine. Do not infer this from timer or dispatch success.
5. **Private network and header variants.** On an approved private runner,
   prove the same delivery/invoke path with public access disabled. Record
   the exact client: 2.4 uses `Routines=V1Preview`; inspected 2.6.1 uses
   `Routines=V2Preview`. Test current header-free REST separately if publishing
   that route; do not remove SDK-injected headers to make a test pass.
6. **Retire.** Disable/delete only owned routines; confirm deletion through
   the supported get path (404 after successful authenticated transport).
   Clean owned agents/connections only if separately authorized. A failed
   auth/network lookup is not proof of deletion. Report residual inventory,
   owner and retention deadline if cleanup is blocked; do not start replacements.

Capture separate pass/fail/not-run entries for these surfaces. Preserve prior
SDK/CLI acceptance as historical evidence, not certification of these variants.
