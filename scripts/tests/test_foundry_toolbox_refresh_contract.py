#!/usr/bin/env python3
"""Regression tests for the foundry-toolbox post-merge correction contract.

These tests pin down three review findings against the tree merged for PR
#436 (squash commit b8ebc554):

1. Fixture cleanup on failure — the Python smoke's toolbox deletion must be
   attempted from a `finally` block so a raised assertion/get/verification
   failure after a successful `create_version` still triggers best-effort
   cleanup instead of leaking the CI toolbox resource.
2. Dangling troubleshooting text — the "Only `tool_search` and `call_tool`
   are listed" row must not promise "pin critical tools" guidance that was
   deliberately removed from the rest of the skill body.
3. Validation date drift — `SKILL.md` frontmatter `metadata.validated` must
   match the upstream pin's `last_validated` date.

Assertions target structure/behavior (AST shape, substring absence/presence,
parsed frontmatter values), not arbitrary line numbers.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-toolbox" / "SKILL.md"
PIN = ROOT / "skills" / "foundry-toolbox" / "references" / "upstream-pin.md"
FIXTURE = ROOT / "skills" / "foundry-toolbox" / "test-fixture" / "consumer_prompt.md"

PYTHON_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _frontmatter(text: str) -> dict:
    """Parse the YAML frontmatter block delimited by the first two `---` lines."""
    return yaml.safe_load(text.split("---", 2)[1])


def _is_call_named(node: ast.AST, dotted_name: str) -> bool:
    """Return True if `node` is a Call whose dotted callee equals `dotted_name`.

    Matches call shapes like ``project.toolboxes.delete(...)`` or
    ``asyncio.run(...)`` by walking the Attribute/Name chain of `node.func`.
    """
    if not isinstance(node, ast.Call):
        return False
    parts: list[str] = []
    target = node.func
    while isinstance(target, ast.Attribute):
        parts.append(target.attr)
        target = target.value
    if isinstance(target, ast.Name):
        parts.append(target.id)
    else:
        return False
    parts.reverse()
    return ".".join(parts) == dotted_name


def _calls_named(stmts: list, dotted_name: str) -> list:
    """Find every call matching `dotted_name` anywhere within a statement list.

    Wraps `stmts` in a synthetic `ast.Module` so `ast.walk` can traverse a
    statement list that isn't itself a full parsed module.
    """
    module = ast.Module(body=list(stmts), type_ignores=[])
    return [n for n in ast.walk(module) if _is_call_named(n, dotted_name)]


def _extract_python_smoke() -> str:
    text = FIXTURE.read_text(encoding="utf-8")
    blocks = PYTHON_FENCE_RE.findall(text)
    if len(blocks) != 1:
        raise AssertionError(
            f"expected exactly one ```python fenced block in the fixture, found {len(blocks)}"
        )
    return blocks[0]


def _find_credential_project_with(tree: ast.Module) -> ast.With:
    """Locate the `with DefaultAzureCredential() as credential, AIProjectClient(...) as project:` block.

    The fixture also contains an unrelated `with open(...) as evidence:` (inside
    `record()`) and an `async with FoundryToolbox(...) as toolbox:` (a distinct
    `ast.AsyncWith` node, not `ast.With`) — filtering by the bound names avoids
    both false matches.
    """
    candidates = []
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            names = {
                getattr(item.optional_vars, "id", None)
                for item in node.items
                if item.optional_vars is not None
            }
            if {"credential", "project"} <= names:
                candidates.append(node)
    if len(candidates) != 1:
        raise AssertionError(
            "expected exactly one `with ... as credential, ... as project:` block, "
            f"found {len(candidates)}"
        )
    return candidates[0]


class FoundryToolboxCleanupContractTests(unittest.TestCase):
    """Finding #1 — best-effort delete must run from `finally`, not after it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = _extract_python_smoke()
        cls.tree = ast.parse(cls.source)
        cls.target_with = _find_credential_project_with(cls.tree)
        cls.with_body = cls.target_with.body

    def _outer_try(self) -> ast.Try:
        tries = [stmt for stmt in self.with_body if isinstance(stmt, ast.Try)]
        if len(tries) != 1:
            self.fail(
                "expected exactly one top-level try/finally directly inside the "
                f"credential/project `with` block, found {len(tries)}. The "
                "create/get/verify/delete lifecycle must be a single protected "
                "region so cleanup cannot be skipped by an early exception."
            )
        return tries[0]

    def _nested_cleanup_try(self, outer_try: ast.Try) -> ast.Try:
        nested = [stmt for stmt in outer_try.finalbody if isinstance(stmt, ast.Try)]
        if len(nested) != 1:
            self.fail(
                "expected the outer try's `finally` block to contain exactly one "
                "nested try/except performing the best-effort toolbox delete, "
                f"found {len(nested)} nested try statements. Deletion must be "
                "attempted from `finally` so it still runs when create/get/verify "
                "raises."
            )
        return nested[0]

    def test_create_version_precedes_the_protective_try_block(self) -> None:
        create_index = next(
            (
                i
                for i, stmt in enumerate(self.with_body)
                if isinstance(stmt, ast.Assign)
                and isinstance(stmt.value, ast.Call)
                and _is_call_named(stmt.value, "project.toolboxes.create_version")
            ),
            None,
        )
        try_index = next(
            (i for i, stmt in enumerate(self.with_body) if isinstance(stmt, ast.Try)),
            None,
        )
        self.assertIsNotNone(
            create_index, "project.toolboxes.create_version(...) call not found in with-block"
        )
        self.assertIsNotNone(
            try_index, "no top-level try/finally found directly in the with-block"
        )
        self.assertLess(
            create_index,
            try_index,
            "create_version must complete before the protective try/finally begins "
            "-- only a toolbox that was actually created needs cleanup",
        )

    def test_get_version_and_verification_run_inside_the_protected_try_body(self) -> None:
        outer_try = self._outer_try()
        get_version_calls = _calls_named(outer_try.body, "project.toolboxes.get_version")
        verify_calls = _calls_named(outer_try.body, "asyncio.run")
        self.assertTrue(
            get_version_calls,
            "project.toolboxes.get_version(...) must run inside the outer try body "
            "so a raised AssertionError there still reaches the finally cleanup "
            "(currently it runs after the try/except, so its failures skip delete)",
        )
        self.assertTrue(
            verify_calls,
            "asyncio.run(verify_functions(...)) must run inside the outer try body "
            "so a raised meta-tool verification failure still reaches the finally "
            "cleanup (currently it runs after the try/except, so its failures skip "
            "delete)",
        )

    def test_outer_try_has_no_except_clause(self) -> None:
        outer_try = self._outer_try()
        self.assertEqual(
            outer_try.handlers,
            [],
            "the outer try must not itself catch exceptions -- an except clause "
            "here would swallow the original assertion/verification failure "
            "instead of letting it propagate once best-effort cleanup finishes",
        )
        self.assertTrue(
            outer_try.finalbody,
            "the outer try must have a non-empty finally block that performs "
            "best-effort toolbox deletion",
        )

    def test_delete_is_attempted_inside_a_nested_try_in_finally(self) -> None:
        outer_try = self._outer_try()
        nested_try = self._nested_cleanup_try(outer_try)
        delete_calls = _calls_named(nested_try.body, "project.toolboxes.delete")
        self.assertTrue(
            delete_calls,
            "project.toolboxes.delete(toolbox_name) must be attempted inside the "
            "nested try/except that lives in the outer try's finally block",
        )

    def test_delete_failure_is_swallowed_sanitized_and_transcript_only(self) -> None:
        outer_try = self._outer_try()
        nested_try = self._nested_cleanup_try(outer_try)
        self.assertEqual(
            len(nested_try.handlers),
            1,
            "the nested cleanup try must have exactly one except handler",
        )
        handler = nested_try.handlers[0]
        handler_module = ast.Module(body=handler.body, type_ignores=[])
        handler_source = ast.unparse(handler_module)

        raises = [n for n in ast.walk(handler_module) if isinstance(n, ast.Raise)]
        self.assertEqual(
            raises,
            [],
            "a failed delete must not re-raise -- doing so would replace the "
            "original assertion/get/verification exception (or mask a clean "
            "success) with a cleanup-only failure",
        )

        record_calls = _calls_named(handler.body, "record")
        self.assertEqual(
            record_calls,
            [],
            "a failed delete must be transcript-only (print) and must never call "
            "record(...) -- that would append a sidecar evidence line for a "
            "cleanup failure, growing the hard-record count past five",
        )

        self.assertIn(
            "type(exc).__name__",
            handler_source,
            "the delete-failure NOTE must be sanitized to the exception TYPE name",
        )
        self.assertNotIn(
            "{exc}",
            handler_source,
            "the delete-failure NOTE must not interpolate the raw exception object "
            "or its message -- only the sanitized type name and toolbox name",
        )
        self.assertIn(
            "toolbox_name",
            handler_source,
            "the delete-failure NOTE must identify which toolbox failed to delete",
        )

    def test_exactly_five_hard_sidecar_records_remain(self) -> None:
        """Guard: the fixture's five-record contract must survive the cleanup fix."""
        fixture_text = FIXTURE.read_text(encoding="utf-8")
        python_record_calls = re.findall(r"(?<!def )record\(", self.source)
        bash_record_calls = re.findall(r'record "', fixture_text)
        self.assertEqual(
            len(python_record_calls),
            3,
            "expected exactly 3 python-side record(...) sidecar emission call-sites "
            "(TOOL_SEARCH_CREATED, TOOLBOX_RETRIEVED, TOOL_SEARCH_FUNCTIONS)",
        )
        self.assertEqual(
            len(bash_record_calls),
            2,
            'expected exactly 2 bash-side record "..." sidecar emission call-sites '
            "(AZD_SERVICE_CREATED, AZD_CLI_CREATED)",
        )
        self.assertEqual(
            len(python_record_calls) + len(bash_record_calls),
            5,
            "the fixture's hard sidecar-evidence contract requires exactly five "
            "record emissions total; the cleanup-path fix must not change this",
        )


