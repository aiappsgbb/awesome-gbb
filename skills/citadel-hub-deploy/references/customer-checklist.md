# Pre-flight checklist

Run this **before** `azd up`. The hub takes 30-45 minutes to provision
and costs $200-2,500/mo at baseline depending on profile — failing
mid-deploy because of a missing provider or quota is expensive.

---

## 1. Tenant + subscription

> Per `azure-tenant-isolation` skill. **Mandatory.**

- [ ] `AZURE_CONFIG_DIR` set to a per-tenant directory
      (e.g., `~/.azure-tenants/<alias>`)
- [ ] `AZD_CONFIG_DIR` set to the matching per-tenant directory
      (e.g., `~/.azd-tenants/<alias>`)
- [ ] `az login --tenant <id>` AND `azd auth login --tenant-id <id>`
      both run (separate caches)
- [ ] `az account set --subscription <name>` after login (multi-sub
      tenants do NOT auto-set the default)
- [ ] Two-layer assertion passes:
      ```
      az account show --query tenantId -o tsv  →  expected tenant id
      az account show --query name -o tsv      →  expected sub name
      ```
- [ ] Subscription has **Owner** OR (**Contributor** + **User Access
      Administrator**) for the deploying principal — role assignments
      are part of the deploy

## 2. Resource provider registration

```bash
for ns in Microsoft.ApiManagement \
          Microsoft.CognitiveServices \
          Microsoft.DocumentDB \
          Microsoft.EventHub \
          Microsoft.Insights \
          Microsoft.Logic \
          Microsoft.Web \
          Microsoft.KeyVault \
          Microsoft.Cache \
          Microsoft.Storage \
          Microsoft.Network \
          Microsoft.OperationalInsights; do
  az provider register --namespace "$ns"
done
```

Verify all show `Registered`:

```bash
az provider list --query "[?starts_with(namespace,'Microsoft.')].{ns:namespace,state:registrationState}" -o table | grep -E "(ApiManagement|CognitiveServices|DocumentDB|EventHub|Insights|Logic|Web|KeyVault|Cache|Storage|Network|OperationalInsights)"
```

- [ ] All required providers `Registered`

## 3. Quota

The hub provisions **a lot**. Validate quota in the target region(s)
before deploy.

### APIM Standard v2

```bash
# Check region availability
az apim list-skus --location <region> -o table
```

Standard v2 is in [limited regions]. Pilot-quickstart's Developer SKU
is everywhere.

[limited regions]: https://learn.microsoft.com/azure/api-management/v2-service-tiers-overview#region-availability

- [ ] Target region supports your chosen APIM SKU

### Foundry / AI Services models

The default `aiFoundryModelsConfig` deploys 6-7 models per Foundry
instance × 2 instances. Each `GlobalStandard` deployment requires TPM
quota in the region.

```bash
# Check Cognitive Services quota
az cognitiveservices usage list --location <region> -o table
```

Models in the upstream default config (capacity field):

- gpt-4.1 (100 TPM × 1k = 100k TPM)
- gpt-5.4-mini (100k TPM)
- gpt-5.4 (100k TPM)
- gpt-5.2 (100k TPM)
- text-embedding-3-large (100k TPM)
- DeepSeek-R1 (1k TPM)
- Mistral-Large-3 (100k TPM)
- Phi-4 (1k TPM)

**Pilot-quickstart** profile uses upstream defaults. **Enterprise-baseline**
should be tuned per region/project.

- [ ] Quota approved for every model in your `aiFoundryModelsConfig`
      (or use a smaller `aiFoundryModelsConfig` array)

### Cosmos DB RU/s

Default: 400 RU/s shared throughput (cheap baseline). Adjust via
`COSMOS_DB_RUS` for high-traffic hubs.

- [ ] Cosmos region supports your chosen RU tier

### Other quotas (rarely an issue)

- Event Hub: 1 capacity unit
- Storage account: standard LRS
- Key Vault: standard tier
- Redis: Balanced_B1 (Managed Redis)

## 4. Networking decision

Pick ONE up front. Switching after deploy = re-deploy.

| Decision | Profile to use | What it means |
|---|---|---|
| **Greenfield** — let the template create everything | `pilot-quickstart` or `enterprise-baseline` | New VNet 10.170.0.0/24 + new private DNS zones in the same RG |
| **BYO VNet** — peer to existing hub | `vnet-isolated-spoke-aware` | Set `USE_EXISTING_VNET=true`, `VNET_NAME=...`, `EXISTING_VNET_RG=...`. Subnets must already exist with required prefixes (or matching subnet names) |
| **BYO Private DNS Zones** — central DNS in a separate sub | `vnet-isolated-spoke-aware` | Set `EXISTING_DNS_ZONE_*` to full ARM resource IDs of the 13 privatelink zones |
| **BYO Log Analytics** — central observability landing zone | `enterprise-baseline` (or layer manually) | Set `USE_EXISTING_LOG_ANALYTICS=true`, `EXISTING_LOG_ANALYTICS_NAME=...`, `EXISTING_LOG_ANALYTICS_RG=...`, `EXISTING_LOG_ANALYTICS_SUBSCRIPTION_ID=...`. RBAC required: `Monitoring Metrics Publisher` on the workspace for the deploying identity |

- [ ] Networking decision made and matching profile selected
- [ ] If BYO VNet: address space carves out 4 /26 subnets (apim, pe,
      functionapp, agents) — names must match `APIM_SUBNET_NAME`,
      `PRIVATE_ENDPOINT_SUBNET_NAME`, `FUNCTION_APP_SUBNET_NAME`,
      `AGENT_SUBNET_NAME` env vars (or accept the `snet-*` defaults)
- [ ] If BYO DNS zones: cross-sub `Network Contributor` granted to deploy identity

## 5. Tagging (MCAPS pilot subscriptions)

The upstream `bicepparam` already includes `SecurityControl: Ignore` —
this stops Defender for Cloud from auto-remediating policy violations
during pilot.

For additional cost-allocation tags (per `azd-patterns` skill):

```bash
azd env set AZURE_TAGS '{"costCenter":"<cc>","owner":"<email>","environment":"pilot"}'
```

- [ ] Tag strategy decided (MCAPS pilot vs. customer landing zone)

## 6. Optional: Entra Auth (JWT)

The upstream supports JWT auth on the gateway. Default is **disabled**
(`entraAuth=false`). To enable post-deploy, run
`bicep/infra/entra-id-setup/setup.ps1` — outside this skill's v1.0.0
scope (will require its own follow-up).

- [ ] If JWT will be enabled later: app registration ready or willing
      to use upstream `entra-id-setup/setup.ps1`

## 7. Optional: Hub upgrade flow

Upstream ships `bicep/infra/apim-gateway-upgrade/` for migrating between
APIM SKUs (e.g., StandardV2 → Premium v2 when GA). Outside this skill's
v1.0.0 scope.

- [ ] Aware that future SKU upgrades use upstream's
      `apim-gateway-upgrade/` Bicep, not this skill

---

## Final go/no-go

- [ ] All boxes above checked
- [ ] You have **30-45 minutes** of uninterrupted time for `azd up`
- [ ] You have a `azd down --purge` plan if you need to roll back
      (the hub's RG should NOT contain shared resources unless you
      explicitly used BYO mode for them)

If yes to all → proceed to the Quickstart paths in `SKILL.md § 5`.
