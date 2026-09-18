# Jobs consumer execution smoke

Read this fixture, then execute the single Bash action below. This is a live
execution smoke, not repository inspection or an invitation to repair prerequisites.
The workflow installs azd, its pinned Foundry extension, uv and the isolated
Python runtime. Do not install tools, grant roles, create identities, hunt for
credentials, change network policy or edit source.

**Never invoke `copilot` recursively.** You are the running process. The workflow
owns transcripts, approvals and encrypted inventory. Never overwrite those files.

The owner provides an existing workload RG, ACR, CAE, a dedicated Blob account,
a dedicated Cosmos account with ONE standing database, and two DISTINCT standing
app/worker UAMIs. App Job Operator is pre-granted at that exact RG; ACR/Blob/Cosmos
grants are also standing prerequisites. Do NOT re-grant them. Runner identity is
an app-only CI UAMI; its object ID is not its client ID or the operator's identity.
Storage Blob Data Contributor is pre-granted to `<ci-uami-name>` and both
workload UAMIs on the dedicated `<ci-storage-account>`; do not re-grant it.
Static bearer is smoke-only; production must use a header provider.
Static bearer is smoke-only; production must use project_connection_id.

The runner-owned helper stages the original-SHA canonical opt-in `ci.bicep`,
uses azd provision/deploy with the canonical shared-image postdeploy hook, and
captures only this run's exact app, Job, control container and two Blob containers.
It also owns prompt/Hosted agents and the owned app's EasyAuth/routing mutation.
There is no child RG, custom role definition, new standing assignment, broad
`azd down`, force-delete, shared-resource cleanup or retry after uncertain writes.
Names are not ownership proof. Missing/expired custody or unknown effects fail
closed; never create a replacement to work around them.

The functional assertions remain task completion, idempotency, cancellation,
fallback tools, exact four-field callback payload, canonical digest/entrypoint
verification, and real prompt/Hosted `mcp_call` outputs. A request retries neither
model invocation nor unknown mutation. Hosted readiness reads are bounded.

```bash
set -euo pipefail
echo "skills/foundry-mcp-aca-jobs/SKILL.md"
"$JOBS_CI_PYTHON" "$JOBS_CI_HELPER" smoke
```

The helper writes the byte-exact result marker after functional assertions.
The workflow then always runs the original-SHA finalizer separately and uploads
only the encrypted receipt. Functional PASS is not cleanup PASS. Residual,
UNKNOWN, expired or interrupted cleanup remains explicit; no `CLEANUP_COMPLETE`
claim follows a submitted DELETE. Standing infrastructure, images and provider
deployment history have separate owner retention, never per-run deletion custody.
