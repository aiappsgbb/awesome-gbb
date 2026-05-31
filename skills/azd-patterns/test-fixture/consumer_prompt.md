# azd-patterns — CI verification fixture

Context: this prompt is fed to the `copilot-cli-matrix` job in the
awesome-gbb repo to verify that the `azd-patterns` skill (at
`skills/azd-patterns/SKILL.md` in the current working directory) still
deploys end-to-end against the live Azure CI infrastructure. The marquee
pattern we exercise is the **ACA Job** documented at SKILL.md
§ "Bicep: ACA Job Pattern" (~L545) — `Microsoft.App/jobs@2024-03-01`
provisioned via Bicep, then manually executed and verified.

**Expected per-run cost: ≤ $0.005** — one ACA Job execution on an
existing Container App Environment (no new env to provision), 1 vCPU
× ≤ 5 s wall time (~$0.0005), no ACR push (we use a public Microsoft
image), and ~10 management-plane API calls (~$0). Weekly stability
cost on this fixture is negligible.

## Environment available

- `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` —
  populated by OIDC login. Resource group `rg-awesome-gbb-ci` exists in
  Sweden Central and the Container Apps environment
  `cae-awesome-gbb-ci` is **pre-provisioned** (do NOT `azd provision`
  or `az containerapp env create` — it's shared infrastructure).
- Azure CLI is logged in via OIDC with the `uami-awesome-gbb-ci`
  workload identity.
- `azd` CLI is installed (≥ 1.5.0). Python 3 is available.
- **Pre-granted RBAC** (one-time CI infra setup — **NOT** something
  you provision per run): the `uami-awesome-gbb-ci` UAMI (the OIDC
  principal you authenticate as) holds **Contributor** on
  `rg-awesome-gbb-ci` and **AcrPush** on `acrawesomegbbci`. The
  pre-existing Container Apps environment `cae-awesome-gbb-ci`
  already routes logs to a Log Analytics Workspace in the same RG.
  Do NOT attempt to grant any of these roles yourself — RBAC
  propagation is 5-15 min (SKILL.md L1218) and the workflow's retry
  classifier (`skill-test.yml` L216) does not catch `Forbidden` from
  ACA control-plane operations, so a fresh grant inside the fixture
  would emit FAIL on first `az deployment group create`. If a step
  2 or step 3 call returns `Forbidden` for >2 min on the first run
  after a fresh PR push, that's NOT a propagation race (the UAMI
  was provisioned weeks ago) — treat it as a real failure and emit
  FAIL with the error detail.

## Steps

Before scratching out code, skim SKILL.md sections **ACA Job
Deployment** (L26), **Bicep: ACA Job Pattern** (L545), and the
**ACA Job: silent-failure debug playbook** (L307). The Bicep block at
L549-587 is the canonical job shape — your fixture's Bicep is a
minimal variant (no UAMI, no `fetch-container-image` indirection, no
ACR — just the smallest job that proves the pattern works against
the pre-provisioned environment).

Then run these steps. Use a shell heredoc or python heredoc as you
prefer — the goal is the result marker, not a particular ergonomics
choice.

1. **Step 0 — Verify the CI auth contract + explicit azd auth login.**
   Run these checks BEFORE any other `azd` or `az` command. If any
   fails, **stop immediately** and emit a single `SMOKE_RESULT=FAIL`
   line per the Result contract. Do NOT invent additional credential
   checks (no `az ad sp show`, no `az role assignment list`) — those
   are workflow-bug indicators, not skill bugs.

   - **Inventory the three OIDC env vars** in THIS shell. Copilot CLI
     subprocesses only inherit the workflow step's `env:` block — not
     the Azure CLI credential cache (per AGENTS.md § 9.7 Pattern 11):

     ```bash
     echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
     echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
     echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
     ```

     Every line MUST print `…=set`. If any is empty, FAIL with
     `workflow env contract: <var> empty`.

   - **Show-don't-assert: `az` CLI state.** Per AGENTS.md § 9.7 Pattern
     11, copilot CLI subprocesses inherit the workflow step's `env:`
     block but NOT the `az` CLI credential cache. The cache MAY or MAY
     NOT be inherited depending on shell-creation semantics — racing
     this is the Pattern 17 anti-pattern. Print for the audit log; do
     NOT gate flow on the result:

     ```bash
     az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
     ```

     Per Pattern 16 + 17, the `azd auth login` step immediately below is
     the deterministic auth proof. Do NOT FAIL the smoke on this `az`
     output — it is informational only.

   - **Explicit `azd auth login`** (AGENTS.md § 9.7 Pattern 6).
     Implicit OIDC pickup via `AZURE_FEDERATED_TOKEN_FILE` has two
     silent failure modes: (a) azd < 1.5.0 doesn't auto-detect the
     file; (b) sub-shell env reset blanks the credential mid-run.
     Explicit login surfaces credential failures up-front (~2 s
     overhead) and mirrors what a customer following SKILL.md verbatim
     would type:

     ```bash
     azd auth login \
       --federated-credential-provider github \
       --client-id "$AZURE_CLIENT_ID" \
       --tenant-id "$AZURE_TENANT_ID"
     ```

     If this errors, FAIL with `azd auth login: <one-line reason>`.

   `az` CLI is already logged in via the workflow's `azure/login@v2`
   step — don't re-run `az login`. Only if all three checks pass,
   proceed to step 2.

