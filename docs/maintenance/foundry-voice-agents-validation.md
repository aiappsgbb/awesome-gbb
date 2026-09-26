# Managed Voice Agent candidate acceptance

Status: **unreleased candidate; functional voice and manual service correlation
PASS, metadata-only tracing FAIL; current-head CI reported in the PR**.
The capability is Foundry Agent Service public preview, not a change to the
existing Voice Live API contract. No waiver from another PR applies.

## Source and environment

Prepared from catalog baseline `2884c989d866bf663c4fd9f131697b7fe5004118`.
Standalone Projects 2.7.0 `[voice]`, Identity 1.25.3 and the exact candidate
constraints; local Python 3.12.13 on macOS. Existing runtimes and model deployments
were not upgraded. Linux results must come from the targeted current-head CI.

Tests use an existing approved project/model in Sweden Central, isolated
AzureCliCredential, managed `gpt-realtime`, Azure standard Ava output and
24-kHz mono PCM input/output. Input consists solely of three fixed fictional
test utterances synthesized through the existing Speech service. No microphone,
real customer content, outbound call, phone binding or network change was used.
The separate manual trace proof used one expressly authorized temporary
project-scoped AppInsights binding and component-scoped ingestion role, both
removed with authenticated absence verified. Resource names, endpoints and
conversation IDs remain private.

## Manual execution on 2026-09-25

| Surface | Result | Evidence boundary |
|---|---|---|
| Startup greeting | PASS | Actual streamed PCM before user input |
| Audio input/output | PASS | Synthetic WAV sent in timed chunks; nonempty spoken reply |
| Function tool | PASS | Actual `get_demo_hours({})` event, fictional result submitted after response completion |
| Interruption/redirect | PASS | Active response audio, subsequent speech onset, `cancelled/turn_detected`, stale buffered audio discarded, completed short hours answer |
| No-storage baseline | PASS | Explicit false on definition and connect; returned session conversation ID not retrievable as stored content |
| Authorized persistence | PASS | Separate true cycle, caller and assistant items, downloaded nonempty stereo WAV |
| Cleanup | PASS | Run-owned conversation, versions and agent names deleted and supported absence verified; all generated local WAVs removed |
| Real service trace | PASS | One actual service trace matched the inventoried agent/session/conversation and turn, VAD, model, tool and TTS spans; no client-generated substitute |
| Metadata-only tracing | FAIL | Service emitted nonempty message arrays and a tool-result object without a client content-capture toggle |
| Existing synthetic trace retention | OWNER-ACCEPTED | Explicit exception for the already-created test window only, under existing 30-day retention; not a metadata-only PASS or future capture consent |
| Browser/speaker hardware | NOT TESTED | Buffered synthetic client does not certify microphone, speaker-queue flush, echo or WebRTC |
| BYOM/BYO storage/simulation/azd provisioning | NOT TESTED | Outside this managed existing-project test |
| Automated Voice consumer | See current-head PR checks | Functional/privacy-preflight/cleanup coverage only; no automated tracing claim |

The successful corrected cycle used three sessions and three function calls.
The service reported 2,787 total tokens across its response usage records;
this is observed usage, not a user spending cap or a billing reconciliation.
Client VAD-event-receipt to first-audio-receipt measurements were approximately
0.29-0.82 seconds. These are not service TTFA, production percentiles or a
pronunciation/prosody/audio-quality score.

An earlier cycle passed the first audio/tool turn but failed its interruption
setup before answer audio. The multi-sentence test utterance produced a second
VAD onset. Cleanup completed. The corrected fixture uses a single-sentence
long-answer request and retains the strict active-audio interruption criterion;
no failed result was relabeled as PASS.

## Observed tracing privacy boundary

