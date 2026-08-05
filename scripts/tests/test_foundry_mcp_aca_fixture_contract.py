#!/usr/bin/env python3
"""Contract tests for the foundry-mcp-aca live fixture.

These tests enforce structural and behavioral contracts on consumer_prompt.md
that CI cannot catch through grep alone. They verify:
- Port lifecycle coherence (no placeholder/probe mismatch)
- Shell correctness (session header must use Bash arrays, not scalar quoting)
- MCP protocol conformance (initialized must be status-gated, not || true)
- Named tool invocation (echo with exact payload assertion, no first-tool fallback)
- Prose/hard-gate consistency (all three protocol steps listed)
- SKILL.md version is PATCH (1.2.4)
- Pin script validates mcp explicitly
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import pathlib
import re
import shlex
import subprocess
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT / "skills" / "foundry-mcp-aca" / "test-fixture" / "consumer_prompt.md"
)
SKILL_MD = ROOT / "skills" / "foundry-mcp-aca" / "SKILL.md"
PIN_FILE = (
    ROOT / "skills" / "foundry-mcp-aca" / "references" / "upstream-pin.md"
)
STATE_PATH = pathlib.Path("/tmp/foundry-mcp-aca-state.env")
STATE_LOCK_PATH = pathlib.Path("/tmp/foundry-mcp-aca-state.env.lock")
SMOKE_MARKER_PATH = pathlib.Path("/tmp/foundry-mcp-aca-smoke-result")
SMOKE_MARKER_LOCK_PATH = pathlib.Path("/tmp/foundry-mcp-aca-smoke-result.lock")
STATE_MARKER = 'STATE_FILE="/tmp/foundry-mcp-aca-state.env"'
SMOKE_MARKER_LITERAL = "/tmp/foundry-mcp-aca-smoke-result"
BOOTSTRAP_BLOCK_HEADING = "### Deterministic bootstrap Bash block (MANDATORY)"
PROVISION_BLOCK_HEADING = "### Deterministic provision Bash block (MANDATORY)"
SCAFFOLD_BLOCK_HEADING = (
    "### Deterministic scaffold-authoring Bash block (MANDATORY)"
)
STEP_1_HEADING = "## Step 1 — goal + scaffolding constraints"
STEP_2_HEADING = "## Step 2 — create the deterministic scaffold"
STEP_4_HEADING = "## Step 4 — `azd up` (HARD GATE)"
STEP_2_BOUNDARY_PREFIX = "---\n\n## Step 2 — "
STEP_4_BOUNDARY = f"---\n\n{STEP_4_HEADING}"
DETERMINISTIC_GUARD_HEADING = (
    "**CRITICAL — deterministic scaffold authoring (MANDATORY).**"
)
EXPECTED_PARAMETERS_HEREDOC = """{
  "\\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "appName": { "value": "${APP_NAME}" },
    "uamiResourceId": { "value": "${UAMI_RESOURCE_ID}" },
    "acrServer": { "value": "${ACR_SERVER}" }
  }
}"""
EXPECTED_AZURE_YAML_HEREDOC = """name: ${APP_NAME}
metadata:
  template: ci-smoke-mcp@0.0.1
services:
  ${APP_NAME}:
    project: ./src
    language: python
    host: containerapp
    docker:
      path: Dockerfile
      context: ."""
SCAFFOLD_HEREDOC_SPECS = (
    ("src/server.py", "'", "PY", None),
    ("src/requirements.txt", "'", "REQ", None),
    ("src/Dockerfile", "'", "DOCKER", None),
    ("infra/main.bicep", "'", "BICEP", None),
    (
        "infra/main.parameters.json",
        "",
        "PARAMS",
        EXPECTED_PARAMETERS_HEREDOC,
    ),
    ("azure.yaml", "", "AZDYAML", EXPECTED_AZURE_YAML_HEREDOC),
)
SCAFFOLD_FILES = tuple(spec[0] for spec in SCAFFOLD_HEREDOC_SPECS)
SCAFFOLD_SOURCE_FALLBACK = (
    "source /tmp/foundry-mcp-aca-state.env || { "
    "printf 'SMOKE_RESULT=FAIL scaffold block failed\\n' > "
    "/tmp/foundry-mcp-aca-smoke-result; exit 1; }"
)
SCAFFOLD_SET_FLAGS = "set -Eeuo pipefail"
SCAFFOLD_ERR_TRAP = (
    """trap 'printf "SMOKE_RESULT=FAIL scaffold block failed\\n" > """
    """/tmp/foundry-mcp-aca-smoke-result' ERR"""
)
SCAFFOLD_STATE_VARIABLES = (
    "APP_NAME",
    "PROJECT_DIR",
    "UAMI_RESOURCE_ID",
    "ACR_SERVER",
)


def _bootstrap_stub_bin(root: pathlib.Path) -> pathlib.Path:
    """Install deterministic no-network az/azd/uuidgen stubs for block replay."""
    bin_dir = root / "bootstrap-bin"
    bin_dir.mkdir()
    scripts = {
        "az": "#!/usr/bin/env bash\nexit 0\n",
        "azd": "#!/usr/bin/env bash\nexit 0\n",
        "uuidgen": "#!/usr/bin/env bash\nprintf 'ABCDEF12-3456-7890\\n'\n",
    }
    for name, content in scripts.items():
        path = bin_dir / name
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)
    return bin_dir


def _scaffold_state_gate(variables: tuple[str, ...]) -> str:
    """Build the one allowed completeness gate for persisted scaffold state."""
    checks = " || ".join(f'-z "${{{variable}:-}}"' for variable in variables)
    return (
        f"if [[ {checks} ]]; then "
        "printf 'SMOKE_RESULT=FAIL scaffold state incomplete\\n' > "
        "/tmp/foundry-mcp-aca-smoke-result; exit 1; fi"
    )


SCAFFOLD_STATE_GATE = _scaffold_state_gate(SCAFFOLD_STATE_VARIABLES)
SCAFFOLD_PREAMBLE_COMMANDS = (
    SCAFFOLD_SOURCE_FALLBACK,
    SCAFFOLD_SET_FLAGS,
    SCAFFOLD_ERR_TRAP,
    SCAFFOLD_STATE_GATE,
    'mkdir -p "$PROJECT_DIR/src" "$PROJECT_DIR/infra"',
    'cd "$PROJECT_DIR"',
)
EXPECTED_SERVER_PY = '''"""Tiny MCP server for the CI smoke — single `echo` tool + /health route."""
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("ci-smoke-mcp")


@mcp.custom_route("/health", methods=["GET"])
async def health(_req: Request) -> PlainTextResponse:
    return PlainTextResponse("ok", status_code=200)


@mcp.tool()
async def echo(message: str) -> str:
    """Echo back the message prefixed with `echoed: `."""
    return f"echoed: {message}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
'''
EXPECTED_REQUIREMENTS_TXT = "fastmcp~=2.14.7\n"
EXPECTED_DOCKERFILE = """FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8080
CMD ["python", "server.py"]
"""
EXPECTED_MAIN_BICEP = """@description('Deployment region — must match the CAE.')
param location string = 'swedencentral'

@description('Container App name (also used as ACR repo tag).')
param appName string

@description('Container image reference. Defaults to placeholder; azd deploy patches with the real image.')
param image string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Resource ID of the user-assigned managed identity used for ACR pull.')
param uamiResourceId string

@description('ACR login server (e.g. myacr.azurecr.io). Must be explicit — do NOT derive from image param.')
param acrServer string

@description('Name of the pre-provisioned Container Apps Environment.')
param caeName string = 'cae-awesome-gbb-ci'

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: caeName
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: {
    'azd-service-name': appName
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiResourceId}': {}
    }
  }
  properties: {
    environmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acrServer
          identity: uamiResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: image
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          // Note: probes are omitted for the placeholder→deploy lifecycle.
          // The placeholder image (containerapps-helloworld) serves on port 80
          // while the real server serves on 8080. Probes targeting 8080 would
          // prevent the placeholder revision from becoming healthy, potentially
          // blocking azd provision. azd deploy immediately swaps the image to
          // the real server which does serve on 8080. Production deployments
          // should add liveness/startup probes after the first successful deploy.
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output appName string = app.name
"""
EXPECTED_GUARD_SENTENCES = (
    "Invoke only the prescribed Bash block in Step 2 to author the six "
    "scaffold files.",
    "NEVER use Edit, Create, or Write file tools.",
    "Never inspect or patch the generated files after the scaffold block runs.",
    "If the scaffold block fails, write SMOKE_RESULT=FAIL and stop.",
    "There is no second file-write path.",
)


@contextlib.contextmanager
def _isolated_locked_file(path: pathlib.Path, lock_path: pathlib.Path):
    """Serialize a fixed-path probe and restore the file's original bytes."""
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        existed = path.exists()
        original = path.read_bytes() if existed else None
        path.unlink(missing_ok=True)
        try:
            yield
        finally:
            if existed:
                assert original is not None
                path.write_bytes(original)
            else:
                path.unlink(missing_ok=True)
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _isolated_shipped_state_file():
    """Serialize exact state-block execution and restore the prior state bytes."""
    return _isolated_locked_file(STATE_PATH, STATE_LOCK_PATH)


def _isolated_shipped_smoke_marker():
    """Serialize marker probes and restore the prior marker bytes."""
    return _isolated_locked_file(SMOKE_MARKER_PATH, SMOKE_MARKER_LOCK_PATH)


