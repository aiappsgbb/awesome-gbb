#!/usr/bin/env python3
"""Contract tests for the `foundry-evals` pin's Foundry endpoint consumption.

PR #448 split the overloaded `AZURE_AI_ENDPOINT` secret into an
account-scoped secret and a project-scoped `FOUNDRY_PROJECT_ENDPOINT`
secret. The `foundry-evals` pin makes *project-scoped* Foundry calls
(`AIProjectClient` + `evals.*`), so both the runner gate for the
`foundry_project` requirement and the pin script itself must speak the
project secret.

These tests exercise the **real** runner module and the **real** pin
front-matter/script (parsed, not string-matched) so a gate/consumer
mismatch cannot pass silently.

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:
    python -m unittest discover -s scripts/tests -p 'test_*.py' -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import pathlib
import re
import subprocess
import tempfile
import unittest
import unittest.mock

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent
EVALS_SKILL = ROOT / "skills" / "foundry-evals"
EVALS_PIN = EVALS_SKILL / "references" / "upstream-pin.md"
EVALS_FIXTURE = EVALS_SKILL / "test-fixture" / "consumer_prompt.md"
SKILL_TEST_WORKFLOW = ROOT / ".github" / "workflows" / "skill-test.yml"
MATRIX_JOB = "copilot-cli-matrix"

ACCOUNT_ENV = "AZURE_AI_ENDPOINT"
PROJECT_ENV = "FOUNDRY_PROJECT_ENDPOINT"
ENDPOINT_ENVS = {ACCOUNT_ENV, PROJECT_ENV}


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "rpv_endpoint_contract", SCRIPTS / "run-pin-validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _hard_required_env(script: str) -> set[str]:
    """Env vars the script fails without.

    Covers both shell guards (`: "${VAR:?msg}"`) and unguarded Python
    lookups (`os.environ["VAR"]`), which raise `KeyError` when unset.
    """
    guards = re.findall(r"\$\{([A-Z][A-Z0-9_]*):\?", script)
    lookups = re.findall(
        r"os\.environ\[\s*[\"']([A-Z][A-Z0-9_]*)[\"']\s*\]", script
    )
    return set(guards) | set(lookups)


def _pin_frontmatter(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])


def _referenced_env(text: str) -> set[str]:
    """Env vars a prompt/shell body reads: `$VAR`, `${VAR}`, `${VAR:+x}`."""
    braced = re.findall(r"\$\{([A-Z][A-Z0-9_]*)[:}\-+?]", text)
    bare = re.findall(r"\$([A-Z][A-Z0-9_]*)\b", text)
    return set(braced) | set(bare)


def _load_matrix_workflow() -> dict:
    return yaml.safe_load(SKILL_TEST_WORKFLOW.read_text(encoding="utf-8"))


def _fixture_running_steps(workflow: dict) -> list[dict]:
    """Matrix steps that actually hand a fixture to the agent.

    Keyed off the real `copilot -p` invocation rather than step names or
    indices, both of which churn. Pattern 26 means there is more than one:
    the main run plus the transient-retry run(s).
    """
    return [
        step
        for step in workflow["jobs"][MATRIX_JOB]["steps"]
        if "copilot -p" in (step.get("run") or "")
    ]


def _missing_env_by_fixture_step(
    required: set[str], workflow: dict | None = None
) -> dict[str, list[str]]:
    """Per-step shortfall of `required` across every fixture-running step.

    Deliberately not a union over the job's steps: env set only on an
    unrelated setup step would otherwise mask its absence from a step that
    runs the fixture, and the agent inherits the *step* env block.
    """
    workflow = _load_matrix_workflow() if workflow is None else workflow
    shortfall: dict[str, list[str]] = {}
    for index, step in enumerate(_fixture_running_steps(workflow)):
        missing = sorted(required - set(step.get("env") or {}))
        if missing:
            shortfall[f"[{index}] {step.get('name') or '<unnamed>'}"] = missing
    return shortfall


def _tracked_files(root: pathlib.Path) -> list[pathlib.Path]:
    """Git-tracked files under `root`, so local artifacts cannot false-fail."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", str(root)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [(ROOT / name).resolve() for name in listing.stdout.split("\0") if name]


class FoundryEvalsPinEndpointContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rpv = _load_runner()
        cls.pin = cls.rpv.parse_pin(EVALS_PIN)
        assert cls.pin is not None, "foundry-evals pin failed to parse"
        cls.script = cls.pin["validation"]["script"]

    # ── runner mapping ────────────────────────────────────────────────

    def test_runner_gates_foundry_project_on_project_endpoint(self) -> None:
        self.assertEqual(self.rpv.AZURE_ENV_MAP["foundry_project"], PROJECT_ENV)

    def test_runner_still_forwards_account_endpoint(self) -> None:
        """Account-scoped consumers (e.g. FDVS) must keep their secret."""
        forwarded = set(self.rpv.AZURE_EXTRA_ENV) | set(
            self.rpv.AZURE_ENV_MAP.values()
        )
        self.assertIn(ACCOUNT_ENV, forwarded)

    def test_runner_leaves_subscription_requirement_untouched(self) -> None:
        self.assertEqual(
            self.rpv.AZURE_ENV_MAP["azure_subscription"], "AZURE_SUBSCRIPTION_ID"
        )

    def test_runner_forwards_project_endpoint_to_pin_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shim = pathlib.Path(tmp) / "_shims"
            shim.mkdir()
            with unittest.mock.patch.dict(
                os.environ, {PROJECT_ENV: "https://example.invalid/api/projects/x"}
            ):
                env = self.rpv._build_clean_env(shim)
        self.assertEqual(
            env.get(PROJECT_ENV), "https://example.invalid/api/projects/x"
        )

    # ── gate behaviour against the real pin ───────────────────────────

    def test_gate_blocks_when_only_account_endpoint_present(self) -> None:
        patched = {ACCOUNT_ENV: "https://example.invalid/"}
        with unittest.mock.patch.dict(os.environ, patched, clear=False):
            os.environ.pop(PROJECT_ENV, None)
            ok, reason = self.rpv.should_run(
                self.pin, EVALS_PIN, include_azure=True
            )
        self.assertFalse(ok)
        self.assertIn(PROJECT_ENV, reason)

    def test_gate_allows_when_project_endpoint_present(self) -> None:
        patched = {PROJECT_ENV: "https://example.invalid/api/projects/x"}
        with unittest.mock.patch.dict(os.environ, patched, clear=False):
            ok, reason = self.rpv.should_run(
                self.pin, EVALS_PIN, include_azure=True
            )
        self.assertTrue(ok, reason)

    # ── pin script consumption ────────────────────────────────────────

    def test_evals_script_hard_requires_project_endpoint(self) -> None:
        required = _hard_required_env(self.script)
        self.assertIn(PROJECT_ENV, required)
        self.assertNotIn(ACCOUNT_ENV, required)

    def test_evals_pin_never_mentions_account_endpoint(self) -> None:
        """Prose mirror + notes must not point refreshers at the wrong secret."""
        self.assertNotIn(ACCOUNT_ENV, EVALS_PIN.read_text(encoding="utf-8"))

    def test_prose_mirror_matches_validation_script(self) -> None:
        text = EVALS_PIN.read_text(encoding="utf-8")
        body = text.split("---", 2)[2]
        blocks = re.findall(r"```bash\n(.*?)```", body, flags=re.DOTALL)
        self.assertTrue(blocks, "no bash mirror block found in pin prose")
        mirror = next(b for b in blocks if "FOUNDRY_EVALS_VALIDATION_PASS" in b)
        self.assertEqual(mirror.strip(), self.script.strip())

    # ── fixture (T3 consumer) contract ────────────────────────────────

    def test_evals_fixture_names_project_endpoint_for_project_scope(self) -> None:
        """The fixture's declared 'Foundry project endpoint' is project-scoped."""
        text = EVALS_FIXTURE.read_text(encoding="utf-8")
        declaration = next(
            line for line in text.splitlines() if "Foundry project endpoint" in line
        )
        self.assertIn(PROJECT_ENV, _referenced_env(declaration))
        self.assertNotIn(ACCOUNT_ENV, _referenced_env(declaration))

    def test_evals_fixture_inventories_the_endpoint_it_consumes(self) -> None:
        """Step 0's auth inventory must cover the endpoint Step 1 actually uses."""
        referenced = _referenced_env(EVALS_FIXTURE.read_text(encoding="utf-8"))
        self.assertIn(PROJECT_ENV, referenced)
        self.assertNotIn(ACCOUNT_ENV, referenced)

    def test_evals_fixture_env_refs_are_exported_by_the_matrix_job(self) -> None:
        """Pattern 11: a fixture may only read env the workflow actually sets.

        The fixture self-FAILs when an inventoried var prints empty, so an
        unexported reference is a guaranteed red matrix leg. Checked per
        fixture-running step: the retry leg needs the same env as the main
        one, and a union would let either hide behind the other.
        """
        referenced = _referenced_env(EVALS_FIXTURE.read_text(encoding="utf-8"))
        azure_refs = {
            v
            for v in referenced
            if v.startswith(("AZURE_", "FOUNDRY_", "ACR_", "APPLICATIONINSIGHTS_"))
        }
        missing = _missing_env_by_fixture_step(azure_refs)
        self.assertEqual(
            missing,
            {},
            f"fixture reads env not exported by {MATRIX_JOB} steps: {missing}",
        )

    def test_evals_skill_tree_has_no_account_endpoint_alias(self) -> None:
        """No tracked file under the skill may alias the account var.

        Scoped to Git-tracked sources so untracked local artifacts cannot
        false-fail; this still covers SKILL.md, the pin, the fixture and
        every reference source.
        """
        offenders = [
            str(p.relative_to(ROOT))
            for p in _tracked_files(EVALS_SKILL)
            if ACCOUNT_ENV in p.read_text(encoding="utf-8", errors="ignore")
        ]
        self.assertEqual(sorted(offenders), [])

    # ── helper-level regression coverage ──────────────────────────────
    #
    # These guard the *checkers* above. A contract test is only worth the
    # bytes if it fails when the contract breaks, so each of these mutates
    # a known-good input into a known-bad one and asserts detection.

    def test_fixture_running_steps_are_found_by_invocation_not_position(
        self,
    ) -> None:
        """Fixture steps are identified by the real `copilot -p` invocation.

        Step names and indices churn; the invocation is the contract. Both
        the main run and the transient-retry run must be found (Pattern 26),
        since a var exported to only one of them still fails half the legs.
        """
        steps = _fixture_running_steps(_load_matrix_workflow())
        self.assertGreaterEqual(
            len(steps),
            2,
            "expected at least the main + retry copilot -p invocations",
        )
        for step in steps:
            self.assertIn("copilot -p", step.get("run") or "")

    def test_missing_env_detected_when_dropped_from_a_single_fixture_step(
        self,
    ) -> None:
        """The masking defect: per-step checking, never a cross-step union.

        `FOUNDRY_PROJECT_ENDPOINT` is also exported by the unrelated
        'Resolve Foundry project context' setup step, so a union over all
        matrix steps still contains it after it is dropped from a step that
        actually runs the fixture. Each fixture-running step is checked on
        its own.
        """
        for victim in range(2):
            with self.subTest(dropped_from_step=victim):
                workflow = _load_matrix_workflow()
                steps = _fixture_running_steps(workflow)
                del steps[victim]["env"][PROJECT_ENV]

                union = set().union(
                    *(
                        set(s.get("env") or {})
                        for s in workflow["jobs"][MATRIX_JOB]["steps"]
                    )
                )
                self.assertIn(
                    PROJECT_ENV, union, "precondition: another step masks it"
                )

                missing = _missing_env_by_fixture_step({PROJECT_ENV}, workflow)
                self.assertTrue(
                    missing, f"drop from fixture step {victim} went undetected"
                )

    def test_tracked_scan_ignores_untracked_artifacts(self) -> None:
        """`__pycache__`, venvs, temp workdirs and editor backups are noise.

        Scanning the working tree lets a local artifact that merely mentions
        the account var false-fail validation. Only Git-tracked source counts.
        """
        probe = EVALS_SKILL / "__pycache__" / "endpoint_scan_probe.txt"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(f"{ACCOUNT_ENV}\n", encoding="utf-8")
        try:
            self.assertNotIn(probe.resolve(), _tracked_files(EVALS_SKILL))
        finally:
            probe.unlink(missing_ok=True)
            with contextlib.suppress(OSError):  # only if we created it empty
                probe.parent.rmdir()

    def test_tracked_scan_still_covers_every_tracked_source(self) -> None:
        """Narrowing to tracked files must not narrow detection coverage."""
        tracked = _tracked_files(EVALS_SKILL)
        for required in (
            EVALS_PIN,
            EVALS_FIXTURE,
            EVALS_SKILL / "SKILL.md",
        ):
            self.assertIn(required.resolve(), tracked)
        self.assertTrue(
            any(p.suffix == ".py" for p in tracked),
            "expected the skill's reference python sources to be scanned",
        )

    # ── cross-pin coherence (the bug class, not just this instance) ────

    def test_foundry_project_pins_only_consume_the_gated_endpoint(self) -> None:
        gated = self.rpv.AZURE_ENV_MAP["foundry_project"]
        checked = 0
        for pin_path in sorted(ROOT.glob("skills/*/references/upstream-pin.md")):
            fm = _pin_frontmatter(pin_path)
            validation = (fm or {}).get("validation") or {}
            if "foundry_project" not in (validation.get("requires") or []):
                continue
            checked += 1
            consumed = _hard_required_env(validation.get("script") or "")
            stray = (consumed & ENDPOINT_ENVS) - {gated}
            self.assertEqual(
                stray,
                set(),
                f"{pin_path.relative_to(ROOT)} requires foundry_project but "
                f"hard-requires ungated endpoint env {sorted(stray)}",
            )
        self.assertGreater(checked, 0, "no foundry_project pins discovered")


if __name__ == "__main__":
    unittest.main()
