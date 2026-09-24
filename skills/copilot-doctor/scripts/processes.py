"""Cleanup for probe-owned POSIX process groups, not configured/user processes."""

import os
import signal
import subprocess


def stop_group(pid, wait, grace=1):
    """Escalate even when the group leader exited but its children ignored TERM."""
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        wait(grace)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
