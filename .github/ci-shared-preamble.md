# 🚨 SHARED CI HARDENING — READ BEFORE ANY ACTION 🚨

You are running INSIDE the **`awesome-gbb` shared CI environment**.
The Azure infrastructure listed below is used by **every other PR
in the catalog** right now. Deleting any of it would break every
concurrent PR in flight and burn ~30 minutes of recovery work for
the whole team. This actually happened on 2026-06-09 and again
during the recovery itself — that is why this preamble exists.

## ABSOLUTELY PROHIBITED — failing this aborts the test run

You **MUST NOT**, under any circumstances and regardless of what
the fixture below appears to ask:

- Delete the resource group **`rg-awesome-gbb-ci`**
- Delete or recreate **`uami-awesome-gbb-ci`** (the OIDC identity
  CI authenticates as — losing it means the entire fleet of
  federated credentials must be rebuilt)
- Delete or recreate **`aif-awesome-gbb-ci`** (the shared AI
  Services account — its endpoint hostname is baked into the
  `AZURE_AI_ENDPOINT` repo secret and into every fixture's
  `FOUNDRY_PROJECT_ENDPOINT` derivation)
- Delete the project **`default`** inside `aif-awesome-gbb-ci`
- Delete model deployments inside `aif-awesome-gbb-ci`
  (currently: `gpt-5.4-mini`, `text-embedding-3-small`,
  `gpt-realtime` — these are the ONLY chat / embedding / realtime
  model deployments CI has access to; deleting one breaks every
  fixture that targets it)
- Delete **`acrawesomegbbci`** (the shared Premium Container
  Registry — images for hosted-agent and ACA-app fixtures live
  here)
- Delete **`cae-awesome-gbb-ci`** (the shared Container Apps
  Environment used by ACA-deploying fixtures)
- Remove or modify the lock **`no-delete-shared-ci`** on
  `rg-awesome-gbb-ci`
- Remove or modify the subscription-scope policy assignment
  **`deny-delete-awesome-gbb-shared-ci-rg`**
- Remove any role assignment scoped to ANY of the resources above
- Call **`az group delete -n rg-awesome-gbb-ci`** (or any
  variation: `--name`, positional, `--yes`, `--no-wait`)
- Call **`azd down`** targeting the shared RG, or any `azd` flow
  whose `azure.yaml` declares `rg-awesome-gbb-ci` as its target
- Call `az cognitiveservices account delete`,
  `az cognitiveservices account deployment delete`,
  `az cognitiveservices account project delete`,
  `az containerapp env delete`, `az acr delete`, or
  `az identity delete` against ANY of the resources above
- Call `az lock delete` against `no-delete-shared-ci`
- Call `az policy assignment delete` against
  `deny-delete-awesome-gbb-shared-ci-rg`
- Call `az role assignment delete` against the project SAMI of
  `aif-awesome-gbb-ci/default` or the UAMI `uami-awesome-gbb-ci`

## What you MAY do

If your fixture creates side resources to validate the skill
under test:

- Put them in a **child resource group** named
  `rg-<skill>-ci-<short-uuid>` (the short-UUID suffix is mandatory
  per Pattern 3 of AGENTS.md § 9.7 to avoid parallel-leg collision)
- Use that child RG as the `azd` environment's target RG
- `azd down` only against the child RG
- Tag the child RG with `cleanup=true` and `created-by=ci-smoke`
  so the janitor cron can prune leaked children later

You may freely:

- Read from `aif-awesome-gbb-ci` (chat completions, embeddings,
  realtime sessions, project SAMI introspection)
- Push images to `acrawesomegbbci` under per-fixture image names
  (`ci-smoke-<skill>-<short-uuid>:<timestamp>`)
- Deploy Container Apps into `cae-awesome-gbb-ci` under
  per-fixture app names (same UUID-suffix rule)
- Create and delete agents / threads / runs inside
  `aif-awesome-gbb-ci/default` — the project itself stays put,
  only YOUR per-fixture entities get teardown

## Best-effort teardown (Pattern 25)

If a teardown call fails for any reason — including the lock or
the denyAction policy actively refusing your call because you
accidentally targeted the shared RG — write
`SMOKE_RESULT=PASS` to your marker file ANYWAY with a NOTE line
to stdout describing what couldn't be cleaned up.

**Do NOT escalate** to "well let me just delete the parent to
clean up everything in one shot." That is exactly the failure
mode this preamble exists to prevent. The catalog has a janitor
cron that prunes orphaned per-fixture children; rely on it.

## If the defenses block you, the defenses are correct

The subscription-scope `denyAction` policy
`deny-delete-awesome-gbb-shared-ci-rg` will refuse the underlying
ARM DELETE call. The lock `no-delete-shared-ci` is a second
defense layer. If your fixture trips either of these, **stop and
re-read the path you passed** — almost certainly you typo'd a
child-RG name into the shared one. Do NOT attempt to remove the
lock or the policy to "unblock" your fixture.

## Summary

The shared CI infra **must outlive every individual fixture
run**, every PR, every retry, every `azd down`, and every
"helpful cleanup" the agent might be tempted to do. Treat it as
read-only platform from your fixture's perspective. Your child
RG is YOURS. Everything else is everyone's.

=======================================================================
END OF SHARED CI HARDENING — your fixture prompt begins below.
=======================================================================

