# citadel-hub-deploy

Wrapper skill for deploying the **AI Citadel Governance Hub** (Layer 1
of the AI Citadel Platform) — APIM AI Gateway + Microsoft Foundry
control plane + telemetry sink — using the
[`Azure-Samples/ai-hub-gateway-solution-accelerator`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator)
`azd` template (branch `citadel-v1`).

See [`SKILL.md`](SKILL.md) for the full skill contract.

## What ships in this skill

```
skills/citadel-hub-deploy/
├── SKILL.md                              # canonical skill contract
├── README.md                             # this file
└── references/
    ├── upstream-pin.md                   # pinned commit SHA + verified surface
    ├── customer-checklist.md             # pre-flight (providers, quota, RBAC, DNS)
    ├── live-audit-notes.md               # live audit against rg-citadel-hub-01
    └── profiles/
        ├── pilot-quickstart.env          # cheapest demo (Developer SKU)
        ├── enterprise-baseline.env       # production-grade (Standard v2 + BYO LA)
        └── vnet-isolated-spoke-aware.env # BYO VNet + DNS (landing zone)
```

## What this skill DOES NOT ship

- **Upstream Bicep is NOT vendored.** Cloned fresh by `azd init` at the
  pinned commit. The 55 KB `main.bicep` and full module tree live at the
  source repo (versioned, MIT-licensed).
- **No fork.** Customizations are env-var overlays applied via
  `azd env set` from the curated `.env` profiles. No patches to upstream Bicep.

## When to use

| Want to … | Use this skill? |
|-----------|-----------------|
| Deploy the central APIM AI gateway hub for an org | ✅ |
| Wire a single agent project into an existing hub | ❌ — use `citadel-spoke-onboarding` |
| Add per-tool-call governance inside the agent process | ❌ — use `foundry-agt` |
| Deploy a single-resource Foundry inside a private VNet (no APIM) | ❌ — use `foundry-vnet-deploy` |
| Switch tenants safely | ❌ — use `azure-tenant-isolation` (and use it before this skill) |

## License & maintenance

Wrapper docs in this skill are MIT (per `awesome-gbb` LICENSE). The
upstream accelerator at the pinned commit is also MIT-licensed by
Microsoft.

When the upstream `citadel-v1` branch advances, bump the pinned SHA in
`references/upstream-pin.md` and re-validate any Known Issues. Profile
`.env` files should be re-tested after any major upstream `bicepparam`
schema change. See `AGENTS.md § 5` for SemVer rules.

## Changelog

See [`SKILL.md` § 13](SKILL.md#13-changelog).
