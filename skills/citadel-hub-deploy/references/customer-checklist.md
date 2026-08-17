# Pre-flight checklist

Run this **before** `azd up`. The hub takes 30-45 minutes to provision
and costs $200-2,500/mo at baseline depending on profile — failing
mid-deploy because of a missing provider or quota is expensive.

This checklist targets pinned commit
`63f0f812474e713916dc909494d655246783a1d9`, which is build-validated
but not yet live-validated on Azure.

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

The default `aiFoundryModelsConfig` deploys eight models in instance 0
and three in instance 1. Each deployment consumes regional quota.

```bash
# Check Cognitive Services quota
az cognitiveservices usage list --location <region> -o table
```

Models in the current upstream default:

- Instance 0 (`AZURE_LOCATION`, default Sweden Central): gpt-4.1,
  gpt-5.2, gpt-image-1.5, MAI-Image-2.5-Flash, FLUX.2-pro,
  text-embedding-3-large, Mistral-Large-3, and gpt-5.4-mini.
- Instance 1 (hardcoded `eastus2` in `aiFoundryInstances`): gpt-5.4-mini,
  gpt-5.2, and text-embedding-3-large. There is no `AZURE_LOCATION_2`
  environment variable; change the literal array to use another region.

The profile ENV files cannot override the two structured arrays safely.
For a smaller pilot, deliberately reduce `aiFoundryInstances` and
`aiFoundryModelsConfig` in the pinned `main.bicepparam`; do not send JSON
arrays through `azd env set`.

- [ ] Quota approved for every model in your `aiFoundryModelsConfig`
      (or use a smaller `aiFoundryModelsConfig` array)
- [ ] Model versions and retirement dates in `main.bicepparam` rechecked

### Cosmos DB RU/s

Default: 400 RU/s shared throughput (cheap baseline). Adjust via
`COSMOS_DB_RUS` for high-traffic hubs.

- [ ] Cosmos region supports your chosen RU tier

### Other quotas (rarely an issue)

- Event Hub: 1 capacity unit
- Storage account: standard LRS
- Key Vault: standard tier
- Redis: Balanced_B1 (Managed Redis)

When Redis is enabled, set `REDIS_HIGH_AVAILABILITY=Enabled`. The pilot
quickstart disables Redis and explicitly uses `Disabled`.

## 4. Networking decision

Pick ONE up front. Switching after deploy = re-deploy.

| Decision | Profile to use | What it means |
|---|---|---|
| **Greenfield** — let the template create everything | `pilot-quickstart` or `enterprise-baseline` | New VNet 10.170.0.0/24 + new private DNS zones in the same RG |
| **BYO VNet** — peer to existing hub | `vnet-isolated-spoke-aware` | Set `USE_EXISTING_VNET=true`, `VNET_NAME=...`, `EXISTING_VNET_RG=...`. Subnets must already exist with required prefixes (or matching subnet names) |
| **BYO Private DNS Zones** — central DNS in a separate sub | `vnet-isolated-spoke-aware` | Set `EXISTING_DNS_ZONE_*` to full ARM resource IDs of the 13 privatelink zones |
| **BYO Log Analytics** — central observability landing zone | `enterprise-baseline` (or layer manually) | Set `USE_EXISTING_LOG_ANALYTICS=true`, `EXISTING_LOG_ANALYTICS_NAME=...`, `EXISTING_LOG_ANALYTICS_RG=...`, `EXISTING_LOG_ANALYTICS_SUBSCRIPTION_ID=...`. RBAC required: `Monitoring Metrics Publisher` on the workspace for the deploying identity |

- [ ] Networking decision made and matching profile selected
- [ ] `foundryNetworkInjectionEnabled=false` remains unchanged. Upstream
      warns that enabling it without full BYO Standard Agent dependencies
      fails; the accelerator does not provision that full dependency set.
- [ ] If BYO VNet: address space carves out 3 /26 subnets (apim, pe,
      functionapp) — names must match `APIM_SUBNET_NAME`,
      `PRIVATE_ENDPOINT_SUBNET_NAME`, and `FUNCTION_APP_SUBNET_NAME`
      env vars (or accept the `snet-*` defaults)
- [ ] If BYO DNS zones: cross-sub `Network Contributor` granted to deploy identity
- [ ] If using APIM Standard v2/Premium v2:
      `EVENTHUB_NETWORK_ACCESS=Enabled` remains set during provisioning. The
      pinned `main.bicep` requires Event Hub public access for APIM v2;
      enterprise and VNet profiles enforce this compatibility setting.

