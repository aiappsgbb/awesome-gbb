"""Opt-in bounded help/version check of one explicitly selected Copilot binary.

No configured command execution, model calls, MCP startup or raw output emission.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from processes import stop_group

TOPICS = ("root", "skill", "plugin", "mcp", "config")
TIMEOUT_SECONDS = 15


def run_check(command, env):
    if os.name != "posix":
        raise ValueError("bounded child-tree cleanup currently requires POSIX")
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, env=env, start_new_session=True) as process:
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT_SECONDS)
            return subprocess.CompletedProcess(command, process.returncode, stdout, "")
        finally:
            stop_group(process.pid, process.wait)
            process.wait(timeout=1)


def probe(binary, topic="root", flag=None):
    binary = Path(binary).expanduser()
    if not binary.is_absolute() or not binary.is_file():
        raise ValueError("select an existing absolute binary path")
    if topic not in TOPICS:
        raise ValueError("unsupported topic")
    if flag is not None and not re.fullmatch(r"--[a-z][a-z0-9-]*", flag):
        raise ValueError("flag must be a long option name")
    env = dict(os.environ, COPILOT_AUTO_UPDATE="false")
    result = {"topic": topic, "version": "not-tested", "help": "not-tested",
              "mcp_handshake": "not-tested", "authentication": "not-tested",
              "useful_tool": "not-tested"}
    checks = [("version", [str(binary), "--version"]),
              ("help", [str(binary), *([] if topic == "root" else [topic]), "--help"])]
    for name, command in checks:
        try:
            response = run_check(command, env)
        except subprocess.TimeoutExpired:
            result[name] = "timeout"
            break
        except (OSError, UnicodeError):
            result[name] = "execution-error"
            break
        if response.returncode:
            result[name] = f"exit-{response.returncode}"
            break
        if name == "version":
            match = re.search(r"GitHub Copilot CLI (\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?)", response.stdout)
            result[name] = match[1] if match else "unrecognized-output"
        else:
            result[name] = "ok" if response.stdout.strip() else "empty-output"
            if flag:
                result["flag"] = flag
                result["flag_status"] = "documented" if re.search(
                    rf"(?<![\w-]){re.escape(flag)}(?![\w-])", response.stdout) else "not-listed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--topic", choices=TOPICS, default="root")
    parser.add_argument("--flag")
    args = parser.parse_args()
    try:
        report = probe(args.binary, args.topic, args.flag)
    except ValueError:
        print("Invalid probe request; select an absolute binary and supported help topic/flag.", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["help"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
