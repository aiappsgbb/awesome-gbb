# Customer goal - foundry-agentops smoke.

You are a developer on a customer team. Prove that the future
`foundry-agentops` skill works end-to-end against the shared CI Foundry
project by onboarding one temporary Foundry prompt agent into an isolated
temporary workspace, running one AgentOps analysis/eval/evidence cycle, and
cleaning up the temporary assets.

**This is a self-contained EXECUTION smoke, not a catalog-inspection task.**
Read `skills/foundry-agentops/SKILL.md` before acting. If that file does not
exist yet, treat the contract as unresolved: set `failure_reason` to
`missing skills/foundry-agentops/SKILL.md`, skip all later steps, and finish
with the FAIL marker in Step 8.

**CRITICAL - never invoke `copilot` recursively from a Bash tool.** You ARE the
running Copilot CLI process. Do NOT run `copilot -p ...`, `copilot --version`,
`npm install -g @github/copilot`, or any other `copilot ...` command. The
workflow already captures your output through its outer `tee`; execute the
smoke steps directly.

**Hard scope guardrails.** Do NOT generate any Threadlight manifest or files.
Do NOT modify APIM, Citadel, RBAC, networking, branch protection, GitHub
environments, or environment approvals. Do NOT create or edit workflow files.
Do NOT provision shared infrastructure. This smoke is limited to:

1. reading the `foundry-agentops` and `foundry-prompt-agents` skill contracts,
2. creating one temporary prompt agent with a UUID suffix,
3. creating one isolated temporary AgentOps workspace,
4. running one AgentOps analyze/eval/doctor cycle there,
5. deleting the temporary prompt agent and local workspace,
6. writing exactly one marker file.

---

## Step -1 - Acknowledge the skill contract (mandatory FIRST action)

Your first Bash action must be:

```bash
echo "skills/foundry-agentops/SKILL.md"
```

This lightweight line is the workflow's audit breadcrumb. Do not substitute a
different path and do not skip the later real `SKILL.md` read.

---

## Step 0 - Auth context (show, do not assert)

