# Additional Toolbox service acceptance

Acceptance cases; executed subsets are recorded in the scoped validation record.
The existing consumer fixture remains the SDK 2.4 / MAF baseline. These cases
do not authorize Azure work. Before execution record
an approved project, caller, cost bound, exact created-resource inventory,
cleanup authority and expiry in private run artifacts. Use unique UUID names.
Do not invoke Copilot recursively or change shared connections, roles or ingress.
Stop on a missing prerequisite; do not substitute public networking or identity.

| Case | Setup and action | Required evidence |
|---|---|---|
| A2A 1.0 | Existing authorized RemoteA2A peer, incoming protocol already enabled. In an isolated management environment create a Toolbox version using `service_tools.a2a_peer`. Invoke its discovered peer tool with a harmless task through the version-specific MCP endpoint. | Stored `a2a` / `a2a_version=1.0`, actual caller, non-error peer result and version endpoint. Agent-card retrieval or `tools/list` alone is insufficient. |
| Tool Search | Existing approved MCP source with at least two harmless tools. Use `searchable_mcp` with `ToolConfig(pin=True)` on one exact source key and `additional_search_text` on another. Keep `require_approval=always` and enforce it in the caller. | Meta-tools and explicit pin in initial discovery; keyword search finds the intended other tool; call its exact discovered name and verify content. Record auto-pinned hot-set/history if present; do not assume exactly two initial tools. |
| Promotion | Create two owned versions and inspect `default_version`; test the candidate endpoint before explicitly promoting. | Default endpoint serves the promoted version; rollback restores the earlier version; explicit version endpoint stays stable. |
| Private File Search | Approved private project/vector store and private runner; public access stays disabled. Retrieve a synthetic document through Toolbox File Search. | Correct content, endpoint/DNS/routing evidence for the actual path, caller identity and no public fallback. A public test does not count. |
| Prompt bridge | Separate approved preview case with an existing prompt-agent caller. | Actual Tool Search and tool execution via the bridge; no claim of GA integration, delegated passthrough or broad MAF upgrade. |

Import canonical helpers; do not paste replacement implementations into a
fixture. The new management requirements contain no MAF/hosting dependency.
Neither a serializer test nor a fixture on the old SDK certifies the new A2A
surface. Search visibility does not waive approval or OAuth consent.

For A2A, inventory returned task/context IDs as soon as invocation returns.
Foundry retains those service-managed records for 60 days from the latest
write; deleting the peer is not evidence of their erasure. Establish a supported
purge path or an explicit bounded-retention disposition before invoking.
`AGENT_NOT_FOUND` after peer removal does not prove `TASK_NOT_FOUND`.

After execution delete only resources recorded as created for the run and
verify their absence using supported read paths. Report functional results and
cleanup separately. Outside CI, unresolved cleanup requires an explicit bounded
owner retention handoff; do not report the test complete or create replacements.
