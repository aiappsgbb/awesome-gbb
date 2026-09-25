# Managed Voice Agent live acceptance

Execute the canonical `skills/foundry-voice-agents` client against the authorized
existing CI project. Read `SKILL.md` and import its actual modules; do not
redefine their code. This is real execution, not catalog inspection.
**Never invoke `copilot` recursively** or rewrite the workflow's transcript.

## Scope and preconditions

No infrastructure provisioning, role grant, shared model/endpoint/telemetry
change, content-capture toggle, phone call, microphone, Docker or hosted pipeline.
The fixture's controlled operations are three fixed synthetic Speech utterances,
two unique prompt voice agents, audio sessions, a harmless local tool, one
persisted synthetic conversation, approved in-memory transcript/audio readback,
private local WAV capture and exact owned cleanup. These independent consent
switches are explicit in `live_acceptance.py`; they are not permission to capture
real content or retain any audio after the test.

Use the workflow-provided `FOUNDRY_PROJECT_ENDPOINT`, `AZURE_AI_PROJECT_ID`,
`AZURE_AI_ENDPOINT` and tenant/subscription.
Select managed `gpt-realtime`, not the fixture driver's chat deployment.
The project must already have managed voice preview access and **no configured
AppInsights binding at either account or project scope**. The canonical helper
checks both scopes before transmitting audio and immediately before each session.
If a binding exists or cannot be checked, stop; do not disable/overwrite it,
create a new secret, grant, connection or exporter, or inherit a previous run's
content-retention consent.

The workflow provides Python, Azure CLI and credentials. No tool installation
or filesystem hunts. Install only this skill's dependencies into its own
private venv; never upgrade the shared test/runtime environment. On a local
run use the canonical tenant-isolation bootstrap and explicit approved target.
In GitHub Actions the runner's Azure login profile is already job-private:
make its path explicit without switching subscriptions or logging in again.
No such fallback is permitted on a developer machine.

## Step 1 - Prepare the isolated client

Run from the repository root. Use these commands only in the authorized runner:

```bash
set -euo pipefail
test "${GITHUB_ACTIONS:-}" = true
: "${RUNNER_TEMP:?}" "${FOUNDRY_PROJECT_ENDPOINT:?}" "${AZURE_AI_PROJECT_ID:?}"
: "${AZURE_AI_ENDPOINT:?}" "${AZURE_TENANT_ID:?}" "${AZURE_SUBSCRIPTION_ID:?}"
umask 077
export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-$HOME/.azure}"
export AZD_CONFIG_DIR="$RUNNER_TEMP/voice-azd"
export AZURE_TOKEN_CREDENTIALS=AzureCliCredential
python3 -m venv "$RUNNER_TEMP/voice-client"
"$RUNNER_TEMP/voice-client/bin/python" -m pip install --quiet \
  -r skills/foundry-voice-agents/requirements.txt \
  -c skills/foundry-voice-agents/constraints.txt
```

Check the exact tenant/subscription through the canonical client's context
guard, without printing credentials. The account ARM ID is the parent of the
workflow-resolved `AZURE_AI_PROJECT_ID`, ending immediately before `/projects/`.
Validate that the project endpoint/account names agree; never substitute a
default project or rewrite shared environment. Tracing is deliberately not
configured or exercised by this automated fixture.

## Step 2 - Execute the exact synthetic contract

Invoke `test-fixture/live_acceptance.py` using the isolated interpreter:
`--endpoint "$FOUNDRY_PROJECT_ENDPOINT"`, `--speech-endpoint "$AZURE_AI_ENDPOINT"`,
`--account-id <validated-parent-ARM-ID>`, `--model gpt-realtime`,
`--evidence-dir <new-private-run-directory>` and `--approve-live-synthetic`.
Do not paste the helper body into another script. Do not reuse an existing
evidence directory: an interrupted run must be reconciled first, not replaced.

The helper records source hashes and create intents before mutations and
uses unique run metadata on every created version. It must prove:

- Greeting audio before input, actual PCM input and nonempty spoken reply.
- Actual function arguments/output and a response completed after tool output.
- User speech during active answer audio, discarded stale audio, cancellation
  only on detected interruption and a completed reply to the latest request.
- Explicit `store=False` baseline with no retrievable persisted conversation.
- Separately enabled storage, chronological caller/assistant transcript meaning,
  actual downloaded nonempty stereo audio, not just metadata or a protected URI.
- Exact inventoried conversation/version/agent absence and local WAV deletion.

The multi-sentence long prompt previously split into two VAD turns; the canonical
single-sentence utterance avoids that setup defect without weakening the actual
barge-in check. Do not substitute text-only input or mute errors.
The helper's `VOICE_FUNCTIONAL=PASS` is only its functional result; require its
privacy preflight and verified cleanup too. Its `TRACE=NOT_EXERCISED` is an
explicit coverage boundary, not a trace PASS.

## Step 3 - Preserve the tracing coverage boundary

Manual service trace correlation was proven separately, but its attempted
metadata-only behavior failed: nonempty message and tool-result attributes were
emitted without a client content toggle. The owner accepted 30-day retention of
that existing synthetic test window only. See the sanitized validation record.
Do not repeat that capture, query its content, or recreate its binding/role.
This automated fixture proves the functional voice/storage contract and refuses
configured tracing rather than claiming a metadata-only tracing recipe works.

## Step 4 - Close the result

Review the private inventory and cleanup errors even if the process exited
nonzero. If cleanup is blocked, fence those exact IDs; no replacement resources.
No `azd down`, shared RG/agent delete, or silent retention. Conversation deletion
does not delete independently captured telemetry or previously downloaded copies.
Keep only the approved metadata evidence with the existing run-artifact policy.

After the no-configured-tracing preflight, all functional and lifecycle gates pass,
use the Bash tool as the
final action:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-voice-agents-smoke-result
```

On any missing/failed gate, write a non-sensitive one-line reason instead:

```bash
printf 'SMOKE_RESULT=FAIL <reason>\n' > /tmp/foundry-voice-agents-smoke-result
```

Never write PASS from a partial functional run, stale evidence, a bypassed
privacy preflight or an unknown cleanup outcome. The byte-exact marker does not
replace proof in the protected evidence artifact.
