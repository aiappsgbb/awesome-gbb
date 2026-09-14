"""Canonical Harness CI probe. The workflow owns dependencies and Azure login."""

from __future__ import annotations

import asyncio
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import stat
import sys


ROOT = Path(__file__).resolve().parents[3]
REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references/python"
VENV_PATH = ROOT / ".scratch/agent-framework-harness-venv"
RESULT_PATH = Path("/tmp/agent-framework-harness-smoke-result")
EVIDENCE_PATH = Path("/tmp/agent-framework-harness-smoke-evidence")
REQUIRED_ENV = (
    "AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID",
    "FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL_DEPLOYMENT",
    "AZURE_CONFIG_DIR", "RUNNER_TEMP",
)


class SmokeFailure(Exception):
    """Fixed diagnostic codes only; never credential or service-response values."""


def runtime_requirements() -> dict[str, tuple[str, str]]:
    requirements = {}
    for line in Path(__file__).with_name("requirements.txt").read_text().splitlines():
        match = re.fullmatch(r"([a-z0-9-]+)(~=|==)([0-9a-z.]+)", line)
        if match is None:
            raise SmokeFailure("RUNTIME_MANIFEST")
        name, operator, expected = match.groups()
        if name in requirements or (operator == "~=" and not re.fullmatch(r"\d+\.\d+\.\d+", expected)):
            raise SmokeFailure("RUNTIME_MANIFEST")
        requirements[name] = (operator, expected)
    if not requirements:
        raise SmokeFailure("RUNTIME_MANIFEST")
    return requirements


def validate_versions(values: object) -> dict[str, str]:
    requirements = runtime_requirements()
    if not isinstance(values, dict) or set(values) != set(requirements):
        raise SmokeFailure("PACKAGE_SET")
    versions = {}
    for name, (operator, expected) in requirements.items():
        actual = values[name]
        if not isinstance(actual, str):
            raise SmokeFailure(f"PACKAGE_VERSION {name}")
        if operator == "==":
            valid = actual == expected
        else:
            release = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", actual)
            floor = tuple(int(part) for part in expected.split("."))
            resolved = tuple(int(part) for part in release.groups()) if release else ()
            valid = len(resolved) == 3 and resolved[:2] == floor[:2] and resolved >= floor
        if not valid:
            raise SmokeFailure(f"PACKAGE_VERSION {name}")
        versions[name] = actual
    return versions


def validate_runtime() -> dict[str, str]:
    executable = Path(sys.executable)
    if (
        Path(sys.prefix).resolve() != VENV_PATH.resolve()
        or executable.is_symlink()
        or not executable.is_file()
        or not executable.resolve().is_relative_to(VENV_PATH.resolve())
    ):
        raise SmokeFailure("RUNTIME_PREFIX")
    if os.environ.get("PYTHONPATH") or os.environ.get("PYTHONHOME"):
        raise SmokeFailure("RUNTIME_ENV")
    versions = {}
    for name in runtime_requirements():
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            raise SmokeFailure(f"MISSING_PACKAGE {name}") from None
    return validate_versions(versions)


def load_context() -> dict[str, str]:
    context = {}
    for name in REQUIRED_ENV:
        value = os.environ.get(name, "")
        if not value.strip():
            raise SmokeFailure(f"MISSING_ENV {name}")
        context[name] = value
    profile = Path(context["AZURE_CONFIG_DIR"])
    runner_temp = Path(context["RUNNER_TEMP"]).resolve()
    if (
        not profile.is_absolute()
        or profile.is_symlink()
        or profile.resolve().parent != runner_temp
        or not profile.name.startswith("harness-azure-cli.")
        or not profile.is_dir()
        or stat.S_IMODE(profile.stat().st_mode) != 0o700
    ):
        raise SmokeFailure("PROFILE_SCOPE")
    return context


def make_credential(context: dict[str, str]):
    from azure.identity.aio import AzureCliCredential

    try:
        return AzureCliCredential(
            subscription=context["AZURE_SUBSCRIPTION_ID"],
        )
    except TypeError:
        raise SmokeFailure("CREDENTIAL_CONTRACT") from None


