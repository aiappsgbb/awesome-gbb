"""Read-only Copilot setup inventory; optional private, append-only scan history.

Never executes configured launchers or emits configuration values/content.
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys

try:
    import yaml
except ImportError:
    yaml = None

MAX_BYTES = 2 * 1024 * 1024
MAX_SKILLS = 2000
SCHEMA = 1


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def label(value):
    """Do not echo arbitrary config strings in metadata slots."""
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.@/:-]{1,160}", value):
        return value
    return "redacted-" + digest(str(value))[:12]


def parse_json(text):
    """Strip JSONC comments outside strings; reject duplicate object keys."""
    out = []
    i = 0
    quoted = False
    while i < len(text):
        c = text[i]
        if quoted:
            out.append(c)
            if c == "\\" and i + 1 < len(text):
                i += 1
                out.append(text[i])
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
            out.append(c)
        elif text[i:i + 2] == "//":
            end = text.find("\n", i + 2)
            i = len(text) if end == -1 else end
            out.append("\n")
            continue
        elif text[i:i + 2] == "/*":
            end = text.find("*/", i + 2)
            if end == -1:
                raise ValueError("unterminated comment")
            out.append(" ")
            i = end + 2
            continue
        else:
            out.append(c)
        i += 1

    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate key")
            obj[key] = value
        return obj

    return json.loads("".join(out), object_pairs_hook=unique)


def read_text(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("file size limit")
    return data.decode("utf-8-sig")


def inspect_server(name, config, source, *, home=None, search_path=None):
    result = {"name": label(name), "source": str(source), "signals": [],
              "handshake": "not-tested", "authentication": "not-tested",
              "useful_tool": "not-tested"}
    signals = result["signals"]
    if not isinstance(config, dict):
        signals.append("invalid-server-shape")
        return result
    result["enabled"] = config.get("disabled") is not True
    result["transport"] = "remote" if "url" in config else "stdio"
    declared_type = config.get("type", "unspecified")
    result["declared_type"] = declared_type if declared_type in (
        "local", "stdio", "http", "sse", "streamable-http", "remote", "unspecified") else "unknown"
    env = config.get("env", {})
    args = config.get("args", [])
    if not isinstance(env, dict) or not isinstance(args, list):
        signals.append("invalid-server-shape")
        return result
    result["env_names"] = sorted(label(k) for k in env)
    tools = config.get("tools")
    result["tools_policy"] = ("all" if tools == ["*"] else
                              "explicit" if isinstance(tools, list) else "unspecified")
    result["tools_count"] = len(tools) if isinstance(tools, list) else None
    result["tools_fingerprint"] = digest(json.dumps(tools, sort_keys=True))
    result["headers_present"] = bool(config.get("headers"))
    result["credential_provider"] = (
        "AzureCliCredential" if env.get("AZURE_TOKEN_CREDENTIALS") == "AzureCliCredential"
        else "configured" if "AZURE_TOKEN_CREDENTIALS" in env else "unspecified")
    result["isolated_browser"] = "--isolated" in args
    result["browser_mode"] = ("extension" if "--extension" in args else
                              "isolated" if "--isolated" in args else "unspecified")
    browser = next((args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--browser"), None)
    result["browser_target"] = browser if browser in ("chrome", "msedge", "chromium", "firefox", "webkit") else "unspecified"
    if result["transport"] == "remote":
        result["endpoint_configured"] = isinstance(config.get("url"), str) and bool(config["url"])
        if not result["endpoint_configured"]:
            signals.append("invalid-endpoint")
        return result
    command = config.get("command")
    if not isinstance(command, str) or not command:
        signals.append("missing-command")
        return result
    base = Path(command).name.lower()
    result["launcher"] = base if base in {
        "python", "python3", "python.exe", "node", "node.exe", "uv", "uvx",
        "npx", "npx.cmd", "npm", "docker", "dotnet", "bash", "sh"
    } else "custom"
    result["launcher_fingerprint"] = digest(command)
    result["launch_mode"] = ("module" if "-m" in args else
                             "dynamic" if base in {"uvx", "npx", "npx.cmd"} else "other")
    if "$" in command or "%" in command or command.startswith("~"):
        signals.append("launcher-expansion-unverified")
    elif os.path.isabs(command):
        if not Path(command).is_file():
            signals.append("missing-launcher")
        elif not os.access(command, os.X_OK):
            signals.append("launcher-not-executable")
    elif "/" in command or "\\" in command:
        signals.append("relative-launcher-unverified")
    elif shutil.which(command, path=search_path) is None:
        signals.append("launcher-not-on-auditor-path")
    if "PATH" in env:
        signals.append("server-path-override-unverified")
    dynamic = base in {"uv", "uv.exe"} and "run" in args and any(
        isinstance(a, str) and (a in {"--with", "--with-requirements", "--with-editable"}
                               or a.startswith(("--with=", "--with-requirements=", "--with-editable=")))
        for a in args)
    if dynamic and str(env.get("UV_OFFLINE", "")).lower() in {"1", "true", "yes"}:
        signals.append("offline-dynamic-resolution")
    cwd = config.get("cwd")
    if cwd is not None:
        if not isinstance(cwd, str) or not os.path.isabs(cwd):
            signals.append("working-directory-unverified")
        elif not Path(cwd).is_dir():
            signals.append("missing-working-directory")
    return result


def inspect_skill(path, source):
    result = {"path": str(path), "source": str(source), "name": label(path.parent.name),
              "signals": []}
    try:
        text = read_text(path)
        result["fingerprint"] = digest(text)
        if yaml is None:
            result["signals"].append("yaml-check-unavailable")
            return result
        match = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.S)
        if not match:
            raise ValueError("missing frontmatter")

        class UniqueLoader(yaml.SafeLoader):
            pass

        def mapping(loader, node):
            loader.flatten_mapping(node)
            result = {}
            for key, value in node.value:
                k = loader.construct_object(key)
                if k in result:
                    raise ValueError("duplicate YAML key")
                result[k] = loader.construct_object(value)
            return result

        UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        data = yaml.load(match[1], Loader=UniqueLoader)
        if not isinstance(data, dict) or not isinstance(data.get("name"), str):
            raise ValueError("invalid name")
        result["name"] = label(data["name"])
        description = data.get("description")
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
            result["signals"].append("invalid-description")
        else:
            result["description_fingerprint"] = digest(description)
            use = re.search(r"USE FOR:\s*(.*?)(?:DO NOT USE FOR:|$)", description, re.S | re.I)
            phrases = re.split(r"[,;]", use[1]) if use else []
            result["trigger_fingerprints"] = sorted({
                digest(" ".join(p.lower().split()).strip(" ."))
                for p in phrases if len(p.split()) >= 2
            })
        metadata = data.get("metadata", {})
        version = metadata.get("version") if isinstance(metadata, dict) else None
        result["version"] = version if isinstance(version, str) and re.fullmatch(
            r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", version) else "unspecified"
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        result["signals"].append("unreadable-skill" if isinstance(exc, OSError) else "invalid-frontmatter")
    except yaml.YAMLError if yaml else ValueError:
        result["signals"].append("invalid-frontmatter")
    return result


def collect_skills(roots):
    results, seen = [], set()
    for root, source in roots:
        root = Path(root)
        if not root.exists():
            continue
        candidates = [root / "SKILL.md"] if (root / "SKILL.md").is_file() else root.glob("*/SKILL.md")
        for path in sorted(candidates):
            real = path.resolve()
            if real in seen:
                continue
            if len(results) >= MAX_SKILLS:
                raise ValueError("skill count limit")
            seen.add(real)
            results.append(inspect_skill(path, source))
    return results


def inventory(home, project=None, extra_skill_roots=(), cli_paths=(), copilot_home=None):
    home = Path(home).resolve()
    copilot_home = Path(copilot_home).expanduser().resolve() if copilot_home else home / ".copilot"
    project = Path(project).resolve() if project else None
    report = {"schema": SCHEMA, "scanned_at": datetime.now(timezone.utc).isoformat(),
              "sources": [], "servers": [], "skills": [], "plugins": [],
              "instructions": [], "runtimes": [], "findings": [], "coverage": [
                  "No processes launched; MCP handshake/authentication/useful tools not tested.",
                  "App startup, bundled CLI, cache integrity and dependency imports not tested.",
                  "Instruction semantics, undocumented precedence and custom runtime sources require agent review.",
                  "No network/version freshness checks; outdated is not broken.",
                  "No credential stores, clipboard, history, transcripts, m-*.json or App databases read; config.json projected to plugin registrations.",
                  "Secret values, endpoint changes and arbitrary launch arguments are excluded from drift.",
                  "Enabled means a candidate from local settings, not proof of loading; managed policy and trust may override it.",
                  "Agent-scoped MCP, hooks, extensions, LSP and custom paths not explicitly supplied are not enumerated.",
              ]}

    def display(path):
        text = str(path)
        if text == str(home) or text.startswith(str(home) + os.sep):
            return "~" + text[len(str(home)):]
        return text

    def finding(code, source, impact="review", evidence=None):
        report["findings"].append({"code": code, "source": str(source), "impact": impact,
                                   "evidence": evidence or code})

    def load(path, required=False):
        src = display(path)
        try:
            data = parse_json(read_text(path))
            if not isinstance(data, dict):
                raise ValueError("object expected")
            report["sources"].append({"path": src, "status": "read"})
            return data
        except FileNotFoundError:
            report["sources"].append({"path": src, "status": "absent"})
            if required:
                finding("missing-registered-path", src, "broken")
        except (OSError, ValueError, UnicodeError, RecursionError):
            report["sources"].append({"path": src, "status": "unreadable-or-invalid"})
            finding("config-unreadable-or-invalid", src, "broken")
        return {}

    settings = load(copilot_home / "settings.json")
    config = load(copilot_home / "config.json")
    project_settings = load(project / ".github/copilot/settings.json") if project else {}
    roots = [(copilot_home / "skills", "personal:copilot"),
             (home / ".agents/skills", "personal:agents")]
    if project:
        roots.extend((project / folder, "project:" + folder) for folder in
                     (".github/skills", ".claude/skills", ".agents/skills"))
    roots.extend((Path(p).expanduser(), "explicit") for p in extra_skill_roots)
    disabled = project_settings.get("disabledSkills", settings.get("disabledSkills", []))
    if not isinstance(disabled, list) or any(not isinstance(x, str) for x in disabled):
        finding("unsupported-disabled-skills-shape", "settings.json")
        disabled = []

    def servers(data, source):
        mapping = data.get("mcpServers", {})
        if not isinstance(mapping, dict):
            finding("unsupported-mcp-shape", source, "broken")
            return
        for name, spec in sorted(mapping.items()):
            report["servers"].append(inspect_server(name, spec, source))

    servers(load(copilot_home / "mcp-config.json"), display(copilot_home / "mcp-config.json"))
    if project:
        for path in (project / ".mcp.json", project / ".github/mcp.json"):
            servers(load(path), display(path))
    registrations = config.get("installedPlugins", [])
    enabled = settings.get("enabledPlugins", {})
    if not isinstance(enabled, dict):
        finding("unsupported-plugin-enablement", "settings.json")
        enabled = {}
    project_enabled = project_settings.get("enabledPlugins", {})
    if isinstance(project_enabled, dict):
        enabled = {**enabled, **project_enabled}
    else:
        finding("unsupported-plugin-enablement", ".github/copilot/settings.json")
    report["configuration"] = {
        "copilot_home": display(copilot_home),
        "disabled_skills": sorted(label(x) for x in disabled),
        "enabled_plugins": {label(k): v if isinstance(v, bool) else "unknown" for k, v in enabled.items()},
        "auto_updates_channel": settings.get("autoUpdatesChannel") if settings.get("autoUpdatesChannel") in (
            "stable", "preview", "prerelease", "beta", "canary", "staff") else "unspecified-or-custom",
    }
    if not isinstance(registrations, list):
        finding("unsupported-plugin-registration", "config.json")
        registrations = []
    seen_plugins = set()
    for entry in registrations:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            finding("unsupported-plugin-registration", "config.json")
            continue
        name = entry["name"]
        market = entry.get("marketplace")
        key = name + ("@" + market if isinstance(market, str) and market else "")
        is_enabled = enabled.get(key, entry.get("enabled", True))
        item = {"name": label(key), "enabled": is_enabled, "signals": []}
        if not isinstance(is_enabled, bool):
            item["enabled"] = "unknown"
            item["signals"].append("unsupported-plugin-enablement")
        report["plugins"].append(item)
        seen_plugins.add(key)
        if item["enabled"] is not True:
            continue
        cache = entry.get("cache_path")
        if not isinstance(cache, str) or not cache:
            item["signals"].append("missing-plugin-cache-path")
            continue
        root = Path(cache).expanduser()
        if not root.is_absolute():
            item["signals"].append("relative-plugin-cache-unverified")
            continue
        item["source"] = display(root)
        candidates = [root / "plugin.json", root / ".github/plugin/plugin.json",
                      root / ".claude-plugin/plugin.json"]
        manifests = [p for p in candidates if p.is_file()]
        if not manifests:
            item["signals"].append("missing-plugin-manifest")
            continue
        if len(manifests) > 1:
            item["signals"].append("multiple-plugin-manifests")
            continue
        manifest = load(manifests[0], required=True)
        item["manifest"] = display(manifests[0])
        version = manifest.get("version")
        item["version"] = version if isinstance(version, str) and re.fullmatch(
            r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", version) else "unspecified"

        def component_path(value):
            if not isinstance(value, str):
                item["signals"].append("unsupported-plugin-component")
                return None
            candidate = (root / value).resolve()
            if not candidate.is_relative_to(root.resolve()):
                item["signals"].append("plugin-component-outside-root")
                return None
            return candidate

        portable = manifest.get("$schema") == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
        skill_spec = "skills" if portable else manifest.get("skills", "skills")
        for value in skill_spec if isinstance(skill_spec, list) else [skill_spec]:
            target = component_path(value)
            if target:
                if not target.exists() and "skills" in manifest:
                    item["signals"].append("missing-plugin-skill-path")
                roots.append((target, "plugin:" + label(key)))
        mcp_spec = "mcp.json" if portable and (root / "mcp.json").exists() else (
            None if portable else manifest.get("mcpServers"))
        if isinstance(mcp_spec, dict):
            servers({"mcpServers": mcp_spec}, display(manifests[0]))
        elif isinstance(mcp_spec, str):
            target = component_path(mcp_spec)
            if target:
                servers(load(target, required=True), display(target))
        elif mcp_spec is not None:
            item["signals"].append("unsupported-plugin-mcp-shape")
        elif not portable and (root / ".mcp.json").is_file():
            servers(load(root / ".mcp.json"), display(root / ".mcp.json"))
    for key, value in enabled.items():
        if value is True and key not in seen_plugins:
            finding("enabled-plugin-without-registration", "settings.json:" + label(key))

    try:
        report["skills"] = collect_skills(roots)
    except (OSError, ValueError, RuntimeError):
        finding("skill-collection-incomplete", "skill roots")
    for skill in report["skills"]:
        skill["path"] = display(Path(skill["path"]))
        skill["enabled"] = skill["name"] not in disabled and skill["path"] not in disabled
    active = [s for s in report["skills"] if s["enabled"]]
    for name, count in Counter(s["name"] for s in active).items():
        if count > 1:
            finding("duplicate-skill-name", name, evidence=f"{count} distinct enabled candidate files")
    for i, left in enumerate(active):
        for right in active[i + 1:]:
            if left["name"] == right["name"]:
                continue
            shared = set(left.get("trigger_fingerprints", [])) & set(right.get("trigger_fingerprints", []))
            if len(shared) >= 2 or (left.get("description_fingerprint") and
                                  left.get("description_fingerprint") == right.get("description_fingerprint")):
                finding("trigger-overlap-candidate", left["path"] + " | " + right["path"],
                        "informational", f"{len(shared)} identical multiword trigger phrases; not a routing verdict")
    for name, count in Counter(s["name"] for s in report["servers"] if s.get("enabled")).items():
        if count > 1:
            finding("duplicate-server-name", name, evidence=f"{count} declarations; precedence not inferred")

    instruction_paths = [copilot_home / "copilot-instructions.md"]
    instruction_paths.extend(sorted((copilot_home / "instructions").glob("*.instructions.md")))
    if project:
        instruction_paths.extend(project / p for p in (
            "AGENTS.md", ".github/copilot-instructions.md", "CLAUDE.md"))
        instruction_paths.extend(sorted((project / ".github/instructions").glob("*.instructions.md")))
    for path in instruction_paths:
        if not path.exists():
            continue
        try:
            text = read_text(path)
            report["instructions"].append({"source": display(path), "fingerprint": digest(text),
                                           "bytes": len(text.encode("utf-8"))})
        except (OSError, ValueError, UnicodeError):
            finding("instruction-unreadable", display(path))
    terminal = shutil.which("copilot")
    runtime_paths = ([("terminal-path", Path(terminal))] if terminal else [])
    runtime_paths.extend(("explicit-runtime", Path(p).expanduser()) for p in cli_paths)
    for origin, path in runtime_paths:
        report["runtimes"].append({"source": origin, "path": display(path),
                                   "exists": path.is_file(), "executable": os.access(path, os.X_OK),
                                   "version": "not-tested"})
    if not terminal:
        finding("terminal-cli-not-on-path", "auditor PATH", "informational")
    for collection in ("skills", "servers", "plugins"):
        for item in report[collection]:
            for signal in item["signals"]:
                impact = "broken" if signal in {
                    "missing-launcher", "launcher-not-executable", "missing-command",
                    "missing-working-directory", "invalid-server-shape", "invalid-endpoint",
                    "invalid-frontmatter", "invalid-description", "missing-plugin-manifest",
                    "missing-plugin-skill-path"
                } else "review"
                if item.get("enabled") is False:
                    impact = "informational"
                finding(signal, item.get("path", item.get("source", item["name"])), impact)
    report["findings"].sort(key=lambda f: (
        {"broken": 0, "review": 1, "informational": 2}[f["impact"]], f["source"], f["code"]))
    report["scope"] = digest(json.dumps([str(home), str(copilot_home), str(project), list(map(str, extra_skill_roots)),
                                        list(map(str, cli_paths))]))
    return report


def compare(previous, current):
    def entries(report):
        result = {"configuration": digest(json.dumps(report["configuration"], sort_keys=True))}
        for group in ("sources", "servers", "skills", "plugins", "instructions", "runtimes", "findings"):
            for item in report[group]:
                key = json.dumps([group, item.get("source"), item.get("path"), item.get("name"), item.get("code")])
                result[key] = digest(json.dumps(item, sort_keys=True))
        return result
    before, after = entries(previous), entries(current)
    return {"added": sorted(after.keys() - before.keys()),
            "removed": sorted(before.keys() - after.keys()),
            "changed": sorted(k for k in before.keys() & after.keys() if before[k] != after[k])}


def record_snapshot(path, report):
    path = Path(path).expanduser()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("history must not be a symlink")
    if path.exists() and path.stat().st_mode & 0o077:
        raise ValueError("history permissions must be owner-only")
    fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS snapshots "
                   "(id INTEGER PRIMARY KEY, scope TEXT NOT NULL, schema INTEGER NOT NULL, body TEXT NOT NULL)")
        previous = db.execute("SELECT body FROM snapshots WHERE scope=? AND schema=? ORDER BY id DESC LIMIT 1",
                              (report["scope"], SCHEMA)).fetchone()
        delta = compare(json.loads(previous[0]), report) if previous else None
        db.execute("INSERT INTO snapshots(scope,schema,body) VALUES (?,?,?)",
                   (report["scope"], SCHEMA, json.dumps(report, sort_keys=True)))
    return {"status": "compared" if previous else "no-baseline", "delta": delta}


ACCEPTABLE_FIELDS = ("browser_mode", "browser_target", "credential_provider", "tools_fingerprint", "launcher_fingerprint")


def apply_preferences(path, report, accept=()):
    """Accept only explicitly selected current structural facts, never defects."""
    path = Path(path).expanduser()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and path.stat().st_mode & 0o077):
        raise ValueError("history must be private and not a symlink")
    fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(fd)
    selections = []
    for selector in accept:
        name, separator, field = selector.partition(":")
        candidates = [s for s in report["servers"] if s["name"] == name and s.get("enabled")]
        if not separator or field not in ACCEPTABLE_FIELDS or len(candidates) != 1 or field not in candidates[0]:
            raise ValueError("accept requires a unique enabled server and supported structural field")
        selections.append((candidates[0], field))
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS preferences "
                   "(scope TEXT, source TEXT, name TEXT, field TEXT, value TEXT, accepted_at TEXT, "
                   "PRIMARY KEY(scope,source,name,field))")
        for server, field in selections:
            db.execute("INSERT OR REPLACE INTO preferences VALUES (?,?,?,?,?,?)",
                       (report["scope"], server["source"], server["name"], field,
                        json.dumps(server[field]), report["scanned_at"]))
        rows = db.execute("SELECT source,name,field,value FROM preferences WHERE scope=?",
                          (report["scope"],)).fetchall()
    by_server = {(s["source"], s["name"]): s for s in report["servers"]}
    for source, name, field, value in rows:
        server = by_server.get((source, name))
        if server is None:
            continue
        status = "accepted" if server.get(field) == json.loads(value) else "changed-from-accepted"
        server.setdefault("preferences", {})[field] = status
        if status == "changed-from-accepted":
            report["findings"].append({"code": status, "source": source + ":" + name,
                                       "impact": "review", "evidence": field + " differs; ask before restoring"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="Synthetic home or actual home")
    parser.add_argument("--project", type=Path, help="Explicit project root; no parent traversal")
    parser.add_argument("--copilot-home", type=Path, help="Configuration directory override (otherwise COPILOT_HOME)")
    parser.add_argument("--skill-root", action="append", default=[], help="Additional known custom skill root")
    parser.add_argument("--cli-path", action="append", default=[], help="Known App/bundled CLI path; stat only")
    parser.add_argument("--state", type=Path, help="Opt in to private doctor-only SQLite history")
    parser.add_argument("--accept", action="append", default=[], metavar="SERVER:FIELD",
                        help="Explicitly accept a current structural preference in --state; never repairs settings")
    args = parser.parse_args()
    try:
        report = inventory(args.home, args.project, args.skill_root, args.cli_path,
                           args.copilot_home or os.environ.get("COPILOT_HOME"))
        if args.accept and not args.state:
            raise ValueError("--accept requires --state")
        if args.state:
            apply_preferences(args.state, report, args.accept)
        report["history"] = record_snapshot(args.state, report) if args.state else {"status": "not-requested"}
    except (OSError, ValueError, sqlite3.Error, RuntimeError):
        print("Doctor failed: input, filesystem or history error; raw values suppressed.", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
