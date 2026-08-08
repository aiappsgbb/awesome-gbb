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

import contextlib
import importlib.util
import os
import pathlib
import re
import shlex
import subprocess
import tempfile
import unittest
import unittest.mock

import yaml

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent
EVALS_SKILL = ROOT / "skills" / "foundry-evals"
EVALS_PIN = EVALS_SKILL / "references" / "upstream-pin.md"
EVALS_FIXTURE = EVALS_SKILL / "test-fixture" / "consumer_prompt.md"
PROMPT_AGENTS_FIXTURE = (
    ROOT
    / "skills"
    / "foundry-prompt-agents"
    / "test-fixture"
    / "consumer_prompt.md"
)
SKILL_TEST_WORKFLOW = ROOT / ".github" / "workflows" / "skill-test.yml"
MATRIX_JOB = "copilot-cli-matrix"

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


def _referenced_env(text: str) -> set[str]:
    """Env vars a prompt/shell body reads: `$VAR`, `${VAR}`, `${VAR:+x}`."""
    braced = re.findall(r"\$\{([A-Z][A-Z0-9_]*)[:}\-+?]", text)
    bare = re.findall(r"\$([A-Z][A-Z0-9_]*)\b", text)
    return set(braced) | set(bare)


_ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_SHELL_PUNCTUATION = ";&|()"
_SHORT_PROMPT_FLAG = re.compile(r"-[A-Za-z]*p")
_LEADING_KEYWORDS = frozenset(
    {"if", "elif", "while", "until", "then", "do", "else", "time", "!", "{", "("}
)


def _lex(text: str) -> tuple[list[str], bool]:
    """Tokenise one logical line; `(tokens, closed)`.

    `closed` is False when quoting never closes, which is how a quoted
    string spanning several physical lines is detected. Separators are
    emitted as their own tokens because `punctuation_chars` keeps them out
    of words -- and, crucially, only when they are *unquoted*.
    """
    lexer = shlex.shlex(text, posix=True, punctuation_chars=_SHELL_PUNCTUATION)
    lexer.whitespace_split = True
    tokens: list[str] = []
    while True:
        try:
            token = lexer.get_token()
        except ValueError:
            return tokens, False
        if token is None:
            return tokens, True
        tokens.append(token)


def _logical_lines(body: str) -> list[str]:
    """Physical lines regrouped so no quoted string is cut in half."""
    lines: list[str] = []
    pending = ""
    for physical in body.splitlines():
        candidate = f"{pending}\n{physical}" if pending else physical
        if _lex(candidate)[1]:
            pending = ""
            if candidate.strip():
                lines.append(candidate)
        else:
            pending = candidate
    if pending.strip():
        lines.append(pending)
    return lines


def _command_segments(run: str) -> list[list[str]]:
    """`argv` lists for the executable commands in a `run:` body.

    Full-line comments are dropped *before* backslash-newline
    continuations are folded, so a commented-out line ending in a
    backslash cannot swallow the command beneath it (bash does not
    continue a comment either). Everything after that is `shlex`'s job:
    splitting raw text on separator bytes cannot distinguish `a; b` from
    `echo "a; b"`, and a stdlib lexer can.
    """
    body = "\n".join(
        line for line in run.splitlines() if not line.lstrip().startswith("#")
    )
    body = re.sub(r"\\\n[ \t]*", " ", body)
    segments: list[list[str]] = []
    for line in _logical_lines(body):
        current: list[str] = []
        for token in _lex(line)[0]:
            if token and all(char in _SHELL_PUNCTUATION for char in token):
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(token)
        if current:
            segments.append(current)
    return segments


def _invokes_copilot_prompt(run: str) -> bool:
    """True when a segment *executes* `copilot` with a `-p` prompt flag.

    Substring matching on `"copilot -p"` both over- and under-matches: it
    counts comments and echoed strings, and misses tabs, repeated spaces
    and line continuations.
    """
    for argv in _command_segments(run or ""):
        tokens = list(argv)
        while tokens and (
            _ENV_ASSIGNMENT.match(tokens[0]) or tokens[0] in _LEADING_KEYWORDS
        ):
            tokens.pop(0)
        if not tokens or tokens[0].rsplit("/", 1)[-1] != "copilot":
            continue
        if any(_SHORT_PROMPT_FLAG.fullmatch(token) for token in tokens[1:]):
            return True
    return False


