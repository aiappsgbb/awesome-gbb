# Skills consumer and network acceptance

Separately authorized cases; executed subsets are recorded in the scoped
validation record. Before creating resources agree on
the exact project, caller, cost, owner, cleanup authority and expiry. Use
UUID-suffixed test skill/Toolbox names and private run inventory. No recursive
Copilot calls, shared-resource changes or new role grants within the fixture.

| Surface | Required check |
|---|---|
| MCP Resources | Create a Toolbox version referencing an owned skill and exact version. From the version-specific MCP endpoint call `resources/list`, follow the returned URI with `resources/read`, verify body and supplementary asset bytes. `tools/list` is not a substitute; do not invent resource URI formats. |
| Two-level pinning | Pin both Toolbox and skill version, then change the skill default. Verify pinned content remains stable. Separately verify a floating skill reference changes only when the consumer intentionally reloads. |
| Progressive provider | Use a provider whose resource support is explicitly documented for its exact framework/version. Capture initial names/descriptions, on-demand selected-body read and later asset read. Prove unrelated bodies are not fetched. A predownload/injection path is not PASS for this case. |
| Agent behavior | Invoke the intended consumer on benign fixtures requiring the selected skill and assert its observable instructions were followed. API CRUD success alone says nothing about that behavior. |
| Private catalog | On an approved private runner with public access disabled, execute the native version fixture against the intended private project. Retain DNS/routing and successful version/content evidence. |
| Private Toolbox | Repeat resource discovery, body/asset reads and intended consumer invocation through the private Toolbox endpoint; separately inspect networking for any downstream tools referenced by the skill. |

Do not upgrade the existing Python MAF/hosting pins to reproduce a C# provider
sample or enable SDK 2.7 Prompt fields merely because their schema exists.
Missing runtime support is a gated decision, not permission for an adapter
rewrite. Keep preview opt-in, consent and approval boundaries intact.

After execution remove only owned Toolbox references/versions before deleting
the test skill. Verify each deletion via its supported read path. Outside CI,
any blocked cleanup needs an explicit bounded retention handoff; retain the
exact residual inventory privately and do not create replacement resources.