## 5. Tagging (MCAPS pilot subscriptions)

The upstream `bicepparam` already includes `SecurityControl: Ignore` —
this stops Defender for Cloud from auto-remediating policy violations
during pilot.

For additional cost-allocation tags (per `azd-patterns` skill):

```bash
azd env set AZURE_TAGS '{"costCenter":"<cc>","owner":"<email>","environment":"pilot"}'
```

- [ ] Tag strategy decided (MCAPS pilot vs. customer landing zone)

## 6. Entra Auth (JWT)

The upstream supports JWT auth on the gateway. All supplied profiles set
`AZURE_ENTRA_AUTH=true`. After `azd up`, run
`bicep/infra/entra-id-setup/setup.ps1`; it creates or updates the app
registration and service principal, resets a two-year client secret, writes
`ENTRA-APP-CLIENT-SECRET` to Key Vault, configures the APIM JWT named values
directly, and writes Entra values to the selected azd environment. No second
hub deployment is required.

Prerequisites from the pinned script and upstream setup guide:

- Microsoft Graph `Application.ReadWrite.All` permission or the Entra
  **Application Developer** role.
- **Key Vault Secrets Officer** on the deployed Key Vault data plane.
- **API Management Service Contributor** on the APIM service or its resource
  group.
- A host with private DNS and network reachability to the Key Vault private
  endpoint. Every supplied profile sets Key Vault public network access to
  `Disabled`; a normal Internet-only workstation cannot complete the secret
  write. Use the approved VPN or a peered administrative host with the same
  exact detached checkout and selected azd environment. This checklist does
  not authorize a temporary public-access exception.

The pinned `setup.ps1` continues when the Key Vault secret write fails and
still stores the client secret in the local azd environment. Therefore, do
not accept its final banner or resource existence alone. Re-run the exact
tenant/subscription GUID assertion immediately before the script, then compare
the stored values with the newly generated azd values:

```bash
EXPECTED_TENANT_ID="<tenant-guid>"
EXPECTED_CLIENT_ID="$(azd env get-value AZURE_CLIENT_ID)"
EXPECTED_CLIENT_SECRET="$(azd env get-value ENTRA_CLIENT_SECRET)"
ACTUAL_CLIENT_SECRET="$(az keyvault secret show \
  --vault-name "$(azd env get-value KEY_VAULT_NAME)" \
  --name ENTRA-APP-CLIENT-SECRET \
  --query value -o tsv)"
[[ -n "$EXPECTED_CLIENT_SECRET" &&
   "$ACTUAL_CLIENT_SECRET" == "$EXPECTED_CLIENT_SECRET" ]] || exit 1
unset EXPECTED_CLIENT_SECRET ACTUAL_CLIENT_SECRET

verify_apim_named_value() {
  local named_value="$1"
  local expected_value="$2"
  local actual_value
  actual_value="$(az apim nv show \
    --resource-group "$(azd env get-value AZURE_RESOURCE_GROUP)" \
    --service-name "$(azd env get-value APIM_NAME)" \
    --named-value-id "$named_value" \
    --query value -o tsv)"
  [[ "$actual_value" == "$expected_value" ]] || exit 1
}
verify_apim_named_value JWT-TenantId "$EXPECTED_TENANT_ID"
verify_apim_named_value JWT-AppRegistrationId "$EXPECTED_CLIENT_ID"
verify_apim_named_value JWT-Issuer \
  "https://login.microsoftonline.com/$EXPECTED_TENANT_ID/v2.0"
verify_apim_named_value JWT-OpenIdConfigUrl \
  "https://login.microsoftonline.com/$EXPECTED_TENANT_ID/v2.0/.well-known/openid-configuration"
```

- [ ] Exact tenant GUID and subscription GUID re-asserted immediately before
      `setup.ps1`
- [ ] Graph app-registration permission/role confirmed
- [ ] Key Vault Secrets Officer and private endpoint reachability confirmed
- [ ] API Management Service Contributor confirmed
- [ ] Key Vault secret and all four APIM named values verified after setup

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
- [ ] You have a `azd down --purge` plan if you need to roll back, and will
      re-run the exact tenant/subscription GUID assertion immediately before it
      (the hub's RG should NOT contain shared resources unless you
      explicitly used BYO mode for them)
- [ ] You will run the 12-scenario sequence in `validation/README.md`;
      at minimum run the four strongly recommended baseline notebooks
- [ ] You understand the current pin has build-only evidence until that
      live validation is captured

If yes to all → proceed to the Quickstart paths in `SKILL.md § 5`.
