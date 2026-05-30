# foundry-hosted-agents — CI verification fixture

Context: this prompt is fed to the `copilot-cli-matrix` job in the
awesome-gbb repo to verify that the `foundry-hosted-agents` skill (at
`skills/foundry-hosted-agents/SKILL.md` in the current working
directory) still deploys end-to-end against the live Azure Foundry CI
test project. We're checking that the documented `azd ai agent`
container-deploy flow — scaffold → `azd deploy` → invoke → teardown —
still runs against the real platform.

**Expected per-run cost: ~$0.005** — ACR storage for one ~200 MB
image held for ≤2 min (~$0.001), ACA cold-start of 1 vCPU × ~30 s
(~$0.001), and one `gpt-5.4-mini` completion of a few tokens
(~$0.0003). Weekly stability cost on this fixture is negligible.

## Environment available

- `FOUNDRY_PROJECT_ENDPOINT` — Foundry project endpoint URL in the
  `https://<acct>.services.ai.azure.com/api/projects/<proj>` form.
  Use this for `AZURE_AI_PROJECT_ENDPOINT` (azd env) AND for any
  data-plane REST invoke calls.
- `FOUNDRY_MODEL_DEPLOYMENT` — chat-model deployment name to use.
  Will be `gpt-5.4-mini` in CI. The matching model version is
  `2026-03-17` (see SKILL.md § Model Version Lookup).
- `ACR_LOGIN_SERVER` — `acrawesomegbbci.azurecr.io`. The shared CI
  Container Registry where `azd deploy` with `remoteBuild: true` will
  push the agent image.
- `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID` — populated by OIDC
  login. The resource group is `rg-awesome-gbb-ci` and the Container
  Apps environment is `cae-awesome-gbb-ci` (both pre-provisioned —
  do NOT run `azd provision`).
- Azure CLI is logged in via OIDC with the `uami-awesome-gbb-ci`
  workload identity, which has Contributor on `rg-awesome-gbb-ci`,
  AcrPush on `acrawesomegbbci`, and Cognitive Services OpenAI User
  + Foundry User on the Foundry account. `DefaultAzureCredential()`
  resolves without extra setup.
- **Pre-granted hosted-agent ACR pull RBAC** (one-time CI infra
  setup, **not** something you provision per run): the **Foundry
  project's system-assigned managed identity** (the principal that
  pulls the hosted-agent container at runtime — see SKILL.md
  § Identity & RBAC L1142-1156) holds **AcrPull** AND **Container
  Registry Repository Reader** on `acrawesomegbbci`. Do NOT attempt
  to grant these roles yourself — RBAC propagation is 5-15 min
  (SKILL.md L1218) and the workflow's retry classifier does not
  catch `ImagePullError|401 Unauthorized`, so a fresh grant inside
  the fixture would `SMOKE_RESULT=FAIL` on first-deploy image pull.
  If your `azd deploy` returns success but the agent invoke 401s
  for >2 min, that's the *agent's own* per-instance identity
  propagation (different concern) — handle it with the step-5 retry
  loop, not by re-granting RBAC.
- `azd` CLI is installed. The `azure.ai.agents` preview extension is
  NOT pre-installed — you must `azd extension install -s
  azure.ai.agents --allow-prerelease` before `azd deploy`.
- Python 3 + `uv` are installed for the container image build.

## Steps

Before scratching out code, skim SKILL.md sections **container.py**,
**Dockerfile**, **agent.yaml (ContainerAgent Schema)** (including the
Critical Rules table — note the literal-vs-mustache trap MID-3 and
the reserved env-var rules), **azure.yaml (azd ai agent Extension)**,
**Required `azd env` variables**, and the **Identity & RBAC** /
**RBAC propagation** rows in Troubleshooting. The canonical container
source lives at:

- `skills/foundry-hosted-agents/references/python/container.py`
- `skills/foundry-hosted-agents/references/python/pyproject.toml`
- `skills/foundry-hosted-agents/references/yaml/agent.yaml`

Copy these verbatim — they're the validator-enforced single source of
truth. The Dockerfile pattern is in SKILL.md § Dockerfile (~L934).

Then run these steps. Use a shell heredoc or python heredoc as you
prefer — the goal is the result marker, not a particular ergonomics
choice.

1. **Generate a per-run UUID suffix** and export reusable names. Use
   8 hex chars from `uuid.uuid4().hex`. Naming pattern (mandatory —
   parallel matrix runs collide on fixed names):
   - `SUFFIX="$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"`
   - `AGENT_NAME="ci-smoke-ha-${SUFFIX}"` (used as the azd service
     name, ACA app name, ACR repository name, AND Foundry agent name)
   - `SCAFFOLD_DIR="/tmp/${AGENT_NAME}"`

2. **Scaffold the agent project** in `${SCAFFOLD_DIR}`:
   - `mkdir -p "${SCAFFOLD_DIR}"`
   - Copy `skills/foundry-hosted-agents/references/python/container.py`
     and `references/python/pyproject.toml` into it verbatim.
   - Copy `skills/foundry-hosted-agents/references/yaml/agent.yaml`
     into it, then substitute the `name:` field at the top with
     `${AGENT_NAME}` and replace any `gpt-5.4` model-name literal
     with `${FOUNDRY_MODEL_DEPLOYMENT}` (CI ships `gpt-5.4-mini`).
   - Write a `Dockerfile` matching SKILL.md § Dockerfile (~L934) —
     `python:3.12-slim` base, `uv sync --no-dev --no-install-project`,
     `COPY container.py .`, `EXPOSE 8088`, `CMD
     [".venv/bin/python", "container.py"]`. Enumerate the files
     explicitly in `COPY` — do NOT glob with `.` or `./*` (per the
     sticky-424 row in SKILL.md Troubleshooting).
   - Write `azure.yaml` per SKILL.md § azure.yaml. Service name MUST
     be `${AGENT_NAME}`. Set `docker.remoteBuild: true`. Drop the
     `infra:` block (we are NOT provisioning). Drop the `deployments:`
     block under `config` (the gpt-5.4-mini deployment already exists
     on `aif-awesome-gbb-ci`).

