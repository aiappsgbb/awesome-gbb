# Manual Freshness Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reversible manual execution mode to the existing freshness detector while preserving issue detection, exact impact labels, reports, and the Copilot assignment path.

**Architecture:** `scripts/check-freshness.py` owns execution-mode semantics and issue ownership reconciliation; `.github/workflows/skill-freshness.yml` selects `manual` or `copilot` from a repository variable with a dispatch override. Manual mode adds `manual-review`, removes only the Copilot bot while preserving human assignees, and fails visibly if ownership reconciliation fails.

**Tech Stack:** Python 3.12, `unittest`, GitHub REST + GraphQL APIs, GitHub Actions YAML, `gh` CLI, static documentation generator.

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `scripts/tests/test_check_freshness_issue_mode.py` | Create | Regression tests for labels, report wording, and bot removal |
| `scripts/check-freshness.py` | Modify | Execution-mode CLI, label selection, report wording, ownership reconciliation |
| `.github/workflows/skill-freshness.yml` | Modify | Repository-variable mode plus dispatch override |
| `docs/maintenance/manual-skill-freshness.md` | Create | Operator runbook |
| `README.md` | Modify | Describe dual manual/Copilot freshness loop |
| `AGENTS.md` | Modify | Make manual mode part of the catalog contract |
| `docs/**` | Regenerate | Publish updated catalog documentation |

---

### Task 1: Establish the baseline

**Files:**
- Verify only: repository and current detector

- [ ] **Step 1: Confirm a clean worktree**

Run:

```bash
git status --short
git --no-pager log -3 --oneline
```

Expected: no uncommitted changes; the approved design and plan commits are at
the top of history.

- [ ] **Step 2: Run the current detector tests**

Run:

```bash
python3 -m unittest scripts.tests.test_check_freshness_pkg_drift -v
```

Expected: all package-drift tests pass.

- [ ] **Step 3: Capture the current dry-run behavior**

Run:

```bash
GH_TOKEN="$(gh auth token)" \
python3 scripts/check-freshness.py \
  --upsert-issues \
  --consolidated \
  --assign-copilot-on-auto-tier \
  --labels freshness,automation \
  --dry-run \
  --print-report > /tmp/freshness-before.md
grep -E "assigned to @Copilot|would assign" /tmp/freshness-before.md
```

Expected: auto-tier items are described as assigned to Copilot. This is the
behavior manual mode must make conditional.

---

### Task 2: Write failing execution-mode tests

**Files:**
- Create: `scripts/tests/test_check_freshness_issue_mode.py`

- [ ] **Step 1: Add focused `unittest` coverage**

Create the test module with the same `importlib.util` loading pattern used by
`test_check_freshness_pkg_drift.py`. Start the file with:

```python
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "check-freshness.py"
_SPEC = importlib.util.spec_from_file_location(
    "check_freshness_issue_mode", _SCRIPT
)
assert _SPEC and _SPEC.loader
CF = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = CF
_SPEC.loader.exec_module(CF)
```

Then add these tests:

```python
class ExecutionModeLabelsTest(unittest.TestCase):
    def test_manual_mode_adds_manual_review_and_replaces_old_impact(self):
        signal = CF.Signal(
            skill="demo",
            signal_type="consolidated",
            severity="medium",
            title="Refresh demo",
            body="body",
            automation_tier="auto",
            impact="medium",
        )
        labels = CF.labels_for_execution_mode(
            ["freshness", "automation", "impact:high"], signal, "manual"
        )
        self.assertEqual(
            labels,
            ["freshness", "automation", "manual-review", "impact:medium"],
        )

    def test_copilot_mode_removes_manual_review(self):
        signal = CF.Signal(
            skill="demo",
            signal_type="consolidated",
            severity="high",
            title="Refresh demo",
            body="body",
            automation_tier="auto",
            impact="high",
        )
        labels = CF.labels_for_execution_mode(
            ["freshness", "automation", "manual-review"], signal, "copilot"
        )
        self.assertEqual(labels, ["freshness", "automation", "impact:high"])

    def test_manual_report_never_claims_copilot_assignment(self):
        signal = CF.Signal(
            skill="demo",
            signal_type="consolidated",
            severity="high",
            title="Refresh demo",
            body="body",
            automation_tier="auto",
            impact="high",
        )
        report = CF.render_report(
            [signal], pin_count=1, consolidated=True, execution_mode="manual"
        )
        self.assertIn("manual review required", report)
        self.assertNotIn("assigned to @Copilot", report)
```

