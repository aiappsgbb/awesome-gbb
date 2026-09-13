#!/usr/bin/env python3
"""Host-only encrypted transport for one redacted native Doctor log."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.parse import quote, quote_plus


def _load_sibling(filename, module_name):
    path = Path(__file__).resolve().with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(module_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = _load_sibling("agentops-ci-preflight.py", "agentops_ci_diagnostic_preflight")
report = _load_sibling("agentops-ci-report.py", "agentops_ci_diagnostic_report")

AGE_VERSION = b"v1.3.2"
AGE_HEADER = b"age-encryption.org/v1\n"
MAX_AGE_BYTES = 32 * 1024 * 1024
MAX_LOG_BYTES = report.LIMIT
MAX_CIPHERTEXT_BYTES = MAX_LOG_BYTES + 1024 * 1024
AGE_TIMEOUT_SECONDS = 30
REDACTED = "[REDACTED]"
NATIVE_PREFIXES = ("doctor", "error", "exception", "traceback", "unclassified")
ERROR_CODES = frozenset({
    "AGE_BINARY", "AGE_HASH", "AGE_PATH", "AGE_RECIPIENT", "AGE_TIMEOUT",
    "AGE_VERSION", "APPROVAL", "APPROVAL_MISMATCH", "ARGUMENTS",
    "CIPHERTEXT_INVALID", "CI_CONTEXT", "ENCRYPTION_FAILED",
    "ENCRYPTION_TIMEOUT", "INTERNAL_ERROR", "MISSING_ENV", "OUTPUT_EXISTS",
    "OUTPUT_UNSAFE", "PUBLICATION_FAILED", "SOURCE_ABSENT", "SOURCE_INVALID",
    "SOURCE_UNSAFE",
})
SECRET_ENV_NAMES = frozenset({
    "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON",
    "AGENTOPS_CI_APPLICATIONINSIGHTS_CONNECTION_STRING",
    "AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
    "APPLICATION_INSIGHTS_CONNECTION_STRING",
    "APPINSIGHTS_CONNECTION_STRING",
    "COPILOT_PROVIDER_BEARER_TOKEN",
    "COPILOT_GITHUB_TOKEN",
    "AZURE_CLIENT_SECRET",
    "AZURE_CLIENT_CERTIFICATE_PASSWORD",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_KEY",
    "AZURE_AI_API_KEY",
    "AZURE_AI_KEY",
    "AZURE_COGNITIVE_SERVICES_KEY",
    "FOUNDRY_API_KEY",
    "AOAI_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_API_KEY",
    "GH_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_TOKEN",
    "GITHUB_PAT",
    "COPILOT_TOKEN",
})
CONNECTION_SECRET_KEYS = frozenset({
    "instrumentationkey", "accountkey", "sharedaccesssignature",
    "sharedaccesskey", "accesskey", "apikey", "password",
})
MINIMAL_ENV = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


class DiagnosticError(Exception):
    pass


def fail(code):
    raise DiagnosticError(code)


def required_env(environ, name):
    value = environ.get(name)
    if not isinstance(value, str) or not value:
        fail("MISSING_ENV")
    return value


def _approval(root, environ, now):
    path = root / "owner-approval.json"
    try:
        raw_text = preflight.read_file(path, root)
        supplied = required_env(environ, "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON").encode("utf-8")
        raw = raw_text.encode("utf-8")
    except DiagnosticError:
        raise
    except Exception:
        fail("APPROVAL")
    if not hmac.compare_digest(raw, supplied):
        fail("APPROVAL_MISMATCH")
    try:
        record = preflight.parse_json(raw_text)
        preflight.validate_record(record, now)
    except Exception:
        fail("APPROVAL")
    if record.get("schema_version") != 2:
        fail("APPROVAL")
    try:
        preflight.validate_github_context(record, environ)
    except Exception:
        fail("CI_CONTEXT")
    return record, raw


def _confirm_approval(root, environ, record, raw, now):
    confirmed, confirmed_raw = _approval(root, environ, now)
    if confirmed != record or not hmac.compare_digest(confirmed_raw, raw):
        fail("APPROVAL_MISMATCH")


def _read_age_binary(path, root):
    try:
        with report.directory(path.parent, root) as parent:
            fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not (
                    stat.S_ISREG(info.st_mode)
                    and info.st_uid == os.getuid()
                    and info.st_nlink == 1
                    and stat.S_IMODE(info.st_mode) == 0o700
                ):
                    fail("AGE_BINARY")
                raw = stream.read(MAX_AGE_BYTES + 1)
                if len(raw) > MAX_AGE_BYTES:
                    fail("AGE_BINARY")
                return raw
    except DiagnosticError:
        raise
    except Exception:
        fail("AGE_BINARY")


@contextmanager
def _sealed_age(binary):
    fd = None
    try:
        try:
            if sys.platform != "linux":
                fail("AGE_BINARY")
            import fcntl

            required_os = ("memfd_create", "MFD_ALLOW_SEALING", "MFD_CLOEXEC")
            required_fcntl = (
                "F_ADD_SEALS",
                "F_GET_SEALS",
                "F_SEAL_WRITE",
                "F_SEAL_GROW",
                "F_SEAL_SHRINK",
                "F_SEAL_SEAL",
            )
            if not all(hasattr(os, name) for name in required_os) or not all(
                hasattr(fcntl, name) for name in required_fcntl
            ):
                fail("AGE_BINARY")
            fd = os.memfd_create(
                "agentops-age",
                os.MFD_ALLOW_SEALING | os.MFD_CLOEXEC,
            )
            remaining = memoryview(binary)
            while remaining:
                written = os.write(fd, remaining)
                if written <= 0:
                    fail("AGE_BINARY")
                remaining = remaining[written:]
            os.fchmod(fd, 0o700)
            seals = (
                fcntl.F_SEAL_WRITE
                | fcntl.F_SEAL_GROW
                | fcntl.F_SEAL_SHRINK
                | fcntl.F_SEAL_SEAL
            )
            fcntl.fcntl(fd, fcntl.F_ADD_SEALS, seals)
            if fcntl.fcntl(fd, fcntl.F_GET_SEALS) != seals:
                fail("AGE_BINARY")
        except DiagnosticError:
            raise
        except Exception:
            fail("AGE_BINARY")
        yield f"/proc/self/fd/{fd}", fd
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _run_age(
    run,
    executable,
    arguments,
    input_bytes=None,
    *,
    timeout_code="AGE_TIMEOUT",
    failure_code="AGE_BINARY",
):
    path, fd = executable
    try:
        return run(
            [path, *arguments],
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=AGE_TIMEOUT_SECONDS,
            check=False,
            env=dict(MINIMAL_ENV),
            pass_fds=(fd,),
        )
    except subprocess.TimeoutExpired:
        fail(timeout_code)
    except Exception:
        fail(failure_code)


def _verified_age_bytes(root, environ):
    expected_path = root / "tools" / "age"
    try:
        configured = preflight.absolute_path(required_env(environ, "AGENTOPS_CI_AGE_BIN"))
    except DiagnosticError:
        raise
    except Exception:
        fail("AGE_PATH")
    if configured != expected_path:
        fail("AGE_PATH")
    expected_hash = required_env(environ, "AGENTOPS_CI_AGE_SHA256")
    if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        fail("AGE_HASH")
    binary = _read_age_binary(configured, root)
    if not hmac.compare_digest(hashlib.sha256(binary).hexdigest(), expected_hash):
        fail("AGE_HASH")
    return binary


def _validate_age(executable, record, run):
    version = _run_age(run, executable, ["--version"])
    if version.returncode != 0 or version.stdout.strip() != AGE_VERSION:
        fail("AGE_VERSION")
    recipient = record["diagnostic"]["recipient"]
    probe = _run_age(run, executable, ["-r", recipient], b"")
    if (
        probe.returncode != 0
        or not probe.stdout.startswith(AGE_HEADER)
        or len(probe.stdout) > MAX_CIPHERTEXT_BYTES
    ):
        fail("AGE_RECIPIENT")


def _secret_variants(environ):
    values = set()
    connection_values = []
    for name in SECRET_ENV_NAMES:
        value = environ.get(name)
        if not isinstance(value, str) or not value:
            continue
        values.add(value)
        values.add(json.dumps(value, ensure_ascii=True)[1:-1])
        values.add(quote(value, safe=""))
        values.add(quote_plus(value, safe=""))
        if "CONNECTION_STRING" in name:
            connection_values.append(value)
    for connection_string in connection_values:
        for component in connection_string.split(";"):
            key, separator, value = component.partition("=")
            if separator and key.strip().lower() in CONNECTION_SECRET_KEYS and value:
                values.add(value)
                values.add(json.dumps(value, ensure_ascii=True)[1:-1])
                values.add(quote(value, safe=""))
                values.add(quote_plus(value, safe=""))
    return sorted((value for value in values if value), key=len, reverse=True)


def _sub(pattern, replacement, text):
    return re.subn(pattern, replacement, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)


def redact(text, environ):
    count = 0
    for secret in _secret_variants(environ):
        occurrences = text.count(secret)
        if occurrences:
            text = text.replace(secret, REDACTED)
            count += occurrences

    patterns = (
        (
            r"(-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----).*?"
            r"(-----END [A-Z0-9 ]*PRIVATE KEY-----)",
            REDACTED,
        ),
        (r"\bAGE-SECRET-KEY-1[0-9A-Z]+\b", REDACTED),
        (r"\bgithub_pat_[A-Za-z0-9_]{20,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b", REDACTED),
        (r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{3,}\b", REDACTED),
    )
    for pattern, replacement in patterns:
        text, replaced = _sub(pattern, replacement, text)
        count += replaced

    double_quoted_value = r'"(?:\\.|[^"\\\r\n])*"'
    single_quoted_value = r"'(?:\\.|[^'\\\r\n])*'"
    value = (
        rf"(?:{double_quoted_value}|{single_quoted_value}|"
        r"(?:Bearer|Basic)\s+[^\s,;}]+|[^\s,;}]+)"
    )
    prefix = (
        r"(\b(?:authorization|proxy-authorization|api[-_]?key|x-api-key)\b"
        r"\s*[\"']?\s*[:=]\s*)"
    )
    text, replaced = re.subn(prefix + value, rf"\1{REDACTED}", text, flags=re.IGNORECASE)
    count += replaced
    standalone_auth = r"(\b(?:Bearer|Basic)\s+)"
    text, replaced = re.subn(
        standalone_auth + r"[^\s,;}]+",
        rf"\1{REDACTED}",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    count += replaced
    delimited_fields = (
        r"(?<![A-Za-z0-9_-])((?:github[_-]?token|token|sas)\b"
        r"\s*[\"']?\s*[:=]\s*)"
    )
    text, replaced = re.subn(
        delimited_fields + value, rf"\1{REDACTED}", text, flags=re.IGNORECASE
    )
    count += replaced
    fields = (
        r"(\b(?:access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|password|"
        r"AccountKey|InstrumentationKey|SharedAccessKey|SharedAccessSignature)\b"
        r"\s*[\"']?\s*[:=]\s*)"
    )
    text, replaced = re.subn(fields + value, rf"\1{REDACTED}", text, flags=re.IGNORECASE)
    count += replaced
    text, replaced = re.subn(
        r"([?&]sig=)([^&#\s\"']+)", rf"\1{REDACTED}", text, flags=re.IGNORECASE
    )
    count += replaced
    return text, count


def _native_prefix(text):
    first = next((line.strip().lower() for line in text.splitlines() if line.strip()), "")
    if first.startswith("traceback"):
        return "traceback"
    if "exception" in first:
        return "exception"
    if first.startswith(("error", "fatal")):
        return "error"
    if first.startswith("doctor"):
        return "doctor"
    return "unclassified"


def _ensure_outputs_absent(public):
    try:
        with report.directory(public, public) as parent:
            for name in ("doctor-log.age", "diagnostic.json"):
                try:
                    os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                fail("OUTPUT_EXISTS")
    except DiagnosticError:
        raise
    except Exception:
        fail("OUTPUT_UNSAFE")


def _read_source(root):
    try:
        workspace = report.workspace_path(root, "primary")
        raw = report.read(workspace / ".agentops/agent/doctor-command.log", root)
    except report.DiagnosticFailure as exc:
        if exc.diagnostic.get("reason") == "absent":
            fail("SOURCE_ABSENT")
        fail("SOURCE_UNSAFE")
    except FileNotFoundError:
        fail("SOURCE_ABSENT")
    except Exception:
        fail("SOURCE_UNSAFE")
    if len(raw) > MAX_LOG_BYTES:
        fail("SOURCE_UNSAFE")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        fail("SOURCE_INVALID")
    if "\x00" in text:
        fail("SOURCE_INVALID")
    return text


def _encrypt(run, executable, recipient, plaintext):
    result = _run_age(
        run,
        executable,
        ["-r", recipient],
        plaintext,
        timeout_code="ENCRYPTION_TIMEOUT",
        failure_code="ENCRYPTION_FAILED",
    )
    if result.returncode != 0:
        fail("ENCRYPTION_FAILED")
    ciphertext = result.stdout
    if (
        not isinstance(ciphertext, bytes)
        or not ciphertext.startswith(AGE_HEADER)
        or len(ciphertext) > MAX_CIPHERTEXT_BYTES
    ):
        fail("CIPHERTEXT_INVALID")
    return ciphertext


def _remove_created(path, private, identity):
    try:
        with report.directory(path.parent, private) as parent:
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (current.st_dev, current.st_ino) == identity:
                os.unlink(path.name, dir_fd=parent)
    except Exception:
        pass


def _publish(public, ciphertext, metadata):
    items = (
        (public / "doctor-log.age", ciphertext),
        (
            public / "diagnostic.json",
            (json.dumps(metadata, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode(),
        ),
    )
    created = []
    try:
        for path, raw in items:
            with report.new_file(path, public) as stream:
                info = os.fstat(stream.fileno())
                created.append((path, (info.st_dev, info.st_ino)))
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        for path, identity in reversed(created):
            _remove_created(path, public, identity)
        fail("PUBLICATION_FAILED")


@contextmanager
def check_contract(environ, now, run):
    if environ.get("GITHUB_RUN_ATTEMPT") != "1":
        fail("CI_CONTEXT")
    root, public = report.roots()
    record, raw = _approval(root, environ, now)
    binary = _verified_age_bytes(root, environ)
    with _sealed_age(binary) as executable:
        _validate_age(executable, record, run)
        yield root, public, record, raw, executable


def export(environ, now, run):
    with check_contract(environ, now, run) as (
        root,
        public,
        record,
        approval_raw,
        executable,
    ):
        _ensure_outputs_absent(public)
        text = _read_source(root)
        redacted, redaction_count = redact(text, environ)
        ciphertext = _encrypt(
            run, executable, record["diagnostic"]["recipient"], redacted.encode("utf-8")
        )
        _confirm_approval(root, environ, record, approval_raw, now)
        metadata = {
            "schema_version": 1,
            "artifact": "doctor-log.age",
            "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
            "ciphertext_size": len(ciphertext),
            "redaction_count": redaction_count,
            "redaction_occurred": redaction_count > 0,
            "native_prefix": _native_prefix(redacted),
        }
        _publish(public, ciphertext, metadata)


def main(argv=None, *, environ=None, now=None, run=None):
    args = sys.argv[1:] if argv is None else argv
    action = args[0] if len(args) == 1 else "arguments"
    display_action = action.upper() if action in ("check", "export") else "ARGUMENTS"
    env = dict(os.environ if environ is None else environ)
    clock = datetime.now(timezone.utc) if now is None else now
    runner = subprocess.run if run is None else run
    try:
        if len(args) != 1 or action not in ("check", "export"):
            fail("ARGUMENTS")
        if action == "check":
            with check_contract(env, clock, runner):
                pass
        else:
            export(env, clock, runner)
    except DiagnosticError as exc:
        code = exc.args[0] if len(exc.args) == 1 and isinstance(exc.args[0], str) else "INTERNAL_ERROR"
        if code not in ERROR_CODES:
            code = "INTERNAL_ERROR"
        print(f"AGENTOPS_CI_DIAGNOSTIC=FAIL {display_action} {code}")
        return 1
    except Exception:
        print(f"AGENTOPS_CI_DIAGNOSTIC=FAIL {display_action} INTERNAL_ERROR")
        return 1
    print(f"AGENTOPS_CI_DIAGNOSTIC=PASS {display_action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
