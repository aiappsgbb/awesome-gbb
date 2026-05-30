# Deep Audit + Testing Rethink — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the catalog's pytest-based "E2E" tests with a Copilot-CLI-as-consumer test mechanism, and run a one-shot deep audit of every skill against a 21-item bug-class catalog. Eliminate the false-confidence pattern documented in `scripts/tests/test_e2e_foundry_toolbox.py` (smoking gun: sync credential paired with async-only client — exactly the bug the catalog's own AST lint catches inside `skills/`).

**Architecture:** Build a new `copilot-cli-matrix` GHA job that, per skill, spins up `azure/login@v2` (OIDC) + `copilot plugin install awesome-gbb@local` + `copilot run --prompt-file skills/<name>/test-fixture/consumer_prompt.md`. Exit code IS the test result. The Copilot CLI reads SKILL.md and self-verifies; no parallel pytest assertions can drift from it. In parallel, dispatch one `general-purpose` audit sub-agent per skill (cap 5 concurrent) with a verbatim copy of the 21-item bug-class catalog and the §4 anti-normalization clause; each agent produces (a) a fix PR, (b) `skills/<name>/test-fixture/consumer_prompt.md`, and (c) `docs/audit/<name>-audit-trail.md`. Pilot 3 skills hands-on, then unleash the army on 22 more (2 stay manual). Delete all `scripts/tests/test_e2e_*.py` files and the `pin-smoke` + `e2e-azure` jobs from `skill-test.yml`.

**Tech Stack:** GitHub Actions (matrix jobs, `azure/login@v2` OIDC, `actions/upload-artifact@v4`), Copilot CLI (`copilot plugin marketplace add .` + `copilot run --prompt-file`), Python 3.11+ (matrix builder, AST lints, unit tests via pytest — for the lints, not for skills), Bash, Azure (`rg-awesome-gbb-ci`, `aif-awesome-gbb-ci`, `gpt-5.4-mini`), Foundry-routed model auth via `COPILOT_MODEL_ENDPOINT` + `COPILOT_MODEL_DEPLOYMENT` (exact names verified against released CLI in Task 1.0).

**Spec:** [`docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md`](../specs/2026-05-30-deep-audit-and-testing-rethink-design.md) (commit `5c8268b`).

---

## File Structure

```
.github/
├── workflows/
│   ├── copilot-cli-foundry-auth-smoke.yml      NEW   (Phase 1 gate)
│   ├── copilot-cli-cost-summary.yml            NEW   (weekly cost telemetry)
│   ├── skill-test.yml                          MOD   (delete pin-smoke + e2e-azure, add copilot-cli-matrix)
│   ├── automation-pr-gate.yml                  MOD   (recognize [audit-2026-Q2] tag; require audit-trail file)
│   ├── skill-validation.yml                    KEEP  (AST lints survive as pre-flight)
│   ├── pin-validation.yml                      KEEP  (different category — proves pip install + import)
│   ├── skill-freshness.yml                     KEEP
│   └── auto-merge-copilot.yml                  KEEP
└── quarantine.yml                              NEW   (matrix-exclusion list, starts empty)

scripts/
├── build-test-matrix.py                        NEW   (emits matrix `skills` list, honours quarantine.yml)
├── validate-skills.py                          MOD   (add doc header confirming AST lints survive)
└── tests/
    ├── test_build_test_matrix.py               NEW   (unit tests for matrix builder)
    ├── test_e2e_prompt_agents.py               DELETE
    ├── test_e2e_foundry_toolbox.py             DELETE  (the smoking gun)
    ├── test_e2e_voice_live.py                  DELETE
    ├── test_automation_pr_gate.py              KEEP  (protects surviving CI infra)
    └── test_validate_skills.py                 KEEP  (protects surviving AST lints)

skills/
├── <pilot-skill>/test-fixture/consumer_prompt.md         NEW × 3   (Phase 2)
└── <rollout-skill>/test-fixture/consumer_prompt.md       NEW × 22  (Phase 3)

docs/
├── superpowers/
│   ├── specs/2026-05-30-deep-audit-and-testing-rethink-design.md   (already committed)
│   └── plans/2026-05-30-deep-audit-and-testing-rethink.md           (this file)
└── audit/
    ├── README.md                               NEW   (explains directory format)
    └── <skill-name>-audit-trail.md             NEW × 25 (one per skill, both pilot + rollout, NOT the 2 manual)

AGENTS.md                                       MOD   (rewrite §§ 2.7–2.9, 9.6, 9.8, 12.5)
plugin.json                                     MOD   (PATCH bump)
.github/plugin/marketplace.json                 MOD   (match plugin.json)
```

**Files that stay manual (no fixture, no audit-trail file):** `citadel-hub-deploy`, `foundry-vnet-deploy`. They remain `automation_tier: issue_only` + `validation.runnable: false`. Their existing pin files cover detection; CI cannot deploy them.

**Resolved spec ambiguity (this plan owns the resolution):** Spec §9.2 says "scripts/tests/ directory — Empty after deletions. Removed." But `test_automation_pr_gate.py` and `test_validate_skills.py` are surviving infrastructure tests (they protect `automation-pr-gate.yml` and the AST lints in `validate-skills.py`, both of which the new design DEPENDS on). They must stay. So the directory is NOT removed — only the three `test_e2e_*.py` files are deleted.

---

## Phase 0 · Foundation Infrastructure

Build the test-harness scaffolding before any skill touches it. Each task in this phase is mechanical, self-contained, and has a CI-verifiable artifact at the end.

### Task 0.1 · Create the `docs/audit/` directory + README

**Files:**
- Create: `docs/audit/README.md`

- [ ] **Step 1: Create the directory with a README explaining the format**

```bash
mkdir -p docs/audit
```

```markdown
<!-- docs/audit/README.md -->
# Audit Trails

Per-skill audit records produced by the 2026-Q2 deep audit (spec
[`docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md`](../superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md),
plan [`docs/superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md`](../superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md)).

One file per audited skill: `<skill-name>-audit-trail.md`.

## Format

```markdown
# <skill-name> — Audit Trail

**Auditor:** <agent-id or human handle>
**Date:** YYYY-MM-DD
**Bug-class scan:** all 21 classes from Appendix A of the spec
**Findings (verbatim list):**
1. <class N> — <one-line description> — file:line → fix in commit <sha>
2. ...

**Fixture:** [`../../skills/<name>/test-fixture/consumer_prompt.md`](../../skills/<name>/test-fixture/consumer_prompt.md)

**CI matrix run that proved the fix:** <link to GHA run>

**Open items (deferred):** <if any, with rationale>
```

Skills excluded from this audit: `citadel-hub-deploy`, `foundry-vnet-deploy` (multi-resource greenfield deploys; remain `automation_tier: issue_only`).
```

- [ ] **Step 2: Commit**

```bash
git add docs/audit/README.md
git commit -m "docs(audit): create docs/audit/ directory for deep-audit trail records

Per spec 2026-05-30-deep-audit-and-testing-rethink-design.md §9.1.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 0.2 · Create the empty quarantine list

**Files:**
- Create: `.github/quarantine.yml`

- [ ] **Step 1: Write the file with a clear comment header**

```yaml
# .github/quarantine.yml
#
# Skills temporarily excluded from the copilot-cli-matrix job in
# .github/workflows/skill-test.yml.
#
# Add a skill here ONLY when it has failed 3 consecutive matrix runs
# (transient flake threshold per spec §8.4). Each entry MUST have a
# GitHub issue linked in the comment so quarantine doesn't become silent
# deprecation.
#
# Format:
#   skills:
#     - name: foundry-toolbox
#       since: 2026-06-01
#       issue: https://github.com/aiappsgbb/awesome-gbb/issues/NNN
#       reason: "Flake on ACA cold-start, see issue"

skills: []
```

- [ ] **Step 2: Commit**

```bash
git add .github/quarantine.yml
git commit -m "ci: add empty quarantine list for copilot-cli-matrix

Per spec 2026-05-30 §8.4. Skills added here are excluded from the
matrix; each entry requires a tracking issue.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 0.3 · Build the matrix-generator script (test-first)

**Files:**
- Create: `scripts/build-test-matrix.py`
- Create: `scripts/tests/test_build_test_matrix.py`

- [ ] **Step 1: Write the failing test FIRST**

