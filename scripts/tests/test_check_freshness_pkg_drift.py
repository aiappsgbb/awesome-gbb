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


def _make_pin_with_hold(
    name: str,
    pinned: str,
    *,
    hold_below: str | None = None,
    hold_reason: str | None = None,
    ki_id: str | None = None,
    ki_status: str = "open",
    automation_tier: str = "auto",
):
    """Pin builder that supports the KI-backed package hold (#241 follow-up).

    A package may carry `hold_below` + `hold_reason`; the hold suppresses a
    MAJOR-bump drift signal ONLY while the referenced known_issue is
    `status: open`. Models the fastmcp<3.0.0 / KI-001 hold in foundry-mcp-aca.
    """
    pkg = {"source": "pypi", "name": name, "version": pinned}
    if hold_below is not None:
        pkg["hold_below"] = hold_below
    if hold_reason is not None:
        pkg["hold_reason"] = hold_reason
    fm: dict = {"automation_tier": automation_tier, "packages": [pkg]}
    if ki_id is not None:
        fm["known_issues"] = [
            {
                "id": ki_id,
                "status": ki_status,
                "description": "held below a known-breaking major",
                "upstream_url": "https://pypi.org/project/fastmcp/",
            }
        ]
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


class DetectPkgDriftHoldTest(unittest.TestCase):
    """KI-backed package hold (#241 follow-up / fastmcp<3.0.0 regression).

    A MAJOR bump on a package that a skill deliberately holds below the new
    major (via `hold_below` + `hold_reason` referencing an OPEN known_issue)
    must NOT emit an auto-refresh signal — otherwise the weekly detector
    re-opens a @Copilot issue that a coding agent actions, re-bumping past
    the ceiling (exactly the fastmcp 2.14.7 -> 3.3.1 regression, PR #166).
    The hold releases automatically once the KI flips to status!=open.
    """

    def setUp(self) -> None:
        self._orig_requests = CF.requests

    def tearDown(self) -> None:
        CF.requests = self._orig_requests

    def _run(self, pin, latest: str):
        CF.requests = _FakeRequests(latest)
        return CF.detect_pkg_drift(pin)

    def test_major_bump_held_by_open_ki_is_skipped(self) -> None:
        """fastmcp 2.14.7 -> 3.4.2 with an OPEN KI-001 hold must emit nothing."""
        pin = _make_pin_with_hold(
            "fastmcp", "2.14.7",
            hold_below="3.0.0", hold_reason="KI-001",
            ki_id="KI-001", ki_status="open",
        )
        self.assertEqual(
            self._run(pin, "3.4.2"), [],
            "an open-KI hold below the new major must suppress the drift signal",
        )

    def test_major_bump_hold_released_when_ki_closed(self) -> None:
        """Once KI-001 is closed, the hold lifts and the MAJOR bump fires again."""
        pin = _make_pin_with_hold(
            "fastmcp", "2.14.7",
            hold_below="3.0.0", hold_reason="KI-001",
            ki_id="KI-001", ki_status="closed_upstream_needs_revalidation",
        )
        signals = self._run(pin, "3.4.2")
        self.assertEqual(len(signals), 1, "closed KI must NOT suppress the signal")
        self.assertEqual(signals[0].signal_type, "pkg_drift")

    def test_hold_ceiling_above_latest_major_still_fires(self) -> None:
        """Hold only suppresses bumps that CROSS the ceiling.

        hold_below 4.0.0 does not cover a 2 -> 3 major (3.0.0 < 4.0.0), so the
        MAJOR-bump signal still fires.
        """
        pin = _make_pin_with_hold(
            "somepkg", "2.0.0",
            hold_below="4.0.0", hold_reason="KI-009",
            ki_id="KI-009", ki_status="open",
        )
        signals = self._run(pin, "3.0.0")
        self.assertEqual(len(signals), 1, "bump below the ceiling must still fire")

    def test_hold_below_without_open_ki_is_ignored(self) -> None:
        """Fail-open: hold_below with no backing OPEN KI does not suppress.

        Guards against a typo'd/absent hold_reason silently freezing a
        package — better to over-flag than silently hold forever.
        """
        pin = _make_pin_with_hold(
            "fastmcp", "2.14.7", hold_below="3.0.0",  # no hold_reason, no KI
        )
        signals = self._run(pin, "3.4.2")
        self.assertEqual(len(signals), 1, "hold without an open KI must fire normally")


if __name__ == "__main__":
    unittest.main()
