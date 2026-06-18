---
name: azure-sre-agent
description: >
  Adopt Azure SRE Agent (Microsoft.App/agents) in GBB engagements without
  rebuilding what Microsoft already ships. Thin wrapper around the
  official microsoft/sre-agent toolchain and Azure/sre-agent-plugins
  marketplace. Adds 3 GBB recipes (Citadel-routed model traffic, Foundry
  hosted-agent ops, Threadlight pilot handover), 2 GBB plugins (Citadel
  APIM, Foundry hosted-agent), pre-flight runbook, and a data-plane
  helper so other awesome-gbb skills post into a customer's SRE Agent
  via HTTP triggers. USE FOR: azure sre agent, sre.azure.com,
  sreagent-templates, sre agent recipe, sre agent plugin, subagent,
  agentmemory upload, http trigger, Microsoft.App agents Bicep,
  azuresre.ai, azuresre.dev, citadel-routed sre agent, threadlight
  handover, sre agent preflight, DeploymentNotFound. DO NOT USE FOR:
  in-process agent policy (foundry-agt), OTel emit
  (foundry-observability), APIM gateway provisioning
  (citadel-hub-deploy), hosted-agent build (foundry-hosted-agents),
  MCP on ACA (foundry-mcp-aca).
metadata:
  version: "1.0.1"
---

# Azure SRE Agent — GBB Adoption Skill

