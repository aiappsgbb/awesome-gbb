# Customer goal — `foundry-hosted-agents` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-hosted-agents`
skill works end-to-end against your CI Foundry project + Container Registry
+ Container Apps environment.

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of `azd`, ACA, ACR, or the Azure AI SDK — read the skill's
`SKILL.md` (and the canonical reference files it points to under
`skills/foundry-hosted-agents/references/`) first, and follow its
documented contract. If your memory of how `azd ai agent`, `azure.yaml`,
`agent.yaml`, or `container.py` should look conflicts with what the skill
says, **the skill wins**.

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
- Foundry project endpoint: `FOUNDRY_PROJECT_ENDPOINT` (also published
  as `AZURE_AI_ENDPOINT` for compatibility) — in the
  `https://<acct>.services.ai.azure.com/api/projects/<proj>` form.
- Foundry model deployment to use: `FOUNDRY_MODEL_DEPLOYMENT=gpt-5.4-mini`
  (already deployed on the Foundry account `aif-awesome-gbb-ci`).

**Pre-granted RBAC (do NOT re-grant — propagation is 5-15 min and would
race the workflow timeout):**

- The UAMI `uami-awesome-gbb-ci` holds Contributor on `rg-awesome-gbb-ci`,
  AcrPush on `acrawesomegbbci`, AcrPull on `acrawesomegbbci`, and
  Cognitive Services OpenAI User + Foundry User on the Foundry account.
- The Foundry project's **system-assigned managed identity** (the
  principal that pulls the hosted-agent container at runtime — see
  SKILL.md § Identity & RBAC) holds **AcrPull** and **Container Registry
  Repository Reader** on `acrawesomegbbci`. This is the load-bearing one
  for hosted-agent image pull. Do NOT attempt to grant or verify it
  yourself.
- The per-agent-instance MI created at deploy time is a separate identity
  whose role propagation is 1-5 min — if a fresh invoke 401s briefly,
  retry per the skill's documented backoff.

**Tooling pre-installed by the workflow** (Pattern 15 — AGENTS.md § 9.7):

- `azd` CLI is pre-installed via `Azure/setup-azd@v2`. Do NOT hunt for
  the binary, `curl install-azd.sh`, or `apt install`. If `command -v
  azd` is empty, that is a workflow regression — FAIL with `azd missing
  from PATH` and stop.
- The `azure.ai.agents` azd preview extension is **NOT** pre-installed.
  The skill tells you when to install it.
- `az` CLI, Python 3, and `uv` are pre-installed.

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
echo "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}"
az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
```

If any env var prints empty, the workflow's `env:` block is broken
(AGENTS.md § 9.7 Pattern 11). That is a workflow bug, not a skill bug.
Write the FAIL marker (Step 2) with reason `auth context missing: <var-name>`
and stop.

Then run `azd auth login` via federated credential **before** any `azd`
command (Pattern 6) so failure is loud and immediate, not buried inside
`azd deploy`:

```bash
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID"
```

---

## Step 1 — The goal

Using the `foundry-hosted-agents` skill, deploy a hosted Foundry agent
as a Container App that classifies inbound customer-support messages
into one of three categories: `billing`, `technical`, `account`. Then
prove it works by sending one test message through it and verifying the
response is one of those three labels. When you're done, tear down
everything you created (the agent, the ACA app, and the ACR repository).

The skill's `SKILL.md` and its `references/` directory are the source of
truth for:

- which container source / Dockerfile / pyproject to ship
- which `azure.yaml` and `agent.yaml` shapes to use
- which `azd env` keys to set
- which `azd` and `azd ai agent` subcommands to invoke and in what order
- which SDK to use to invoke the agent (and whether to use the
  preview-CLI surface — see AGENTS.md § 9.7 Pattern 16 if relevant)
- how to authenticate the invoke call (managed identity vs `DefaultAzureCredential`)
- how to delete the agent + the ACA app + the ACR repository on teardown

Read the SKILL (and the canonical reference files it cites) before you
write any code. If you have to write your own container source, Dockerfile,
or `agent.yaml` from training-data memory, you are doing it wrong — copy
verbatim from the skill's `references/`.

Give every Azure resource you create a CI-safe name with a short UUID
suffix so parallel matrix runs don't collide (Pattern 15.3). Suggested
pattern: `ci-smoke-ha-$(uuidgen | cut -c1-8)`. Use the same suffix for
the azd service name, ACA app name, ACR repository name, and Foundry
agent name.

Do all scaffolding under `${GITHUB_WORKSPACE}/.scratch/<your-agent-name>/`
— the Copilot CLI's shell-tool gate rejects `cd` outside
`$GITHUB_WORKSPACE` even with `--allow-all-tools`. `.scratch/` is
gitignored.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after teardown — is to invoke the Bash tool to write
the marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded.

On success (all of: agent + ACA app deployed, test message returned a
valid label, teardown completed):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-hosted-agents-smoke-result
```

On ANY failure (auth, skill not found, `azd deploy` failure, invoke
error, invalid response, teardown failure):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-hosted-agents-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