Add a bot-removal test that stubs `CF._graphql`, returns one bot plus one human
from the query, and asserts the mutation receives only the human actor ID:

```python
class RemoveCopilotAssignmentTest(unittest.TestCase):
    def setUp(self):
        self.original_graphql = CF._graphql

    def tearDown(self):
        CF._graphql = self.original_graphql

    def test_removal_preserves_human_assignees(self):
        calls = []

        def fake_graphql(query, variables, _token):
            calls.append((query, variables))
            if "mutation" not in query:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"id": "BOT", "login": "copilot-swe-agent"},
                                    {"id": "HUMAN", "login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            self.assertEqual(variables["actors"], ["HUMAN"])
            return {
                "replaceActorsForAssignable": {
                    "assignable": {
                        "number": 42,
                        "assignees": {
                            "nodes": [{"id": "HUMAN", "login": "maintainer"}]
                        },
                    }
                }
            }

        CF._graphql = fake_graphql
        self.assertTrue(
            CF.remove_copilot_from_issue("aiappsgbb/awesome-gbb", 42, "token")
        )
        self.assertEqual(len(calls), 2)
```

- [ ] **Step 2: Run the new tests and verify red**

Run:

```bash
python3 -m unittest scripts.tests.test_check_freshness_issue_mode -v
```

Expected: errors for missing `labels_for_execution_mode`,
`remove_copilot_from_issue`, and the new `render_report` parameter.

- [ ] **Step 3: Commit the red tests**

```bash
git add scripts/tests/test_check_freshness_issue_mode.py
git commit -m "test: define manual freshness mode contract

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Implement execution-mode semantics

**Files:**
- Modify: `scripts/check-freshness.py:71-218`
- Modify: `scripts/check-freshness.py:845-1000`
- Modify: `scripts/check-freshness.py:1063-1166`

- [ ] **Step 1: Add mode constants and exact label selection**

Add:

```python
EXECUTION_MODES = ("manual", "copilot")
MANUAL_REVIEW_LABEL = "manual-review"


def labels_for_execution_mode(
    base_labels: list[str], signal: Signal, execution_mode: str
) -> list[str]:
    if execution_mode not in EXECUTION_MODES:
        raise ValueError(f"unsupported execution mode: {execution_mode}")
    labels = [
        label
        for label in base_labels
        if label != MANUAL_REVIEW_LABEL and not label.startswith("impact:")
    ]
    if execution_mode == "manual":
        labels.append(MANUAL_REVIEW_LABEL)
    if signal.signal_type == "consolidated":
        labels.append(f"impact:{signal.impact}")
    return list(dict.fromkeys(labels))
```

Place this after the `Signal`/impact definitions so the type is available.

- [ ] **Step 2: Add bot-only assignment removal**

Add `remove_copilot_from_issue(repo, issue_number, gh_token) -> bool` beside
`assign_copilot_to_issue`:

```python
def remove_copilot_from_issue(
    repo: str, issue_number: int, gh_token: str
) -> bool:
    token = os.environ.get("GH_ASSIGN_TOKEN") or gh_token
    owner, _, name = repo.partition("/")
    try:
        data = _graphql(
            """
            query($owner:String!, $name:String!, $num:Int!) {
              repository(owner:$owner, name:$name) {
                issue(number:$num) {
                  id
                  assignees(first:100) { nodes { id login } }
                }
              }
            }
            """,
            {"owner": owner, "name": name, "num": issue_number},
            token,
        )
        issue = data["repository"]["issue"]
        assignees = issue["assignees"]["nodes"]
        if not any(a["login"] == COPILOT_BOT_LOGIN for a in assignees):
            return True
        remaining_ids = [
            a["id"] for a in assignees if a["login"] != COPILOT_BOT_LOGIN
        ]
        data = _graphql(
            """
            mutation($assignable:ID!, $actors:[ID!]!) {
              replaceActorsForAssignable(
                input:{assignableId:$assignable, actorIds:$actors}
              ) {
                assignable {
                  ... on Issue {
                    number
                    assignees(first:100) { nodes { id login } }
                  }
                }
              }
            }
            """,
            {"assignable": issue["id"], "actors": remaining_ids},
            token,
        )
        assigned = data["replaceActorsForAssignable"]["assignable"][
            "assignees"
        ]["nodes"]
        return not any(a["login"] == COPILOT_BOT_LOGIN for a in assigned)
    except Exception as exc:  # Match existing best-effort GraphQL boundary.
        print(
            f"WARN: remove @{COPILOT_BOT_LOGIN} from issue "
            f"#{issue_number} failed: {exc}",
            file=sys.stderr,
        )
        return False