```python
# scripts/tests/test_build_test_matrix.py
"""Unit tests for scripts/build-test-matrix.py.

The matrix builder emits a JSON list of skill names that have a
`test-fixture/consumer_prompt.md` and are NOT listed in
`.github/quarantine.yml`. The GHA `copilot-cli-matrix` job consumes
this list as its `matrix.skill` axis.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "build-test-matrix.py"


def run(repo_root: Path) -> list[str]:
    out = subprocess.check_output(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo_root)],
        text=True,
    )
    payload = json.loads(out)
    assert isinstance(payload, dict) and "skill" in payload, payload
    return payload["skill"]


def test_includes_skill_with_fixture(tmp_path: Path) -> None:
    (tmp_path / "skills" / "alpha" / "test-fixture").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text("skills: []\n")

    assert run(tmp_path) == ["alpha"]


def test_excludes_quarantined_skill(tmp_path: Path) -> None:
    (tmp_path / "skills" / "alpha" / "test-fixture").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / "skills" / "beta" / "test-fixture").mkdir(parents=True)
    (tmp_path / "skills" / "beta" / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text(
        "skills:\n  - name: beta\n    since: 2026-01-01\n    issue: x\n    reason: y\n"
    )

    assert run(tmp_path) == ["alpha"]


def test_skips_skill_without_fixture(tmp_path: Path) -> None:
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text("skills: []\n")

    assert run(tmp_path) == []


def test_output_is_sorted(tmp_path: Path) -> None:
    for name in ("zeta", "alpha", "mu"):
        (tmp_path / "skills" / name / "test-fixture").mkdir(parents=True)
        (tmp_path / "skills" / name / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text("skills: []\n")

    assert run(tmp_path) == ["alpha", "mu", "zeta"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest scripts/tests/test_build_test_matrix.py -v
```

Expected: ERROR — `scripts/build-test-matrix.py` does not exist yet.

- [ ] **Step 3: Implement the script**

```python
#!/usr/bin/env python3
# scripts/build-test-matrix.py
"""Emit the GHA matrix `skills` list for copilot-cli-matrix.

Output: a single-line JSON object `{"skill": [...]}` consumable by
`fromJSON(steps.build.outputs.matrix)` in skill-test.yml.

A skill is included iff:
  1. `skills/<name>/test-fixture/consumer_prompt.md` exists.
  2. `<name>` is NOT in `.github/quarantine.yml::skills[].name`.

Sorted alphabetically for deterministic GHA matrix expansion.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def build(repo_root: Path) -> dict[str, list[str]]:
    quarantine_file = repo_root / ".github" / "quarantine.yml"
    quarantined: set[str] = set()
    if quarantine_file.exists():
        data = yaml.safe_load(quarantine_file.read_text()) or {}
        for entry in data.get("skills") or []:
            quarantined.add(entry["name"])

    skills_dir = repo_root / "skills"
    matrix_skills: list[str] = []
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir():
                continue
            if (child / "test-fixture" / "consumer_prompt.md").exists():
                if child.name not in quarantined:
                    matrix_skills.append(child.name)

    return {"skill": matrix_skills}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(build(args.repo_root.resolve())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Make executable + run the test**

```bash
chmod +x scripts/build-test-matrix.py
pytest scripts/tests/test_build_test_matrix.py -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Manual smoke against the live repo**

```bash
python scripts/build-test-matrix.py --repo-root .
```

Expected output (now, before any fixture exists): `{"skill": []}`

- [ ] **Step 6: Commit**

```bash
git add scripts/build-test-matrix.py scripts/tests/test_build_test_matrix.py
git commit -m "ci: add scripts/build-test-matrix.py (emits copilot-cli-matrix list)

Honours .github/quarantine.yml exclusions. Per spec 2026-05-30 §8.4.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 0.4 · Extend `automation-pr-gate.yml` for the audit tag

**Files:**
- Modify: `.github/workflows/automation-pr-gate.yml`
- Modify: `scripts/tests/test_automation_pr_gate.py`

- [ ] **Step 1: Read the current gate logic to find the tag-recognition branch**

```bash
grep -n "skill-rewrite\|multi-skill\|scrub-canon" .github/workflows/automation-pr-gate.yml
grep -rn "skill-rewrite\|multi-skill\|scrub-canon" scripts/tests/test_automation_pr_gate.py
```

- [ ] **Step 2: Write the failing test for the new `[audit-2026-Q2]` tag**

Add to `scripts/tests/test_automation_pr_gate.py`:

```python
def test_audit_tag_requires_audit_trail_file():
    """A commit tagged [audit-2026-Q2] must touch docs/audit/<name>-audit-trail.md
    for every skill it changes, otherwise the gate fails."""
    # Simulated diff: touches skills/foo/SKILL.md but no docs/audit/foo-audit-trail.md
    diff_files = ["skills/foo/SKILL.md", "skills/foo/test-fixture/consumer_prompt.md"]
    commit_message = "audit(foo): fix MID-I credential bug per Appendix A class 1\n\n[audit-2026-Q2]"

    from scripts.automation_pr_gate import check_audit_tag_invariants
    errors = check_audit_tag_invariants(diff_files, commit_message)
    assert any("missing audit-trail" in e.lower() for e in errors), errors


def test_audit_tag_passes_when_audit_trail_present():
    diff_files = [
        "skills/foo/SKILL.md",
        "skills/foo/test-fixture/consumer_prompt.md",
        "docs/audit/foo-audit-trail.md",
    ]
    commit_message = "audit(foo): fix\n\n[audit-2026-Q2]"

    from scripts.automation_pr_gate import check_audit_tag_invariants
    errors = check_audit_tag_invariants(diff_files, commit_message)
    assert errors == []


def test_audit_tag_allows_multi_skill_within_audit_scope():
    """The [audit-2026-Q2] tag is the ONLY case where multi-skill body
    edits are allowed without [multi-skill] — but only if each touched
    skill has a paired audit-trail file."""
    diff_files = [
        "skills/foo/SKILL.md",
        "docs/audit/foo-audit-trail.md",
        "skills/bar/SKILL.md",
        "docs/audit/bar-audit-trail.md",
    ]
    commit_message = "audit(foo, bar): fix shared bug class\n\n[audit-2026-Q2]"

    from scripts.automation_pr_gate import check_audit_tag_invariants
    errors = check_audit_tag_invariants(diff_files, commit_message)
    assert errors == []
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
pytest scripts/tests/test_automation_pr_gate.py::test_audit_tag_requires_audit_trail_file -v
```

Expected: FAIL — `check_audit_tag_invariants` not defined OR returns nothing.

- [ ] **Step 4: Implement the check**

Add to `scripts/automation_pr_gate.py` (or whatever file `test_automation_pr_gate.py` already imports from — confirm before adding):

```python
def check_audit_tag_invariants(diff_files: list[str], commit_message: str) -> list[str]:
    """Per spec §9.2: [audit-2026-Q2] tag allows multi-skill edits IFF
    every touched skills/<name>/ has a paired docs/audit/<name>-audit-trail.md
    in the same diff."""
    errors: list[str] = []
    if "[audit-2026-Q2]" not in commit_message:
        return errors

    touched_skills: set[str] = set()
    for path in diff_files:
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "skills":
            touched_skills.add(parts[1])

    audit_trails_present: set[str] = set()
    for path in diff_files:
        if path.startswith("docs/audit/") and path.endswith("-audit-trail.md"):
            name = path[len("docs/audit/"): -len("-audit-trail.md")]
            audit_trails_present.add(name)

    missing = touched_skills - audit_trails_present
    for name in sorted(missing):
        errors.append(
            f"[audit-2026-Q2] tag: missing audit-trail file "
            f"docs/audit/{name}-audit-trail.md for skill {name}"
        )
    return errors
```

- [ ] **Step 5: Wire the check into the gate workflow YAML**

Edit `.github/workflows/automation-pr-gate.yml`. In the step that runs the gate checks, add a call to `check_audit_tag_invariants`. The existing pattern likely calls `check_mass_edit_invariants` and friends — add this one alongside, gated on the `[audit-2026-Q2]` substring so unrelated PRs aren't affected.

- [ ] **Step 6: Run tests + commit**

```bash
pytest scripts/tests/test_automation_pr_gate.py -v
git add scripts/automation_pr_gate.py scripts/tests/test_automation_pr_gate.py .github/workflows/automation-pr-gate.yml
git commit -m "ci(automation-pr-gate): recognize [audit-2026-Q2] tag + require audit-trail file

Per spec 2026-05-30 §9.2. The audit tag is the only path for multi-skill
body edits without [multi-skill]; each touched skill MUST have a paired
docs/audit/<name>-audit-trail.md in the diff.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 0.5 · Add doc header to `scripts/validate-skills.py`

**Files:**
- Modify: `scripts/validate-skills.py`

- [ ] **Step 1: Read the top of the file**

```bash
head -40 scripts/validate-skills.py
```

- [ ] **Step 2: Add the section-header comment immediately under the existing module docstring**

```python
# --- 2026-Q2 testing rethink note ---
#
# The AST lints in this file (sync-credential check, MID-I/MID-G detectors,
# reference-vs-SKILL.md drift check) SURVIVE the testing rebuild per spec
# 2026-05-30-deep-audit-and-testing-rethink-design.md §5.4. They function as
# fast pre-flight filters: they catch bugs that don't require a live deploy
# to detect, and they catch them in seconds rather than minutes. The
# copilot-cli-matrix job (skill-test.yml) is the live-Azure layer; this
# file is the static layer. Both are required.
#
# DO NOT remove a lint from this file without an explicit replacement
# documented in AGENTS.md §9.8.
# --- end note ---
```

