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
import textwrap
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


def _exception_var_name(handler: ast.ExceptHandler) -> str:
    """Return the identifier an `except ... as <name>:` clause binds.

    `ast.ExceptHandler.name` is a plain `str` (not an `ast.Name`), so a
    missing bind (`except Exception:`) surfaces as `None` -- fail loudly
    rather than let callers silently treat "no binding" as "no leak risk".
    """
    if not handler.name:
        raise AssertionError(
            "except handler does not bind the exception to a name "
            "(expected `except Exception as exc:`)"
        )
    return handler.name


def _unsafe_exception_references(handler: ast.ExceptHandler) -> list[ast.Name]:
    """Return every reference to the handler's bound exception name that leaks it.

    The only permitted shape for referencing the caught exception is as the
    direct, sole, non-keyword argument of a bare `type(...)` call -- e.g.
    `type(exc)`, whose result may then be narrowed further (`.__name__`).
    Every other reference -- `f"{exc}"`, `f"{exc!r}"`, `f"{exc!s}"`,
    `str(exc)`, `exc.args`, string concatenation with `exc`, passing `exc`
    to any other call, etc. -- risks leaking the raw exception object or its
    message and is rejected.

    `ast` nodes carry no parent pointers, so this builds a one-off parent
    map over the handler body before classifying each `ast.Name` match.
    """
    var_name = _exception_var_name(handler)
    module = ast.Module(body=list(handler.body), type_ignores=[])

    parent_of: dict[int, ast.AST] = {}
    for parent in ast.walk(module):
        for child in ast.iter_child_nodes(parent):
            parent_of[id(child)] = parent

    unsafe: list[ast.Name] = []
    for node in ast.walk(module):
        if not (isinstance(node, ast.Name) and node.id == var_name):
            continue
        parent = parent_of.get(id(node))
        is_direct_type_arg = (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "type"
            and not parent.keywords
            and len(parent.args) == 1
            and parent.args[0] is node
        )
        if not is_direct_type_arg:
            unsafe.append(node)
    return unsafe


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

        # Structural anti-leak guard (AST shape, not a source substring check):
        # every reference to the bound exception name must be the direct sole
        # argument of `type(...)`. A substring check for literal "{exc}" would
        # miss `{exc!r}`, `{exc!s}`, `str(exc)`, `exc.args`, or concatenation.
        unsafe_refs = _unsafe_exception_references(handler)
        self.assertEqual(
            unsafe_refs,
            [],
            "the delete-failure NOTE must reference the caught exception only as "
            "the direct argument of `type(...)` (e.g. `type(exc).__name__`) -- "
            "found raw/unsafe reference(s) at line(s) "
            f"{[n.lineno for n in unsafe_refs]} in handler body: "
            f"{ast.unparse(ast.Module(body=handler.body, type_ignores=[]))!r}",
        )
        self.assertIn(
            "type(exc).__name__",
            handler_source,
            "the delete-failure NOTE must be sanitized to the exception TYPE name",
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

    def test_skill_metadata_version_matches_post_merge_correction(self) -> None:
        """Guard: a version/history revert must not be able to go green.

        Pins `metadata.version` to the exact SemVer the post-merge correction
        (cleanup-from-finally + dangling-remediation-text + date-alignment
        fixes) shipped under, so reverting `SKILL.md` to a pre-correction
        version string fails here even if it happens to keep the corrected
        body content intact.
        """
        skill_meta = _frontmatter(SKILL.read_text(encoding="utf-8"))["metadata"]
        self.assertEqual(
            str(skill_meta["version"]),
            "2.1.1",
            "SKILL.md metadata.version must be '2.1.1' -- the PATCH bump that "
            "shipped the post-merge correction. A version/history revert must "
            "not be able to go green.",
        )


def _handler_from_snippet(snippet: str) -> ast.ExceptHandler:
    """Parse a standalone `try/except` snippet, returning its single handler.

    Test-only harness for proving `_unsafe_exception_references` itself
    (Finding #1's "prove the guard against mutations" requirement) against
    representative safe/unsafe handler bodies, independent of the fixture
    file on disk.
    """
    tree = ast.parse(textwrap.dedent(snippet))
    stmt = tree.body[0]
    if not isinstance(stmt, ast.Try):
        raise AssertionError(f"snippet's first statement must be a Try, got {type(stmt)}")
    if len(stmt.handlers) != 1:
        raise AssertionError(f"snippet must have exactly one except handler, got {len(stmt.handlers)}")
    return stmt.handlers[0]


class ExceptionReferenceGuardUnitTests(unittest.TestCase):
    """Mutation proof for `_unsafe_exception_references` (Finding #1).

    A plain `assertNotIn("{exc}", handler_source)` substring check -- the
    pre-hardening version of the anti-leak assertion -- passes on every
    snippet below EXCEPT the literal `f"{exc}"` case, meaning it misses
    `{exc!r}`, `{exc!s}`, `str(exc)`, `exc.args`, and concatenation entirely.
    These tests pin the AST-structural replacement against exactly those
    variants, plus the one safe shape it must continue to accept.
    """

    def test_accepts_type_exc_dunder_name(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print(f"NOTE failed error_type={type(exc).__name__}")
            """
        )
        self.assertEqual(
            _unsafe_exception_references(handler),
            [],
            "type(exc).__name__ is the canonical sanitized shape and must be accepted",
        )

    def test_accepts_bare_type_exc_without_dunder_name(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                kind = type(exc)
                print(f"NOTE failed error_type={kind.__name__}")
            """
        )
        self.assertEqual(
            _unsafe_exception_references(handler),
            [],
            "type(exc) alone (result bound and narrowed later) must also be accepted "
            "-- the guard only constrains how `exc` itself may be referenced",
        )

    def test_rejects_raw_interpolation(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print(f"NOTE failed error={exc}")
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(len(unsafe), 1, "f\"{exc}\" must be flagged as an unsafe leak")

    def test_rejects_repr_conversion(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print(f"NOTE failed error={exc!r}")
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(len(unsafe), 1, "f\"{exc!r}\" must be flagged as an unsafe leak")

    def test_rejects_str_conversion_field(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print(f"NOTE failed error={exc!s}")
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(len(unsafe), 1, "f\"{exc!s}\" must be flagged as an unsafe leak")

    def test_rejects_str_call(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print("NOTE failed error=" + str(exc))
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(len(unsafe), 1, "str(exc) must be flagged as an unsafe leak")

    def test_rejects_args_attribute_access(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print(f"NOTE failed error={exc.args}")
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(len(unsafe), 1, "exc.args must be flagged as an unsafe leak")

    def test_rejects_bare_concatenation(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                message = "NOTE failed error=" + exc
                print(message)
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(len(unsafe), 1, "bare string concatenation with exc must be flagged")

    def test_rejects_passing_exc_to_a_non_type_call(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print(f"NOTE failed error={repr(exc)}")
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(len(unsafe), 1, "repr(exc) must be flagged as an unsafe leak")

    def test_rejects_exc_as_extra_argument_alongside_type(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                print(f"NOTE failed error_type={type(exc).__name__} raw={exc}")
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(
            len(unsafe),
            1,
            "the safe type(exc).__name__ reference must not mask a second, unsafe "
            "raw reference to exc in the same handler",
        )

    def test_rejects_exc_passed_as_second_positional_to_type(self) -> None:
        # Avoid nesting a dict/collection literal inside an f-string
        # expression -- unsupported by the f-string grammar before the
        # PEP 701 relaxation (Python < 3.12); the CI matrix runs 3.11 too.
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception as exc:
                result = type("unused", exc)
                print(result)
            """
        )
        unsafe = _unsafe_exception_references(handler)
        self.assertEqual(
            len(unsafe),
            1,
            "exc must remain the SOLE argument of type(...) -- passed alongside "
            "other arguments it is no longer the accepted shape",
        )

    def test_reference_requires_a_bound_exception_name(self) -> None:
        handler = _handler_from_snippet(
            """
            try:
                pass
            except Exception:
                print("NOTE failed")
            """
        )
        with self.assertRaises(AssertionError):
            _unsafe_exception_references(handler)


if __name__ == "__main__":
    unittest.main()
