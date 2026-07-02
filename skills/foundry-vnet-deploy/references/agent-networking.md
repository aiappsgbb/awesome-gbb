# Agent networking deep-dive (bring-your-own VNet)

> **Source of truth.** Distilled from the official Microsoft Foundry doc
> [*Agents networking deep-dive*](https://learn.microsoft.com/azure/foundry/agents/concepts/agents-networking-deep-dive)
> (`articles/foundry/agents/concepts/agents-networking-deep-dive.md`). When the
> two disagree, the upstream doc wins — open an issue to re-sync this file.
>
> This reference explains **how agent traffic flows through the injected
> subnet, how IPs are allocated, how big the subnet must be, and which signals
> mean you are running out of capacity.** It is background for the subnet-sizing
> decision in `SKILL.md` Step 6 — it does not change any deployment command.

---

## 1. Two traffic paths: hosted vs prompt agents

The Foundry platform network hosts the Foundry endpoint, the **Micro VM host
layer** (runs hosted agents), the **Tools Service**, and the **Data Proxy host
layer**. Your customer VNet contributes a **delegated subnet** (where Micro VMs
and data proxies consume IPs) and a **private-endpoint subnet** (PEs to your
storage, databases, Key Vault).

| Agent type | Request path |
|---|---|
| **Hosted agent** | Client → Foundry endpoint → **Micro VM** (`/invoke`) → Tools Service → Data Proxy → your resources via private endpoints |
| **Prompt agent** | Client → Foundry endpoint → Tools Service → Data Proxy → your resources via private endpoints (**no Micro VM on this path**) |

Key architecture facts:

- **Single-tenant data proxy, one per project.** Every Foundry *project* gets
  its own isolated data proxy instance. **All tool calls route through the data
  proxy**, regardless of agent type.
- **Hosted-agent Micro VM has two NICs.** The agent's *own* outbound traffic
  goes direct through the Micro VM's dedicated NIC in the delegated subnet;
  *tool-server* calls still route through the single-tenant data proxy.
- **Subnet config is account-level.** All projects in a Foundry account share
  the same delegated subnet — hosted and prompt agents included. Size the
  subnet for the *combined* IP usage across every project, plus upgrades and
  scaling.

---

## 2. IP allocation model

- IPs are reserved at roughly a **1 IP per 10 pods** ratio.
- Each project's data proxy starts at **1 pod (1 replica)** and scales out with
  traffic — more traffic per project ⇒ more pods ⇒ more IPs.

| Scenario | Example | IP impact |
|---|---|---|
| Low traffic | 10 projects × 1 replica | ~1 IP shared across 10 pods |
| High traffic | 10 projects × 10 replicas | 100 pods, ~10 IPs |

Project IP consumption is therefore **dynamic** — it rises and falls with load.

---

## 3. Subnet size and concurrent sessions

**The platform supports a maximum of 50 concurrent agent sessions per
subscription per region.** That ceiling is fixed — it does **not** scale up
with a bigger subnet. Your subnet size only determines whether you can *reach*
that maximum and how much headroom you keep for project density and upgrades.

| Agent subnet CIDR | Usable IPs | Concurrent sessions | Use when |
|---|---|---|---|
| **/24** | 251 | 50 (platform cap) + upgrade/scale buffer | **Production default** — Microsoft-recommended |
| /25 | 123 | 50 (platform cap) | Buffer between /26 and /24 |
| /26 | ~59 | ~50 — **minimum to reach the cap** | Smallest subnet that supports the full 50 |
| /27 | ~27 | ~17 | Dev/test only — **minimum, risky**, exhausts fast |

> The upstream doc publishes only the /27 (~17) and /26 (~50, "maximum
> supported") rows. The /24 and /25 rows here are extrapolated for planning:
> because 50 sessions is the platform cap, both simply give you the cap **plus**
> spare IPs for projects and maintenance spikes.

**Rules of thumb:**

- **/24 for production.** A /24 gives enough buffer to absorb the temporary IP
  spike during Microsoft-managed platform upgrades (old + new infra run in
  parallel).
- **/26 is the minimum to reach the full 50 sessions.** /27 tops out around 17.
- **Target < 80 % subnet utilization.** Don't plan to run at the theoretical
  maximum — leave room for upgrade and scaling spikes.

---

## 4. Project capacity

A Foundry instance supports **~250 projects at low traffic**. Under heavy
traffic — when agents scale to many replicas — the effective limit can drop to
**as few as ~25 projects**. When the subnet runs out of IPs, **new project
provisioning fails**. (Note: ~250 is a *project* count, not a session count —
concurrent sessions are always capped at 50 per subscription per region.)

---

## 5. Hosted vs prompt revision behavior

| | Hosted agents | Prompt agents |
|---|---|---|
| Compute | Micro VM (ACA), you control CPU/memory, deployed via **your own ACR** | Fully Microsoft-managed compute |
| **Revisions consume subnet IPs?** | **Yes** — old + new revisions run in parallel during rollout, both consume IPs | **No** — data proxy runs single-revision; inactive revisions don't affect IPs |
| Revision limits | **100 active** / **1,000 total revisions per agent name** (oldest inactive purged automatically) | n/a |
| Instance limit | ~**200 hosted agents** per Foundry instance (preview) — separate from the ~250 project cap | **No hard limit** on prompt agent count |

The practical consequence: **hosted-agent deploy churn is what eats the subnet.**
A busy hosted agent that redeploys often keeps two revisions live per rollout,
each drawing IPs. Prompt agents are effectively free on the IP budget.

---

## 6. Address-space rules

- **RFC 1918 private IPv4 only:** `10.0.0.0/8`, `172.16.0.0/12`
  (172.16–172.31.x), `192.168.0.0/16`.
- **CGNAT `100.64.0.0/10` is not supported** — public and CGNAT ranges cause
  routing failures.
- **Avoid `172.17.0.0/16`** — reserved by Docker bridge networking.
- **No overlapping ranges.** All peered VNets must use unique, non-overlapping
  ranges (applies to bidirectional peering too). Overlaps cause routing
  failures.

---

## 7. Capacity / exhaustion signals

The Azure portal **does not** expose IP utilization for delegated subnets, so
you cannot monitor it directly. Watch these leading indicators instead:

| Signal | Means |
|---|---|
| **HTTP 5xx from the data proxy** | Data proxy can't scale — subnet IPs likely exhausted |
| **Hosted-agent session creation failing with 4xx** | Platform can't allocate a Micro VM for a new session |

When IPs are exhausted, **data proxy scaling and new project provisioning both
fail**, and hosted agents can't allocate a Micro VM for new sessions. The
platform does **not** proactively warn you — monitor data-proxy health and
hosted-agent session-creation success as your early-warning system.

---

## 8. Quick reference

| Dimension | Guidance |
|---|---|
| Subnet size | **/24 for production.** /27 is the minimum but risky; /26 is needed for the full 50 concurrent sessions. |
| Concurrent sessions | **50 per subscription per region** (platform cap — doesn't grow with subnet). |
| Project capacity | ~250 at low traffic, as few as ~25 at full scale. Driven by IP availability. |
| IP ratio | ~1 IP per 10 pods; one data proxy per project, scales with traffic. |
| IP consumption | Hosted-agent revisions consume IPs. Prompt-agent revisions don't. |
| Supported ranges | RFC 1918 only (`10.x`, `172.16`–`172.31.x`, `192.168.x`). No public, no CGNAT, avoid `172.17.0.0/16`. |
| Utilization target | ≤ 80 % to absorb upgrade + scaling spikes. |
| Exhaustion signals | 5xx from data proxy; hosted-agent session-create 4xx. |

---

## See also

- `SKILL.md` Step 6 — subnet sizing during the deployment interview.
- [`agent-tools-network-isolation.md`](agent-tools-network-isolation.md) — which
  agent **tools** work behind the isolated VNet and how their traffic flows.
- Upstream: [Agents networking deep-dive](https://learn.microsoft.com/azure/foundry/agents/concepts/agents-networking-deep-dive)
  · [Set up private networking for Foundry Agent Service](https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks)