- [ ] **Step 3: Commit**

```bash
git add scripts/validate-skills.py
git commit -m "docs(validate-skills): note that AST lints survive 2026-Q2 testing rebuild

Per spec 2026-05-30 §5.4. Static AST lints are pre-flight filters; the
copilot-cli-matrix job is the live-Azure layer. Both are kept.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 1 · Pre-Pilot Auth Smoke Gate

This is the **single load-bearing assumption** of the whole design: that the Copilot CLI can authenticate against a Foundry-hosted model in GitHub Actions using the same OIDC identity the rest of the workflows use. If this fails, the whole plan halts and we rethink.

> **Empirical findings recorded mid-execution (2026-05-30):**
>
> - **Auth-smoke shipped at commit `8209f68`** uses the verified Task-1.0 env-var stack (`COPILOT_PROVIDER_TYPE=azure`, `COPILOT_PROVIDER_BASE_URL`, `COPILOT_PROVIDER_BEARER_TOKEN`, `COPILOT_PROVIDER_MODEL_ID`, `COPILOT_PROVIDER_WIRE_MODEL`, `COPILOT_PROVIDER_WIRE_API=responses`, `COPILOT_ALLOW_ALL=true`). The legacy `COPILOT_MODEL_*` placeholders in §5.3 of the spec **do not exist** in the released CLI 1.0.57-2 and would be silently ignored. Task 2.1 Step 4 above has been corrected to use the verified stack.
> - **`AZURE_AI_ENDPOINT` secret is account-host shape** (`https://aif-awesome-gbb-ci.cognitiveservices.azure.com/`) — confirmed by querying the CI resource directly with `az cognitiveservices account show -n aif-awesome-gbb-ci -g rg-awesome-gbb-ci`. This matches AGENTS.md §9.7 documentation; that section is **correct**, not stale. Workflows that need the **project endpoint** (`https://aif-awesome-gbb-ci.services.ai.azure.com/api/projects/ci-test`) for `AIProjectClient` must derive it from the account host inside the workflow rather than introducing a new secret.
> - **The legacy `scripts/tests/test_e2e_*.py` files have never actually executed in CI.** The `unit-tests` job skips them (`@unittest.skipUnless(AZURE_AI_ENDPOINT, ...)` — the secret is not exposed there); the `e2e-azure` job invokes `scripts/run-pin-validation.py --include-azure`, not `pytest scripts/tests/`. Their pass/fail status has never been observed empirically. Phase 4's deletion step is therefore lower-risk than originally feared — but if any consumer-fixture rewrites cross-reference patterns from those files, **verify the pattern works** rather than trusting "it was green on main" (it wasn't observed).

### Task 1.0 · Verify exact Copilot CLI Foundry-routing env-var names

**Files:** (research, no commits yet)

- [ ] **Step 1: Install the released Copilot CLI locally**

```bash
copilot --version
copilot --help 2>&1 | grep -iE "model|endpoint|foundry|env"
```

- [ ] **Step 2: Locate the model-routing configuration in the released CLI docs / source**

The spec §5.3 uses placeholder names `COPILOT_MODEL_ENDPOINT` and `COPILOT_MODEL_DEPLOYMENT`. Confirm the actual names against the released CLI. Likely candidates: `COPILOT_LLM_ENDPOINT`, `COPILOT_LLM_DEPLOYMENT`, `COPILOT_FOUNDRY_ENDPOINT`, or per-config-file. Check `copilot config --help` and `~/.copilot/config.json`.

```bash
copilot config --help 2>&1
ls ~/.copilot/
cat ~/.copilot/config.json 2>/dev/null | head -40
```

- [ ] **Step 3: Record the verified names in a scratch note for use in Task 1.1**

Write the exact env-var names to `docs/superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md` as a margin note OR (better) record them in a session-state file you'll consult in the next task:

```bash
mkdir -p /Users/ricchi/.copilot/session-state/b9c8d150-a8e4-4879-9e84-75837e9f4ff5/files
cat > /Users/ricchi/.copilot/session-state/b9c8d150-a8e4-4879-9e84-75837e9f4ff5/files/cli-env-vars.md <<'EOF'
# Verified Copilot CLI Foundry-routing env-var names (as of 2026-05-30)

CLI version: <fill in>
Endpoint env-var name: <fill in>
Deployment env-var name: <fill in>
Auth mechanism: <DefaultAzureCredential / OIDC token / API key>
Source of truth: <link to docs or source file>
EOF
```

- [ ] **Step 4: If the released CLI does NOT support Foundry routing yet, STOP**

This is a hard blocker. The whole design assumes it works. Open an issue in `aiappsgbb/awesome-gbb` titled "BLOCKED: Copilot CLI Foundry-routing not available in released CLI — Phase 1 cannot proceed" and notify the user. Do NOT proceed to Task 1.1.

- [ ] **Step 5: No commit (research-only task)**

---

### Task 1.1 · Write `copilot-cli-foundry-auth-smoke.yml`

**Files:**
- Create: `.github/workflows/copilot-cli-foundry-auth-smoke.yml`

- [ ] **Step 1: Author the minimal workflow that proves the path**

Use the verified env-var names from Task 1.0. Replace `COPILOT_MODEL_ENDPOINT` / `COPILOT_MODEL_DEPLOYMENT` below with the actual names if different.

```yaml
# .github/workflows/copilot-cli-foundry-auth-smoke.yml
name: copilot-cli-foundry-auth-smoke

on:
  workflow_dispatch:
  schedule:
    - cron: "17 6 * * 1"   # Monday 06:17 UTC, before skill-freshness

permissions:
  id-token: write
  contents: read

jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Azure login via OIDC
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Install Copilot CLI
        run: |
          # Use the same install path the catalog documents in README.md.
          curl -fsSL https://github.com/github/copilot-cli/releases/latest/download/install.sh | bash
          echo "$HOME/.copilot/bin" >> "$GITHUB_PATH"

      - name: Configure CLI for Foundry-routed model
        env:
          COPILOT_MODEL_ENDPOINT: ${{ secrets.AZURE_AI_ENDPOINT }}
          COPILOT_MODEL_DEPLOYMENT: gpt-5.4-mini
        run: |
          copilot --version
          copilot config show || true

      - name: Smoke test — one-shot prompt that requires model auth
        env:
          COPILOT_MODEL_ENDPOINT: ${{ secrets.AZURE_AI_ENDPOINT }}
          COPILOT_MODEL_DEPLOYMENT: gpt-5.4-mini
        timeout-minutes: 5
        run: |
          set -euo pipefail
          OUT=$(copilot run --no-skills --prompt "Reply with the single word PONG and nothing else.")
          echo "$OUT"
          echo "$OUT" | grep -q "PONG" || { echo "smoke FAILED: no PONG"; exit 1; }
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/copilot-cli-foundry-auth-smoke.yml
git commit -m "ci: add copilot-cli-foundry-auth-smoke workflow (Phase 1 gate)

Per spec 2026-05-30 §5.4. This workflow proves the load-bearing
assumption: Copilot CLI can auth against a Foundry-hosted model in GHA
via the same OIDC identity used elsewhere. If this workflow is red, the
deep-audit + testing-rethink plan halts.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 3: Dispatch the workflow manually + verify it goes green**

```bash
gh workflow run copilot-cli-foundry-auth-smoke.yml
sleep 30
gh run list --workflow=copilot-cli-foundry-auth-smoke.yml --limit 1
gh run watch
```

Expected: `PONG` in the run log; conclusion = success.

- [ ] **Step 4: If RED, STOP and triage**

The most likely failure modes (per spec §11): wrong env-var names (re-do Task 1.0), missing RBAC on UAMI (check Cognitive Services OpenAI User on `aif-awesome-gbb-ci`), CLI install path moved (check the install script URL). Do NOT proceed to Phase 2 until this is green on `main`.

---

## Phase 2 · Pilot (3 skills, hands-on)

Validates the whole design end-to-end before unleashing the agent army. Done hands-on (not by sub-agents) so failures are caught against the harness, not amplified by autonomous execution.

### Task 2.1 · Pilot skill — `foundry-prompt-agents`

**Files:**
- Create: `skills/foundry-prompt-agents/test-fixture/consumer_prompt.md`
- Create: `docs/audit/foundry-prompt-agents-audit-trail.md`
- Modify: `.github/workflows/skill-test.yml` (add the matrix job skeleton)
- Modify: `skills/foundry-prompt-agents/SKILL.md` (only if audit finds bugs)

- [ ] **Step 1: Read SKILL.md end-to-end + run the 21-class scan**

```bash
view skills/foundry-prompt-agents/SKILL.md
view skills/foundry-prompt-agents/references/   # if present
```

For each of the 21 classes in spec Appendix A, scan SKILL.md and references. Record findings (even "none observed") in the audit-trail file as you go.

- [ ] **Step 2: Write the audit-trail file**

```markdown
# foundry-prompt-agents — Audit Trail

