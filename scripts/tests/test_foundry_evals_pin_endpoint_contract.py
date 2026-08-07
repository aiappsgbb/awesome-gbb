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

import importlib.util
import os
import pathlib
import re
import tempfile
import unittest
import unittest.mock

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent
EVALS_PIN = ROOT / "skills" / "foundry-evals" / "references" / "upstream-pin.md"

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
