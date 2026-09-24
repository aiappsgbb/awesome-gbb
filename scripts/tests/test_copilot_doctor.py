"""Run doctor collector tests in the existing offline catalog test job."""

import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    root = Path(__file__).resolve().parents[2] / "skills/copilot-doctor/tests"
    for path in sorted(root.glob("test_*.py")):
        spec = importlib.util.spec_from_file_location("copilot_doctor_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tests.addTests(loader.loadTestsFromModule(module))
    return tests
