---
schema_version: 2
freshness_tier: A
automation_tier: auto
upstream:
  type: github_repo
  repo: Azure/agentops
  ref: refs/tags/v0.14.0
  pinned_sha: fb5c93eee489c71ef4084fa209adae24f762e3d7
  pinned_commit_message: |
    Merge pull request #478 from Azure/release/v0.14.0
  license: MIT
  notes: |
    The tagged merge commit body is "Release v0.14.0"; that is not its subject.
    Support is limited to this tag/SHA and agentops-accelerator==0.14.0.
    Reference the tagged source, not main or latest documentation. No upstream
    implementation is vendored into this skill.
packages:
  - name: agentops-accelerator
    source: pypi
    version: "0.14.0"
    upstream_changelog: https://github.com/Azure/agentops/releases/tag/v0.14.0
    notes: |
      Exact consumer install: agentops-accelerator==0.14.0 (Python >=3.11).
      Pre-1.0 support does not imply compatibility with later minor releases.
      The validation installer uses ~=0.14.0 for catalog cap compliance plus
      an exact constraint and installed-version assertion; it does not silently
      certify a later patch. Re-pin all three together after revalidation.
docs_to_revalidate:
  - https://github.com/Azure/agentops/tree/v0.14.0
  - https://github.com/Azure/agentops/blob/v0.14.0/docs/concepts.md
  - https://github.com/Azure/agentops/blob/v0.14.0/docs/doctor-explained.md
  - https://pypi.org/project/agentops-accelerator/0.14.0/
known_issues:
  - id: KI-001
    description: "Pre-1.0 support requires contract revalidation for every minor release."
    upstream_url: null
    status: open
    workaround_location: 'references/upstream-pin.md § "KI-001 — Pre-1.0 compatibility"'
  - id: KI-002
    description: "Release evidence is unsigned and release/latest is a mutable output directory."
    upstream_url: null
    status: open
    workaround_location: 'references/upstream-pin.md § "KI-002 — Unsigned, mutable release evidence"'
  - id: KI-003
    description: "Doctor sources may fail open; unavailable diagnostics must never be treated as healthy."
    upstream_url: null
    status: open
    workaround_location: 'references/upstream-pin.md § "KI-003 — Doctor source availability"'
validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python >=3.11 required'"
    python3 -m venv .venv
    . .venv/bin/activate
    # Bounded install plus an exact constraint preserves the supported patch.
    printf 'agentops-accelerator==0.14.0\n' > agentops-constraints.txt
    python -m pip install --quiet --disable-pip-version-check \
      --constraint agentops-constraints.txt "agentops-accelerator~=0.14.0"
    python - <<'PY'
    from importlib.metadata import version

    installed = version("agentops-accelerator")
    assert installed == "0.14.0", f"Unsupported agentops-accelerator version: {installed}"
    print(f"agentops-accelerator=={installed}")
    PY

    agentops --help > /dev/null
    echo "agentops --help: OK"
    agentops eval analyze --help > /dev/null
    echo "agentops eval analyze --help: OK"
    agentops workflow analyze --help > /dev/null
    echo "agentops workflow analyze --help: OK"
    agentops doctor --help > /dev/null
    echo "agentops doctor --help: OK"

    python - <<'PY'
    from agentops.core.results import RunResult
    from agentops.core.release_evidence import ReleaseEvidence

    assert RunResult.model_fields["version"].default == 1
    assert ReleaseEvidence.model_fields["version"].default == 1
    print("RunResult.version=1")
    print("ReleaseEvidence.version=1")
    PY
    echo "AGENTOPS_CONTRACT_VALIDATION_PASS"
  expected_output:
    - "agentops-accelerator==0.14.0"
    - "agentops --help: OK"
    - "agentops eval analyze --help: OK"
    - "agentops workflow analyze --help: OK"
    - "agentops doctor --help: OK"
    - "RunResult.version=1"
    - "ReleaseEvidence.version=1"
    - "AGENTOPS_CONTRACT_VALIDATION_PASS"
  failure_signatures: []
last_validated: 2026-09-04
validated_by: copilot-bot
known_issues_count: 3
---

# Upstream pin — `foundry-agentops`

## 1. Tagged source and package support

