# foundry-prompt-agents — CI verification fixture

Context: this prompt is fed to the `copilot-cli-matrix` job in the
awesome-gbb repo to verify that the `foundry-prompt-agents` skill (at
`skills/foundry-prompt-agents/SKILL.md` in the current working directory)
still works against a live Azure Foundry test project. We're checking that
the documented Python quickstart — create a prompt agent, chat with it,
list it, delete it — still runs end-to-end against the real service.

## Environment available

- `FOUNDRY_PROJECT_ENDPOINT` — full project endpoint URL, of the form
  `https://<account>.services.ai.azure.com/api/projects/<project>`. Pass
  it as the `endpoint=` argument to `AIProjectClient`.
- `FOUNDRY_MODEL_DEPLOYMENT` — name of the chat-model deployment to use.
- Azure CLI is logged in via OIDC with a managed identity that has
  `Cognitive Services OpenAI User` and `Foundry User` on the account, so
  `DefaultAzureCredential()` resolves without any extra setup.
- Python 3 is installed. `pip install --quiet azure-ai-projects==2.1.0
  azure-identity openai` will give you the SDK versions documented in
  the skill's pin file.

## Steps

Skim sections 1 (create), 3 (chat via the Conversations API + agent
reference), and the "List and delete agents" snippet in section 4 of
SKILL.md for the documented Python patterns. Then run a Python script
(an inline `python3 - <<'PY' ... PY` heredoc is fine) that does the
following:

0. **Step 0 — Verify the CI auth contract BEFORE any work.** Run these
   two commands first. Both MUST succeed before you proceed. If either
   fails, **stop immediately** and emit a single `SMOKE_RESULT=FAIL`
   line with the precise failure mode (see Result contract). Do NOT
   invent additional credential checks (no `az ad sp show`, no
   `az role assignment list`, no `az login --service-principal`) —
   those are workflow-bug indicators, not skill bugs.

   - First, prove the three OIDC env vars are exported into THIS
     shell (Copilot CLI subprocesses only inherit the workflow step's
     env block — see AGENTS.md § 9.7 Pattern 11):

     ```bash
     echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
     echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
     echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
     ```

     Every line MUST print `…=set`. If any is empty, the workflow env
     contract is broken — FAIL with `workflow env contract: <var> empty`.

   - **Show-don't-assert: `az` CLI state (Pattern 17).** Per AGENTS.md
     § 9.7 Pattern 11, copilot CLI subprocesses inherit env vars but
     **NOT** the `az` CLI credential cache (`~/.azure/`). Cache
     visibility is non-deterministic across shell-creation semantics
     (run `26703036366` Finding #18). The fixture is GA-SDK-only — it
     uses `DefaultAzureCredential()` which reads env vars, not the
     `az` cache. Print the `az` table for the audit log; do NOT gate
     flow on it:

     ```bash
     az account show --output table || echo "(az cache not inherited — SDK path uses env-var OIDC)"
     ```

     **No assertion. The auth contract is the env-var OIDC chain
     `DefaultAzureCredential` consumes — not the `az` cache.**

   Only if the env-var check passes, proceed to step 1.

1. Build an `AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT,
   credential=DefaultAzureCredential())`.
2. Generate `agent_name = f"ci-smoke-pa-{uuid.uuid4().hex[:8]}"` and call
   `project.agents.create_version(agent_name=agent_name,
   definition=PromptAgentDefinition(model=FOUNDRY_MODEL_DEPLOYMENT,
   instructions="Reply with the single word OK and nothing else."))`.
   Capture the returned `agent.version`.
3. Open a conversation via `openai = project.get_openai_client()` and
   `conv = openai.conversations.create()`, then call
   `openai.responses.create(conversation=conv.id,
   extra_body={"agent_reference": {"name": agent_name,
   "type": "agent_reference"}}, input="ping")` and print
   `response.output_text`.
4. Confirm the agent appears in `project.agents.list()` (the iterable
   yields `AgentDetails` objects; match by `.name`).
5. Remove it with `project.agents.delete_version(agent_name,
   str(agent.version))` — note the positional `(name, version)` form.
6. Confirm the agent is gone from `project.agents.list()`.
7. **Step 7 — Write the result marker (deterministic, MANDATORY).**
   After step 6 succeeds, your FINAL action is to invoke the Bash tool
   to run exactly this command. The file's literal byte content is what
   CI grades — **NOT** your assistant text reply. Do NOT type the marker
   token in prose; do NOT echo it; do NOT mention it in your summary.

   ```bash
   printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-prompt-agents-smoke-result
   ```

   If ANY step 0-6 fails, instead run (substitute a real reason, ≤80
   chars, no backticks, no newlines):

   ```bash
   printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-prompt-agents-smoke-result
   ```

   The marker path is fixed: `/tmp/foundry-prompt-agents-smoke-result`.
   After writing the marker you may add a brief free-form prose summary
   for the human reviewer, but it does not affect grading.

## Result contract

CI clears `/tmp/foundry-prompt-agents-smoke-result` BEFORE invoking you,
then after your turn ends grades the result in this strict order:

1. If the marker file contains a line starting with `SMOKE_RESULT=FAIL`
   → the leg FAILs (and the line's reason is surfaced in the run log).
2. If the marker file contains exactly the bytes `SMOKE_RESULT=PASS\n`
   (compared with `cmp -s`, byte-exact) → the leg PASSes.
3. If the marker file is missing or malformed → the leg FAILs with a
   diagnostic dump (legacy transcript-grep fallback exists for the
   transition window but is scheduled for removal — do not rely on it).

The deterministic file-write path is mandatory because an earlier run
(`actions/runs/26697592828`, 2026-05-30) showed the LLM stochastically
wraps the marker in markdown decoration (backticks, bold) when asked
to emit it as prose, breaking line-boundary grep. Writing the marker
via a Bash tool call bypasses prose rendering entirely — the bytes that
hit disk are the bytes `printf` puts there.

### Runtime guardrail

- Do NOT redirect your own stdout via `exec > >(tee ...)` or any
  process-substitution pattern. The Copilot CLI shell wrapper blocks
  process substitution. Your stdout is already captured by CI — you do
  not need to tee it.

Please don't modify any file under `skills/` — this is verification only.
