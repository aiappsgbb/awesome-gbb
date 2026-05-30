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

   - Then prove `az` is actually authenticated:

     ```bash
     az account show --output table
     ```

     MUST return a row whose `SubscriptionId` column matches
     `$AZURE_SUBSCRIPTION_ID`. If it errors with "Please run
     'az login'", `azure/login@v2` failed upstream — FAIL with
     `az account show: not logged in`.

   Only if both checks pass, proceed to step 1.

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
7. **Step 7 — Emit the result marker. This is mandatory work, not a
   postscript.** A previous run of this fixture
   ([`actions/runs/26695861103`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26695861103)
   — `foundry-prompt-agents` leg) completed all of steps 1-6
   successfully, the agent replied to the ping, the list/delete cycle
   verified, the model emitted a prose summary saying "lifecycle
   complete, all assertions held" — and then it stopped without
   emitting the marker line. The CI grep failed and the matrix leg
   went red on what was a successful skill execution. **Do not let
   that happen here.** If you have declared success in prose, you are
   NOT done. The run is not complete until the final assistant reply
   contains exactly one line matching `^SMOKE_RESULT=PASS$` per the
   contract below. The marker MUST be emitted in the SAME assistant
   reply that performs steps 5-6 — do NOT split it into a separate
   "summary" turn. The LAST thing you do in this fixture is print
   that line. Read the "Result contract" section below carefully
   BEFORE you start step 1, and re-read it before you emit your final
   reply.

## Result contract

CI greps the **whole transcript** with anchored, line-boundary patterns:

```bash
grep -qE '^SMOKE_RESULT=FAIL'   transcript.log   # FAIL wins if both appear
grep -q  '^SMOKE_RESULT=PASS$'  transcript.log   # PASS pattern is fully anchored
```

The `^` and `$` are **zero-tolerance** for ANY surrounding character.
The first character of the line MUST be the literal capital `S` of
`SMOKE_RESULT`, and the last character MUST be the literal capital
`S` of `PASS` (no trailing period, space, backtick, or newline noise).
The Copilot CLI appends a footer (`Changes / Duration / Tokens`)
after your reply, but the marker need not be the final line — just
the only line matching the grep.

### Marker emission rules — read carefully

Empirical evidence from `actions/runs/26693703357` (the run that
triggered this contract tightening across both pilot fixtures): in the
SAME workflow run, this skill's matrix leg emitted the marker **clean**
while the parallel `foundry-hosted-agents` matrix leg emitted it
**wrapped in backticks**, breaking the start-of-line anchor. We've been
lucky here so far — symmetric hardening below removes the latent
vulnerability before it bites. The Copilot CLI's underlying LLM
autoregression non-deterministically formats identifiers in markdown —
your job is to defeat that.

WRONG (every pattern below has been seen fail an anchored grep):

```
`SMOKE_RESULT=PASS`              ← backticks break ^ anchor (LITERAL bug seen in sister fixture)
**SMOKE_RESULT=PASS**            ← bold asterisks break both anchors
`SMOKE_RESULT=PASS` (success)    ← trailing prose breaks $ anchor
> SMOKE_RESULT=PASS              ← blockquote prefix breaks ^ anchor
  SMOKE_RESULT=PASS              ← leading whitespace breaks ^ anchor
SMOKE_RESULT=PASS.               ← trailing period breaks $ anchor
SMOKE_RESULT=PASS ✓              ← trailing emoji/glyph breaks $ anchor
```

RIGHT (the ONLY accepted form for success — note that in this prompt
the literal `S` of `SMOKE_RESULT` is rendered as `_` so this
documentation itself doesn't trip the grep; your reply MUST substitute
the literal capital `S`):

```
_MOKE_RESULT=PASS
```

The line MUST stand alone in its own paragraph — a blank line before
it and a blank line after it. Do NOT embed it in a list bullet, code
fence, or inline mention. If you want to add prose explaining what
happened (recommended), put that prose in a **separate paragraph**
before or after, never on the same line as the marker, and never
write the literal token `SMOKE_RESULT` in any decorated form
(backticks, bold, italic) anywhere else in your reply — autoregressive
priming from those earlier mentions is what causes the final marker
emission to come out backtick-wrapped.

On any failure in steps 1-6, emit a single line of the form
`SMOKE_RESULT=FAIL` followed by a single space and a short reason
(≤80 chars, no backticks, no newlines). Example shape (with the
literal `S` of `SMOKE_RESULT` replaced by `_` so this prompt itself
doesn't trip the grep — your reply MUST use the literal `S`):

```
_MOKE_RESULT=FAIL conversations.create returned 401 after retry
```

Same line-boundary rules apply (no surrounding decoration). CI checks
FAIL before PASS, so an explicit FAIL always wins even if you also
emit PASS elsewhere — useful if you want to FAIL with detail and ALSO
emit a stub PASS for debugging.

### Runtime guardrails (avoid known shell-block traps)

- Do NOT redirect your own stdout via `exec > >(tee -a "$LOG") 2>&1`
  or any process-substitution pattern. The Copilot CLI shell wrapper
  blocks process substitution as "dangerous shell expansion" (seen in
  run `26693703357` at 20:09:44Z, where the sister hosted-agents
  fixture's heredoc using `exec > >(...)` got rejected before
  execution). Your stdout is ALREADY captured by the CI runner — you
  do not need to tee it yourself.

Please don't modify any file under `skills/` — this is verification
only.