class FoundryToolboxTroubleshootingContractTests(unittest.TestCase):
    """Finding #2 — remove the dangling 'pin critical tools' remediation text."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_troubleshooting_row_no_longer_promises_pin_critical_tools(self) -> None:
        self.assertNotIn(
            "pin critical tools",
            self.text,
            "the skill removed all ToolConfig/pinning guidance, so no "
            "troubleshooting remediation may still promise 'pin critical tools'",
        )

    def test_troubleshooting_row_still_documents_tool_search_fix(self) -> None:
        match = re.search(
            r"\|\s*Only `tool_search` and `call_tool` are listed\s*\|([^|]*)\|([^|]*)\|",
            self.text,
        )
        self.assertIsNotNone(
            match, "could not locate the 'Only tool_search and call_tool' troubleshooting row"
        )
        cause, fix = match.group(1).strip(), match.group(2).strip()
        self.assertEqual(cause, "Tool Search is active")
        self.assertEqual(
            fix,
            "Search first, then call the discovered tool",
            "the remaining remediation text must stay intact once the dangling "
            "pinning clause is removed",
        )


class FoundryToolboxValidationDateContractTests(unittest.TestCase):
    """Finding #3 — SKILL.md validated date must match the upstream pin."""

    def test_skill_validated_matches_upstream_pin_last_validated(self) -> None:
        skill_meta = _frontmatter(SKILL.read_text(encoding="utf-8"))["metadata"]
        pin_meta = _frontmatter(PIN.read_text(encoding="utf-8"))

        skill_validated = str(skill_meta["validated"])
        pin_last_validated = str(pin_meta["last_validated"])

        self.assertEqual(
            skill_validated,
            pin_last_validated,
            "SKILL.md metadata.validated must match the upstream pin's last_validated",
        )
        self.assertEqual(
            skill_validated,
            "2026-08-04",
            "both SKILL.md metadata.validated and the upstream pin last_validated "
            "must equal 2026-08-04",
        )


if __name__ == "__main__":
    unittest.main()
