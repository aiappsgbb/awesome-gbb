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

## Result contract

If every step succeeds, your **final chat reply** must be exactly the
single line `SMOKE_RESULT=PASS` — no markdown, no bold, no leading or
trailing prose, no follow-up summary. The Python script can print
whatever it wants while it runs, but your last line of output to the
CI runner is the marker only. On any failure, your final chat reply
must be `SMOKE_RESULT=FAIL <short reason>` (one line, same rules).
The CI job uses `tail -n 1 | grep -q '^SMOKE_RESULT=(PASS|FAIL)'`, so
any commentary after the marker breaks the check.

Please don't modify any file under `skills/` — this is verification
only.