```

This preserves all non-Copilot assignees and changes no issue content.
      }
    }
  }
}
```

- [ ] **Step 3: Make report ownership wording mode-aware**

Change `render_report` to accept `execution_mode: str = "manual"`. For both
legacy and consolidated reports use:

```python
if s.automation_tier != "auto":
    assignee_note = " — human action required"
elif execution_mode == "copilot":
    assignee_note = " — assigned to @Copilot"
else:
    assignee_note = " — manual review required"
```

- [ ] **Step 4: Make issue upsert mode-aware**

Replace the `assign_copilot` parameter with `execution_mode`. Build labels
through:

```python
issue_labels = labels_for_execution_mode(labels, signal, execution_mode)
want_copilot_assign = (
    execution_mode == "copilot" and signal.automation_tier == "auto"
)
want_copilot_remove = execution_mode == "manual" and matched is not None
```

After a successful edit:

- in `copilot` mode, assign Copilot for auto-tier signals;
- in `manual` mode, remove Copilot while preserving human assignees;
- in dry-run mode, print the ownership action without calling GraphQL.

Return `False` on REST or ownership failure and `True` on success/dry-run:

```python
if want_copilot_remove:
    issue_number = r.json().get("number")
    if not issue_number or not remove_copilot_from_issue(
        repo, issue_number, gh_token
    ):
        return False
return True
```

Aggregate results in `main()`:

```python
issue_results = [
    upsert_issue(
        signal,
        repo=args.repo,
        gh_token=gh_token or "",
        execution_mode=execution_mode,
        labels=labels,
        dry_run=args.dry_run,
    )
    for signal in issue_signals
]
if not all(issue_results):
    return 1
```

- [ ] **Step 5: Add the CLI mode and preserve the old flag as an alias**

Add:

```python
ap.add_argument(
    "--execution-mode",
    choices=EXECUTION_MODES,
    default=None,
    help="issue ownership mode (default: manual)",
)
```

Keep `--assign-copilot-on-auto-tier` temporarily. Reject use of both flags;
otherwise resolve:

```python
if args.execution_mode and args.assign_copilot_on_auto_tier:
    ap.error(
        "--execution-mode and --assign-copilot-on-auto-tier "
        "cannot be used together"
    )
execution_mode = (
    args.execution_mode
    or ("copilot" if args.assign_copilot_on_auto_tier else "manual")
)
```

Pass the resolved mode to report rendering and every issue upsert.

- [ ] **Step 6: Run focused tests**

Run:

```bash
python3 -m unittest \
  scripts.tests.test_check_freshness_issue_mode \
  scripts.tests.test_check_freshness_pkg_drift -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add scripts/check-freshness.py scripts/tests/test_check_freshness_issue_mode.py
git commit -m "feat: add manual freshness execution mode

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Wire the workflow mode selector

**Files:**
- Modify: `.github/workflows/skill-freshness.yml:9-51`

- [ ] **Step 1: Add a dispatch override**

Under `workflow_dispatch.inputs`, add:

```yaml
      execution_mode:
        description: "Execution mode override"
        type: choice
        options:
          - repository
          - manual
          - copilot
        default: repository
```

- [ ] **Step 2: Resolve the repository variable safely**

In the detector step add:

```yaml
          CONFIGURED_MODE: ${{ vars.FRESHNESS_EXECUTION_MODE || 'manual' }}
          DISPATCH_MODE: ${{ inputs.execution_mode || 'repository' }}
```

Replace the hard-coded assignment flag with:

```bash
MODE="$CONFIGURED_MODE"
if [ "$DISPATCH_MODE" != "repository" ]; then
  MODE="$DISPATCH_MODE"
fi
case "$MODE" in
  manual|copilot) ;;
  *) echo "::error::Invalid FRESHNESS_EXECUTION_MODE=$MODE"; exit 2 ;;
