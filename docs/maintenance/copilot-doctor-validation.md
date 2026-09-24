# Copilot doctor validation

Status: **local source candidate**, skill **1.1.0**, proposed catalog **4.36.0**.
No PR, push, release or broad runtime certification is implied.

## Initial 1.0.0 acceptance scope

The collector is a local read-only implementation with opt-in doctor-owned SQLite
history. Thirty-six synthetic tests pass, covering JSONC and duplicate keys,
redaction, malformed frontmatter, description limits, symlink deduplication,
enabled plugin registration, legacy/portable plugin MCP discovery, project
overlays, intentional exclusions, direct-Python offline behavior, snapshot drift
and bounded CLI probe failures. The suite is wired into the existing offline
catalog unit-test job.

A read-only local scan completed on 2026-09-24. A selected bounded terminal CLI
probe reported **1.0.88**, with skill help available. No MCP server was launched.
Local names, paths and findings remain private; they are not catalog test data.

The approved user-scope installation matched all six source files by SHA-256;
the pre-existing starter test was backed up first. Fresh terminal
`copilot skill list --json` discovered `copilot-doctor` as enabled in personal
scope. Native skill loading in the already-running App session returned
**Skill not found**; reading the installed SKILL.md is the verified fallback,
not a claim of App slash-menu refresh. Recheck in a fresh App session.

Two local snapshots exercised the private baseline: first **no baseline**, then
**compared with zero drift**. Secret-value checks passed and the MCP configuration,
settings and personal instructions retained identical hashes. The selected
offline regression run completed **184 tests, OK, 2 skipped**; T0, plugin
structure validation and generated-site validation passed (zero broken links).
One missing CI test dependency was restored in a session-local directory, not
the user's global environment. No repair was performed.

Local checks and installation are performed separately from product runtime
acceptance. A terminal skill listing does not prove App slash-menu refresh or
instruction-following. Static inventory does not prove MCP startup, authentication
or useful results. No MCP server, SSO flow or model invocation is required or
authorized by this validation.

## Remaining limits

- App-bundled CLI location/version and **Help > Run Health Check** coverage are
  not inferred from the terminal binary.
- Managed policy, runtime trust, custom session overlays, agent-scoped MCP and
  undocumented precedence may alter effective loading.
- Dependency imports, cache corruption and instruction conflicts require selected
  approved checks from the runbook; fingerprints alone do not establish them.
- Remote freshness is not polled. Intentional pins and exclusions are not defects.
- Reports suppress content and values but retain local names/paths/fingerprints;
  keep them private and review before sharing.
- Repair/rollback behavior is a runbook contract, not an executed repair test.

No Azure resource connection or deployment path is present; live Azure T3 is inapplicable.
No automatic schedule, hook, cleanup or update is installed.

## 1.1.0 live-feedback acceptance

The approved follow-up added optional MCP probes and accepted structural
preferences. Browser extension mode is an intentional user choice, not a defect
relative to an older isolated-mode snapshot. The default collector still performs
no runtime/network calls. The parent session reported successful native App skill
loading after the initial delivery; that supersedes its earlier discovery gap,
but does not prove every future running session refreshes automatically.

On 2026-09-24 all seven selected registrations initialized and listed tools.
Explicit read-only functional probes produced these scoped results:

| Service | Functional evidence | Authentication scope |
|---|---|---|
| Microsoft Learn | Public documentation search passed | Not required |
| Context7 | Public React library ID resolved | Credentialed request accepted |
| Tavily | One-result public search passed | Credentialed request accepted |
| mem0 | One-item read returned expected pagination/results shape; content suppressed | Credentialed request accepted |
| Azure MCP | Documentation namespace search passed | Azure resource authentication not tested |
| WorkIQ | Message-fetch schema metadata passed | M365 delegated authentication not tested |
| Playwright | Initialization and 23-tool metadata only | Browser connection/actions deliberately not tested |

Cached, reviewed executables replaced dynamic package resolution for probe
processes only; registrations, pins and credential-provider settings were not
rewritten. No browser actions, memory writes/deletes, cloud resource mutations,
SSO/EULA acceptance or excluded Azure tools were used. Every owned probe worker
stopped and transports closed.

Context7's first query and mem0's initial wrapper interpretation yielded
**unexpected shape**, not proven service failure. One bounded correction each
resolved them; both original and corrected sanitized receipts were retained
privately. The mem0 regression is covered by a string-wrapper test. Claude Code
inspiration is attributed to official documentation in the runbook, not to
inspection or claimed parity with proprietary implementations.

The updated suite covers real synthetic stdio initialization/tool exchange,
timeout teardown, approval/config-fingerprint/allowlist gates, API error
classification, accepted preference scoping and timestamp-ordered health history.
The 1.1.0 run completed 52 doctor tests and 183 selected catalog regressions
(two skipped); a subsequent history-order regression brings doctor coverage to 53.
All 53 doctor tests and the measured catalog-count check passed after that addition.
T0, plugin structure and generated-site link checks passed. The configured
Playwright extension mode and browser target were accepted in the existing private
history, and the next scan reported zero drift. Dynamic package resolution and
cold-cache startup remain untested; reviewed cached binaries were used instead.
The approved 1.1.0 local installation matched all eight source files by SHA-256
after backing up 1.0.0. Installed inventory reported version 1.1.0 and accepted
browser mode/target; fresh terminal discovery and installed MCP-probe CLI help passed.

## Draft PR preparation

Integrated the latest main-branch progress-guard update without changing any of
the eight completed doctor source files. Rebuilt generated documentation and ran
the combined affected regression selection: **210 tests, OK, 2 skipped**.
T0, single-plugin validation and 51-page generated-site link validation passed.
Publication checks exclude private scan receipts/history, probe plans, credentials,
machine-specific paths and installation backups from the commit.