def _synthetic_matrix_workflow(run_bodies: list[str]) -> dict:
    """A minimal workflow doc shaped like the matrix job, for unit cases."""
    return {
        "jobs": {
            MATRIX_JOB: {
                "steps": [
                    {"name": f"synthetic-{index}", "run": body}
                    for index, body in enumerate(run_bodies)
                ]
            }
        }
    }


def _load_matrix_workflow() -> dict:
    return yaml.safe_load(SKILL_TEST_WORKFLOW.read_text(encoding="utf-8"))


def _fixture_running_steps(workflow: dict) -> list[dict]:
    """Matrix steps that actually hand a fixture to the agent.

    Keyed off the real `copilot -p` invocation rather than step names or
    indices, both of which churn. Pattern 26 means there is more than one:
    the main run plus the transient-retry run(s).
    """
    return [
        step
        for step in workflow["jobs"][MATRIX_JOB]["steps"]
        if _invokes_copilot_prompt(step.get("run") or "")
    ]


def _missing_env_by_fixture_step(
    required: set[str], workflow: dict | None = None
) -> dict[str, list[str]]:
    """Per-step shortfall of `required` across every fixture-running step.

    Deliberately not a union over the job's steps: env set only on an
    unrelated setup step would otherwise mask its absence from a step that
    runs the fixture, and the agent inherits the *step* env block.
    """
    workflow = _load_matrix_workflow() if workflow is None else workflow
    shortfall: dict[str, list[str]] = {}
    for index, step in enumerate(_fixture_running_steps(workflow)):
        missing = sorted(required - set(step.get("env") or {}))
        if missing:
            shortfall[f"[{index}] {step.get('name') or '<unnamed>'}"] = missing
    return shortfall