3. **Initialize azd** without a template and wire it to existing CI
   infrastructure:
   - `cd "${SCAFFOLD_DIR}"`
   - `azd init -e "${AGENT_NAME}" --no-prompt` (minimal env, no
     template scaffold — we already wrote azure.yaml ourselves)
   - `azd extension install -s azure.ai.agents --allow-prerelease`
   - `azd env set AZURE_SUBSCRIPTION_ID "${AZURE_SUBSCRIPTION_ID}"`
   - `azd env set AZURE_TENANT_ID "${AZURE_TENANT_ID}"`
   - `azd env set AZURE_LOCATION swedencentral`
   - `azd env set AZURE_RESOURCE_GROUP rg-awesome-gbb-ci`
   - `azd env set AZURE_AI_PROJECT_ENDPOINT "${FOUNDRY_PROJECT_ENDPOINT}"`
   - Compose `AZURE_AI_PROJECT_ID` from the endpoint host + project
     name. The endpoint is `https://aif-awesome-gbb-ci.services.ai.azure.com/api/projects/ci-test`
     so the ID is `/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.CognitiveServices/accounts/aif-awesome-gbb-ci/projects/ci-test`.
     `azd env set AZURE_AI_PROJECT_ID "<that-id>"`

4. **Deploy with `azd deploy`** (this builds the image in ACR and
   creates the ACA container app + Foundry agent registration):
   - `azd deploy "${AGENT_NAME}"`
   - If this prints a clear error about a missing Bicep `infra/`
     directory, write a no-op stub `infra/main.bicep` (empty
     module) and `infra/main.parameters.json` (empty `parameters`
     object), then retry once. Do NOT add real resource declarations.

5. **Sleep 60 s** for RBAC propagation on the newly-created per-agent
   workload identity (per SKILL.md § RBAC propagation — first invoke
   often 401s while the agent's instance identity gets its role
   assignment). Then invoke the agent. Prefer
   `azd ai agent invoke "${AGENT_NAME}" --message "ping"` if the
   extension version supports the subcommand; otherwise fall back to
   a Foundry data-plane Responses REST call against
   `${FOUNDRY_PROJECT_ENDPOINT}` using `DefaultAzureCredential` with
   the `https://ai.azure.com/.default` scope (per the MAF 1.4.0
   token-scope migration documented in SKILL.md L60-62).
   - **Retry-on-401:** if the first invoke returns HTTP 401 or
     `agent_not_found`, sleep another 60 s and retry up to 2 more
     times. The skill-test workflow's retry classifier does NOT cover
     401s, so this fixture must self-retry.
   - Capture the response body. Verify the response is non-empty.

6. **Teardown** (best-effort — do NOT FAIL the run if cleanup throws,
   just log and continue, because partial teardown still costs less
   than a leak):
   - `az containerapp delete --name "${AGENT_NAME}" --resource-group
     rg-awesome-gbb-ci --yes` to release the ACA app + revision.
   - `az acr repository delete --name acrawesomegbbci --repository
     "${AGENT_NAME}" --yes` to drop the image and all its tags.
   - Delete the Foundry agent registration. If `azd ai agent delete
     "${AGENT_NAME}" --no-prompt` is supported, use it. Otherwise
     issue a DELETE against the Foundry agents REST endpoint for
     `${AGENT_NAME}`. A 404 here means the agent was already gone —
     treat as success.

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
triggered this very contract tightening): in the SAME workflow run,
the parallel `foundry-prompt-agents` matrix leg emitted the marker
**clean** while this skill's matrix leg emitted it **wrapped in
backticks**, breaking the start-of-line anchor. The Copilot CLI's
underlying LLM autoregression non-deterministically formats
identifiers in markdown — your job is to defeat that.

WRONG (every pattern below has been seen fail an anchored grep):

```
`SMOKE_RESULT=PASS`              ← backticks break ^ anchor (LITERAL bug we hit)
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

On any failure in steps 1-5, emit a single line of the form
`SMOKE_RESULT=FAIL` followed by a single space and a short reason
(≤80 chars, no backticks, no newlines). Example shape (with the
literal `S` of `SMOKE_RESULT` replaced by `_` so this prompt itself
doesn't trip the grep — your reply MUST use the literal `S`):

```
_MOKE_RESULT=FAIL agent invoke returned 401 after 60s RBAC grace
```

Same line-boundary rules apply (no surrounding decoration). CI checks
FAIL before PASS, so an explicit FAIL always wins even if you also
emit PASS elsewhere — useful if you want to FAIL with detail and ALSO
emit a stub PASS for debugging.

### Runtime guardrails (avoid known shell-block traps)

- Do NOT redirect your own stdout via `exec > >(tee -a "$LOG") 2>&1`
  or any process-substitution pattern. The Copilot CLI shell wrapper
  blocks process substitution as "dangerous shell expansion" (seen in
  run `26693703357` at 20:09:44Z, where the agent's heredoc using
  `exec > >(...)` got rejected before execution). Your stdout is
  ALREADY captured by the CI runner — you do not need to tee it
  yourself.

Please don't modify any file under `skills/` — this is verification
only.
