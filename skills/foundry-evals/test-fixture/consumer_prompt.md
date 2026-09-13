# Customer goal — `foundry-evals` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-evals`
skill works end-to-end against your CI Foundry project.

This is an execution smoke, not a catalog inspection. Read the skill's path
selection and Day-1 recipe; execute the canonical helper rather than rewriting
it. Do not change the repository or shared Azure resources/RBAC.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do not launch another `copilot`,
install CLI tooling, or write to the workflow's transcript. Execute the
steps directly; the workflow already captures the output.

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

Prove both documented Responses evaluation paths with **one disposable prompt
agent and two invocations total**. Install the pin's bounded runtime set:
`azure-ai-projects~=2.6.0`, `azure-identity~=1.25.3`, `openai~=3.8.0`.
Do not upgrade unrelated tools. The pre-granted caller/project identity roles
are prerequisites; do not re-grant them or repair shared infrastructure.

Create a minimal prompt agent per `foundry-prompt-agents` (the existing
cross-skill dependency), with instructions "Answer in one short factual
sentence. Do not call tools." and the existing CI model below.

Put `skills/foundry-evals/references/python` on `sys.path`, then import the
**real** `smoke_score` and `invoke_and_capture` from `eval_runner`. Never copy
their bodies into the fixture script:

1. Call `smoke_score("What is the capital of France?", agent_name=agent.name,
   agent_version=agent.version, project_client=project, judge_model="gpt-5.4-mini",
   artifact_path=<private-agent-target-artifact>)`.
2. Separately call `invoke_and_capture` for the same query and agent, passing
   `project_client=project`. Pass that actual non-empty text to
   `smoke_score(query, captured_response, project_client=project,
   judge_model="gpt-5.4-mini", artifact_path=<private-invoke-score-artifact>)`.
3. Require both calls to return a finite numeric `coherence` metric and both
   artifacts to contain one scored output item, a successful terminal status,
   and `cleanup: deleted`. Agent-target evidence must contain the generated
   `datasource_item["sample.output_text"]`, not just a submitted query.
4. In a `finally` block, delete only the disposable agent this run created.
   Record cleanup even after a scoring failure.

The helper shares a default 300-second acceptance budget across eval/run creation,
polling and each result page. Every request gets the remaining per-I/O timeout
and zero SDK retries; late completion or score responses must fail, not pass.
Cleanup of its own eval has a separate 30-second budget with no retries.
This is not hard wall-clock cancellation: a blocked I/O/auth operation can
overrun before control returns, at which point the deadline check rejects it.
Do not describe the entire fixture or its separate agent invocation as a
300-second wall-clock guarantee.
This smoke checks execution, **not** a universal quality threshold. Do not call
`decide()` to pretend an execution smoke certifies task or tool quality.
If agent-target is unavailable, preserve its exact error and FAIL this fixture;
a working fallback is useful evidence but not proof that both paths passed.
Do not add an automatic service fallback or replace generated output with
synthetic answers.

Foundry project endpoint: `$FOUNDRY_PROJECT_ENDPOINT`
Model deployment available in that project: `gpt-5.4-mini` (use this for
both the agent under test AND the evaluator's judge model unless the
skill says otherwise).

The skill's `SKILL.md` is the source of truth for which SDK to use, how to
authenticate, how to configure the evaluator, how to feed it the
response, and how to read the score back. Read it before you write any
code. Also read `foundry-prompt-agents` `SKILL.md` for the agent
create / invoke / delete contract. If the skills' instructions conflict
with anything you remember from training data, the skills win.

Give the disposable agent a `ci-refresh-eval-<short-UUID>` name.
The canonical helper names each eval/run with the same prefix and its own UUID.
Keep raw response/evaluator artifacts private; output only aggregate scores,
status and cleanup. Do not print full per-item payloads to the CI transcript.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after cleanup — is to invoke the Bash tool to write the
marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded.

On success (both canonical evaluation paths scored real output, their evals
deleted, and the disposable agent deleted):

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
