"""CI wrapper for foundry-observability operating-evidence tests.

Loads the test suite from the skill references directory so that::

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

(invoked by ``.github/workflows/skill-test.yml::unit-tests``) discovers and
runs the full observability-evidence contract tests.

All test classes live in
``skills/foundry-observability/references/python/test_observability_evidence.py``
and are imported here verbatim.  Keeping the authoritative suite co-located
with the module under test follows the same convention used by
``test_foundry_evals_trust.py`` for the foundry-evals skill.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve skill module path so both the module and the test classes can import.
# ---------------------------------------------------------------------------
_SKILL_DIR = (
    Path(__file__).resolve().parents[1].parent
    / "skills"
    / "foundry-observability"
    / "references"
    / "python"
)

if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

# ---------------------------------------------------------------------------
# Import all test cases from the authoritative reference test file.
# They are re-exported at module scope so unittest discover picks them up.
# ---------------------------------------------------------------------------
from test_observability_evidence import (  # noqa: E402, F401
    TestModuleImport,
    TestBuildEvidence,
    TestAlertValidation,
    TestActionGroupValidation,
    TestEvaluatorDefinitionValidation,
    TestTracePolicyValidation,
    TestSamplingValidation,
    TestRetentionDaysValidation,
    TestMonthlyBudgetValidation,
    TestTimestampValidation,
    TestImmutabilityAndDeterminism,
    TestWriteEvidence,
    TestFixtureFiles,
    TestSchemaValidation,
    TestMalformedNestedTypes,
)

if __name__ == "__main__":
    unittest.main()
