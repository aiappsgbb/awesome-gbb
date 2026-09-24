"""Opt-in, reviewed MCP probe. No automatic launcher selection or raw results.

Requires mcp~=1.27.1. A private plan binds one exact registered configuration to
one reviewed existing launcher and optionally one approved read-only tool call.
"""

import argparse
import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
import multiprocessing
import os
from pathlib import Path
import sqlite3
import sys
import time

from inventory import parse_json, read_text, label
from processes import stop_group
from contextlib import closing


@asynccontextmanager
async def owned_stdio(launch, env, cwd):
    """Keep the server in the worker's owned process group for deadline cleanup."""
    import anyio
    from mcp.types import JSONRPCMessage
    from mcp.shared.message import SessionMessage

    incoming, reads = anyio.create_memory_object_stream(1)
    writes, outgoing = anyio.create_memory_object_stream(1)
    process = await asyncio.create_subprocess_exec(
        launch["command"], *launch["args"], env=env, cwd=cwd,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, limit=2 * 1024 * 1024)

    async def receive():
        async with incoming:
            while line := await process.stdout.readline():
                await incoming.send(SessionMessage(JSONRPCMessage.model_validate_json(line)))

    async def send():
        async with outgoing:
            async for message in outgoing:
                data = message.message.model_dump_json(by_alias=True, exclude_none=True)
                process.stdin.write((data + "\n").encode())
                await process.stdin.drain()

    tasks = [asyncio.create_task(receive()), asyncio.create_task(send())]
    try:
        yield reads, writes
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        process.stdin.close()
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 1)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        await reads.aclose()
        await writes.aclose()


def fingerprint(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_plan(plan):
    if plan.get("approved_read_only") is not True:
        raise ValueError("explicit read-only approval required")
    timeout = plan.get("deadline_seconds", 30)
    if type(timeout) is not int or not 5 <= timeout <= 60:
        raise ValueError("deadline must be 5-60 seconds")
    config_path = Path(plan["config_path"]).expanduser()
    config = parse_json(read_text(config_path))["mcpServers"][plan["server"]]
    if not isinstance(config, dict):
        raise ValueError("invalid registration")
    if fingerprint(config) != plan.get("config_fingerprint"):
        raise ValueError("registered configuration changed since review")
    if config.get("disabled") is True:
        raise ValueError("disabled registration")
    policy = config.get("tools")
    if "tools" in config and (not isinstance(policy, list)
                              or any(not isinstance(t, str) or not t for t in policy)):
        raise ValueError("invalid registration allowlist")
    tool = plan.get("tool")
    if tool is not None:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise ValueError("invalid selected tool")
        if not isinstance(tool.get("arguments"), dict) or not isinstance(tool.get("expect"), dict):
            raise ValueError("tool requires arguments and expected response shape")
        if tool["expect"].get("kind") not in ("text-contains", "json-keys", "nonempty-text"):
            raise ValueError("unsupported expectation")
        if tool["expect"]["kind"] == "text-contains":
            value = tool["expect"].get("value")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("nonempty expected text required")
        if tool["expect"]["kind"] == "json-keys":
            keys = tool["expect"].get("keys")
            if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or not k for k in keys):
                raise ValueError("expected keys must be nonempty strings")
        if isinstance(policy, list) and "*" not in policy and tool["name"] not in policy:
            raise ValueError("selected tool not in registration allowlist")
    if "url" not in config:
        launch = plan.get("launcher")
        if not isinstance(launch, dict) or not isinstance(launch.get("args"), list):
            raise ValueError("reviewed launcher required; never execute config blindly")
        command = Path(launch.get("command", ""))
        if not command.is_absolute() or not command.is_file() or not os.access(command, os.X_OK):
            raise ValueError("launcher must be an existing absolute executable")
        if command.name.lower() in ("npx", "npx.cmd", "uvx", "npm", "pip", "pip3"):
            raise ValueError("package runners prohibited; select an existing cached executable")
        if any(not isinstance(a, str) for a in launch["args"]):
            raise ValueError("invalid launcher arguments")
    elif plan.get("launcher") is not None:
        raise ValueError("remote registration cannot have a launcher override")
    if plan.get("authentication") not in ("not-tested", "public", "credentialed"):
        raise ValueError("declare auth expectation; never infer from handshake")
    return config


