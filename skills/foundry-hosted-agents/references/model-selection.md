# Model selection for Foundry hosted agents

Choose **which model, in which region, at what capacity** before you run
`azd provision`. The deployment *mechanics* are in SKILL.md — the
`azure.yaml` `services.ai-project.deployments:` block (§ *azure.yaml
(unified hosted-agent configuration)*), the version pin (§ *Model
Version Lookup*), the `azd env` wiring (§ *azd env variables for the
azure.ai.agents extension*), and region support (§ *Region
Availability*). This file is the *decision* that feeds them.

## When to read this

You're standing up a hosted agent and must pick a model deployment. The
classic pilot failure is "I picked a region and the model or quota
wasn't there." Decide the four axes below **before** committing a region
in `main.bicep` / `azure.yaml`.

## 1 — Capability selection

Match the workload to the cheapest family that clears the capability
bar. Use the version pins from § *Model Version Lookup* — that table is
the single source of truth for versions; do not restate them here.

| Workload | Start with | Why |
|---|---|---|
| Deep multi-step reasoning / agentic planning | `gpt-5.4` | Top capability tier in the pinned table |
| Code generation / repair | `gpt-5.3-codex` | Code-specialized |
| Balanced general + tool/function calling | `gpt-5.4-mini` | Cheaper/faster; keeps structured-output + tool calling |
| High-volume classify / extract / route | `gpt-5.4-nano` | Cheapest/fastest of the pinned family |
| Legacy / compat baseline | `gpt-4.1` / `gpt-4.1-mini` | When a consumer pins the 4.x surface |

### GPT-5.6 GA availability boundary (verified 2026-07-15)

`gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` are distinct SKUs,
not aliases. Microsoft publishes a common capability envelope but no
comparative ranking among them. Keep the workload defaults above until
first-party comparative evidence supports changing them.

> **Source discrepancy.** On 2026-07-15, the
> [reasoning-model feature matrix](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning)
> still showed `2026-06-25`, while the deployable catalog and live control
> plane reported `2026-07-09`. Use the catalog/control-plane version for
> deployment and keep capability claims to the shared envelope repeated in
> the current model catalog.

The table below combines the documented deployment-type boundary with a
read-only Sweden Central catalog/quota check on 2026-07-15. Quota values
are capacity units (1 unit = 1,000 TPM) and remain subscription-specific.

| Model ID | Global Standard | Data Zone Standard | Global Provisioned Managed | Sweden Central Global Standard quota | Sweden Central Data Zone Standard quota | Global Provisioned minimum / increment |
|---|---|---|---|---:|---:|---:|
| `gpt-5.6-sol` | Yes | Yes | Yes | 1,000 | 333 | 15 / 5 |
| `gpt-5.6-terra` | Yes | Yes | No | 1,000 | 333 | N/A |
| `gpt-5.6-luna` | Yes | Yes | No | 1,000 | 333 | N/A |

Use this as an availability boundary, not as a recommendation:

- The [Foundry Agent Service compatibility table](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/limits-quotas-regions)
  currently stops at `gpt-5.5`; the model catalog does not establish
  GPT-5.6 Agent Service compatibility. Confirm the model in the target
  project's model experience before binding it to an agent.
- Do not change an agent default, judge, router, or cost recommendation
  based only on GA status. Sol, Terra, and Luna have no first-party
  comparative ranking in the cited catalog.
