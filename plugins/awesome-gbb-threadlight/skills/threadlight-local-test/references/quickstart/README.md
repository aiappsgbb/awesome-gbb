# threadlight_quickstart — Pattern 0 reference package

Drop-in implementation of the **Pattern 0 — Quickstart** runtime
documented in `../SKILL.md`. Lets any threadlight-designed PoC boot
a screen-shareable demo in minutes:

```
python -m threadlight_quickstart           # Streamlit UI on http://localhost:8501
python -m threadlight_quickstart --check   # CI-friendly sanity check, no UI
python -m threadlight_quickstart --info    # print the discovered layout, no LLM
python -m threadlight_quickstart --simulator  # pre-load the demo-script prompts
```

## What it consumes (from threadlight-design output)

| File / dir | Purpose | Required? |
|---|---|---|
| `specs/sample-data/<entity>.json` | One JSON array per entity → in-memory store + CRUD tools | **Yes** (≥ 1 entity) |
| `src/agent/skills/<name>/SKILL.md` | Wired into `SkillsProvider` for progressive disclosure | No (agent runs without) |
| `tests/demo-prompts.txt` | One prompt per line; simulator source | No |
| `specs/prep-guide.html` | Fallback simulator source (regex on `<strong>Type this:</strong>`) | No |
| `tests/quickstart_tools.py` | PoC-side tool overrides (`register(tools, stores) -> list`) | No |

## Install into a PoC

```bash
# from the PoC root
pip install -e <awesome-gbb>/skills/threadlight-local-test/references/quickstart
cp <…>/quickstart/.env.local.example .env.local
$EDITOR .env.local              # FOUNDRY_PROJECT_ENDPOINT, MODEL_DEPLOYMENT_NAME
az login --tenant <dev-tid>     # see azure-tenant-isolation skill
python -m threadlight_quickstart --check     # sanity (~5s)
python -m threadlight_quickstart             # full UI
```

(`cp` the bundled `Makefile.demo` into the PoC root if you want `make demo`.)

## Try the fixture without a real PoC

```bash
cd fixture-poc
python -m threadlight_quickstart --info
python -m threadlight_quickstart --check     # needs an LLM unless agent_framework absent
```

The fixture ships:
- 1 entity (`tickets`, 5 rows of realistic support data)
- 1 skill (`triage` — classifies severity, reassigns urgent tickets)
- a 3-prompt demo simulator

## Layout

```
quickstart/
├── pyproject.toml                  # pip-installable; pins streamlit + agent-framework
├── threadlight_quickstart/
│   ├── __init__.py
│   ├── __main__.py                 # python -m threadlight_quickstart
│   ├── cli.py                      # argparse + dispatch
│   ├── discover.py                 # auto-find specs/sample-data/, src/agent/skills/
│   ├── agent_wiring.py             # Agent + SkillsProvider + tool registration
│   ├── stub_tools.py               # in-memory store + CRUD tool factory
│   ├── simulator.py                # demo-prompt cursor
│   └── ui_streamlit.py             # Streamlit chat page
├── .env.local.example              # env-var template
├── Makefile.demo                   # make demo / make demo-check / make demo-pump
├── fixture-poc/                    # 1-skill, 1-entity toy PoC
└── tests/                          # pytest against fixture-poc
```

## When NOT to use Pattern 0

- **You need the real workspace UI render** — use Pattern 1 + run the
  PoC's own `npm run dev:workspace` separately. Pattern 0 ships a
  Streamlit one-pager only.
- **You need real Cosmos / Search semantics** — Pattern 0 is in-memory
  only; ranking, partition keys, RU consumption are not exercised. Use
  Pattern 3 (Cosmos emulator, Linux/Windows x86 only) or `azd up` to a
  dev sub.
- **You're debugging the live MCP server** — use Pattern 1 (MCP-direct
  via Copilot CLI). Pattern 0 explicitly bypasses the MCP layer.
