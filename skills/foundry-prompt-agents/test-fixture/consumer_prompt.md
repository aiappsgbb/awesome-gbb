<!-- skills/foundry-prompt-agents/test-fixture/consumer_prompt.md -->

You are a Copilot CLI agent driving an end-to-end smoke test of the
`foundry-prompt-agents` skill. The repo containing the skill is at
your current working directory (`$GITHUB_WORKSPACE`). The skill file
is `skills/foundry-prompt-agents/SKILL.md` — read it once, then
execute its happy path verbatim. No mocked clients. No stubs. Real
Azure calls only.

## Environment you can rely on

- `AZURE_AI_ENDPOINT` is set to the Foundry account host
  (`https://aif-awesome-gbb-ci.cognitiveservices.azure.com/`).
- Azure CLI is logged in via OIDC (UAMI `uami-awesome-gbb-ci` has
  `Cognitive Services OpenAI User` + `Foundry User` on the account).
- `gpt-5.4-mini` is deployed on the account.
- The skill uses `DefaultAzureCredential`, which picks up the
  workflow's `azure/login@v2` token automatically.

## What you MUST do (in order)

1. Read `skills/foundry-prompt-agents/SKILL.md` end-to-end. Note the
   Python create / invoke / list / delete patterns and the KI-001,
   KI-002, KI-003 gotchas in § 6.
2. Derive the Foundry **project endpoint** from `AZURE_AI_ENDPOINT`
   per KI-001 (account-host → project-host conversion is documented
   in the skill).
3. In a Python invocation (use `python3 -c '<inline>'` or a tempfile),
   import the skill's canonical SDK surface
   (`from azure.ai.projects import AIProjectClient`,
   `from azure.identity import DefaultAzureCredential`) and:
   1. Create a prompt agent named
      `ci-smoke-pa-<8-char-uuid>` using deployment `gpt-5.4-mini`
      with instructions exactly: `"Reply with the single word OK and
      nothing else."`
   2. Send a single user message `ping` via the Conversations API
      pattern documented in § 3 of SKILL.md.
   3. Print the agent's reply.
   4. List agents (KI-002 path — exercise the pagination quirk
      documented in the skill) and confirm the new agent is in the
      list.
   5. Delete the agent by name (KI-003 path — uses the
      delete-by-name signature documented in the skill).
   6. List agents again and confirm the agent is NOT in the list.
4. Print exactly one of these two lines as the LAST line of output:
   - On success: `SMOKE_RESULT=PASS`
   - On failure: `SMOKE_RESULT=FAIL <one-line reason>`

## Hard constraints

- Do NOT modify any file under `skills/foundry-prompt-agents/`.
- Do NOT add new pip dependencies; the runner already has the
  packages declared in the skill's pin file
  (`references/upstream-pin.md` → `packages[]`).
- If any step throws, print `SMOKE_RESULT=FAIL <step N>: <exception
  type + message>` and exit non-zero.
- If `SMOKE_RESULT=PASS` is the last line of stdout, the matrix job
  marks the run green; any other last line is treated as failure.

Begin now.
