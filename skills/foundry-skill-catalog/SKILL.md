---
name: foundry-skill-catalog
description: >
  Centrally store and distribute SKILL.md instructions through the Foundry
  Skills preview API and consume them with the compatible FoundrySkillsSource
  adapter. Use native immutable versions, default_version promotion and rollback,
  pinned downloads, build-time bundles, or same-project Toolbox skill references.
  Covers allow_preview=True, the Skills=V1Preview header, package validation,
  and explicit legacy has_blob / JSON compatibility.
  USE FOR: foundry skills, central skill store, client.beta.skills, has_blob,
  create_from_package migration, Foundry-Features Skills V1Preview,
  FoundrySkillsSource, SkillsProvider with Foundry, skills:import migration,
  skills:download migration, native skill versions, skill rollback,
  Toolbox skill attachment.
  DO NOT USE FOR: awesome-gbb skill authoring, general Foundry tools
  (use foundry-toolbox), file-system SkillsProvider wiring (use
  foundry-hosted-agents), generic hosted-agent runtime.
metadata:
  version: "2.1.0"
---

# Foundry Skills Catalog — Reference Guide

Store reusable instructions once in a Foundry project, then distribute them
without duplicating instruction bodies across agent implementations. The
current Skills API has a **parent skill plus immutable versions**. The parent
tracks `default_version` and `latest_version`; they need not be equal.

**Preview boundary:** Skills, including Toolbox skill discovery, remain preview.
Do not infer a production SLA from Toolbox's GA status. The current
[Skills documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)
now supports **private networking**. This does not make every tool or external
endpoint used by a skill private. Verify catalog access and any downstream
calls separately; keep public access disabled when validating a private path.
Do not change networking to bypass a failure without resource-owner approval.

This skill retains both existing consumption patterns:

1. **Pattern A:** download selected packages at build time, including assets.
2. **Pattern B:** `FoundrySkillsSource(project_endpoint, credential)` returns
   MAF `InlineSkill` instructions. Optional `skill_versions` selects and pins.
3. **Toolbox alternative:** publish same-project skill references; compatible
   clients discover them through MCP Resources.

## ⚠️ Foundry Skills ≠ awesome-gbb skill catalog

| | Foundry Skills | awesome-gbb |
|---|---|---|
| Storage | Versioned product API under `{project}/skills` | This repository's `skills/` directory |
| Consumer | Hosted/local agent code or an MCP Resources client | Coding-tool skill loader |
| Artifact | Domain `SKILL.md`, optionally with resources/scripts | Instructions that teach coding agents workflows |

Sharing a filename and Agent Skills format does not make the two loaders
interchangeable. Upload only skills intended for the target agent.

## Consumption boundary

Direct injection requires code that downloads and loads the skill, typically
a hosted or local agent. There is no justification for a blanket
"hosted agents only" restriction: **Toolbox exposes skills to compatible MCP
Resources clients** via `resources/list` and `resources/read`.

This does **not** establish automatic Prompt-agent support. A client that only
uses MCP `tools/list` does not thereby load MCP Resources. SDK 2.7 adds optional
`PromptAgentDefinition.harness` and `skills` fields, but schema availability
alone does not prove the deployed service, selected harness or pinned runtime
can use them. This skill retains SDK 2.6 and the existing MAF pin; it does not
enable a native Prompt skills route or upgrade a runtime to use those fields.
Verify the actual consumer's resource-discovery behavior.

### Progressive loading is a separate capability

Distinguish three different pieces of evidence:

| Path | What happens | What it does not prove |
|---|---|---|
| Direct download/injection sample | Downloads SKILL.md and supplies instructions to the agent | Native resource discovery or on-demand loading |
| Existing Pattern B adapter | Downloads selected instruction bodies at `get_skills()` time; provider caching applies | Lazy remote asset reads or per-turn refresh |
| Resource-aware Toolbox provider | Advertises names/descriptions, loads selected bodies, then reads assets on demand | Compatibility with every MCP client or Python runtime |