Print the auth context for the run log. Do not gate flow on the Azure CLI cache
check - Copilot CLI subprocesses do not always inherit `~/.azure/`.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
az account show --output table || echo "(az cache not inherited - relying on DefaultAzureCredential)"
```

If any required variable above prints empty, stop the run, set
`failure_reason` to `auth context missing: <var-name>`, and finish with the
FAIL marker in Step 8.

Do NOT run `command -v`, `find /`, or `curl -fsSL` to hunt for tooling. Use
the preinstalled `python3`, `pip`, and `az` already on the runner.

---

## Step 1 - Read the source-of-truth skill contracts

Before writing any code or creating any resource:

1. Read `skills/foundry-agentops/SKILL.md`.
2. Read `skills/foundry-prompt-agents/SKILL.md` because this smoke creates and
   later deletes a temporary prompt agent using that dependency contract.

If either file is missing, unreadable, or conflicts with the hard guardrails
above, stop immediately, set `failure_reason` to the shortest precise reason,
and finish with Step 8. Do NOT improvise from training data when the skill
contracts are available.

---

## Step 2 - Create isolated local workspace and install the exact AgentOps pin

Create a per-run workspace with a short UUID suffix so parallel runs do not
collide. The workspace must be disposable and isolated from the repository
checkout; do not write AgentOps artifacts into the tracked repo.

Suggested names:

- workspace: `/tmp/foundry-agentops-<uuid>`
- prompt agent: `ci-smoke-agentops-pa-<uuid>`

Inside that workspace:

1. create a virtual environment,
2. upgrade `pip`,
3. install **exactly** `agentops-accelerator==0.14.0`,
4. if the `foundry-prompt-agents` skill requires Azure SDK helpers for prompt
   agent creation, install only the bounded packages and versions that skill
   documents - do NOT widen or replace the `agentops-accelerator==0.14.0` pin,
5. persist the UUID, workspace path, and requested prompt-agent name so later
   Bash calls can reuse them.

If the exact AgentOps install fails, set `failure_reason` to
`agentops install failed` and finish with Step 8.

---

## Step 3 - Create one temporary Foundry prompt agent (UUID-suffixed)

Using the `foundry-prompt-agents` contract, create exactly one temporary prompt
agent in the CI Foundry project at `$FOUNDRY_PROJECT_ENDPOINT`.

Requirements:

- The name MUST include the same short UUID suffix from Step 2.
- Use a chat-capable deployment already present in the project (the current CI
  baseline uses `gpt-5.4-mini`).
- Keep the instructions deterministic so one eval row can succeed repeatably.
  Recommended instructions: `Reply with exactly PASS and nothing else.`
- Capture the resolved agent name and version returned by Foundry and persist
  them for later steps.

If agent creation fails, set `failure_reason` to `prompt agent create failed`
and finish with Step 8.

---

## Step 4 - Create the minimal valid AgentOps workspace contract

In the isolated workspace, create the smallest valid release-gate setup for
that exact prompt agent and exactly one dataset row.

You MAY use `agentops init --no-prompt` to scaffold `.agentops/` support files,
but the final checked config at the project root must be a minimal
`agentops.yaml` for the exact created agent and dataset path:

```yaml
version: 1
project_endpoint: "<value of $FOUNDRY_PROJECT_ENDPOINT>"
agent: "<resolved-agent-name>:<resolved-agent-version>"
dataset: .agentops/data/smoke.jsonl
```

Then write exactly one JSONL dataset row at `.agentops/data/smoke.jsonl`. Keep
it minimal and deterministic. A valid example is:

```json
{"id":"smoke-1","input":"Reply with exactly PASS and nothing else.","expected":"PASS"}
```

Do not add extra rows, Threadlight files, workflow files, or deployment
artifacts. If `agentops.yaml` or the dataset row cannot be created, set
`failure_reason` to `agentops workspace contract failed` and finish with
Step 8.

---

## Step 5 - Run `agentops eval analyze --format json`

From the isolated workspace, run:

```bash
agentops eval analyze --format json
```

Requirements:

- the command must succeed,
- the JSON payload must parse cleanly,
- `version == 1` must hold.

Persist the JSON output for the run log or later inspection if helpful. If the
analyze command errors, the JSON is invalid, or `version != 1`, set
`failure_reason` to `eval analyze contract failed` and finish with Step 8.

---

## Step 6 - Run one eval and verify `.agentops/results/latest/results.json`

Run exactly one AgentOps evaluation for the temporary prompt agent.

Requirements:

- use the isolated workspace from Step 2,
- allow AgentOps' public eval exit-code contract:
  - `0` = succeeded and thresholds passed,
  - `2` = succeeded and thresholds failed,
  - `1` = runtime/configuration error.
- Treat exit codes `0` and `2` as acceptable for this smoke because the proof
  is the artifact contract, not a guaranteed quality pass.
- After the run, require `.agentops/results/latest/results.json`.
- Parse that file and assert:
  - `version == 1`
  - `summary.overall_passed` exists and is a boolean

If the eval command exits `1`, the results file is missing, the JSON is
invalid, `version != 1`, or `summary.overall_passed` is not a boolean, set
`failure_reason` to `eval results contract failed` and finish with Step 8.

---

## Step 7 - Run `agentops doctor --evidence-pack`

From the same isolated workspace, run:

```bash
agentops doctor --evidence-pack
```

Requirements:

- accept Doctor's public exit-code contract (`0` or `2` are acceptable, `1` is
  not),
- require `.agentops/release/latest/evidence.json`,
- parse that file and assert `version == 1`.

If the command exits `1`, the evidence file is missing, the JSON is invalid, or
`version != 1`, set `failure_reason` to `doctor evidence contract failed` and
finish with Step 8.

---

## Step 8 - Teardown and deterministic marker contract

After the hard criteria in Steps 0-7 succeed, attempt cleanup before writing
the marker:

1. delete the temporary prompt agent created in Step 3 using the
   `foundry-prompt-agents` contract,
2. delete the isolated local workspace from Step 2.

Do not broaden cleanup scope beyond those two temporary assets. Never delete or
modify shared CI infrastructure, RBAC, APIM, networking, or GitHub policy
objects while cleaning up.

If either or both cleanup actions fail after the hard criteria succeeded, print
exactly one concise `NOTE:` line to stdout naming the leftover prompt agent
and/or workspace, still finish this step, and still write the byte-exact PASS
marker below. Only a prior hard-criteria failure may write the FAIL marker. Do
NOT compensate by touching shared CI infrastructure, RBAC, APIM, networking, or
GitHub policy objects.

### Final action (MANDATORY, deterministic)

Write exactly one marker file as your FINAL Bash action:

On success:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-agentops-smoke-result
```

On failure:

```bash
printf 'SMOKE_RESULT=FAIL %s\n' "$failure_reason" > /tmp/foundry-agentops-smoke-result
```

The marker-file write is the single source of truth. Do not print the literal
marker token anywhere else in your reply.
