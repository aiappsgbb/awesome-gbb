# Customer goal — `foundry-prompt-agents` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-prompt-agents`
skill works end-to-end against your CI Foundry project.

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Azure SDK — read the skill's `SKILL.md` first, and follow
its documented contract.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You are the running consumer. Execute the steps directly; do not launch another
Copilot process, install Copilot, or overwrite the workflow-owned transcript.
Never edit tracked source/tests to recover from a failure.
Never print, save or inspect bearer tokens, including token prefixes. Use only
the SDK credential chain below. A tool permission denial is not an Azure
authorization diagnosis: stop with FAIL, without REST/CLI fallback, changing
credentials, moving files, or trying another form of the denied operation.

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

First exercise the documented constructors in the exact declared SDK cohort.
Run these commands from the workspace; use the same interpreter for the live
smoke below. A model import or wire-shape failure is a failure, not permission
to upgrade the SDK or alter the tests.

```bash
set -euo pipefail
python3 -m venv .scratch/foundry-prompt-agents/sdk24
source .scratch/foundry-prompt-agents/sdk24/bin/activate
python -m pip install -r skills/foundry-prompt-agents/tests/requirements.txt
python -m unittest discover -s skills/foundry-prompt-agents/tests -v
```

These offline checks cover tool construction, not live Fabric/Work IQ/browser
access. Do not provision those dependencies or claim their live acceptance as
part of this classifier smoke.

Using the `foundry-prompt-agents` skill, build a prompt agent that
classifies inbound customer-support messages into one of three categories:
`billing`, `technical`, `account`. Then prove it works by sending one test
message through it and verifying the response is one of those three labels.
When you're done, tear down everything you created.

Foundry project endpoint: `$FOUNDRY_PROJECT_ENDPOINT`
Model deployment available in that project: `gpt-5.4-mini`

The skill's `SKILL.md` is the source of truth for which SDK to use, how to
authenticate, how to construct the agent, how to invoke it, and how to clean
it up. Read it before you write any code. If the skill's instructions
conflict with anything you remember from training data, the skill wins.

Execute the canonical SDK program once. It owns UUID-named resources, checks
real output and verifies deletion. Do not author another smoke or inspect
installed package internals. Activate the same declared venv in this tool call,
then use `python` (do not directly invoke a venv path or change interpreters):

```bash
set -euo pipefail
source .scratch/foundry-prompt-agents/sdk24/bin/activate
python skills/foundry-prompt-agents/test-fixture/prompt_smoke.py
```

If the command is denied, write the failure marker and stop. Do not infer
that Azure writes were denied when no SDK request ran.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

The canonical program writes the byte-exact marker only after a valid label
and verified conversation/agent-version deletion. Its exception path writes
FAIL with the sanitized error type. That invocation is your final action;
do not independently overwrite its marker or claim success from prose.

If an earlier step or the tool invocation itself fails before the program runs,
your final action is:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-prompt-agents-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. Never alter the canonical program,
tests or result oracle to obtain PASS.