| Field | Verified value |
|---|---|
| Upstream | [Azure/agentops](https://github.com/Azure/agentops/tree/v0.14.0) |
| Ref | `refs/tags/v0.14.0` |
| Commit | `fb5c93eee489c71ef4084fa209adae24f762e3d7` |
| Actual commit subject | `Merge pull request #478 from Azure/release/v0.14.0` |
| Commit body | `Release v0.14.0` |
| License | [MIT](https://github.com/Azure/agentops/blob/v0.14.0/LICENSE) |
| Supported distribution | `agentops-accelerator==0.14.0` |
| Python | `>=3.11`, as declared by tagged `pyproject.toml` and PyPI |
| Last validated | 2026-09-04 by `copilot-bot` |

The consumer install is deliberately exact:

```bash
python3 -m pip install "agentops-accelerator==0.14.0"
```

The distribution is **`agentops-accelerator`**, not `agentops`; its console
command is `agentops` and its Python import namespace is `agentops`.
[Tagged packaging metadata](https://github.com/Azure/agentops/blob/v0.14.0/pyproject.toml)
declares the entry point `agentops.cli.app:main`.

The catalog requires a compatible-release bound in validation installers.
The frontmatter therefore installs `~=0.14.0` **with an exact `==0.14.0`
constraint**, then asserts the installed distribution version before checking
the CLI or imports. The supported consumer contract remains exactly 0.14.0;
the bound alone would allow later 0.14.x releases and is not a support promise.

## 2. Executable contract and validation scope

`validation.script` above is the single executable source of truth. The pin
runner gives it a fresh isolated working directory and removes that directory
afterward; `.venv` and the constraint file are disposable run-local artifacts.
Only public PyPI access is required. No Azure login, deployment, Doctor
execution, or model inference occurs.

The contract checks the installed version, all four help commands, and both
Pydantic artifact schema defaults before emitting
`AGENTOPS_CONTRACT_VALIDATION_PASS`. A zero exit without every expected-output
substring is not sufficient.

| Check | Tagged implementation |
|---|---|
| `agentops --help` | [`src/agentops/cli/app.py`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/cli/app.py), root app |
| `agentops eval analyze --help` | Same file, `cmd_eval_analyze` |
| `agentops workflow analyze --help` | Same file, `cmd_workflow_analyze` |
| `agentops doctor --help` | Same file, Doctor group callback |
| `agentops.core.results.RunResult` | [`src/agentops/core/results.py`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/core/results.py), `version` defaults to `1` |
| `agentops.core.release_evidence.ReleaseEvidence` | [`src/agentops/core/release_evidence.py`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/core/release_evidence.py), `version` defaults to `1` |

This is a local package/CLI/import smoke, **not** evidence that Azure
connectivity, evaluation execution, or Doctor's remote sources work.
Those paths require separate live validation when the skill documents them.
Package version `0.14.0` and artifact schema version `1` are distinct contracts.

**2026-09-04 validation evidence:** on Python 3.14.5, the installed distribution
was exactly 0.14.0, all four help commands exited successfully, both schema
default assertions passed, and the final marker was emitted. The local mirror
did not yet list 0.14.0 and the PyPI file host was unreachable from that test
environment. Validation used the
[official tagged release wheel](https://github.com/Azure/agentops/releases/download/v0.14.0/agentops_accelerator-0.14.0-py3-none-any.whl)
as a local pip `find-links` input, verified against the version-specific PyPI
metadata: SHA-256
`6e5a70b8f52a5f8f765c6da218675b11420a8ad1c3e2578ea045f25e9d5bbd33`.
The wheel was byte-identical to the PyPI artifact; the pin's script,
constraints, dependency resolution, and assertions were not bypassed.

## 3. Native artifact paths

Preserve upstream names rather than inventing a parallel artifact schema:

| Native path | Purpose |
|---|---|
| `agentops.yaml` | Root, flat evaluation configuration |
| `.agentops/data/` | Dataset rows |
| `.agentops/results/<run>/results.json` | Machine-readable evaluation result |
| `.agentops/results/<run>/report.md` | Human-readable evaluation report |
| `.agentops/results/latest/results.json` | Latest evaluation result mirror |
| `.agentops/results/latest/report.md` | Latest evaluation report mirror |
| `.agentops/agent/report.md` | Doctor report |
| `.agentops/agent/history.jsonl` | Doctor history |
| `.agentops/release/latest/evidence.json` | Machine-readable release evidence |
| `.agentops/release/latest/evidence.md` | Human-readable release evidence |

These defaults are described by
[concepts](https://github.com/Azure/agentops/blob/v0.14.0/docs/concepts.md)
and [Doctor explained](https://github.com/Azure/agentops/blob/v0.14.0/docs/doctor-explained.md),
with writer behavior in the tagged
[`pipeline`](https://github.com/Azure/agentops/tree/v0.14.0/src/agentops/pipeline),
[`agent/history.py`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/agent/history.py),
and [`services/evidence_pack.py`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/evidence_pack.py).
Output overrides can change destinations. This smoke verifies the schemas,
not generation of all these artifacts.

## 4. Known issues at this pin

These are support constraints and tagged-source observations, not claims of
filed upstream bugs. Their `upstream_url` values are intentionally `null`;
there is no fabricated issue number or automatic issue-closure signal.
Revisit all three during every re-pin.

### KI-001 — Pre-1.0 compatibility

**Status:** open. The pinned package is 0.14.0. Do not infer cross-minor
compatibility from artifact `version: 1` or upstream prose that calls the
pipeline “1.0”. Those labels do not change the distribution version.

**Workaround:** keep the exact consumer pin. Revalidate every minor release
against its own tag: packaging/Python requirements, CLI commands and flags,
schema fields/defaults, native artifacts, and all known issues. Patch updates
also require an explicit re-pin before this skill claims support.

### KI-002 — Unsigned, mutable release evidence

**Status:** open.
[`write_release_evidence`](https://github.com/Azure/agentops/blob/v0.14.0/src/agentops/services/evidence_pack.py)
serializes JSON and Markdown to `.agentops/release/latest/` with ordinary file
writes. The tagged `ReleaseEvidence` schema and writer do not provide a
cryptographic signature. Subsequent writes replace the same latest files.
This describes generated **evidence packs**, not the signing status of the
upstream Git tag or PyPI distribution.

**Workaround:** archive both native evidence files with the evaluated commit,
candidate identity/version, and CI run identity in retention-controlled,
immutable release storage before another run replaces `latest`. Hash or sign
that archived bundle using the organization's release controls if required.
A `ready` value is a readiness summary, not a signed attestation or an
immutable approval record; never approve by a mutable `release/latest` path
alone.

### KI-003 — Doctor source availability

**Status:** open.
[Doctor's source documentation](https://github.com/Azure/agentops/blob/v0.14.0/docs/doctor-explained.md)
explicitly describes fail-open behavior: missing configuration, inference,
or SDKs can yield `skipped` diagnostics while other checks continue.
Source readers also handle network/auth failures with diagnostic information.
Some wiring checks report gaps; explicitly disabled sources can suppress
those findings.

**Workaround:** review each required source's status, reason, and coverage
alongside findings and exit code. Treat unavailable, skipped, errored, or
`cannot_verify` sources as **unverified**, never healthy. Record deliberate
opt-outs separately; an empty finding list or zero exit code does not prove
that every source was checked. Require missing evidence or an explicit,
reviewed exception before claiming release readiness.

## 5. Re-pin procedure

1. Resolve the candidate tag, including any annotated-tag dereference, and
   inspect the actual commit subject and body:

   ```bash
   git ls-remote https://github.com/Azure/agentops.git refs/tags/v0.14.0 'refs/tags/v0.14.0^{}'
   ```

   At this pin the ref resolves directly to
   `fb5c93eee489c71ef4084fa209adae24f762e3d7`. Stop and investigate unexpected
   movement of an existing tag rather than silently replacing its SHA.
2. Read the candidate's tagged source and version-specific PyPI metadata.
   Revalidate CLI signatures, imports/schema defaults, Python requirements,
   artifact writers, licensing, and KI-001 through KI-003; do not use `main`
   or latest docs to certify an older release.
3. Update ref/SHA/actual subject, package version, versioned URLs, exact
   constraint, bounded installer, version assertion, expected output, and
   human audit trail together. The exact-version constraint is intentional;
   do not remove it to make an unreviewed newer patch pass.
4. Run the frontmatter script in a fresh isolated directory before committing.
   After the pin is committed on the review branch, run the repository's
   changed-pin runner:

   ```bash
   python3 scripts/run-pin-validation.py --base <base-ref>
   ```

   The runner compares committed `base...HEAD`; it does not discover
   untracked or merely staged additions. It has no `--skill` selector.
   Use a base whose changed skill set is intentional, and require the
   `foundry-agentops` pin to be listed as passed, not skipped.
5. Record successful evidence, refresh `last_validated`, `validated_by`,
   and `known_issues_count`, and bump the skill's metadata PATCH when its
   `SKILL.md` exists. A failed contract is not an automatic refresh approval.
   If Azure behavior changes, attach the separate live test evidence required
   by `AGENTS.md` before proposing the refresh for merge.
