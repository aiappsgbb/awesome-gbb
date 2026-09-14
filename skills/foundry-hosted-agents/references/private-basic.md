# Private Hosted BASIC: existing project and registry

This opt-in consumer runs one **no-tools** Hosted container and one plain model
request. It is not the public CI fixture, a private prompt-agent threads/runs
test, or governed business execution. Operator approval is required for each
write/invocation, within its original scope and expiry. A setup gate is neither
approval nor a live result. Preserve all existing resources, versions and logs.

## Native contracts and the confirmed defect

- [Official container precheck](https://github.com/microsoft/GitHub-Copilot-for-Azure/blob/91b451609306a490e84854c7c2c1fd79c62398a4/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/deploy/references/container-deploy.md):
  an existing ACR needs a **project ContainerRegistry connection**, independently
  of capability hosts, `AcrPull`, ACR environment variables or BYO-store arrays.
- [Native ACR connection emission](https://github.com/Azure/azure-dev/blob/2850298a3f0d9f296a4f5795b593a69115fe5b05/cli/azd/extensions/azure.ai.agents/internal/synthesis/templates/modules/foundry-project.bicep):
  `ManagedIdentity`, bare registry `loginServer`, `metadata.ResourceId` = registry
  ARM ID. In this native registry-specific contract, **credentials.clientId is
  the project's principalId** (despite the field name), and
  `credentials.resourceId` is the registry ID. Do not substitute an agent MI or
  infer an Entra application client ID from the field name.
- [Native passthrough](https://github.com/Azure/azure-dev/blob/2850298a3f0d9f296a4f5795b593a69115fe5b05/cli/azd/pkg/project/container_helper.go):
  service-level `image`, `docker.imagePassthrough: true`, `remoteBuild: false`
  skip build and ordinary republishing, preserving the expanded digest reference.
  **Do not use `--from-package` with a digest** as a substitute.
- [Official Responses BASIC runtime](https://github.com/azure-ai-foundry/foundry-samples/blob/1abe346cbb2428fce504970498bafecf3803f29c/samples/python/hosted-agents/agent-framework/responses/01-basic/src/agent-framework-agent-basic-responses/main.py):
  `Agent` + `FoundryChatClient` + `ResponsesHostServer`, no tools, `store: False`.
  Its adjacent `azure.yaml` defaults to preview **code** mode. Our stager
  explicitly chooses **container** mode, reuses the catalog dependency cohort
  and never adds a placeholder tool, skill provider or consent bootstrap.

The published setup omission was confirmed in #499. Adding the connection
fixed that prerequisite, **not the entire failed deployment**. An exact copied
BASIC image subsequently activated privately and returned a model response.
Those were different whole artifacts; image contents and propagation/timing were
not isolated. Neither an OCI-only cause nor a Microsoft SDK/backend defect is
proven. No blanket OCI ban is justified. Historical BASIC evidence with an
unused local tool is not fresh evidence for this no-tools consumer.

## 1. Context and credential-free connection inspection

Follow [azure-tenant-isolation](../../azure-tenant-isolation/SKILL.md) before
**every** operator shell: both existing `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR`,
then exact tenant/subscription assertion immediately before any write.
Use the environment owner's already-approved auth and private operator route.
Never log in or switch global defaults automatically.

Retain `azd version` and `azd ext list --output json` privately; do not upgrade
global tooling to make a smoke pass. Source support above is not proof that an
older installed azd honors passthrough. If local/native package output does not
preserve the digest, stop for an explicit tooling decision.

Collect the [setup schema](deployment-preflight.md#setup-evidence-schema-version-1),
using the **oldest** observation timestamp. All GETs must succeed and all list
pages must be consumed. Use the exact approved IDs, not default discovery.
For connections the ordinary ARM API is:

```text
GET https://management.azure.com<project-id>/connections?api-version=2025-04-01-preview
GET https://management.azure.com<project-id>/connections/<connection-name>?api-version=2025-04-01-preview
```

Never call `listsecrets`, `include_credentials`, registry key APIs or an invented
SDK `connections.create`. Keep only ordinary GET properties without credentials
in `project_connections.value`. Compare `id`, category, target, authType and
metadata ResourceId. Preserve unrelated connections. A 403, partial response,
timeout or unsupported API is **unreadable**, never an empty list.

Supply `target.registry_connection_name` and `registry_connection_identity`:
`connection_id`, `principal_id`, `registry_id`, `source: native-provisioning`,
`evidence: <retained-native-input-or-deployment-reference>`. This is a
non-secret projection of **real reviewed native provisioning inputs**, not a
receipt fabricated from a successful GET. Ordinary GET can omit the credential
mapping. If its provenance is unavailable, stop for the owner; do not retrieve
secrets or manufacture a `pass`. Conflicting/duplicate connections or a
different identity block reuse. A correct connection is reused unchanged.

`ContainerRegistry` is **not** a Basic capability-host BYO store: leave
`threadStorageConnections`, `vectorStoreConnections`, `storageConnections` and
`aiServicesConnections` absent/empty in Basic.

### Missing only: native configuration/provisioning

This is a separately authorized prerequisite repair, never an automatic retry:

1. Retain the successful empty/missing inventory. Do **not** delete a correct
   connection to test this branch. Missing-case regression testing is offline.
2. Use [native Bicep ejection](https://github.com/Azure/azure-dev/blob/2850298a3f0d9f296a4f5795b593a69115fe5b05/cli/azd/extensions/azure.ai.agents/docs/infrastructure-eject.md)
   (`azd ai agent init --infra=bicep`) in a separate owner-approved staging
   directory, targeting the existing project. Review the generated graph before
   provisioning. No new account, project, registry, host, model or role is
   authorized by a missing connection.
3. For the pinned native existing-project template, use **`acrMode:
   reuse-connect`**, exact `projectResourceId`, `existingAcrResourceId`,
   `existingAcrEndpoint`, `projectEndpoint`, `deployments: []`, and
   **`acrPullAssigned: true` only after verifying the existing effective
   project-MI pull assignment**. The native existing-project graph then skips
   the registry/RBAC module and emits only the project connection. Its name is
   `<registry-name>-conn`; a different desired name requires an explicit owner
   decision, not silent substitution. Review the ejected parameter file and
   compiled graph; a tool version with another shape must not receive guessed
   parameters.
4. A previously ejected native **generic `modules/connections.bicep`** can
   instead be reused as a connection-only module. Its verified parameter
   contract is `foundryAccountName`, `foundryProjectName`, `connections` (one
   entry with name/category/target/authType/metadata), `connectionCredentials`
   keyed by connection name (`clientId: <project-principal-id>`,
   `resourceId: <registry-id>`). Retain that module's hash and installed
   extension version. Do not provision its unrelated parent graph. No
   credential broker/password is needed; these two mapping fields are IDs.
5. Execute the reviewed connection-only **`azd provision`** once, then repeat
   ordinary connection GETs and the gate. Preserve network settings and all
   existing hosts/registry/auth state. Uncertain provisioning ACK requires
   GET reconciliation, not blind repeated provision.

Native `reuse-connect` without verified `acrPullAssigned` can emit a role
assignment. It is **not** authorized as a convenient fix for absent connection
metadata, and is especially wrong for an ABAC registry expecting repository
roles. Unknown/insufficient pull access is a separate owner decision.

## 2. Stage a minimal container

Use a dedicated local management venv with `azure-ai-projects~=2.3.0`,
`azure-identity~=1.25.3`, `httpx~=0.28.1` and `PyYAML~=6.0`. Never update a global
SDK or mix this environment with the container's canonical dependencies.
In the commands below `$PYTHON` is that venv interpreter and `$REFS` is the
absolute path to this skill's `references` directory. `$WORK` must not exist.
Set a fresh UUID-suffixed `$AGENT` for the approved candidate; do not touch
another agent's endpoint or routing.

Choose exactly one path:

```bash
# Source container build on a network-reachable local builder.
"$PYTHON" "$REFS/python/private_bootstrap.py" prepare "$WORK" --agent "$AGENT" --build local

# OR prebuilt: already validated no-tools image in the selected private ACR.
"$PYTHON" "$REFS/python/private_bootstrap.py" prepare "$WORK" --agent "$AGENT" \
  --build prebuilt --image "$IMAGE"
```

`$IMAGE` must be `registry/repository@sha256:<digest>`, not a tag. Prebuilt does
not require a local Docker daemon. For source builds, use `--build remote` only
when the approved builder can reach the private registry/data endpoints;
never expose the registry to make remote build work.

The stager copies the canonical runtime/dependencies and creates an isolated
`app/` context. **Both `.dockerignore` and `.azdignore` allowlist only** main,
pyproject, lock and Dockerfile. `.env`, `.azure`, credentials, local venvs,
caches, evidence and sibling workspaces are not uploaded. This is a BASIC
build-context rule, not a global security-exclusion policy.

For source builds, resolve once using an already-approved Python 3.12 / uv
toolchain and retain the lock; replay with that exact file:

```bash
(cd "$WORK/app" && uv lock --python 3.12)
"$PYTHON" "$REFS/python/private_bootstrap.py" inventory "$WORK"
```

Set `PYTHON_IMAGE` and `UV_IMAGE` to approved **immutable** Python 3.12-slim and
uv base-image references in the local azd environment. The Dockerfile consumes
both build args and `uv sync --locked`; never silently re-resolve during build.
Export those same two values in the operator shell and run
`"$PYTHON" "$REFS/python/private_bootstrap.py" check-build "$WORK" --agent "$AGENT"`
before native package/publish (or deploy for prebuilt). Keep both environment
sources equal; the output records the chosen path and exact base references.
Retain resolved package versions, base manifests, context inventory, build
output and final image config/layer descriptors. Do not mutate Docker config or
Keychain helpers globally; if auth requires local changes, stop for the owner
or use an approved process-scoped `DOCKER_CONFIG`.

## 3. Build/publish is not platform pull

In `$WORK`, configure the isolated azd environment with exact
`AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_AI_PROJECT_ID`,
`FOUNDRY_PROJECT_ENDPOINT`, `AZURE_CONTAINER_REGISTRY_ENDPOINT`,
`AZURE_CONTAINER_REGISTRY_RESOURCE_ID`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`.
Registry name, endpoint and ARM ID must describe one registry. The shell and
azd values must agree; the live oracle checks each selected value without
dumping the entire environment.

**Source path:** use the installed native `azd package "$AGENT"` /
`azd publish "$AGENT"` container path to build/push **before registration**.
Retain output and independently resolve the published manifest from the selected
registry to an immutable digest. Do not guess its repository/tag. Freeze it into
a second fresh stager directory using `--build prebuilt --image "$IMAGE"`;
retain the original source directory/lock and inventory. Configure its isolated
azd env identically. The final registration path is now the same passthrough
path as prebuilt, without a second build.

**Prebuilt path:** retain source provenance and actual image validation for
this no-tools contract. For an authorized native import, compare the source
and destination **raw manifest digest and all config/layer descriptors**.
An equal tag or four equal source files is not equal image provenance. Do not
import anything as part of the smoke without the owner's approval.

For original raw platform-manifest bytes (not reformatted CLI JSON):

```bash
"$PYTHON" "$REFS/python/private_bootstrap.py" manifest "$MANIFEST" --digest "$DIGEST"
```

Record the manifest's media type; both Docker v2 and OCI manifests are accepted.
Resolve an index to the approved `linux/amd64` manifest explicitly, and validate
its config/platform, startup/imports and local `/home/session/.sessions` behavior.
Do not infer a live native mount write from a local check.

## 4. Register once, activate, invoke, independently read back

Refresh setup evidence for the frozen digest. For this no-tools consumer use
`target.mode: basic-private`, `registry_network: private`, `tool_endpoints: []`,
`tenant_id: <approved-tenant>`, `account.properties.disableLocalAuth: true`,
`registry.properties.adminUserEnabled: false`, and the unchanged private network
configuration. **Do not require future tool auth or invent tool-path receipts**
when no tools are requested. Retain real model/network/local-runtime prerequisites.
Use `target.model_env: AZURE_AI_MODEL_DEPLOYMENT_NAME` and the same
`environment_variables` entry as the stager's canonical YAML.

```bash
"$PYTHON" "$REFS/python/deploy_preflight.py" "$SETUP"
# Owner only, still within approval: assert paired tenant/subscription context,
# then one native deploy from the final passthrough directory.
azd deploy "$AGENT" --no-prompt
# Reconcile the exact returned version, emitted digest and native metadata.
# Never assume the version number or use LIST active as proof.
"$PYTHON" "$REFS/python/hosted_smoke.py" --setup "$SETUP" --agent "$AGENT" \
  --version "$VERSION" --evidence "$NEW_PRIVATE_EVIDENCE" --execute
```

The CLI writes exclusive mode-0600 JSONL; it never overwrites previous evidence.
It requires two consecutive direct version GETs (60 attempts, 10-second
intervals), exact name/version/digest/model/instance identity and native metadata,
one model request (180-second timeout, zero automatic retries), independent
response GET plus session GET, and a final unchanged active version GET.
Setup freshness remains 30 minutes throughout; expiry is a blocker, not a
reason to edit timestamps. A fresh owner authorization remains mandatory.

The oracle compares completed assistant text/message identity, response and
session IDs and the native session's version indicator. Optional `phase: null`
does not affect equality; arbitrary exact phrasing such as `billing` is not the
criterion. Tool calls, consent requests, empty output, failed/incomplete responses,
wrong session/version/image or a newer failed GET block success. There is no
SDK patch, preview routing change, `--skip` flag or synthetic business receipt.
The response GET explicitly sends `x-agent-session-id` from the completed
response's observed session ID. Projects SDK 2.3/2.6 do not derive that header
from a prior POST on the same OpenAI client; a response ID alone does not
establish Hosted session affinity. This adds no new session or extra POST.

Registration timeout/lost ACK: stop and reconcile native versions before any
retry. Pull success, registration, health and active metadata are distinct from
the final **`PRIVATE_BASIC_MODEL_PASS`** result. Record the failed stage,
status/error code/request correlation and retained private evidence. No blind
redeploys. Refresh account/ACR ordinary GETs afterward to independently confirm
private/keyless/admin-off settings stayed unchanged. No cleanup is performed.

**Acceptance:** archive candidate SHA, exact module/tool/runtime/lock provenance,
fresh context and before/after private settings, emitted image/version/identity,
native invocation/readbacks and any failures privately. Publish only a redacted
summary. `PRIVATE_BASIC_MODEL_PASS` proves a plain model completion, not real
governed business effects, a standalone native mount-write test, production
readiness, or complete security certification.
