"""Unit tests for scripts/check-freshness.py :: detect_pkg_drift (#241).

Regression guard for the dead-code bug where the `body = ...` /
`out.append(Signal(...))` block was indented INSIDE the
`if not is_major and not is_critical_pkg: continue` skip branch, after
the `continue`. The net effect: the detector NEVER emitted a drift
signal for the packages it was supposed to flag (critical SDKs or
MAJOR bumps), so newly-drifted packages silently vanished from the
consolidated refresh issues (#241).

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

`unittest discover` cannot resolve pytest fixtures and silently emits
0 tests. Keep this file unittest-native so CI actually runs it.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "check-freshness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_freshness", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules before exec so @dataclasses.dataclass can
    # resolve cls.__module__ (required on Python 3.12+).
    import sys

    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CF = _load_module()


class _FakeResp:
    def __init__(self, latest: str):
        self._latest = latest

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"info": {"version": self._latest}}


class _FakeRequests:
    """Stand-in for the `requests` module used inside check-freshness."""

    RequestException = Exception

    def __init__(self, latest: str):
        self._latest = latest
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs) -> _FakeResp:
        self.calls.append(url)
        return _FakeResp(self._latest)


def _make_pin(name: str, pinned: str, *, automation_tier: str = "auto"):
    fm = {
        "automation_tier": automation_tier,
        "packages": [{"source": "pypi", "name": name, "version": pinned}],
    }
    return CF.PinFile(skill="demo-skill", path=Path("/dev/null"), fm=fm)


class DetectPkgDriftTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_requests = CF.requests

    def tearDown(self) -> None:
        CF.requests = self._orig_requests

    def _run(self, name: str, pinned: str, latest: str):
        CF.requests = _FakeRequests(latest)
        pin = _make_pin(name, pinned)
        return CF.detect_pkg_drift(pin)

    def test_critical_sdk_minor_bump_emits_signal(self) -> None:
        """#241 regression: agent-framework 1.7.0 -> 1.8.0 MUST fire.

        Before the indentation fix this returned [] (the append was
        dead code after `continue`).
        """
        signals = self._run("agent-framework", "1.7.0", "1.8.0")
        self.assertEqual(len(signals), 1, "critical SDK minor drift must emit one signal")
        sig = signals[0]
        self.assertEqual(sig.signal_type, "pkg_drift")
        self.assertIn("1.7.0", sig.title)
        self.assertIn("1.8.0", sig.title)
        self.assertEqual(sig.automation_tier, "auto")

    def test_critical_sdk_patch_bump_emits_signal(self) -> None:
        signals = self._run("azure-ai-projects", "1.0.0", "1.0.1")
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, "pkg_drift")

    def test_major_bump_on_noncritical_pkg_emits_signal(self) -> None:
        signals = self._run("gradio", "4.0.0", "5.0.0")
        self.assertEqual(len(signals), 1, "MAJOR bump on any pkg must emit a signal")
        self.assertIn("4.0.0", signals[0].title)
        self.assertIn("5.0.0", signals[0].title)

    def test_noncritical_minor_bump_is_skipped(self) -> None:
        signals = self._run("gradio", "4.0.0", "4.1.0")
        self.assertEqual(signals, [], "non-critical MINOR bump must be skipped")

    def test_in_sync_pkg_emits_nothing(self) -> None:
        signals = self._run("agent-framework", "1.8.0", "1.8.0")
        self.assertEqual(signals, [], "version in sync must emit nothing")


if __name__ == "__main__":
    unittest.main()
