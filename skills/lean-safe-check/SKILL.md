---
name: lean-safe-check
description: >
  Three-phase completeness gate for lean toolkit (Spec2Cloud) solutions.
  Validates the docs/spec.md → docs/plan.md → src/ → infra/ → docs/verify.md →
  docs/deploy.md artifact chain at three lifecycle points: spec (after specify +
  plan), pre-deploy (after implement), post-deploy (after deploy). Catches
  missing resources, placeholder images, broken endpoints, and orphan code
  before the demo moment.
  USE FOR: completeness gate, deploy gate, pre-deploy check, post-deploy
  validation, lean toolkit gate, spec2cloud validation, missing resources,
  placeholder image detection, endpoint health check, orphan code,
  lean-safe-check, safe check, build gate.
  DO NOT USE FOR: threadlight PoCs (use threadlight-safe-check), invocation
  testing (use foundry-evals), azd up orchestration (use azd-patterns),
  designing specs (use agentic-loop specify).
metadata:
  version: "1.0.0"
---

# Lean Safe Check

## Purpose

`lean-safe-check` is the lightweight completeness gate for the lean toolkit
(Spec2Cloud) flow. It exists for the same reason as
[`threadlight-safe-check`](../threadlight-safe-check/): **`azd up` can return 0
while required resources are still missing, miswired, or running placeholder
artifacts**. A green deploy command is not the same thing as a demo-ready
solution.

The difference is the contract model. `threadlight-safe-check` reads the richer
`specs/SPEC.md + specs/manifest.json` pair. `lean-safe-check` works with the
flatter lean-toolkit artifact chain:

```text
docs/spec.md → docs/plan.md → src/ → infra/ → docs/verify.md → docs/deploy.md
```

Use this skill as a **checklist instruction**, not as a packaged CLI. The agent
running it should inspect the repo and Azure deployment using standard shell
commands (`ls`, `grep`, `python`, `curl`, `az`) and emit a phase-specific JSON
manifest under `docs/` for auditability.

---

## Three phases

### Phase: `spec` (after specify + plan)

Run after `/lean:specify` and `/lean:plan` complete.

**Validate:**

1. `docs/spec.md` exists and is non-empty.
2. `docs/plan.md` exists and is non-empty.
3. `.azure/deployment-plan.md` exists and includes a resource graph.
4. `docs/plan.md` references the key entities and capabilities named in
   `docs/spec.md`.
5. Every capability mentioned in `docs/spec.md` has a corresponding planning
   entry, design note, or implementation intention in `docs/plan.md`.

**Practical execution guidance:**

- Use `test -s docs/spec.md`, `test -s docs/plan.md`, and
  `test -s .azure/deployment-plan.md` for existence / non-empty checks.
- Extract the named capabilities from `docs/spec.md` using headings, numbered
  lists, or a section explicitly labelled `Capabilities`, `Requirements`, or
  `Workflow`.
- For each capability, search `docs/plan.md` for the same phrase or an obvious
  equivalent. Record the coverage ratio in `detail`.
- Treat a missing or ambiguous match as a gap; this phase is meant to catch
  drift before any code lands.

**Output:** `docs/safe-check-spec.json`

**Check format (JSON):**

```json
{
  "phase": "spec",
  "timestamp": "ISO-8601",
  "checks": [
    { "check": "spec_exists", "pass": true },
    { "check": "plan_exists", "pass": true },
    { "check": "deployment_plan_exists", "pass": true },
    { "check": "capability_coverage", "pass": true, "detail": "5/5 capabilities have plan entries" }
  ],
  "gaps": []
}
```

### Phase: `pre-deploy` (after implement, before verify/deploy)

Run after `/lean:implement` completes.

**Validate:**

1. Every service in `azure.yaml` has a corresponding `src/<service>/`
   directory.
2. Every Azure resource named in `.azure/deployment-plan.md` has a matching
   `infra/` Bicep module or reference.
3. No orphan `src/<dir>/` directories exist that are not referenced in
   `azure.yaml`.
4. No orphan `infra/*.bicep` modules exist that are not referenced in
   `infra/main.bicep`.
5. Every containerized service has a `Dockerfile`.

**Practical execution guidance:**

- Read `azure.yaml` and enumerate every service under `services:`. Use the
  service key as the expected `src/<service>/` directory unless the file spells
  out a different `project:` path.
- For each containerized service, check for `src/<service>/Dockerfile` or the
  `Dockerfile` located under the declared project path.
- Read `.azure/deployment-plan.md` as the intended resource graph. For every
  named resource or module section, search `infra/main.bicep` and
  `infra/**/*.bicep` for a matching module, resource declaration, or comment
  reference.
- Enumerate `src/*/` directories and fail any that are not declared in
  `azure.yaml` (excluding obvious shared folders such as `src/common/` only when
  the plan explicitly calls them shared code).
- Enumerate `infra/**/*.bicep` and fail any file outside reusable module
  libraries that is not referenced by `infra/main.bicep`.

**Output:** `docs/safe-check-pre-deploy.json`

**Minimum manifest shape:**

