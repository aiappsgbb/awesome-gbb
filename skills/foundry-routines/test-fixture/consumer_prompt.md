# Customer goal — `foundry-routines` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-routines` skill
works end-to-end against your CI Foundry project.

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Azure SDK — read the skill's `SKILL.md` first, and follow
its documented contract.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on any of these
checks — `azure/login@v2` already validated the credentials upstream
(AGENTS.md § 9.7 Patterns 11 and 17 — show, don't assert).

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If any env var prints empty, the workflow's `env:` block is broken
(Pattern 11). That is a workflow bug, not a skill bug. Write the FAIL
marker (Step 2) with reason `auth context missing: <var-name>` and stop.

---

## Step 1 — The goal

Using the `foundry-routines` skill, exercise the full routine lifecycle
end-to-end against the CI Foundry project. The skill wraps the PREVIEW
`client.beta.routines` surface introduced in `azure-ai-projects` 2.2.0,
so the test must prove the SDK surface is reachable AND that
create/dispatch/list all work against a live Foundry project.

Read `skills/foundry-routines/SKILL.md` before writing any code — it is
the source of truth for the SDK surface, action / trigger shapes, the
`Foundry-Features` header convention, and the limitations to design
around. If the skill's instructions conflict with anything you remember
from training data, the skill wins.

Foundry project endpoint: `$FOUNDRY_PROJECT_ENDPOINT`
Model deployment available in that project: `$FOUNDRY_MODEL_DEPLOYMENT`
(currently `gpt-5.4-mini`, in Sweden Central — which is a routines
preview region).

Give every Azure resource you create a CI-safe name that includes a short
UUID suffix (Pattern 15.3) so parallel runs don't collide. Suggested
patterns:

- prompt agent: `ci-smoke-routine-pa-$(uuidgen | cut -c1-8)`
- routine: `ci-smoke-routine-$(uuidgen | cut -c1-8)`

The lifecycle below is mandatory. Do not invent shortcuts; each step
proves a different part of the skill contract.

### Step 1a — Install the pinned SDK

In a fresh venv (or directly in the runner's site-packages, whichever
matches what the skill documents), install the pin:

```bash
pip install --quiet "azure-ai-projects~=2.2.0" "azure-identity~=1.25"
python -c "import azure.ai.projects as m; print(f'azure-ai-projects=={m.__version__}')"
```

Print the version line. If `azure-ai-projects` resolves to anything
below 2.2.0, `client.beta.routines` will not exist and the rest of the
fixture cannot proceed — FAIL with reason
`azure-ai-projects<2.2.0 — routines surface missing`.

### Step 1b — Create the prompt agent (target of the routine)

Per AGENTS.md § 9.7 Pattern 23 + this skill's § 7, routines need an
agent with a **configured agent identity**. A prompt agent published
via `project.agents.create_version(...)` qualifies. Pure prompt-only
agents without an agent identity are rejected by the routines service.

Create one with:

- `agent_name`: `ci-smoke-routine-pa-<uuid>` (capture the resolved
  `.name` for use in Step 1c)
- model: `$FOUNDRY_MODEL_DEPLOYMENT`
- instructions: `"Echo back the input verbatim. Do not embellish."`

Use `project.agents.create_version(...)` — the SDK shape is documented
in `skills/foundry-prompt-agents/SKILL.md` § 1. Capture and print:

- `agent.name`
- `agent.version`

If creation raises, FAIL with reason
`prompt agent create failed: <exception class> <first line of message>`.

### Step 1c — Create a RECURRING routine bound to that agent

Per the brief, use a **recurring schedule** with a cron expression that
will NOT auto-fire during the CI run window. The chosen cron is
`"0 0 1 1 *"` (midnight on January 1, UTC) — far enough in the future
that the routine cannot be triggered automatically while the fixture
is still running. The `dispatch()` call in Step 1d is the only
invocation path this fixture exercises.

Required trigger shape per SKILL.md § 3 (the schedule trigger requires
BOTH `cron_expression` AND `time_zone`):

```python
triggers = {
    "annual-anchor": {
        "type": "schedule",
        "cron_expression": "0 0 1 1 *",
        "time_zone": "UTC",
    }
}
```

Required action shape (Responses API target):

```python
action = {
    "type": "invoke_agent_responses_api",
    "agent_name": "<the .name captured from Step 1b>",
}
```

Create the routine with:

- routine_name: `ci-smoke-routine-<uuid>`
- description: `"CI smoke for foundry-routines lifecycle."`
- enabled: `True` (so `dispatch()` is accepted in Step 1d)
- the trigger + action above

Call `client.beta.routines.create_or_update(routine_name=..., ...)`.
Assert:

- `routine.name` equals the requested name
- `routine.enabled is True`

Print both. If either assertion fails OR the call raises, FAIL with
reason `routine create failed: <details>`.

### Step 1d — Manually dispatch the routine

`dispatch()` queues a one-off run without waiting for the schedule.
The `payload.type` MUST match the routine's `action.type` (anti-pattern
§ 9 in SKILL.md).

