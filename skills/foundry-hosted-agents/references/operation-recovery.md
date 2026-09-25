# Response, effect and evidence custody

The versioned [hosted contract](hosted-contract.json) owns deployment selection.
This guide owns recovery semantics, not orchestration or permission to replay.
Use the existing application's durable storage, or a private journal for a
bounded demo; do not provision a new database merely to follow this guide.

## Record before interpretation

| Fact | Evidence | Not equivalent to |
|---|---|---|
| Intent | Client correlation, hash of frozen input/target, caller and approval | A service ID or idempotency guarantee |
| Dispatch | Observed transport request or accepted operation | Completed execution |
| Native operation | Original response/operation ID, status, request ID, session/version when emitted | Locally generated correlation |
| Response completion | Service terminal status and usable response | The requested business effect |
| Effect/readback | Actual reader identity, exact object/version, consistency guarantee, independent correlation | Assistant prose, health, a generic404 |
| Client completion | Browser assertion, message/file delivery | Server execution or its rollback |

`operation_evidence.py` provides small projection/capture functions. Supply a
durable record callback; a storage failure before dispatch must prevent send.
Retain returned identity/status **before** application parsing. The private
hosted CLI additionally captures the HTTP body in a separate owner-private file
before SDK parsing. A custom adapter that cannot intercept before SDK parsing
must retain available SDK error/request metadata and explicitly keep UNKNOWN.
Do not claim the missing response never existed.

Raw captures may contain user content or signed operation URLs: keep them
outside source control with owner-only access and an approved retention period.
Sanitized receipts contain only approved metadata/hashes. Record which sanitized
files actually appear in the commit; a local artifact is not a published one.
Never regenerate an effect to replace a missing transcript.

## Recovery decisions

| Classification | Next permitted action |
|---|---|
| `LOCAL_PREFLIGHT_REJECTION` | Correct the local decision/input. Zero dispatch must be observed, not inferred from an exception. |
| `UNSUPPORTED_CAPABILITY` | Return the missing capability/owner decision before dependent build/deploy. No broad-role or public-network fallback. |
| `PENDING_OPERATION` | Read the same service-issued operation using its supported API and finite deadline. Do not start another. |
| `COMPLETED_RESPONSE` | Preserve the response; independently verify any requested effect. |
| `VERIFIED_EFFECT` | Report effect evidence and separately finish client delivery. A failed browser assertion does not undo it. |
| `UNCERTAIN_EFFECT` | Reconcile the original ID/target. No replay, reset, restart or new idempotency key merely because the client timed out. |

Missing ID, generic404, readback403, parse failure, lost create ACK, cancellation
of a local stream, and an exhausted diagnostic window are not absence proofs.
For eventual-consistency reads, declare the reader, auth scope and expected
visibility window; an empty list after that window is still not a service
guarantee of non-execution. Read-only retries must remain bounded and retain the
original binding. A retry of a mutation requires proven non-dispatch or the
destination's documented deduplication/fencing contract, not a client flag.

For capability-host DELETE, retain its API-specific final-state contract:
the documented original-resource read can prove deletion under that operation's
auth/context. Do not generalize this rule to response retrieval or unknown writes.

## Desired versus loaded

Keep these identifiers distinct:

1. Local image configuration ID from image inspection.
2. Registry index digest, platform manifest digest, and config/layer descriptors.
3. The deployed image reference, agent version and actual runtime identity.
4. The route/session that served the response and a safe loaded-config discriminator.

A management PATCH ACK, an `active` version, a tag, or the local image ID alone
does not bind all four. Preserve the existing manifest-byte verification and
independent session/version readbacks. For a runtime flag, use an approved
non-secret startup/config fingerprint or a benign capability probe from the
actual serving path. If that discriminator is unavailable, report `NOT_PROVEN`;
do not infer a root cause from a later restart failure.

## Bounded diagnosis

Give every HTTP request, subprocess and poll a finite I/O timeout and give the
diagnostic question an explicit deadline. A count of sleeps does not bound an
SDK request with an unlimited read. Preserve the stage and available
status/request/error IDs when the deadline expires; remote effects stay UNKNOWN.
Do not conflate model/registry/control-plane/diagnostic-tool failures.

After two attempts at the same hypothesis without new evidence, change the
discriminator or return the specific decision. Healthy operations with observed
advancement are not failures. A stalled diagnostic tool is not proof the platform
failed and must not indefinitely block unrelated authorized work.
