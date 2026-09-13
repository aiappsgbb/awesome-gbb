"""The pin runner must preserve explicit Azure isolation, not unrelated secrets."""

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
ISOLATION_ENV = {
    "AZURE_CONFIG_DIR": "/isolated/azure/test",
    "AZD_CONFIG_DIR": "/isolated/azd/test",
    "AZURE_TOKEN_CREDENTIALS": "AzureCliCredential",
    "JUDGE_MODEL_DEPLOYMENT": "approved-test-judge",
}


def runner():
    spec = importlib.util.spec_from_file_location(
        "pin_isolation_runner", ROOT / "scripts/run-pin-validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PinValidationIsolationTests(unittest.TestCase):
    def test_explicit_isolation_survives_the_clean_environment(self):
        with patch.dict(os.environ, {**ISOLATION_ENV, "UNRELATED_SECRET": "do-not-copy"}, clear=True):
            environment = runner()._build_clean_env(Path("/python-shims"))
        for name, expected in ISOLATION_ENV.items():
            with self.subTest(name=name):
                self.assertEqual(environment.get(name), expected)
        self.assertNotIn("UNRELATED_SECRET", environment)
        self.assertEqual(environment["PIN_VALIDATION_REPO_ROOT"], str(ROOT.resolve()))

    def test_absent_selectors_are_not_invented(self):
        with patch.dict(os.environ, {}, clear=True):
            environment = runner()._build_clean_env(Path("/python-shims"))
        self.assertFalse(set(ISOLATION_ENV) & set(environment))


if __name__ == "__main__":
    unittest.main()