esac
ARGS="--upsert-issues --consolidated --execution-mode $MODE --labels freshness,automation --output report.md --print-report"
```

Keep the existing dry-run branch.

- [ ] **Step 3: Parse the workflow and run a local dry run**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import yaml
yaml.safe_load(Path(".github/workflows/skill-freshness.yml").read_text())
print("workflow yaml: OK")
PY
GH_TOKEN="$(gh auth token)" python3 scripts/check-freshness.py \
  --upsert-issues --consolidated --execution-mode manual \
  --labels freshness,automation --dry-run --print-report \
  > /tmp/freshness-manual.md
grep -q "manual review required" /tmp/freshness-manual.md
! grep -q "assigned to @Copilot" /tmp/freshness-manual.md
```

Expected: `workflow yaml: OK`; both grep assertions succeed.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/skill-freshness.yml
git commit -m "ci: make freshness execution mode reversible

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Document manual operation

**Files:**
- Create: `docs/maintenance/manual-skill-freshness.md`
- Modify: `README.md:276-292,350-366`
- Modify: `AGENTS.md:608-614,635-660,737-743,2933-2937`

- [ ] **Step 1: Write the operator runbook**

The runbook must contain these exact procedures:

1. Set manual mode:
   `gh variable set FRESHNESS_EXECUTION_MODE --repo aiappsgbb/awesome-gbb --body manual`.
2. Preview:
   `gh workflow run skill-freshness.yml --repo aiappsgbb/awesome-gbb -f dry_run=true -f execution_mode=repository`.
3. Run live:
   `gh workflow run skill-freshness.yml --repo aiappsgbb/awesome-gbb -f dry_run=false -f execution_mode=repository`.
4. Inspect:
   `gh run list --repo aiappsgbb/awesome-gbb --workflow "Skill freshness" --limit 5`.
5. Restore Copilot mode by setting the variable to `copilot`, dry-running,
   then running live once.
6. Failure behavior: return to `manual`; never disable detection.

- [ ] **Step 2: Update README and AGENTS**

Replace unconditional `@Copilot` wording with the dual-mode contract:
detection always runs; `manual` labels and unassigns; `copilot` assigns the
coding agent. Keep the existing delivery-loop documentation, explicitly scoped
to Copilot mode.

- [ ] **Step 3: Rebuild docs and validate**

Run:

```bash
python3 scripts/build-site.py --out docs/
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
git diff --check
```

Expected: every command exits `0`.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md README.md docs/ docs/maintenance/manual-skill-freshness.md
git commit -m "docs: add manual freshness operations

Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Deploy and prove manual mode

**Files:**
- No repository files; GitHub repository configuration

- [ ] **Step 1: Create the label**

Run:

```bash
gh label create manual-review \
  --repo aiappsgbb/awesome-gbb \
  --color FBCA04 \
  --description "Freshness item awaiting manual review" \
  --force
```

Expected: command exits `0`.

- [ ] **Step 2: Set the repository variable**

Run:

```bash
gh variable set FRESHNESS_EXECUTION_MODE \
  --repo aiappsgbb/awesome-gbb \
  --body manual
```

Expected: command exits `0`.

- [ ] **Step 3: Open and merge the infrastructure PR**

Open one PR containing only this plan's implementation. Required checks:
`validate`, `gate`, `validate-pins`, `unit-tests`, and `catalog-lint`.

- [ ] **Step 4: Dispatch a dry run after merge**

Run:

```bash
gh workflow run skill-freshness.yml \
  --repo aiappsgbb/awesome-gbb \
  --ref main \
  -f dry_run=true \
  -f execution_mode=repository
```

Expected: report says `manual review required`; no issue writes occur.

- [ ] **Step 5: Dispatch one live run**

Run the same command with `dry_run=false`. Verify a sample of critical, high,
and medium issues:

```bash
gh issue view 420 --repo aiappsgbb/awesome-gbb --json assignees,labels
gh issue view 429 --repo aiappsgbb/awesome-gbb --json assignees,labels
gh issue view 189 --repo aiappsgbb/awesome-gbb --json assignees,labels
```

Expected: no `copilot-swe-agent` assignee; `manual-review` present; exactly one
`impact:*` label matching the latest report.

- [ ] **Step 6: Verify the next scheduled run**

After the next Monday or Thursday 07:00 UTC schedule, verify the newest run
succeeded and preserved the same ownership/label contract.
