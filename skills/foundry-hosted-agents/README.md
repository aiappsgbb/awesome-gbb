# foundry-hosted-agents

Deploy and manage Foundry hosted agents (container-built agents run on
Foundry-managed, per-session sandboxes — GA) via `azd` and the unified
`azure.yaml` — the FoundryChatClient bootstrap, identity (implicit
access by default), and blue-green/canary version rollout patterns.

The [private BASIC consumer](references/private-basic.md) adds credential-free
project ACR-connection validation, explicit source-build/prebuilt container
paths, and a native no-tools model/session readback oracle. A bounded private
run on **2026-09-17** passed native deployment, one model request, independent
response/session/version readbacks and verified native cleanup
([#500](https://github.com/aiappsgbb/awesome-gbb/pull/500)). Retained artifacts
have explicit bounded custody. This BASIC result is separate from public CI
and does not certify governed business effects.

Select the [versioned deployment profile](references/hosted-contract.json)
before generating or refreshing manifests. Newer tools are not implicitly
compatible; legacy two-file projects require a reviewed migration. The
[operation custody guide](references/operation-recovery.md) separates service
completion, business effect and client delivery, and forbids replay after an
uncertain outcome. Compare actual adopted helper/template hashes with
`references/python/hosted_contract.py`, not only skill version labels.

## Roadmap

**Planned for v0.7.0 — thread-retention reader
([#270](https://github.com/aiappsgbb/awesome-gbb/issues/270)).**
A read-only `audit()` method to enumerate a hosted agent's conversation threads
and report oldest-thread age against a declared retention window so a pilot can
prove data-lifecycle posture. Threadlight's `sibling-skills-map.md` names the
expected contract: `audit(subscription_id, resource_group, retention_days) -> dict`,
and maps the finding to **this skill** (not `foundry-memory`). This unblocks
threadlight finding **MDL-011**, which **must stay `kind: manual` until this method
ships** — the threadlight map currently lists MDL-011 without the `(planned)` tag,
but no such method exists here yet.

## See also

- [`SKILL.md`](SKILL.md) — the skill contract
- [#270](https://github.com/aiappsgbb/awesome-gbb/issues/270) — the deferred work