def decoded_content(result):
    text = "\n".join(c.text for c in result.content if getattr(c, "type", None) == "text")
    try:
        return text, json.loads(text)
    except ValueError:
        return text, getattr(result, "structuredContent", None)


def check_result(result, expectation):
    if result.isError:
        return "tool-error"
    text, data = decoded_content(result)
    if isinstance(data, dict) and data.get("error"):
        return "tool-error"
    kind = expectation["kind"]
    if kind == "nonempty-text":
        return "response-received-unvalidated" if text.strip() else "unexpected-shape"
    if kind == "text-contains":
        return "pass" if expectation["value"].casefold() in text.casefold() else "unexpected-shape"
    return "pass" if isinstance(data, dict) and all(k in data for k in expectation["keys"]) else "unexpected-shape"


def response_shape(result):
    """Structural troubleshooting without persisting tool payloads."""
    text, data = decoded_content(result)
    if data is None:
        try:
            data = json.loads(text)
        except ValueError:
            return {"kind": "text", "nonempty": bool(text.strip()), "is_error": result.isError,
                    "recognized_markers": [marker for marker in (
                        "library id", "library-id", "unauthorized", "invalid api key",
                        "rate limit", "no libraries found", "could not", "failed")
                        if marker in text.casefold()]}
    known = {"results", "result", "memories", "data", "count", "next", "previous",
             "error", "message", "status", "code", "type", "properties"}
    return {"kind": type(data).__name__, "is_error": result.isError,
            "known_keys": sorted(k for k in data if k in known) if isinstance(data, dict) else []}


def schema_type(schema):
    allowed = ("string", "number", "integer", "boolean", "object", "array", "null")
    value = schema.get("type")
    if isinstance(value, str) and value in allowed:
        return value
    if isinstance(value, list) and value and all(isinstance(v, str) and v in allowed for v in value):
        return value
    return "unspecified"


def safe_error(exc):
    # Do not emit error text: SDK errors may contain URLs, tokens or tool content.
    if isinstance(exc, ImportError):
        return "missing-or-incompatible-dependency"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "timeout"
    nested = getattr(exc, "exceptions", ())
    if nested:
        codes = [safe_error(e) for e in nested]
        return next((c for c in codes if c in ("auth-required-or-denied", "timeout")), "transport-error")
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) in (401, 403):
        return "auth-required-or-denied"
    return "transport-or-protocol-error"


async def execute(plan, config, emit):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    result = {"server": label(plan["server"]), "registration": "matched-reviewed-config",
              "initialization": "not-tested", "tool_listing": "not-tested",
              "authentication": "not-tested", "useful_result": "not-tested",
              "scanned_at": datetime.now(timezone.utc).isoformat(),
              "deadline_seconds": plan.get("deadline_seconds", 30)}
    emit(result)
    async with AsyncExitStack() as stack:
        if "url" in config:
            if config.get("type", "http") not in ("http", "streamable-http", "remote"):
                raise ValueError("transport not supported by this bounded probe")
            streams = await stack.enter_async_context(streamablehttp_client(
                config["url"], headers=config.get("headers"), timeout=10,
                sse_read_timeout=20, terminate_on_close=True))
        else:
            launch = plan["launcher"]
            # No package resolution. Do not change the configured credential provider.
            env = dict(os.environ, **config.get("env", {}))
            env.update({"COPILOT_AUTO_UPDATE": "false", "npm_config_offline": "true"})
            streams = await stack.enter_async_context(owned_stdio(
                launch, env, launch.get("cwd", config.get("cwd"))))
        session = await stack.enter_async_context(ClientSession(
            streams[0], streams[1], read_timeout_seconds=timedelta(seconds=15)))
        await session.initialize()
        result["initialization"] = "pass"
        emit(result)
        tools = await session.list_tools()
        result["tool_listing"] = "pass"
        result["tool_count"] = len(tools.tools)
        result["tools"] = [{"name": label(t.name),
                            "required": [label(k) for k in t.inputSchema.get("required", [])],
                            "parameters": {label(k): schema_type(v)
                                           for k, v in t.inputSchema.get("properties", {}).items()
                                           if isinstance(v, dict)}}
                           for t in tools.tools]
        result["more_tools_available"] = tools.nextCursor is not None
        emit(result)
        if plan.get("tool"):
            spec = plan["tool"]
            if spec["name"] not in {t.name for t in tools.tools}:
                result["useful_result"] = "tool-not-in-first-page"
            else:
                response = await session.call_tool(spec["name"], spec["arguments"])
                result["useful_result"] = check_result(response, spec["expect"])
                result["response_shape"] = response_shape(response)
                if result["useful_result"] == "pass":
                    result["authentication"] = ("accepted-for-this-request" if plan["authentication"] == "credentialed"
                                                else "not-required" if plan["authentication"] == "public"
                                                else "not-tested")
            emit(result)
    result["cleanup"] = "transport-closed"
    emit(result)


