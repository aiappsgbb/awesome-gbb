# Customer goal — `ghcp-hosted-agents` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `ghcp-hosted-agents`
skill works end-to-end against your CI Foundry project + Container
Registry + Container Apps environment using the **BYOK** path (Foundry
model via managed identity, no `GITHUB_TOKEN`).

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of `azd`, ACA, ACR, the Azure AI SDK, or the github-copilot-sdk
— read the skill's `SKILL.md` (and the canonical reference files it points
to under `skills/ghcp-hosted-agents/references/`) first, and follow its
documented contract. If your memory of how `azd ai agent`, `azure.yaml`,
`agent.yaml`, `container.py`, or the GHCP SDK's `CopilotClient` should
look conflicts with what the skill says, **the skill wins**.

This fixture is the FIRST CI smoke for `ghcp-hosted-agents` and the
primary regression for KI-006 (`SubprocessConfig` removed, `auto_start`
kwarg removed in `github-copilot-sdk` 1.0 GA). If the container fails to
start because the imports or constructor shape are wrong, `azd deploy`
will surface that as the ACA app crashing — your invoke step will then
hard-FAIL the marker. That is the entire point of the fixture: prove the
1.0 GA refactor in `references/container.py` survives a real Azure deploy.

---

## Environment available to your run

The workflow has pre-provisioned shared CI infrastructure. You consume it;
you do NOT create it.

- `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` —
  populated by `azure/login@v2` OIDC upstream.
- Resource group: `rg-awesome-gbb-ci` (Sweden Central). Pre-provisioned.
  Do NOT run `azd provision` or `az group create`.
- Container Apps environment: `cae-awesome-gbb-ci`. Pre-provisioned.
- Container Registry: `ACR_LOGIN_SERVER=acrawesomegbbci.azurecr.io`.
  The UAMI you authenticate as has `AcrPush` here.
- Foundry project endpoint: `FOUNDRY_PROJECT_ENDPOINT` — in the
  `https://<acct>.services.ai.azure.com/api/projects/<proj>` form.
- Foundry account name (derive from endpoint): `aif-awesome-gbb-ci`.
- Foundry model deployment to use: `FOUNDRY_MODEL_DEPLOYMENT=gpt-5.4-mini`
  (already deployed on the Foundry account).

**Pre-granted RBAC (do NOT re-grant — propagation is 5-15 min and would
race the workflow timeout):**

- The UAMI `uami-awesome-gbb-ci` holds Contributor on `rg-awesome-gbb-ci`,
  AcrPush + AcrPull on `acrawesomegbbci`, and Cognitive Services OpenAI
  User + Foundry User on the Foundry **account**.
- The Foundry project's **system-assigned managed identity** holds
  **AcrPull** on `acrawesomegbbci`. This is the load-bearing role for
  the hosted-agent's image pull at runtime. Do NOT attempt to grant or
  verify it yourself.
- **NOT pre-granted (you DO grant these — see Step 1c):** the **two
  per-agent-instance MIs** that `azd ai agent` creates fresh on each
  deploy (`instance_identity.principal_id` and `blueprint.principal_id`
  per SKILL.md § "Identity & RBAC for hosted agents"). Granting these
  at **account** scope is unavoidable per KI-001 and is part of the
  skill's documented contract. AAD propagation for fresh principals is
  60-90 s — your invoke step (Step 1d) is responsible for retrying on
  401 within that window per Pattern 23 (AGENTS.md § 9.7).

**Tooling pre-installed by the workflow** (Pattern 15 — AGENTS.md § 9.7):

- `azd` CLI is pre-installed via `Azure/setup-azd@v2.3.0`. Do NOT hunt
  for the binary, `curl install-azd.sh`, or `apt install`. If `command
  -v azd` is empty, that is a workflow regression — FAIL with `azd
  missing from PATH` and stop.
- The `azure.ai.agents` azd preview extension is **NOT** pre-installed.
  Install it as Step 1a.
