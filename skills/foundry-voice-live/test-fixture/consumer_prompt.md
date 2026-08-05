# Customer goal — `foundry-voice-live` self-contained execution smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-voice-live` skill
works end-to-end against your CI Foundry resource using the native
`azure-ai-voicelive` Python SDK (Rung 4 of the skill's migration ladder).

This fixture is self-contained. Do NOT open/read the whole skill file, do
NOT inspect unrelated repository files, and do NOT improvise from
training-data knowledge of the Azure SDK. The first required Bash action is
the lightweight audit acknowledgement below; after that, execute the steps in
this prompt directly.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You ARE
the running Copilot CLI process. Do NOT run any `copilot ...` command from
inside a Bash tool call, and do NOT install or probe Copilot CLI. The workflow
already captures your output; your job is to execute these steps directly.

---

## Step -1 — Acknowledge skill contract (first required Bash action)

```bash
echo "skills/foundry-voice-live/SKILL.md"
```

Do not perform broad repository inspection. Do not hunt for tooling. Python,
`az`, and the workflow-provided environment are already present.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on any of these
checks — `azure/login@v2` already validated the credentials upstream and
`DefaultAzureCredential` will be the authoritative gate in Step 3.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "AZURE_AI_ENDPOINT=${AZURE_AI_ENDPOINT:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If any of the four env vars prints empty (no `set` suffix), the workflow's
`env:` block is broken (AGENTS.md § 9.7 Pattern 11). That is a workflow bug,
not a skill bug. Write the FAIL marker (Step 4) with reason
`auth context missing: <var-name>` and stop.

---

## Step 1 — The goal

Open a Voice Live WSS session against the CI Foundry resource using the
native `azure-ai-voicelive` SDK with `DefaultAzureCredential` (scope
`https://ai.azure.com/.default` — handled by the SDK). Send one short
text turn (a `session.update` configuring text modality + a single user
message + a `response.create`). Receive `session.created`, then require
the terminal `response.done` event and require its final
`response.status` to be exactly `completed`. Close the session cleanly.

The deployment to use is `gpt-realtime` (GA in Voice Live, NOT preview)
on the CI Foundry resource. It is already provisioned in
`aif-awesome-gbb-ci` (region `swedencentral`, GlobalStandard, capacity 5,
version `2025-08-28`). SDK 1.3 now defaults 2026-07-15, so this fixture
passes `api_version="2026-04-10"` explicitly to preserve the live-proven
GA path.

The Voice Live WSS endpoint lives on the `services.ai.azure.com` DNS
surface, NOT on `cognitiveservices.azure.com`. Both names point at the
same Foundry resource — Voice Live just exposes its WSS handler under the
former. The fixture's Python script (Step 3) derives the right host from
`AZURE_AI_ENDPOINT` by swapping the DNS suffix:
`https://<resource>.cognitiveservices.azure.com/` →
`https://<resource>.services.ai.azure.com/`.

There are no Azure resources to create or tear down — the WSS session
auto-closes when the Python `async with` block exits, and no
persistent Foundry artefacts are touched (AGENTS.md § 9.7 Pattern 25 —
teardown N/A for this fixture).

Do NOT branch on "if `az` has a voice-live CLI extension, use it;
otherwise SDK" (AGENTS.md § 9.7 Pattern 16). There is no GA `az` surface
for Voice Live — use the Python SDK only.

---

## Step 2 — Install the SDK

Voice Live needs only Python packages — no OS-level CLI install, so this
runs inside the fixture (AGENTS.md § 9.7 Pattern 15 only kicks in for
binaries like `azd` / `func` / `kubectl`).

```bash
python3 -m pip install --quiet \
  "azure-ai-voicelive[aiohttp]~=1.3.0" \
  "azure-identity~=1.25.3"
```

The `[aiohttp]` extra is REQUIRED for the async `connect()` path — without
it the SDK raises `ImportError: aiohttp is required for azure-ai-voicelive` (see
SKILL.md § 11 "Troubleshooting" for the corresponding row).

---

## Step 3 — Open the WSS session

Run the Python script below. It MUST complete without exception, print
`voice-live-roundtrip-ok` on success, persist the successful runtime audit
records to `/tmp/foundry-voice-live-smoke-evidence`, and exit 0. The
workflow uploads the evidence file; it is the authoritative audit trail for
the runtime connect record, session-created record, and completed terminal
record when the Copilot CLI transcript collapses long shell output.

**Do NOT redirect the script's stdout anywhere.** The workflow harness
already captures all output via its own `tee` pipeline (so the
post-hoc skill-usage audit can see what tools you invoked). Any
shell redirect — `> /tmp/...`, `>>`, `tee`, `rm` of a `/tmp/*log`
file, or wrapping the heredoc in a sub-harness that mimics the
workflow's `MARKER=…; TRANSCRIPT=…; rm -f; python3 … > "$TRANSCRIPT"`
pattern — clobbers the workflow's audit transcript and fails the
post-hoc step even when the WSS roundtrip succeeded. The Python script's
sanctioned evidence-file write is the only `/tmp` write in this step. Just
invoke `python3 <<'PY' … PY` and let the runtime print to stdout normally.

```bash
python3 <<'PY'
import asyncio, os, sys
from pathlib import Path
from urllib.parse import urlparse

from azure.identity.aio import DefaultAzureCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    AzureSemanticVad,
    InputTextContentPart,
    Modality,
    RequestSession,
    ServerEventType,
    UserMessageItem,
)

EVIDENCE_PATH = Path('/tmp/foundry-voice-live-smoke-evidence')
EVIDENCE_PATH.write_text('', encoding='utf-8')

def record(message: str) -> None:
    with EVIDENCE_PATH.open("a", encoding="utf-8") as evidence:
        evidence.write(message + "\n")
    print(message)

# Derive the Voice Live WSS host from AZURE_AI_ENDPOINT (the
# cognitiveservices.azure.com surface). Voice Live lives on
# services.ai.azure.com — same resource, different DNS handler.
raw = os.environ["AZURE_AI_ENDPOINT"]
host = urlparse(raw).hostname or ""
resource = host.split(".")[0]
if not resource:
    print(f"FAIL: cannot derive resource from AZURE_AI_ENDPOINT={raw!r}", file=sys.stderr)
    sys.exit(1)
voicelive_endpoint = f"https://{resource}.services.ai.azure.com/"
print(f"voicelive endpoint: {voicelive_endpoint}")

def enum_value(value):
    if value is None:
        return None
    return getattr(value, "value", value)


def event_type(event):
    return enum_value(getattr(event, "type", None))


def response_status(event):
    response = getattr(event, "response", None)
    return enum_value(getattr(response, "status", None))


async def await_completed_response(conn, timeout_seconds=60.0):
    saw_session_created = False
    session_created_type = enum_value(ServerEventType.SESSION_CREATED)
    response_done_type = enum_value(ServerEventType.RESPONSE_DONE)
    error_type = enum_value(ServerEventType.ERROR)

    try:
        async with asyncio.timeout(timeout_seconds):
            async for event in conn:
                etype = event_type(event)
                print(f"event: {etype}")

                if etype == error_type:
                    error = getattr(event, "error", str(event))
                    raise RuntimeError(f"server error event: {error}")

                if etype == session_created_type:
                    if not saw_session_created:
                        record("VOICELIVE_EVENT type=session.created")
                    saw_session_created = True
                    continue

                if etype == response_done_type:
                    if not saw_session_created:
                        raise RuntimeError("response.done received before session.created")
                    status = response_status(event)
                    status_label = "None" if status is None else str(status)
                    if status_label != "completed":
                        raise RuntimeError(
                            f"response.done status={status_label} is not completed"
                        )
                    record("VOICELIVE_TERMINAL type=response.done status=completed")
                    return status_label
    except asyncio.TimeoutError as exc:
        raise RuntimeError(
            f"timeout waiting for response.done after {timeout_seconds:g}s"
        ) from exc

    if not saw_session_created:
        raise RuntimeError("stream ended before session.created")
    raise RuntimeError("stream ended before response.done")

async def main() -> None:
    async with DefaultAzureCredential() as cred:
        # SDK 1.3 defaults 2026-07-15; the fixture preserves the live-proven 2026-04-10 API.
        async with connect(
            endpoint=voicelive_endpoint,
            credential=cred,
            api_version="2026-04-10",
            model="gpt-realtime",
        ) as conn:
            record("VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3")
            # session.update — text modality + GA AzureSemanticVad with
            # the 2026-04-10 fields (create_response / auto_truncate).
            await conn.session.update(session=RequestSession(
                modalities=[Modality.TEXT],
                instructions="You are a brief assistant. Reply in <=10 words.",
                turn_detection=AzureSemanticVad(
                    create_response=True,
                    auto_truncate=True,
                ),
            ))
            # One short text turn → response.create.
            await conn.conversation.item.create(item=UserMessageItem(
                content=[InputTextContentPart(text="say hi")],
            ))
            await conn.response.create()

            # Voice Live emits response.done for every completed response
            # attempt, regardless of final state. Only status=completed is
            # success for this smoke.
            await await_completed_response(conn, timeout_seconds=60.0)

    print("voice-live-roundtrip-ok")

asyncio.run(main())
PY
```

Success criteria for Step 3:

- Process exits 0.
- Stdout contains the literal string `voice-live-roundtrip-ok`.
- The evidence file contains exactly the successful runtime audit records:
  one connect record, one session-created record, and one terminal completed
  record.
- The terminal event was `response.done` and its final
  `response.status` was exactly `completed`.

If the script raises `ClientAuthenticationError` or any HTTP
`401`/`403` from the WSS handshake, the CI UAMI is missing a role
grant for Voice Live. Write the FAIL marker with reason
`voice-live-auth: <error class>` and stop — this is an infrastructure
issue, not a fixture bug.

---

## Step 4 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after Step 3 — is to invoke the Bash tool to write
the marker file. The file's literal byte content is what CI grades; your
assistant-text reply is NOT graded. The marker token below is rendered
with a leading underscore (`_MOKE_RESULT`) in this prose so it can never
match the workflow's anchored grep — substitute the leading `_` back to
`S` when you emit the actual `printf` command.

On success (Step 3's script exited 0 AND its stdout contained
`voice-live-roundtrip-ok` AND the evidence file contains exactly three
runtime records: connect, session-created, and terminal completed):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-voice-live-smoke-result
```

On ANY failure (auth context missing in Step 0, `pip install` failure
in Step 2, Python exception, `_MOKE_RESULT=FAIL` condition in Step 3,
HTTP 401/403 from the WSS handshake, timeout before terminal
`response.done`, stream ending before `response.done`, non-`completed`
terminal status, or explicit server-side `error` event):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-voice-live-smoke-result
```

The marker file is single-source-of-truth. Do NOT print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal `_MOKE_RESULT=PASS` or
`_MOKE_RESULT=FAIL` string outside the two `printf` commands above. The
Bash tool write is the only legitimate emission path.
