# Microsoft resource authentication profiles

**PREPARED / NOT TESTED.** Source review: 2026-09-11. These are readiness
contracts, not connector implementations or evidence of licensed-service
access. The validation tenant does not supply the required service licenses.
Do not provision connections, consent, resource grants or test data from this
document without separate operator approval and an eligible target tenant.
Actual results belong only in the [status matrix](../../../docs/maintenance/foundry-mcp-auth-validation.md#final-acceptance-remains-unchanged).
Endpoint/audience examples below are for the public Microsoft cloud.
Sovereign-cloud routes require their own publisher contract, not suffix
substitution or automatic reuse of these audiences.

## Choose the boundary before the credential

| Route | Token boundary | Ownership |
|---|---|---|
| Native Foundry/Toolbox -> published Microsoft MCP | Publisher's documented audience, scopes and supported delegated connection type. | Use that publisher's connection workflow; the custom-API OAuth builder is not a universal native-service builder. |
| Foundry -> custom MCP API A -> downstream API B | First a user token with `aud=A`; then a proper user OBO exchange for B using A's own confidential-client credentials. | Keep the existing inbound verifier; implement and test the downstream boundary separately. OBO is not implemented here. |
| App-only service access | Application permissions and client credentials supported by the selected API. | Separate operator-approved profile and tests; never a fallback when a user token or consent is missing. |

The existing `UserEntraToken` bridge is for first-party **Foundry Toolbox**
with audience `https://ai.azure.com`. It is not a generic bridge to Graph,
Fabric or an arbitrary custom server. Successfully receiving the user's
MCP token does not confer permissions or licenses for another resource.
Use `tid` + `oid` for user identity and the authorized operation's `scp`;
UPN, `preferred_username` and `name` are mutable display data, not access keys.

## Fabric IQ

Status: **NOT TESTED - licensed target required.** The [Foundry Fabric IQ
contract][fabric] distinguishes item types and connection routes. Do not
normalize all of them to one Fabric audience or one permission set.

### Fabric prerequisites common to the selected route

- Invoking users need a Fabric license granting access to the relevant agent
  queries, not just a valid Entra account.
- A Fabric data agent must be published on paid **F2+** Fabric capacity or
  **P1+** Power BI Premium capacity with Fabric enabled. It needs supported
  source data; the caller needs read access to the data agent **and** its
  sources. Data agent and source capacities must be in the same region.
- Check relevant Fabric tenant settings, including cross-geo processing and
  storage where required. Record data-boundary approval; private transport
  does not waive geographic or service processing terms.
- Verify the developer's connection-management permission, runtime's platform
  permission and invoking user's project/content access separately. The
  source lists Foundry User/Project Manager roles for setup; do not grant all
  users developer or administration rights merely to make a read succeed.

### Fabric route contracts

| Item / route | Endpoint | Resource and delegated permission contract |
|---|---|---|
| Data agent, native Foundry BYO Entra OAuth | `https://{host}/v1/mcp/workspaces/{workspaceId}/dataagents/{dataAgentId}/agent` | Source recipe requests `https://analysis.windows.net/powerbi/api/DataAgent.Execute.All` plus `offline_access`, with required admin/user consent. This is the Power BI resource contract for this route. |
| Data agent, direct MCP client | Same published data-agent endpoint | The direct-client section requests `https://api.fabric.microsoft.com/.default`. It documents user **or** service-principal authentication; app-only is a separate profile, not proof of delegated Foundry passthrough. |
| Data agent, workspace-private Foundry route | Host `{workspaceIdWithoutDashes}.z{first2chars}.w.api.fabric.microsoft.com` with the same data-agent path; derive it from the documented workspace identity, never a guessed public fallback | Dedicated `UserEntraToken` connection, audience `https://analysis.windows.net/powerbi/api`. Do not substitute the AI audience used by the Toolbox bridge. |
| Ontology, native delegated OAuth | `https://{host}/v1/mcp/dataPlane/workspaces/{workspaceId}/items/{itemId}/ontologyEndpoint` | The ontology setup specifies Power BI delegated `Item.Execute.All` and `Item.Read.All`, requested as `https://analysis.windows.net/powerbi/api/Item.Execute.All` and `https://analysis.windows.net/powerbi/api/Item.Read.All`, plus `offline_access` and appropriate consent. |
| Power BI semantic model, native BYO/managed OAuth | `https://{host}/v1/mcp/fabricaihub/integrations/m365` | Delegated OAuth is documented, but the reviewed ontology scope pair is **not** an established semantic-model scope contract. Verify the selected publisher endpoint's exact audience/scopes before any provisioning. Do not infer `DataAgent.Execute.All` or a global Fabric audience. This unresolved permission selection is an explicit readiness gate, not runnable placeholder configuration. |

For a public item, `{host}` is the published Fabric API host from the selected
item's documented connection. Workspace-private data agents use the specific
host above. A Foundry BYO OAuth recipe and a direct MCP client example are
different routes: do not silently replace either scope set with the other.
The Fabric UI scope example uses commas; OAuth scope strings normally use
spaces, while the generic connection definition uses an array. Follow the
selected UI/CLI/wire schema rather than copying punctuation across schemas.

### Fabric network and acceptance contract

| Item | Documented native integration network support |
|---|---|
| Ontology | Tenant-level Private Link |
| Data agent | Tenant-level and workspace-level Private Link |
| Power BI semantic model | **Public access only** in this integration contract |

Validate actual Foundry/runtime DNS, target host, Entra/consent egress and the
chosen private endpoint route. Do not advertise private support for the
semantic-model route or expose the custom MCP publicly as a workaround.
Only data-agent MCP items are documented for the integration's long-running
background mode; do not assume ontology/semantic-model calls inherit it.
No job/callback framework is supplied by this skill.

Positive acceptance: a licensed, consented user invokes the selected item and
gets a result attributable to authorized source data, with actual tool evidence.
Negative acceptance: reject an unlicensed caller, missing consent, unavailable
capacity, denied item/source access, wrong audience or unsupported network
route without using application identity or public access as fallback. Test
two users with different source rights, refresh/revocation and Conditional
Access on the exact route. Permission/capacity changes belong to an authorized
operator, not automatic runtime remediation.

## Native Microsoft SharePoint/OneDrive MCP

Status: **NOT TESTED - eligible Microsoft 365 target and endpoint required.**

The [Foundry MCP authentication catalog][mcp-auth] lists Microsoft
SharePoint/OneDrive MCP (Server Frontier) with delegated
`McpServers.OneDriveSharepoint.All` on the **Agent365Tools** resource.
Use the catalog's published resource application ID when qualifying that
scope, plus `offline_access` for the documented custom Entra OAuth flow.
Resolve the actual MCP endpoint from the current publisher/tenant catalog;
this reference deliberately invents no endpoint URL.

This permission is **not** Graph `Files.Read` or `Sites.Selected`, and an
Agent365Tools token must not be sent to this skill's custom MCP API.
Confirm endpoint, resource identifier, scope serialization, OAuth redirect
and tenant availability before enabling the native connection.

Prerequisites include the underlying SharePoint/OneDrive entitlement and
the user's actual content rights. [Agent 365 eligibility][agent365-plan] is
feature/plan-specific: standalone availability with eligible Microsoft 365
plans and inclusion in E7 do not establish every feature for every tenant.
Check the applicable feature matrix and Frontier availability. Do not impose
a universal Copilot-license rule on the separate direct Graph route.

[Agent 365 SharePoint integration][agent365-sharepoint] describes an agent's
**own identity/access and governance**. That is not evidence of the current
user's delegated passthrough. Keep the two designs and acceptance records
separate. Validate the native endpoint's actual reachability and outbound
identity dependencies; a private custom MCP demo proves neither.

Positive acceptance: the real user consents and retrieves approved work/school
content through the selected native MCP, with tool-level evidence and preserved
user access trimming. Negative acceptance: deny missing entitlement, denied
content access, missing/revoked consent, wrong resource audience and a second
user without access. A service principal or agent identity succeeding is not
the delegated-user result.

## Custom MCP -> Microsoft Graph

Status: **NOT TESTED - work/school resource access and downstream OBO required.**
This is an alternative to the native MCP, not a relabeling of its permission.
Personal Microsoft accounts and OneDrive consumer support differ; this
prepared profile is limited to enterprise work/school accounts.

The downstream API endpoint is **`https://graph.microsoft.com/v1.0`** and the
token is for the **Microsoft Graph resource**, not the AI, Power BI,
Agent365Tools or custom-MCP audience. Select the exact read operation and its
published API permission table before implementation. For a bounded proof,
prefer an explicitly selected file, list or site over tenant-wide discovery.

| Target | Narrow permission/resource-grant candidate |
|---|---|
| OneDrive/SharePoint file or folder | `Files.SelectedOperations.Selected`, with an explicit assignment on the approved resource and a supported drive-item read operation |
| SharePoint site collection | `Sites.Selected`, with an explicit `read` assignment on the approved site and a supported site/content read operation |
| Specific SharePoint list/item | The applicable `Lists.SelectedOperations.Selected` or `ListItems.SelectedOperations.Selected` scope and corresponding selected-resource assignment |

The [Selected permissions contract][selected] requires **all three**:
consent to the selected scope, explicit application assignment on the selected
resource, and a valid scoped token. **Consent alone grants zero resource
access.** Selected permissions support delegated and application modes;
delegated access is the intersection of the user's rights and the app's grants.
Do not use broad `Files.*All`/`Sites.*All` permissions as the default repair.

The resource assignment must be provisioned by an authorized operator with
the necessary grant-management rights. Never elevate the MCP runtime so it
can grant itself access. Selecting at list/item/file granularity can break
permission inheritance and consume unique-permission limits; include that
impact in the provisioning review. API access creates neither licenses nor
content: confirm entitlement, provisioned drive/site and actual user rights.

A Graph scope does not automatically cover SharePoint REST
`https://{tenant}.sharepoint.com/_api/...`; that would be a distinct API
resource contract and is not implemented here. A private MCP still requires
approved egress to Graph and Entra; do not claim the downstream Graph endpoint
became private because the MCP uses Private Link.

Positive acceptance: a real delegated user reads one approved selected
resource through API A's supported OBO call to Graph. Negative acceptance:
consent without assignment, assignment without user rights, a different
unselected resource, missing scope, wrong tenant, another user, revoked access
and denied consent must not produce data. Keep app-only tests separate.
No current code calls Graph or provisions these grants.

## Downstream OBO and interaction readiness

Before implementing any custom MCP -> resource route, record and approve:

| Requirement | Contract |
|---|---|
| Inbound assertion | A delegated user access token with `aud=API A`, verified by the custom MCP. Never a portal token copied from storage or a token intended for API B. |
| Middle-tier identity | API A's **own confidential-client credentials**, not blind reuse of the upstream Foundry OAuth broker's client secret. Use approved secret custody; never log the assertion or returned tokens. |
| Downstream token | Acquire token B through the maintained MSAL/library OBO flow for B's approved delegated scopes/consent. App-only uses a separate supported client-credentials flow, not OBO. |
| Token validation | Validate only the incoming token for the API you own. Downstream Microsoft tokens can be opaque/encrypted; do not require decoding them with this skill's custom-MCP JWT verifier. API B validates its own token. |
| Cache isolation | Maintained-library cache handling partitioned by tenant, user, client, resource/scopes and claims context. No shared global bearer, label-keyed cache or managed-identity fallback. |
| Consent and lifetime | Correct resource consent and human interaction, encrypted/protected cache custody, refresh, explicit denial, revocation and expiry handling. Retaining infrastructure does not extend token lifetime. |
| Claims challenge | Handle API B's `401` / `WWW-Authenticate` `insufficient_claims`/`claims` through a supported client interaction. Repeating the same cached token is not remediation. Do not enable `cp1` until complete challenge handling is implemented and tested. |
| Foundry boundary | Verify that the selected Foundry/MCP/Toolbox route can surface the downstream challenge and resume correctly. Native connection consent is not proof that arbitrary downstream Conditional Access challenges work. |

Sources: [Entra OBO][obo] and [claims challenges][challenge].
These are requirements, **not an implemented token exchange or cache**.
Positive testing must show the same real user across the two distinct resource
audiences and an authorized downstream operation. Negative testing must cover
wrong-audience assertions, app-only input, denied consent, missing resource
assignment, tenant/user cache isolation, Conditional Access challenges,
refresh/revocation and network failure without unauthorized fallback.

[fabric]: https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq
[mcp-auth]: https://learn.microsoft.com/azure/foundry/agents/how-to/mcp-authentication
[agent365-plan]: https://learn.microsoft.com/office365/servicedescriptions/microsoft-agent-365/microsoft-agent-365
[agent365-sharepoint]: https://learn.microsoft.com/microsoft-agent-365/admin/sharepoint-integration
[selected]: https://learn.microsoft.com/graph/permissions-selected-overview
[obo]: https://learn.microsoft.com/entra/identity-platform/v2-oauth2-on-behalf-of-flow
[challenge]: https://learn.microsoft.com/entra/identity-platform/claims-challenge
