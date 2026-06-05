# Customer goal — `foundry-memory` skill smoke
<!-- retest-trigger: 2026-05-31 post-Foundry-MI-RBAC-grant -->

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-memory`
skill works end-to-end against your CI Foundry project.

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Azure SDK — read the skill's `SKILL.md` first, and follow
its documented contract.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on any of these
checks — `azure/login@v2` already validated the credentials upstream.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If any env var prints empty, the workflow's `env:` block is broken (AGENTS.md
§ 9.7 Pattern 11). That is a workflow bug, not a skill bug. Write the FAIL
marker (Step 2) with reason `auth context missing: <var-name>` and stop.

---

## Step 1 — The goal

Using the `foundry-memory` skill, create a Foundry Memory Store, write one
small user-profile fact into it (`prefers metric units`), retrieve memories
for that same user back out, and verify the retrieval result references the
fact (either in a returned memory's content or in a summary of stored
profile attributes). Then delete the memory store.

Foundry project endpoint: `$FOUNDRY_PROJECT_ENDPOINT`
Model deployments available in that project: `gpt-5.4-mini` (chat),
`text-embedding-3-small` (embedding).

The skill's `SKILL.md` is the source of truth for which SDK to use, how to
authenticate, how to construct the memory store definition, how to write
and retrieve memories, and how to delete the store. Read it before you
write any code. If the skill's instructions conflict with anything you
remember from training data, the skill wins.

The skill documents both a `chat_model` and an `embedding_model` field on
the memory-store definition. The CI Foundry project at `$FOUNDRY_PROJECT_ENDPOINT`
has both deployed (names above). Pass those exact deployment names to the
memory-store definition. If either is missing (e.g. infra drift), probe via
`AIProjectClient`'s deployments collection or the Azure OpenAI REST
`/deployments` endpoint and write the FAIL marker with a clear reason
naming the missing deployment — do not invent one.

**Pattern 23 — RBAC propagation lag on brand-new deployments.** The CI
embedding deployment was created recently and Azure has documented 5-15
min RBAC/metadata propagation lag for new Cognitive Services deployments
(account-scope role assignments may not yet be visible to the deployment
endpoint even though `az role assignment list` shows them granted). The
visible symptom is a 401 from the embedding endpoint on the FIRST few
calls. The UAMI ALREADY has the correct roles (`Cognitive Services
OpenAI User` + `Foundry User` at account scope) — do NOT try to re-grant
them; that races propagation further. Instead, wrap the memory-store
write (the first call that exercises the embedding) in a retry loop:

- max 6 attempts
- 30 s sleep between attempts (3 min total budget)
- retry ONLY on 401 / 403 / "AuthenticationFailed" / "AccessDenied"
- on other errors, FAIL immediately with the original reason

If after 3 min you're still getting 401, the issue is NOT propagation —
write the FAIL marker with `embedding 401 after 3min retry budget — check
deployment auth`.

Give every Azure resource you create a CI-safe name that includes a short
UUID suffix (Pattern 15.3) so parallel runs don't collide. Suggested pattern:
`ci-smoke-mem-$(uuidgen | cut -c1-8)`.

---

## Step 1b — Procedural memory + TTL branch (v1.1.0 surface)

After the user-profile write+retrieve+delete completes, exercise the new
v1.1.0 surface against a **second** memory store. Use a new CI-safe name
(`ci-smoke-mem-<uuid>-proc`) so the two stores never collide.

1. **Create store2** with BOTH `procedural_memory_enabled=True` AND
   `default_ttl_seconds=30` on `MemoryStoreDefaultOptions`. Re-use the same
   `chat_model` + `embedding_model` deployments. The 30-second TTL is short
   on purpose so the leg can re-query after `time.sleep(35)` and observe
   eviction without blowing the Pattern 14 timeout budget.

2. **Submit one or two conversation turns** to `begin_update_memories` that
   contain a clear procedural pattern (for example: a turn where the agent
   says `"always confirm order ID before issuing a refund"` and the user
   acknowledges). Use scope `{"user_id": "ci-smoke-proc-<uuid>"}`.

3. **Exercise the new CRUD direct API** by calling
   `project_client.beta.memory_stores.list_memories(name=store2, scope=...)`
   right after submit. Confirm the call returns an iterable without error.
   This is the API-contract part of the §10 direct-API surface; it MUST
   succeed regardless of extraction timing.

4. **Poll `list_memories` for procedural extraction** every 15 seconds for up
   to 90 seconds total, looking for any item with `kind == "procedural"`.
   Record the observed count in the transcript.

5. **If at least one procedural memory was extracted in step 4:**
   - `time.sleep(35)` to cross the TTL boundary.
   - `list_memories` again. Pattern 13 soft-grace: allow up to 3 additional
     re-checks with a 10-second gap before failing — server-side expiry is
     eventually consistent.
   - If the procedural-item count drops to 0 → strict TTL PASS.
   - If the count is still > 0 after the grace re-checks → emit transcript
     NOTE `procedural_ttl_lag` and still PASS the branch (Pattern 13 — async
     surface, don't false-FAIL).

6. **If after 90 seconds no procedural items appeared (count == 0 at step 4):**
   - Emit transcript NOTE `procedural_extraction_lag_90s`.
   - The new-flag API contract (steps 1 + 3) already succeeded, so the
     branch is still PASS.

7. **Cleanup store2** via `project_client.beta.memory_stores.delete(name=store2)`.
   The call is idempotent and returns an object with `.deleted=True`. Per
   AGENTS.md § 9.7 Pattern 25, if this delete call fails, write a transcript
   NOTE naming the resource that wasn't cleaned and still PASS — the
   `rg-awesome-gbb-ci` janitor sweeps `ci-smoke-mem-*` weekly.

The HARD PASS conditions for this branch are: store2 created with both new
flags accepted, `list_memories` callable, store2 deleted (or NOTE'd per
Pattern 25). The post-TTL eviction observation is soft (Pattern 13).

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after cleanup — is to invoke the Bash tool to write the
marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded.

On success (all of: store1 created, user-profile fact written, retrieval
returned the fact, store1 deleted, store2 created with both
`procedural_memory_enabled=True` AND `default_ttl_seconds=30`,
`list_memories` callable against store2, store2 deleted [or cleanup
NOTE'd per Pattern 25]):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-memory-smoke-result
```

On ANY failure (auth, skill not found, SDK error, missing embedding model,
retrieval miss on store1, store2 create rejected for an unknown
`procedural_memory_enabled` / `default_ttl_seconds` field,
`list_memories` raised, store1 cleanup failure):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-memory-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.

Pattern 13 soft-PASS NOTEs (`procedural_ttl_lag`,
`procedural_extraction_lag_90s`, or a Pattern 25 cleanup NOTE) belong in
the transcript only — NEVER in the marker file. The marker line is the
exact 18 bytes `SMOKE_RESULT=PASS\n`; anything else is FAIL.