def _tracked_files(root: pathlib.Path) -> list[pathlib.Path]:
    """Git-tracked files under `root`, so local artifacts cannot false-fail."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", str(root)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [(ROOT / name).resolve() for name in listing.stdout.split("\0") if name]


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

    # ── fixture (T3 consumer) contract ────────────────────────────────

    def test_evals_fixture_names_project_endpoint_for_project_scope(self) -> None:
        """The fixture's declared 'Foundry project endpoint' is project-scoped."""
        text = EVALS_FIXTURE.read_text(encoding="utf-8")
        declaration = next(
            line for line in text.splitlines() if "Foundry project endpoint" in line
        )
        self.assertIn(PROJECT_ENV, _referenced_env(declaration))
        self.assertNotIn(ACCOUNT_ENV, _referenced_env(declaration))

    def test_evals_fixture_inventories_the_endpoint_it_consumes(self) -> None:
        """Step 0's auth inventory must cover the endpoint Step 1 actually uses."""
        referenced = _referenced_env(EVALS_FIXTURE.read_text(encoding="utf-8"))
        self.assertIn(PROJECT_ENV, referenced)
        self.assertNotIn(ACCOUNT_ENV, referenced)

    def test_evals_fixture_env_refs_are_exported_by_the_matrix_job(self) -> None:
        """Pattern 11: a fixture may only read env the workflow actually sets.

        The fixture self-FAILs when an inventoried var prints empty, so an
        unexported reference is a guaranteed red matrix leg. Checked per
        fixture-running step: the retry leg needs the same env as the main
        one, and a union would let either hide behind the other.
        """
        referenced = _referenced_env(EVALS_FIXTURE.read_text(encoding="utf-8"))
        azure_refs = {
            v
            for v in referenced
            if v.startswith(("AZURE_", "FOUNDRY_", "ACR_", "APPLICATIONINSIGHTS_"))
        }
        missing = _missing_env_by_fixture_step(azure_refs)
        self.assertEqual(
            missing,
            {},
            f"fixture reads env not exported by {MATRIX_JOB} steps: {missing}",
        )

    def test_prompt_agents_fixture_uses_exported_project_endpoint(self) -> None:
        """Prompt-agent SDK calls consume only the dedicated project endpoint."""
        text = PROMPT_AGENTS_FIXTURE.read_text(encoding="utf-8")
        declarations = [
            line
            for line in text.splitlines()
            if line.startswith("Foundry project endpoint:")
        ]
        self.assertEqual(
            declarations,
            [f"Foundry project endpoint: `${PROJECT_ENV}`"],
        )

        endpoint_refs = _referenced_env(text) & ENDPOINT_ENVS
        self.assertEqual(endpoint_refs, {PROJECT_ENV})

        workflow = _load_matrix_workflow()
        fixture_steps = _fixture_running_steps(workflow)
        self.assertGreaterEqual(
            len(fixture_steps),
            2,
            "expected at least the main + retry copilot -p invocations",
        )
        missing = _missing_env_by_fixture_step(endpoint_refs, workflow)
        self.assertEqual(
            missing,
            {},
            f"prompt fixture reads env not exported by fixture steps: {missing}",
        )

    def test_evals_skill_tree_has_no_account_endpoint_alias(self) -> None:
        """No tracked file under the skill may alias the account var.

        Scoped to Git-tracked sources so untracked local artifacts cannot
        false-fail; this still covers SKILL.md, the pin, the fixture and
        every reference source.
        """
        offenders = [
            str(p.relative_to(ROOT))
            for p in _tracked_files(EVALS_SKILL)
            if ACCOUNT_ENV in p.read_text(encoding="utf-8", errors="ignore")
        ]
        self.assertEqual(sorted(offenders), [])

    # ── helper-level regression coverage ──────────────────────────────
    #
    # These guard the *checkers* above. A contract test is only worth the
    # bytes if it fails when the contract breaks, so each of these mutates
    # a known-good input into a known-bad one and asserts detection.

    def test_fixture_running_steps_are_found_by_invocation_not_position(
        self,
    ) -> None:
        """Fixture steps are identified by the real `copilot -p` invocation.

        Step names and indices churn; the invocation is the contract. Both
        the main run and the transient-retry run must be found (Pattern 26),
        since a var exported to only one of them still fails half the legs.
        """
        workflow = _load_matrix_workflow()
        steps = _fixture_running_steps(workflow)
        self.assertGreaterEqual(
            len(steps),
            2,
            "expected at least the main + retry copilot -p invocations",
        )
        # Non-tautological: the job also runs `copilot --version` and
        # `copilot plugin install`, which must NOT count as fixture runs.
        all_steps = workflow["jobs"][MATRIX_JOB]["steps"]
        self.assertLess(len(steps), len(all_steps))
        selected = {id(step) for step in steps}
        for step in all_steps:
            if id(step) in selected:
                continue
            self.assertNotIn(
                "consumer_prompt.md",
                step.get("run") or "",
                f"step {step.get('name')!r} feeds a fixture but was not selected",
            )

    def test_copilot_invocation_detection_is_command_aware(self) -> None:
        """Detection tolerates real shell forms and ignores mere mentions.

        A literal `"copilot -p"` substring test both misses executable
        forms (extra whitespace, backslash continuation) and counts
        non-executable ones (comments, echoed strings).
        """
        cases = (
            ("single space", 'copilot -p "$(cat prompt.md)"', True),
            ("extra spaces", 'copilot  -p "$(cat prompt.md)"', True),
            ("tab separated", 'copilot\t-p "$(cat prompt.md)"', True),
            (
                "backslash continuation",
                'copilot \\\n  -p "$(cat prompt.md)" \\\n  --allow-all-tools',
                True,
            ),
            ("indented and piped", '  copilot -p "$(cat p.md)" | tee log', True),
            ("env assignment prefix", 'FOO=1 copilot -p "x"', True),
            ("absolute path", '/usr/local/bin/copilot -p "x"', True),
            ("bundled short flags", 'copilot -sp "x"', True),
            ("comment only", "# copilot -p example", False),
            ("indented comment", "   # copilot -p example", False),
            ("echoed mention", 'echo "run copilot -p to start"', False),
            ("other subcommand", "copilot --version", False),
            ("plugin install", "copilot plugin install awesome-gbb@awesome-gbb", False),
            ("unrelated shell", "az account show --output table", False),
        )
        for label, run, expected in cases:
            with self.subTest(case=label):
                workflow = _synthetic_matrix_workflow([run])
                self.assertEqual(
                    len(_fixture_running_steps(workflow)),
                    1 if expected else 0,
                    f"{label}: {run!r}",
                )

    def test_copilot_invocation_detection_honours_shell_quoting(self) -> None:
        """Quoting and control syntax decide what is a command, not raw text.

        Splitting the raw body on `;`, `&` and `|` cannot tell a separator
        from the same byte inside a quoted string, and treats a compound
        command's leading keyword as the program being run. That both
        invents invocations out of echoed prose and hides real ones behind
        an `if`/`while` guard.
        """
        cases = (
            # Quoted separators and mentions are data, never commands.
            ("quoted semicolon mention", 'echo "note; copilot -p x"', False),
            ("quoted andand mention", 'echo "note && copilot -p x"', False),
            ("quoted pipe mention", "echo 'note | copilot -p x'", False),
            ("printf mention", "printf 'copilot -p %s\\n' x", False),
            # Compound-command keywords precede the program; strip them.
            ("if guard", "if copilot -p x; then echo ok; fi", True),
            ("elif guard", "if false; then :; elif copilot -p x; then :; fi", True),
            ("while guard", "while copilot -p x; do :; done", True),
            ("until guard", "until copilot -p x; do :; done", True),
            ("then keyword", "if true; then copilot -p x; fi", True),
            # Newlines separate commands; a lexer must not weld them.
            (
                "newline separated",
                'echo start\ncopilot -p "$(cat prompt.md)"\necho done',
                True,
            ),
            ("newline boundary not welded", "copilot --version\necho -p later", False),
            ("quoted body spanning lines", 'echo "line one\ncopilot -p x"', False),
        )
        for label, run, expected in cases:
            with self.subTest(case=label):
                workflow = _synthetic_matrix_workflow([run])
                self.assertEqual(
                    len(_fixture_running_steps(workflow)),
                    1 if expected else 0,
                    f"{label}: {run!r}",
                )

    def test_missing_env_detected_when_dropped_from_a_single_fixture_step(
        self,
    ) -> None:
        """The masking defect: per-step checking, never a cross-step union.

        `FOUNDRY_PROJECT_ENDPOINT` is also exported by the unrelated
        'Resolve Foundry project context' setup step, so a union over all
        matrix steps still contains it after it is dropped from a step that
        actually runs the fixture. Each fixture-running step is checked on
        its own.
        """
        for victim in range(2):
            with self.subTest(dropped_from_step=victim):
                workflow = _load_matrix_workflow()
                steps = _fixture_running_steps(workflow)
                del steps[victim]["env"][PROJECT_ENV]

                union = set().union(
                    *(
                        set(s.get("env") or {})
                        for s in workflow["jobs"][MATRIX_JOB]["steps"]
                    )
                )
                self.assertIn(
                    PROJECT_ENV, union, "precondition: another step masks it"
                )

                missing = _missing_env_by_fixture_step({PROJECT_ENV}, workflow)
                self.assertTrue(
                    missing, f"drop from fixture step {victim} went undetected"
                )

    def test_tracked_scan_ignores_untracked_artifacts(self) -> None:
        """`__pycache__`, venvs, temp workdirs and editor backups are noise.

        Scanning the working tree lets a local artifact that merely mentions
        the account var false-fail validation. Only Git-tracked source counts.
        """
        with tempfile.TemporaryDirectory(
            prefix=".endpoint-scan-probe-", dir=EVALS_SKILL
        ) as workdir:
            probe = pathlib.Path(workdir) / "artifact.txt"
            probe.write_text(f"{ACCOUNT_ENV}\n", encoding="utf-8")
            self.assertNotIn(probe.resolve(), _tracked_files(EVALS_SKILL))
            self.test_evals_skill_tree_has_no_account_endpoint_alias()

    def test_untracked_probe_owns_its_artifact(self) -> None:
        """The probe must not touch anything it did not create.

        A fixed probe path deletes whatever already sits there and races
        parallel runs; an exclusively owned temporary directory cannot.
        """
        bystander = EVALS_SKILL / "__pycache__"
        preexisting = bystander.exists()
        bystander.mkdir(exist_ok=True)
        try:
            before = {p.name for p in EVALS_SKILL.iterdir()}
            self.test_tracked_scan_ignores_untracked_artifacts()
            self.assertTrue(
                bystander.is_dir(), "probe removed a directory it did not create"
            )
            self.assertEqual(
                before,
                {p.name for p in EVALS_SKILL.iterdir()},
                "probe leaked or removed entries under the skill",
            )
        finally:
            if not preexisting:
                with contextlib.suppress(OSError):
                    bystander.rmdir()

    def test_tracked_scan_still_covers_every_tracked_source(self) -> None:
        """Narrowing to tracked files must not narrow detection coverage."""
        tracked = _tracked_files(EVALS_SKILL)
        for required in (
            EVALS_PIN,
            EVALS_FIXTURE,
            EVALS_SKILL / "SKILL.md",
        ):
            self.assertIn(required.resolve(), tracked)
        self.assertTrue(
            any(p.suffix == ".py" for p in tracked),
            "expected the skill's reference python sources to be scanned",
        )

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
