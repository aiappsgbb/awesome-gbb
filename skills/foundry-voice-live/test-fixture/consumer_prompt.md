# Customer goal — `foundry-voice-live` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-voice-live` skill
works end-to-end against your CI Foundry resource using the native
`azure-ai-voicelive` Python SDK (Rung 4 of the skill's migration ladder).

Do whatever the skill tells you to do. Do NOT improvise from training-data
knowledge of the Azure SDK — read the skill's `SKILL.md` first (in
particular § 1 "Four Rungs", § 2 "Rung 4 — native `azure-ai-voicelive` SDK",
and § 12 "2026-04-10 GA Deltas") and follow its documented contract.

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
message + a `response.create`). Receive at least one server event back
from the family `session.created` / `session.updated` /
`conversation.item.created` / `response.created` /
`response.audio_transcript.delta` / `response.text.delta` /
`response.done`. Close the session cleanly.

The deployment to use is `gpt-realtime` (GA in Voice Live, NOT preview)
on the CI Foundry resource. It is already provisioned in
`aif-awesome-gbb-ci` (region `swedencentral`, GlobalStandard, capacity 5,
version `2025-08-28`). The API version is `2026-04-10` (the SDK default —
do not override).

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

The skill's `SKILL.md` is the source of truth for which SDK to use, how
to authenticate, the endpoint hostname convention, the `connect()` kwargs,
and how to build session/conversation/response items. Read it before you
write any code. If the skill's instructions conflict with anything you
remember from training data, the skill wins.

Do NOT branch on "if `az` has a voice-live CLI extension, use it;
otherwise SDK" (AGENTS.md § 9.7 Pattern 16). There is no GA `az` surface
for Voice Live — use the Python SDK only.

---

## Step 2 — Install the SDK

Voice Live needs only Python packages — no OS-level CLI install, so this
runs inside the fixture (AGENTS.md § 9.7 Pattern 15 only kicks in for
binaries like `azd` / `func` / `kubectl`).

```bash
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet \
  "azure-ai-voicelive[aiohttp]~=1.2.0" \
  "azure-identity~=1.24.0"
```

The `[aiohttp]` extra is REQUIRED for the async `connect()` path — without
it the SDK raises `ImportError: aiohttp transport is required` (see
SKILL.md § 11 "Troubleshooting" for the corresponding row).

---

## Step 3 — Open the WSS session

Run the Python script below. It MUST complete without exception, print
`voice-live-roundtrip-ok` on success, and exit 0. The script's stdout
is captured into the transcript for audit.

```bash
python3 <<'PY'
import asyncio, os, sys
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

ACCEPT = {
    ServerEventType.SESSION_CREATED,
    ServerEventType.SESSION_UPDATED,
    ServerEventType.CONVERSATION_ITEM_CREATED,
    ServerEventType.RESPONSE_CREATED,
    ServerEventType.RESPONSE_TEXT_DELTA,
    ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA,
    ServerEventType.RESPONSE_DONE,
}

async def main() -> None:
    saw_event = False
    saw_terminal = False
    saw_error = None
    async with DefaultAzureCredential() as cred:
        # SDK defaults: api_version="2026-04-10",
        # credential_scopes=["https://ai.azure.com/.default"].
        async with connect(
            endpoint=voicelive_endpoint,
            credential=cred,
            model="gpt-realtime",
        ) as conn:
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

            # Wait up to 60 s for any accepted server event (Voice Live
            # response generation is typically 5-15 s — 60 s leaves
            # headroom for cold-start jitter without flaking).
            try:
                async with asyncio.timeout(60.0):
                    async for event in conn:
                        etype = getattr(event, "type", None)
                        print(f"event: {etype}")
                        if etype == ServerEventType.ERROR:
                            saw_error = getattr(event, "error", str(event))
                            break
                        if etype in ACCEPT:
                            saw_event = True
                        if etype == ServerEventType.RESPONSE_DONE:
                            saw_terminal = True
                            break
            except asyncio.TimeoutError:
                print("event loop hit 60 s timeout")

    if saw_error is not None:
        print(f"FAIL: server error event: {saw_error}", file=sys.stderr)
        sys.exit(1)
    if not saw_event:
        print("FAIL: no accepted server event received", file=sys.stderr)
        sys.exit(1)
    print(f"saw_terminal={saw_terminal}")
    print("voice-live-roundtrip-ok")

asyncio.run(main())
PY
```

Success criteria for Step 3:

- Process exits 0.
- Stdout contains the literal string `voice-live-roundtrip-ok`.
- At least one event of type `session.created` / `session.updated` /
  `conversation.item.created` / `response.created` /
  `response.text.delta` / `response.audio_transcript.delta` /
  `response.done` was printed.

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
`voice-live-roundtrip-ok`):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-voice-live-smoke-result
```

On ANY failure (auth context missing in Step 0, `pip install` failure
in Step 2, Python exception, `_MOKE_RESULT=FAIL` condition in Step 3,
HTTP 401/403 from the WSS handshake, no accepted server event received,
explicit server-side `error` event):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-voice-live-smoke-result
```

The marker file is single-source-of-truth. Do NOT print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal `SMOKE_RESULT=PASS` or
`SMOKE_RESULT=FAIL` string outside the two `printf` commands above. The
Bash tool write is the only legitimate emission path.
