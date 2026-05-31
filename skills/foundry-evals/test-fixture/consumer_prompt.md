# Customer goal — `foundry-evals` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-evals`
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

Using the `foundry-evals` skill, score one real assistant response with one
Foundry built-in evaluator and prove a numeric score came back.

The skill documents a two-phase invoke + score pattern: first invoke an
agent to capture a response, then run an evaluator over that response.
Create a minimal prompt agent for the invoke phase — per the
`foundry-prompt-agents` skill (declared as a cross-skill dependency in
`.github/skill-deps.yml`) — give it a single-sentence instruction like
"Answer the user's question in one short sentence", send it one trivial
prompt (e.g. `What is the capital of France?`), and capture the
assistant's reply.

Then use `foundry-evals` to score that prompt + response pair with ONE
built-in evaluator. Pick the cheapest single-turn evaluator the skill
documents (e.g. `coherence`, `relevance`, `intent_resolution`, or
`task_adherence`) — do NOT run the full suite. Verify the evaluator
returned a numeric score (any number is fine; this smoke is not asserting
quality, only that the eval pipeline returned a result).

Then delete the prompt agent.

Foundry project endpoint: `$AZURE_AI_ENDPOINT`
Model deployment available in that project: `gpt-5.4-mini` (use this for
both the agent under test AND the evaluator's judge model unless the
skill says otherwise).

The skill's `SKILL.md` is the source of truth for which SDK to use, how to
authenticate, how to configure the evaluator, how to feed it the
response, and how to read the score back. Read it before you write any
code. Also read `foundry-prompt-agents` `SKILL.md` for the agent
create / invoke / delete contract. If the skills' instructions conflict
with anything you remember from training data, the skills win.

Give every Azure resource you create a CI-safe name that includes a short
UUID suffix (Pattern 15.3) so parallel runs don't collide. Suggested pattern:
`ci-smoke-evals-$(uuidgen | cut -c1-8)`.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after cleanup — is to invoke the Bash tool to write the
marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded.

On success (all of: agent created, response captured, evaluator returned a
numeric score, agent deleted):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-evals-smoke-result
```

On ANY failure (auth, skill not found, SDK error, agent create/invoke
failed, evaluator returned no score, cleanup failure):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-evals-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
