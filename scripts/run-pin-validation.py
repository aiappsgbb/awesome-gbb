#!/usr/bin/env python3
"""
Run validation.script for every changed pin file, assert expected_output
substrings appear in stdout. This is the CI gate that proves a freshness
PR actually validates against the new pin — no more "trust me, I tested".

Used by: .github/workflows/pin-validation.yml
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

import yaml

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
    )

REPO = Path(__file__).resolve().parent.parent
PIN_GLOB = "skills/*/references/upstream-pin.md"
SAFE_REQUIRES = {"github_only", "pypi"}
AZURE_REQUIRES = {"azure_subscription", "foundry_project"}
SCRIPT_TIMEOUT_SECONDS = 600
EXPECTED_TIMEOUT_PER_PIN_MIN = 10

# Env vars that must be set for --include-azure pins
AZURE_ENV_MAP = {
    "azure_subscription": "AZURE_SUBSCRIPTION_ID",
    "foundry_project": "AZURE_AI_ENDPOINT",
}


def parse_pin(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        print(f"::warning::{path} does not start with ---; skipping")
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        print(f"::warning::{path} is not a YAML-fronted markdown file; skipping")
        return None
    try:
        fm = yaml.safe_load(parts[1])
    except Exception as e:
        print(f"::error::{path} YAML parse failed: {e}")
        return None
    if not isinstance(fm, dict):
        return None
    return fm


def changed_pin_files(base: str) -> list[Path]:
    """git diff --name-only base...HEAD -- skills/*/references/upstream-pin.md"""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD", "--", PIN_GLOB],
            cwd=REPO,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"::error::git diff failed: {e}")
        sys.exit(1)
    files = [REPO / line.strip() for line in out.splitlines() if line.strip()]
    files = [f for f in files if f.exists()]
    return files


def all_pin_files() -> list[Path]:
    return sorted(REPO.glob(PIN_GLOB))


def should_run(pin: dict, path: Path, *, include_azure: bool = False) -> tuple[bool, str]:
    """
    Decide whether this pin's validation.script is safe + intended to run
    in CI. Returns (should_run, reason).

    With include_azure=True, also run pins that need Azure/Foundry creds
    (azure_subscription, foundry_project) when the required env vars are set.
    """
    validation = pin.get("validation") or {}
    requires = validation.get("requires") or []
    runnable = validation.get("runnable", False)
    script = validation.get("script", "").strip()
    automation_tier = pin.get("automation_tier", "issue_only")

    if not script:
        return False, "no validation.script"
    if not isinstance(requires, list):
        return False, f"validation.requires is not a list ({type(requires).__name__})"

    has_azure_needs = bool(AZURE_REQUIRES & set(requires))

    if include_azure and has_azure_needs:
        # Azure E2E mode: bypass runnable/automation_tier checks for pins
        # that need Azure creds, but verify the env vars are actually set.
        missing_env = []
        for req in requires:
            env_var = AZURE_ENV_MAP.get(req)
            if env_var and not os.environ.get(env_var):
                missing_env.append(f"{env_var} (for {req})")
        if missing_env:
            return False, f"--include-azure but missing env vars: {missing_env}"
        # Non-Azure requires must still be in the safe set
        non_azure = [r for r in requires if r not in AZURE_REQUIRES and r not in SAFE_REQUIRES]
        if non_azure:
            return False, f"validation.requires has unsafe non-Azure entries: {non_azure}"
        return True, ""

    # Standard logic for non-Azure pins
    if not runnable:
        return False, "validation.runnable is false"
    if automation_tier != "auto":
        return False, f"automation_tier={automation_tier} (not auto)"
    extra = [r for r in requires if r not in SAFE_REQUIRES]
    if extra:
        return False, f"validation.requires has unsafe entries: {extra}"
    return True, ""


def _find_best_python() -> str:
    """
    Find the newest python3.X (>=3.10) available on PATH, falling back to
    `python3` and finally `python` if nothing better exists.

    The pin scripts target SDKs that require Python >=3.10 (e.g.
    agent-framework). On macOS the system `python3` is 3.9 (too old), but
    homebrew installs versioned binaries like `python3.13`. CI runners
    using actions/setup-python expose both `python3.12` and `python3` →
    either resolves correctly.
    """
    for ver in ("3.13", "3.12", "3.11", "3.10"):
        found = shutil.which(f"python{ver}")
        if found:
            return found
    fallback = shutil.which("python3") or shutil.which("python")
    if fallback:
        return fallback
    raise RuntimeError("no python3 binary found on PATH")


def _ensure_python_pip_shims(tmp: Path) -> Path:
    """
    Create a `bin/` dir with cross-platform `python` and `pip` shims that
    point at the best python3 binary. Returns the dir path so the caller
    can prepend it to PATH.

    Why: the pin scripts use bare `python` and `pip` (works on CI runners
    that install both via actions/setup-python). On macOS and minimal Linux
    only `python3` (or `python3.13`) exists. Aliasing in a shim dir keeps
    the pin scripts portable without touching every file.
    """
    python3 = _find_best_python()

    bin_dir = tmp / "_shims"
    bin_dir.mkdir()

    py_shim = bin_dir / "python"
    py_shim.write_text(f'#!/usr/bin/env bash\nexec "{python3}" "$@"\n', encoding="utf-8")
    py_shim.chmod(0o755)

    pip_shim = bin_dir / "pip"
    pip_shim.write_text(
        f'#!/usr/bin/env bash\nexec "{python3}" -m pip "$@"\n', encoding="utf-8"
    )
    pip_shim.chmod(0o755)

    return bin_dir


def run_one(path: Path, pin: dict) -> tuple[bool, str]:
    """
    Execute the pin's validation.script in a fresh temp dir. Capture
    combined stdout+stderr. Verify every string in expected_output is
    a substring of the captured output. Return (ok, message).
    """
    validation = pin["validation"]
    script = validation["script"]
    expected = validation.get("expected_output") or []
    failure_sigs = validation.get("failure_signatures") or []

    skill = path.parent.parent.name
    print(f"\n::group::Running validation for {skill}")
    print(f"  script preview (first 300 chars):")
    for line in script[:300].splitlines():
        print(f"    | {line}")
    print(f"  expected_output: {expected}")
    print(f"  failure_signatures: {failure_sigs}")

    with tempfile.TemporaryDirectory(prefix=f"pin-{skill}-") as tmp:
        tmp_path = Path(tmp)
        script_path = tmp_path / "validate.sh"
        script_path.write_text(script, encoding="utf-8")
        script_path.chmod(0o755)

        env = os.environ.copy()
        env.setdefault("PYTHONUTF8", "1")

        # Forward Azure CI env vars so validation scripts can authenticate
        for env_var in AZURE_ENV_MAP.values():
            val = os.environ.get(env_var)
            if val:
                env[env_var] = val
        # Also forward AZURE_CLIENT_ID + AZURE_TENANT_ID for OIDC/DefaultAzureCredential
        for extra_var in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID",
                          "AZURE_SUBSCRIPTION_ID", "AZURE_AI_ENDPOINT"):
            val = os.environ.get(extra_var)
            if val:
                env[extra_var] = val

        # Cross-platform python/pip shims so pin scripts that use bare
        # `python`/`pip` work on macOS (where only python3 exists) without
        # changing the script itself.
        try:
            shim_dir = _ensure_python_pip_shims(tmp_path)
            env["PATH"] = f"{shim_dir}{os.pathsep}{env.get('PATH', '')}"
        except RuntimeError as e:
            print("::endgroup::")
            return False, str(e)

        try:
            proc = subprocess.run(
                ["bash", str(script_path)],
                cwd=tmp,
                env=env,
                capture_output=True,
                text=True,
                timeout=SCRIPT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            print("::endgroup::")
            return False, f"validation.script timed out after {SCRIPT_TIMEOUT_SECONDS}s"

        combined = (proc.stdout or "") + (proc.stderr or "")
        # Print last 2KB so PR reviewers can see what happened
        tail = combined[-2048:]
        print("  --- script output (last 2KB) ---")
        for line in tail.splitlines():
            print(f"    | {line}")
        print("  --- end output ---")

        if proc.returncode != 0:
            print("::endgroup::")
            return False, (
                f"validation.script exited with code {proc.returncode}. "
                "See script output above."
            )

        missing = [s for s in expected if s not in combined]
        if missing:
            print("::endgroup::")
            return False, (
                f"expected_output substrings not found in script output: {missing}"
            )

        for sig in failure_sigs:
            if sig in combined:
                print("::endgroup::")
                return False, f"failure_signature detected in output: {sig!r}"

        print("::endgroup::")
        return True, "OK"


def main(argv: list[str]) -> int:
    args = {a.split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "")
            for a in argv[1:]}
    base = args.get("--base", "origin/main")
    all_files_mode = "--all" in argv
    include_azure = "--include-azure" in argv
    skip_install_check = "--skip-install" in argv

    if all_files_mode:
        pins = all_pin_files()
        print(f"Mode: --all ({len(pins)} pin files)")
    else:
        pins = changed_pin_files(base)
        print(f"Mode: changed-only against base={base} ({len(pins)} pin files)")

    if include_azure:
        present = {k: bool(os.environ.get(v)) for k, v in AZURE_ENV_MAP.items()}
        print(f"Azure E2E mode: --include-azure (env: {present})")

    if not pins:
        print("\nNo pin files to validate. ✅")
        return 0

    # Sanity check that bash exists and at least one python3 is on PATH.
    # `pip` is invoked via `python3 -m pip` through the shim, so we don't
    # require a standalone `pip` binary. We use _find_best_python to allow
    # python3.13/3.12/etc fallback for SDKs that need >=3.10.
    if not skip_install_check:
        if shutil.which("bash") is None:
            print("::error::required tool 'bash' not on PATH")
            return 2
        try:
            chosen = _find_best_python()
            print(f"::notice::using python interpreter: {chosen}")
        except RuntimeError as e:
            print(f"::error::{e}")
            return 2

    failures: list[tuple[Path, str]] = []
    skipped: list[tuple[Path, str]] = []

    for path in pins:
        rel = path.relative_to(REPO)
        pin = parse_pin(path)
        if pin is None:
            failures.append((path, "parse failed"))
            continue
        ok, reason = should_run(pin, path, include_azure=include_azure)
        if not ok:
            print(f"\n[SKIP] {rel}: {reason}")
            skipped.append((path, reason))
            continue
        success, msg = run_one(path, pin)
        if success:
            print(f"\n[OK]   {rel}: {msg}")
        else:
            print(f"\n[FAIL] {rel}: {msg}")
            failures.append((path, msg))

    print("\n" + "=" * 60)
    print(
        f"Pin validation summary: "
        f"{len(pins) - len(failures) - len(skipped)} passed, "
        f"{len(failures)} failed, "
        f"{len(skipped)} skipped"
    )
    if skipped:
        print("\nSkipped (not eligible for CI auto-validation):")
        for p, reason in skipped:
            print(f"  - {p.relative_to(REPO)}: {reason}")
    if failures:
        print("\nFailures:")
        for p, msg in failures:
            print(f"  - {p.relative_to(REPO)}: {msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