2. **Step 1 — Generate per-run UUID suffix and scaffold Bicep.**
   Use 8 hex chars from `uuid.uuid4().hex`. Naming pattern (mandatory
   — parallel matrix runs and PR retries collide on fixed names):

   - `SUFFIX="$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"`
   - `JOB_NAME="ci-azd-pat-${SUFFIX}"` (must be ≤ 32 chars, lowercase,
     alphanumeric + dashes — `ci-azd-pat-` is 11 chars + 8 hex = 19,
     well under the limit)
   - `RG="rg-awesome-gbb-ci"`
   - `CAE_NAME="cae-awesome-gbb-ci"`
   - `LOCATION="swedencentral"`
   - `SCAFFOLD_DIR="/tmp/${JOB_NAME}"`
   - `mkdir -p "${SCAFFOLD_DIR}"`

   Write `${SCAFFOLD_DIR}/main.bicep` — a minimal `Microsoft.App/jobs`
   resource referencing the existing CAE by name lookup. Use the
   `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`
   image with a `command:` + `args:` override so the container prints
   `HELLO` and exits 0 (no ACR push needed). The job MUST be
   `triggerType: 'Manual'` and `replicaCompletionCount: 1` so we can
   control execution timing in Step 3.

   ```bicep
   param jobName string
   param caeName string
   param location string = resourceGroup().location

   resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
     name: caeName
   }

   resource job 'Microsoft.App/jobs@2024-03-01' = {
     name: jobName
     location: location
     properties: {
       environmentId: cae.id
       configuration: {
         triggerType: 'Manual'
         replicaTimeout: 300
         replicaRetryLimit: 0
         manualTriggerConfig: {
           replicaCompletionCount: 1
           parallelism: 1
         }
       }
       template: {
         containers: [
           {
             name: 'job'
             image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
             command: ['/bin/sh', '-c']
             args: ['echo HELLO']
             resources: {
               cpu: json('0.5')
               memory: '1Gi'
             }
           }
         ]
       }
     }
   }
   ```

   This is a deliberate minimal variant of SKILL.md L549-587 — no
   UAMI, no ACR, no `fetch-container-image` indirection. The fixture
   proves the canonical `Microsoft.App/jobs@2024-03-01` resource
   shape + the `triggerType: 'Manual'` + `replicaCompletionCount: 1`
   pattern still deploys against an existing CAE. The fuller
   ACR-image + UAMI + cron variant in the SKILL is audited per the
   21-class catalog at `docs/audit/azd-patterns-audit-trail.md` but
   not exercised here (see Out-of-scope coverage note below).

3. **Step 2 — Deploy via `az deployment group create`.** SKILL.md
   L26 explicitly notes that `azd` does NOT natively deploy Container
   Apps Jobs — only Container Apps. A pure-Job fixture (no service)
   cannot use `azd up` at all because the deploy phase has nothing
   to deploy and the documented `postdeploy` hook never fires. So we
   hand-roll the deployment directly:

   ```bash
   az deployment group create \
     --resource-group "${RG}" \
     --template-file "${SCAFFOLD_DIR}/main.bicep" \
     --parameters jobName="${JOB_NAME}" caeName="${CAE_NAME}" \
     --no-prompt --only-show-errors -o none
   ```

   Expected: ≤ 60 s. If this returns non-zero, capture stderr and
   emit FAIL with the first 80 chars of the error message.