**Auditor:** <your handle>
**Date:** 2026-05-30
**Bug-class scan:** all 21 classes from Appendix A of the spec

**Findings:**
1. Class 1 (sync credential in async client) — <found? where?>
2. Class 2 (endpoint URL bugs) — <found? where?>
3. ... (all 21)

**Fixture:** [`../../skills/foundry-prompt-agents/test-fixture/consumer_prompt.md`](../../skills/foundry-prompt-agents/test-fixture/consumer_prompt.md)

**CI matrix run that proved the fix:** <filled in after Step 5>

**Open items (deferred):** <if any>
```

- [ ] **Step 3: Write the consumer prompt fixture**

The fixture is a single-task prompt that, when executed by `copilot run`, exercises the SKILL's happy path against real Azure and self-verifies. Keep it specific and short. Example shape:

```markdown
<!-- skills/foundry-prompt-agents/test-fixture/consumer_prompt.md -->

You are testing the `foundry-prompt-agents` skill end-to-end.

Use the skill to:
1. Create a prompt agent named `ci-smoke-<short-uuid>` in the Foundry
   project at endpoint `$AZURE_AI_ENDPOINT` using deployment
   `gpt-5.4-mini`. The agent's instructions: "Reply with the single
   word OK and nothing else."
2. Send the agent a single user message: "ping".
3. Assert the agent's reply contains the word `OK`.
4. Delete the agent.
5. Exit 0 on success. On any failure, print the failing step and exit
   non-zero.

Do NOT skip any step. Do NOT use mocked clients. Use the credential
chain documented in the skill (DefaultAzureCredential via
azure/login@v2 OIDC).
```

- [ ] **Step 4: Add the matrix job skeleton to `skill-test.yml`**

Edit `.github/workflows/skill-test.yml`. Add a new job alongside (not replacing yet) the existing `pin-smoke` and `e2e-azure` jobs:

```yaml
  build-matrix:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.build.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pyyaml
      - id: build
        run: echo "matrix=$(python scripts/build-test-matrix.py --repo-root .)" >> "$GITHUB_OUTPUT"

  copilot-cli-matrix:
    needs: build-matrix
    if: fromJSON(needs.build-matrix.outputs.matrix).skill[0] != null
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      max-parallel: 5
      matrix: ${{ fromJSON(needs.build-matrix.outputs.matrix) }}
    timeout-minutes: 30
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Install Copilot CLI
        # npm install is the documented install path (proven by the auth-smoke
        # workflow at .github/workflows/copilot-cli-foundry-auth-smoke.yml).
        # Node 22 is pre-installed on ubuntu-latest. Do NOT use a `curl …
        # install.sh | bash` pattern — no such canonical URL is published.
        run: |
          npm install -g @github/copilot
          copilot --version

      - name: Install awesome-gbb plugin from this checkout
        run: |
          copilot plugin marketplace add "$GITHUB_WORKSPACE"
          copilot plugin install awesome-gbb@awesome-gbb

      - name: Get Foundry bearer token
        # Mirrors the auth-smoke pattern. `tr -d '\r\n'` is load-bearing:
        # without it, the trailing newline from `-o tsv` produces a 401
        # masquerading as a token-format error.
        run: |
          set -euo pipefail
          TOKEN=$(az account get-access-token \
            --resource https://cognitiveservices.azure.com/.default \
            --query accessToken -o tsv | tr -d '\r\n')
          echo "::add-mask::$TOKEN"
          echo "COPILOT_PROVIDER_BEARER_TOKEN=$TOKEN" >> "$GITHUB_ENV"

      - name: Run consumer prompt for ${{ matrix.skill }}
        id: run
        env:
          # BYOK routing → Foundry, identical to the auth-smoke workflow.
          # Env-var names verified against released CLI 1.0.57-2 via
          # `copilot help providers` / `copilot help environment` (Task 1.0
          # notes in the session-state files dir). The legacy
          # `COPILOT_MODEL_*` names DO NOT EXIST and would be silently
          # ignored — leading to a confusing "Copilot didn't authenticate"
          # failure that's actually a misconfigured provider stack.
          #
          # AZURE_AI_ENDPOINT secret is verified account-host shape per
          # AGENTS.md §9.7 (`https://aif-awesome-gbb-ci.cognitiveservices.azure.com/`).
          # If a consumer fixture also needs the Foundry project endpoint
          # (`…services.ai.azure.com/api/projects/<name>`), derive it from
          # the account host inside the fixture's prompt or add a derive
          # step — do NOT add a separate secret.
          COPILOT_PROVIDER_TYPE: azure
          COPILOT_PROVIDER_BASE_URL: ${{ secrets.AZURE_AI_ENDPOINT }}
          COPILOT_PROVIDER_MODEL_ID: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_MODEL: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_API: responses
          COPILOT_ALLOW_ALL: "true"
          COPILOT_AUTO_UPDATE: "false"
          AZURE_AI_ENDPOINT: ${{ secrets.AZURE_AI_ENDPOINT }}
          ACR_LOGIN_SERVER: ${{ secrets.ACR_LOGIN_SERVER }}
        run: |
          set -euo pipefail
          PROMPT="skills/${{ matrix.skill }}/test-fixture/consumer_prompt.md"
          test -f "$PROMPT" || { echo "missing fixture: $PROMPT"; exit 2; }
          # `-p` is the released CLI's one-shot prompt form. `copilot run`
          # does not exist; `--prompt-file` does not exist. Read the fixture
          # via `$(cat …)` and inline it. `--disable-builtin-mcps` drops the
          # GitHub MCP server so the run doesn't depend on github.com
          # reachability — the consumer fixture is allowed to opt back in
          # to specific MCP servers via `--allow-tool=mcp__…` flags.
          copilot -p "$(cat "$PROMPT")" \
                  --allow-all-tools \
                  --disable-builtin-mcps \
                  -C "$GITHUB_WORKSPACE" \
                  2>&1 | tee "/tmp/${{ matrix.skill }}-transcript.log"

      - name: Retry once on classified-transient failure
        if: failure() && steps.run.outcome == 'failure'
        env:
          COPILOT_PROVIDER_TYPE: azure
          COPILOT_PROVIDER_BASE_URL: ${{ secrets.AZURE_AI_ENDPOINT }}
          COPILOT_PROVIDER_MODEL_ID: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_MODEL: gpt-5.4-mini
          COPILOT_PROVIDER_WIRE_API: responses
          COPILOT_ALLOW_ALL: "true"
          COPILOT_AUTO_UPDATE: "false"
          AZURE_AI_ENDPOINT: ${{ secrets.AZURE_AI_ENDPOINT }}
          ACR_LOGIN_SERVER: ${{ secrets.ACR_LOGIN_SERVER }}
        run: |
          set -euo pipefail
          PROMPT="skills/${{ matrix.skill }}/test-fixture/consumer_prompt.md"
          if grep -qE "429|503|throttl|capacity|EOF during azd deploy|revision .* not found" "/tmp/${{ matrix.skill }}-transcript.log"; then
            echo "classified-transient — retrying once"
            copilot -p "$(cat "$PROMPT")" \
                    --allow-all-tools \
                    --disable-builtin-mcps \
                    -C "$GITHUB_WORKSPACE"
          else
            echo "non-transient failure — not retrying"
            exit 1
          fi

      - name: Upload transcript (forensics)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: transcript-${{ matrix.skill }}
          path: /tmp/${{ matrix.skill }}-transcript.log
          retention-days: 7
```

- [ ] **Step 5: Open a PR + verify the matrix runs the pilot skill green**

```bash
git add skills/foundry-prompt-agents/test-fixture/ docs/audit/foundry-prompt-agents-audit-trail.md .github/workflows/skill-test.yml
git commit -m "audit(foundry-prompt-agents): Phase 2 pilot — fixture + audit trail + matrix wiring