The existing Python **MAF core 1.17** line includes experimental
`MCPSkillsSource`. It reads `skill://index.json` for metadata, then fetches a
selected skill's body through `resources/read` when `load_skill` is invoked.
This is separate from Pattern B, which downloads bodies before constructing
inline skills. **MUST:** use
[`references/mcp_skills_provider.py`](references/mcp_skills_provider.py) for the
native composition with an already authenticated, caller-owned MCP session.
Keep that session open throughout agent execution; close it at the caller's
lifecycle boundary. Install the bounded `mcp~=1.29.0` transport alongside the
existing core pin, not a general framework upgrade.

Loading requires approval by default. `trusted_skill_loading=True` opts out
only for reviewed, trusted skill bodies; it does not disable resource/script
approval or authorize arbitrary skill instructions. The live synthetic test
used this explicit opt-in. No customer content or scripts were executed.

Current Learn also links a C# `AgentSkillsProviderBuilder.UseMcpSkills` sample.
That sample does not certify every Python provider version. Capture actual
metadata/body reads and show that unrelated bodies were not fetched; separately
test model application. Archive-backed skills and supplementary assets need
their own checks: do not infer lazy archive downloads or asset reads from the
inline-body case.

## When to use this vs alternatives

| Situation | Use |
|---|---|
| Centrally shared instructions with controlled promotion | Native Skills versions plus explicit pins |
| Reproducible deployment without runtime catalog dependency | Pattern A |
| MAF instruction-only consumption from a shared catalog | Pattern B |
| Skills and tools through one endpoint | Toolbox skill references plus MCP Resources |
| Local-only instructions | `SkillsProvider.from_paths(...)` |
| Full skill assets/scripts at runtime | Pattern A or an asset-aware Toolbox provider; Pattern B returns instructions only |

## The mandatory `Foundry-Features: Skills=V1Preview` header

Every Skills REST request requires `Foundry-Features: Skills=V1Preview`.
Construct `AIProjectClient(..., allow_preview=True)` so the Python SDK adds
the header. Missing opt-in is an error, not a reason to retry a different API.
Toolbox resource management and Skills discovery have separate support boundaries;
do not reintroduce the retired `Toolboxes=V1Preview` header.

## Auth & RBAC

| Item | Contract |
|---|---|
| Endpoint | `{FOUNDRY_PROJECT_ENDPOINT}/skills` |
| API version | `v1` |
| Token scope | `https://ai.azure.com/.default` |
| Developer and runtime access | **Foundry User** on the project |
| Local auth | `AzureCliCredential` against an explicitly isolated CLI context |
| Hosted auth | Managed identity with the required project access |

Load `azure-tenant-isolation` before Azure commands. Export both
`AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR`, and verify the intended tenant and
subscription immediately before mutations. Do not log tokens, use global-cache
fallbacks, switch subscription, or grant roles silently.

**Build-only stack:** `azure-ai-projects~=2.6.0`,
`azure-identity~=1.25.3`, `httpx~=0.28.1`. Pattern A does **not** require MAF.
**Pattern B additionally needs** `agent-framework-core~=1.17.0`.
See the pin file for executable import validation of the complete adapter stack.
The SDK **2.6.0** methods are `download` and `download_version`; some Learn
examples still spell the default download `download_content`. Do not copy
that spelling into the pinned Python implementation.

## Two creation modes

Both modes create an immutable version beneath the same stable skill name.
Neither uses the legacy top-level `/skills:import` endpoint.

### Mode 1 — Create from JSON

Structural excerpt, assuming an authenticated preview-enabled `project`:

```python
from azure.ai.projects.models import SkillInlineContent

version = project.beta.skills.create(
    name="greeting",
    inline_content=SkillInlineContent(
        description="Use for concise greetings",
        instructions="Greet the user briefly.",
    ),
    default=False,
)
```

Use `default=False` to stage an update without changing active consumers.
For initial creation, set `default=True` explicitly when that version should
be active. Read the parent back; never assume the service promoted a version.

### Mode 2 — Create from files

Structural excerpt, assuming `project` and a local `Path` named `skill_zip`:

