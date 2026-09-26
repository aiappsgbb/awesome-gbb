# Execute the checked-in managed Voice contract once

You are a **test executor, not a coding agent or fixture maintainer** in this run.
Read `skills/foundry-voice-agents/SKILL.md`, then execute the single command below.
Do not edit any source, assertion, test, workflow or instructions. Do not run
another live attempt if it fails. Do not substitute another script, lower a
transcript requirement to roles/audio, or write a PASS marker yourself.
**Never invoke `copilot` recursively.**

The canonical entry point records ownership before mutations and performs exact
cleanup in `finally`. It rejects a dirty checkout and a second entry in the same
CI run/attempt before Azure work. Failure is a result to report, not permission
to diagnose by generating more resources. Preserve its private inventory and
sanitized receipt: **never delete evidence directories or the attempt receipt**.

## Authorized coverage

Only fixed synthetic Speech utterances, two unique managed prompt voice agents,
audio/greeting/function/barge-in, an explicit no-storage cycle and a separately
consented transcript/stereo-audio storage/read/delete cycle. No microphone,
telephony, Docker, new model, role, connection, network or infrastructure change.
The helper checks account and project connections and refuses configured
AppInsights tracing. It must not disable another owner's binding.

Use only existing workflow inputs. Managed `gpt-realtime` is independent of the
Copilot driver chat model. No shared SDK/environment upgrades, credential repair,
global login or new secrets. The workflow provides tooling; only the candidate's
locked Python dependencies are installed into a private venv.

## One execution

Run the following from the repository root in the authorized GitHub runner.
Do not pre-create `VOICE_RUN_DIR`: the helper must create the new directory.
Do not run offline tests here; those already ran in the workflow's isolated job.

```bash
set -euo pipefail
test "${GITHUB_ACTIONS:-}" = true
: "${RUNNER_TEMP:?}" "${FOUNDRY_PROJECT_ENDPOINT:?}" "${AZURE_AI_PROJECT_ID:?}"
: "${AZURE_AI_ENDPOINT:?}" "${AZURE_TENANT_ID:?}" "${AZURE_SUBSCRIPTION_ID:?}"
umask 077
export AZURE_CONFIG_DIR="${AZURE_CONFIG_DIR:-$HOME/.azure}"
export AZD_CONFIG_DIR="$RUNNER_TEMP/voice-azd"
export AZURE_TOKEN_CREDENTIALS=AzureCliCredential
export PYTHONDONTWRITEBYTECODE=1
python3 -m venv "$RUNNER_TEMP/voice-client"
"$RUNNER_TEMP/voice-client/bin/python" -m pip install --quiet \
  -r skills/foundry-voice-agents/requirements.txt \
  -c skills/foundry-voice-agents/constraints.txt
VOICE_RUN_DIR="$RUNNER_TEMP/voice-case-$(python3 -c 'import uuid; print(uuid.uuid4().hex)')"
VOICE_STATUS=0
"$RUNNER_TEMP/voice-client/bin/python" \
  skills/foundry-voice-agents/test-fixture/live_acceptance.py \
  --endpoint "$FOUNDRY_PROJECT_ENDPOINT" \
  --speech-endpoint "$AZURE_AI_ENDPOINT" \
  --account-id "${AZURE_AI_PROJECT_ID%/projects/*}" \
  --model gpt-realtime \
  --evidence-dir "$VOICE_RUN_DIR" \
  --public-evidence /tmp/foundry-voice-agents-smoke-evidence \
  --approve-live-synthetic || VOICE_STATUS=$?
if [ "$VOICE_STATUS" -eq 0 ]; then
  printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-voice-agents-smoke-result
else
  printf 'SMOKE_RESULT=FAIL canonical entry failed; preserve evidence\n' \
    > /tmp/foundry-voice-agents-smoke-result
fi
exit "$VOICE_STATUS"
```

The runner's Azure login profile is already job-private; the explicit default
cache path above is allowed **only** under `GITHUB_ACTIONS=true`. Local manual
runs must use the approved tenant-isolation bootstrap, not this fallback.

## Meaning of the result

The helper requires actual audio input/output, startup greeting, a real harmless
function call, active-audio interruption and a completed latest response.
Persistence requires actual caller/assistant transcript text and nonempty stereo
recording bytes. Role names or an audio URL alone do not pass readback. It keeps
content-free shape/length diagnostics if the transcript assertion fails.

The sanitized receipt at the workflow's existing evidence path records source
hashes, run custody, functional state and cleanup. It omits endpoint, conversation
IDs, audio and transcript values. Raw inventory remains private in `VOICE_RUN_DIR`;
do not print, edit or delete it. On failure, report the receipt and stop. If cleanup
is blocked, no replacement run or parent-resource deletion is permitted.

Automatic tracing is **not exercised**. A separate manual service-correlation
test passed, while its metadata-only attempt failed. The owner accepted only that
existing synthetic trace window's 30-day retention. This is not new trace-capture
consent or a metadata-only PASS. Do not query or regenerate those traces.