Per spec 2026-05-30 Phase 2. Adds the copilot-cli-matrix job skeleton
to skill-test.yml (pin-smoke + e2e-azure jobs stay for now; deleted in
Phase 4). Adds the foundry-prompt-agents consumer-prompt fixture and
21-class audit trail.

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
gh pr create --fill --base main
gh pr checks --watch
```

Expected: `copilot-cli-matrix (foundry-prompt-agents)` = success.

- [ ] **Step 6: Update audit-trail file with the run URL + merge**

```bash
# Edit docs/audit/foundry-prompt-agents-audit-trail.md and fill in the CI run URL.
git add docs/audit/foundry-prompt-agents-audit-trail.md
git commit --amend --no-edit
git push -f
gh pr merge --squash --auto
```

---

### Task 2.2 · Pilot skill — `foundry-hosted-agents`

> **Lessons harvested from Task 2.1 (`foundry-prompt-agents`)** — read
> these BEFORE starting. They are codified in `AGENTS.md` § 9.7; this
> callout is a quick reference so you don't have to context-switch.
>
> 1. **UAMI FIC is narrow** — only `pull_request`, `ref:refs/heads/main`,
>    `ref:refs/tags/*`. `workflow_dispatch` on a PR branch fails
>    `AADSTS700213`. Stability re-runs MUST be `pull_request synchronize`
>    (empty commits, one push at a time, **≥ 45 s spacing**) — GitHub
>    coalesces simultaneous pushes into one event regardless of any
>    workflow `concurrency:` block.
> 2. **Result marker contract** is grep-whole-transcript, **FAIL beats
>    PASS**, never `tail`. Copilot CLI emits an unsuppressible
>    `Changes / Duration / Tokens` footer after the agent reply. The
>    matrix job grep contract is already correct in
>    `.github/workflows/skill-test.yml` — your fixture just needs to
>    emit `SMOKE_RESULT=PASS` (or `SMOKE_RESULT=FAIL <reason>`) on its
>    own line at the end. `copilot -s/--silent` was NOT tried in Task
>    2.1 — worth probing if you want a cleaner transcript.
> 3. **UUID suffix on every resource name** —
>    `f"ci-smoke-ha-{uuid.uuid4().hex[:8]}"` for agent display name, ACA
>    service name, ACR image tag, etc. Parallel runners + same-SHA
>    retries WILL collide on fixed names.
> 4. **Anti-theater principle from Task 2.1** — if the audit-trail file
>    contains "TODO / fill in later / placeholder" for any of the 21
>    bug classes, the deliverable is NOT done. List each class explicitly
>    with evidence citations (file:line) or an explicit "not applicable"
>    + one-sentence justification. Deferred items go to a separate "Open
>    items" section with an owner and a rationale for deferral.
> 5. **AGENTS.md § 2.7, § 2.8, § 9.6, § 9.8, § 10.3, § 12.3, § 12.5 still
>    reference the deleted `pin-smoke` / `e2e-azure` jobs and
>    `scripts/tests/test_e2e_*.py` files.** Those jobs were deleted in
>    commit `3af9662` (Task 2.1). The replacement is the
>    `copilot-cli-matrix` job — see `.github/workflows/skill-test.yml`
>    L201+. Do NOT author a pytest `test_e2e_<name>.py`; author the
>    fixture under `skills/<name>/test-fixture/consumer_prompt.md`
>    instead. Updating AGENTS.md to reflect this is its own separate
>    cleanup task — out of scope here.

**Files:**
- Create: `skills/foundry-hosted-agents/test-fixture/consumer_prompt.md`
- Create: `docs/audit/foundry-hosted-agents-audit-trail.md`
- Modify: `skills/foundry-hosted-agents/SKILL.md` (only if audit finds bugs)

- [ ] **Step 1: Audit using the same 21-class scan as Task 2.1**

```bash
view skills/foundry-hosted-agents/SKILL.md
ls skills/foundry-hosted-agents/references/
```

Pay extra attention to class 1 (MID-I — this skill was hit by 6 instances of this bug per checkpoint 008). Verify the `FoundryChatClient` paired with `DefaultAzureCredential` (async) and NOT `AzureCliCredential` (sync).

- [ ] **Step 2: Write the audit-trail file** (same template as Task 2.1)

- [ ] **Step 3: Write the consumer prompt fixture**

Hosted agents need a container build + deploy + chat turn. Example:

```markdown
<!-- skills/foundry-hosted-agents/test-fixture/consumer_prompt.md -->

You are testing the `foundry-hosted-agents` skill end-to-end.

Use the skill to:
1. Build a minimal hosted agent container using the skill's canonical
   reference at `skills/foundry-hosted-agents/references/python/main.py`.
   Deploy it as an ACA service to `cae-awesome-gbb-ci` with image
   pushed to `acrawesomegbbci.azurecr.io/ci-smoke-<short-uuid>:latest`.
   Use deployment `gpt-5.4-mini` at endpoint `$AZURE_AI_ENDPOINT`.
2. Send one chat turn: "Reply with EXACTLY the single word READY and
   nothing else." Assert the reply contains `READY`.
3. Tear down the ACA service and delete the ACR image tag.
4. Exit 0 on success. On any failure, print the failing step and exit
   non-zero.

Follow the skill's documented credential pattern. Do NOT substitute a
sync credential into the async client (that is the MID-I bug class).
```

- [ ] **Step 4: Open PR + verify matrix green + merge**

```bash
git add skills/foundry-hosted-agents/test-fixture/ docs/audit/foundry-hosted-agents-audit-trail.md
git commit -m "audit(foundry-hosted-agents): Phase 2 pilot — fixture + audit trail

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
gh pr create --fill --base main
gh pr checks --watch
gh pr merge --squash --auto
```

Expected: `copilot-cli-matrix (foundry-hosted-agents)` = success.

---

### Task 2.3 · Pilot skill — `azd-patterns`

> **Lessons harvested from Task 2.1** (also see the callout on Task 2.2):
> UAMI FIC narrow → `pull_request synchronize` for stability; result
> marker contract is grep-whole-transcript with FAIL beating PASS; UUID
> suffix every resource name; anti-theater on audit trail. Codified in
> `AGENTS.md` § 9.7. `azd-patterns` is shaped differently from the two
> agent-runtime pilots (Bicep module library, not a runtime), so the
> fixture exercises a **single representative pattern** (the ACA-job
> pattern; spec § 11 accepts the incomplete-coverage trade-off).

**Files:**
- Create: `skills/azd-patterns/test-fixture/consumer_prompt.md`
- Create: `docs/audit/azd-patterns-audit-trail.md`
- Modify: `skills/azd-patterns/SKILL.md` (only if audit finds bugs)

- [ ] **Step 1: 21-class audit**

```bash
view skills/azd-patterns/SKILL.md
ls skills/azd-patterns/references/
```

This skill is the Bicep-module library; pay extra attention to classes 9 (Bicep module drift), 10 (Bicep param mismatches), 13 (region defaults), and 16 (missing `dependsOn` for RBAC race).

- [ ] **Step 2: Write the audit-trail file**

- [ ] **Step 3: Write the consumer prompt fixture**

`azd-patterns` can't be exercised as a whole; pick the most-used pattern as the fixture surface. Spec §11 acknowledges this and accepts incomplete coverage in the first wave. Example:

```markdown
<!-- skills/azd-patterns/test-fixture/consumer_prompt.md -->

You are testing the `azd-patterns` skill's ACA-job pattern end-to-end.

Use the skill to:
1. Scaffold a minimal `azure.yaml` + `infra/main.bicep` for an ACA job
   that runs `echo HELLO` once. Use the module shapes documented in
   the skill's references.
2. Run `azd up` against resource group `rg-awesome-gbb-ci` (use a
   short-lived environment name `ci-azd-pat-<short-uuid>` so cleanup
   is unambiguous).
3. Trigger the job once via `az containerapp job start`.
4. Verify the job's log contains `HELLO`.
5. Run `azd down --force --purge` to clean up.
6. Exit 0 on success.

Note: This fixture covers the ACA-job pattern. Other azd-patterns
(ACA service, Functions, container apps with managed identity) are
audited per the 21-class catalog but not exercised by this fixture.
That gap is accepted per spec §11.
```

- [ ] **Step 4: Open PR + verify matrix green + merge**

```bash
git add skills/azd-patterns/test-fixture/ docs/audit/azd-patterns-audit-trail.md
git commit -m "audit(azd-patterns): Phase 2 pilot — fixture + audit trail (ACA-job pattern)

[audit-2026-Q2]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
gh pr create --fill --base main
gh pr checks --watch
gh pr merge --squash --auto
```

---

### Task 2.4 · Pilot exit criteria — 5 consecutive green matrix runs

> **Status note (harvested from Task 2.1):** Task 2.1
> (`foundry-prompt-agents`) has already shipped 5 consecutive green
> matrix runs on `unsafecode/pr-review` — see
> `docs/audit/foundry-prompt-agents-audit-trail.md`. Task 2.4 here is
> NOT a third repetition of that — it is the **all-three-pilots-on-the-
> same-SHA** check. The 5 runs from 2.1 only counted while 2.1 was the
> ONLY fixture in the matrix; once 2.2 and 2.3 land, the matrix is
> wider and the 5-green counter resets to zero.

**Files:** (no commits; verification only)

- [ ] **Step 0: Confirm matrix scope BEFORE counting**

```bash
python3 scripts/build-test-matrix.py | jq '.include[].skill'
```

Expected output: `"foundry-prompt-agents"`, `"foundry-hosted-agents"`,
`"azd-patterns"`. If any of the three is missing, do NOT start counting
— go fix the missing fixture first.

- [ ] **Step 1: Trigger 3 stability runs via empty-commit pushes (NOT
      `workflow_dispatch`)**

```bash
for i in 1 2 3; do
  git commit --allow-empty -m "ci: stability run #$i for 3-pilot matrix [audit-2026-Q2]"
  git push origin HEAD
  # Wait for the previous CI run to start before queuing the next
  # (≥ 45 s — GitHub coalesces simultaneous pushes per AGENTS.md § 9.7).
  sleep 60
done
```

`workflow_dispatch` against a PR branch fails `AADSTS700213` because the
UAMI's federated credentials don't cover non-`main` refs — this is
documented in `AGENTS.md` § 9.7 and was learned the hard way during
Task 2.1.

- [ ] **Step 2: Wait for the natural cron cycle to provide runs 4 + 5**

The workflow runs on weekly cron Monday 07:00 UTC. The 3 empty-commit
runs above plus the next 2 PR-`synchronize` events (any review comment,
amend, or rebase counts) make 5. Track them:

```bash
gh run list --workflow=skill-test.yml --branch unsafecode/pr-review \
  --limit 5 --json conclusion,createdAt,displayTitle,headSha
```

- [ ] **Step 3: If any of the 5 fail on a NON-classified-transient cause, STOP and triage**

A non-transient failure during pilot means the design is broken. Quarantine is NOT acceptable as a pilot exit. Fix the root cause (likely: fixture too brittle, or SKILL.md missed a bug class) and reset the 5-run counter.

Transient causes documented during Task 2.1 (allowed retry without
reset):
- `gpt-5.4-mini` 429 quota (rare; back off + retry on next push)
- Foundry agent creation timing out (back off 30s, retry once)
- ACR auth token race during parallel runner startup

Anything else — especially anything that looks like a SKILL.md prose
bug — is a STOP-and-triage event.

- [ ] **Step 4: Triage the deferred items from each pilot's audit trail
      BEFORE declaring exit**

Each pilot audit-trail file has an "Open items" / "Deferred" section.
Task 2.1's deferred set is in
`docs/audit/foundry-prompt-agents-audit-trail.md` (Class 11 cross-skill
drift in `foundry-iq` / `foundry-doc-vision-speech` / `azd-patterns`;
KI-002/003 A/B rigor; L95 audience parity). Pilot exit means each
deferred item has either landed a follow-up PR or been explicitly
re-scoped to Phase 3 with a written rationale in the audit-trail file.

- [ ] **Step 5: When 5/5 green AND deferred items triaged, open the rollout-go-ahead issue**

```bash
gh issue create --title "Phase 2 pilot exit criteria met — Phase 3 rollout cleared" \
  --body "5 consecutive green copilot-cli-matrix runs across all three pilot fixtures (foundry-prompt-agents, foundry-hosted-agents, azd-patterns). Run URLs:
- run 1: <url>
- run 2: <url>
- run 3: <url>
- run 4: <url>
- run 5: <url>

Deferred items from pilot audits: triaged (see audit-trail files).

Phase 3 rollout authorized."
```

---

## Phase 3 · Rollout (22 skills via agent army)

The same kind of work done in Phase 2, but per-skill via autonomous sub-agents. One `general-purpose` agent per skill, cap 5 concurrent, one PR each. Reviewer time is the only bottleneck.

### Task 3.1 · Author the audit-agent prompt template

**Files:**
- Create: `docs/superpowers/plans/2026-05-30-audit-agent-prompt-template.md`

- [ ] **Step 1: Write the template**

```markdown
<!-- docs/superpowers/plans/2026-05-30-audit-agent-prompt-template.md -->

# Audit-Agent Prompt Template (Phase 3 rollout)

This template is interpolated per skill. Replace `{SKILL_NAME}` and run as a
`general-purpose` `task` agent in background mode.

---

## Prompt body

You are auditing the `{SKILL_NAME}` skill in `aiappsgbb/awesome-gbb` against
a 21-item bug-class catalog. Open a PR that does three things in a SINGLE
branch: (a) fix every bug you find, (b) create
`skills/{SKILL_NAME}/test-fixture/consumer_prompt.md`, (c) create
`docs/audit/{SKILL_NAME}-audit-trail.md`.

### Mandatory clauses (verbatim, do not paraphrase)

1. **Anti-normalization (§4 of AGENTS.md):** Reference data under
   `skills/{SKILL_NAME}/references/data-realism/` (if present) is canonical
   published shorthand. Do NOT normalize whitespace, capitalization, number
   widths, or formatting. If you see a single-digit code that "looks
   wrong", it is correct per the cited spec. STOP and ask before editing.
2. **Scope:** You may edit ONLY files under `skills/{SKILL_NAME}/` plus the
   single new file `docs/audit/{SKILL_NAME}-audit-trail.md`. The PR commit
   message MUST include the tag `[audit-2026-Q2]`. The automation-pr-gate
   accepts multi-file edits within this scope only with that tag.
3. **No pytest:** Do NOT add any file under `scripts/tests/`. Do NOT add
   any Python test code anywhere. The test mechanism is `copilot run
   --prompt-file <fixture>` executed by GHA. Adding pytest helpers
   reintroduces the exact drift the spec eliminates.
4. **Verbatim reference cross-link:** If the skill has `references/<lang>/`
   files that are referenced in SKILL.md, follow the SSOT rule in
   AGENTS.md §7: do not duplicate code bodies inline.

### 21-item bug-class catalog (scan SKILL.md + all references against each)

1. Credential type bugs (MID-I) — sync credential in async-only client
2. Endpoint URL bugs (MID-G project vs account)
3. Wrong model names
4. Wrong RBAC role names
5. Wrong API scopes
6. Wrong env-var names
7. Hardcoded GUIDs
8. Deprecated SDK calls
9. Bicep module drift
10. Bicep param mismatches
11. Cross-skill contradictions
12. Container probe misconfigurations
13. Wrong region defaults
14. JSON/YAML escaping in agent prompts
15. Reference ↔ SKILL.md drift
16. Missing `dependsOn` (RBAC race)
17. Tool wrapper type mismatches (dict vs Pydantic)
18. Bot/webhook signature bugs
19. Logging exposure (secrets, PII)
20. Async/sync mismatches beyond credentials
21. Outdated package pins (beyond what the freshness loop catches)

For each class, record "found at <file>:<line>, fix: <description>" OR
"none observed" in the audit-trail file. Do not skip a class.

### Fixture authoring rules

- Single-task prompt. Specific. Short. Self-verifying (asserts a string
  or exit code).
- Uses `$AZURE_AI_ENDPOINT`, deployment `gpt-5.4-mini`,
  `acrawesomegbbci.azurecr.io` for image pushes. Uses a unique
  `<short-uuid>` suffix on every resource it creates so concurrent matrix
  runs don't collide.
- Tears down ALL resources it creates before exiting 0.
- Exits non-zero with a specific error message if any step fails.
- Does NOT call `pytest` or shell out to Python test code. The
  Copilot CLI is the test runner.

### Audit-trail format

See `docs/audit/README.md`. Required fields: Auditor, Date, per-class
findings, fixture link, CI run URL (filled in after Step 5 below), open
items.

### PR steps

1. Branch from `main`: `unsafecode/audit-{SKILL_NAME}-2026-q2`.
2. Make all fixes + author fixture + author audit-trail in this branch.
3. Open PR with title `audit({SKILL_NAME}): 2026-Q2 deep audit + Copilot-CLI fixture`.
4. PR body MUST include the list of bug-class findings + a link to
   `docs/audit/{SKILL_NAME}-audit-trail.md`.
5. Watch `copilot-cli-matrix ({SKILL_NAME})` — it MUST go green before
   you self-merge. If it fails 3 consecutive runs (including the retry),
   do NOT add `{SKILL_NAME}` to `.github/quarantine.yml` yourself —
   open an issue requesting human triage.
6. When green, update the audit-trail with the CI run URL.
7. Squash-merge into `main` with the auto-merge tag if all checks pass.

### Do NOT

- Touch any skill other than `{SKILL_NAME}`.
- Add pytest files anywhere.
- Modify `.github/workflows/*`, `AGENTS.md`, `plugin.json`, or
  `marketplace.json`. Those are in Phase 4.
- Edit `references/data-realism/` content (anti-normalization rule).
- Auto-quarantine on failure. Open an issue instead.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-05-30-audit-agent-prompt-template.md
git commit -m "plan(rollout): audit-agent prompt template for Phase 3

Per spec 2026-05-30 Phase 3. One general-purpose agent per skill,
cap 5 concurrent. Verbatim 21-class catalog + verbatim anti-normalization
clause + no-pytest scope clause.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3.2 · Dispatch the agent army (22 skills, cap 5 concurrent)

**Files:** (no direct commits in this task; each agent commits its own PR)

The 22 rollout skills (27 total − 3 pilot − 2 manual):

| # | Skill | Wave |
|---|---|---|
| 1 | auto-demo-producer | A |
| 2 | azure-sre-agent | A |
| 3 | azure-tenant-isolation | A |
| 4 | citadel-spoke-onboarding | A |
| 5 | foundry-agt | A |
| 6 | foundry-cross-resource | B |
| 7 | foundry-doc-vision-speech | B |
| 8 | foundry-evals | B |
| 9 | foundry-iq | B |
| 10 | foundry-mcp-aca | B |
| 11 | foundry-memory | C |
| 12 | foundry-observability | C |
| 13 | foundry-skill-catalog | C |
| 14 | foundry-teams-bot | C |
| 15 | foundry-toolbox | C |
| 16 | foundry-voice-live | D |
| 17 | gbb-humanizer | D |
| 18 | gbb-pptx | D |
| 19 | ghcp-cli-config | D |
| 20 | ghcp-hosted-agents | D |
| 21 | ip-catalog | E |
| 22 | paygo-ptu-cost-analyzer | E |

Waves are processing units only — 5 agents in flight, replace as each completes. Concurrency is enforced by GHA `max-parallel: 5` AND by the dispatcher (this task) launching no more than 5 at once.

- [ ] **Step 1: For each skill in Wave A, launch a `general-purpose` agent in background mode**

Use the `task` tool with `agent_type: general-purpose`, `mode: background`. Prompt = the template from Task 3.1 with `{SKILL_NAME}` replaced. Example for `auto-demo-producer`:

```
task(
  agent_type="general-purpose",
  mode="background",
  name="audit-auto-demo-producer",
  description="2026-Q2 deep audit + fixture for auto-demo-producer",
  prompt=<contents of docs/superpowers/plans/2026-05-30-audit-agent-prompt-template.md with {SKILL_NAME} → auto-demo-producer>
)
```

- [ ] **Step 2: Wait for the 5 agents in Wave A to complete (notifications arrive automatically)**

When each completes, retrieve its result with `read_agent` and review the PR it opened. Specifically check:
- PR commits ONLY touch `skills/<name>/` and `docs/audit/<name>-audit-trail.md`
- PR commit message contains `[audit-2026-Q2]`
- `copilot-cli-matrix (<skill>)` is green on the PR
- Audit-trail file has all 21 classes addressed (not just "none observed" for all of them — if zero findings on a skill, spot-check the PR yourself)

- [ ] **Step 3: Squash-merge the PR or send the agent a fix request**

If a PR is good, merge it. If it has issues, send the agent a `write_agent` message with the specific concern (e.g., "Class 11 cross-skill contradictions section is blank — re-scan against foundry-hosted-agents references"). Do not micro-manage; the agent is autonomous.

- [ ] **Step 4: Launch Wave B (5 more agents). Repeat for Waves C, D, E**

- [ ] **Step 5: When all 22 PRs are merged, verify the matrix runs all 25 skills green**

```bash
gh workflow run skill-test.yml
gh run watch
```

Expected: 25 successful matrix legs (3 pilot + 22 rollout). If any are RED on a non-transient cause, that's a Phase 3 reopen — surface to the user before proceeding to Phase 4.

---

### Task 3.3 · Reconciliation — verify every skill (except the 2 manual) has a fixture

**Files:** (verification only; commits land in Phase 4)

- [ ] **Step 1: Diff the expected set against the actual set**

```bash
EXPECTED=$(ls skills | grep -v '^README.md$' | grep -v '^citadel-hub-deploy$' | grep -v '^foundry-vnet-deploy$' | sort)
ACTUAL=$(find skills -path '*/test-fixture/consumer_prompt.md' | sed -E 's|skills/([^/]+)/.*|\1|' | sort)
diff <(echo "$EXPECTED") <(echo "$ACTUAL")
```

Expected: no output (sets identical).

- [ ] **Step 2: Diff audit-trail files**

```bash
EXPECTED=$(ls skills | grep -v '^README.md$' | grep -v '^citadel-hub-deploy$' | grep -v '^foundry-vnet-deploy$' | sort)
ACTUAL=$(ls docs/audit/*-audit-trail.md | sed -E 's|docs/audit/(.+)-audit-trail.md|\1|' | sort)
diff <(echo "$EXPECTED") <(echo "$ACTUAL")
```

Expected: no output.

- [ ] **Step 3: If gaps exist, dispatch a follow-up agent for each gap before moving to Phase 4**

---

## Phase 4 · Cleanup

The new mechanism is live and green across all 25 fixturized skills. Remove the legacy pytest tests, prune `skill-test.yml`, rewrite the affected AGENTS.md sections, and bump versions.

### Task 4.1 · Delete the three `test_e2e_*.py` files

**Files:**
- Delete: `scripts/tests/test_e2e_prompt_agents.py`
- Delete: `scripts/tests/test_e2e_foundry_toolbox.py`
- Delete: `scripts/tests/test_e2e_voice_live.py`

- [ ] **Step 1: Confirm no other code imports from them**

```bash
grep -rn "from scripts.tests.test_e2e" .
grep -rn "test_e2e_prompt_agents\|test_e2e_foundry_toolbox\|test_e2e_voice_live" .github/workflows/
```

Expected: only the workflow file `skill-test.yml` references them (in the about-to-be-deleted `e2e-azure` job).

- [ ] **Step 2: Delete the files**

```bash
git rm scripts/tests/test_e2e_prompt_agents.py
git rm scripts/tests/test_e2e_foundry_toolbox.py
git rm scripts/tests/test_e2e_voice_live.py
```

- [ ] **Step 3: Verify directory still contains the surviving unit tests**

```bash
ls scripts/tests/
# Expected:
#   test_automation_pr_gate.py
#   test_build_test_matrix.py
#   test_validate_skills.py
```

The `scripts/tests/` directory STAYS (resolved spec ambiguity — see File Structure section above).

- [ ] **Step 4: Commit**

```bash
git commit -m "test: delete legacy E2E pytest files (smoking gun + sibling drift)

Per spec 2026-05-30 §9.2. These tests proved 'pip install + import',
not 'the SKILL works'. test_e2e_foundry_toolbox.py L41-49 was the
exact MID-I bug the catalog's own AST lint catches inside skills/ —
hand-written test code mirroring but contradicting the SKILL is false
confidence. The copilot-cli-matrix job (skill-test.yml) replaces them.

scripts/tests/ directory stays — test_automation_pr_gate.py and
test_validate_skills.py protect surviving CI infrastructure.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4.2 · Delete `pin-smoke` + `e2e-azure` jobs from `skill-test.yml`

**Files:**
- Modify: `.github/workflows/skill-test.yml`

- [ ] **Step 1: Read the file + locate the two jobs**

```bash
grep -nE "^  (pin-smoke|e2e-azure|copilot-cli-matrix|build-matrix):" .github/workflows/skill-test.yml
```

- [ ] **Step 2: Delete the two job blocks**

Edit `.github/workflows/skill-test.yml`. Remove the entire `pin-smoke:` and `e2e-azure:` blocks (from job key through last indented line). Keep `build-matrix:` and `copilot-cli-matrix:` (added in Task 2.1).

- [ ] **Step 3: Verify YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/skill-test.yml'))"
```

- [ ] **Step 4: Dispatch the workflow + verify it runs without those jobs**

```bash
gh workflow run skill-test.yml
gh run watch
```

Expected: only `build-matrix` + `copilot-cli-matrix` matrix legs run.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/skill-test.yml
git commit -m "ci(skill-test): delete pin-smoke + e2e-azure jobs

Per spec 2026-05-30 §9.2. Both jobs are replaced by copilot-cli-matrix,
which exercises every skill end-to-end against real Azure via the
Copilot CLI consuming the skill's test-fixture/consumer_prompt.md.
pip+import was insufficient (see deleted test_e2e_*.py rationale).

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4.3 · Create the weekly cost-summary workflow

**Files:**
- Create: `.github/workflows/copilot-cli-cost-summary.yml`

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/copilot-cli-cost-summary.yml
name: copilot-cli-cost-summary

on:
  schedule:
    - cron: "0 7 * * 1"   # Monday 07:00 UTC
  workflow_dispatch:

permissions:
  contents: read
  issues: write
  actions: read

jobs:
  summarize:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Fetch last 7 days of copilot-cli-matrix runs
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh run list --workflow=skill-test.yml --created ">=$(date -u -d '7 days ago' +%Y-%m-%d)" \
            --json conclusion,createdAt,displayTitle,databaseId,durationMS \
            > /tmp/runs.json
          cat /tmp/runs.json | jq .

      - name: Open weekly cost-telemetry issue
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -euo pipefail
          TOTAL_MIN=$(jq '[.[].durationMS] | add / 60000' /tmp/runs.json)
          GREEN=$(jq '[.[] | select(.conclusion=="success")] | length' /tmp/runs.json)
          RED=$(jq '[.[] | select(.conclusion=="failure")] | length' /tmp/runs.json)
          BODY=$(printf '## Weekly cost summary — %s\n\nRuns: green=%s, red=%s\nTotal runner minutes: %s\n\nPer spec §8.1 we track this to keep the design within budget.\n' \
            "$(date -u +%Y-%m-%d)" "$GREEN" "$RED" "$TOTAL_MIN")
          gh issue create \
            --title "💸 Copilot-CLI matrix cost summary — $(date -u +%Y-%m-%d)" \
            --body "$BODY" \
            --label "cost-telemetry"
```

- [ ] **Step 2: Commit + dispatch once to verify**

```bash
git add .github/workflows/copilot-cli-cost-summary.yml
git commit -m "ci: weekly Copilot-CLI matrix cost summary

Per spec 2026-05-30 §8.1. Opens a weekly issue with run counts +
runner minutes for the copilot-cli-matrix job, so cost stays
visible.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push
gh workflow run copilot-cli-cost-summary.yml
gh run watch
```

Expected: workflow green; an issue titled "💸 Copilot-CLI matrix cost summary — 2026-05-30" is opened.

---

### Task 4.4 · Rewrite AGENTS.md §§ 2.7, 2.8, 2.9, 9.6, 9.8, 12.5

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: § 2.7 — replace the 4-tier table**

Find the section header `### 2.7 Skills must be tested` and replace the table + bullets with:

```markdown
### 2.7 Skills must be tested by the Copilot CLI consuming them

The catalog's test mechanism is: a real `copilot run --prompt-file
skills/<name>/test-fixture/consumer_prompt.md` invocation, executed by
`.github/workflows/skill-test.yml :: copilot-cli-matrix`, against a real
Azure Foundry-hosted `gpt-5.4-mini` deployment.

There are exactly two test tiers:

| Tier | Name | What it proves | When required | Enforced by |
|------|------|----------------|---------------|-------------|
| **T0** | Static lints | Frontmatter parses, description ≤ 1024, no forbidden strings, AST lints (sync-cred check, MID-I/MID-G detectors, reference/SKILL.md drift) | Every PR | `skill-validation.yml` |
| **T1** | Copilot-CLI matrix | A real Copilot CLI session consumes the SKILL and reaches the documented happy path against real Azure | Every PR touching `skills/**`; weekly cron | `skill-test.yml :: copilot-cli-matrix` |

There is NO parallel pytest layer. Hand-written test code that mirrors a
SKILL is by definition drift waiting to happen — that's why
`scripts/tests/test_e2e_foundry_toolbox.py` paired a sync credential
with an async-only client for months without anyone noticing. The whole
class of bug is now structurally impossible: there is no parallel test
code to drift from.

Skills excluded from T1 in CI (multi-resource greenfield deploy, validated
manually only): `citadel-hub-deploy`, `foundry-vnet-deploy`.
```

- [ ] **Step 2: § 2.8 — replace with the Copilot-CLI rule**

Find `### 2.8 Skills that connect to Azure MUST have E2E tests` and replace:

```markdown
### 2.8 Skills that connect to Azure MUST have a Copilot-CLI fixture

If SKILL.md tells consumers to call an Azure endpoint, provision a
resource, or authenticate with `DefaultAzureCredential`, the catalog
MUST prove that path works **by having a real Copilot CLI session
execute the SKILL** — not by running pytest-style assertions.

- ✅ Add `skills/<name>/test-fixture/consumer_prompt.md` — a single-task,
  self-verifying prompt the Copilot CLI executes against
  `rg-awesome-gbb-ci` infrastructure (§ 9.7).
- ✅ The fixture creates unique resources with a `<short-uuid>` suffix
  and tears them down before exiting.
- ✅ `copilot-cli-matrix` picks up the skill automatically once the
  fixture exists (`scripts/build-test-matrix.py` scan).
- ❌ Do NOT add pytest files anywhere. The 2026-Q2 testing rebuild
  deleted that layer for cause; reintroducing it via the back door is a
  PR-blocker.
- ❌ "I tested locally" is NOT sufficient — CI must reproduce it.

**Exceptions** (too complex for CI, manually validated only):
`citadel-hub-deploy`, `foundry-vnet-deploy`.
```

- [ ] **Step 3: § 2.9 — keep the "nothing lands without Azure test" rule, retarget at the new mechanism**

Find `### 2.9 Nothing lands on main unless tested on Azure`. Keep the rule and tone; replace specific guidance to point at `copilot-cli-matrix` instead of pytest, and replace the "Who tests" table's "AI agents" row to say "must verify the skill's `consumer_prompt.md` runs green in `copilot-cli-matrix` on the PR — pytest helpers are forbidden".

- [ ] **Step 4: § 9.6 — collapse the 6-gate table to the 5 surviving gates**

Delete the `pin-smoke` and `e2e-azure` mentions. Add `copilot-cli-matrix` as the live-Azure gate. The 5 gates now: `skill-validation`, `automation-pr-gate`, `pin-validation`, `copilot-cli-matrix` (now the live layer), `skill-freshness`, `auto-merge-copilot`. Update the table accordingly. Also update the cron-timing diagram.

- [ ] **Step 5: § 9.8 — replace the 4-tier section with a back-reference to § 2.7**

```markdown
### 9.8 · Skill testing tiers

See § 2.7. The 2026-Q2 testing rebuild collapsed T2 (pin smoke) and T3
(pytest E2E) into a single T1 layer: the `copilot-cli-matrix` job in
`skill-test.yml`. The Copilot CLI is the test runner; the
`consumer_prompt.md` fixture is the test surface.
```

- [ ] **Step 6: § 12.5 — update catalog stats**

Find the "Catalog at a glance" table. Update:
- "CI workflows": from 6 to 7 (+ `copilot-cli-foundry-auth-smoke.yml` and `copilot-cli-cost-summary.yml`, − the implicit retired counts in old text)
- "Unit tests": rebase the number against the actual count after Task 4.1 deletions (`pytest --collect-only scripts/tests/ -q | tail -1`)
- "Azure E2E resources": add "Foundry-routed gpt-5.4-mini for Copilot CLI"
- Remove the "T2/T3" distinction from any prose

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md
git commit -m "docs(AGENTS): rewrite §§ 2.7-2.9, 9.6, 9.8, 12.5 for 2026-Q2 testing rebuild

Per spec 2026-05-30 §9.2. Two tiers (T0 static + T1 copilot-cli-matrix),
no pytest helpers for skills, 7 CI workflows (added auth-smoke +
cost-summary, retained automation-pr-gate / skill-validation /
pin-validation / skill-freshness / auto-merge-copilot, retired
pin-smoke + e2e-azure jobs).

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4.5 · Version bumps + final verification

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`

- [ ] **Step 1: Read current versions**

```bash
jq -r .version plugin.json
jq -r '.plugins[0].version' .github/plugin/marketplace.json
```

- [ ] **Step 2: Bump PATCH on both**

Per § 5.1, this whole project is testing-infrastructure churn — no new skill, no rename — so PATCH. Apply manually (jq inline edit if you prefer).

- [ ] **Step 3: Verify both match**

```bash
diff <(jq -r .version plugin.json) <(jq -r '.plugins[0].version' .github/plugin/marketplace.json)
```

Expected: empty diff.

- [ ] **Step 4: Run the full repo validators**

```bash
python scripts/validate-skills.py
python scripts/build-plugins.py --check
pytest scripts/tests/test_automation_pr_gate.py scripts/tests/test_validate_skills.py scripts/tests/test_build_test_matrix.py -v
gh workflow run skill-test.yml
gh run watch
```

Expected: all green; matrix runs 25 skills green.

- [ ] **Step 5: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json
git commit -m "chore: bump plugin version for 2026-Q2 testing rebuild

Per spec 2026-05-30 + § 5.1 (PATCH — infrastructure churn, no skill add
or rename).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Open Items + Watch-Outs

These are documented here so any executing engineer (human or agent) doesn't surprise themselves mid-flight.

1. **Task 1.0 is a hard gate.** If the released Copilot CLI doesn't support Foundry routing in GHA, the plan halts at Task 1.0 Step 4. Surface this to the user immediately; do not proceed.

2. **Quarantine is a circuit-breaker, not a workflow.** Adding a skill to `.github/quarantine.yml` is a last-resort move that REQUIRES a tracking issue (per § 8.4 and the file's header comment). Agents in Phase 3 are forbidden from auto-quarantining — they must open an issue requesting human triage. Honour this.

3. **Cost is the silent failure mode.** Each matrix leg runs `azd up` / `azd down` cycles. The cost-summary workflow (Task 4.3) is the early warning. If runner minutes balloon past 200/week, narrow the cron trigger (currently weekly) or shrink fixtures (use `azd provision --preview` instead of full deploys for skills where the SKILL.md happy path doesn't strictly require deploy).

4. **Pilot exit criteria are not negotiable.** 5 consecutive green matrix runs across the 3 pilot skills. Non-transient failures reset the count. Do NOT relax this to ship Phase 3 sooner.

5. **The smoking gun is Exhibit A.** Anyone arguing "we should keep a pytest layer for safety" should be pointed at `scripts/tests/test_e2e_foundry_toolbox.py` L41-49 (spec Appendix B). That file paired `AzureCliCredential` (sync) with `FoundryChatClient` (async-only) — the exact MID-I bug the catalog's own AST lint catches inside `skills/`. The test passed for months. False confidence is worse than no test.
