#!/usr/bin/env python3
"""Private CI delivery boundary; no Azure calls or native scoring implementation.

The fixture's two checked-in assertion blocks remain the only scoring/readiness
checks. This host-side adapter executes them read-only, then projects a fixed
public allowlist. Runner pointers/identity files are NOT native AgentOps schemas.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


METRICS = ("coherence", "fluency", "similarity", "response_completeness", "avg_latency_seconds")
EVAL_FILES = (".agentops/results/eval-exit-code", ".agentops/results/latest/results.json",
              ".agentops/data/smoke.jsonl")
DOCTOR_FILES = (".agentops/agent/doctor-exit-code", ".agentops/agent/doctor-started-at",
                ".agentops/agent/doctor-finished-at", ".agentops/agent/history.jsonl",
                ".agentops/release/latest/evidence.json")
ARTIFACT_LABELS = dict(zip(EVAL_FILES + DOCTOR_FILES, (
    "eval_exit", "results", "dataset", "doctor_exit", "doctor_started",
    "doctor_finished", "history", "evidence",
)))
FIXTURE = "skills/foundry-agentops/test-fixture/consumer_prompt.md"
LIMIT = 4 * 1024 * 1024
LEGACY_DIRECTORY = Path("/tmp")
LEGACY_FILES = (
    "foundry-agentops-transcript.log", "foundry-agentops-retry.log",
    "foundry-agentops-smoke-evidence", "foundry-agentops-primary-smoke-evidence",
    "foundry-agentops-retry-smoke-evidence", "foundry-agentops-invoke.log",
    "foundry-agentops-primary-invoke.log", "foundry-agentops-retry-invoke.log",
    "foundry-agentops-smoke-result",
)


def require(condition):
    if not condition:
        raise ValueError("invalid delivery contract")


def absolute(value):
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts)
    return path


def roots():
    runner = absolute(os.environ["RUNNER_TEMP"])
    run, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    require(re.fullmatch(r"[1-9][0-9]*", run) and re.fullmatch(r"[1-9][0-9]*", attempt))
    return runner / f"agentops-ci-{run}-{attempt}", runner / f"agentops-ci-public-{run}-{attempt}"


@contextmanager
def directory(path, private=None):
    """Walk each component with no-follow dirfds, including non-private parents."""
    path = absolute(str(path))
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    walked = Path(path.anchor)
    try:
        for part in path.parts[1:]:
            walked /= part
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            if private is not None and walked.is_relative_to(private):
                info = os.fstat(fd)
                require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700)
        yield fd
    finally:
        os.close(fd)


def mkdir(path, private=None):
    with directory(path.parent, private) as fd:
        os.mkdir(path.name, 0o700, dir_fd=fd)


def file_info(fd):
    info = os.fstat(fd)
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600)


def read(path, private):
    with directory(path.parent, private) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            file_info(stream.fileno())
            raw = stream.read(LIMIT + 1)
            require(len(raw) <= LIMIT)
            return raw


@contextmanager
def new_file(path, private):
    with directory(path.parent, private) as parent:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        with os.fdopen(fd, "wb") as stream:
            file_info(stream.fileno())
            yield stream


def write(path, private, raw):
    with new_file(path, private) as stream:
        stream.write(raw)


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result

    def reject(_):
        raise ValueError("nonfinite JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)


class DiagnosticFailure(Exception):
    """Only code-defined reasons/labels may cross the public boundary."""

    def __init__(self, reason, artifact=None):
        super().__init__(reason)
        self.diagnostic = {"reason": reason}
        if artifact is not None:
            self.diagnostic["artifact"] = artifact


def read_artifact(path, private, artifact):
    try:
        return read(path, private)
    except FileNotFoundError:
        raise DiagnosticFailure("absent", artifact) from None
    except (OSError, ValueError):
        raise DiagnosticFailure("unsafe_or_unreadable", artifact) from None


def parse_artifact(raw, artifact):
    try:
        return parse(raw)
    except (ValueError, TypeError, RecursionError):
        raise DiagnosticFailure("malformed", artifact) from None


def initialize(root, public):
    mkdir(root)
    for name in ("azure", "azd", "attempts", "workspaces"):
        mkdir(root / name, root)
    mkdir(public)


def attempt_dir(root, attempt):
    require(attempt in ("primary", "retry"))
    return root / "attempts" / attempt


def prepare(root, attempt):
    target = attempt_dir(root, attempt)
    mkdir(target, root)
    write(target / "transcript.log", root, b"")


def workspace_path(root, attempt):
    # A pointer is only a UUID, never a supplied absolute or relative path.
    pointer = read_artifact(attempt_dir(root, attempt) / "workspace-pointer", root, "workspace_pointer")
    if not re.fullmatch(rb"[0-9a-f]{32}\n", pointer):
        raise DiagnosticFailure("malformed", "workspace_pointer")
    path = root / "workspaces" / pointer.decode().strip()
    try:
        with directory(path, root):
            return path
    except FileNotFoundError:
        raise DiagnosticFailure("absent", "workspace") from None
    except (OSError, ValueError):
        raise DiagnosticFailure("unsafe_or_unreadable", "workspace") from None


def checker_block(fixture, label):
    begin, end = f"# BEGIN AGENTOPS {label} CHECK", f"# END AGENTOPS {label} CHECK"
    require(fixture.count(begin) == fixture.count(end) == 1)
    block = fixture.split(begin, 1)[1].split(end, 1)[0]
    compile(block, "<fixture-assertions>", "exec")
    return block


def run_checker(root, attempt, workspace, block, identity, label):
    # -I rejects cwd/PYTHONPATH shadow modules and ignores PYTHONOPTIMIZE.
    # No credentials/exporter settings are needed by these stdlib-only blocks.
    with new_file(attempt / f"{label}-check.log", root) as log:
        result = subprocess.run(
            [sys.executable, "-I", "-c", block, identity["name"], identity["version"]],
            cwd=workspace, env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=log, stderr=subprocess.STDOUT, timeout=60, check=False,
        )
    return result.returncode


def eval_projection(result):
    # Called only after the original eval checker accepted these bytes.
    return {
        "metrics": {key: result["aggregate_metrics"][key] for key in METRICS},
        "quality": {key: result["summary"][native] for key, native in (
            ("passed", "overall_passed"), ("thresholds_passed", "thresholds_passed"),
            ("thresholds_total", "thresholds_total"))},
    }


def doctor_projection(evidence):
    # Called only after the original Doctor checker accepted these bytes.
    by_name = {item["name"]: item["status"] for item in evidence["checks"]}
    diagnostics = evidence.get("monitoring", {}).get("diagnostics", {})
    aggregates = (evidence.get("monitoring", {}).get("status") == "ok"
                  and diagnostics.get("enabled") is True
                  and diagnostics.get("lookback_days") == 1
                  and all(diagnostics.get(key) == "ok" for key in
                          ("status", "safety_status", "token_status", "rate_limit_status")))
    return {
        "doctor": {
            "readiness": evidence["status"],
            "severity_counts": {key: evidence["doctor"]["counts"][key]
                                for key in ("critical", "warning", "info")},
        },
        "coverage": {
            "component_aggregates": "queried" if aggregates else "unverified",
            "fresh_ingestion": "unverified", "multi_turn": "unverified",
            "rubrics": "unverified",
            "official_eval": evidence.get("official_eval", {}).get("status", "missing"),
            "observability": by_name.get("Foundry observability", "unknown"),
            "governance": by_name.get("Governance artifacts", "unknown"),
            "landing_zone": by_name.get("AI Landing Zone readiness", "unknown"),
        },
    }


def report_workspace(root, target, workspace, summary):
    # This owned marker is independent of native evidence/identity acceptance.
    try:
        if read(workspace / "prompt-agent-cleanup", root) == b"verified\n":
            summary["prompt_agent_cleanup"] = "verified"
    except (OSError, ValueError):
        pass

    # Exit observations are not evidence acceptance, quality, or readiness.
    native_raw = {}
    for label, paths in (("eval", EVAL_FILES), ("doctor", DOCTOR_FILES)):
        try:
            raw = read_artifact(workspace / paths[0], root, ARTIFACT_LABELS[paths[0]])
            if raw.strip() not in (b"0", b"1", b"2"):
                raise DiagnosticFailure("malformed", ARTIFACT_LABELS[paths[0]])
            summary["native_exit_codes"][label] = int(raw.strip())
            native_raw[label] = raw
        except DiagnosticFailure as failure:
            summary["diagnostics"][label] = failure.diagnostic

    try:
        identity = parse_artifact(read_artifact(workspace / "agent-identity.json", root, "identity"),
                                  "identity")
        if not (isinstance(identity, dict) and set(identity) == {"name", "version"}
                and all(isinstance(value, str) and value.strip() and len(value) <= 256
                        for value in identity.values())):
            raise DiagnosticFailure("malformed", "identity")
    except DiagnosticFailure as failure:
        summary["diagnostics"]["identity"] = failure.diagnostic
        return

    try:
        if read_artifact(workspace / ".agentops/analyze-exit-code", root, "analyze_exit").strip() != b"0":
            raise DiagnosticFailure("contract_rejected", "analyze_exit")
        analyze_raw = read_artifact(workspace / ".agentops/analyze.json", root, "analyze")
        analyze = parse_artifact(analyze_raw, "analyze")
        if not (isinstance(analyze, dict) and type(analyze.get("version")) is int and analyze["version"] == 1):
            raise DiagnosticFailure("contract_rejected", "analyze")
        summary["execution_checks"]["analyze"] = "verified"
        summary["sha256"]["analyze"] = hashlib.sha256(analyze_raw).hexdigest()
    except DiagnosticFailure as failure:
        summary["diagnostics"]["analyze"] = failure.diagnostic

    try:
        fixture = (absolute(os.environ["GITHUB_WORKSPACE"]) / FIXTURE).read_text()
    except (OSError, ValueError, KeyError):
        summary["diagnostics"]["fixture"] = {"reason": "checker_unavailable"}
        return

    for label, paths, accepted in (("eval", EVAL_FILES, {0}), ("doctor", DOCTOR_FILES, {0, 2})):
        if label not in native_raw:
            continue
        try:
            raw = {paths[0]: native_raw[label]}
            for path in paths[1:]:
                data = read_artifact(workspace / path, root, ARTIFACT_LABELS[path])
                raw[path] = data
                if path.endswith((".json", ".jsonl")):
                    for line in data.splitlines() if path.endswith(".jsonl") else [data]:
                        if line.strip() or path.endswith(".json"):
                            parse_artifact(line, ARTIFACT_LABELS[path])
            try:
                block = checker_block(fixture, "EVAL RESULT" if label == "eval" else "DOCTOR EVIDENCE")
                code = run_checker(root, target, workspace, block, identity, label)
            except (OSError, ValueError, SyntaxError, subprocess.SubprocessError):
                raise DiagnosticFailure("checker_unavailable") from None
            summary["checker_exit_codes"][label] = code if code in (0, 1, 2) else None
            if code not in accepted:
                raise DiagnosticFailure("checker_rejected")
            # Do not publish a projection of different bytes than the checkers read.
            for path, data in raw.items():
                if read_artifact(workspace / path, root, ARTIFACT_LABELS[path]) != data:
                    raise DiagnosticFailure("changed_after_check", ARTIFACT_LABELS[path])
            if label == "eval":
                projection = eval_projection(parse(raw[EVAL_FILES[1]]))
                hashes = (("results", raw[EVAL_FILES[1]]),)
            else:
                projection = doctor_projection(parse(raw[DOCTOR_FILES[-1]]))
                hashes = (("evidence", raw[DOCTOR_FILES[-1]]), ("history", raw[DOCTOR_FILES[-2]]))
            summary.update(projection)
            summary["execution_checks"][label] = "verified"
            for name, data in (*hashes, ("fixture", fixture.encode())):
                summary["sha256"][name] = hashlib.sha256(data).hexdigest()
        except DiagnosticFailure as failure:
            summary["diagnostics"][label] = failure.diagnostic


def report(root, public, attempt, copilot_status):
    require(re.fullmatch(r"[0-9]{1,3}", copilot_status) and int(copilot_status) <= 255)
    target = attempt_dir(root, attempt)
    summary = {
        "execution_checks": {"analyze": "failed", "eval": "failed", "doctor": "failed"},
        "checker_exit_codes": {"eval": None, "doctor": None},
        "native_exit_codes": {"eval": None, "doctor": None},
        "copilot_exit_code": int(copilot_status), "marker": "failed", "delivery": "failed",
        "prompt_agent_cleanup": "unverified", "response_purge": "unverified",
        "sha256": {}, "diagnostics": {},
    }
    try:
        marker = read_artifact(target / "marker", root, "marker")
        if marker != b"SMOKE_RESULT=PASS\n":
            failed = any(line == b"SMOKE_RESULT=FAIL" or line.startswith(b"SMOKE_RESULT=FAIL ")
                         for line in marker.splitlines())
            raise DiagnosticFailure("explicit_fail" if failed else "invalid_marker", "marker")
        summary["marker"] = "passed"
    except DiagnosticFailure as failure:
        summary["diagnostics"]["marker"] = failure.diagnostic
    try:
        workspace = workspace_path(root, attempt)
    except DiagnosticFailure as failure:
        summary["diagnostics"]["workspace"] = failure.diagnostic
    else:
        report_workspace(root, target, workspace, summary)
    if (all(value == "verified" for value in summary["execution_checks"].values())
            and summary["marker"] == "passed" and copilot_status == "0"):
        summary["delivery"] = "passed"
    write(public / f"{attempt}.json", public,
          (json.dumps(summary, sort_keys=True, allow_nan=False) + "\n").encode())
    return summary["delivery"] == "passed"


def retry_allowed(root):
    # Conservative: once a workspace exists, retain the primary cycle. A
    # classifier hit in native output must never trigger a second evaluation.
    with directory(root / "workspaces", root) as fd:
        return not os.listdir(fd)


def clean_directory(fd):
    ok = True
    for name in os.listdir(fd):
        try:
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            require(info.st_uid == os.getuid())
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    child_ok = clean_directory(child)
                    ok = child_ok and ok
                finally:
                    os.close(child)
                if child_ok:
                    os.rmdir(name, dir_fd=fd)
            else:
                # Unlink a symlink itself; never follow it to its destination.
                os.unlink(name, dir_fd=fd)
        except (OSError, ValueError):
            ok = False
    return ok


def cleanup_private(root):
    with directory(root.parent) as parent:
        try:
            info = os.stat(root.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return True
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o700)
        fd = os.open(root.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            ok = clean_directory(fd)
        finally:
            os.close(fd)
        if ok:
            os.rmdir(root.name, dir_fd=parent)
        return ok


def cleanup_legacy():
    """Unlink only owned compatibility entries, never recurse or follow links."""
    ok = True
    try:
        with directory(LEGACY_DIRECTORY) as parent:
            for name in LEGACY_FILES:
                try:
                    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    require(info.st_uid == os.getuid())
                    require(stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode))
                    os.unlink(name, dir_fd=parent)
                except FileNotFoundError:
                    continue
                except (OSError, ValueError):
                    ok = False
    except (OSError, ValueError):
        ok = False
    return ok


def cleanup(root):
    try:
        private_ok = cleanup_private(root)
    except (OSError, ValueError):
        private_ok = False
    # Always attempt the fixed compatibility set, even after missing/unsafe root.
    return cleanup_legacy() and private_ok


def main():
    action = "ARGUMENTS"
    try:
        args = sys.argv[1:]
        require(args and args[0] in ("init", "prepare", "report", "retry-allowed", "cleanup"))
        action = args[0]
        root, public = roots()
        if action == "init":
            require(len(args) == 1)
            initialize(root, public)
            ok = True
        elif action == "prepare":
            require(len(args) == 2)
            prepare(root, args[1])
            ok = True
        elif action == "report":
            require(len(args) == 3)
            ok = report(root, public, args[1], args[2])
        elif action == "retry-allowed":
            require(len(args) == 1)
            ok = retry_allowed(root)
        else:
            require(len(args) == 1)
            ok = cleanup(root)
    except Exception:
        # Native/error/path strings are never part of the public contract.
        print(f"AGENTOPS_CI_DELIVERY=FAIL {action.upper()}")
        # Report exit 1 means a host-written negative summary; exit 2 means
        # publication itself failed and no existing path may be uploaded.
        return 2 if action == "report" else 1
    print(f"AGENTOPS_CI_DELIVERY={'PASS' if ok else 'FAIL'} {action.upper()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
