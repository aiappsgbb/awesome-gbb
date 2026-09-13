# azd routines workflow

This reference extends `foundry-routines`; it does not replace its SDK/REST
consumer contract or require installation of another skill catalog.

## Setup and target

Apply `azure-tenant-isolation` first: export tenant-specific `AZURE_CONFIG_DIR`
and `AZD_CONFIG_DIR`, verify the intended tenant/subscription, and retain those
exports in every subprocess. Do not silently change the active subscription.
Repeat the tenant/subscription assertion immediately before each mutating
command below, not only once at the start of the session.
The CLI examples below assume `FOUNDRY_PROJECT_ENDPOINT` is explicitly set
to the approved `https://<account>.services.ai.azure.com/api/projects/<project>`.

Routines require `azd >= 1.27.0` and the `azure.ai.routines` extension.
Inspect the installed extension list and help first. Install only if missing,
with approval; do not reset valid authentication:

```bash
azd extension list --installed --output json
azd extension install azure.ai.routines
azd ai routine --help
```

The install line is conditional on the preceding check; do not run the whole
block blindly. In CI, the workflow must install and authenticate the tooling,
not the consumer fixture.

## Aliases and wire types

| CLI alias | Manifest/API `type` | Meaning |
|-----------|---------------------|---------|
| `timer` | `timer` | One future moment |
| `recurring` | `schedule` | Five-field cron, minimum interval five minutes |
| `github-issue` | `github_issue` | Opened or closed GitHub issue |
| `custom` | `custom` | Event from a supported provider |
| `agent-response` | `invoke_agent_responses_api` | Responses protocol |
| `agent-invoke` | `invoke_agent_invocations_api` | Invocations protocol |

Use `cron_expression` in YAML, not `cron`. The CLI flag is `--cron`.
`--file` and `--trigger` are mutually exclusive.

## Imperative lifecycle

Use the standalone `routine.yaml` from SKILL.md when the agent needs a stored
prompt/payload. `azd ai routine create` has no `--input` flag: persist that
value as `action.input` in the manifest. Explicitly approve the schedule
before creating an enabled routine.

```bash
azd ai routine create daily-summary --file routine.yaml -p "$FOUNDRY_PROJECT_ENDPOINT"
azd ai routine show daily-summary --output json -p "$FOUNDRY_PROJECT_ENDPOINT"
```

Flag-only creation is appropriate only when no stored input is needed. This
example starts disabled and uses a different name to avoid replacing the
manifest-created routine:

```bash
azd ai routine create scheduled-check --trigger recurring --cron "0 7 * * 1-5" \
  --time-zone UTC --action agent-response --agent-name my-summary-agent \
  --enabled=false -p "$FOUNDRY_PROJECT_ENDPOINT"
```

The manifest in SKILL.md uses a named `weekday-morning` trigger. In routines
extension `1.0.0-beta.6`, inline update flags such as `--cron` address only a
`default` trigger; they fail for this manifest with
`cannot set --cron: routine has no default trigger`. For a description-only
update, edit `routine.yaml` and use `--file`, preserving the complete trigger,
action and stored input. Do not recreate the routine merely to rename its key.

The service tested in Sweden Central also rejects changing the cron value
through a manifest with `Routine trigger cannot be changed after creation`.
This is a **trigger definition** boundary, not just a trigger-type boundary.
The CLI exposing `--cron` does not guarantee that a deployed service accepts
that update. Keep the original routine intact on rejection and use the
coordinated replacement procedure below for an approved schedule change.

The following commands operate on the manifest-created routine:

```bash
azd ai routine update daily-summary --file routine.yaml -p "$FOUNDRY_PROJECT_ENDPOINT"
azd ai routine disable daily-summary -p "$FOUNDRY_PROJECT_ENDPOINT"
azd ai routine enable daily-summary -p "$FOUNDRY_PROJECT_ENDPOINT"
azd ai routine dispatch daily-summary -p "$FOUNDRY_PROJECT_ENDPOINT"
azd ai routine run list daily-summary --top 20 --output json -p "$FOUNDRY_PROJECT_ENDPOINT"
```

`dispatch --input` is a one-run override and does not change the stored
`action.input`. Match the input to the chosen action protocol and the target
agent's expected payload. Inspect run history using the returned dispatch ID:
enqueueing a run does not prove that the agent completed successfully.

Imperative `create` refuses to overwrite an existing routine unless `--force`
is explicitly supplied. Inspect the existing definition before approving an
overwrite. `update` preserves unspecified fields, but trigger and action types
are immutable, and the service may also reject definition changes within a
trigger type. A safe replacement retains the old routine until
the replacement has been verified: create the replacement disabled, check its
definition, coordinate cutover, and explicitly retire the old routine. Avoid
having both schedules enabled simultaneously.

After approval and a fresh tenant/subscription assertion, delete only the
routines created for this exercise. `--force` is required for noninteractive
deletion; it is not a substitute for authorization:

```bash
azd ai routine delete daily-summary --force -p "$FOUNDRY_PROJECT_ENDPOINT"
azd ai routine delete scheduled-check --force -p "$FOUNDRY_PROJECT_ENDPOINT"
```

