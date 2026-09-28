# Foundry Memory retirement

Catalog 5.0.0 removes the GBB `foundry-memory` skill. Use Microsoft's
[`microsoft-foundry`](https://github.com/microsoft/azure-skills/tree/main/.github/plugins/azure-skills/skills/microsoft-foundry)
skill, then its
[Memory workflow](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/create/references/tools/prompt-agent/tool-memory.md)
and the linked
[current Memory documentation](https://learn.microsoft.com/azure/foundry/agents/how-to/memory-usage).

There is **no separate official `foundry-memory` entrypoint** in the reviewed
Azure Skills distribution. Invoke `microsoft-foundry` explicitly for Memory;
do not install a renamed copy of its nested Markdown reference as a standalone
skill. Its prerequisites, references and parent workflow would be lost.

## What changes

- The duplicate GBB instructions, upstream pin and CI fixture are removed.
- Prompt/hosted guidance points to the official Memory workflow.
- The old catalog website URL remains a retirement notice.
- Existing Azure memory stores, scopes, retention, identities, application
  dependencies and Threadlight deployment contracts are unchanged.
- Other GBB specialists remain preferred for their existing responsibilities.
  Installing the official skill for Memory is not a general routing cutover.

## Local installation

First inspect `copilot skill list --json`. If `microsoft-foundry` is already
present, inspect its actual directory and confirm the Memory reference exists.
An older installation can contain the parent skill without the current nested
Memory workflow.

Install or refresh **only the complete `microsoft-foundry` directory** from
`.github/plugins/azure-skills/skills/` in the official repository. Use an
explicitly reviewed commit, preserve all child references/scripts and the
upstream license, and record the source revision locally. The source reviewed
for this retirement is
[`117b038edfef5d7af09848b8ffcd355f28f19956`](https://github.com/microsoft/azure-skills/tree/117b038edfef5d7af09848b8ffcd355f28f19956).
Do not copy only `SKILL.md`: `copilot skill add <file-or-url>` installs that
single file, not its companion tree.

Back up the existing skill outside all discovery roots before replacing it.
Use one personal location (`~/.agents/skills/microsoft-foundry/` or
`~/.copilot/skills/microsoft-foundry/`), not duplicate active copies.
Do not install the full Azure plugin merely for this replacement: that can
introduce unrelated skills, MCP servers or hooks. Preserve existing MCP
allowlists, excluded tools, authentication configuration and SDK environments.
Installing instructions does not require running their dependency installers.

Disable any remaining GBB plugin copy by its skill name:

```bash
copilot skill disable foundry-memory
copilot skill enable microsoft-foundry
copilot skill list --json
```

These commands affect future sessions. Verify that the official skill is
enabled, the old skill is absent or disabled, and its Memory reference and
linked documentation are available. An already running session can retain
old instructions; begin a new session to use the refreshed source.
Updating the GBB plugin to a revision containing this retirement removes its
old bundled copy, but a full plugin update may also update other skills.

For rollback before adoption, restore only the saved official directory and
re-enable the retained GBB skill if it is still installed. Do not reset the
whole plugin, global configuration or credential stores.

## Evidence boundary

The retirement is based on a source comparison: the official workflow and its
linked documentation cover the valid Memory capabilities while correcting
stale GBB instructions on item deletion, procedural defaults and Python TTL
types. Local discovery and package integrity establish installation, not a
live Memory API result. No new Azure execution, data migration or whole-agent
reliability certification is implied by this change.
