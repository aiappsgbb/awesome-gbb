# Agent tools with network isolation

> **Source of truth.** Distilled from the official Microsoft Foundry how-to
> [*Configure network isolation* →
> *Agent tools with network isolation*](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link#agent-tools-with-network-isolation)
> (`articles/foundry/how-to/configure-private-link.md`). When the two disagree,
> the upstream doc wins — open an issue to re-sync this file.
>
> Use this when a user asks **"will tool X work once my Foundry is network
> isolated?"** It maps every agent tool to its support status and traffic path,
> then lists the isolation-specific limitations, firewall allowlist, and
> troubleshooting steps. Scope: **new Responses-API agents** created through
> SDK/CLI or the new Foundry portal — **not** classic-portal agents.

---

## 1. Tool reachability matrix

| Tool | Support status | Traffic flow |
|---|---|---|
| **MCP Tool (Private MCP)** | ✅ Supported | Through your VNet subnet |
| **Azure AI Search** | ✅ Supported | Through private endpoint |
| **OpenAPI tool** | ✅ Supported | Through your VNet subnet |
| **Azure Functions** | ✅ Supported | Through your VNet subnet |
| **Agent-to-Agent (A2A)** | ✅ Supported | Through your VNet subnet |
| **Foundry IQ** (preview) | ✅ Supported | Via MCP |
| **Function Calling** | ✅ Supported | Microsoft backbone network |
| **Code Interpreter** | ⚠️ Partial | Microsoft backbone. **Works without files.** File upload/download not supported — workaround: use the SDK to create a container with the files and pass the `container_id` (not available in the portal UI). |
| **Bing Grounding** | ✅ Supported | **Public endpoint** |
| **Websearch** | ✅ Supported | **Public endpoint** |
| **SharePoint Grounding** | ✅ Supported | **Public endpoint** |
| **Fabric Data Agent** | ❌ Not supported | Fabric resource must have **public network access enabled** (workspace-level private-link Fabric unsupported) |
| **Logic Apps** | ❌ Not supported | Under development |
| **File Search** | ❌ Not supported | Under development |
| **Browser Automation** | ❌ Not supported | Under development |
| **Computer Use** | ❌ Not supported | Under development |
| **Image Generation** | ❌ Not supported | Under development |

> **Public-endpoint caveat.** Bing Grounding, Websearch, and SharePoint
> Grounding are *supported* but communicate over the **public internet** — they
> need no private endpoint or VNet config. If your compliance posture requires
> all traffic to stay on a private network, these three may not qualify. You
> can block them with Azure Policy if users must not call public-endpoint tools.

---

## 2. Configuration by traffic pattern

**① Tools using your VNet subnet** — MCP Tool, Azure AI Search, OpenAPI, A2A,
Azure Functions. These reach your resources through the injected subnet /
private endpoints. End-to-end setup (including private MCP) is shown in the
official sample
[`19-hybrid-private-resources-agent-setup`](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/19-hybrid-private-resources-agent-setup).

**② Tools using the Microsoft backbone** — Code Interpreter, Function Calling.
**No private endpoints or extra networking config required**; traffic stays
inside Microsoft's backbone.

**③ Tools using public endpoints** — Bing, Websearch, SharePoint. No private
endpoints needed, but they egress to the public internet. Block with Azure
Policy if that violates your posture.

> **Private AI Search + private Foundry:** if your AI Search has public network
> access disabled and you use it as an agent tool, you **must build the agents
> in the new Foundry portal** — this is unsupported in the classic Agent
> service. For a fully worked end-to-end AI Search + tools isolation setup,
> follow sample template `19-hybrid-private-resources-agent-setup` (linked
> above) rather than hand-wiring the indexer.

---

## 3. Feature limitations under network isolation

Beyond tools, these **Foundry features** don't yet fully support isolation:

| Feature | Status | Notes |
|---|---|---|
| Synthetic Data Gen for Evaluations | Not supported | Bring your own data to run evaluations. |
| **Traces** | Not supported | No VNet support with a **private Application Insights** yet. |
| Workflow Agents | Partial | Inbound (UI/SDK/CLI) works; **outbound VNet injection is not** supported. |
| AI Gateway (APIM) | Partial | A gateway created from the Foundry UI is **automatically public**. For data-plane actions against a private Foundry, configure network isolation on the gateway via the Azure Portal. |
| Certain agent tools | Partial | See the matrix in §1. |

---

## 4. Load-bearing isolation gotchas

These four constraints break deployments if missed:

1. **Hosted agents need a *public* Azure Container Registry.** A private-endpoint
   ACR (public access disabled) is **not yet supported** with a private Foundry
   setup — the ACR must keep **public network access enabled**. Hosted agents
   still deploy onto a VNet-injected private Foundry; you do **not** need to
   redeploy Foundry to enable them.
2. **You cannot change outbound networking after the fact.** You can't swap the
   delegated subnet, and you can't add VNet injection to an existing
   non-injected Foundry. **Adding or changing outbound networking requires a
   full redeploy** of Foundry.
3. **`172.17.0.0/16` is reserved** by Docker bridge networking — never use it
   for the VNet.
4. **Publishing agents to Teams/M365** works with a public-access-disabled
   Foundry but has extra setup (custom-engine-agents-through-the-firewall flow).

---

## 5. Firewall FQDN allowlist

If you place an Azure Firewall (or hub-and-spoke shared firewall) in front of
the injected subnet to inspect egress, allowlist these trusted FQDNs by
scenario:

| Scenario | FQDNs | Why |
|---|---|---|
| **Agents** | `*.identity.azure.net`, `login.microsoftonline.com`, `*.login.microsoftonline.com`, `*.login.microsoft.com` (or the **AzureActiveDirectory** service tag) | Required for the ACA delegation that runs the agent service |
| **Evaluations & Traces** | `*.blob.core.windows.net`, `settings.sdk.monitor.azure.com` | Evaluators catalogue + sending results to the linked App Insights |
| **Finetuning** | `raw.githubusercontent.com` | Curated sample dataset download in the Foundry portal |

Hub-and-spoke pattern: put the shared firewall in a **hub** VNet and the Foundry
networking in a **spoke** VNet, then peer them. (A standalone project without a
hub will differ — adapt peering/firewall to your layout.)

---

## 6. Private-endpoint limitations

- **Same region + subscription:** the private endpoint must be in the same
  region and subscription as the VNet.
- **Approved only:** only PEs in an **Approved** state pass traffic. Without
  **Contributor**/**Owner** on the Foundry resource, connections stay
  **Pending** until an owner approves them (Networking → Private endpoint
  connections).

---

## 7. Troubleshooting

**Private endpoint**

- *Stuck in Pending* → you need Contributor/Owner on the Foundry project, or ask
  the owner to approve.
- *PE creation fails* → you need **Network Contributor** on the VNet+subnet;
  check the subnet isn't out of IPs.

**DNS resolution**

- *Resolves to a public IP* → confirm a `privatelink` private DNS zone exists
  and is linked to the VNet. Run `nslookup <foundry-endpoint-hostname>` **from
  inside the VNet**; it must return the private IP.
- *Custom DNS not resolving* → forward `privatelink` queries to Azure DNS
  `168.63.129.16`.
- *Intermittent DNS* → ensure the DNS server is reachable from all subnets;
  check NIC/VNet DNS settings.

**Connectivity**

- *Times out on 443* → NSG must allow outbound to the PE IP on 443; verify no
  firewall is blocking.
- *Can't reach from on-prem* → verify VPN/ExpressRoute is up and route tables
  include the VNet address space.
- *403 Forbidden* → usually **auth**, not networking — check RBAC on the Foundry
  project.

**Agent-specific**

- *Agent fails to start* → verify you're using **Standard** agent deployment
  (not Basic), network injection is configured, and the subnet has free IPs.
- *Agent can't reach MCP tools* → ensure PEs exist for every Azure service the
  MCP tools touch, the managed identity has the right RBAC, and firewall rules
  permit agent → service traffic.
- *Evaluation runs fail with network errors* → confirm all required DNS zones
  are configured and the eval compute can reach Foundry + model endpoints via
  private link.
- *Agent timeouts on external API calls* → allow outbound HTTPS to those
  destinations on the firewall, or deploy a NAT gateway for controlled egress.

---

## See also

- [`agent-networking.md`](agent-networking.md) — subnet sizing, IP allocation,
  and traffic flow behind the isolated VNet.
- `SKILL.md` Step 6 / Step 8 — VNet + DNS configuration during the interview.
- Sample: [`19-hybrid-private-resources-agent-setup`](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/19-hybrid-private-resources-agent-setup) — end-to-end agent-tools-in-isolation reference.
- Upstream: [Configure network isolation for Microsoft Foundry](https://learn.microsoft.com/azure/foundry/how-to/configure-private-link)