If a mutation returns a response-decoding error, do not assume nothing was
created. Inspect with `show`/`list` before retrying or changing names, and
report a persistent decode failure rather than creating duplicate schedules.

## Event triggers

An event routine is not a generic HTTP webhook. Current Microsoft Learn
documents GitHub issue events and the `custom` provider `teams`:

| Trigger | Required configuration |
|---------|------------------------|
| `github_issue` | `connection_id`, `owner`, `repository`, `issue_event` (`opened` or `closed`) |
| `custom` / `teams` | `event_name: on_new_channel_message`; `parameters` with `connection_id`, `thread_type: channel`, `group_id`, `channel_id` |

An authorized connector connection and completed OAuth consent are prerequisites.
Creating a connection is a separate write requiring approval; creating a
routine does not itself complete consent. Connector identity and dispatch
identity are separate. For GitHub events, the issue payload replaces the
stored action input; the configured input is used for manual test dispatches.

Use the [official event setup](https://learn.microsoft.com/azure/foundry/agents/how-to/use-routines#event-based-triggers)
for provider-specific connection creation and consent. Do not infer support
for arbitrary providers from the CLI accepting a `--provider` string.
Manual dispatch does not prove event delivery: acceptance requires a controlled
event in the approved repository/channel and its correlated successful run.

## Declarative deployment

This is a structural excerpt to merge into an **existing** `azure.yaml` that
already defines the `summary-agent` service; it is not a standalone agent
scaffold. Replace `agent_name` with the deployed Foundry name, not merely the
local service key.

```yaml
services:
  daily-summary:
    host: azure.ai.routine
    uses:
      - summary-agent
    description: Summarize activity for the selected environment.
    enabled: false
    triggers:
      weekday-morning:
        type: schedule
        cron_expression: "0 7 * * 1-5"
        time_zone: UTC
    action:
      type: invoke_agent_responses_api
      agent_name: "<deployed-agent-name>"
      input: "Summarize activity for ${AZURE_ENV_NAME}."
```

The **service key** (`daily-summary`) is the routine name; a nested `name`
does not rename it. `uses` orders the agent before the routine. Bind the
selected azd environment to the approved project and review that environment's
subscription before deployment:

```bash
azd env set AZURE_AI_PROJECT_ENDPOINT "$FOUNDRY_PROJECT_ENDPOINT"
azd deploy daily-summary --no-prompt
```

Declarative deployment upserts the named routine. `${VAR}` strings resolve
from the selected azd environment; Foundry server-side `${{...}}` expressions
are preserved. Removing the service block does not delete the remote routine:
explicitly disable/delete it through the imperative lifecycle.

## Evidence and acceptance boundary

Source alignment: official Azure Skills v1.2.46, corresponding to
[GitHub-Copilot-for-Azure `a55fe6da7e24cbcf4331aafb903e4a070a35e972`](https://github.com/microsoft/GitHub-Copilot-for-Azure/tree/a55fe6da7e24cbcf4331aafb903e4a070a35e972/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/routine),
plus the [Microsoft Learn how-to](https://learn.microsoft.com/azure/foundry/agents/how-to/use-routines)
reviewed on 2026-09-12. Learn constrains custom events to supported providers;
the CLI's generic parameter vocabulary is not a broader service guarantee.

The existing `test-fixture/consumer_prompt.md` covers the **SDK lifecycle only**.
Additional manual live acceptance on 2026-09-13 used `azd` 1.27.0,
`azure.ai.routines` 1.0.0-beta.6 and `azure-ai-projects` 2.4.0 in the standing
CI project:

| Scenario | Observed result |
|----------|-----------------|
| SDK create, dispatch, run correlation, list and cleanup | Completed run with a response ID; disposable routine and agent deleted |
| Manifest create/show, duplicate create | Definition and stored input preserved; unapproved overwrite rejected |
| Description-only manifest update | Succeeded while retaining the complete trigger |
| Changed cron expression | Rejected as immutable; original definition remained intact |
| CLI enable, dispatch override, history, disable and delete | Succeeded; override did not change stored `action.input` |
| CLI `recurring` alias | Stored wire type was `schedule`; disabled routine deleted |
| `host: azure.ai.routine` deployment | Service key selected the name; environment interpolation worked |
| Repeated declarative deploy | Idempotent upsert; exactly one named routine |
| Cleanup | All disposable routines and prompt agents deleted; shared infrastructure unchanged |

These are CLI-user/manual results, not a new CI/OIDC fixture run. Connector
event delivery and creator-identity opt-in were **not** certified by this
acceptance: no connector consent or standing connection was changed. They
require their own authorized scenarios; do not infer either from an SDK smoke
PASS or manual dispatch.

A separate response-body diagnostic returned 404 on both project and agent
OpenAI retrieval routes despite `phase=completed`, `status=Finished` and empty
run error fields. The lifecycle acceptance proves routine execution status,
not the generated text. That diagnostic remains a recorded limitation, not
an inferred authorization workaround or a model-output PASS.
