#!/usr/bin/env python3
"""Focused exact-contract test for the foundry-doc-vision-speech Speech RBAC role.

Guards the Gotchas-table row for "Speech 401 with managed identity" against
naming the wrong Azure role. `Cognitive Services User` does NOT grant Speech
data-plane access; the Speech SDK's `token_credential` path requires
`Cognitive Services Speech User` (role ID f2dc8367-1007-4938-bd23-fe263f013447).

The skill already states the correct role in its Speech pattern section and in
its RBAC matrix, so a contradicting Gotchas row is an internal inconsistency
that sends a consumer down a dead-end fix.
"""

from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-doc-vision-speech" / "SKILL.md"

SPEECH_ROLE = "Cognitive Services Speech User"
SPEECH_ROLE_ID = "f2dc8367-1007-4938-bd23-fe263f013447"
DOCINTEL_ROLE = "Cognitive Services User"


def _speech_401_row(markdown: str) -> str:
    rows = [
        line
        for line in markdown.splitlines()
        if line.startswith("|") and "Speech 401" in line
    ]
    if len(rows) != 1:
        raise AssertionError(
            f"expected exactly 1 Gotchas row mentioning 'Speech 401', found {len(rows)}"
        )
    return rows[0]


def _cells(row: str) -> tuple[str, str, str]:
    """Split a 3-column Gotchas row into (issue, cause, fix)."""
    parts = [cell.strip() for cell in row.strip().strip("|").split("|")]
    if len(parts) != 3:
        raise AssertionError(f"expected 3 Gotchas cells, found {len(parts)}: {parts!r}")
    return parts[0], parts[1], parts[2]


def _strip_speech_role(text: str) -> str:
    """Remove the correct role name so a bare-role check cannot match inside it."""
    return text.replace(SPEECH_ROLE, "")


NEGATING = ("not grant", "NOT grant", "Wrong role", "does NOT", "does not")


class SpeechManagedIdentityRoleContract(unittest.TestCase):
    def setUp(self) -> None:
        self.markdown = SKILL.read_text(encoding="utf-8")
        self.row = _speech_401_row(self.markdown)
        self.issue, self.cause, self.fix = _cells(self.row)

    def test_fix_prescribes_the_speech_data_plane_role(self) -> None:
        self.assertIn(
            SPEECH_ROLE,
            self.fix,
            "the Fix cell must prescribe the Speech data-plane role",
        )

    def test_fix_does_not_prescribe_the_docintel_role(self) -> None:
        self.assertNotIn(
            DOCINTEL_ROLE,
            _strip_speech_role(self.fix),
            f"{DOCINTEL_ROLE!r} does not grant Speech data-plane access; "
            "prescribing it as the fix sends consumers down a dead-end",
        )

    def test_cause_only_names_the_docintel_role_to_negate_it(self) -> None:
        """Naming the wrong role is fine — but only as an explicit anti-pattern."""
        if DOCINTEL_ROLE not in _strip_speech_role(self.cause):
            return
        self.assertTrue(
            any(token in self.cause for token in NEGATING),
            f"the Cause cell names {DOCINTEL_ROLE!r} without negating language, "
            "which reads as a prescription rather than an anti-pattern",
        )

    def test_fix_carries_the_canonical_role_id(self) -> None:
        self.assertIn(
            SPEECH_ROLE_ID,
            self.fix,
            "the Fix cell must carry the role GUID so it is directly actionable",
        )

    def test_role_id_matches_the_speech_pattern_section(self) -> None:
        """The Gotchas row must not drift from the skill's canonical RBAC pin."""
        pins = re.findall(
            rf"`{SPEECH_ROLE}`\s*\n?>?\s*\(role ID `([0-9a-f-]+)`\)",
            self.markdown,
        )
        self.assertTrue(pins, "canonical Speech RBAC pin with role ID not found in SKILL.md")
        for pin in pins:
            self.assertEqual(
                pin,
                SPEECH_ROLE_ID,
                "Speech role GUID drifted between the RBAC pin and this test",
            )


if __name__ == "__main__":
    unittest.main()