4. **Step 3 — Trigger one manual execution.** ACA Jobs with
   `triggerType: 'Manual'` only run when explicitly started. The
   `az containerapp job start` call returns the execution name on
   success:

   ```bash
   EXECUTION="$(az containerapp job start \
     --resource-group "${RG}" \
     --name "${JOB_NAME}" \
     --query name -o tsv)"
   ```

   Now poll for completion. ACA Jobs surface a `JobExecutionNotFound`
   transient (Finding #17 — ~10 s window between `start` returning
   and the execution record being observable), so the first
   `az containerapp job execution show` may 404 — retry the show
   call up to 6 times with 5 s sleeps before treating as a real
   failure. Then wait for `properties.status` to transition out of
   `Running`. Total budget: 90 s.

   ```bash
   for i in $(seq 1 18); do
     STATUS="$(az containerapp job execution show \
       --resource-group "${RG}" \
       --name "${JOB_NAME}" \
       --job-execution-name "${EXECUTION}" \
       --query "properties.status" -o tsv 2>/dev/null || echo 'pending')"
     case "${STATUS}" in
       Succeeded) break ;;
       Failed|Degraded) break ;;
     esac
     sleep 5
   done
   ```

   If `STATUS` is not `Succeeded` after the loop, emit FAIL with the
   observed status.

5. **Step 4 — Verify HELLO in the execution console logs.** SKILL.md
   L313 documents that `az containerapp job logs show` hangs
   indefinitely on some ACA Job runs — DO NOT use that command. Use
   the Log Analytics Workspace query instead (SKILL.md L351-357
   pattern). The CAE's LAW customer ID is discoverable via:

   ```bash
   WS_CUSTOMER_ID="$(az containerapp env show \
     --resource-group "${RG}" \
     --name "${CAE_NAME}" \
     --query "properties.appLogsConfiguration.logAnalyticsConfiguration.customerId" \
     -o tsv)"
   ```

   ACA Job console logs are routed through the LogAnalytics agent on
   the worker and then through LAW ingestion. Documented Azure
   ingestion p50 is ~2 min, p95 ~5 min, p99 ~10 min — the latency is
   inherent to the LAW pipeline, NOT a bug in the ACA Job. The smoke's
   PRIMARY success signal is Step 3's `STATUS=Succeeded` (control-plane
   synchronous). The LAW probe verifies that the documented SKILL.md
   L351-357 query pattern works **when ingestion has landed**, but
   ingestion lag MUST NOT fail the smoke (Pattern 13 — Finding #18,
   2026-05-31 azd-patterns run `26697996194`). Poll for up to 300 s:

   ```bash
   QUERY="ContainerAppConsoleLogs_CL | where ContainerJobName_s == '${JOB_NAME}' | where Log_s contains 'HELLO' | take 1 | project Log_s"
   FOUND=""
   for i in $(seq 1 60); do
     ROW="$(az monitor log-analytics query \
       --workspace "${WS_CUSTOMER_ID}" \
       --analytics-query "${QUERY}" \
       --query "[0].Log_s" -o tsv 2>/dev/null || true)"
     if [ -n "${ROW}" ] && echo "${ROW}" | grep -q "HELLO"; then
       FOUND="yes"; break
     fi
     sleep 5
   done
   ```

   **Soft-PASS on LAW lag.** If `FOUND` is `yes`, both signals align —
   proceed to Step 5. If `FOUND` is empty after 300 s AND Step 3 already
   proved `STATUS=Succeeded`, the smoke STILL PASSes — emit a clear
   NOTE line to your stdout (the transcript captures it for audit):

   ```
   NOTE: LAW ingestion lag observed (300s budget exhausted, execution status Succeeded). Skill behavior verified via control-plane signal.
   ```

   The marker file MUST remain byte-exact `SMOKE_RESULT=PASS\n` —
   qualifiers in the marker defeat the `cmp -s` PASS contract.

   ONLY emit FAIL if Step 3's `STATUS` was NOT `Succeeded` (that case
   is already handled at Step 3 L233-234 — Step 4 should never reach
   FAIL on its own).

