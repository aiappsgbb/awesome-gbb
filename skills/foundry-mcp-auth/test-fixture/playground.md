# Interactive delegated acceptance - Gate B required

Do not execute without the approved resource/Entra/connection allow-list.
No automatic consent, token copying, browser storage/devtools extraction,
shared user credential, frontend, jobs or Graph data.

1. Use isolated Azure CLI/AZD profiles and the explicit approved subscription.
   Confirm the private runtime paths, browser access and Entra/consent egress.
   Record source SHA, package versions, deployed image digest, agent versions,
   Toolbox version and connection binding. Keep real inventory private.
2. Configure the custom OAuth connection per the canonical contract. Verify
   create/read separately from runtime. Register the exact portal-provided
   redirect URI on the separate OAuth client. Never replace unrelated redirects.
3. Sign into Foundry Playground as user A, open the Prompt direct-MCP agent,
   ask `Call who_am_i, then list_my_demo_items`. Initially deny consent: no data
   may be returned. Repeat, consent explicitly and resume. Match the tool
   receipt to server-side evidence; agent prose is not identity evidence.
4. Repeat through the Hosted Toolbox agent using Responses 2.0.0 and the pinned
   Toolbox version. Prove the server receives a delegated token for its API,
   not the runtime/developer principal. Do not reveal opaque call IDs or tokens.
5. In an independent browser profile sign in as user B. Exercise first consent
   AFTER A has initialized the shared Hosted runtime. Alternate and overlap
   requests. Each user must receive only their own synthetic items/subject.
   If late consent fails, record NOT DEMONSTRATED/FAIL; do not restart per user,
   pre-consent everyone, bypass the shared runtime, or add a speculative adapter.
6. Exercise valid access-token renewal, revoked/expired refresh credentials,
   reauthorization and denial after revocation. Respect token lifetime; revocation
   is not necessarily instantaneous. Record any unsupported late-consent case.
7. Exercise Prompt -> Toolbox -> MCP using the native first-party bridge
   (not the static-token sample). Exercise Hosted -> direct MCP independently;
   do not substitute the Toolbox path and label it direct. Consult the
   [validation notes](../../../docs/maintenance/foundry-mcp-auth-validation.md)
   before running any currently unresolved path.
8. Attempt anonymous/app-only/insufficient-scope access using properly issued
   test credentials through supported flows, never copied portal tokens. No
   app-only principal may masquerade as the user. Invalid-signature/issuer/
   audience/lifetime local tests remain labeled local unless also reproduced live.
9. Correlate receipts and per-phase statuses; sanitize evidence against the
   candidate SHA. One real user proves only the initial demonstration. Two
   independent users are required for the isolation gate. Unavailable users
   or unsupported paths are BLOCKED, not skipped-to-PASS.

Literal OBO is a separate optional Gate-B delta: tiny API B with a distinct
audience, MSAL exchange in API A, both audiences and user continuity proven.
Native passthrough by itself does not prove that exchange. Wave 2 is not
authorized by this protocol.