async def run_smoke(context: dict[str, str]) -> None:
    from agent_framework import Agent, AgentSession
    from agent_framework_foundry_hosting import ResponsesHostServer
    from azure.core.exceptions import AzureError
    from openai import OpenAIError

    previous_path = sys.path[:]
    sys.path.insert(0, str(REFERENCE_DIR))
    try:
        from hosted_harness import build_agent, build_server
        from session_recovery import restore_session, serialize_session

        async with make_credential(context) as credential:
            agent = build_agent(
                project_endpoint=context["FOUNDRY_PROJECT_ENDPOINT"],
                model=context["FOUNDRY_MODEL_DEPLOYMENT"],
                credential=credential,
            )
            if not isinstance(agent, Agent) or agent.default_options["store"] is not False:
                raise SmokeFailure("AGENT_CONTRACT")
            print("HARNESS_AGENT_CONSTRUCTED")
            if not isinstance(build_server(agent), ResponsesHostServer):
                raise SmokeFailure("HOSTING_CONTRACT")
            print("HOSTING_ADAPTER_CONSTRUCTED")
            session = restore_session(serialize_session(agent.create_session()))
            if not isinstance(session, AgentSession):
                raise SmokeFailure("SESSION_CONTRACT")
            response = await agent.run("Reply with exactly HARNESS_LIVE_OK.", session=session)
            if "HARNESS_LIVE_OK" not in response.text:
                raise SmokeFailure("RESPONSE_MARKER")
            print("HARNESS_LIVE_RESPONSE_OK")
    except (AzureError, OpenAIError) as error:
        raise SmokeFailure(type(error).__name__) from None
    finally:
        sys.path[:] = previous_path


def execution_evidence(versions: dict[str, str]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "credential_type": "AzureCliCredential",
        "runtime_versions": versions,
        "runtime_prefix_matched": True,
        "agent_run_calls": 1,
        "response_marker_found": True,
        "reference_sha256": hashlib.sha256(
            (REFERENCE_DIR / "hosted_harness.py").read_bytes()
        ).hexdigest(),
    }


def verify_result() -> None:
    for path in (RESULT_PATH, EVIDENCE_PATH):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 16_384:
            raise SmokeFailure("RESULT_FILE")
    if RESULT_PATH.read_bytes() != b"SMOKE_RESULT=PASS\n":
        raise SmokeFailure("RESULT_MARKER")
    try:
        evidence = json.loads(EVIDENCE_PATH.read_text())
    except (ValueError, UnicodeError):
        raise SmokeFailure("EVIDENCE_JSON") from None
    if not isinstance(evidence, dict):
        raise SmokeFailure("EVIDENCE_CONTRACT")
    versions = validate_versions(evidence.get("runtime_versions"))
    expected = execution_evidence(versions)
    if json.dumps(evidence, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise SmokeFailure("EVIDENCE_CONTRACT")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["--check-runtime"], ["--verify-result"]):
        try:
            if args == ["--check-runtime"]:
                validate_runtime()
                make_credential({"AZURE_SUBSCRIPTION_ID": "ci-check"})
            else:
                verify_result()
        except (SmokeFailure, OSError) as error:
            code = str(error) if isinstance(error, SmokeFailure) else type(error).__name__
            print(f"HARNESS_CHECK_FAIL {code}")
            return 1
        print("HARNESS_RUNTIME_READY" if args == ["--check-runtime"] else "HARNESS_EXECUTION_VERIFIED")
        return 0

    RESULT_PATH.write_text("SMOKE_RESULT=FAIL Harness smoke did not complete\n")
    EVIDENCE_PATH.unlink(missing_ok=True)
    try:
        if args:
            raise SmokeFailure("ARGUMENTS")
        versions = validate_runtime()
        context = load_context()
        print("skills/agent-framework-harness/test-fixture/live_smoke.py")
        print("HARNESS_RUNTIME_VERIFIED")
        asyncio.run(run_smoke(context))
        EVIDENCE_PATH.write_text(json.dumps(execution_evidence(versions), sort_keys=True) + "\n")
    except (SmokeFailure, OSError) as error:
        code = str(error) if isinstance(error, SmokeFailure) else type(error).__name__
        RESULT_PATH.write_text(f"SMOKE_RESULT=FAIL {code}\n")
        print(f"HARNESS_SMOKE_FAIL {code}")
        return 1
    RESULT_PATH.write_text("SMOKE_RESULT=PASS\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