6. **Step 5 — Cleanup (job-scoped only).** Delete the job resource.
   Do NOT `az group delete rg-awesome-gbb-ci` — that's shared CI
   infrastructure that the other matrix legs (`foundry-hosted-agents`,
   `foundry-prompt-agents`) also use.

   ```bash
   az containerapp job delete \
     --resource-group "${RG}" \
     --name "${JOB_NAME}" \
     --yes -o none
   ```

   A 404 here means the job was already gone — treat as success.

7. **Step 6 — Write the result marker (deterministic, MANDATORY).**
   After step 5 succeeds, your FINAL action is to invoke the Bash tool
   to run exactly this command. The file's literal byte content is what
   CI grades — **NOT** your assistant text reply. Do NOT type the marker
   token in prose; do NOT echo it; do NOT mention it in your summary.

   ```bash
   printf 'SMOKE_RESULT=PASS\n' > /tmp/azd-patterns-smoke-result
   ```

   If ANY step 1-5 fails, instead run (substitute a real reason, ≤80
   chars, no backticks, no newlines):

   ```bash
   printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azd-patterns-smoke-result
   ```

   The marker path is fixed: `/tmp/azd-patterns-smoke-result`. After
   writing the marker you may add a brief free-form prose summary for
   the human reviewer, but it does not affect grading.

## Out-of-scope coverage note

This fixture exercises ONLY the ACA Job marquee pattern. Other
`azd-patterns` documented surfaces audited per the 21-class catalog at
`docs/audit/azd-patterns-audit-trail.md` but NOT exercised by this
fixture:

- **ACA service postdeploy hook** (SKILL.md § "Fetch-Latest-Image
  Pattern", L164) — would require an ACR push of a real image, ~$0.005
  added per run for storage + transfer; deferred because the
  hosted-agents fixture already covers `azd deploy` with `remoteBuild`.
- **Azure Functions wiring** (SKILL.md § "Composable Bicep Module
  Library", L755 entry for the Functions module) — no separate matrix
  leg today; deferred to a Functions-specific skill if/when one ships.
- **Cosmos DB firewall pilot-grade defaults** (SKILL.md § "Cosmos
  firewall", L824) — exercised end-to-end by customer-pilot E2E, not
  CI matrix.
- **MI wiring matrix** (SKILL.md § "Shared UAMI Pattern", L595) — the
  CAE+UAMI shared in `rg-awesome-gbb-ci` already exercises the shared-
  UAMI pattern statically; no per-run regression risk.

Per master-plan spec § 11, single-fixture coverage is the accepted
trade-off for library-shaped skills. Cross-pattern integration testing
belongs in customer-pilot E2E, not the CI matrix.

## Result contract

CI clears `/tmp/azd-patterns-smoke-result` BEFORE invoking you, then
after your turn ends grades the result in this strict order:

1. If the marker file contains a line starting with `SMOKE_RESULT=FAIL`
   → the leg FAILs (and the line's reason is surfaced in the run log).
2. If the marker file contains exactly the bytes `SMOKE_RESULT=PASS\n`
   (compared with `cmp -s`, byte-exact) → the leg PASSes.
3. If the marker file is missing or malformed → the leg FAILs with a
   diagnostic dump (legacy transcript-grep fallback exists for the
   transition window but is scheduled for removal — do not rely on it).

The deterministic file-write path is mandatory because an earlier run
(`actions/runs/26697592828`, 2026-05-30) showed the LLM stochastically
wraps the marker in markdown decoration (backticks, bold) when asked
to emit it as prose, breaking line-boundary grep. Writing the marker
via a Bash tool call bypasses prose rendering entirely — the bytes that
hit disk are the bytes `printf` puts there.

### Runtime guardrails

- Do NOT redirect your own stdout via `exec > >(tee ...)` or any
  process-substitution pattern. The Copilot CLI shell wrapper blocks
  process substitution. Your stdout is already captured by CI — you do
  not need to tee it.
- Do NOT call `az containerapp job logs show` — SKILL.md L313
  documents that it hangs indefinitely. Use the LAW query in Step 4.
- Do NOT delete the resource group (`rg-awesome-gbb-ci`) — it is
  shared CI infrastructure. Only delete the per-run job resource.

Please don't modify any file under `skills/` — this is verification
only.