```python
result = client.beta.routines.dispatch(
    routine_name="<the routine name>",
    payload={
        "type": "invoke_agent_responses_api",
        "input": "Echo: live-routine-smoke",
    },
)
```

Capture and print:

- `result.dispatch_id`
- `result.task_id`
- `result.action_correlation_id`

Assert `result.dispatch_id` is non-empty (a truthy string). If empty
or absent, FAIL with reason
`dispatch returned empty dispatch_id`.

> **Note:** Whether the queued run actually completes a Responses API
> invocation against the prompt agent is **soft** for this fixture —
> the per-Pattern-13 reasoning is that the run executes asynchronously
> on Foundry's worker pool with documented eventual-consistency
> behaviour, and the queueing is what the dispatch contract proves.
> The hard contract is: the SDK call returned a valid
> `DispatchRoutineResult` with a non-empty `dispatch_id`. Do NOT
> poll `list_runs` and FAIL on no-run-yet within a tight window.

### Step 1e — List routines

Call `client.beta.routines.list()` and iterate. Assert the routine
name created in Step 1c appears in the listing.

```python
names = [r.name for r in client.beta.routines.list()]
assert "<routine name>" in names, f"routine not in list: {names}"
print(f"list-ok: {len(names)} routines visible to this project")
```

If the routine is missing, FAIL with reason
`routine not visible in list() after create`.

### Step 1f — Disable + delete the routine (best-effort, Pattern 25)

Disable first, then delete:

```python
client.beta.routines.disable("<routine name>")
client.beta.routines.delete("<routine name>")
print("routine-cleanup-ok: <routine name>")
```

If either call raises, capture the exception class + first line of the
message and emit a transcript NOTE:

```
routine-cleanup-note: <exception class> — <first line>
```

Then continue. **Do not FAIL** the marker on cleanup failure
(AGENTS.md § 9.7 Pattern 25 — teardown is soft after happy-path
success; the `rg-awesome-gbb-ci` janitor sweeps `ci-smoke-routine-*`
on a periodic schedule).

### Step 1g — Delete the prompt agent (best-effort, Pattern 25)

Per `foundry-prompt-agents` SKILL.md § 4, delete by **positional** args:

```python
project.agents.delete_version("<agent_name>", "<agent_version>")
print(f"prompt-agent-cleanup-ok: <agent_name> v<agent_version>")
```

If the call raises, capture the exception class + first line of the
message and emit a transcript NOTE:

```
prompt-agent-cleanup-note: <exception class> — <first line>
```

Then continue. **Do not FAIL** the marker on cleanup failure
(Pattern 25).

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after cleanup — is to invoke the Bash tool to write
the marker file. The file's literal byte content is what CI grades;
your assistant-text reply is NOT graded.

On success (Step 0 + Steps 1a through 1e all passed; 1f and 1g are
best-effort per Pattern 25):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-routines-smoke-result
```

On ANY failure in Step 0, 1a, 1b, 1c, 1d, or 1e (auth context missing,
SDK below 2.2.0, prompt agent create failed, routine create failed,
dispatch returned empty `dispatch_id`, routine missing from `list()`):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-routines-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal string. The Bash tool write is the
only legitimate emission path.

Pattern 25 cleanup NOTEs (`routine-cleanup-note: …`,
`prompt-agent-cleanup-note: …`) belong in the transcript only — NEVER
in the marker file. The marker line is the exact 18 bytes
`SMOKE_RESULT=PASS\n`; anything else (extra spaces, trailing prose,
decoration) is FAIL.

Per AGENTS.md § 9.7 Pattern 16, do NOT invoke `azd ai routine` from
this fixture. The preview-CLI flag surface drifts between releases;
this fixture is SDK-only.
