# azure-sre-agent

> GBB wrapper around Microsoft's **Azure SRE Agent** (preview). Thin: we add
> recipes, plugins, pre-flight checks, and cross-skill integration glue.
> **We do NOT rebuild** Microsoft's Bicep, deploy scripts, or starter agent
> library — that work lives at [`microsoft/sre-agent`](https://github.com/microsoft/sre-agent).

## What this skill is

A reference SKILL that helps a GBB SE deliver an Azure SRE Agent into a
customer engagement built on the rest of the awesome-gbb catalog (Citadel,
Foundry, Threadlight). It assumes the SE will use Microsoft's official
toolchain for the actual deploy.

## What's in here

| Path | Purpose |
|---|---|
| `SKILL.md` | The 8-section runbook a GBB SE reads before walking into a customer engagement |
| `scripts/preflight.sh` | 5-gate pre-flight check (`Microsoft.App` RP, RBAC, region availability, `*.azuresre.ai` reachability, Citadel JWT issuance) — run before `bin/new-agent.sh` |
| `scripts/data_plane.py` | Data-plane helper for other awesome-gbb skills: DefaultAzureCredential → `https://azuresre.dev/.default` token → HTTP triggers, plugin uploads, knowledge-base uploads |
| `references/upstream-pin.md` | Tier A freshness pin against `microsoft/sre-agent` HEAD SHA + `Azure/sre-agent-plugins` HEAD SHA |
| `references/recipes/citadel-routed/` | Recipe in upstream shape — routes outbound LLM through an AI Citadel APIM gateway |
| `references/recipes/foundry-hosted-agents/` | Recipe in upstream shape — investigates Foundry hosted-agent operations (BYOK 401, deploy fail, quota) |
| `references/recipes/threadlight-pilot-handover/` | Recipe in upstream shape — webhook-triggered triage for Threadlight ACA pilots |
| `references/plugins/gbb-citadel/` | Plugin in `Azure/sre-agent-plugins` shape — `apim_throttle_expert`, `jwt_403_debug_expert` |
| `references/plugins/gbb-foundry/` | Plugin in `Azure/sre-agent-plugins` shape — `hosted_agent_deploy_expert`, `byok_401_debug_expert`, `quota_throttle_expert` |

## How to use

See `SKILL.md` — it's the entry point. TL;DR:

1. `bash scripts/preflight.sh` to confirm the subscription is ready
2. `git clone https://github.com/microsoft/sre-agent.git` and copy one of
   our `references/recipes/<name>/` into `sreagent-templates/recipes/`
3. `./bin/new-agent.sh --recipe <name> -o <out>/` then `./bin/deploy.sh <out>/`
4. (Optional) Install one of our plugins via `data_plane.py install-plugin`
5. Pair with `threadlight-pilot-handover` to wire the SRE Agent's HTTP
   trigger into a Threadlight pilot's exception handler

## Upstream contribution path

Our recipes and plugins are MIT-licensed and authored byte-for-byte in
upstream shape. They can be PR-ed directly into `microsoft/sre-agent` (for
recipes) and `Azure/sre-agent-plugins` (for plugins) once a customer
engagement validates them. The pin file tracks both upstream SHAs to flag
when a contribution should be considered.

## Cross-skill matrix

| Awesome-GBB skill | How `azure-sre-agent` interacts |
|---|---|
| [`citadel-hub-deploy`](../citadel-hub-deploy/) | The Citadel hub's RG is added to `targetResourceGroups`; SRE Agent uses the hub's AppIn |
| [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/) | SRE Agent's UAMI is onboarded as a spoke with `llm:read` Access Contract to call models through the gateway |
| [`microsoft-foundry`](../microsoft-foundry/) | Foundry project's AppIn + LAW are wired as connectors; SRE Agent investigates hosted-agent issues |
| [`foundry-hosted-agents`](../foundry-hosted-agents/) | `gbb-foundry` plugin encodes KIs from the hosted-agents skill |
| [`ghcp-hosted-agents`](../ghcp-hosted-agents/) | Same — `byok_401_debug_expert` is the canonical fix for KI-001 |
| [`threadlight-deploy`](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-deploy/) | Threadlight pilots set `SRE_AGENT_WEBHOOK_URL` on every ACA app; exceptions POST to the SRE Agent's HTTP trigger |
| [`foundry-observability`](../foundry-observability/) | SRE Agent's AppIn connector points at the same AppIn that `foundry-observability` Bicep produces |

## Cost notes

Azure SRE Agent bills in **Azure Agent Units (AAU)**. There's an always-on
baseline (4 AAU/hr) plus token-active flow. The `monthlyAgentUnitLimit`
property in `agent.json` is a hard cap — set it explicitly to bound spend
during pilots. See [pricing](https://aka.ms/sreagent/pricing).

## License

MIT. Same as the rest of awesome-gbb.