def worker(plan, config, connection):
    if os.name == "posix":
        os.setsid()
    logging.disable(logging.CRITICAL)
    # Suppress library/startup messages, not just final exception formatting.
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
        try:
            asyncio.run(execute(plan, config, lambda result: connection.send(dict(result))))
        except Exception as exc:
            connection.send({"error": safe_error(exc)})
    connection.close()


def run_probe(plan):
    config = validate_plan(plan)
    if os.name != "posix":
        raise ValueError("bounded child-tree cleanup currently requires POSIX")
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(plan, config, child))
    result = {"server": label(plan["server"]), "registration": "matched-reviewed-config",
              "initialization": "not-tested", "authentication": "not-tested", "useful_result": "not-tested"}
    process.start()
    child.close()
    deadline = time.monotonic() + plan.get("deadline_seconds", 30)
    try:
        while time.monotonic() < deadline:
            if parent.poll(min(0.1, max(0, deadline - time.monotonic()))):
                try:
                    result.update(parent.recv())
                except EOFError:
                    break
            if not process.is_alive() and not parent.poll():
                break
        process.join(min(0.2, max(0, deadline - time.monotonic())))
        if process.is_alive() and time.monotonic() >= deadline:
            result["error"] = "deadline-exceeded"
        elif not process.is_alive() and "cleanup" not in result and "error" not in result:
            result["error"] = "worker-exited-incomplete"
        if result.get("error") == "auth-required-or-denied":
            result["authentication"] = "required-or-denied"
    finally:
        # Cleanup must also run on interruption or a broken result pipe.
        stop_group(process.pid, process.join)
        if process.is_alive():
            # Covers interruption before the spawned worker could call setsid().
            process.kill()
        process.join(1)
        result["worker_stopped"] = not process.is_alive()
        parent.close()
        process.close()
    return result


def save_result(path, plan, result):
    path = Path(path).expanduser()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and path.stat().st_mode & 0o077):
        raise ValueError("history must be private and not a symlink")
    fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    identity = json.dumps([str(Path(plan["config_path"]).expanduser().resolve()),
                           plan["server"], plan.get("launcher"), plan.get("tool")], sort_keys=True)
    scope = hashlib.sha256(identity.encode()).hexdigest()
    # Do not store config fingerprints, arguments, URLs, headers or returned content.
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS health_checks "
                   "(id INTEGER PRIMARY KEY, scope TEXT NOT NULL, checked_at TEXT NOT NULL, body TEXT NOT NULL)")
        previous = db.execute(
            "SELECT body FROM health_checks WHERE scope=? "
            "ORDER BY coalesce(json_extract(body,'$.scanned_at'),checked_at) DESC,id DESC LIMIT 1",
            (scope,)).fetchone()
        fields = ("registration", "initialization", "tool_listing", "authentication", "useful_result", "error")
        prior = json.loads(previous[0]) if previous else {}
        delta = [key for key in fields if prior.get(key) != result.get(key)] if previous else None
        db.execute("INSERT INTO health_checks(scope,checked_at,body) VALUES (?,?,?)",
                   (scope, result.get("scanned_at", datetime.now(timezone.utc).isoformat()),
                    json.dumps(result, sort_keys=True)))
    return {"status": "compared" if previous else "no-baseline", "changed_statuses": delta}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--state", type=Path, help="Optional same private doctor history used by inventory")
    args = parser.parse_args()
    try:
        plan = parse_json(read_text(args.plan))
        result = run_probe(plan)
        if args.state:
            result["history"] = save_result(args.state, plan, result)
    except (ValueError, KeyError, OSError, TypeError, ImportError, sqlite3.Error):
        print('{"error":"invalid-plan-or-missing-dependency","raw_details":"suppressed"}')
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if "error" in result or result.get("useful_result") in (
        "tool-error", "unexpected-shape", "tool-not-in-first-page") else 0


if __name__ == "__main__":
    sys.exit(main())
