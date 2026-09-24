# Setup doctor runbook

## Boundaries and evidence

Default scope: known files only, local reads, zero runtime launches. The collector
reads the JSONC application-state file to project `installedPlugins`; it never
reports authentication fields or reads credential stores. The script never
modifies input files. Only explicit `--state` writes append-only doctor snapshots.
Keep history outside a repository; directory mode 0700 and database mode 0600 are
created on POSIX. Existing shared-permission databases are refused. Windows users
must restrict the history directory using their filesystem ACLs.

Each scan is bounded by 2 MiB per file and 2,000 distinct skill files. Skill roots
are shallow, not a recursive home/cache crawl. Unreadable sources and limits are
coverage failures, not healthy defaults. Symlink aliases to one skill file are
deduplicated; distinct copies remain candidates even when identical. Disabled
skills/plugins are not duplicate-routing defects. Managed policies, App-specific
overlays, trusted-folder gating and runtime precedence can change actual activation.

Use `--home <fixture-home>` for synthetic inventory, `--copilot-home <config-dir>`
for an alternate configuration directory, `--project <project-root>` for a project
overlay, `--skill-root <known-custom-directory>` for explicit extra sources, and
`--cli-path <known-app-cli>` to stat a known bundled executable. These are inventory
options, not Copilot CLI flags. `COPILOT_HOME` is honored by the command-line script.
An alternate `--home` test should also clear `COPILOT_HOME` or explicitly override
it; direct Python `inventory(home)` tests ignore the live environment override.

Inventory reports launch structure, not raw command arguments, module names,
URLs, headers or environment values. Structural hashes detect changes without
persisting file content. Configuration fingerprints deliberately exclude secrets
and arbitrary arguments: no endpoint/credential-value drift claim is possible.
Instruction/skill hashes show changed files, not conflicting instructions.

## Focused triage, not another catalog audit

Use **one symptom, one discriminating check**. Record the selected scope and stop
condition. No recursive agent/session/factory launches. A model or MCP tool call
needs explicit authorization for its side effects and data destination.

| Symptom | Bounded next check | Do not infer |
|---|---|---|
| Unsupported command | Exact owning binary's `--help` or subcommand `--help`, 15 s process deadline; compare the failing flag with returned help | A newer terminal CLI proves the App supports it |
| App/terminal discrepancy | Record App version from About and exact bundled CLI path if available; pass the latter to `--cli-path`; compare help only with approval | Different versions imply broken; undocumented paths are safe to guess |
| Missing launcher | Check the exact declared file and parent environment; no global filesystem search | Reinstalling every package is appropriate |
| Python dependency issue | Read the selected environment's lock/requirements metadata and package metadata; approved `python -I -c` import probe with 15 s deadline, one module only | Installed package implies successful import or valid auth |
| Dynamic runner/offline | Inspect intended pin and local runner cache metadata for that one package | Offline + dynamic is necessarily broken; direct Python uses runner resolution |
| MCP startup | With approval, one server's initialization only, external process deadline 20 s and exact owned PID cleanup | Initialization proves authentication |
| Authentication | Separate approved harmless authenticated read, if available; stop at consent/SSO and ask | A logged-in CLI authenticates every MCP |
| Useful result | One approved read-only tool with expected shape and no confidential payload, 30 s operation deadline where supported | Handshake/auth success proves the tool works |
| Cache/startup issue | Native App **Help > Run Health Check**, then review the relevant redacted symptom with consent | Cache age means corrupt; a reset is safe |
| Instruction drift/conflict | Review only the implicated clauses locally and compare source/precedence/intent; cite paths, not private prose | Fingerprint drift or wording similarity is a contradiction |
| Trigger overlap/duplicates | Verify discovery in the affected runtime; inspect the two descriptions locally, identify intended specialization | All duplicates should be removed |
| Outdated package/plugin | Compare one declared pin to official release metadata only if requested; identify intentional constraint first | Latest is compatible, required or approved |

For bounded subprocess checks, use the host's process runner with a real timeout
(for example Python `subprocess.run([...], timeout=15, capture_output=True)`),
never a shell command assembled from configuration. Suppress raw stderr containing
values; report exit code, timeout or safe error class. Consult installed help
before using update-suppression flags; avoid `copilot version` freshness checks
when only local identity is needed. No `-p` model invocations for discovery.
A tool initial-wait setting is not a process deadline. If the available MCP
transport cannot enforce a deadline, disclose that limit before starting; do not
promise to interrupt it, relaunch a duplicate or poll to stay busy.