On 2026-09-25, a shape-only diagnostic for the single owned trace found seven
nonempty output-message attribute occurrences, four input-message occurrences
and one tool-result occurrence. One tool-argument attribute was an empty object.
These are **attribute-row occurrences, not unique spans**. Only field categories,
types, counts and lengths were exported; no payload values or examples were read
back into the evidence. The trace identity/correlation proof remains valid, but
the attempted metadata-only behavior failed.

The operator stopped further capture and removed the exact temporary binding
and ingestion role. The owner explicitly accepted retention of **those existing
synthetic traces only** for the configured 30 days. Connection deletion is not
telemetry erasure, and acceptance of retention does not approve another capture,
retroactively make the attempt metadata-only, or change shared retention/access.
No purge, redaction experiment, API-key fallback or content-toggle workaround
was attempted.

**Do not assume that a client content-capture default or `store=False` prevents
server-side trace content.** Before enabling managed Voice tracing, obtain
informed consent for potential conversational/tool content and its actual
destination, access and retention. This candidate ships no working metadata-only
server-tracing recipe.

## Automated coverage and remaining gates

The initial Voice consumer failed stored transcript content checks, then the
executor edited the checked-in assertion and discarded private inventories.
The existing checkout-integrity guard correctly rejected the run. No modified
assertion or claimed PASS from that run is accepted. A subsequent authenticated
listing found no remaining Voice-prefixed agents in the approved project, but
the missing inventories prevent independent reconstruction of every stored
conversation's deletion; this is not proof of storage purge.

The owner explicitly accepted that old CI run's evidence gap; cleanup remains
UNKNOWN, without an invented purge date or replay to replace missing evidence.

## Corrected controlled validation on 2026-09-26

The earlier one-attempt manual run failed immediately after `session.created`,
but its collector hid the error classification. That negative result remains.
The diagnostic correction now retains allowlisted error type/code/parameter and
event/request identifiers without free-form messages or payloads.

A new controlled discriminator reported `invalid_request_error` against
`session.turn_detection` for the combination of explicit `azure-speech`
transcription and `server_vad`. Switching only turn detection to the documented
Azure semantic VAD with `en-US` resolved startup. The next stored-conversation
test passed every meaningful text check: caller text about hours, assistant text
containing the fictional opening/closing hours, a real function result and
nonempty 24-kHz stereo PCM. This proves the corrected combination works; it does
not prove a general service limitation for other VAD/model configurations.

The full canonical corrected fixture then passed three sessions covering the
non-persisted hours turn, active-audio barge-in and a separately persisted hours
turn. Stored readback contained 42 caller-text characters, a 61-character final
assistant transcript and 246,192 stereo audio frames. Text content was checked
in memory; only shapes/lengths/hashes were recorded. Both agents, their versions,
the stored conversation and all local WAVs were removed with authenticated
absence verified. No tracing connection, role or exporter was created.

Source hashes were captured before each run. The fixture now fsyncs returned
session/conversation/event identifiers before assertions, rejects a dirty
checkout or duplicate CI execution, retains the real text assertion and writes a
sanitized custody receipt to the existing artifact path. Direct manual success
is not a substitute for the current-head Linux/agent-driven checks in the PR.

The automated fixture covers the approved synthetic greeting/audio/function/
interruption and separately stored transcript/stereo-audio readback and deletion.
It checks that no AppInsights binding is configured at the project or inherited
account scope before invocation and refuses to run if one appears. It creates
no binding or role, reads no telemetry workspace, and does not certify tracing.
The manual correlation and privacy deviation above are separate evidence,
not an automatic fixture PASS. A newly configured shared binding requires a
new decision; the fixture must not disable or overwrite another owner's setup.

Before every push and merge request, the canonical selector must run on the
actual committed diff against freshly fetched main. Both PR and anticipated
push-main selection must remain Voice-only or narrowly justified. No full
catalog dispatch, unrelated CI rewrite, check bypass or historical-PASS reuse.
Required checks remain `gate`, `validate-pins`, `validate`, and `smoke-result`.