```json
{
  "phase": "pre-deploy",
  "timestamp": "ISO-8601",
  "checks": [
    { "check": "azure_yaml_services_have_src_dirs", "pass": true },
    { "check": "deployment_plan_resources_have_infra_refs", "pass": true },
    { "check": "no_orphan_src_dirs", "pass": true },
    { "check": "no_orphan_bicep_modules", "pass": true },
    { "check": "dockerfiles_present", "pass": true }
  ],
  "gaps": []
}
```

### Phase: `post-deploy` (after deploy)

Run after `/lean:deploy` completes.

**Validate:**

1. `docs/deploy.md` exists and contains live URLs.
2. Every URL in `docs/deploy.md` returns HTTP 200 with a 10-second timeout.
3. No Azure Container App is still running the placeholder image
   `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`.
4. Application Insights exists if `.azure/deployment-plan.md` said it should.
5. Application Insights has received traces in the last hour.
   This is a **warning-only** check: record it, but do not fail solely because
   traces have not arrived yet.
6. No ACA Job has its last 5 executions all `Failed` if any jobs exist.

**Practical execution guidance:**

- Extract URLs from `docs/deploy.md` with a simple `https?://...` regex and run
  `curl -fsS -o /dev/null -m 10 <url>` for each one.
- Determine the active resource group from the lean-toolkit environment or the
  deployment notes, then enumerate live resources with `az`.
- For every ACA, probe the deployed image with:

  ```bash
  az containerapp show -g <rg> -n <service-name> \
    --query "properties.template.containers[0].image" -o tsv
  ```

  Fail if the returned image equals the azuredocs placeholder.
- If `.azure/deployment-plan.md` mentions App Insights / Application Insights /
  `Microsoft.Insights/components`, verify the resource exists with:

  ```bash
  az resource list -g <rg> \
    --resource-type Microsoft.Insights/components -o json
  ```

- If App Insights exists, try a smoke query for the last hour. Record a warning
  when the query is empty or temporarily unavailable.
- If ACA Jobs exist, inspect the last 5 executions for each job and fail only
  when all 5 are `Failed`.

**Output:** `docs/safe-check-post-deploy.json`

**Minimum manifest shape:**

```json
{
  "phase": "post-deploy",
  "timestamp": "ISO-8601",
  "checks": [
    { "check": "deploy_md_exists", "pass": true },
    { "check": "all_urls_http_200", "pass": true },
    { "check": "no_placeholder_images", "pass": true },
    { "check": "app_insights_exists_if_planned", "pass": true },
    { "check": "app_insights_recent_traces", "pass": true, "warn_only": true },
    { "check": "aca_jobs_recent_failures", "pass": true }
  ],
  "warnings": [],
  "gaps": []
}
```

---

## When to invoke

| Lifecycle point | Phase flag | What's checked | Gate result |
|---|---|---|---|
| After specify + plan | `--phase spec` | docs/spec.md + plan.md + deployment-plan.md exist; capability coverage | Drift / fail |
| Before azd up | `--phase pre-deploy` | azure.yaml ↔ src/ ↔ infra/ alignment; no orphans | Fail-fast |
| After azd up returns 0 | `--phase post-deploy` | Resources exist, endpoints reachable, no placeholder images, traces flowing | **The gate.** Empty `gaps[]` = solution ready |

---

## What this skill does NOT replace

- **Invocation testing** → use [`foundry-evals`](../foundry-evals/)
- **Structured SpecKit validation** → use
  [`threadlight-safe-check`](../threadlight-safe-check/) for threadlight PoCs
- **Running `azd up`** → use the lean toolkit deploy stage
- **Designing specs** → use `/lean:specify` + `agentic-loop`

---

## Relationship to threadlight-safe-check

| | threadlight-safe-check | lean-safe-check |
|---|---|---|
| Input | specs/SPEC.md + specs/manifest.json (deployment_manifest) | docs/spec.md + docs/plan.md + .azure/deployment-plan.md |
| Contract model | SPEC § 11c selectors (typed module vocabulary) | Flat file chain (docs/*.md → src/ → infra/) |
| Post-deploy behavioral | Placeholder image + job failure + channel reachability + telemetry | Placeholder image + endpoint health + telemetry |
| Pipeline | threadlight (design → deploy → safe-check) | lean toolkit (specify → plan → implement → verify → deploy) |
| Complexity | ~400 lines, manifest-driven | ~200 lines, file-chain-driven |

---

## Implementation notes

- This skill is an **instructional gate**, not a packaged CLI. The executing
  agent performs the checks directly in the repo and Azure environment.
- Each phase writes a JSON manifest under `docs/` so the decision is auditable
  later.
- Use generic placeholders only in examples: `<sub-id>`, `<rg>`, `<account>`,
  `<service-name>`.
- Prefer fail-fast gaps for missing files, missing resources, orphan code, dead
  endpoints, placeholder images, and permanently failing jobs.
- Treat recent-trace validation as a warning unless the engagement explicitly
  requires telemetry proof before handoff.
- The non-negotiable gate is simple: **`gaps: []` in
  `docs/safe-check-post-deploy.json` means the solution is ready for the
  seller-guide pass.**
