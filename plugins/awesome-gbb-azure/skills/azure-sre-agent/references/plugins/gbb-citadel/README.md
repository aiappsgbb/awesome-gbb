# gbb-citadel

Azure SRE Agent plugin for **AI Citadel APIM gateway** operations. Pairs
with engagements built on the awesome-gbb Citadel skills
([`citadel-hub-deploy`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/citadel-hub-deploy),
[`citadel-spoke-onboarding`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/citadel-spoke-onboarding)).

## Skills

- **`apim_throttle_expert`** — investigates 429s from the Citadel gateway. Correlates per-product quota, named-value rate-limit keys, and backend pool TPM utilization.
- **`jwt_403_debug_expert`** — investigates 401/403s at the Citadel gateway. Decodes JWT claims, verifies Access Contract scope grants, validates Foundry MI token audience.

## Install

Two paths:

### A — official marketplace path (when this plugin has been merged into `Azure/sre-agent-plugins`)

```bash
git clone https://github.com/Azure/sre-agent-plugins.git
cd sre-agent-plugins/plugins/gbb-citadel
./install.sh <agent-name> <resource-group>
```

### B — direct push from awesome-gbb (until upstream merge)

```bash
# from awesome-gbb repo root
python3 skills/azure-sre-agent/scripts/data_plane.py install-plugin \
  --agent <agent-name> \
  --resource-group <agent-rg> \
  --plugin-dir skills/azure-sre-agent/references/plugins/gbb-citadel/
```

`data_plane.py` authenticates via DefaultAzureCredential, gets an
`https://azuresre.dev/.default` token, looks up the agent's data-plane URL
from ARM, and pushes each skill via the
`/api/v1/skills/upload-zip-bundle` endpoint.

## Verify

After install, the SRE Agent should respond to:

> "Why is the Citadel gateway returning 403 to my hosted agent?"

with an investigation that uses `jwt_403_debug_expert`.

## Cross-skill notes

- These skills do NOT modify APIM policy XML or named values — read-only investigation only. Any change requires human action.
- For deeper Citadel hub debugging (provisioning issues), use the `citadel-routed` recipe in `references/recipes/`, which ships the same investigative skills as part of the agent's initial config.