```python
from azure.ai.projects.models import CreateSkillVersionFromFilesBody

version = project.beta.skills.create_from_files(
    "greeting",
    content=CreateSkillVersionFromFilesBody(
        files=[(skill_zip.name, skill_zip.read_bytes())],
        default=False,
    ),
)
```

Use this same operation to append a ZIP-backed version to an existing skill.
Do **not** delete and recreate a skill to update content.

## Legacy JSON-mode compatibility (the historical write-only trap)

The old SDK 2.1-era API returned `has_blob`. JSON-created objects with
`has_blob=False` could not be downloaded. That historical observation is
**not a limitation of native inline versions**: current inline versions
have downloadable ZIP content.

The adapter retains compatibility only when metadata explicitly has legacy
`has_blob` and no `default_version`:

- `has_blob=True`: call the legacy SDK `download(name)`.
- `has_blob=False`: retain the description placeholder and emit a
  `RuntimeWarning`; the bundler warns and skips it.
- An explicit numeric pin on legacy metadata is rejected.
- 401/403/404/5xx, interrupted downloads, absent native methods, malformed
  metadata, and invalid archives **propagate as failures**, never as legacy
  placeholders. Re-publish through the native API after obtaining the original
  instruction body; do not manufacture content from the description.

## ⚠️ TRAP — Quoted frontmatter → HTTP 500

The service documentation still requires unquoted `name` and `description`.
Historical imports returned HTTP 500 for quoted frontmatter. Do not retry the
same malformed payload indefinitely. Native skill names use lowercase letters,
numbers and hyphens, no leading/trailing or consecutive hyphens, maximum 64
characters; descriptions have a 1,024-character maximum.

This authoring restriction applies to uploaded domain skills, not a license to
normalize this repository's canonical frontmatter or reference data.

## ZIP layout — what's actually accepted (vs documented)

Author a root `SKILL.md` and keep optional `references/`, `assets/`, and
`scripts/` beside it. The consumers also accept one enclosing folder, preserving
legacy packages. They reject missing/ambiguous `SKILL.md`, path traversal,
absolute paths, duplicate paths, symlinks and files outside that skill's root.

Pattern A preserves validated package files. Pattern B strips frontmatter and
returns the instruction body only; it does **not** expose supplementary assets
or execute bundled scripts.

## REST surface — full reference

All paths below are relative to the project endpoint and require `api-version=v1`
and the Skills preview header.

| Operation | REST | Python SDK 2.6.0 |
|---|---|---|
| Create inline version | `POST /skills/{name}/versions` JSON | `create(name, inline_content=..., default=False)` |
| Create file version | `POST /skills/{name}/versions` multipart | `create_from_files(name, content=...)` |
| List parents | `GET /skills` | `list()` |
| Read parent | `GET /skills/{name}` | `get(name)` |
| List/read versions | `GET /skills/{name}/versions[/<version>]` | `list_versions(name)` / `get_version(name, version)` |
| Download default | `GET /skills/{name}/content` | `download(name)` |
| Download immutable version | `GET /skills/{name}/versions/{version}/content` | `download_version(name, version)` |
| Promote / rollback | `POST /skills/{name}` with `default_version` | `update(name, default_version=version)` |
| Delete one version | `DELETE /skills/{name}/versions/{version}` | `delete_version(name, version)` |
| Delete skill and versions | `DELETE /skills/{name}` | `delete(name)` |

SDK pagers iterate all returned pages. Native delete returns a result with
`deleted`; verify it and then confirm the deleted object returns 404.
Moving the default does not delete earlier versions.

## Pattern A — Build-time bundle (the GHCP-SDK approach)

**MUST:** copy both canonical files into the same directory:

| File | Contract |
|---|---|
| [`references/sync_skills.py`](references/sync_skills.py) | Build-time selection, validated package extraction, legacy skip warning |
| [`references/skill_packages.py`](references/skill_packages.py) | Standard-library snapshot download and archive validation; receives an existing project client |

Invoke `sync_skills.py` from the existing azd predeploy hook. The reference
module contains the hook fragment; do not duplicate its implementation.

