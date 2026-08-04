# Foundry Voice Live Critical Refresh - Design

- **Date:** 2026-08-04
- **Status:** Approved after independent specification review
- **Skill:** `foundry-voice-live`
- **Current skill version:** `1.3.1`
- **Target skill version:** `1.4.0`
- **PR shape:** one skill source plus required catalog metadata and generated docs

---

## 1. Decision

Adopt the current compatible SDK stack while holding Gradio below 6:

| Package | Target |
|---|---|
| `openai` | `~=2.53.0` |
| `azure-identity` | `~=1.25.3` |
| `fastrtc` | `~=0.0.34` |
| `gradio` | `~=5.50.0`, held below 6.0 |
| `azure-ai-voicelive[aiohttp]` | `~=1.3.0` |

`fastrtc==0.0.34` requires `gradio>=4,<6`; a literal install with Gradio
6.22 fails resolution. Keep Gradio 5.50 and add an open known issue linked to
`gradio-app/fastrtc#428`.

Voice Live SDK 1.3 changes the default `connect()` API version to
`2026-07-15`. Preserve the skill's currently proven behavior by passing
`api_version="2026-04-10"` explicitly in canonical code and the live
fixture. Adoption of `2026-07-15` is a later migration with separate live
proof.

---

## 2. Goals and non-goals

### Goals

- Refresh OpenAI and Voice Live SDK pins and package claims.
- Encode the Gradio 6 compatibility ceiling as a machine-enforced hold.
- Correct all prose that says Voice Live SDK 1.2 is current.
- State that SDK 1.3 defaults to `2026-07-15`, while the skill deliberately
  passes `2026-04-10`.
- Update the live fixture to install SDK 1.3 and pass the API version
  explicitly.
- Keep the current WSS roundtrip as the hard success contract.
- Rebuild generated catalog pages.

### Non-goals

- No Gradio 6 migration.
- No FastRTC replacement.
- No adoption of Voice Live API `2026-07-15`.
- No UI rewrite or new voice architecture rung.
- No edit to another skill body.

The contract migration requires a `[skill-rewrite]` commit tag. The MINOR
bump is intentional because the fixture's implicit API-version behavior is
made an explicit, durable contract while the SDK moves to a new default.

---

## 3. Compatibility hold

Add to the Gradio package:

```yaml
hold_below: "6.0.0"
hold_reason: KI-001
```

Add open `KI-001` linked to:

```text
https://github.com/gradio-app/fastrtc/issues/428
```

The pin must contain the matching `known_issues` entry with `status: open`,
set `known_issues_count: 1`, and add a human-readable KI-001 section. The hold
fails open without that matching issue.

The hold closes only when a released FastRTC version declares Gradio 6
support, the bounded dependency set installs, and the relevant FastRTC/WebRTC
sample passes.

---

## 4. API-version boundary

Canonical Rung 4 code and the fixture use:

```python
async with connect(
    endpoint=voicelive_endpoint,
    credential=credential,
    api_version="2026-04-10",
    model="gpt-realtime",
) as connection:
    ...
```

The pin script separately asserts:

```python
import inspect
from azure.ai.voicelive.aio import connect

assert inspect.signature(connect).parameters["api_version"].default == "2026-07-15"
```

The apparent mismatch is deliberate: the assertion detects upstream default
drift, while the explicit argument preserves the already documented and
live-proven contract.

---

## 5. Validation design

### T0/T1/T2

The pin script installs the exact compatible set and asserts:

1. the five package versions match the target;
2. `connect()` accepts `endpoint`, `credential`, `api_version`, and `model`;
3. SDK 1.3 defaults `api_version` to `2026-07-15`;
4. OpenAI 2.53 retains Azure endpoint, deployment, API version, realtime, and
   websocket parameters;
5. FastRTC 0.0.34 imports with Gradio 5.50;
6. the Gradio hold references open `KI-001`.

### T3

The fixture installs Voice Live 1.3 and Azure Identity 1.25.3, then opens the
live WSS session with explicit `api_version="2026-04-10"`. It sends the
existing text turn and requires at least one accepted server event. A
successful SDK default assertion alone is not sufficient; the explicit
2026-04-10 WSS roundtrip must pass.

---

## 6. Files

| File | Responsibility |
|---|---|
| `skills/foundry-voice-live/SKILL.md` | Current package/API-version contract and `1.4.0` |
| `skills/foundry-voice-live/references/upstream-pin.md` | Pins, Gradio hold, default-version probe, corrected table |
| `skills/foundry-voice-live/test-fixture/consumer_prompt.md` | Explicit 2026-04-10 live WSS proof on SDK 1.3 |
| `README.md` | Replace the stale row with GA `2026-04-10` and the four-rung ladder from `SKILL.md` |
| `plugin.json` | Validator-required minimal PATCH `4.29.4 -> 4.29.5` in the approved serialized wave |
| `.github/plugin/marketplace.json` | Match both marketplace version fields to `4.29.5` |
| `docs/` | Regenerated static catalog |

The numeric target assumes the approved order: Toolbox first moves the plugin
to 4.29.4, while the Hosted and MCP/ACA PATCH PRs do not change it. If the
merge base differs, rebase before implementation rather than coupling the
voice PR to stale metadata.

Update `docs_to_revalidate` from
`azure/ai-foundry/openai/concepts/audio` to
`azure/foundry-classic/openai/concepts/audio`. Keep the existing
2026-04-10 API reference and do not add the unpublished 2026-07-15 URL.

---

## 7. Rollback and future migration

Rollback is one revert. If SDK 1.3 fails the explicit 2026-04-10 live
roundtrip, keep SDK 1.2, retain the new Gradio hold only in a separate PATCH
if independently validated, and attach the WSS evidence to the freshness
issue.

Adopt API `2026-07-15` only in a later PR that verifies event models, session
options, and a live roundtrip against that version. Do not infer compatibility
from the SDK default.
