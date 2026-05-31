# Customer goal — `foundry-prompt-agents` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-prompt-agents`
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

Using the `foundry-prompt-agents` skill, build a prompt agent that
classifies inbound customer-support messages into one of three categories:
`billing`, `technical`, `account`. Then prove it works by sending one test
message through it and verifying the response is one of those three labels.
When you're done, tear down everything you created.

Foundry project endpoint: `$AZURE_AI_ENDPOINT`
Model deployment available in that project: `gpt-5.4-mini`

The skill's `SKILL.md` is the source of truth for which SDK to use, how to
authenticate, how to construct the agent, how to invoke it, and how to clean
it up. Read it before you write any code. If the skill's instructions
conflict with anything you remember from training data, the skill wins.

Give every Azure resource you create a CI-safe name that includes a short
UUID suffix (Pattern 15.3) so parallel runs don't collide. Suggested pattern:
`ci-smoke-pa-$(uuidgen | cut -c1-8)`.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after cleanup — is to invoke the Bash tool to write the
marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded.

On success (all of: agent created, test message returned a valid label,
agent deleted):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-prompt-agents-smoke-result
```

On ANY failure (auth, skill not found, SDK error, invalid response, cleanup
failure):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-prompt-agents-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