- The [Azure OpenAI pricing page](https://azure.microsoft.com/en-us/pricing/details/azure-openai/)
  and Retail Prices data checked on 2026-07-15 do not yet list this family;
  pricing tables do not yet publish GPT-5.6 rates. Do not add inferred
  prices to `paygo-ptu-cost-analyzer`.
- Recheck the [region/deployment matrix](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability)
  and [quota table](https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits)
  immediately before deployment; both can vary by region, subscription,
  and quota tier.

Cross-cutting checks before you commit a family:

- **Tool / function calling + structured outputs** — required for most
  agent patterns (MCP tools, `@tool`, JSON output). Confirm the chosen
  family supports it for your API surface.
- **Context window** — long-context RAG needs headroom for retrieved
  chunks + history. Confirm the exact token limit for the pinned version
  on MS Learn (limits differ across the family — don't assume).
- **Latency vs cost** — smaller suffixes (`-mini`, `-nano`) trade
  capability for lower latency and cost; size to the task, not the
  ceiling. Per-call cost drivers live in `foundry-cost-monitoring`.

## 2 — Region & availability

Model availability is **per region** and independent of hosted-agent
region support. Both gates must hold:

1. Hosted-agent support in the region — see § *Region Availability*.
2. The model + version is deployable there — check **before** committing:

```bash
# Models deployable for an existing account's region:
az cognitiveservices account list-models \
  --resource-group <rg> --name <account> -o table

# Models available in a region (pre-account planning):
az cognitiveservices model list \
  --location <region> -o table
```

If either gate fails, fall back per § 4.

## 3 — Capacity & quota (TPM)

A deployment's `sku.capacity` is its throughput ceiling in **units of
1,000 TPM** (tokens-per-minute): `capacity: N` provisions N×1,000 TPM
(e.g. `capacity: 120` = 120K TPM). `sku.name` sets the residency/scale
class (§ 4). Check regional headroom before you pick a number:

```bash
az cognitiveservices usage list --location <region> -o table
# Find the model's *-GlobalStandard (or *-Standard) usage row. limit and
# currentValue are in the same 1,000-TPM units as sku.capacity, so
# (limit - currentValue) = the capacity units still assignable in that region.
```

- Size `sku.capacity` so its N×1,000 TPM covers expected peak **with
  headroom**: too low → `429`s under load; too high → wasted quota that
  blocks other deployments in the region.
- Request increases via the account's quota experience **before** deploy
  day — regional ceilings are shared across every deployment in that
  region/subscription.
- Deeper capacity economics (PAYGO vs PTU) are in
  `paygo-ptu-cost-analyzer`.

## 4 — Data-residency & fallback

`sku.name` is your residency lever — a ladder from widest reach to
tightest locality:

| `sku.name` | Data-processing locality | Use when |
|---|---|---|
| `GlobalStandard` | May process in any region worldwide | No residency constraint; widest model + capacity availability |
| `DataZoneStandard` | Stays within the geo / data zone (e.g. EU) | EU (or US) data-zone residency is sufficient |
| `Standard` (regional) | Single region only | Strict single-region residency |

**EU-residency path:** prefer `DataZoneStandard` in an EU data zone, or
regional `Standard` in an EU region. When your primary EU region lacks
the model or capacity, `swedencentral` is the pragmatic fallback — a
known-working hosted-agent region (§ *Region Availability*) with broad
model coverage.

> **Caveat (verified):** in `swedencentral`, embedding deployments
> (e.g. `text-embedding-3-small`) require `GlobalStandard` — regional
> `Standard` is rejected there. If an EU-residency design needs
> embeddings in Sweden Central, that specific deployment cannot use a
> regional SKU; plan the residency story around it.

The residency ↔ SKU choice also has a cost dimension (regional SKUs can
cost more than `GlobalStandard` where residency isn't needed) — see the
`foundry-cost-monitoring` optimization table.

## 5 — Wiring the decision in

The four axes land in one place — the `azure.yaml`
`services.ai-project.deployments:` block (§ *azure.yaml (unified
hosted-agent configuration)*):

| Decision | `azure.yaml` field |
|---|---|
| Model family (§ 1) | `deployments[].model.name` |
| Version (§ *Model Version Lookup*) | `deployments[].model.version` |
| Capacity / TPM (§ 3) | `deployments[].sku.capacity` |
| Residency class (§ 4) | `deployments[].sku.name` |

Region is set by where you `azd provision` (the account location in
`main.bicep`); the project endpoint / ID flow through the `azd env`
vars in § *Required azd env variables for the azure.ai.agents
extension*.