def _run_bash(
    shell: str,
    env: dict[str, str],
    *,
    cwd: pathlib.Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run an architectural shell probe with a bounded execution time."""
    return subprocess.run(
        ["bash", "-c", shell],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


def _scaffold_block_with_probe_marker(
    scaffold_block: str, probe_marker: pathlib.Path
) -> str:
    """Rewrite only the marker path after proving the shipped literal contract."""
    commands, _heredocs, _events = _parse_scaffold_shell(scaffold_block)
    marker_commands = [
        command for command in commands if "SMOKE_RESULT=FAIL scaffold" in command
    ]
    literal_marker_count = scaffold_block.count(SMOKE_MARKER_LITERAL)
    if not marker_commands or literal_marker_count != len(marker_commands):
        raise AssertionError(
            "every executable scaffold FAIL writer must use the literal fixed "
            "marker path before execution-only marker-path replacement; "
            f"writers={marker_commands!r} literal_count={literal_marker_count}"
        )
    if any(SMOKE_MARKER_LITERAL not in command for command in marker_commands):
        raise AssertionError(
            "every executable scaffold FAIL writer must use the literal fixed "
            "marker path before execution-only marker-path replacement"
        )
    return scaffold_block.replace(
        SMOKE_MARKER_LITERAL,
        shlex.quote(str(probe_marker)),
    )


def _standard_bash_block_containing(markdown: str, marker: str) -> str:
    """Extract the standard Bash fence body containing a unique marker."""
    marker_index = markdown.index(marker)
    block_start = markdown.rfind("```bash\n", 0, marker_index)
    block_end = markdown.index("```", marker_index)
    if block_start < 0:
        raise AssertionError(f"standard Bash fence not found for {marker!r}")
    return markdown[block_start + len("```bash\n") : block_end]


def _shell_fences(markdown: str) -> list[tuple[int, str]]:
    """Extract Bash-compatible fences across backtick/tilde and indentation forms."""
    lines = markdown.splitlines(keepends=True)
    offsets: list[int] = []
    offset = 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)

    opener = re.compile(
        r"^(?P<indent> {0,3})(?P<marker>`{3,}|~{3,})"
        r"[ \t]*(?:bash|sh|shell)[ \t]*\r?\n?$",
        re.IGNORECASE,
    )
    fences: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = opener.match(lines[index])
        if match is None:
            index += 1
            continue
        marker = match.group("marker")
        indent = match.group("indent")
        closing = re.compile(
            rf"^{re.escape(indent)}{re.escape(marker[0])}"
            rf"{{{len(marker)},}}[ \t]*\r?\n?$"
        )
        body_start = index + 1
        index = body_start
        while index < len(lines) and closing.match(lines[index]) is None:
            index += 1
        if index == len(lines):
            raise AssertionError(
                f"unterminated {marker[0]!r} shell fence at offset "
                f"{offsets[body_start - 1]}"
            )
        fences.append((offsets[body_start - 1], "".join(lines[body_start:index])))
        index += 1
    return fences


def _bootstrap_block(markdown: str) -> str:
    """Extract the sole first-action bootstrap Bash block."""
    headings = list(
        re.finditer(rf"(?m)^{re.escape(BOOTSTRAP_BLOCK_HEADING)}$", markdown)
    )
    if len(headings) != 1:
        raise AssertionError(
            "expected the exact mandatory bootstrap heading exactly once"
        )

    bash_fences = list(
        re.finditer(r"(?m)^```bash\n(?P<body>.*?)^```(?:\n|$)", markdown, re.DOTALL)
    )
    if not bash_fences:
        raise AssertionError("fixture must contain a standard Bash fence")
    first_fence = bash_fences[0]
    shell_fences = _shell_fences(markdown)
    if not shell_fences or shell_fences[0][0] != first_fence.start():
        raise AssertionError(
            "the mandatory bootstrap must be the first shell action regardless "
            "of Markdown fence style"
        )
    if headings[0].end() > first_fence.start():
        raise AssertionError(
            "the mandatory bootstrap heading must immediately precede the first "
            "Bash action"
        )
    between = markdown[headings[0].end():first_fence.start()]
    if between != "\n\n":
        raise AssertionError(
            "the mandatory bootstrap heading must be followed only by one blank "
            "line and the first Bash fence"
        )
    return first_fence.group("body")


def _step_1_state_block(markdown: str) -> str:
    """Compatibility wrapper for tests that replay initial state creation."""
    return _bootstrap_block(markdown)


def _provision_block(markdown: str) -> str:
    """Extract the sole prescribed provision Bash block."""
    headings = list(
        re.finditer(rf"(?m)^{re.escape(PROVISION_BLOCK_HEADING)}$", markdown)
    )
    if len(headings) != 1:
        raise AssertionError(
            "expected the exact mandatory provision heading exactly once"
        )
    next_step = markdown.find("\n---\n\n## Step 5 ", headings[0].end())
    if next_step < 0:
        raise AssertionError("provision block must end before the exact Step 5 boundary")
    section = markdown[headings[0].start():next_step]
    shape = re.match(
        rf"{re.escape(PROVISION_BLOCK_HEADING)}\n\n"
        r"```bash\n(?P<body>.*?)```\n\n",
        section,
        re.DOTALL,
    )
    if shape is None:
        raise AssertionError(
            "the prescribed provision section must contain exactly one standard "
            "Bash fence and no alternate command path"
        )
    if len(_shell_fences(section)) != 1:
        raise AssertionError(
            "the prescribed provision section must not expose a second command path"
        )
    return shape.group("body")


def _heredoc_spec(raw_line: str) -> tuple[str, bool] | None:
    """Return an unquoted heredoc delimiter and whether tab stripping is active."""
    single_quoted = False
    double_quoted = False
    escaped = False
    arithmetic_depth = 0
    index = 0
    while index < len(raw_line):
        char = raw_line[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if char == "\\" and not single_quoted:
            escaped = True
            index += 1
            continue
        if char == "'" and not double_quoted:
            single_quoted = not single_quoted
            index += 1
            continue
        if char == '"' and not single_quoted:
            double_quoted = not double_quoted
            index += 1
            continue
        if char == "#" and not single_quoted and not double_quoted:
            break
        if (
            not single_quoted
            and not double_quoted
            and raw_line[index : index + 2] == "(("
        ):
            arithmetic_depth += 1
            index += 2
            continue
        if (
            arithmetic_depth
            and not single_quoted
            and not double_quoted
            and raw_line[index : index + 2] == "))"
        ):
            arithmetic_depth -= 1
            index += 2
            continue
        if (
            char == "<"
            and not single_quoted
            and not double_quoted
            and arithmetic_depth == 0
            and raw_line[index : index + 2] == "<<"
            and raw_line[index : index + 3] != "<<<"
        ):
            cursor = index + 2
            strip_tabs = cursor < len(raw_line) and raw_line[cursor] == "-"
            cursor += int(strip_tabs)
            while cursor < len(raw_line) and raw_line[cursor] in " \t":
                cursor += 1
            quote = raw_line[cursor] if cursor < len(raw_line) else ""
            if quote in ("'", '"'):
                cursor += 1
                end = raw_line.find(quote, cursor)
                if end < 0:
                    return None
                delimiter = raw_line[cursor:end]
            else:
                match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", raw_line[cursor:])
                if match is None:
                    return None
                delimiter = match.group(0)
            return delimiter, strip_tabs
        index += 1
    return None


def _shell_lines_without_heredoc_bodies(shell: str) -> list[str]:
    """Return logical command lines while excluding actual heredoc bodies."""
    command_lines: list[str] = []
    heredoc_delimiter: str | None = None
    strip_tabs = False
    for raw_line in shell.replace("\\\n", " ").splitlines():
        if heredoc_delimiter is not None:
            candidate = raw_line.lstrip("\t") if strip_tabs else raw_line
            if candidate == heredoc_delimiter:
                heredoc_delimiter = None
                strip_tabs = False
            continue

        command_lines.append(raw_line)
        spec = _heredoc_spec(raw_line)
        if spec is not None:
            heredoc_delimiter, strip_tabs = spec
    if heredoc_delimiter is not None:
        raise AssertionError(f"unterminated heredoc delimiter: {heredoc_delimiter}")
    return command_lines


def _command_lines_with_tokens(shell: str, expected: tuple[str, ...]) -> list[str]:
    """Return executable logical lines containing an adjacent token sequence."""
    commands: list[str] = []
    for raw_line in _shell_lines_without_heredoc_bodies(shell):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            lexer = shlex.shlex(
                stripped,
                posix=True,
                punctuation_chars="();|&$",
            )
            lexer.whitespace_split = True
            lexer.commenters = "#"
            tokens = list(lexer)
        except ValueError:
            tokens = stripped.split()
        for index in range(len(tokens) - len(expected) + 1):
            candidate = tokens[index : index + len(expected)]
            executable = pathlib.PurePosixPath(candidate[0]).name
            if executable == expected[0] and tuple(candidate[1:]) == expected[1:]:
                commands.append(stripped)
    return commands


def _azd_up_command_lines(shell: str) -> list[str]:
    """Return executable lines that invoke `azd up`, excluding heredoc bodies."""
    return _command_lines_with_tokens(shell, ("azd", "up"))


def _azd_auth_login_command_lines(shell: str) -> list[str]:
    """Return executable lines that invoke `azd auth login`."""
    return _command_lines_with_tokens(shell, ("azd", "auth", "login"))


def _scaffold_block(markdown: str) -> str:
    """Extract the Bash body only when the complete Step 2 shape is exact."""
    scaffold_headings = list(
        re.finditer(rf"(?m)^{re.escape(SCAFFOLD_BLOCK_HEADING)}$", markdown)
    )
    if len(scaffold_headings) != 1:
        raise AssertionError(
            "expected the exact mandatory scaffold heading exactly once globally"
        )
    starts = list(re.finditer(rf"(?m)^{re.escape(STEP_2_HEADING)}$", markdown))
    boundaries = list(
        re.finditer(rf"(?m)^{re.escape(STEP_4_BOUNDARY)}$", markdown)
    )
    if len(starts) != 1 or len(boundaries) != 1:
        raise AssertionError(
            "expected one exact scaffold Step 2 heading and one exact Step 4 boundary"
        )
    if boundaries[0].start() <= starts[0].start():
        raise AssertionError("the exact Step 4 boundary must follow scaffold Step 2")

    section = markdown[starts[0].start():boundaries[0].start()]
    shape = re.fullmatch(
        rf"{re.escape(STEP_2_HEADING)}\n\n"
        rf"{re.escape(SCAFFOLD_BLOCK_HEADING)}\n\n"
        r"```bash\n(?P<body>.*?)```\n\n",
        section,
        re.DOTALL,
    )
    if shape is None:
        raise AssertionError(
            "Step 2 must contain only the exact heading, the exact "
            "mandatory scaffold heading, and one standard triple-backtick Bash fence"
        )
    body = shape.group("body")
    if re.search(r"(?m)^[ \t]*(?:`{3,}|~{3,})", body):
        raise AssertionError("the scaffold Bash block must not contain nested fences")
    return body


def _parse_scaffold_shell(
    shell: str,
) -> tuple[
    list[str],
    list[tuple[str, str, str, str]],
    list[tuple[str, str]],
]:
    """Separate executable lines from heredoc bodies and closing delimiters."""
    lines = shell.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    commands: list[str] = []
    events: list[tuple[str, str]] = []
    heredocs: list[tuple[str, str, str, str]] = []
    opener = re.compile(
        r"cat > (?P<path>[^ \t]+) <<(?P<quote>['\"]?)"
        r"(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)"
    )

    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue

        match = opener.fullmatch(line)
        commands.append(line)
        events.append(("command", line))
        if match is None:
            index += 1
            continue

        delimiter = match.group("delimiter")
        body_start = index + 1
        index = body_start
        while index < len(lines) and lines[index] != delimiter:
            index += 1
        if index == len(lines):
            raise AssertionError(f"unterminated heredoc {delimiter!r}")

        heredocs.append(
            (
                match.group("path"),
                match.group("quote"),
                delimiter,
                "\n".join(lines[body_start:index]),
            )
        )
        events.append(("heredoc-close", delimiter))
        index += 1

    return commands, heredocs, events


def _scaffold_shell_contract(shell: str) -> list[tuple[str, str]]:
    """Validate the scaffold's exact executable-command allowlist."""
    commands, heredocs, events = _parse_scaffold_shell(shell)
    if len(heredocs) != len(SCAFFOLD_FILES):
        raise AssertionError(
            f"expected exactly six scaffold heredocs, found {len(heredocs)}"
        )

    expected_openers = []
    expected_events: list[tuple[str, str]] = [
        ("command", command) for command in SCAFFOLD_PREAMBLE_COMMANDS
    ]
    for (
        expected_path,
        expected_quote,
        expected_delimiter,
        expected_body,
    ), (path, quote, delimiter, body) in zip(
        SCAFFOLD_HEREDOC_SPECS,
        heredocs,
    ):
        if path != expected_path:
            raise AssertionError(
                "scaffold heredocs must target the six literal paths in canonical "
                f"order; expected {expected_path!r}, found {path!r}"
            )
        if quote != expected_quote:
            heredoc_kind = "quoted" if expected_quote else "expanding unquoted"
            raise AssertionError(f"{path} must use a {heredoc_kind} heredoc")
        if delimiter != expected_delimiter:
            raise AssertionError(
                f"{path} must use literal heredoc delimiter {expected_delimiter!r}"
            )
        if expected_body is not None and body != expected_body:
            raise AssertionError(
                f"{path} must use the exact expanding heredoc template"
            )
        expected_opener = (
            f"cat > {path} "
            f"<<{expected_quote}{expected_delimiter}{expected_quote}"
        )
        expected_openers.append(expected_opener)
        expected_events.extend(
            (("command", expected_opener), ("heredoc-close", delimiter))
        )

    expected_commands = [*SCAFFOLD_PREAMBLE_COMMANDS, *expected_openers]
    if commands != expected_commands or events != expected_events:
        raise AssertionError(
            "scaffold executable lines must be exactly the restored-state preamble "
            "and six literal cat heredocs in canonical order; "
            f"found commands={commands!r}"
        )
    return events


def _assert_single_scaffold_writer_block(
    markdown: str, scaffold_block: str
) -> None:
    """Reject scaffold writes anywhere outside the exact canonical block."""
    canonical_fence = f"```bash\n{scaffold_block}```"
    if markdown.count(canonical_fence) != 1:
        raise AssertionError(
            "the exact combined scaffold Bash fence must occur exactly once"
        )
    outside_scaffold = markdown.replace(canonical_fence, "", 1)
    authoring_primitive = re.compile(
        r"(?:\bcat\s*>|\btee\b|"
        r"\b(?:echo|printf)\b[^\n]*>>?|"
        r"\b(?:touch|install|cp|mv)\b)"
    )
    logical_lines = outside_scaffold.replace("\\\n", " ").splitlines()
    second_writers = [
        line
        for line in logical_lines
        if any(path in line for path in SCAFFOLD_FILES)
        and authoring_primitive.search(line)
    ]
    if second_writers:
        raise AssertionError(
            "scaffold target paths may not be paired with authoring primitives "
            f"outside the canonical block; found {second_writers!r}"
        )


def _normalize_text(text: str) -> str:
    """Normalize line endings and tolerate only a missing terminal newline."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized if normalized.endswith("\n") else normalized + "\n"


class FoundryMcpAcaFixtureContractTests(unittest.TestCase):
    """Structural contract tests for consumer_prompt.md."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = FIXTURE.read_text(encoding="utf-8")
        cls.skill = SKILL_MD.read_text(encoding="utf-8")
        cls.pin = PIN_FILE.read_text(encoding="utf-8")

    # --- Issue #1: Port lifecycle coherence ---

    def test_no_probe_port_mismatch_with_placeholder(self) -> None:
        """If probes target port 8080, no placeholder image serving port 80."""
        has_probe_8080 = "port: 8080" in self.fixture and "probes:" in self.fixture
        has_placeholder_80 = "containerapps-helloworld" in self.fixture
        # Both cannot coexist — probes on 8080 will never pass against a port-80 image
        self.assertFalse(
            has_probe_8080 and has_placeholder_80,
            "Fixture has probes targeting port 8080 with a placeholder image "
            "that serves on port 80 — the startup probe can never become healthy "
            "during the placeholder window, potentially blocking azd provision.",
        )

    # --- Issue #2: Session header shell correctness ---

    def test_session_header_uses_bash_array(self) -> None:
        """Session header must use Bash array, not scalar with embedded quotes."""
        # Anti-pattern: SESSION_HEADER="-H \"mcp-session-id: $SESSION_ID\""
        self.assertNotIn(
            'SESSION_HEADER="-H',
            self.fixture,
            "Session header uses scalar with embedded quotes — shell does not "
            "re-parse quotes in variable expansions. Use a Bash array instead.",
        )
        # Must use array pattern
        self.assertIn("SESSION_ARGS", self.fixture)

    # --- Issue #3: notifications/initialized must be status-gated ---

    def test_initialized_notification_captures_status(self) -> None:
        """notifications/initialized must NOT be silently swallowed with || true."""
        # Find the notifications/initialized section
        init_section_match = re.search(
            r'notifications/initialized.*?\n```', self.fixture, re.DOTALL
        )
        self.assertIsNotNone(init_section_match, "notifications/initialized section not found")
        init_section = init_section_match.group(0)
        # Must NOT use bare || true that swallows HTTP errors
        self.assertNotIn(
            "|| true",
            init_section,
            "notifications/initialized uses `|| true` which swallows failures — "
            "must capture and assert HTTP status.",
        )

    # --- Issue #4: Named tool invocation with exact payload ---

    def test_tools_call_uses_named_tool_not_first_fallback(self) -> None:
        """tools/call must invoke a named tool with known args, not fallback to first."""
        # Anti-pattern: FIRST_TOOL=$(... .result.tools[0].name ...) then call with {}
        self.assertNotIn(
            "FIRST_TOOL",
            self.fixture,
            "Fixture uses dynamic first-tool fallback — must invoke a named tool "
            "(echo) with known arguments and assert exact payload.",
        )

    def test_tools_call_asserts_exact_echo_payload(self) -> None:
        """tools/call on echo must assert 'echoed: <probe>' in response."""
        self.assertIn(
            "echoed:",
            self.fixture,
            "Fixture does not assert exact echo payload — must verify "
            "'echoed: <probe>' in tools/call response.",
        )

    def test_tools_call_asserts_no_error(self) -> None:
        """tools/call must verify isError is not true."""
        self.assertIn(
            "isError",
            self.fixture,
            "Fixture does not check isError — must verify tools/call "
            "did not return an error response.",
        )

    # --- Issue #5: Prose/hard-gate consistency ---

    def test_intro_mentions_tools_call(self) -> None:
        """Fixture intro must mention tools/call as part of the acceptance criteria."""
        # First 20 lines = intro section
        intro = "\n".join(self.fixture.split("\n")[:20])
        self.assertIn(
            "tools/call",
            intro,
            "Fixture intro does not mention tools/call — hard gates must include "
            "all three protocol steps (initialize + tools/list + tools/call).",
        )

    def test_hard_gates_list_includes_tools_call(self) -> None:
        """Pattern 25 hard gate list must include tools/call."""
        # Find the hard gates section
        gates_match = re.search(
            r"hard gates.*?(?=\n---|\nDo NOT chain)",
            self.fixture,
            re.DOTALL | re.IGNORECASE,
        )
        self.assertIsNotNone(gates_match)
        gates_section = gates_match.group(0)
        self.assertIn("tools/call", gates_section)

    # --- Issue #6: Correct dates (2026, not 2025) ---

    def test_spec_has_correct_year(self) -> None:
        """Design spec must use 2026, not 2025."""
        spec_path = ROOT / "docs" / "superpowers" / "specs" / "foundry-mcp-aca-refresh-1.2.4.md"
        if spec_path.exists():
            spec = spec_path.read_text(encoding="utf-8")
            self.assertNotIn("2025-08-05", spec, "Spec has wrong year — should be 2026")

    # --- Issue #7: PATCH version ---

    def test_skill_version_is_patch(self) -> None:
        """SKILL.md version must be 1.2.4 (PATCH)."""
        self.assertIn('version: "1.2.4"', self.skill)

    # --- Pin validation contracts ---

    def test_pin_script_installs_mcp_explicitly(self) -> None:
        """Pin validation script must explicitly install mcp with bounded specifier."""
        self.assertRegex(
            self.pin,
            r"mcp[~>=<]",
            "Pin script does not install mcp explicitly — must use bounded specifier.",
        )

    def test_pin_script_asserts_mcp_version(self) -> None:
        """Pin script must assert mcp version via importlib.metadata."""
        self.assertIn("importlib.metadata", self.pin)
        self.assertIn("mcp", self.pin)

    def test_pin_script_asserts_jobs_operations(self) -> None:
        """Pin script must assert JobsOperations.get and begin_create_or_update."""
        self.assertIn("JobsOperations", self.pin)
        self.assertIn("get", self.pin)
        self.assertIn("begin_create_or_update", self.pin)

    def test_ki001_does_not_claim_fastmcp3_requires_mcp2(self) -> None:
        """KI-001 must not claim FastMCP 3 requires MCP 2 — it still pins mcp<2."""
        self.assertNotIn("requires mcp>=2.0", self.pin)
        self.assertNotIn("requires mcp>=2", self.pin.split("KI-001")[1].split("KI-002")[0] if "KI-002" in self.pin else self.pin.split("KI-001")[1])

    # --- Issue #8: Registry must not derive server from placeholder image ---

    def test_registry_uses_explicit_acr_param_not_image_split(self) -> None:
        """Registries must use an explicit ACR server param, not split(image, '/')[0].

        When the default image is mcr.microsoft.com/..., split(image, '/')[0]
        resolves to 'mcr.microsoft.com' — registering MCR as a managed-identity
        registry, which fails because MCR is public and doesn't accept MI tokens.
        """
        self.assertNotIn(
            "split(image, '/')[0]",
            self.fixture,
            "Bicep uses split(image, '/')[0] for registry server — this resolves "
            "to mcr.microsoft.com when image is the MCR placeholder, causing "
            "managed-identity pull failure. Use an explicit acrServer param.",
        )

    def test_registry_server_references_acr_param(self) -> None:
        """Registries block must reference an explicit ACR server parameter."""
        # Must have an acrServer or acrLoginServer param in the Bicep
        self.assertRegex(
            self.fixture,
            r"param\s+acr(Server|LoginServer)\s+string",
            "Bicep must declare an explicit ACR server parameter for registries.",
        )

    # --- Issue #9: Unique service identity per run ---

    def test_service_tag_uses_app_name_variable(self) -> None:
        """azd-service-name must use $APP_NAME, not static 'mcp'."""
        # Find the Bicep tags block; static 'mcp' causes collision in shared RG
        bicep_match = re.search(
            r"tags:\s*\{[^}]*azd-service-name[^}]*\}",
            self.fixture, re.DOTALL
        )
        self.assertIsNotNone(bicep_match, "azd-service-name tag not found in Bicep")
        tag_block = bicep_match.group(0)
        # Must NOT be hardcoded 'mcp' — must reference appName param
        self.assertNotIn(
            "'mcp'",
            tag_block,
            "azd-service-name uses static 'mcp' — causes collision in shared CI RG. "
            "Must use appName parameter for per-run uniqueness.",
        )

    def test_azure_yaml_service_key_matches_bicep_tag(self) -> None:
        """azure.yaml service key must not be static 'mcp' if Bicep uses variable tag."""
        # The azure.yaml is now generated via heredoc with ${APP_NAME} as service key
        # Verify the fixture uses $APP_NAME (or ${APP_NAME}) in the services block
        self.assertRegex(
            self.fixture,
            r"\$\{?APP_NAME\}?:\s*\n\s+project:",
            "azure.yaml service key must use $APP_NAME (dynamic) not a static string. "
            "Must match dynamic Bicep azd-service-name for per-run uniqueness.",
        )

    # --- Issue #10: Session ID must be required, not optional ---

    def test_session_id_empty_is_fail(self) -> None:
        """Fixture must FAIL if Mcp-Session-Id is empty after initialize."""
        # Must contain an explicit empty-session-ID check that writes FAIL
        session_section = self.fixture[self.fixture.index("SESSION_ID="):]
        session_section = session_section[:session_section.index("```", 100)]
        self.assertRegex(
            session_section,
            r'-z.*SESSION_ID|SESSION_ID.*empty|FAIL.*session',
            "Fixture does not FAIL on empty session ID — FastMCP always assigns one, "
            "so empty means the protocol handshake is broken.",
        )

    # --- Issue #11: MCP 2025-06-18 protocol conformance ---

    def test_initialized_requires_http_202(self) -> None:
        """notifications/initialized must require HTTP 202, not any 2xx."""
        init_section = self.fixture[self.fixture.index("notifications/initialized"):]
        init_section = init_section[:init_section.index("```", 200)]
        # Must check for exactly 202, not a range
        self.assertIn(
            "202",
            init_section,
            "notifications/initialized must require HTTP 202 per MCP spec — "
            "notifications return 202 Accepted, not 200 OK.",
        )

    def test_protocol_version_captured_from_initialize(self) -> None:
        """Initialize response must capture result.protocolVersion."""
        # Must extract protocolVersion into a variable (between initialize and Step 5b)
        init_section = self.fixture[self.fixture.index("## Step 5"):]
        init_section = init_section[:init_section.index("## Step 5b")]
        self.assertIn(
            "protocolVersion",
            init_section,
            "protocolVersion not captured from initialize response.",
        )
        # Must extract it into a variable for subsequent headers
        self.assertRegex(
            self.fixture,
            r"PROTOCOL_VERSION.*protocolVersion|protocolVersion.*PROTOCOL_VERSION",
            "protocolVersion not extracted into PROTOCOL_VERSION variable.",
        )

    def test_protocol_version_header_on_subsequent_requests(self) -> None:
        """MCP-Protocol-Version header required on tools/list and tools/call."""
        after_init = self.fixture[self.fixture.index("tools/list"):]
        self.assertIn(
            "MCP-Protocol-Version",
            after_init,
            "MCP-Protocol-Version header missing from subsequent requests — "
            "required by MCP 2025-06-18 spec for HTTP transport.",
        )

    # --- Issue #12: Stale probe prose ---

    def test_no_stale_probe_prose(self) -> None:
        """No references to probe configuration that was removed."""
        # Step 2 area should not claim probes are configured
        step2_match = re.search(r"## Step 2.*?## Step", self.fixture, re.DOTALL)
        if step2_match:
            step2 = step2_match.group(0)
            self.assertNotIn(
                "startup probes against",
                step2,
                "Step 2 still references startup probes — probes were removed.",
            )

    # --- Issue #13: Failure list synchronized ---

    def test_failure_list_includes_session_id(self) -> None:
        """Failure summary must include missing session ID."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        self.assertRegex(
            fail_section,
            r"[Ss]ession|Mcp-Session-Id",
            "Failure list does not mention missing session ID.",
        )

    def test_failure_list_includes_tools_call(self) -> None:
        """Failure summary must include tools/call failures."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        self.assertIn(
            "tools/call",
            fail_section,
            "Failure list does not mention tools/call failures.",
        )

    def test_failure_list_includes_initialized_status(self) -> None:
        """Failure summary must include initialized notification status."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        self.assertRegex(
            fail_section,
            r"initialized.*202|notifications/initialized",
            "Failure list does not mention initialized notification status.",
        )

    # --- Issue #14: No search_orders_filtered fallback ---

    def test_no_search_orders_filtered_fallback(self) -> None:
        """Fixture must not reference search_orders_filtered (server only has echo)."""
        self.assertNotIn(
            "search_orders_filtered",
            self.fixture,
            "Fixture references search_orders_filtered but the deployed server "
            "only exposes 'echo'. Remove unreachable fallback.",
        )

    # --- Issue #15: Pin regex must not match fastmcp suffix ---

    def test_pin_mcp_regex_excludes_fastmcp(self) -> None:
        """Pin regex for mcp must not match the 'mcp' suffix of 'fastmcp~='."""
        # Find lines with 'mcp' pin specifiers — must be word-boundary safe
        # Extract the pip install line for standalone mcp
        pin_lines = [
            l for l in self.pin.splitlines()
            if "mcp" in l and ("~=" in l or ">=" in l or "==" in l)
        ]
        # There must be a line that starts with 'mcp' (not 'fastmcp')
        standalone_mcp = [l for l in pin_lines if re.search(r'(?<![a-z])mcp[~>=<]', l)]
        self.assertTrue(
            standalone_mcp,
            "Pin script has no standalone 'mcp' specifier — the regex "
            "'mcp[~>=<]' would match the suffix of 'fastmcp~='. "
            "Must have an explicit 'mcp~=X.Y.Z' or '\"mcp~=X.Y.Z\"' line.",
        )

    # --- Issue #16: SKILL protocol claims correctness ---

    def test_skill_notifications_return_202_not_200(self) -> None:
        """SKILL.md must state notifications/initialized returns HTTP 202, not 200."""
        protocol_section = self.skill[self.skill.index("## MCP Protocol Requirements"):]
        protocol_section = protocol_section[:protocol_section.index("## ", 5)]
        # Must NOT claim ALL methods return HTTP 200 — notifications return 202
        self.assertNotIn(
            "ALL 6 JSON-RPC methods must return HTTP 200",
            protocol_section,
            "SKILL.md falsely claims ALL 6 methods return HTTP 200 — "
            "notifications/initialized returns HTTP 202 per MCP 2025-06-18 spec.",
        )

    def test_skill_initialized_not_can_return_empty(self) -> None:
        """SKILL.md must not say notifications/initialized 'Can return {}'."""
        # Find the protocol table
        protocol_section = self.skill[self.skill.index("## MCP Protocol Requirements"):]
        protocol_section = protocol_section[:protocol_section.index("## ", 5)]
        # initialized is a notification — 202 with no body, not 200 with {}
        self.assertNotIn(
            "Can return `{}`",
            protocol_section,
            "SKILL.md says initialized 'Can return {}' — per MCP 2025-06-18, "
            "accepted notifications return HTTP 202 with no body.",
        )

    def test_skill_gotchas_notifications_not_200(self) -> None:
        """Gotchas table must not claim all methods return HTTP 200."""
        gotchas_section = self.skill[self.skill.index("## Gotchas"):]
        # The gotchas fix column says "All 6 ... must return HTTP 200"
        self.assertNotIn(
            "All 6 JSON-RPC methods must return HTTP 200",
            gotchas_section,
            "Gotchas table repeats the wrong claim — notifications return 202.",
        )

    # --- Issue #17: Initialized body assertion ---

    def test_initialized_asserts_empty_body_or_no_body(self) -> None:
        """notifications/initialized must verify body is empty (202 = no body)."""
        # Find the bash block that actually sends notifications/initialized
        init_curl_idx = self.fixture.index('"method": "notifications/initialized"')
        block_start = self.fixture.rfind("```bash", 0, init_curl_idx)
        block_end = self.fixture.index("```", init_curl_idx)
        block_content = self.fixture[block_start:block_end]
        has_body_check = (
            "body" in block_content.lower()
            or "INIT_NOTIFY_BODY" in block_content
            or "empty" in block_content.lower()
        )
        self.assertTrue(
            has_body_check,
            "notifications/initialized must verify response body is empty "
            "(HTTP 202 = accepted notification, no body per MCP spec).",
        )

    # --- Issue #18: Failure contract completeness ---

    def test_failure_list_includes_protocol_version(self) -> None:
        """Failure summary must mention protocol version negotiation failure."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        has_protocol = (
            "protocolVersion" in fail_section
            or "protocol version" in fail_section.lower()
            or "MCP-Protocol-Version" in fail_section
        )
        self.assertTrue(
            has_protocol,
            "Failure list does not mention protocol version negotiation — "
            "missing negotiated version or MCP-Protocol-Version replay is a FAIL.",
        )

    # --- Issue #19: Scoped echo assertion ---

    def test_echo_assertion_in_tools_call_block(self) -> None:
        """'echoed:' assertion must be in the same bash block as tools/call."""
        call_idx = self.fixture.rindex('"method": "tools/call"')
        block_start = self.fixture.rfind("```bash", 0, call_idx)
        block_end = self.fixture.index("```", call_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "echoed:",
            block_content,
            "'echoed:' assertion must appear in the bash block containing tools/call.",
        )

    def test_isError_assertion_in_tools_call_block(self) -> None:
        """isError check must be in the same bash block as tools/call."""
        call_idx = self.fixture.rindex('"method": "tools/call"')
        block_start = self.fixture.rfind("```bash", 0, call_idx)
        block_end = self.fixture.index("```", call_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "isError",
            block_content,
            "isError check must appear in the bash block containing tools/call.",
        )

    # --- Issue #20: Spec date must not silently skip ---

    def test_spec_file_exists(self) -> None:
        """Design spec file must exist — test should not silently skip."""
        spec_path = ROOT / "docs" / "superpowers" / "specs" / "foundry-mcp-aca-refresh-1.2.4.md"
        self.assertTrue(
            spec_path.exists(),
            f"Design spec file does not exist: {spec_path}",
        )

    # --- Issue #21: SESSION_ARGS replayed on all three requests ---

    def test_session_args_on_initialized(self) -> None:
        """SESSION_ARGS must be used on notifications/initialized curl request."""
        # Find the actual curl command for initialized (the bash block containing it)
        init_curl_idx = self.fixture.index('notifications/initialized", "params"')
        block_start = self.fixture.rfind("```bash", 0, init_curl_idx)
        block_end = self.fixture.index("```", init_curl_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "SESSION_ARGS[@]",
            block_content,
            "SESSION_ARGS must be replayed on notifications/initialized curl.",
        )

    def test_session_args_on_tools_list(self) -> None:
        """SESSION_ARGS must be used on tools/list curl request."""
        list_curl_idx = self.fixture.index('"method": "tools/list"')
        block_start = self.fixture.rfind("```bash", 0, list_curl_idx)
        block_end = self.fixture.index("```", list_curl_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "SESSION_ARGS[@]",
            block_content,
            "SESSION_ARGS must be replayed on tools/list curl.",
        )

    def test_session_args_on_tools_call(self) -> None:
        """SESSION_ARGS must be used on tools/call curl request."""
        call_curl_idx = self.fixture.index('"method": "tools/call"')
        block_start = self.fixture.rfind("```bash", 0, call_curl_idx)
        block_end = self.fixture.index("```", call_curl_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "SESSION_ARGS[@]",
            block_content,
            "SESSION_ARGS must be replayed on tools/call curl.",
        )

    # --- Skill acknowledgment (preserved from original) ---

    def test_fixture_acknowledges_skill_inside_step_zero_bootstrap(self) -> None:
        acknowledgement = 'echo "skills/foundry-mcp-aca/SKILL.md"'
        bootstrap = _bootstrap_block(self.fixture)
        self.assertNotIn("## Step -1", self.fixture)
        self.assertIn("## Step 0", self.fixture)
        self.assertIn(acknowledgement, bootstrap)