> **Posture: upstream-first.** Microsoft ships the full toolchain at
> [`microsoft/sre-agent`](https://github.com/microsoft/sre-agent) and the
> plugin marketplace at [`Azure/sre-agent-plugins`](https://github.com/Azure/sre-agent-plugins).
> This skill does **not** rebuild Bicep modules, deploy scripts, or a
> custom-agent library — those are MIT-licensed and actively maintained
> there. We add only what GBB engagements need on top: 3 GBB-shaped
> recipes, 2 GBB-shaped plugins, a small cross-skill data-plane helper,
> and the pre-flight runbook the official docs assume you don't need.

---

## 1. When to use / when NOT

Use this skill when a customer wants **Azure SRE Agent** (`sre.azure.com`,
`Microsoft.App/agents`) deployed in a GBB engagement — typically because
they already run on Azure and want an always-on operator/responder agent
on top of App Insights + Log Analytics + their incident platform.

| Use this skill | Use a different skill |
|---|---|
| Deploy Azure SRE Agent in a customer sub | Deploy a Foundry hosted agent → [`foundry-hosted-agents`](../foundry-hosted-agents/) |
| Wire SRE Agent to a Citadel-routed Foundry connection | Provision the Citadel hub itself → [`citadel-hub-deploy`](../citadel-hub-deploy/) |
| Post a Threadlight incident into a customer's SRE Agent | Onboard a Foundry spoke to a Citadel hub → [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/) |
| Knowledge-base seed with GBB runbooks | In-process agent governance (policy-decision middleware) → [`foundry-agt`](../foundry-agt/) |
| Author a GBB recipe upstream-shaped | OTel emit from a hosted agent → [`foundry-observability`](../foundry-observability/) |
| Author a GBB plugin upstream-shaped | Host an MCP server on ACA → [`foundry-mcp-aca`](../foundry-mcp-aca/) |

---

## 2. Use the official toolchain first

**Before you write a single byte of Bicep, do this:**

```bash
git clone https://github.com/microsoft/sre-agent.git
cd sre-agent/sreagent-templates

./bin/install-prerequisites.sh          # az, jq, python3, pyyaml; --all adds Terraform + azd

# Generate config from a vendor-neutral recipe
./bin/new-agent.sh --recipe minimal --non-interactive \
  --set agentName=my-sre-agent \
  --set resourceGroup=rg-my-sre-agent \
  --set location=swedencentral \
  --set targetRGs=rg-my-workload \
  -o my-agent/

./bin/deploy.sh my-agent/                # Bicep deploy, ~3 min
```

That's everything Microsoft considers the canonical happy path. Backends
are pluggable — same `my-agent/` config directory deploys via:

| Backend | Command |
|---|---|
| Bicep | `./bin/deploy.sh my-agent/` |
| Terraform | `./bin/deploy-tf.sh my-agent/` |
| azd | `azd up` (uses the `azure.yaml` in `sreagent-templates/`) |
| PowerShell | `./bin/ps/Deploy-Agent.ps1 -InputPath my-agent/` |

**This skill's value is what comes next** — when you need a GBB-shaped
recipe or plugin that upstream doesn't ship.

---

## 3. GBB pre-flight runbook (the gotchas Learn docs assume away)

Run this BEFORE the customer Tuesday meeting:

```bash
bash scripts/preflight.sh <subscription-id>
```

Verifies (in order — first failure stops):

1. **`Microsoft.App` resource provider is registered** in the target sub.
   Fresh subs return `DeploymentNotFound` on `az deployment group create`
   if you skip this. Fix: `az provider register --namespace Microsoft.App`
2. **You have `Microsoft.Authorization/roleAssignments/write`** at the
   target scope. SRE Agent provisioning assigns RBAC to its UAMI; without
   this perm the wizard fails opaquely with "Failed to create resource."
3. **You're in a supported region.** Only **Sweden Central**, **East US 2**,
   **UK South**, **Australia East** for the public preview. Request more
   via <https://aka.ms/sreagent/region>.
4. **Network ACL allows `*.azuresre.ai` and `sre.azure.com`**. Zscaler and
   corporate proxies often block the `*.azuresre.ai` data-plane wildcard
   by default. Fix: add to allow-list — the data plane MUST be reachable
   for chat to work.
5. **(Citadel engagements only)** Foundry project's UAMI has been issued
   a JWT scoped to the Citadel APIM `/llm/*` operation. SRE Agent's
   `defaultModel.provider: MicrosoftFoundry` needs this to call the
   gateway-routed model — symptom is HTTP 401 on the first chat turn.

### Known traps

| Symptom | Cause | Fix |
|---|---|---|
| `DeploymentNotFound` on a fresh sub | `Microsoft.App` RP not registered | `az provider register --namespace Microsoft.App` |
| HTTP 401 on first chat turn (Citadel) | APIM rejecting Foundry token (no JWT, wrong audience) | Issue JWT via `citadel-spoke-onboarding` Access Contract |
| "Failed to create resource" in wizard | Missing `Microsoft.Authorization/roleAssignments/write` | Elevate to Owner or User Access Administrator at the target scope |
| Chat works in browser, dies in CLI | Zscaler blocking `*.azuresre.ai` data plane | Add allow-list for `*.azuresre.ai` + `sre.azure.com` |
| "Region not available" | Region not in preview footprint | Pick eastus2 / swedencentral / uksouth / australiaeast or file a region request |
| Agent answers garbage / hangs on first prompt | English-only at preview, customer typed in another language | Communicate at engagement-kickoff; pin chat language to `en-US` |

---

## 4. GBB recipes (upstream-shaped, ready to drop into `sreagent-templates/recipes/`)

Three recipes live under [`references/recipes/`](references/recipes/). Each
follows the **exact** [`microsoft/sre-agent/sreagent-templates/recipes/<name>/`](https://github.com/microsoft/sre-agent/tree/main/sreagent-templates/recipes)
shape — `agent.json` + `connectors.json` + `roles.yaml` + `expected-config.json` +
`README.md` + `config/{skills,subagents,common-prompts}/` + optional
`automations/scheduled-tasks/`. You drop the directory in, then deploy
with the official `bin/deploy.sh`:

```bash
# from a clone of microsoft/sre-agent
cp -r /path/to/awesome-gbb/skills/azure-sre-agent/references/recipes/citadel-routed \
      sreagent-templates/recipes/citadel-routed
./bin/new-agent.sh --recipe citadel-routed --non-interactive \
  --set agentName=sre-citadel-pilot \
  --set resourceGroup=rg-sre-pilot \
  --set location=swedencentral \
  --set targetRGs=rg-pilot-prod \
  --set citadelGatewayUrl=https://apim-citadel.contoso.net \
  --set citadelProductKey=<sub-key-or-blank-for-jwt> \
  -o sre-citadel-pilot/
./bin/deploy.sh sre-citadel-pilot/
```

| Recipe | One-line | Adds |
|---|---|---|
| [`citadel-routed/`](references/recipes/citadel-routed/) | SRE Agent with `defaultModel.provider: MicrosoftFoundry` routed through a Citadel APIM gateway — keyless via Foundry connection or JWT-protected | `citadel-gateway-debug` skill + `apim-403-investigator` subagent + safety-rules common prompt that forbids reading APIM subscription keys |
| [`foundry-hosted-agents/`](references/recipes/foundry-hosted-agents/) | SRE Agent specialised for diagnosing Foundry hosted-agent failures (BYOK 401, MAF version skew, ACA cold-start, ACR pull failures) | `hosted-agent-deploy-triage` skill + `byok-401-investigator` subagent + daily hosted-agent-health-check |
| [`threadlight-pilot-handover/`](references/recipes/threadlight-pilot-handover/) | Handover recipe for Threadlight pilots transitioning to production — pre-wires the SRE Agent to the Threadlight ACA workload, MCP servers, Cosmos KV, and HITL webhook bridge | `threadlight-incident-triage` skill + `threadlight-runtime-investigator` subagent + `scheduled-task: daily-pipeline-health` |

> **Recipes are vendored** at `references/recipes/<name>/`. They are not
> copied into the upstream repo — you (or the customer) drop them in
> when needed. We open PRs upstream once a customer engagement validates
> a recipe; see § 8.

---

## 5. GBB plugins (upstream-shaped, ready to add to `Azure/sre-agent-plugins`)

Two plugin packs live under [`references/plugins/`](references/plugins/).
Each follows the **exact** [`Azure/sre-agent-plugins/plugins/<name>/`](https://github.com/Azure/sre-agent-plugins/tree/main/plugins)
shape — `plugin.json` + optional `.mcp.json` + `README.md` + `skills/<skill_name>/SKILL.md`.

| Plugin | Bundles |
|---|---|
| [`gbb-citadel/`](references/plugins/gbb-citadel/) | `apim_throttle_expert` (Citadel APIM 429/503 diagnostics) + `jwt_403_debug_expert` (JWT/audience/scope debugging) — no MCP server; pure skills |
| [`gbb-foundry/`](references/plugins/gbb-foundry/) | `hosted_agent_deploy_expert` (ACR/ACA/refreshed-preview ctor) + `byok_401_debug_expert` (BYOK Foundry-User scope) + `quota_throttle_expert` (PTU vs PayGo header decoding) |

### Install a plugin onto an SRE Agent

Two paths, pick one:

**(A) Upstream marketplace clone** (recommended for production — survives
plugin updates from us via the standard `git pull` workflow):

```bash
# fork or clone Azure/sre-agent-plugins
cp -r /path/to/awesome-gbb/skills/azure-sre-agent/references/plugins/gbb-citadel plugins/
# Register in YOUR fork's .github/plugin/marketplace.json (see upstream README)
# Then follow upstream install steps documented in the marketplace
```

**(B) Direct data-plane push** (recommended for pilot demos — single
command):

```bash
python3 scripts/data_plane.py install-plugin \
  --agent /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.App/agents/<name> \
  --plugin references/plugins/gbb-citadel
```

This walks the plugin's `skills/<skill_name>/SKILL.md`, base64-encodes the
content, and PUTs each into `/subagents/{name}/skills/{skill}?api-version=2025-05-01-preview`.

---

## 6. Cross-skill integration

### 6.1 Posting Threadlight incidents into a customer's SRE Agent

A Threadlight pilot can post incidents (HITL escalations, eval-fail
alerts, cron-job failures) into the customer's SRE Agent via the data
plane's HTTP trigger:

```python
from skills.azure_sre_agent.scripts.data_plane import SREAgentClient

client = SREAgentClient.from_arm(agent_resource_id)
trigger = client.create_http_trigger(
    name="threadlight-incident",
    prompt="Investigate the linked Threadlight HITL escalation: {{payload}}.",
)
# trigger.webhook_url → public; no auth required. Save to KV; pass to ACA cron.
```

This is what enables a Threadlight pilot to **degrade gracefully into
existing customer ops** — the moment something escalates, the customer's
SRE Agent picks it up, with full agent-memory context from the pilot's
SPEC and runbooks.

### 6.2 Routing `defaultModel.provider: MicrosoftFoundry` through a Citadel APIM

Set `defaultModelProvider: Azure OpenAI` in the recipe `agent.json`, then
configure the Foundry connection to point at the Citadel APIM gateway,
and grant the SRE Agent's UAMI the Citadel `llm:read` access contract
(via [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/)). The
`citadel-routed` recipe (§ 4) wires all of this.

### 6.3 Aligning auto-created App Insights with `foundry-observability`

SRE Agent auto-creates its own App Insights resource by default. If
you've already established a project-wide AppIn via
[`foundry-observability`](../foundry-observability/), pass
`--set existingAgentAppInsightsId=<arm-id>` to `bin/new-agent.sh` so SRE
Agent reuses it instead of fragmenting telemetry.

---

## 7. Cost notes

SRE Agent bills in **Azure Agent Units (AAU)**. Two flows:

- **Always-on flow** — `4 AAU/hour` baseline per agent, regardless of usage. ~$0.10/hr at preview pricing.
- **Active flow** — token-based when the agent actually processes a query. Charged against the recipe's `monthlyAgentUnitLimit` cap.

Set `monthlyAgentUnitLimit` in the recipe's `agent.json` to a deliberate
cap — the upstream `minimal` recipe defaults to **10,000 AAU/month** which
is reasonable for a pilot. For production, model from
<https://aka.ms/sreagent/pricing>.

Always-on flow is the **biggest hidden cost surprise** — leaving 4 demo
agents running over a 2-week disco workshop adds up. Either:

- `./bin/deploy.sh my-agent/ --stop` between sessions (sets `powerState: Stopped`), or
- `az resource delete` the whole RG when the pilot is over.

---

## 8. Upstream contribution path

When a customer engagement validates a GBB-authored recipe or plugin:

1. **Fork** `microsoft/sre-agent` (recipe) or `Azure/sre-agent-plugins` (plugin)
2. **Copy** `references/recipes/<name>/` or `references/plugins/<name>/` to the fork
3. **Scrub** any GBB-specific references (this skill keeps them generic, but double-check)
4. **Add** marketplace.json entry (plugins) or update the upstream README recipe table (recipes)
5. **Open PR** with a customer testimonial in the description (anonymized per AGENTS.md § 2.1)

License is **MIT** on both upstream repos — same as ours. No license
conflict. Microsoft welcomes recipe / plugin contributions; the recipe
request issue template at <https://github.com/microsoft/sre-agent/issues/new?template=recipe_request.md>
is the right entry point for triage.

---

## Cross-references

- Upstream toolchain: <https://github.com/microsoft/sre-agent>
- Upstream plugins: <https://github.com/Azure/sre-agent-plugins>
- Product home: <https://www.azure.com/sreagent>
- Portal: <https://sre.azure.com> · `aka.ms/sreagent`
- Docs: <https://aka.ms/sreagent/newdocs>
- API reference: <https://learn.microsoft.com/en-us/azure/sre-agent/api-reference>
- Region requests: <https://aka.ms/sreagent/region>
- Pricing: <https://aka.ms/sreagent/pricing>
- Pin file: [`references/upstream-pin.md`](references/upstream-pin.md)
