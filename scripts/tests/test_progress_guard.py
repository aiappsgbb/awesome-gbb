"""Run the bundled persistence suite in the existing catalog unit-test job."""

import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = (Path(__file__).resolve().parents[2] / "skills" / "progress-guard"
            / "tests" / "test_ledger.py")
    spec = importlib.util.spec_from_file_location("progress_guard_ledger_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