Set `FOUNDRY_SKILL_VERSIONS` to a JSON object such as
`{"greeting":"1","refund-rules":null}`: numeric strings pin, `null` follows the
current default. Omit the variable to load the whole catalog; `{}` requests an
empty bundle. Set `FOUNDRY_SKILLS_TARGET` to a dedicated generated-skills
directory, otherwise the script uses `src/skills` relative to its parent.

**Explicit selections require a clean target:** if the dedicated output contains
an unselected directory or a root `SKILL.md`, the bundler fails **before any
write or deletion**. This includes `{}` when an earlier bundle is present:
otherwise downstream file discovery would still load excluded skills.
Use a fresh target directory, or review and move stale files yourself; the
bundler never prunes unselected/user files automatically.

Downloads are validated before replacing selected directories, including
obsolete assets. A legacy JSON skip also fails if it would leave an existing
skill directory active. Without an explicit selection, the historical
all-catalog mode preserves unselected directories and is **not a mirror/prune
operation**. Keep authored files outside the generated directory. A write-time
filesystem failure still requires a rerun; this is not an atomic transaction
across directories.

Bundle the resulting tree into the agent image and consume through the existing
file-based provider or GHCP `skill_directories`. Promotion in Foundry cannot
change already-bundled bytes; rebuild/redeploy to update them.

## Pattern B — Runtime fetch via `FoundrySkillsSource` (recommended for shared catalogs)

**MUST:** copy [`references/foundry_skills_source.py`](references/foundry_skills_source.py)
and its lightweight sibling [`references/skill_packages.py`](references/skill_packages.py)
into the same directory, verbatim. They are the source of truth, not inline
duplicates. The adapter re-exports the shared download/validation helpers.

The public constructor and no-argument `async get_skills()` remain compatible.
The source also accepts the optional context argument passed by the pinned
MAF 1.17 `SkillsProvider`; it does not interpret that context as a different
catalog selection or permission grant.
Structural wiring excerpt, assuming an existing synchronous token credential:

```python
from agent_framework import SkillsProvider
from foundry_skills_source import FoundrySkillsSource

source = FoundrySkillsSource(
    project_endpoint, credential,
    skill_versions={"greeting": "1", "refund-rules": None},
)
provider = SkillsProvider(source)
```

Omit `skill_versions` for the original all-skills behavior. A mapping limits
reads to those names; it does not enumerate unrelated skills. The adapter
resolves `default_version` once per load, fetches that version's metadata, then
downloads **that exact version**, not `latest_version` or a racing default URL.
It verifies returned name/version metadata and never silently drops a pin.

Current MAF `InlineSkill(frontmatter=SkillFrontmatter(...), instructions=...)`
and legacy `InlineSkill(name=..., description=..., instructions=...)` are
supported through constructor-signature detection. This is local object-shape
compatibility, not a fallback on Azure errors.

### Caching

The source does not cache: each explicit `get_skills()` reads current defaults.
MAF 1.17 passes a caller-supplied `SkillsSource` through without automatically
caching it. Its `disable_caching` and `cache_refresh_interval` constructor
options apply to provider-built file/in-memory sources, not this source.
If the application wraps this source in `CachingSkillsSource`, control that
wrapper's refresh and isolation policy explicitly. Production callers should
pin versions or intentionally control reloads. Network failures fail loading
instead of silently substituting stale instruction bodies.

## Governing skill versions in production

Use a stable service name such as `report-writer` and a separate native version
string such as `"1"`. Historical names containing `@1.4.0` are not the native
version model and violate today's name rules for new uploads.

1. Create a **new version**, explicitly unpromoted.
2. Read its metadata and download the exact version; run the consuming agent's
   behavioral tests. Successful CRUD does not prove instruction quality.
3. Pin the candidate version in canary consumers. Native Skills do not supply
   weighted agent traffic routing; that is a separate hosted-agent concern.
4. Promote with `update(name, default_version=candidate_version)`, then verify
   `get(name).default_version` and content through the intended consumer.
5. Roll back with the same operation targeting the previous version. Pinned
   consumers stay pinned; floating consumers change when they reload.
6. Retain versions still referenced by any deployment or Toolbox. Move the
   default and remove references before deleting a version. Deleting the parent
   deletes all versions and is not an update strategy.