class TestStatePersistence(unittest.TestCase):
    """Bash tool calls run in fresh processes; env vars don't persist."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = FIXTURE.read_text(encoding="utf-8")

    def test_bootstrap_is_the_only_auth_and_initial_state_path(self):
        """Audit, auth, and initial state must share the first Bash action."""
        bootstrap = _bootstrap_block(self.fixture)
        first_bash = re.search(
            r"(?m)^```bash\n(?P<body>.*?)^```(?:\n|$)",
            self.fixture,
            re.DOTALL,
        )
        self.assertIsNotNone(first_bash)
        self.assertEqual(bootstrap, first_bash.group("body"))
        self.assertIn('echo "skills/foundry-mcp-aca/SKILL.md"', bootstrap)
        self.assertIn("set -Eeuo pipefail", bootstrap)
        self.assertIn("FAIL()", bootstrap)
        self.assertEqual(
            [
                "set -Eeuo pipefail",
                'echo "skills/foundry-mcp-aca/SKILL.md"',
            ],
            bootstrap.splitlines()[:2],
            "the audit path must be visible before Copilot collapses the "
            "first Bash action in its transcript",
        )
        bash_bodies = [body for _start, body in _shell_fences(self.fixture)]
        auth_commands = [
            command
            for body in bash_bodies
            for command in _azd_auth_login_command_lines(body)
        ]
        self.assertEqual(
            1,
            len(auth_commands),
            "the fixture must expose exactly one authenticated azd bootstrap path",
        )
        self.assertEqual(
            auth_commands,
            _azd_auth_login_command_lines(bootstrap),
            "the sole azd auth login command must be inside the bootstrap block",
        )
        self.assertEqual(
            1,
            self.fixture.count(STATE_MARKER),
            "the initial state path must be declared only in the bootstrap block",
        )
        self.assertIn(STATE_MARKER, bootstrap)
        self.assertNotIn("## Step -1", self.fixture)
        before_scaffold = self.fixture[:self.fixture.index(STEP_2_HEADING)]
        self.assertEqual(
            1,
            len(_shell_fences(before_scaffold)),
            "bootstrap must be the only shell command fragment before scaffolding",
        )
        for case, command in {
            "direct": "azd auth login --client-id test",
            "if": "if azd auth login --client-id test; then",
            "compound": "echo ready; azd auth login --client-id test",
            "subshell": "(azd auth login --client-id test)",
            "command substitution": "result=$(azd auth login --client-id test)",
            "line continuation": "azd auth \\\n  login --client-id test",
            "path-qualified": "/usr/local/bin/azd auth login --client-id test",
        }.items():
            with self.subTest(azd_auth_form=case):
                self.assertEqual(
                    1,
                    len(_azd_auth_login_command_lines(command)),
                    f"{case} must be classified as an executable azd auth path",
                )
        self.assertEqual(
            2,
            len(
                _azd_auth_login_command_lines(
                    "azd auth login --client-id one; "
                    "azd auth login --client-id two"
                )
            ),
            "two auth invocations on one compound line must count as two paths",
        )

    def test_bootstrap_executes_auth_before_atomically_publishing_state(self):
        """Execute the exact bootstrap with stubbed Azure CLIs and verify order."""
        bootstrap = _bootstrap_block(self.fixture)

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
            _isolated_shipped_smoke_marker(),
        ):
            temp = pathlib.Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            call_log = temp / "calls.log"

            (bin_dir / "az").write_text(
                "#!/usr/bin/env bash\n"
                'printf "az %s\\n" "$*" >> "$CALL_LOG"\n'
                "printf '__EVENT__:az account show\\n'\n"
                "exit 0\n",
                encoding="utf-8",
            )
            (bin_dir / "azd").write_text(
                "#!/usr/bin/env bash\n"
                'printf "azd %s\\n" "$*" >> "$CALL_LOG"\n'
                "printf '__EVENT__:azd auth login\\n'\n"
                '[ ! -e "$BOOTSTRAP_STATE_PATH" ] || exit 91\n'
                '[ "${AZD_AUTH_RESULT:-success}" = success ] || exit 42\n'
                "exit 0\n",
                encoding="utf-8",
            )
            (bin_dir / "uuidgen").write_text(
                "#!/usr/bin/env bash\n"
                "printf 'ABCDEF12-3456-7890-ABCD-EF1234567890\\n'\n",
                encoding="utf-8",
            )
            for stub in ("az", "azd", "uuidgen"):
                (bin_dir / stub).chmod(0o755)

            base_env = {
                "PATH": f"{bin_dir}:/usr/bin:/bin:/usr/local/bin",
                "CALL_LOG": str(call_log),
                "BOOTSTRAP_STATE_PATH": str(STATE_PATH),
                "GITHUB_WORKSPACE": str(temp),
                "AZURE_CLIENT_ID": "test-client",
                "AZURE_TENANT_ID": "test-tenant",
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }

            failed_auth = _run_bash(
                bootstrap,
                {**base_env, "AZD_AUTH_RESULT": "fail"},
                cwd=temp,
            )
            self.assertNotEqual(0, failed_auth.returncode)
            self.assertFalse(
                STATE_PATH.exists(),
                "failed azd auth must leave no published state from this invocation",
            )
            self.assertTrue(
                SMOKE_MARKER_PATH.read_bytes().startswith(
                    b"SMOKE_RESULT=FAIL azd auth login failed"
                ),
                f"failed auth must write a precise FAIL marker: "
                f"stdout={failed_auth.stdout!r} stderr={failed_auth.stderr!r}",
            )
            self.assertIn("skills/foundry-mcp-aca/SKILL.md", failed_auth.stdout)
            self.assertEqual(
                [
                    "az account show --output table",
                    (
                        "azd auth login --federated-credential-provider github "
                        "--client-id test-client --tenant-id test-tenant"
                    ),
                ],
                call_log.read_text(encoding="utf-8").splitlines(),
            )

            call_log.unlink()
            SMOKE_MARKER_PATH.unlink()
            succeeded = _run_bash(bootstrap, base_env, cwd=temp)
            self.assertEqual(
                0,
                succeeded.returncode,
                f"bootstrap failed: stdout={succeeded.stdout!r} "
                f"stderr={succeeded.stderr!r}",
            )
            self.assertIn("skills/foundry-mcp-aca/SKILL.md", succeeded.stdout)
            self.assertEqual(
                [
                    "az account show --output table",
                    (
                        "azd auth login --federated-credential-provider github "
                        "--client-id test-client --tenant-id test-tenant"
                    ),
                ],
                call_log.read_text(encoding="utf-8").splitlines(),
            )
            self.assertLess(
                succeeded.stdout.index("skills/foundry-mcp-aca/SKILL.md"),
                succeeded.stdout.index("__EVENT__:az account show"),
            )
            self.assertLess(
                succeeded.stdout.index("__EVENT__:az account show"),
                succeeded.stdout.index("__EVENT__:azd auth login"),
            )
            self.assertLess(
                succeeded.stdout.index("__EVENT__:azd auth login"),
                succeeded.stdout.index("APP_NAME=ci-smoke-mcp-abcdef12"),
            )
            expected_uami = (
                "/subscriptions/test-subscription/resourceGroups/rg-awesome-gbb-ci/"
                "providers/Microsoft.ManagedIdentity/userAssignedIdentities/"
                "uami-awesome-gbb-ci"
            )
            self.assertEqual(
                [
                    "APP_NAME=ci-smoke-mcp-abcdef12",
                    f"PROJECT_DIR={temp}/.scratch/ci-smoke-mcp-abcdef12",
                    f"UAMI_RESOURCE_ID={expected_uami}",
                    "ACR_SERVER=test.azurecr.io",
                ],
                STATE_PATH.read_text(encoding="utf-8").splitlines(),
            )

    def test_bootstrap_rejects_each_missing_required_env_before_auth(self):
        """Required workflow inputs must fail before azd auth or state publication."""
        bootstrap = _bootstrap_block(self.fixture)
        required = (
            "GITHUB_WORKSPACE",
            "AZURE_CLIENT_ID",
            "AZURE_TENANT_ID",
            "AZURE_SUBSCRIPTION_ID",
            "ACR_LOGIN_SERVER",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = pathlib.Path(temp_dir)
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            call_log = temp / "calls.log"
            for name in ("az", "azd"):
                stub = bin_dir / name
                stub.write_text(
                    "#!/usr/bin/env bash\n"
                    f"printf '{name} called\\n' >> \"$CALL_LOG\"\n",
                    encoding="utf-8",
                )
                stub.chmod(0o755)
            uuidgen = bin_dir / "uuidgen"
            uuidgen.write_text(
                "#!/usr/bin/env bash\nprintf 'abcdef12\\n'\n",
                encoding="utf-8",
            )
            uuidgen.chmod(0o755)
            complete_env = {
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "CALL_LOG": str(call_log),
                "GITHUB_WORKSPACE": str(temp),
                "AZURE_CLIENT_ID": "test-client",
                "AZURE_TENANT_ID": "test-tenant",
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }

            for missing in required:
                with (
                    self.subTest(missing=missing),
                    _isolated_shipped_state_file(),
                    _isolated_shipped_smoke_marker(),
                ):
                    call_log.unlink(missing_ok=True)
                    result = _run_bash(
                        bootstrap,
                        {
                            key: value
                            for key, value in complete_env.items()
                            if key != missing
                        },
                        cwd=temp,
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse(STATE_PATH.exists())
                    self.assertFalse(
                        call_log.exists(),
                        f"missing {missing} must fail before az or azd is called",
                    )
                    self.assertEqual(
                        f"SMOKE_RESULT=FAIL auth context missing: {missing}\n",
                        SMOKE_MARKER_PATH.read_text(encoding="utf-8"),
                    )

    def test_global_guard_forbids_all_non_bash_file_tools_and_plan_files(self):
        """The first-page guard applies globally, including session plan files."""
        first_page = self.fixture[:3000]
        required_guard = (
            "NEVER use Edit, Create, Write, or any other file-editing tool "
            "anywhere in this smoke, for any purpose.",
            "This includes `~/.copilot/session-state/*/plan.md`.",
            "Do not create a plan file.",
            "Every action in this smoke must be one of the prescribed Bash tool actions.",
        )
        for sentence in required_guard:
            with self.subTest(sentence=sentence):
                self.assertIn(sentence, first_page)

    def test_provision_is_one_state_dependent_prescribed_block(self):
        """The fixture must expose one provision path after bootstrap state."""
        provision = _provision_block(self.fixture)
        bash_bodies = [body for _start, body in _shell_fences(self.fixture)]
        executable_azd_up = [
            command
            for body in bash_bodies
            for command in _azd_up_command_lines(body)
        ]
        self.assertEqual(
            ["until azd up --no-prompt; do"],
            executable_azd_up,
            "there must be exactly one executable azd up path globally",
        )
        self.assertEqual(
            executable_azd_up,
            _azd_up_command_lines(provision),
            "the sole executable azd up must be inside the prescribed provision block",
        )
        self.assertTrue(
            provision.startswith(
                "source /tmp/foundry-mcp-aca-state.env || "
                "{ printf 'SMOKE_RESULT=FAIL provision state missing\\n'"
            ),
            "the sole provision path must begin by requiring bootstrap state",
        )
        self.assertLess(
            self.fixture.index(BOOTSTRAP_BLOCK_HEADING),
            self.fixture.index(PROVISION_BLOCK_HEADING),
        )
        invocation_cases = {
            "direct": "azd up --no-prompt",
            "until": "until azd up --no-prompt; do",
            "if": "if azd up --no-prompt; then",
            "timeout": "timeout 60 azd up --no-prompt",
            "compound": "echo ready; azd up --no-prompt",
            "subshell": "(azd up --no-prompt)",
            "command substitution": "result=$(azd up --no-prompt)",
            "line continuation": "azd \\\n  up --no-prompt",
            "path-qualified": "/usr/local/bin/azd up --no-prompt",
        }
        for case, command in invocation_cases.items():
            with self.subTest(azd_up_form=case):
                self.assertEqual(
                    1,
                    len(_azd_up_command_lines(command)),
                    f"{case} must be classified as an executable azd up path",
                )
        self.assertEqual(
            2,
            len(
                _azd_up_command_lines(
                    "azd up --no-prompt || azd up --no-prompt"
                )
            ),
            "two provision invocations on one compound line must count as two paths",
        )
        self.assertEqual(
            [],
            _azd_up_command_lines(
                "echo 'azd up failed'\n"
                "cat > script.sh <<'SH'\n"
                "azd up --no-prompt\n"
                "SH\n"
            ),
            "quoted diagnostics and heredoc content are not executable azd paths",
        )
        self.assertEqual(
            ["azd up --no-prompt"],
            _azd_up_command_lines(
                'echo "<<NOT_A_HEREDOC"\n'
                "azd up --no-prompt\n"
            ),
            "a quoted heredoc-like token must not hide the next executable path",
        )
        self.assertEqual(
            ["azd up --no-prompt"],
            _azd_up_command_lines(
                'echo "<<" STOP\n'
                "azd up --no-prompt\n"
                "STOP\n"
            ),
            "a separately quoted heredoc operator must not hide executable paths",
        )
        self.assertEqual(
            ["azd up --no-prompt"],
            _azd_up_command_lines(
                "echo $((1 << STOP))\n"
                "azd up --no-prompt\n"
            ),
            "an arithmetic shift must not be mistaken for a heredoc opener",
        )
        alternate_fence = "~~~sh\nazd up --no-prompt\n~~~\n"
        self.assertEqual(
            ["azd up --no-prompt"],
            [
                command
                for _start, body in _shell_fences(alternate_fence)
                for command in _azd_up_command_lines(body)
            ],
            "alternate shell fences must participate in global path discovery",
        )
        self.assertEqual(
            ["azd up --no-prompt"],
            [
                command
                for _start, body in _shell_fences(
                    "```Bash\nazd up --no-prompt\n```\n"
                )
                for command in _azd_up_command_lines(body)
            ],
            "case-variant shell fences must participate in path discovery",
        )

    def test_state_file_written_after_naming(self):
        """Bootstrap must atomically persist every cross-shell deployment value."""
        bootstrap = _bootstrap_block(self.fixture)
        self.assertIn('STATE_FILE="/tmp/foundry-mcp-aca-state.env"', bootstrap)
        for variable in ("APP_NAME", "PROJECT_DIR", "UAMI_RESOURCE_ID", "ACR_SERVER"):
            self.assertIn(
                f"printf '{variable}=%s\\n'",
                bootstrap,
                f"{variable} must be persisted to the fixture state file.",
            )
        self.assertIn('} > "$STATE_TMP"', bootstrap)
        self.assertIn('mv "$STATE_TMP" "$STATE_FILE"', bootstrap)

    def test_scaffolding_block_uses_restored_state_without_reassignment(self):
        """The fresh-shell scaffold must trust every persisted Step 1 value."""
        state_block = _step_1_state_block(self.fixture)
        scaffolding_block = _standard_bash_block_containing(
            self.fixture,
            'mkdir -p "$PROJECT_DIR/src" "$PROJECT_DIR/infra"'
        )
        source_index = scaffolding_block.index(
            "source /tmp/foundry-mcp-aca-state.env"
        )
        restored_body = scaffolding_block[source_index:]
        persisted_variables = (
            "APP_NAME",
            "PROJECT_DIR",
            "UAMI_RESOURCE_ID",
            "ACR_SERVER",
        )
        reassigned = re.findall(
            rf"^\s*(?:export\s+)?({'|'.join(persisted_variables)})=",
            restored_body,
            re.MULTILINE,
        )
        self.assertEqual(
            [],
            reassigned,
            "the scaffolding block must not reassign persisted variables after "
            f"sourcing Step 1 state; found {reassigned}",
        )

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
        ):
            workspace = pathlib.Path(temp_dir)
            stub_bin = _bootstrap_stub_bin(workspace)
            restored_project_dir = workspace / "restored-from-state"
            workflow_env = {
                "PATH": f"{stub_bin}:/usr/bin:/bin:/usr/local/bin",
                "GITHUB_WORKSPACE": str(workspace),
                "AZURE_CLIENT_ID": "test-client",
                "AZURE_TENANT_ID": "test-tenant",
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }
            create_state = _run_bash(state_block, workflow_env)
            self.assertEqual(
                0,
                create_state.returncode,
                f"shipped Step 1 state creation failed: {create_state.stderr!r}",
            )
            state_lines = STATE_PATH.read_text(encoding="utf-8").splitlines()
            STATE_PATH.write_text(
                "\n".join(
                    (
                        f"PROJECT_DIR={restored_project_dir}"
                        if line.startswith("PROJECT_DIR=")
                        else line
                    )
                    for line in state_lines
                )
                + "\n",
                encoding="utf-8",
            )

            scaffold = _run_bash(scaffolding_block, workflow_env)
            self.assertEqual(
                0,
                scaffold.returncode,
                "shipped scaffolding block failed after sourcing Step 1 state: "
                f"{scaffold.stderr!r}",
            )
            self.assertTrue(
                (restored_project_dir / "src").is_dir()
                and (restored_project_dir / "infra").is_dir(),
                "the scaffolding block must create directories under the "
                "PROJECT_DIR restored from persisted state",
            )

    def test_azure_yaml_block_sources_state(self):
        """The azure.yaml heredoc block must source state first."""
        # Find the azure.yaml heredoc
        azdyaml_idx = self.fixture.index("<<AZDYAML")
        # Find the bash block start before it
        block_start = self.fixture.rfind("```bash", 0, azdyaml_idx)
        block_content = self.fixture[block_start:azdyaml_idx]
        self.assertIn(
            "source /tmp/foundry-mcp-aca-state.env", block_content,
            "azure.yaml heredoc bash block must source state file"
        )

    def test_azd_up_block_sources_state(self):
        """The azd up retry block must source state first."""
        azdup_idx = self.fixture.index("until azd up --no-prompt")
        block_start = self.fixture.rfind("```bash", 0, azdup_idx)
        block_content = self.fixture[block_start:azdup_idx]
        self.assertIn(
            "source /tmp/foundry-mcp-aca-state.env", block_content,
            "azd up block must source state file"
        )

    def test_mcp_probe_block_sources_state(self):
        """The MCP probe block must source state for APP_NAME fallback."""
        fqdn_idx = self.fixture.index("FQDN=$(azd env get-values")
        block_start = self.fixture.rfind("```bash", 0, fqdn_idx)
        block_content = self.fixture[block_start:fqdn_idx]
        self.assertIn(
            "source /tmp/foundry-mcp-aca-state.env", block_content,
            "MCP probe block must source state file"
        )

    def test_every_fresh_mcp_and_auth_block_sources_persisted_state_first(self):
        """Fresh Bash calls that consume deployment state must restore it first."""
        for marker in (
            "INIT_RESPONSE=$(curl",
            "SUB=$(az account show",
            "CODE=$(curl",
            "TOKEN=$(az account get-access-token",
        ):
            with self.subTest(marker=marker):
                block = _standard_bash_block_containing(self.fixture, marker)
                self.assertTrue(
                    block.lstrip().startswith(
                        "source /tmp/foundry-mcp-aca-state.env\n"
                    ),
                    f"fresh block containing {marker!r} must source state first",
                )

    def test_azure_tenant_id_in_azd_env(self):
        """azd env .env must include AZURE_TENANT_ID for federated-credential CI."""
        self.assertIn(
            'AZURE_TENANT_ID=${AZURE_TENANT_ID}',
            self.fixture,
            "AZURE_TENANT_ID must be written to the azd .env file"
        )

    def test_no_azd_env_new_or_set(self):
        """Fixture bash blocks must NOT use 'azd env new' or 'azd env set'."""
        import re
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        self.assertNotIn(
            'azd env new',
            combined,
            "azd env new requires interactive prompts; use direct file creation"
        )
        self.assertNotIn(
            'azd env set ',
            combined,
            "azd env set requires interactive prompts; write .env directly"
        )

    def test_state_persistence_documentation(self):
        """Fixture must document the state-persistence requirement."""
        self.assertIn(
            "State persistence between Bash tool calls", self.fixture,
            "Fixture must have a section explaining state persistence"
        )

    # --- Round 7: Heredoc, state, protocol, anchoring ---

    def test_parameters_json_escapes_schema_in_expanding_heredoc(self):
        """The heredoc must preserve $schema while expanding deployment values."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        self.assertRegex(
            combined,
            r"cat\s*>\s*.*parameters\.json.*<<\s*PARAMS",
            "main.parameters.json must use an expanding heredoc so deployment "
            "values are rendered instead of preserved as literal placeholders.",
        )
        self.assertIn(
            r'"\$schema"',
            combined,
            "main.parameters.json must escape only the $schema key.",
        )

    def test_parameters_json_heredoc_preserves_schema_and_expands_values(self):
        """Replay exact state and scaffold blocks in separate fresh shells."""
        state_block = _step_1_state_block(self.fixture)
        scaffold_block = _scaffold_block(self.fixture)

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
        ):
            workspace = pathlib.Path(temp_dir)
            stub_bin = _bootstrap_stub_bin(workspace)
            workflow_env = {
                "PATH": f"{stub_bin}:/usr/bin:/bin:/usr/local/bin",
                "GITHUB_WORKSPACE": str(workspace),
                "AZURE_CLIENT_ID": "test-client",
                "AZURE_TENANT_ID": "test-tenant",
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }
            create_state = _run_bash(state_block, workflow_env)
            self.assertEqual(
                create_state.returncode,
                0,
                f"shipped Step 1 state creation failed: stderr={create_state.stderr!r}",
            )
            state_values = dict(
                line.split("=", 1)
                for line in STATE_PATH.read_text().splitlines()
                if "=" in line
            )
            project_dir = pathlib.Path(state_values["PROJECT_DIR"])

            render_parameters = _run_bash(scaffold_block, workflow_env)
            self.assertEqual(
                render_parameters.returncode,
                0,
                "shipped combined scaffold block failed after sourcing Step 1 state: "
                f"stderr={render_parameters.stderr!r}",
            )
            rendered = json.loads(
                (project_dir / "infra" / "main.parameters.json").read_text()
            )

        expected_uami = (
            "/subscriptions/test-subscription/resourceGroups/rg-awesome-gbb-ci/"
            "providers/Microsoft.ManagedIdentity/userAssignedIdentities/"
            "uami-awesome-gbb-ci"
        )
        self.assertRegex(
            state_values["APP_NAME"],
            r"^ci-smoke-mcp-[0-9a-f]{8}$",
            "the exact Step 1 state block must generate and persist APP_NAME",
        )
        self.assertIn("$schema", rendered)
        self.assertEqual(
            rendered["parameters"]["appName"]["value"], state_values["APP_NAME"]
        )
        self.assertEqual(state_values.get("UAMI_RESOURCE_ID"), expected_uami)
        self.assertEqual(state_values.get("ACR_SERVER"), "test.azurecr.io")
        self.assertEqual(
            rendered["parameters"]["uamiResourceId"]["value"], expected_uami
        )
        self.assertEqual(
            rendered["parameters"]["acrServer"]["value"], "test.azurecr.io"
        )

    def test_combined_scaffold_block_executes_complete_contract(self):
        """The exact shipped blocks must build all six files across fresh shells."""
        synthetic_scaffold = f"""{SCAFFOLD_SOURCE_FALLBACK}
{SCAFFOLD_SET_FLAGS}
{SCAFFOLD_ERR_TRAP}
{SCAFFOLD_STATE_GATE}
mkdir -p "$PROJECT_DIR/src" "$PROJECT_DIR/infra"
cd "$PROJECT_DIR"
cat > src/server.py <<'PY'
az account show
read OTHER APP_NAME
(( APP_NAME++ ))
PY
cat > src/requirements.txt <<'REQ'
fastmcp~=2.14.7
REQ
cat > src/Dockerfile <<'DOCKER'
FROM python:3.12-slim
DOCKER
cat > infra/main.bicep <<'BICEP'
param appName string
BICEP
cat > infra/main.parameters.json <<PARAMS
""" + EXPECTED_PARAMETERS_HEREDOC + """
PARAMS
cat > azure.yaml <<AZDYAML
""" + EXPECTED_AZURE_YAML_HEREDOC + """
AZDYAML
"""
        with self.subTest(scaffold_oracle="heredoc bodies are not commands"):
            commands, heredocs, _events = _parse_scaffold_shell(
                synthetic_scaffold
            )
            self.assertNotIn("az account show", commands)
            self.assertIn("az account show", heredocs[0][3])
            events = _scaffold_shell_contract(synthetic_scaffold)
            self.assertEqual(18, len(events))

        rejected_scaffolds = {
            "source fallback removed": synthetic_scaffold.replace(
                SCAFFOLD_SOURCE_FALLBACK,
                "source /tmp/foundry-mcp-aca-state.env",
                1,
            ),
            "set -e removed": synthetic_scaffold.replace(
                SCAFFOLD_SET_FLAGS,
                "set -Euo pipefail",
                1,
            ),
            "ERR trap removed": synthetic_scaffold.replace(
                f"{SCAFFOLD_ERR_TRAP}\n",
                "",
                1,
            ),
            **{
                f"state gate missing {variable} check": synthetic_scaffold.replace(
                    SCAFFOLD_STATE_GATE,
                    _scaffold_state_gate(
                        tuple(
                            candidate
                            for candidate in SCAFFOLD_STATE_VARIABLES
                            if candidate != variable
                        )
                    ),
                    1,
                )
                for variable in SCAFFOLD_STATE_VARIABLES
            },
            "external az call": synthetic_scaffold.replace(
                'cd "$PROJECT_DIR"\n',
                'cd "$PROJECT_DIR"\naz account show\n',
                1,
            ),
            "read assignment": synthetic_scaffold.replace(
                'cd "$PROJECT_DIR"\n',
                'cd "$PROJECT_DIR"\nread OTHER APP_NAME\n',
                1,
            ),
            "arithmetic mutation": synthetic_scaffold.replace(
                'cd "$PROJECT_DIR"\n',
                'cd "$PROJECT_DIR"\n(( APP_NAME++ ))\n',
                1,
            ),
            "unquoted static delimiter": synthetic_scaffold.replace(
                "<<'PY'", "<<PY", 1
            ),
            "renamed static delimiter": synthetic_scaffold.replace(
                "<<'DOCKER'", "<<'CONTAINER'", 1
            ).replace("\nDOCKER\n", "\nCONTAINER\n", 1),
            "renamed parameters delimiter": synthetic_scaffold.replace(
                "<<PARAMS", "<<JSONPARAMS", 1
            ).replace("\nPARAMS\n", "\nJSONPARAMS\n", 1),
            "renamed azure.yaml delimiter": synthetic_scaffold.replace(
                "<<AZDYAML", "<<SERVICEYAML", 1
            ).replace("\nAZDYAML\n", "\nSERVICEYAML\n", 1),
            "unescaped schema": synthetic_scaffold.replace(
                '"\\$schema"', '"$schema"', 1
            ),
            "extra parameters expansion": synthetic_scaffold.replace(
                '"contentVersion": "1.0.0.0"',
                '"contentVersion": "${AZURE_SUBSCRIPTION_ID}"',
                1,
            ),
            "extra azure.yaml expansion": synthetic_scaffold.replace(
                "metadata:",
                "subscription: ${AZURE_SUBSCRIPTION_ID}\nmetadata:",
                1,
            ),
        }
        for case, shell in rejected_scaffolds.items():
            with self.subTest(scaffold_oracle=case):
                with self.assertRaises(AssertionError):
                    _scaffold_shell_contract(shell)

        synthetic_document = f"```bash\n{synthetic_scaffold}```\n"
        with self.subTest(scaffold_oracle="single writer block"):
            _assert_single_scaffold_writer_block(
                synthetic_document, synthetic_scaffold
            )
        with self.subTest(scaffold_oracle="duplicate writer block"):
            with self.assertRaises(AssertionError):
                _assert_single_scaffold_writer_block(
                    synthetic_document + synthetic_document,
                    synthetic_scaffold,
                )
        duplicate_writer_documents = {
            "tilde-fenced duplicate": (
                synthetic_document
                + "~~~bash\ncat > azure.yaml <<DUPLICATE\nbad\nDUPLICATE\n~~~\n"
            ),
            "indented nonstandard duplicate": (
                synthetic_document
                + "    ```sh\n"
                + "    printf 'bad\\n' > infra/main.parameters.json\n"
                + "    ```\n"
            ),
        }
        for case, document in duplicate_writer_documents.items():
            with self.subTest(scaffold_oracle=case):
                with self.assertRaises(AssertionError):
                    _assert_single_scaffold_writer_block(
                        document,
                        synthetic_scaffold,
                    )
        with self.subTest(scaffold_oracle="protocol artifact remains allowed"):
            _assert_single_scaffold_writer_block(
                synthetic_document
                + "~~~sh\nprintf 'probe\\n' > "
                "/tmp/foundry-mcp-aca-smoke-result\n~~~\n",
                synthetic_scaffold,
            )

        synthetic_bootstrap = (
            f"{BOOTSTRAP_BLOCK_HEADING}\n\n"
            f"```bash\n{STATE_MARKER}\n```\n\n"
            f"{STEP_1_HEADING}\n"
        )
        with self.subTest(state_marker_scope="unique in exact bootstrap"):
            self.assertEqual(
                f"{STATE_MARKER}\n",
                _bootstrap_block(synthetic_bootstrap),
            )
        invalid_state_documents = {
            "duplicate bootstrap heading": (
                synthetic_bootstrap
                + f"\n{BOOTSTRAP_BLOCK_HEADING}\n\n```bash\necho duplicate\n```\n"
            ),
            "prose between heading and fence": (
                f"{BOOTSTRAP_BLOCK_HEADING}\n\nDo this first.\n\n"
                f"```bash\n{STATE_MARKER}\n```\n"
            ),
            "earlier Bash action": (
                "```bash\necho too-early\n```\n\n"
                f"{BOOTSTRAP_BLOCK_HEADING}\n\n```bash\n{STATE_MARKER}\n```\n"
            ),
            "earlier tilde-fenced shell action": (
                "~~~bash\necho too-early\n~~~\n\n"
                f"{BOOTSTRAP_BLOCK_HEADING}\n\n```bash\n{STATE_MARKER}\n```\n"
            ),
            "earlier indented shell action": (
                "   ```sh\n   echo too-early\n   ```\n\n"
                f"{BOOTSTRAP_BLOCK_HEADING}\n\n```bash\n{STATE_MARKER}\n```\n"
            ),
            "earlier case-variant shell action": (
                "```Bash\necho too-early\n```\n\n"
                f"{BOOTSTRAP_BLOCK_HEADING}\n\n```bash\n{STATE_MARKER}\n```\n"
            ),
        }
        for case, document in invalid_state_documents.items():
            with self.subTest(state_marker_scope=case):
                with self.assertRaises(AssertionError):
                    _bootstrap_block(document)

        with self.subTest(scaffold_heading_scope="duplicate outside Step 2"):
            with self.assertRaises(AssertionError):
                _scaffold_block(
                    f"{self.fixture}\n{SCAFFOLD_BLOCK_HEADING}\n"
                )

        state_block = _step_1_state_block(self.fixture)
        scaffold_block = _scaffold_block(self.fixture)
        _scaffold_shell_contract(scaffold_block)
        _assert_single_scaffold_writer_block(self.fixture, scaffold_block)

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
        ):
            workspace = pathlib.Path(temp_dir)
            stub_bin = _bootstrap_stub_bin(workspace)
            workflow_env = {
                "PATH": f"{stub_bin}:/usr/bin:/bin:/usr/local/bin",
                "GITHUB_WORKSPACE": str(workspace),
                "AZURE_CLIENT_ID": "test-client",
                "AZURE_TENANT_ID": "test-tenant",
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }

            create_state = _run_bash(state_block, workflow_env)
            self.assertEqual(
                0,
                create_state.returncode,
                "exact shipped Step 1 state block failed in a fresh process: "
                f"stdout={create_state.stdout!r} stderr={create_state.stderr!r}",
            )
            state_values = dict(
                line.split("=", 1)
                for line in STATE_PATH.read_text(encoding="utf-8").splitlines()
                if "=" in line
            )

            scaffold = _run_bash(scaffold_block, workflow_env)
            self.assertEqual(
                0,
                scaffold.returncode,
                "exact shipped combined scaffold block failed in a fresh process: "
                f"stdout={scaffold.stdout!r} stderr={scaffold.stderr!r}",
            )

            project_dir = pathlib.Path(state_values["PROJECT_DIR"])
            for relative_path in SCAFFOLD_FILES:
                with self.subTest(file=relative_path):
                    self.assertTrue(
                        (project_dir / relative_path).is_file(),
                        f"combined scaffold block did not write {relative_path}",
                    )

            server = (project_dir / "src" / "server.py").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                EXPECTED_SERVER_PY,
                _normalize_text(server),
                "server.py must equal the complete prescribed health/echo/main body",
            )
            requirements = (
                project_dir / "src" / "requirements.txt"
            ).read_text(encoding="utf-8")
            self.assertEqual(
                EXPECTED_REQUIREMENTS_TXT,
                _normalize_text(requirements),
                "requirements.txt must contain exactly the prescribed FastMCP pin",
            )
            dockerfile = (project_dir / "src" / "Dockerfile").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                EXPECTED_DOCKERFILE,
                _normalize_text(dockerfile),
                "Dockerfile must equal the complete prescribed container body",
            )
            bicep = (project_dir / "infra" / "main.bicep").read_text(
                encoding="utf-8"
            )
            self.assertEqual(
                EXPECTED_MAIN_BICEP,
                _normalize_text(bicep),
                "main.bicep must equal the complete prescribed deployment body",
            )

            parameters = json.loads(
                (project_dir / "infra" / "main.parameters.json").read_text(
                    encoding="utf-8"
                )
            )
            expected_parameters = {
                "$schema": (
                    "https://schema.management.azure.com/schemas/"
                    "2019-04-01/deploymentParameters.json#"
                ),
                "contentVersion": "1.0.0.0",
                "parameters": {
                    "appName": {"value": state_values["APP_NAME"]},
                    "uamiResourceId": {
                        "value": state_values["UAMI_RESOURCE_ID"]
                    },
                    "acrServer": {"value": state_values["ACR_SERVER"]},
                },
            }
            self.assertEqual(
                expected_parameters,
                parameters,
                "main.parameters.json must be exactly the schema, content version, "
                "and three persisted deployment parameters",
            )

            app_name = state_values["APP_NAME"]
            azure_yaml = yaml.safe_load(
                (project_dir / "azure.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                {
                    "name": app_name,
                    "metadata": {"template": "ci-smoke-mcp@0.0.1"},
                    "services": {
                        app_name: {
                            "project": "./src",
                            "language": "python",
                            "host": "containerapp",
                            "docker": {
                                "path": "Dockerfile",
                                "context": ".",
                            },
                        }
                    },
                },
                azure_yaml,
                "azure.yaml must have exactly one APP_NAME-keyed containerapp service",
            )

    def test_scaffold_failure_is_fail_fast_and_writes_marker(self):
        """A bad restored PROJECT_DIR must fail before any scaffold file is written."""
        scaffold_block = _scaffold_block(self.fixture)
        repo_artifacts = {
            relative_path: (
                (ROOT / relative_path).is_file(),
                (
                    (ROOT / relative_path).read_bytes()
                    if (ROOT / relative_path).is_file()
                    else None
                ),
            )
            for relative_path in SCAFFOLD_FILES
        }

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
            _isolated_shipped_smoke_marker(),
        ):
            safe_cwd = pathlib.Path(temp_dir)
            invalid_project_dir = safe_cwd / "project-is-a-file"
            invalid_project_dir.write_text("not a directory\n", encoding="utf-8")
            probe_marker = safe_cwd / "smoke-result"
            STATE_PATH.write_text(
                "\n".join(
                    (
                        "APP_NAME=ci-smoke-mcp-invalid",
                        f"PROJECT_DIR={shlex.quote(str(invalid_project_dir))}",
                        "UAMI_RESOURCE_ID=/subscriptions/test/resourceGroups/test/"
                        "providers/Microsoft.ManagedIdentity/"
                        "userAssignedIdentities/test",
                        "ACR_SERVER=test.azurecr.io",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            probe_block = _scaffold_block_with_probe_marker(
                scaffold_block, probe_marker
            )
            probe = _run_bash(
                probe_block,
                {"PATH": "/usr/bin:/bin"},
                cwd=safe_cwd,
            )
            marker_bytes = probe_marker.read_bytes() if probe_marker.is_file() else b""
            later_files = [
                relative_path
                for relative_path in SCAFFOLD_FILES
                if (safe_cwd / relative_path).exists()
            ]

            violations = []
            if probe.returncode == 0:
                violations.append(
                    "invalid PROJECT_DIR returned zero because a later relative "
                    "scaffold write masked the earlier failure"
                )
            if not marker_bytes.startswith(b"SMOKE_RESULT=FAIL"):
                violations.append(
                    "failure marker is missing or does not begin SMOKE_RESULT=FAIL"
                )
            if later_files:
                violations.append(
                    f"scaffold continued to create later files: {later_files!r}"
                )

            self.assertEqual(
                [],
                violations,
                "exact shipped combined scaffold block is not fail-fast: "
                + "; ".join(violations)
                + f"; stdout={probe.stdout!r} stderr={probe.stderr!r}",
            )

        restored_repo_artifacts = {
            relative_path: (
                (ROOT / relative_path).is_file(),
                (
                    (ROOT / relative_path).read_bytes()
                    if (ROOT / relative_path).is_file()
                    else None
                ),
            )
            for relative_path in SCAFFOLD_FILES
        }
        self.assertEqual(
            repo_artifacts,
            restored_repo_artifacts,
            "failure probe must not create or change scaffold files in the repository",
        )

    def test_scaffold_missing_state_source_fails_before_authoring(self):
        """An absent shipped state file must fail before any scaffold output."""
        scaffold_block = _scaffold_block(self.fixture)

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
            _isolated_shipped_smoke_marker(),
        ):
            safe_cwd = pathlib.Path(temp_dir)
            probe_marker = safe_cwd / "smoke-result"
            workflow_env = {
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "GITHUB_WORKSPACE": str(safe_cwd),
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }
            self.assertFalse(
                STATE_PATH.exists(),
                "the missing-source probe requires the shipped state path to be absent",
            )

            probe_block = _scaffold_block_with_probe_marker(
                scaffold_block, probe_marker
            )
            probe = _run_bash(probe_block, workflow_env, cwd=safe_cwd)
            marker_bytes = probe_marker.read_bytes() if probe_marker.is_file() else b""
            scaffold_outputs = [
                relative_path
                for relative_path in SCAFFOLD_FILES
                if (safe_cwd / relative_path).exists()
            ]

            self.assertNotEqual(
                0,
                probe.returncode,
                "an absent shipped state source must return nonzero",
            )
            self.assertTrue(
                marker_bytes.startswith(b"SMOKE_RESULT=FAIL"),
                "an absent shipped state source must write the deterministic FAIL "
                f"marker; marker={marker_bytes!r} stderr={probe.stderr!r}",
            )
            self.assertEqual(
                [],
                scaffold_outputs,
                "an absent shipped state source must not create scaffold outputs; "
                f"outputs={scaffold_outputs!r}",
            )

    def test_scaffold_first_heredoc_write_failure_stops_later_writes(self):
        """A first-heredoc redirection failure must stop all later heredocs."""
        scaffold_block = _scaffold_block(self.fixture)

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
            _isolated_shipped_smoke_marker(),
        ):
            safe_cwd = pathlib.Path(temp_dir)
            project_dir = safe_cwd / "project"
            (project_dir / "src").mkdir(parents=True)
            (project_dir / "infra").mkdir()
            (project_dir / "src" / "server.py").mkdir()
            probe_marker = safe_cwd / "smoke-result"
            STATE_PATH.write_text(
                "\n".join(
                    (
                        "APP_NAME=ci-smoke-mcp-heredoc-failure",
                        f"PROJECT_DIR={shlex.quote(str(project_dir))}",
                        "UAMI_RESOURCE_ID=/subscriptions/test/resourceGroups/test/"
                        "providers/Microsoft.ManagedIdentity/"
                        "userAssignedIdentities/test",
                        "ACR_SERVER=test.azurecr.io",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            probe_block = _scaffold_block_with_probe_marker(
                scaffold_block, probe_marker
            )
            probe = _run_bash(
                probe_block,
                {"PATH": "/usr/bin:/bin:/usr/local/bin"},
                cwd=safe_cwd,
            )
            marker_bytes = probe_marker.read_bytes() if probe_marker.is_file() else b""
            later_outputs = [
                relative_path
                for relative_path in SCAFFOLD_FILES[1:]
                if (project_dir / relative_path).exists()
            ]

            self.assertNotEqual(
                0,
                probe.returncode,
                "a directory at src/server.py must make the first heredoc fail",
            )
            self.assertTrue(
                marker_bytes.startswith(b"SMOKE_RESULT=FAIL"),
                "the first-heredoc failure must write the deterministic FAIL marker; "
                f"marker={marker_bytes!r} stderr={probe.stderr!r}",
            )
            self.assertEqual(
                [],
                later_outputs,
                "the first-heredoc failure must prevent all later scaffold writes; "
                f"outputs={later_outputs!r}",
            )

    def test_scaffold_missing_persisted_state_fails_before_authoring(self):
        """Every missing persisted value must deterministically fail before writes."""
        scaffold_block = _scaffold_block(self.fixture)

        with (
            tempfile.TemporaryDirectory() as temp_dir,
            _isolated_shipped_state_file(),
            _isolated_shipped_smoke_marker(),
        ):
            safe_cwd = pathlib.Path(temp_dir)
            state_values = {
                "APP_NAME": "ci-smoke-mcp-state-probe",
                "PROJECT_DIR": "",
                "UAMI_RESOURCE_ID": (
                    "/subscriptions/test/resourceGroups/test/providers/"
                    "Microsoft.ManagedIdentity/userAssignedIdentities/test"
                ),
                "ACR_SERVER": "test.azurecr.io",
            }

            for missing_variable in SCAFFOLD_STATE_VARIABLES:
                with self.subTest(missing_persisted_variable=missing_variable):
                    project_dir = safe_cwd / f"project-{missing_variable.lower()}"
                    state_values["PROJECT_DIR"] = str(project_dir)
                    STATE_PATH.write_text(
                        "\n".join(
                            f"{variable}={shlex.quote(value)}"
                            for variable, value in state_values.items()
                            if variable != missing_variable
                        )
                        + "\n",
                        encoding="utf-8",
                    )

                    source_probe = _run_bash(
                        "source /tmp/foundry-mcp-aca-state.env",
                        {"PATH": "/usr/bin:/bin"},
                        cwd=safe_cwd,
                    )
                    self.assertEqual(
                        0,
                        source_probe.returncode,
                        "state omission probe must use a syntactically valid state "
                        f"file; missing={missing_variable} "
                        f"stderr={source_probe.stderr!r}",
                    )

                    probe_marker = safe_cwd / (
                        f"smoke-result-{missing_variable.lower()}"
                    )
                    probe_block = _scaffold_block_with_probe_marker(
                        scaffold_block, probe_marker
                    )
                    probe = _run_bash(
                        probe_block,
                        {"PATH": "/usr/bin:/bin"},
                        cwd=safe_cwd,
                    )
                    marker_bytes = (
                        probe_marker.read_bytes()
                        if probe_marker.is_file()
                        else b""
                    )
                    unexpected_outputs = [
                        str(path.relative_to(safe_cwd))
                        for base in (project_dir, safe_cwd)
                        for path in (
                            base / "src",
                            base / "infra",
                            *(base / relative for relative in SCAFFOLD_FILES),
                        )
                        if path.exists()
                    ]

                    self.assertNotEqual(
                        0,
                        probe.returncode,
                        "missing persisted state must return nonzero; "
                        f"missing={missing_variable}",
                    )
                    self.assertTrue(
                        marker_bytes.startswith(b"SMOKE_RESULT=FAIL"),
                        "missing persisted state must write the deterministic FAIL "
                        f"marker; missing={missing_variable} "
                        f"marker={marker_bytes!r} stderr={probe.stderr!r}",
                    )
                    self.assertEqual(
                        [],
                        unexpected_outputs,
                        "missing persisted state must fail before mkdir or any "
                        f"scaffold heredoc; missing={missing_variable} "
                        f"outputs={unexpected_outputs!r}",
                    )

    def test_scaffold_authoring_section_has_exact_shape(self):
        """Step 2 is exactly two headings and one standard Bash fence."""
        scaffold_block = _scaffold_block(self.fixture)
        _scaffold_shell_contract(scaffold_block)
        _assert_single_scaffold_writer_block(self.fixture, scaffold_block)

    def test_first_page_guard_forbids_nondeterministic_file_authoring(self):
        """The critical guard must make the one Bash scaffold path mandatory."""
        first_page = self.fixture[:3000]
        guard_matches = list(
            re.finditer(
                rf"(?m)^{re.escape(DETERMINISTIC_GUARD_HEADING)}$",
                self.fixture,
            )
        )
        self.assertEqual(
            1,
            len(guard_matches),
            "the exact deterministic scaffold-authoring guard heading must occur "
            "exactly once",
        )
        guard_start = guard_matches[0].start()
        self.assertLess(
            guard_start,
            len(first_page),
            "the exact deterministic scaffold-authoring guard heading must begin "
            "within the fixture's first 3000 characters",
        )
        following = self.fixture[guard_matches[0].end():]
        guard_end = re.search(
            r"\n(?:\*\*CRITICAL\b|---\s*$|##\s)",
            following,
            re.MULTILINE,
        )
        guard_body = following[: guard_end.start()] if guard_end else following
        normalized_guard = re.sub(r"\s+", " ", guard_body).strip()
        missing = [
            sentence
            for sentence in EXPECTED_GUARD_SENTENCES
            if re.sub(r"\s+", " ", sentence) not in normalized_guard
        ]
        self.assertEqual(
            [],
            missing,
            "the exact first-page guard is missing required machine-contract "
            f"sentences: {missing}",
        )

    def test_protocol_version_fails_if_empty(self):
        """Fixture must FAIL if negotiated protocolVersion is empty."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        # Must have an explicit fail gate on empty PROTOCOL_VERSION
        self.assertRegex(
            combined,
            r'(if\s+\[\s+-z\s+"\$PROTOCOL_VERSION"\s*\]|'
            r'\[\s+-z\s+"\$PROTOCOL_VERSION"\s*\]\s*&&)',
            "Fixture must FAIL deterministically when protocolVersion is empty — "
            "the MCP spec requires a negotiated version.",
        )

    def test_protocol_version_header_unconditional(self):
        """MCP-Protocol-Version header must be added unconditionally (not gated on -n)."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        # The conditional pattern `[ -n "$PROTOCOL_VERSION" ] && SESSION_ARGS+=` is wrong
        self.assertNotRegex(
            combined,
            r'\[\s+-n\s+"\$PROTOCOL_VERSION"\s*\]\s*&&\s*SESSION_ARGS',
            "MCP-Protocol-Version header must be unconditional — protocol version "
            "is mandatory per MCP 2025-06-18; conditional add defeats the FAIL gate.",
        )

    def test_mcp_exchange_state_persisted_to_file(self):
        """FQDN, SESSION_ID, PROTOCOL_VERSION must be persisted to STATE_FILE."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        for var in ("FQDN", "SESSION_ID", "PROTOCOL_VERSION"):
            self.assertRegex(
                combined,
                rf'echo\s+"?{var}=',
                f"{var} must be appended/written to STATE_FILE for cross-fence persistence",
            )

    def test_initialized_notification_captures_status_scoped(self):
        """notifications/initialized status gate must be in the actual enforcement block."""
        # Find the bash block containing the actual curl for notifications/initialized
        method_marker = '"method": "notifications/initialized"'
        idx = self.fixture.find(method_marker)
        self.assertGreater(idx, 100, "enforcement block for notifications/initialized not found")
        # Find the containing bash block
        block_start = self.fixture.rfind("```bash", 0, idx)
        block_end = self.fixture.find("```", idx)
        enforcement_block = self.fixture[block_start:block_end]
        # Must contain the 202 status check
        self.assertIn("!= \"202\"", enforcement_block,
                      "The enforcement block must assert HTTP 202 for notifications/initialized")
        # Must NOT contain || true
        self.assertNotIn("|| true", enforcement_block,
                         "notifications/initialized must not swallow failures with || true")

    def test_initialized_requires_http_202_scoped(self):
        """HTTP 202 gate must be in the enforcement block, not just mentioned in prose."""
        method_marker = '"method": "notifications/initialized"'
        idx = self.fixture.find(method_marker)
        self.assertGreater(idx, 100)
        block_start = self.fixture.rfind("```bash", 0, idx)
        block_end = self.fixture.find("```", idx)
        enforcement_block = self.fixture[block_start:block_end]
        # Must have FAIL on non-202
        self.assertIn("SMOKE_RESULT=FAIL", enforcement_block,
                      "notifications/initialized must write FAIL marker on non-202")

    def test_skill_consumer_config_no_trailing_slash(self):
        """SKILL.md consumer config must use /mcp (no trailing slash) for FastMCP 2.x."""
        skill = SKILL_MD.read_text(encoding="utf-8")
        # Find the consumer config JSON block with url field
        config_match = re.search(r'"url":\s*"https://[^"]+/mcp/"', skill)
        self.assertIsNone(
            config_match,
            "SKILL.md consumer config uses /mcp/ (trailing slash) but pinned FastMCP 2.x "
            "returns 307 for trailing slash. Use /mcp (no slash).",
        )


    def test_anti_catalog_inspection_guard(self):
        """Fixture must explicitly forbid reading catalog source files."""
        # The guard must name specific forbidden paths
        self.assertIn("Do NOT read, view, grep, glob, or open ANY repository file",
                      self.fixture)
        for forbidden in ["SKILL.md", "scripts/tests/", ".github/workflows/",
                          "skill-deps.yml"]:
            self.assertIn(forbidden, self.fixture[:2000],
                          f"Anti-catalog-inspection guard must mention '{forbidden}' "
                          "in the preamble (first 2000 chars)")


    # --- Blocker 1: auth curl targets must use /mcp not /mcp/ ---
    def test_auth_curl_targets_use_canonical_mcp_path(self):
        """Step 5b auth curl targets must use /mcp (no trailing slash).
        FastMCP 2.14.7 returns 307 for /mcp/ which breaks non-redirect curls."""
        # Extract Step 5b auth section (after MCP_AUTH_APP_CLIENT_ID check)
        auth_section = ""
        in_auth = False
        for line in self.fixture.split("\n"):
            if "MCP_AUTH_APP_CLIENT_ID" in line:
                in_auth = True
            if in_auth:
                auth_section += line + "\n"
        # All curl URLs in auth section must use /mcp" not /mcp/"
        import re
        curl_urls = re.findall(r'https://\$\{FQDN\}/mcp/?["\']?\)', auth_section)
        for url in curl_urls:
            self.assertNotIn("/mcp/", url,
                             "Auth curl target must use /mcp (no trailing slash); "
                             "FastMCP 2.14.7 returns 307 for /mcp/")

    # --- Blocker 2: malformed JSON must not bypass tools/list gate ---
    def test_tools_list_gate_handles_malformed_json(self):
        """TOOL_COUNT assignment must use jq -e or explicit parse guard so
        malformed JSON cannot silently bypass the >=1 check."""
        # Find the TOOL_COUNT assignment block
        import re
        # The gate must either use jq -e, or have an explicit empty/error guard
        tool_count_match = re.search(
            r'TOOL_COUNT=\$\(.*?\)', self.fixture, re.DOTALL)
        self.assertIsNotNone(tool_count_match, "TOOL_COUNT assignment not found")
        tc_line = tool_count_match.group(0)
        # Must have explicit malformed-JSON protection:
        # Either jq -e (exits non-zero on null/false), or a subsequent
        # empty-string guard before the arithmetic comparison
        has_jq_e = "jq -e" in tc_line
        # Check for explicit empty guard after assignment
        tc_pos = tool_count_match.end()
        next_100 = self.fixture[tc_pos:tc_pos + 200]
        has_empty_guard = ('[ -z "$TOOL_COUNT" ]' in next_100 or
                           '[ -z "${TOOL_COUNT' in next_100 or
                           'TOOL_COUNT:-' in next_100 or
                           '|| {' in tc_line or
                           '|| printf' in tc_line or
                           '|| exit' in tc_line)
        self.assertTrue(has_jq_e or has_empty_guard,
                        "TOOL_COUNT gate must protect against malformed JSON: "
                        "use 'jq -e' or guard empty TOOL_COUNT before arithmetic test. "
                        f"Found: {tc_line}")

    def test_tools_list_gate_enforces_jsonrpc_tools_array_contract(self):
        """Execute the shipped gate against valid and invalid tools/list bodies."""
        gate_match = re.search(
            r'^TOOL_COUNT=\$\(echo "\$TOOLS_JSON".*?'
            r'^echo "tools/list returned \$TOOL_COUNT tool\(s\)"$',
            self.fixture,
            re.DOTALL | re.MULTILINE,
        )
        self.assertIsNotNone(gate_match, "Executable tools/list gate not found")

        invalid_payloads = {
            "malformed syntax": '{"jsonrpc":"2.0","result":',
            "missing result.tools": '{"jsonrpc":"2.0","result":{}}',
            "JSON-RPC error": (
                '{"jsonrpc":"2.0","error":{"code":-32603,"message":"failure"},"id":2}'
            ),
            "null tools": '{"jsonrpc":"2.0","result":{"tools":null},"id":2}',
            "string tools": '{"jsonrpc":"2.0","result":{"tools":"echo"},"id":2}',
            "object tools": (
                '{"jsonrpc":"2.0","result":{"tools":{"name":"echo"}},"id":2}'
            ),
            "empty tools array": '{"jsonrpc":"2.0","result":{"tools":[]},"id":2}',
        }
        valid_payload = (
            '{"jsonrpc":"2.0","result":{"tools":[{"name":"echo"}]},"id":2}'
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            marker = pathlib.Path(temp_dir) / "smoke-result"
            gate = gate_match.group(0).replace(
                "/tmp/foundry-mcp-aca-smoke-result", str(marker)
            )

            for name, payload in invalid_payloads.items():
                with self.subTest(payload=name):
                    result = subprocess.run(
                        ["bash", "-c", gate],
                        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "TOOLS_JSON": payload},
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(
                        result.returncode,
                        0,
                        f"{name} incorrectly passed the shipped tools/list gate: "
                        f"stdout={result.stdout!r} stderr={result.stderr!r}",
                    )

            result = subprocess.run(
                ["bash", "-c", gate],
                env={"PATH": "/usr/bin:/bin:/usr/local/bin", "TOOLS_JSON": valid_payload},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                "valid JSON-RPC tools/list response failed the shipped gate: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()
