# foundry-hosted-agents

Deploy and manage Foundry hosted agents (container-built agents run on
Foundry-managed, per-session sandboxes — GA) via `azd` and the unified
`azure.yaml` — the FoundryChatClient bootstrap, identity (implicit
access by default), and blue-green/canary version rollout patterns.

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