- `az` CLI, Python 3, `uv`, `jq`, and `curl` are pre-installed.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on any of these
checks — `azure/login@v2` already validated the credentials upstream
(Pattern 17 — show-don't-assert):

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:+set}"
echo "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}"
az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
command -v azd && azd version || echo "(azd missing from PATH — workflow regression)"
```

If any env var prints empty, the workflow's `env:` block is broken
(AGENTS.md § 9.7 Pattern 11). That is a workflow bug, not a skill bug.
Write the FAIL marker (Step 2) with reason `auth context missing: <var-name>`
and stop.

Then run `azd auth login` via federated credential **before** any `azd`
command (Pattern 6) so failure is loud and immediate:

```bash
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID"
```

---

## Step 1 — The goal

Using the `ghcp-hosted-agents` skill, deploy a GHCP SDK hosted Foundry
agent as a Container App that responds to a simple greeting prompt
via the Invocations protocol. Then prove it works by POSTing one test
message to its `/invocations` endpoint and verifying the SSE response
contains an `assistant.message_delta` or `assistant.message` event.

**Use BYOK mode** (Foundry model via the agent's managed identity —
NO `GITHUB_TOKEN`). The skill's `references/container.py` ships with
both code paths; BYOK is selected at runtime when
`FOUNDRY_PROJECT_ENDPOINT` and `AZURE_AI_MODEL_DEPLOYMENT_NAME` are
present in `agent.yaml` and `GITHUB_TOKEN` is absent.

The skill's `SKILL.md` and its `references/` directory are the source
of truth for:

- which container source / Dockerfile / pyproject to ship (copy
  `references/*` verbatim into the scratch project — do NOT regenerate
  from `azd ai agent init -t github-copilot`, which would download the
  upstream MS sample and miss the skill's specific pin set + 1.0 GA
  refactor)
- which `azure.yaml` and `agent.yaml` shapes to use
- which `azd env` keys to set (KI-004 — `AZURE_TENANT_ID` is
  mandatory before `azd deploy`)
- the manual account-scope `Foundry User` grant for both per-agent MIs
  (KI-001) and the 60-90 s AAD propagation wait that follows
- which `curl` / SDK call to use for the invoke (KI-002 — `azd ai
  agent invoke` is BROKEN against this skill's container at the time
  of writing; use the documented `curl POST /invocations` recipe
  exclusively, single-path per Pattern 16)

Read the SKILL (and the canonical reference files it cites) before you
write any code. If you have to write your own `container.py`,
`Dockerfile`, or `pyproject.toml` from training-data memory, you are
doing it wrong — copy verbatim from the skill's `references/`.

Give every Azure resource you create a CI-safe name with a short UUID
suffix so parallel matrix runs don't collide (Pattern 15.3). Suggested
pattern: `ci-smoke-ghcp-$(uuidgen | cut -c1-8)`. Use the same suffix
for the azd service name, ACA app name, ACR repository name, and
Foundry agent name. The `pyproject.toml`, `agent.yaml`, and
`azure.yaml` from the skill's `references/` use the placeholder name
`my-agent` — replace it with your UUID-suffixed name in all three
files before `azd up`.

Do all scaffolding under `${GITHUB_WORKSPACE}/.scratch/<your-agent-name>/`
— the Copilot CLI's shell-tool gate rejects `cd` outside
`$GITHUB_WORKSPACE` even with `--allow-all-tools`. `.scratch/` is
gitignored.

**Teardown is best-effort, NOT a success criterion** (AGENTS.md § 9.7
Pattern 25). After the invoke proves success, attempt to delete what
you created (the Foundry agent, the ACA app, and the ACR repository),
but cap your total teardown attempt at **5 minutes wall-clock**. If
teardown fails or runs over budget for ANY reason (missing CLI
subcommand, expired OIDC token, REST endpoint changed, AAD
propagation race), that is acceptable — emit a single transcript NOTE
describing what couldn't be cleaned up and proceed to write the PASS
marker. The CI resource group `rg-awesome-gbb-ci` is periodically
pruned of orphaned hosted-agent versions and ACR repositories by a
separate janitor; do NOT spend stability-run budget hunting for delete
paths.

---

## Step 1a — Install the `azure.ai.agents` azd extension

The skill requires the `azure.ai.agents` azd preview extension for
`azd ai agent show` and `azd up` to recognise the `host: azure.ai.agent`
service entry. Install it:

```bash
azd extension install azure.ai.agents
azd ai agent --help | head -20  # smoke-check it registered
```

If the install fails with a network or registry error, retry once.
If it fails twice, write the FAIL marker with reason
`azd extension install azure.ai.agents failed: <reason>` and stop.

---

## Step 1b — Scaffold the agent project from `references/`

Copy the skill's reference files verbatim into a fresh scratch project
directory, then update the three files that contain the `my-agent`
placeholder. Create `azure.yaml` at the project root per the skill's
"§ azure.yaml (required for azd deploy)" section, substituting your
UUID-suffixed name.

After scaffolding:

1. `azd env new <agent-name>` in the scratch project dir.
2. `azd env set AZURE_TENANT_ID $(az account show --query tenantId -o tsv)`
   (KI-004 — mandatory before `azd deploy`).
3. `azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "$FOUNDRY_MODEL_DEPLOYMENT"`
   so the container picks up the Foundry deployment name.
4. `azd up` — this provisions the Foundry agent + ACA app + builds the
   container image via ACR remote build + assigns the postdeploy hook's
   project-scope `Foundry User` to both per-agent MIs.

If `azd up` fails, capture the last 80 lines of its output to the
transcript and write the FAIL marker with reason
`azd up failed: <one-line summary>`.

---

## Step 1c — Manual account-scope `Foundry User` grant (KI-001)

`azd up` only assigns `Foundry User` at the **project** scope. The
container's BYOK call to the Foundry model deployment needs the role
at the CognitiveServices **account** scope too. This is documented in
SKILL.md § "Identity & RBAC for hosted agents" → § "Manual account-scope
assignment".

Run the exact recipe from that section (substituting the live values):

```bash
ACCT_SCOPE="/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.CognitiveServices/accounts/aif-awesome-gbb-ci"
FOUNDRY_USER="53ca6127-db72-4b80-b1b0-d745d6d5456d"

INSTANCE_PID=$(azd ai agent show --output json | jq -r '.instance_identity.principal_id')
BLUEPRINT_PID=$(azd ai agent show --output json | jq -r '.blueprint.principal_id')

for PID in "$INSTANCE_PID" "$BLUEPRINT_PID"; do
  az role assignment create \
    --role "$FOUNDRY_USER" \
    --assignee-object-id "$PID" \
    --assignee-principal-type ServicePrincipal \
    --scope "$ACCT_SCOPE" \
    --output none || echo "(role may already exist — continuing)"
done
```

If `azd ai agent show` doesn't return both principal IDs, or jq fails
to parse the output, the deploy hasn't fully landed yet — `sleep 30`
and retry the `azd ai agent show` call up to twice. If still empty
after the second retry, write the FAIL marker with reason
`azd ai agent show: instance/blueprint principal_id not found after deploy`.

**Do NOT `sleep 60` blindly here.** The 60-90 s AAD-propagation wait is
folded into Step 1d's retry loop — that way the invoke itself
discovers the moment AAD is ready, rather than this step blocking on
a worst-case timer.

---

## Step 1d — Invoke the agent

Per SKILL.md § "Invoking the Agent" → § "Via curl (SSE streaming)" the
single documented invoke path is `curl POST /invocations` with a bearer
token from `az account get-access-token --resource https://ai.azure.com`.
Per Pattern 16 (AGENTS.md § 9.7): use ONLY this path. Do NOT attempt
`azd ai agent invoke` (KI-002 — broken: sends wrong body shape). Do NOT
synthesize a different invoke route from training-data memory.

The agent's invocation URL pattern (from SKILL.md):

```
${FOUNDRY_PROJECT_ENDPOINT}/agents/<agent-name>/endpoint/protocols/invocations?api-version=2025-11-15-preview
```

**Retry loop (Pattern 23 — RBAC propagation race; AGENTS.md § 9.7):**
Wrap the invoke in a bounded retry loop. On HTTP 401 from the agent
endpoint (the symptom of `Foundry User` not yet propagated to the
per-agent MI), `sleep 15` and retry. Budget: 6 attempts × 15 s back-off
= 90 s total, comfortably inside the documented 60-90 s AAD-propagation
window. On HTTP 200, inspect the SSE stream — success is at least one
event whose JSON body contains `assistant.message` OR
`assistant.message_delta`.

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv | tr -d '\r\n')
URL="${FOUNDRY_PROJECT_ENDPOINT}/agents/${AGENT_NAME}/endpoint/protocols/invocations?api-version=2025-11-15-preview"

for i in 1 2 3 4 5 6; do
  HTTP_AND_BODY=$(curl -sN -w "\nHTTP_STATUS:%{http_code}\n" \
    -X POST "$URL" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"input": "Say hello in one short sentence."}' \
    --max-time 90)
  STATUS=$(echo "$HTTP_AND_BODY" | awk -F: '/^HTTP_STATUS:/ {print $2}')
  if [ "$STATUS" = "200" ]; then
    # Parse SSE — succeed if any line contains assistant.message[_delta]
    if echo "$HTTP_AND_BODY" | grep -qE '"type"\s*:\s*"assistant\.message(_delta)?"'; then
      echo "INVOKE_OK: assistant.message event received on attempt $i"
      INVOKE_OK=1
      break
    else
      echo "INVOKE_BAD_SHAPE attempt $i: 200 but no assistant.message event in body"
    fi
  elif [ "$STATUS" = "401" ]; then
    echo "401 on attempt $i — AAD propagation in progress, sleeping 15 s"
    sleep 15
  else
    echo "Unexpected HTTP $STATUS on attempt $i; body:"
    echo "$HTTP_AND_BODY" | head -40
    sleep 5
  fi
done

if [ -z "${INVOKE_OK:-}" ]; then
  echo "All 6 invoke attempts failed."
  echo "Last response body (tail 40 lines):"
  echo "$HTTP_AND_BODY" | tail -40
fi
```

If the loop exits without `INVOKE_OK=1`, write the FAIL marker with
reason `invoke failed after 6 retries (last HTTP=<status>)`.

---

## Step 1e — KI-006 regression NOTE (best-effort, Pattern 13 soft-PASS)

If Step 1d succeeded, the container in production started cleanly with
`github-copilot-sdk` 1.0 GA — that proves the `SubprocessConfig` import
removal and the flat `CopilotClient(github_token=...)` constructor
refactor (the entire point of skill version 1.2.0) survived a real
Azure deploy. Emit ONE transcript NOTE so this fact is captured in the
run log:

```
NOTE KI-006 regression cleared: container booted on github-copilot-sdk 1.0 GA — flat CopilotClient(github_token=...) constructor + SubprocessConfig removal validated in production.
```

This is a NOTE only — it does NOT gate the marker. The marker remains
conditioned on hard PASS criteria (deploy + invoke).

---

## Step 1f — Best-effort teardown (Pattern 25)

After the invoke succeeds, attempt cleanup with a **5-minute total
wall-clock cap**. Use the skill's documented teardown if it exists; if
not, use the generic `azd down --force --purge` + `az containerapp
delete` + `az acr repository delete --name $AGENT_NAME --yes` path.

If teardown fails or times out, emit ONE transcript NOTE describing
what couldn't be cleaned up (the janitor handles orphans):

```
NOTE teardown best-effort: agent <AGENT_NAME> / ACA app / ACR repo <AGENT_NAME> not fully deleted (reason: <one-line>); rg-awesome-gbb-ci janitor will prune.
```

Do NOT FAIL the marker on teardown failure.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after the invoke succeeds AND after your best-effort
teardown attempt (or after the 5-minute teardown budget expires) — is to
invoke the Bash tool to write the marker file. The file's literal byte
content is what CI grades; your assistant-text reply is NOT graded.

**PASS condition (hard success criteria):**

- `azd up` succeeded (the GHCP hosted agent is deployed as an ACA app)
- The retry-bounded invoke (Step 1d) emitted `INVOKE_OK=1` (at least
  one `assistant.message` / `assistant.message_delta` event received
  on a `HTTP 200` SSE response)

Teardown outcome is irrelevant to the PASS marker. KI-006 regression
NOTE (Step 1e) is informational, not a gate. On hard success:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/ghcp-hosted-agents-smoke-result
```

**FAIL condition (auth, scaffold, deploy, grant, or invoke failed):**

- Auth context missing (Step 0)
- Skill or required reference file not findable
- `azd extension install azure.ai.agents` failed twice (Step 1a)
- `azd up` failed (Step 1b)
- `azd ai agent show` did not surface both per-agent MI principal IDs
  after retry (Step 1c)
- Invoke 401'd through all 6 retries OR returned non-200 / non-401 /
  200-without-assistant.message (Step 1d)

On FAIL:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/ghcp-hosted-agents-smoke-result
```

**Do NOT FAIL on teardown failure.** Teardown is best-effort (Pattern 25).
Any teardown error — missing CLI subcommand, expired OIDC assertion,
REST 404, AAD propagation race, network blip — gets a NOTE and a PASS,
never a FAIL. The CI janitor handles orphan cleanup.

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
