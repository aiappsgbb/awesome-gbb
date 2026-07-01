---
name: foundry-skill-catalog
description: >
  Centrally store and distribute instruction-only `SKILL.md` files via the
  Foundry **Skills** REST API (`{project}/skills`) — and consume them at
  runtime from MAF agents through a custom `SkillsSource` adapter. Hosted
  agents only (no Prompt agents). Covers the JSON vs ZIP modes (JSON mode
  is **write-only** — body never returned), the mandatory
  `Foundry-Features: Skills=V1Preview` header, the unquoted-frontmatter
  HTTP 500 trap, `allow_preview=True`, and the verified-working
  `FoundrySkillsSource(SkillsSource)` for `agent_framework.SkillsProvider`.
  USE FOR: foundry skills, central skill store, client.beta.skills,
  has_blob, create_from_package, Foundry-Features Skills V1Preview,
  FoundrySkillsSource, SkillsProvider with Foundry, skills:import,
  skills:download.
  DO NOT USE FOR: awesome-gbb skill authoring (this very repo), Foundry
  tools (use foundry-toolbox), file-system SkillsProvider wiring (use
  foundry-hosted-agents § Skill Loading), generic hosted-agent runtime.
metadata:
  version: "1.2.0"
---

# Foundry Skills Catalog — Reference Guide

The **Foundry Skills** API is a project-level store for instruction-only
`SKILL.md` files. You publish skills once, the API holds them centrally, and
any Hosted agent in the project can either bundle them at build time or
pull them at runtime — without editing the agent's hard-coded instructions.

This skill covers:

1. The full REST surface (`{project}/skills` — create, import, list, get,
   download, delete) with verified gotchas
2. A working **`FoundrySkillsSource(SkillsSource)`** that lets MAF's
   `SkillsProvider` consume Foundry skills at runtime — the missing piece
   the MS Learn doc never connects
3. The build-time bundling alternative (the GHCP/file-copy approach), with
   trade-offs

```
┌────────────────────────────────────────────────────────────────────────┐
│                Foundry Project (managed catalog)                        │
│                                                                          │
│   ┌──────────────────────────────────────────────────────────┐         │
│   │  Skills store: {project}/skills                           │         │
│   │   ├─ greeting     (has_blob: true   — from ZIP)           │         │
│   │   ├─ refund-rules (has_blob: true   — from ZIP)           │         │
│   │   └─ nudge        (has_blob: false  — from JSON)  ⚠ write-only       │
│   └──────────┬──────────────────────────────────────┬────────┘         │
│              │                                      │                    │
│  POST/GET ↓ Foundry-Features: Skills=V1Preview      │ GET :download      │
│           required on EVERY request                  ↓                    │
└──────────────┼──────────────────────────────────────┼────────────────────┘
               │                                      │
       ┌───────┴────────┐                    ┌────────┴──────────┐
       │ Pattern A      │                    │ Pattern B         │
       │ build-time     │                    │ runtime fetch     │
       │ bundle into    │                    │ via custom        │
       │ agent image    │                    │ FoundrySkillsSource│
       └───────┬────────┘                    └────────┬──────────┘
               │                                      │
               ↓                                      ↓
   azd deploy → /app/skills/* → SkillsProvider.from_paths(…)
                                  agent_framework.SkillsProvider(source=FoundrySkillsSource(…))
```

---

## ⚠️ Foundry Skills ≠ awesome-gbb skill catalog

**Two different things, same `SKILL.md` filename:**

