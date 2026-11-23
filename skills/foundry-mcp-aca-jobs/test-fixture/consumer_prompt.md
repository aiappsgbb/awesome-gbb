# Customer goal — `foundry-mcp-aca-jobs` skill smoke

Execute this live Azure smoke exactly as written. Do not replace commands,
invent fallback implementations, or browse the repository.

## Step -1 — acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/foundry-mcp-aca-jobs/SKILL.md"
```

Do NOT browse the repository. Do not view, glob, grep, or search files.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You are
already the running Copilot CLI process. Execute the commands below directly.

**Pre-granted live-infrastructure prerequisite:** the `<ci-uami-name>` identity
already has **Storage Blob Data Contributor** at the
`<ci-storage-account>` scope. The fixture needs that standing grant to create,
read, and delete its UUID-scoped blobs and containers. **Do NOT re-grant** this
role in the fixture: RBAC propagation would race the smoke timeout.

**Explicit standing-resource CI route.** This fixture uses existing resource
group, app/worker identities and Cosmos database. It never provisions a child
resource group, identity, role definition or role assignment. The executor's
Cosmos access is read-only; app/worker identities write their run-specific
control container. Storage and registry permissions must already cover the
temporary objects. Missing/mismatched permission is a blocker, not a grant.
Public endpoint reachability is NOT inferred from ARM reads; preserve any
SecuredByPerimeter configuration and fail on an unreachable data path.

## Step 0 — auth context and deterministic failure contract

The workflow has installed `az`, `azd`, `uv`, `curl`, `jq`, `python3`, and
`uuidgen`. Never install tools or search for binaries. CI grades only
`/tmp/foundry-mcp-aca-jobs-smoke-result`, not assistant prose.

Run every remaining step with exactly ONE Bash call, from the workspace root:

    bash skills/foundry-mcp-aca-jobs/test-fixture/smoke.sh

The script is the tracked, reviewed smoke (Steps 1–7 are its sections). It has
its own internal deadline and always writes the marker before it exits.

**Hard rules — the run is graded invalid if you break any of them:**
- Do NOT create, copy, edit, patch or rewrite any file (tracked or in `.scratch`).
  CI refuses to grade a run whose tracked files changed.
- Do NOT run parts of the script, re-run it, retry it, or delegate it.
- When the script exits, read `/tmp/foundry-mcp-aca-jobs-smoke-result`, report
  that one line, and STOP. A FAIL marker is a valid result: do not diagnose,
  fix or work around it. Diagnostics are already in the uploaded evidence file.
- Wait for the Bash call with long reads (it can take 40–60 minutes); do not
  start other commands while it runs.

The script's `ERR` trap writes a deterministic FAIL marker for any unhandled
hard abort; explicit preconditions write a more precise FAIL marker.

No repository writes outside `.scratch/`. The brownfield Cosmos
CI mode preserves the standing database and creates only its UUID control
container plus two UUID blob containers and the app/job. Identity, grants and
network configuration remain unchanged. On failure before postprovision records
creation, run only `ci_reuse.py record` to reconcile the exact partial deployment
before authorized cleanup; missing creation evidence blocks deletion. Never
rerun provisioning to obtain ownership evidence.
The callback payload must contain the exact four fields shown in Step 4.
PASS is written only after exact run-resource and shared worker-image deletion
has been verified, including the separately recorded hosted build image.
If cleanup cannot be proved, stop and obtain explicit bounded retention rather
than writing PASS. On interruption retain the original
ownership manifests and report residuals, never delete the shared RG/database.
