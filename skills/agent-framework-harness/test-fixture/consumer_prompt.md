# Agent Framework Harness live Foundry smoke

This is an execution smoke, not a repository review or repair task.
The workflow has installed the pinned Python runtime inside the approved
workspace and authenticated its private Azure CLI profile before starting you.
Do not install packages, create environments, read credential files, request
identity tokens, change permissions, or repair the environment.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You are already the running Copilot CLI process. The workflow captures your
output and checks the unchanged checkout.

## Execute the canonical probe once

Your first and only execution action is this exact command from the repository
root. Do not substitute an interpreter, set `PYTHONPATH`/`PYTHONHOME`, add
arguments, redefine helpers inline, or replace the credential.

```bash
.scratch/agent-framework-harness-venv/bin/python skills/agent-framework-harness/test-fixture/live_smoke.py
```

The canonical probe validates the runtime and runner profile, imports the
checked-in hosted/session helpers, makes one Harness invocation against the
standing CI model, and writes sanitized evidence plus the deterministic result.
It creates no Azure resources or role assignments and starts no server.

If the command is denied or fails, stop and report that exact failure.
Do not try another executable path, token adapter, package version or login.
Do not write or overwrite either the result marker or evidence yourself.
Only the canonical probe may declare success after its actual live assertions.

## Result contract

Success requires command exit zero, `HARNESS_LIVE_RESPONSE_OK` in its output,
and the probe-written `/tmp/agent-framework-harness-smoke-result` containing
exactly the unadorned success marker. Missing or failed evidence is not success.
The result file is authoritative; assistant prose is not evidence of execution.
