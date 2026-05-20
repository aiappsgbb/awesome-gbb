# gbb-foundry

Azure SRE Agent plugin for **Microsoft Foundry hosted-agent** operations.
Pairs with engagements built on the awesome-gbb Foundry skills
([`microsoft-foundry`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/microsoft-foundry),
[`foundry-hosted-agents`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/foundry-hosted-agents),
[`ghcp-hosted-agents`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/ghcp-hosted-agents)).

## Skills

- **`hosted_agent_deploy_expert`** — investigates failed hosted-agent deploys. Knows MAF 1.4.0 breakage patterns, ACR push status, ACA revision rollout, and BYOK provisioning.
- **`byok_401_debug_expert`** — the silent BYOK 401 (Foundry User RBAC scoped to project but missing at CognitiveServices account). Encodes the exact fix.
- **`quota_throttle_expert`** — AOAI deployment TPM exhaustion. Pulls capacity vs utilization, recommends scale-up or PTU migration.

## Install

### A — official marketplace path (after upstream merge)

```bash
git clone https://github.com/Azure/sre-agent-plugins.git
cd sre-agent-plugins/plugins/gbb-foundry
./install.sh <agent-name> <resource-group>
```

### B — direct push from awesome-gbb

```bash
python3 skills/azure-sre-agent/scripts/data_plane.py install-plugin \
  --agent <agent-name> \
  --resource-group <agent-rg> \
  --plugin-dir skills/azure-sre-agent/references/plugins/gbb-foundry/
```

## Verify

After install, the SRE Agent should respond to:

> "Why does my Foundry hosted agent return 401 on BYOK calls?"

with `byok_401_debug_expert` running its 6-step investigation.

## Cross-skill notes

- The skills in this plugin encode known issues (KIs) tracked in
  `references/upstream-pin.md` of `foundry-hosted-agents` and
  `ghcp-hosted-agents`. When upstream fixes a KI, the skill should be
  updated to reflect the new diagnosis path.
- This plugin is read-only — RBAC changes always require human action.