## Toolbox attachment and CLI boundaries

Attach a same-project `ToolboxSkillReference(name="greeting", version="1")` for
a pin; omit `version` to follow the skill default. A Toolbox version contains
these references in its `skills` collection, separate from `tools`.
Publish/promote the Toolbox version after changing its references.

The consumer must actually call `resources/list` and `resources/read`.
Verify skill content, not only `tools/list`; attach success alone is not proof
that an agent uses the skill. For full Toolbox composition/auth use
[`foundry-toolbox`](../foundry-toolbox/SKILL.md).

Use `allow_preview=True` for management that attaches skill references, keeping
the Skills opt-in separate from GA Toolbox management. Test a version-specific
Toolbox endpoint before promotion. A pinned Toolbox version containing a
floating skill reference still follows that skill's default when reloaded:
pin **both** the Toolbox and skill versions for reproducible content.

The official azd workflow includes create/show/list/download, native default
promotion and Toolbox skill add/list/remove. **CLI file-input support differs
by extension build:** the official skill snapshot and Learn disagree on folder
and ZIP update support. Inspect the installed command's help and use the pinned
SDK `create_from_files` for non-destructive version append. Never use
`azd ai skill create --force` as an update: documented builds delete the parent
and all versions before recreating it.

## Verified end-to-end

**2026-09-13 native API/adapter validation:** on a standing public-access project,
`azure-ai-projects 2.6.0`, `agent-framework-core 1.17.0` and
`azure-identity 1.25.3` created two inline versions, listed versions, promoted
and rolled back the default, loaded real content through the canonical
`FoundrySkillsSource`, kept a version-1 pin stable, constructed `SkillsProvider`,
and deleted the disposable skill with 404 readback. A second disposable skill
appended a ZIP-backed version without promotion; the canonical adapter and
bundler read it, preserved an asset, then bundled the inline version and removed
the obsolete asset. Individual-version and parent deletion both passed 404
readback. All generated test files were removed.

After extracting the standard-library package reader, the canonical
`sync_skills.py` CLI was rerun live with `agent_framework` deliberately
unavailable. Inline and ZIP bundles passed. Both nonempty explicit selection
and `{}` rejected stale output without modifying its files. The canonical MAF
adapter again passed promotion/rollback with its pin stable. The additional
disposable parent was deleted with 404 readback and local output removed.

This proves the API and adapter read path, **not** model behavior, private
network access, or Toolbox MCP discovery. The historical SDK 2.1/MAF 1.3
verification exercised `has_blob` ZIP/JSON behavior and preview-header errors.
Those legacy observations are retained as compatibility history, not current
native limitations. See the pin audit trail for validation scope.

**2026-09-25 scoped live acceptance:** SDK 2.6.1 executed the unchanged
synchronous `download_catalog` / `skill_archive` reader against two inline
versions and a ZIP version. Exact/default selection, promotion, rollback,
pinned content, supplementary asset bytes and individual-version deletion
passed. A separate skill/Toolbox test called actual MCP `resources/list` and
`resources/read` through version-specific endpoints: after skill promotion,
the pinned reference retained the original body while the floating reference
served the new body on reconnect. All Skills and the Toolbox created for these
cases were deleted with authenticated 404 readback.

These package/resource tests made no model calls. A subsequent isolated
MAF core 1.17.0 / Foundry client 1.13.0 / OpenAI adapter 1.14.2 test exercised
the native MCP provider: metadata advertised two skills, the model invoked
`load_skill` for the relevant one, only that skill's body was fetched, and the
model returned the sentinel present only in those instructions. The unrelated
body was not fetched. The canonical Pattern B adapter also loaded a pinned
version with the actual provider context argument. The temporary Skills and
Toolbox were deleted; the direct model call used `store=False` and its returned
response was not retrievable.

This proves the tested progressive inline-body/model path, not on-demand
supplementary assets, private networking or an upgraded framework. The CI
consumer fixture itself has not run in CI.

## Troubleshooting

