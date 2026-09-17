# Opt-in Citadel spoke validation

This is a manual, owner-authorized acceptance protocol, not an automatically
enrolled shared-CI fixture. You are the designated live executor. Do not invoke
Copilot recursively or install global tooling. Local mock transport results
are not Azure acceptance.

1. Obtain the exact candidate source/hash and approved tenant-isolated CLI/AZD
   context, APIM subscription/resource group/service, selected API/product names,
   credential identity and read scope. Apply `azure-tenant-isolation` in every
   shell. Record source/runtime versions privately. No login/context switch,
   grant, key retrieval or resource change is implied by this protocol.
2. Import `references/python/access_contract_probe.py` as a real module using
   the skill directory's `references/python` on `PYTHONPATH`. Use
   `azure-mgmt-apimanagement~=5.0.0`, `azure-mgmt-resource~=23.1.0` and
   `azure-identity~=1.25.3`; no replacement model/transport on the live path.
3. On the approved positive tuple, invoke `probe_hub_contract` with explicit
   `api_id`, `product_id`, `subscription`, `apim_name` and approved credential.
   Verify actual GET API/product, HEAD product/API association, complete
   subscription-list pagination and optional API-policy GET observations.
   Retain sanitized status/request correlations; never publish raw policies,
   SDK exceptions, credentials or private resource IDs.
4. Require `api_present`, `product_assigned`, `subscription_key_present` true,
   `hub_contract_status == "ok"`, empty `missing_perms`,
   `foundry_connection_status == "unverified"` and
   `evidence_scope == "hub-arm-inventory"`. The subscription field is legacy
   metadata naming, not proof of key validity or successful authentication.
5. Use separately approved existing negative tuples (or temporary fixtures
   independently authorized and inventoried by the owner): an existing API
   not associated with the selected product must return `product_assigned=false`;
   an unrelated subscription's matching display name must not satisfy exact
   product scope. A deliberately unavailable read using an approved limited
   identity must be `errored`, not `missing` or `ok`. Do not revoke shared
   permissions, unlink existing APIs or manufacture live receipts. If a negative
   tuple/identity is unavailable, report NOT TESTED, not the local result.
6. Separately, if authorized, validate the corrected Hosted Option B on the
   selected already-hosted runtime: unified `azure.yaml` declares
   `AZURE_AI_MODEL_DEPLOYMENT_NAME=connectionName/modelName`; canonical runtime
   consumes it. Read the actual credential-free Foundry connection category,
   target and auth type. A bounded real model request and independently
   correlated gateway evidence must show that this route was used. Caller Entra
   auth is not downstream JWT; the pinned connection uses ApiKey. No credential
   migration, secret export, public fallback or new hosted deployment is implied.
   If this tuple or invocation is not authorized, report that acceptance gate
   BLOCKED/NOT TESTED separately from the hub inventory result.
7. Preserve native errors and every unverified boundary. Positive JWT,
   private routing, policy enforcement and governed actions are separate tests,
   never conclusions from this inventory. Attach only redacted evidence with
   exact source and SDK versions for the PR.
8. Close the resource lifecycle: this read-only protocol creates nothing.
   If the owner separately created temporary fixtures, verify removal of exactly
   that inventory or document an explicitly approved bounded retention handoff.
   Report functional outcome and cleanup outcome separately.

The final report must distinguish HUB_INVENTORY, HOSTED_GATEWAY_ROUTE,
DOWNSTREAM_JWT and CLEANUP. An unavailable scenario is not PASS.