Current installed `copilot skill --help` is the first discovery authority.
When supported, `copilot skill list` is a focused listing check, not permission to
run a prompt session. Disable auto-update for that subprocess when the installed
runtime documents `COPILOT_AUTO_UPDATE=false`. List results establish terminal
discovery only. The App may require a fresh session; do not terminate a user's
session or promise a `/doctor` alias.

The optional canonical probe implements help/version checks only:

```bash
python3 "$SKILL_ROOT/scripts/probe_cli.py" --binary /absolute/path/to/copilot \
  --topic root --flag=--no-auto-update
```

Pass option-shaped values using `--flag=--no-auto-update`. It checks `--version` and the chosen help topic, each with a
15-second timeout plus at most two seconds for cleanup, sets `COPILOT_AUTO_UPDATE=false`, never starts a prompt session,
and emits only version/status/flag presence. Use the exact binary of the owning
runtime, not a value copied out of MCP config. `not-listed` means help did not list
the flag, not definitive removal. A probe timeout or nonzero exit stops without
retry; missing help/version coverage remains explicit.
The CLI probe requires POSIX, launches each check in its own process group, and
escalates cleanup for descendants even when the group leader has exited. The MCP
probe uses the same cleanup helper. A launcher that deliberately daemonizes into
a different session is outside this process-group boundary; do not select such
launchers. No unrelated user process group is terminated.

## Leave alone unless proven relevant

- Explicit dependency versions, lockfiles and dedicated virtual environments.
- Direct `python -m ...` launchers with `UV_OFFLINE` inherited from an older setup.
- Intentional MCP tool exclusions and allowlists; never restore `["*"]`.
- `AZURE_TOKEN_CREDENTIALS=AzureCliCredential` when intentionally selected.
- The user's current browser mode, user skill preferences and domain-specific skills.
- Disabled registrations, retained caches and App-bundled CLI versions.

No automatic health label from version age. A finding must carry an observable
symptom or be marked **review/informational**, with a leave-alone alternative.

## Opt-in functional MCP checks

The runner needs `mcp~=1.27.1` and POSIX process groups. It refuses unsupported
hosts rather than pretending to bound child-tree cleanup. Inventory remains
standard-library-only except optional PyYAML; missing live-probe dependencies
do not authorize installation.

First inspect the selected registration and installed package manifest locally.
Never launch an unknown configured command, `npx -y`, `uvx`, or an installer.
Choose the already-installed executable/module or exact cached package CLI
after checking its version and entry point. A cache-selected binary proves that
binary, not the future resolution of an `@latest` registration. Preserve env
credentials and explicit exclusions. Read-only namespace narrowing is allowed
only in the private probe plan, not by rewriting the actual configuration.

Create a private session plan with:

| Field | Contract |
|---|---|
| `server`, `config_path` | One exact MCP registration; user or enabled plugin config |
| `config_fingerprint` | `fingerprint(config)` from `scripts/probe_mcp.py`; prevents stale reviewed-config execution; keep private |
| `approved_read_only` | `true` only after authorization for these exact checks |
| `deadline_seconds` | Integer 5-60; 30 recommended; hard deadline plus at most 2 seconds for teardown |
| `authentication` | `public`, `credentialed`, or `not-tested`; handshake never implies auth |
| `launcher` | Stdio only: reviewed absolute existing `command`, string `args`, optional `cwd`; never auto-selected |
| `tool` | Optional exact `name`, harmless `arguments`, and `expect`; omitted means initialization/listing only |

The `expect` object supports `{"kind":"json-keys","keys":["results"]}` or
`{"kind":"text-contains","value":"expected public marker"}`. Select a response
shape from the tool's actual contract, not a guessed universal schema.
`nonempty-text` records **response received, unvalidated**, never useful PASS.
Structured API errors and MCP `isError` fail. No raw result or stderr is persisted;
text and structured-string wrappers are handled separately.

```bash
python3 "$SKILL_ROOT/scripts/probe_mcp.py" --plan "$PRIVATE_PLAN" \
  --state "$HOME/.copilot/doctor/history.sqlite"
```

The same doctor database holds optional health history and accepted preferences;
it is not Copilot's internal database. Each health receipt carries status, timestamp,
deadline and tool metadata, not query/response content or tokens. Source/launcher/
tool selection is hashed for comparison; a different check has no prior baseline.
Do not upload plans, reports or databases. Remove scratch plans only when no
longer needed; they may contain private arguments.

For seven typical services, choose minimal checks, never a sweep of all tools:

- Documentation services: one public documentation search with an expected URL.
- Context retrieval: resolve one public library and verify its canonical ID.
- Web search: one public query, one result, no raw-page content.
- Memory service: read at most one item or an explicitly empty filter; suppress
  all content. Never add, update or delete a "test memory".
- Azure: documentation namespace probe is functional but **does not test Azure
  resource authentication**. No excluded namespaces or broad subscription dump.
- WorkIQ: schema metadata is functional but **does not test M365 delegated auth**.
  Do not escalate to SSO/EULA or private data access just to obtain a green badge.
- Browser MCP in extension mode: initialize/list tools only. Do not list tabs,
  navigate, screenshot or inspect the user's active browser. Functionality of
  the browser connection stays untested without a separately approved safe target.

Every selected tool must remain in the registration's allowlist. A tools/list
response is metadata, not permission to invoke anything. The private plan records
authorization; the runner cannot decide whether arbitrary arguments are harmless.
Malformed allowlists or expectation types are rejected before launch. Schema type
metadata is restricted to JSON Schema primitive names; arbitrary type values are
not emitted or stored.
The server may perform its own internal caching/telemetry/auth refresh on a read.
No automatic consent handling is installed.

No retries by default. An unexpected shape is not necessarily a broken server:
review structural evidence, make at most one justified correction, retain both
receipts, and stop on another uninformative failure. Do not broaden expectations
to "anything nonempty" to manufacture success.

## Verifiable inspiration from Claude

Official [Claude Code troubleshooting](https://code.claude.com/docs/en/troubleshooting)
and [configuration debugging](https://code.claude.com/docs/en/debug-your-config),
checked 2026-09-24, document:

- `claude doctor`: read-only installation/settings diagnostics without a session.
- In-session `/doctor`: installation/settings/extensions/context checks and
  proposed fixes requiring confirmation.
- `/mcp`, `/context`, `/status`: connected servers, actually loaded context, and
  active setting sources. Static configuration alone is not effective loading.

This doctor borrows the separation of read-only diagnosis from approved repair,
source attribution and loaded-versus-configured evidence. It does not copy
proprietary internals or claim equivalent coverage. The
[Claude Desktop documentation](https://code.claude.com/docs/en/desktop) describes
Chat, Cowork and Code tabs: these Claude Code commands are not evidence of a
general Claude Desktop Chat/Cowork doctor. Copilot App **Help > Run Health Check**
is a separate product feature with unverified scope here.

## Repairs are separate transactions

Before any repair, show: target runtime/source, evidence, exact minimal diff,
impact, backup path, post-change check and rollback. Obtain approval of that
specific operation. Back up only the affected file to a private timestamped path,
preserving permissions; backups may contain secrets and must never be committed.
Check the file has not changed since review; abort on concurrent edits.

Prefer documented CLI management commands for managed configuration; do not hand
edit `config.json`, auto-managed `m-*.json`, internal App databases or credential
stores. Never blanket-update, recursively purge caches, delete credentials,
disable all plugins or rewrite instruction files. Apply one approved repair,
verify the original symptom, then record the next scan. Verification failure is
not permission for additional repairs; use the approved rollback or stop.

## Report contract

Lead with concrete broken items. For each: impact, source, observation, confidence,
prior-scan status, repair proposal **or leave-alone rationale**. Group duplicate
candidates rather than dumping hundreds of identical rows. A removed finding
means *not observed this time*, not *fixed*: the source may have been disabled,
removed or become unreadable. End with scan scope and untested surfaces.

Four independent MCP statuses: inventory, handshake, authentication, useful result.
Never compress them into a single green badge. A successful inventory exit code
means the report was generated; inspect `findings` and `coverage` for failures.
The history database stores immutable snapshots, not verdicts or approval state.
No automatic retention cleanup; deleting old doctor history is also user-directed.

## Sources and compatibility

Checked 2026-09-24 against terminal Copilot CLI 1.0.88 help and first-party docs:

- [CLI plugin reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference):
  legacy manifests, enabled registrations, Agent Plugins 1.0 fixed `skills/` and
  `mcp.json`, and managed/repository overrides.
- [CLI configuration directory](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference):
  JSONC settings, managed state, `COPILOT_HOME`, project MCP files and personal
  instructions.

Docs can lead installed builds. Unsupported shapes are disclosed, not migrated.
The collector supports legacy and Agent Plugins 1.0 plugin components, but is not
a replica of the runtime's policy/trust resolver. Live App health-check scope,
agent-scoped MCP and App-managed session overlays remain outside automatic coverage.
