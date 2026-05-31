# Customer goal — `foundry-memory` skill smoke

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
echo "AZURE_AI_ENDPOINT=${AZURE_AI_ENDPOINT:+set}"
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

Foundry project endpoint: `$AZURE_AI_ENDPOINT`
Model deployments available in that project: `gpt-5.4-mini` (chat),
`text-embedding-3-small` (embedding).

The skill's `SKILL.md` is the source of truth for which SDK to use, how to
authenticate, how to construct the memory store definition, how to write
and retrieve memories, and how to delete the store. Read it before you
write any code. If the skill's instructions conflict with anything you
remember from training data, the skill wins.

The skill documents both a `chat_model` and an `embedding_model` field on
the memory-store definition. The CI Foundry project at `$AZURE_AI_ENDPOINT`
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

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after cleanup — is to invoke the Bash tool to write the
marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded.

On success (all of: memory store created, fact written, retrieval returned
the fact, store deleted):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-memory-smoke-result
```

On ANY failure (auth, skill not found, SDK error, missing embedding model,
retrieval miss, cleanup failure):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-memory-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
