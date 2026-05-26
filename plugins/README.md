# `awesome-gbb` plugins

Three Copilot CLI plugins that bundle subsets of the 38-skill catalog so
sellers and customers can install whole domains with one command instead
of one skill at a time.

| Plugin | Skills | One-command install |
|---|---|---|
| [`awesome-gbb-basic`](./awesome-gbb-basic/) | 9 — cross-cutting (research, humanizer, pptx, demo, lean safe-check, ip-catalog, copilot-cli-bootstrap) | `copilot plugin install awesome-gbb-basic@awesome-gbb` |
| [`awesome-gbb-azure`](./awesome-gbb-azure/) | 21 — Foundry, memory, governance, azd, cost, tenant isolation | `copilot plugin install awesome-gbb-azure@awesome-gbb` |
| [`awesome-gbb-threadlight`](./awesome-gbb-threadlight/) | 25 — 8 threadlight-* + the Foundry/Azure/basic skills it depends on | `copilot plugin install awesome-gbb-threadlight@awesome-gbb` |

Register the marketplace first:

```bash
copilot plugin marketplace add aiappsgbb/awesome-gbb
copilot plugin marketplace browse awesome-gbb
```

> Plugins also work in [Copilot Desktop App (preview)](https://github.com/github/app),
> [VS Code Copilot Chat agent mode (preview)](https://code.visualstudio.com/docs/copilot/chat/chat-agent-mode),
> and [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) via the same
> cross-runtime [plugin spec](https://docs.github.com/en/copilot/reference/cli-plugin-reference).

---

## Source of truth + build model

Every skill lives under [`skills/<name>/`](../skills/) at the repo root.
That stays the source of truth — the per-skill `gh skill install
aiappsgbb/awesome-gbb <name>` workflow is unchanged.

For each plugin, [`scripts/build-plugins.py`](../scripts/build-plugins.py)
copies the source skill trees into `plugins/<plugin>/skills/<name>/` so
the plugin install package is self-contained. The `skills/` subdirectory
inside each plugin is **generated content** — do **not** hand-edit it.

```
awesome-gbb/
├── skills/                        ← source of truth
│   ├── gbb-humanizer/SKILL.md
│   ├── foundry-iq/SKILL.md
│   └── …
├── plugins/
│   ├── awesome-gbb-basic/
│   │   ├── plugin.json
│   │   ├── README.md
│   │   └── skills/                ← generated copies
│   │       ├── gbb-humanizer/...
│   │       └── …
│   ├── awesome-gbb-azure/
│   └── awesome-gbb-threadlight/
└── .github/plugin/
    └── marketplace.json           ← lists all 3 plugins
```

---

## Dependency model

`plugin.json` has **no `dependencies` field** per the official spec. The
spec deduplicates skills by their SKILL.md `name` (first-loaded-wins), so
the same skill can appear in multiple plugins safely.

This is how `awesome-gbb-threadlight` declares its dependencies: it bundles
the Foundry/Azure skills its 8 threadlight-* skills cross-reference
(foundry-hosted-agents, foundry-memory, foundry-observability,
foundry-iq, azd-patterns, azure-tenant-isolation, etc.). Install just the
threadlight plugin → fully
working pipeline. Install both threadlight + azure → dedup resolves the
overlap at runtime.

---

## Authoring workflow

1. Edit `skills/<name>/SKILL.md` (or anything else under `skills/<name>/`)
2. Add `<name>` to the appropriate plugin's `plugin.json` `skills` list
   (if it's not already there)
3. Run `python scripts/build-plugins.py --write` to sync the plugin copies
4. Commit both the source change and the regenerated plugin copies in
   the same commit
5. CI runs `python scripts/build-plugins.py --check` and fails if you
   forgot step 3

Skill version bumps follow [AGENTS.md § 5](../AGENTS.md). Plugin version
bumps follow the same rules at the bundle level.
