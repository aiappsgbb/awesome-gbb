# Native Skills version/package smoke

**This is an authorized LIVE EXECUTION smoke, not a catalog inspection,
implementation request or unit-test task.** You are already running inside the
registered CI matrix leg. The workflow supplied the approved project and
credentials. Execute Steps -1 through 3 against that project now, including
real Skills API create/download/promote/delete calls and the final marker.
Checking that a fixture exists or that unit tests pass does not execute this
contract and must never replace any step.

Do NOT run `git status`, inspect workflow/registration files, write a plan,
run unittest/pytest or catalog lint, rebuild docs, or edit repository files.
Import the canonical reader as instructed below; do not browse or rewrite it.
Do not upgrade MAF, provision infrastructure, re-grant roles, or select another
project/identity. Missing workflow inputs or API failures are a FAIL with the
precise stage, after owned cleanup, not a reason to switch into repo maintenance.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You ARE
the running fixture process. Execute the commands directly, not another CLI.
The workflow owns tooling and authentication; the existing CI identity must
already have Foundry User on the project.

## Step -1 - Acknowledge the contract

Your FIRST action must be this separate Bash tool call, not a search or read:

```bash
echo "skills/foundry-skill-catalog/SKILL.md"
```

## Step 0 - Preconditions and ownership

Require nonempty `FOUNDRY_PROJECT_ENDPOINT`, `AZURE_CLIENT_ID`,
`AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID`. Print only set/unset status.
Show Azure CLI state without asserting cache inheritance. Use the workflow's
approved credential chain; do not login again, switch identities, grant roles
or search for credentials. Stop on SDK authentication failure.

Create a UUID-suffixed `ci-smoke-skill-<suffix>` name and record it in the
run's private inventory **before** the first create attempt. The test owns
only this name and its versions. Retain that inventory if any operation has
an unknown outcome. Never use a standing domain skill.

## Step 1 - Isolated build-only client

In a workflow scratch virtual environment install `azure-ai-projects~=2.6.0`,
`azure-identity~=1.25.3` and `httpx~=0.28.1`. Do not install MAF: this fixture
checks native package access only. Construct a synchronous `AIProjectClient`
for the provided endpoint with the existing credential and `allow_preview=True`.
No model deployment or inference is required.

Import the actual module `skills/foundry-skill-catalog/references/skill_packages.py`
by adding its directory to `sys.path`; do not redefine `download_catalog` or
`skill_archive`. Those functions are the canonical reader under test.

Both helpers are **synchronous**; do not `await` them. The call signatures are
`download_catalog(project, skill_versions=None) -> list[SkillPackage]` and
`skill_archive(content: bytes) -> tuple[str, dict[str, bytes]]`.
The catalog result is a list of packages, not raw archive bytes. For each
single-skill check below, set `selected_version` to the requested version
string or `None` for the default, and `expected_version` to the native version
that should be served. Use this wiring with the already imported helpers:

```python
packages = download_catalog(project, {name: selected_version})
assert len(packages) == 1
package = packages[0]
assert package.name == name and package.version == expected_version
assert package.content is not None, "Native version must have downloadable content"
skill_md, files = skill_archive(package.content)
```

Check sentinels in `skill_md` (decoded text); check assets in `files`, whose
keys are root-relative paths and values are bytes.

## Step 2 - Native version round trips

Using the owned name:

1. Create inline version one with `SkillInlineContent`, benign instructions
   containing a unique `version-one` sentinel, and `default=True`.
2. Create inline version two with `version-two` and `default=False`.
   Use returned numeric version strings, never assume their values.
3. Read the parent and list versions. Verify default remains version one and
   both versions exist. Use the wiring above with `selected_version` and
   `expected_version` both set to version one, and assert the correct sentinel.
4. Promote version two through `beta.skills.update(name, default_version=...)`.
   Verify the parent, then load `{name: None}` and assert version-two content.
   Reload the explicit version-one pin and prove it is unchanged.
5. Roll back the default to version one and prove floating content returns
   version-one again. No implicit latest-version selection is acceptable.
6. Append a ZIP version with a root `SKILL.md` and a synthetic `assets/note.txt`
   using `CreateSkillVersionFromFilesBody` / `create_from_files`, `default=False`.
   Load its explicit pin using the canonical reader and verify both the body
   sentinel and exact asset bytes. Confirm default is still version one.

Use a `try/finally` around all mutation and verification steps so failure still
attempts the owned cleanup. Preserve the original failure if cleanup also fails.
HTTP errors, missing preview opt-in or invalid archives are FAIL, not legacy
fallbacks. Do not retry creation with a fresh name after an uncertain response.

## Step 3 - Cleanup and result

Delete one nondefault owned version; require its deletion response and verify
`get_version` yields authenticated 404. Delete the owned parent and verify
`get` yields authenticated 404. Do not accept an auth/network failure as absence.
Remove only this run's local ZIP/scratch output. Report functional result and
cleanup status separately. No PASS if this fixture's own parent remains.

The final action is a Bash tool file-write, not a prose assertion. Only after
all native content checks and cleanup succeeded:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-skill-catalog-smoke-result
```

On any failure, first perform the authorized owned cleanup, report the exact
failed stage and any residual inventory privately, then write:

```bash
printf 'SMOKE_RESULT=FAIL native version/package or cleanup check failed\n' > /tmp/foundry-skill-catalog-smoke-result
```

This marker proves **native API/package access only**. It does not certify
model application of instructions, MAF, MCP resource discovery, progressive
loading, or private networking. Execute `service_acceptance.md` separately for
those surfaces; do not expand this CI run implicitly.

Do not finish with a repository-status summary. You are not done until the live
lifecycle (or its exact failure and cleanup) is recorded and the final Bash tool
call writes the appropriate marker file.
