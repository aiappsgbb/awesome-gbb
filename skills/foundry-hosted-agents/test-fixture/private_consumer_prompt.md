# Opt-in private Hosted BASIC execution fixture

Run the exact no-tools container contract in
`skills/foundry-hosted-agents/references/private-basic.md`, sections 1-4, using
`private_bootstrap.py`, `deploy_preflight.py` and `hosted_smoke.py` as real
modules/scripts, never inline reimplementations.

This is not the public `consumer_prompt.md` CI leg. It requires the existing
private environment's designated executor and current bounded owner approval.
Do not invoke `copilot` recursively, install/upgrade global tools, sync user
skills, create replacement resources, grant roles, change networking, delete
connections, mutate shared Docker/Keychain configuration, or perform cleanup.
No additional session/agent is authorized to become a cloud writer.

Before execution the owner supplies candidate SHA, exact private project/
registry/model/subnet/tenant, paired isolated CLI caches, operator route,
fresh setup JSON (including actual native connection mapping provenance),
the approved build choice and image/base provenance, unique agent name, and
an unexpired approval covering one deploy and one plain model invocation.
No raw private inventory, credentials, signed URLs or logs belong in GitHub.

1. Read the pinned contract and preserve all prior evidence. Check the selected
   source file hashes and installed azd/extension versions. Do not silently
   choose the official sample's preview code route.
2. Inspect the real connection without credentials. Correct: reuse. Missing:
   stop for separately approved native connection-only provisioning; do not
   remove anything to reproduce absence. Mismatched/unreadable: precise blocker.
3. Stage the no-tools runtime and explicit container configuration. For source
   builds, retain the lock, immutable base references and allowlisted upload
   context; native package/publish must use a private-network-reachable builder.
   Resolve the published image and switch to the exact prebuilt passthrough
   path for one registration. For an approved prebuilt path verify the exact
   no-tools artifact, not historical v7 or a same-tag approximation.
4. Collect real prerequisite evidence and run the setup gate without fabricated
   receipts. Preserve private account/ACR and keyless/admin-disabled settings.
   Verify paired tenant isolation and shell/azd target equality before the
   authorized one-shot deploy.
5. Run `hosted_smoke.py --execute` with the actual returned version and a NEW
   private evidence file. Never skip native GET/model/response/session checks.
   Preserve failure output and return the exact failed stage. No blind retry,
   new image, changed identity or public fallback to obtain PASS.
6. Refresh account/ACR settings through ordinary GETs and compare the selected
   stable fields to the pre-run values. Retain before/after evidence. Report
   private BASIC model proof separately from governed tools/business execution.
7. Only if steps 1-6 succeed and approval is still valid, use a Bash tool to write
   `printf 'SMOKE_RESULT=PASS\n' > "$PRIVATE_BASIC_MARKER"` at the owner's NEW,
   attempt-specific private marker path. On failure write a single
   `SMOKE_RESULT=FAIL <stage/reason>` line there instead. Do not overwrite an
   earlier run's marker or put prose/raw logs in it.

The registered public fixture remains unchanged in purpose. This private
fixture is not automatically enrolled against public CI resources; it supplies
the reproducible manual live evidence required by AGENTS.md section 2.9.