| Symptom | Action |
|---|---|
| Native methods missing | Use the pinned native SDK; do not retry legacy endpoints |
| `download_content` AttributeError | SDK 2.6.0 spells it `download`; use `download_version` for a pin |
| Preview-feature 403 | Set `allow_preview=True` or the Skills header |
| Missing/empty `default_version` | Select a known version explicitly or promote it; never assume latest |
| Provider metadata/content mismatch, 404 or 5xx | Stop and report the failing operation; do not convert to a placeholder |
| Legacy JSON warning | Recover original instructions and republish; the placeholder is not the skill body |
| Skill loads old content after promotion | Check explicit pins and provider cache, then reload intentionally |
| Toolbox tools work but skills do not appear | Check same-project references, Toolbox promotion and MCP Resources support |
| Private endpoint cannot access Skills | Private networking is supported; inspect project/data private endpoints, DNS, routing and the actual caller. Do not enable public access as a fallback |
| ZIP validation fails | Supply one root SKILL.md with safe relative assets; no archive traversal or symlinks |
| Explicit bundle selection rejects stale output | Use a clean target directory; review/move old files manually, never silently retain excluded skills |
| Build-only import tries to load MAF | Copy `sync_skills.py` plus `skill_packages.py`, not the MAF adapter |
| Runtime 403, local succeeds | Verify runtime identity has Foundry User on the intended project |

## Cross-skill references

- **`foundry-hosted-agents`** — MAF runtime and local SkillsProvider loading.
- **`foundry-toolbox`** — Toolbox lifecycle, MCP/auth and skill references.
- **`azure-tenant-isolation`** — mandatory auth-cache and subscription guards.
- **`ghcp-hosted-agents`** — build-time bundles via `skill_directories`.
- [Microsoft Learn: Skills](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)
- [MAF Agent Skills](https://learn.microsoft.com/agent-framework/agents/skills?pivots=programming-language-python)
- [Agent Skills specification](https://agentskills.io/)

## Candidate acceptance and private networking

The [consumer fixture](test-fixture/consumer_prompt.md) exercises the native
version and canonical package-reader path without MAF, using the existing SDK
2.6 cap. It is registered in the central dependency map; registration is not
a passing CI run. Its marker is not evidence of model behavior or dynamic
Toolbox loading.

The [additional acceptance cases](test-fixture/service_acceptance.md) require
separate authorized runs for MCP resource discovery, true progressive loading
and private networking. The September 13 public-project observations above
must not be relabeled as private-endpoint or dynamic-loading evidence. For a
private run, establish approved runner placement and DNS/routing first, keep
public network access disabled, and exercise the exact pinned package download
and Toolbox resource reads. A skill can still call a public downstream service;
audit those calls separately.

Source alignment on September 24 adds guidance and a fixture candidate.
September 25 manual evidence is scoped above; it does not certify the untested
variants or change the upstream pin's validation date. Resource scope, cost,
credentials, consent and verified cleanup remain explicit owner gates before
further execution or publication.

A subsequent private-ingress test used an isolated Basic account/project with
public access disabled. The managed-identity runner resolved the project host
to its private endpoint, loaded a pinned package through the unchanged canonical
reader and verified actual Toolbox MCP resource content. An authenticated
external request was rejected for disabled public access. These results prove
the tested private-ingress path, not all downstream networking used by skills.
See the [scoped validation record](../../docs/maintenance/foundry-service-pr1-validation.md).

## Catalog history

- **2.1.0** — Current private-network support, progressive-loading evidence
  boundaries, two-level version pinning and a native package fixture candidate.
  Existing API/adapter and MAF dependency pins are unchanged.
- **2.0.0** — Native API/dependency baseline and documented section migration;
  the skill name and adapter's two-argument async interface remain unchanged.
  Native immutable versions, default promotion/rollback, selected
  pinned consumption and bundles, current MAF compatibility, Toolbox delivery
  boundary, explicitly gated legacy support, MAF-free bundling and fail-closed
  selection against stale output.
- **1.2.0** — Historical name-addressed governance; superseded by native
  version fields for current uploads.
- **1.0.0** — Original REST wrapper, legacy JSON/ZIP findings, MAF adapter and
  build-time bundles.