| | **Foundry Skills (this skill documents this)** | **awesome-gbb skill catalog (this very repo)** |
|---|---|---|
| What it is | Microsoft Foundry **product feature** — REST API + storage in your Foundry project | Repository of `SKILL.md` files for the GitHub Copilot CLI / Cursor / Cowork |
| Storage | Foundry project (`{project}/skills`) | This Git repo + per-user `~/.copilot/skills/` mirror |
| Consumed by | **Foundry Hosted agents** (your runtime code reads them and injects as session instructions) | **Coding-tool agents** (load skills as additional system context for coding sessions) |
| File format | Same Agent Skills `SKILL.md` spec from [agentskills.io](https://agentskills.io/) | Same Agent Skills `SKILL.md` spec |
| Example skill | `greeting`, `refund-rules`, `compliance-checklist` — domain knowledge for end-user agents | `azd-patterns`, `threadlight-design`, `foundry-toolbox` — knowledge for coding-tool sessions |

The on-disk shape is identical (frontmatter + body), but the **runtime
loader** is completely different. This skill is exclusively about the
Microsoft Foundry product feature.

---

## ⚠️ Hosted agents only (Prompt agents not supported)

Same constraint as `foundry-toolbox`: skills are consumed by **agent code**
that pulls them at session create / build time. Prompt agents are stateless
server-side LLM calls with no mechanism to load skill bodies into a session
prompt — there is no `skills` field on the prompt-agent definition shape,
and the platform doesn't auto-inject Foundry skills into prompt-agent runs.

If you need centrally-managed instructions for a Prompt agent, the
workarounds are:
- Bake the instructions into the prompt-agent definition's `instructions`
  field directly (loses the central-update benefit)
- Front the prompt agent with a thin Hosted agent that pulls the skills and
  forwards the augmented system prompt

---

## When to use this vs alternatives

| Situation | Use |
|---|---|
| You want one team to own canonical "how to handle X" instructions and many Hosted agents to inherit them | **This skill** (Foundry Skills + `FoundrySkillsSource`) |
| Every agent has its own instructions and they never need to be shared | Just put `SKILL.md` files in the agent's `skills/` dir → standard `SkillsProvider.from_paths(…)` (see `foundry-hosted-agents` § Skill Loading) |
| You need progressive-disclosure tools, but the **bodies** live elsewhere (DB, env, code) | `agent_framework.InlineSkill` directly + `InMemorySkillsSource` (see MAF docs) |
| You need to share executable scripts / multi-file resources, not just an instruction body | Foundry Skills ZIP-mode (this skill) — the ZIP can contain `scripts/`, `references/`, `assets/` |

---

## The mandatory `Foundry-Features: Skills=V1Preview` header

Every REST call to `{project}/skills*` must carry:

```
Foundry-Features: Skills=V1Preview
```

Verified behavior (raw HTTP, live Foundry project):

```
GET {project}/skills?api-version=v1
  WITHOUT header:  HTTP 403  preview_feature_required
                   "This operation requires the following opt-in preview
                    feature(s): Skills=V1Preview. Include the
                    'Foundry-Features: Skills=V1Preview' header."
  WITH header:     HTTP 200  list returned
```

**SDK behavior (Python `azure-ai-projects 2.1.0`)**: when you construct
`AIProjectClient(endpoint, credential, allow_preview=True)`, the SDK
**auto-injects** the header on every `client.beta.skills.*` call — no
per-request policy needed. Without `allow_preview=True`, the `beta.skills`
attribute may be present but the header won't be injected and calls
will fail with the 403 above.

The .NET SDK requires a manual `FeaturePolicy` injecting the header
per-request; see the [Foundry Skills doc](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills?pivots=python).

---

## Auth & RBAC

| Item | Value |
|---|---|
| Endpoint base | `{FOUNDRY_PROJECT_ENDPOINT}/skills` |
| API version | `v1` |
| Token scope | `https://ai.azure.com/.default` |
| Required RBAC role | **Azure AI User** on the Foundry project |
| Recommended credential | `DefaultAzureCredential` (local dev) → Managed Identity (production) |

Per `azure-tenant-isolation`, set `AZURE_CONFIG_DIR` per-tenant before any
`az login` / SDK call to keep the token cache isolated.

---

## Two creation modes (the `has_blob` distinction matters a lot)

### Mode 1 — Create from JSON

Submit `name`, `description`, and `instructions` as a JSON body. The skill
is registered as `has_blob: false`.

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

ENDPOINT = "https://<foundry-account>.services.ai.azure.com/api/projects/<project>"

with (
    DefaultAzureCredential() as cred,
    AIProjectClient(endpoint=ENDPOINT, credential=cred, allow_preview=True) as project,
):
    created = project.beta.skills.create(
        name="greeting",
        description="Generate a personalized greeting.",
        instructions="You are a friendly assistant. Keep greetings to 1-2 sentences.",
    )
    print(created.has_blob)   # → False
```

### Mode 2 — Create from ZIP (`:import`)

Build a ZIP containing `SKILL.md` (frontmatter + body) and POST it to the
`:import` endpoint. The skill is registered as `has_blob: true`.

```python
from pathlib import Path

with (
    DefaultAzureCredential() as cred,
    AIProjectClient(endpoint=ENDPOINT, credential=cred, allow_preview=True) as project,
):
    imported = project.beta.skills.create_from_package(
        Path("greeting.zip").read_bytes()
    )
    print(imported.has_blob)  # → True
```

---

## ⚠️ TRAP — JSON-mode skills are write-only

**This is the biggest silent gotcha in the Skills API**, and the MS Learn
doc does not call it out:

| Operation | JSON-mode (`has_blob: false`) | ZIP-mode (`has_blob: true`) |
|---|---|---|
| Create | ✅ accepts `instructions` | ✅ accepts ZIP body |
| `GET /skills/{name}` | ✅ but **does NOT return `instructions`** | ✅ does not return body either |
| `GET /skills/{name}:download` | ❌ HTTP 404 — *"Skill does not have an associated package"* | ✅ returns the original ZIP bytes |
| `?include=instructions` / `?expand=…` / `:body` / `:content` / `:text` | ❌ none of these expose the body | n/a |

**Verified by raw HTTP probing on `azure-ai-projects 2.1.0`** (May 2026):
the `instructions` you POST in JSON mode are **never retrievable** through
any documented or undocumented API path. The list/get response gives you
back only `name`, `description`, `has_blob`, `metadata`, `skill_id`,
`object`.

### Practical consequence

| Use case | Use JSON mode? |
|---|---|
| You want the agent code to download the skill body at runtime via the API | ❌ No — JSON mode is unusable for this. **Use ZIP mode.** |
| You're shipping a `FoundrySkillsSource` adapter (Pattern B below) | ❌ No — only ZIP-mode bodies come back. JSON entries appear in `list()` but `_from_json` can only return their `description`. |
| You bundle the skill body into the agent image at build time and use the Foundry record purely as a registration / version marker | ✅ OK — but you might as well use ZIP mode anyway, for parity. |

### Recommendation

**Always create via ZIP** unless you have a very specific reason to use
JSON mode (e.g., you only need the registry entry for cataloging, never
the body).

---

## ⚠️ TRAP — Quoted frontmatter → HTTP 500

Verified against the live API (request id captured in the error response):

```yaml
# ❌ FAILS with HTTP 500 server_error on :import
---
name: 'greeting'
description: 'Generate a personalized greeting.'
---
```

```yaml
# ✅ Accepted
---
name: greeting
description: Generate a personalized greeting.
---
```

The `name` and `description` values **must be unquoted** in the YAML
frontmatter. Quoted values produce a generic 500 ("An error occurred while
processing your request") with no hint about the cause — easy to lose
hours debugging.

If you author skills from a system that quotes string values by default
(some YAML serializers do), strip the quotes before writing the file or
use a serializer with `default_style=None`.

---

## ZIP layout — what's actually accepted (vs documented)

The MS Learn doc says:

> The ZIP must contain `SKILL.md` at the root, not in a subdirectory.

**Verified behavior is more permissive** (May 2026, live Foundry project):

| ZIP layout | Outcome |
|---|---|
| `SKILL.md` at root | ✅ Accepted, `has_blob: true`, downloads round-trip cleanly |
| `SKILL.md` at root + `references/extra.md` + `scripts/helper.py` | ✅ All entries preserved through download |
| `subdir/SKILL.md` only (nested) | ✅ **Accepted** despite the doc — but downloads keep the subdir prefix, which most consumers won't expect |
| ZIP with no `SKILL.md` anywhere | ❌ HTTP 500 server_error |

**Practical rule** (matches the doc): always place `SKILL.md` at the ZIP
root. The fact that nested layouts are accepted today is not a guarantee
they will be tomorrow, and any consumer that runs `zipfile.read("SKILL.md")`
will silently fail to find a nested copy.

```python
# The right way
import io, zipfile
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("SKILL.md", skill_md_text)             # ← at root
    z.writestr("references/policy.md", policy_text)   # ← supporting files OK
    z.writestr("scripts/lookup.py", script_text)      # ← scripts OK
project.beta.skills.create_from_package(buf.getvalue())
```

---

## REST surface — full reference

All operations are against `{FOUNDRY_PROJECT_ENDPOINT}/skills` with header
`Foundry-Features: Skills=V1Preview` and bearer token from
`https://ai.azure.com/.default`.

| Op | REST | SDK (`client.beta.skills`) | Returns |
|---|---|---|---|
| Create from JSON | `POST /skills?api-version=v1` | `.create(name, description, instructions)` | `has_blob: false` skill |
| Create from ZIP | `POST /skills:import?api-version=v1` (body: ZIP) | `.create_from_package(zip_bytes)` | `has_blob: true` skill |
| List | `GET /skills?api-version=v1&limit=20&order=desc&after=<cursor>` | `.list(limit=…, order=…, after=…)` | Paginated list |
| Get | `GET /skills/{name}?api-version=v1` | `.get(name)` | Metadata (no body); `404` if missing |
| Download | `GET /skills/{name}:download?api-version=v1` | `.download(name)` (iterator of bytes) | ZIP bytes for `has_blob:true`; `404` for `has_blob:false` |
| Update | `PATCH /skills/{name}?api-version=v1` | `.update(name, description=…)` | Updated metadata (description only — body cannot be patched in place; re-import to replace) |
| Delete | `DELETE /skills/{name}?api-version=v1` | `.delete(name)` | `204`; subsequent `get` returns `404` |

### Pagination

`list()` returns `{ data: […], has_more, first_id, last_id }`. Use
`first_id` / `last_id` with `before` / `after` query params for cursor
pagination.

### Errors observed in PoC

| Status | Code | When |
|---|---|---|
| 403 | `preview_feature_required` | `Foundry-Features` header missing |
| 404 | `not_found` | GET / DELETE / DOWNLOAD on a missing skill, or `:download` on a JSON-mode skill |
| 500 | `server_error` | Quoted frontmatter on `:import`, ZIP without `SKILL.md`, generic catch-all |

---

## Pattern A — Build-time bundle (the GHCP-SDK approach)

Match the MS Learn sample: at `azd deploy` time, download every Foundry
skill and bake the resulting `SKILL.md` files into the container image.
Standard `SkillsProvider.from_paths(…)` then loads them at session start.

```python
# scripts/sync_skills.py — run as an azd predeploy hook
import io
import zipfile
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

ENDPOINT = "https://<account>.services.ai.azure.com/api/projects/<project>"
TARGET = Path(__file__).parent.parent / "src" / "skills"
TARGET.mkdir(parents=True, exist_ok=True)

with (
    DefaultAzureCredential() as cred,
    AIProjectClient(endpoint=ENDPOINT, credential=cred, allow_preview=True) as project,
):
    for s in project.beta.skills.list():
        if not s.has_blob:
            print(f"  skipping JSON-mode skill {s.name} (body unretrievable)")
            continue
        zip_bytes = b"".join(project.beta.skills.download(s.name))
        skill_dir = TARGET / s.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extractall(skill_dir)
        print(f"  unpacked {s.name} → {skill_dir}")
```

In the agent code:

```python
from agent_framework import SkillsProvider
provider = SkillsProvider.from_paths(Path(__file__).parent / "skills")
```

| Pros | Cons |
|---|---|
| Sealed image — no runtime network dep on Foundry | Skill changes require a redeploy |
| Same code path as a fully-local agent (good test parity) | Skills are duplicated across every agent deployment |
| Works with any `SkillsProvider`-based runtime today | JSON-mode skills are silently skipped (write-only trap) |

---

## Pattern B — Runtime fetch via `FoundrySkillsSource` (recommended for shared catalogs)

The MAF Python `SkillsProvider` accepts any `SkillsSource` — an ABC with
one method, `async def get_skills() -> list[Skill]`. There's no built-in
Foundry-backed source; the snippet below is a verified-working
implementation.

```python
# foundry_skills_source.py
import asyncio
import io
import zipfile

from agent_framework import InlineSkill, Skill, SkillsSource
from azure.ai.projects import AIProjectClient


class FoundrySkillsSource(SkillsSource):
    """Pull skills from a Foundry project's Skills REST API.

    Materialises ZIP-mode (`has_blob: true`) skills as `InlineSkill`
    instances by parsing the SKILL.md frontmatter and returning the
    body as `instructions`. JSON-mode skills are returned with their
    description as a placeholder — see the JSON-mode write-only trap.
    """

    def __init__(self, project_endpoint: str, credential) -> None:
        self._endpoint = project_endpoint
        self._credential = credential

    async def get_skills(self) -> list[Skill]:
        # The azure-ai-projects SDK is sync; offload to a worker thread.
        return await asyncio.to_thread(self._collect)

    def _collect(self) -> list[Skill]:
        out: list[Skill] = []
        with AIProjectClient(
            endpoint=self._endpoint,
            credential=self._credential,
            allow_preview=True,
        ) as project:
            for summary in project.beta.skills.list():
                if summary.has_blob:
                    out.append(self._from_zip(project, summary))
                else:
                    out.append(self._from_json_placeholder(summary))
        return out

    def _from_zip(self, project, summary) -> InlineSkill:
        zip_bytes = b"".join(project.beta.skills.download(summary.name))
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            md_name = next(
                (n for n in z.namelist() if n.lower().endswith("skill.md")), None
            )
            if md_name is None:
                raise RuntimeError(
                    f"Skill '{summary.name}' downloaded ZIP has no SKILL.md"
                )
            raw = z.read(md_name).decode("utf-8")
        return InlineSkill(
            name=summary.name,
            description=summary.description or "",
            instructions=self._strip_frontmatter(raw),
        )

    def _from_json_placeholder(self, summary) -> InlineSkill:
        # JSON-mode skills are write-only — the body is unretrievable.
        # Return a placeholder so the agent at least sees the skill exists.
        return InlineSkill(
            name=summary.name,
            description=summary.description or "",
            instructions=(
                summary.description
                or f"[Foundry JSON-mode skill '{summary.name}' — body not "
                f"retrievable from the API. Re-import as a ZIP to fix.]"
            ),
        )

    @staticmethod
    def _strip_frontmatter(raw: str) -> str:
        if not raw.startswith("---"):
            return raw
        parts = raw.split("---", 2)
        return parts[2].lstrip("\n") if len(parts) >= 3 else raw
```

Wire it into a hosted agent (`container.py` or equivalent):

```python
from agent_framework import Agent, SkillsProvider
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential

from foundry_skills_source import FoundrySkillsSource

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
credential = DefaultAzureCredential()

source = FoundrySkillsSource(PROJECT_ENDPOINT, credential)
skills_provider = SkillsProvider(source)

agent = Agent(
    chat_client=FoundryChatClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential,
        deployment_name="gpt-4.1-mini",
    ),
    instructions="You are a helpful assistant.",
    context_providers=[skills_provider],
)
```

### Caching

`get_skills()` runs on every fresh `SkillsProvider` instantiation but is
called by the framework once per session create — not per turn. For
multi-instance agents you can layer `DeduplicatingSkillsSource` /
`FilteringSkillsSource` (built into `agent_framework`) around your
source. For a TTL cache, wrap `_collect` with your own decorator.

| Pros | Cons |
|---|---|
| Skill updates take effect on the next session — no redeploy | Network call on every session create (mitigate with caching) |
| Single source of truth across many agents | JSON-mode skills surface only their description (use ZIP mode) |
| Auditable — `list()` shows exactly what's published | Foundry outage = no skills (sealed-image fallback worth considering) |

---

## Governing skill versions in production

Patterns A/B tell you how to *publish* and *consume* skills. This section
tells you how to **not break** the agents already consuming them when you
ship a change.

### Why this needs discipline

Two failure modes, both silent:

- **Floating pointer.** If every agent resolves a skill by a bare, reused
  name, one re-import pushes a capability change to *all* agents at once
  — no canary, no staged rollout.
- **Destructive replace.** `delete` + re-import (or re-import over a live
  name) mutates the bytes running agents depend on. Nothing fails loudly;
  the next agent turn just behaves differently.

### The API is name-addressed, not version-addressed

Every operation in the REST surface keys on `{name}` — there is **no
native `version` field**. `update` patches the **description only** (the
instruction body cannot be patched in place), and `delete` is a hard
`204` that makes the next `get` return `404` (see the *Update* / *Delete*
rows above). So the **name is your version key**: govern versions by
naming discipline, not by an API primitive.

### 1 — Treat each published version as immutable, versioned bytes

Encode the version in the skill name and publish via **ZIP mode**
(JSON-mode skills are write-only — you can never read the body back):

```
report-writer@1.4.0     # not: report-writer  (a floating pointer)
report-writer@1.5.0     # a new version = a new name = new bytes
```

A given versioned name always resolves to the same bytes. You never
`update` the body of `report-writer@1.4.0`; you publish
`report-writer@1.5.0` alongside it.

### 2 — Pin in production

Production agents bind to a **specific versioned name**
(`report-writer@1.4.0`), never a floating alias. Then "which
capabilities ran during the incident at 14:32?" has one auditable answer
— the pinned name is in the deploy manifest, not inferred from whatever
the shared name happened to point at.

### 3 — Promote the default in stages

Keep a **resolvable default pointer** — a deploy-time value (env var or
config the agent's `SkillsSource` / Pattern-A sync reads), **not** a
runtime mutation of the store. Promote it canary-first:

- Point a small subset of agents' pointer at `report-writer@1.5.0`.
- Observe (traces, eval scores) for hours-to-days.
- Roll the pointer forward for the broad fleet.

Because the pointer lives in each agent's deploy config, promotion is a
redeploy of the canary subset — the store itself is never mutated, and
rollback is re-pointing to `@1.4.0`.

### 4 — Never destructively replace a live version

To ship a change, **publish a new versioned name and re-point
consumers.** Do **not** `delete` or re-import over a name that live
agents pin. The *Update* (description-only) / *Delete* (`204` → `404`)
rows above are the mechanical reason: you *cannot* patch bytes in place,
and `delete` is irreversible — a pinned agent that resolves a deleted
name gets a `404` mid-run.

### 5 — Fetch at deploy, not at runtime

Prefer downloading the pinned artifact at **deploy time** (Pattern A
build-time bundle, or Pattern B's cached `FoundrySkillsSource` primed at
startup) over cloning capability source into a running container. The
pinned bytes become part of the immutable deployment, so a store change
can't alter a running agent's behavior between turns. See **§ Caching**
above for the Pattern-B TTL knobs.

---

## Verified end-to-end

This skill was verified against a live Foundry project on **2025-11-19**:

- Foundry account / project: standard `services.ai.azure.com/api/projects/<project>` shape
- Subscription: MCAPS pilot subscription (Sweden Central region)
- SDK versions: `azure-ai-projects 2.1.0`, `agent-framework 1.3.0`,
  `azure-identity 1.26.0b2`

What was exercised:

| Scenario | Result |
|---|---|
| `client.beta.skills` attribute available with `allow_preview=True` | ✅ |
| Create from JSON → `has_blob: false` | ✅ |
| Create from ZIP → `has_blob: true` | ✅ |
| List, get, get-missing-→-404 | ✅ |
| Download ZIP → bytes round-trip cleanly through `zipfile.ZipFile` | ✅ |
| Download JSON-mode skill → 404 | ✅ |
| **TRAP**: any retrieval path for JSON-mode `instructions` | ❌ no path exists — JSON mode is write-only |
| Quoted frontmatter on `:import` → 500 | ✅ confirmed |
| Missing `Foundry-Features` header → 403 `preview_feature_required` | ✅ confirmed |
| `FoundrySkillsSource(SkillsSource)` returns valid `InlineSkill` instances | ✅ |
| `SkillsProvider(source=FoundrySkillsSource(…))` constructs cleanly | ✅ |

All test skills were deleted at end of run (`list()` confirms 0 PoC
artifacts remaining).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `client.beta.skills` raises `AttributeError` | `allow_preview=True` missing on `AIProjectClient` | Pass `allow_preview=True` |
| `HTTP 403 preview_feature_required` from raw HTTP | `Foundry-Features: Skills=V1Preview` header missing | Use the SDK with `allow_preview=True` (auto-injects) or add the header to every request |
| `HTTP 500 server_error` on `:import` and the request id changes each retry | Quoted `name` / `description` in YAML frontmatter | Remove the quotes (`name: greeting`, not `name: 'greeting'`) |
| `HTTP 500 server_error` on `:import` consistently | ZIP has no `SKILL.md` anywhere, or zero-byte upload | Build a real ZIP with `SKILL.md` at the root |
| `download()` returns 404 with *"does not have an associated package"* | The skill is JSON-mode (`has_blob: false`) | Re-create the skill via ZIP-mode `:import` |
| Agent code retrieves a skill but `instructions` is empty / wrong | Read the JSON-mode write-only trap above — the body is gone | Re-publish as ZIP |
| `FoundrySkillsSource` works locally but fails in ACA | Managed identity has no **Azure AI User** role on the project | Grant the role; verify with `az role assignment list --assignee <principalId>` |
| Skill list returns empty in production but populated locally | Wrong tenant / wrong project endpoint | Check `AZURE_CONFIG_DIR` (see `azure-tenant-isolation`) and `FOUNDRY_PROJECT_ENDPOINT` env var |
| `Foundry-Features` header request id 5xx-cluster | Foundry preview-feature regression | Open a Foundry support case with the `additionalInfo.request_id` from the error body |
| Agent never calls `load_skill` | Skills are advertised but the model isn't picking them up | Check the skill `description` includes a clear "use when …" trigger, and that the body is concise (≤500 lines per Agent Skills spec) |

---

## Cross-skill references

- **`foundry-hosted-agents`** — the hosted-agent runtime that consumes
  this skill's `FoundrySkillsSource`. The skill's § *Skill Loading* section
  documents the file-based `SkillsProvider` wiring that Pattern A relies on.
- **`foundry-toolbox`** — sibling Foundry preview feature for tool catalogs,
  same hosted-agent-only constraint, same `Foundry-Features` header pattern.
- **`azure-tenant-isolation`** — required for any multi-tenant work
  against the Foundry REST API; isolates the AAD token cache per tenant.
- **`ghcp-hosted-agents`** — alternative runtime; the build-time bundle
  (Pattern A) works identically there via `skill_directories=[…]`.
- **MS Learn — Skills (REST API)**:
  <https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills>
- **MS Learn — Agent Skills (MAF Python)**:
  <https://learn.microsoft.com/agent-framework/agents/skills?pivots=programming-language-python>
- **Open spec**: <https://agentskills.io/>

---

## Catalog history

- **1.2.0** — Added § *Governing skill versions in production*: naming-
  convention discipline for the name-addressed Skills API (immutable
  versioned names, pin-in-prod, staged default promotion, no destructive
  replace, fetch-at-deploy). Closes #336.
- **1.0.0** (initial) — REST API surface, JSON-mode write-only trap,
  quoted-frontmatter trap, ZIP layout findings, `FoundrySkillsSource`
  adapter for MAF `SkillsProvider`, build-time bundle alternative.
  Verified against `azure-ai-projects 2.1.0` + `agent-framework 1.3.0`
  on a live Foundry project (Sweden Central, May 2026).
