"""Credential-free, immutable-candidate runner proof. Never invoke a producer."""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


CASES = (
    "preserve", "workspace_only", "root_cleanup", "root_cleanup_then_init",
    "primary_and_workspace", "env_redirect_only", "missing_ack",
    "native_timeout", "signal", "cohort_mismatch",
)
REPOSITORY = "aiappsgbb/awesome-gbb"
HARNESS = "_agentops_custody_validation.py"
DIAGNOSTIC_FILES = {
    "validate.py", HARNESS, "agentops-ci-isolation.py",
    "agentops-ci-custody.py", "agentops-ci-report.py",
}
DOCKER_COMMANDS = (
    ("image", "inspect"), ("image", "ls"), ("image", "rm"),
    ("container", "ls"), ("build",), ("create",), ("inspect",),
    ("start",), ("stop",), ("rm",),
)
FAILURE_CLASSES = (
    (b"invalid mount config", "INVALID_MOUNT"),
    (b"bind source path does not exist", "MISSING_MOUNT_SOURCE"),
    (b"permission denied", "PERMISSION_DENIED"),
    (b"cannot connect to the docker daemon", "DOCKER_UNAVAILABLE"),
    (b"executable file not found", "EXECUTABLE_NOT_FOUND"),
    (b"no such file or directory", "PATH_NOT_FOUND"),
)
SONAME = r"lib[A-Za-z0-9_.+-]{1,96}\.so(?:\.[A-Za-z0-9_.+-]{1,32})?"
MODULE = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
RUNTIME_PREFIXES = (
    "/usr/bin", "/usr/lib", "/usr/lib64", "/usr/local/bin", "/usr/local/lib",
    "/bin", "/lib", "/lib64",
)
STATIC_INSPECTOR = r'''package main

import (
    "debug/elf"
    "encoding/json"
    "errors"
    "io"
    "os"
    "path/filepath"
    "strings"
    "syscall"
)

var prefixes []string

func permitted(path string, ancestor bool) bool {
    if !filepath.IsAbs(path) { return false }
    path = filepath.Clean(path)
    for _, prefix := range prefixes {
        if path == prefix || strings.HasPrefix(path, prefix + "/") { return true }
        if ancestor && (path == "/" || strings.HasPrefix(prefix, path + "/")) { return true }
    }
    return false
}

func record(class, path string) {
    value := map[string]string{"classification": class}
    if class == "MISSING" && permitted(path, false) { value["path"] = path }
    raw, _ := json.Marshal(value)
    os.Stdout.Write(append(append([]byte("AGENTOPS_STATIC_PATH="), raw...), '\n'))
}

func pathFailure(err error, path string) {
    if errors.Is(err, os.ErrNotExist) { record("MISSING", path) } else {
        record("UNREADABLE_OR_UNEXECUTABLE", "")
    }
}

func resolveExact(path string) (string, bool) {
    if !permitted(path, false) { record("OUTSIDE_SCOPE", ""); return "", false }
    pending := strings.Split(strings.TrimPrefix(filepath.Clean(path), "/"), "/")
    current, links := "/", 0
    for len(pending) > 0 {
        current = filepath.Join(current, pending[0])
        pending = pending[1:]
        if !permitted(current, true) { record("OUTSIDE_SCOPE", ""); return "", false }
        info, err := os.Lstat(current)
        if err != nil { pathFailure(err, current); return "", false }
        if info.Mode() & os.ModeSymlink != 0 {
            links++
            if links > 40 { record("SYMLINK_LIMIT", ""); return "", false }
            target, err := os.Readlink(current)
            if err != nil { pathFailure(err, current); return "", false }
            if !filepath.IsAbs(target) { target = filepath.Join(filepath.Dir(current), target) }
            target = filepath.Clean(target)
            if !permitted(target, true) { record("OUTSIDE_SCOPE", ""); return "", false }
            pending = append(strings.Split(strings.TrimPrefix(target, "/"), "/"), pending...)
            current = "/"
        }
    }
    return current, true
}

func readableExecutable(path string) bool {
    resolved, ok := resolveExact(path)
    if !ok { return false }
    info, err := os.Stat(resolved)
    if err != nil { pathFailure(err, resolved); return false }
    if !info.Mode().IsRegular() { record("NOT_REGULAR", ""); return false }
    file, err := os.Open(resolved)
    if err != nil { pathFailure(err, resolved); return false }
    file.Close()
    if err := syscall.Access(resolved, 1); err != nil {
        pathFailure(err, resolved); return false
    }
    return true
}

func interpreter(binary string) (string, bool) {
    file, err := elf.Open(binary)
    if err != nil { record("ELF_UNAVAILABLE", ""); return "", false }
    defer file.Close()
    for _, program := range file.Progs {
        if program.Type == elf.PT_INTERP {
            raw, err := io.ReadAll(io.LimitReader(program.Open(), 1025))
            if err != nil || len(raw) == 0 || len(raw) > 1024 {
                record("ELF_UNAVAILABLE", ""); return "", false
            }
            value := strings.TrimRight(string(raw), "\x00")
            if !permitted(value, false) { record("OUTSIDE_SCOPE", ""); return "", false }
            return value, true
        }
    }
    record("NO_ELF_INTERPRETER", "")
    return "", false
}

func main() {
    if len(os.Args) < 3 || json.Unmarshal([]byte(os.Args[1]), &prefixes) != nil {
        record("INVALID_INPUT", ""); os.Exit(125)
    }
    for _, prefix := range prefixes {
        if !filepath.IsAbs(prefix) || filepath.Clean(prefix) != prefix || prefix == "/" {
            record("INVALID_INPUT", ""); os.Exit(125)
        }
    }
    binary := os.Args[2]
    if !permitted(binary, false) { record("OUTSIDE_SCOPE", ""); os.Exit(125) }
    record("STARTED", "")
    readableExecutable(binary)
    if _, ok := resolveExact(binary); ok {
        if loader, ok := interpreter(binary); ok { readableExecutable(loader) }
    }
    // Replace the inspector with the unchanged checked Python command.
    // Successful inspector startup must never turn a failing Python into PASS.
    err := syscall.Exec(binary, os.Args[2:], os.Environ())
    if errors.Is(err, os.ErrNotExist) { record("EXEC_ENOENT", ""); os.Exit(127) }
    if errors.Is(err, os.ErrPermission) { record("EXEC_PERMISSION", ""); os.Exit(126) }
    record("EXEC_UNKNOWN", "")
    os.Exit(125)
}
'''


def require(value):
    if not value:
        raise ValueError("inert validation contract")


def emit(check, status):
    print(json.dumps({"check": check, "status": status}, sort_keys=True), flush=True)


def command_label(args):
    if not isinstance(args, (tuple, list)) or not args or not isinstance(args[0], str):
        return None
    name = Path(args[0]).name
    if name == "docker":
        for prefix in DOCKER_COMMANDS:
            if tuple(args[1:1 + len(prefix)]) == prefix:
                return "docker " + " ".join(prefix)
    if name in ("node", "copilot", "uv") and list(args[1:]) == ["--version"]:
        return name + " --version"
    if name in ("az", "azd") and list(args[1:]) == ["version"]:
        return name + " version"
    if re.fullmatch(r"python3(?:\.\d+)?", name) and list(args[1:]) == ["--version"]:
        return "python3 --version"
    return None


def diagnostic_error(failure, phase):
    known = (
        AssertionError, ValueError, KeyError, TypeError, RuntimeError,
        OSError, FileNotFoundError, PermissionError, TimeoutError,
        subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError,
    )
    record = {"check": "exception", "phase": phase,
              "type": type(failure).__name__ if type(failure) in known else "OtherException"}
    frames = []
    frame = failure.__traceback__
    while frame is not None:
        name = Path(frame.tb_frame.f_code.co_filename).name
        if name in DIAGNOSTIC_FILES:
            frames.append({"file": name, "line": frame.tb_lineno})
        frame = frame.tb_next
    record["frames"] = frames[-12:]
    if isinstance(failure, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
        label = command_label(failure.cmd)
        if label:
            record["command"] = label
            if isinstance(failure, subprocess.CalledProcessError):
                record["returncode"] = failure.returncode
            if label.startswith("docker "):
                stderr = failure.stderr
                if isinstance(stderr, str):
                    stderr = stderr[:16384].encode()
                if isinstance(stderr, bytes):
                    bounded = stderr[:16384].lower()
                    record["classification"] = next(
                        (value for token, value in FAILURE_CLASSES if token in bounded),
                        "UNCLASSIFIED",
                    )
    print(json.dumps(record, sort_keys=True), flush=True)


@contextlib.contextmanager
def diagnostic_phase(name):
    emit(name, "START")
    try:
        yield
    except Exception as failure:
        diagnostic_error(failure, name)
        raise
    else:
        emit(name, "PASS")


def traced(name, function):
    def invoke(*args, **kwargs):
        with diagnostic_phase(name):
            return function(*args, **kwargs)
    return invoke


def startup_classification(raw):
    text = raw[:65536].decode("utf-8", errors="replace")
    record = {"check": "startup", "classification": "UNKNOWN"}
    loader = re.search(r"error while loading shared libraries:\s*(" + SONAME + r"):", text)
    module = re.search(r"ModuleNotFoundError: No module named '(" + MODULE + r")'", text)
    imported = re.search(r"ImportError: cannot import name '[^'\n]+' from '(" + MODULE + r")'", text)
    if loader:
        record.update(classification="DYNAMIC_LOADER", soname=loader[1])
    elif module or imported:
        name = (module or imported)[1]
        record.update(classification="PYTHON_MODULE_IMPORT")
        if len(name) <= 128:
            record["module"] = name
    elif re.search(r"(?:exec|execve)[^\n]{0,512}(?:no such file or directory|executable file not found)",
                   text, flags=re.IGNORECASE):
        record["classification"] = "EXECUTABLE_OR_LOADER_ENOENT"
    return record


def runtime_prefixes(binary):
    selected = Path(binary)
    prefixes = list(RUNTIME_PREFIXES)
    if selected.is_relative_to("/opt") and len(selected.parts) >= 5 and selected.parent.name == "bin":
        prefixes.append(str(selected.parent.parent))
    return prefixes


def safe_runtime_path(value, prefixes):
    if not isinstance(value, str) or len(value) > 512:
        return False
    if not re.fullmatch(r"/[A-Za-z0-9_./+-]+", value) or "//" in value:
        return False
    path = Path(value)
    return str(path) == value and ".." not in path.parts and any(
        path.is_relative_to(prefix) for prefix in prefixes)


def static_path_diagnostics(raw, binary):
    prefixes = runtime_prefixes(binary)
    classes = {
        "MISSING", "UNREADABLE_OR_UNEXECUTABLE", "OUTSIDE_SCOPE", "SYMLINK_LIMIT",
        "NOT_REGULAR", "ELF_UNAVAILABLE", "NO_ELF_INTERPRETER", "INVALID_INPUT",
        "STARTED", "EXEC_ENOENT", "EXEC_PERMISSION", "EXEC_UNKNOWN",
    }
    records = []
    for line in raw[:65536].splitlines():
        if not line.startswith(b"AGENTOPS_STATIC_PATH=") or len(line) > 1024:
            continue
        try:
            value = json.loads(line[len(b"AGENTOPS_STATIC_PATH="):])
        except (ValueError, UnicodeError):
            continue
        if (not isinstance(value, dict) or not isinstance(value.get("classification"), str)
                or value["classification"] not in classes):
            continue
        record = {"check": "container_path", "classification": value["classification"]}
        if value["classification"] == "MISSING":
            if not safe_runtime_path(value.get("path"), prefixes):
                continue
            record["path"] = value["path"]
        if record not in records:
            records.append(record)
        if len(records) >= 16:
            break
    # An init/exec failure can precede even the statically linked inspector.
    text = raw[:65536].decode("utf-8", errors="replace")
    for match in re.finditer(
            r"\bexec(?:ve)? [\"']?(/[A-Za-z0-9_./+-]+)[\"']?(?: failed)?: "
            r"[Nn]o such file or directory", text):
        if safe_runtime_path(match[1], prefixes):
            records.append({"check": "startup_exec_path", "classification": "EXEC_ENOENT",
                            "path": match[1]})
            break
    return records or [{"check": "container_path", "classification": "UNKNOWN"}]


def verify_static_elf(binary):
    with binary.open("rb") as stream:
        header = stream.read(64)
        require(header[:6] == b"\x7fELF\x02\x01")
        offset = struct.unpack_from("<Q", header, 32)[0]
        size, count = struct.unpack_from("<HH", header, 54)
        require(size >= 4 and 0 < count <= 64)
        for index in range(count):
            stream.seek(offset + index * size)
            kind = struct.unpack("<I", stream.read(4))[0]
            require(kind not in (2, 3))  # No PT_DYNAMIC or PT_INTERP.


def build_static_inspector(work):
    compiler = shutil.which("go")
    require(compiler is not None)
    build = work / "static-inspector"
    build.mkdir(mode=0o700)
    source, binary = build / "main.go", build / "inspector"
    source.write_text(STATIC_INSPECTOR)
    home, cache, temporary = build / "home", build / "cache", build / "tmp"
    for directory in (home, cache, temporary):
        directory.mkdir(mode=0o700)
    env = {
        "PATH": os.environ["PATH"], "HOME": str(home), "GOCACHE": str(cache),
        "TMPDIR": str(temporary), "CGO_ENABLED": "0", "GOOS": "linux",
        "GOTOOLCHAIN": "local", "GOPROXY": "off", "GOSUMDB": "off",
        "GOENV": "off", "GOWORK": "off", "GO111MODULE": "off",
        "GOTELEMETRY": "off",
    }
    subprocess.run([compiler, "build", "-trimpath", "-buildvcs=false",
                    "-ldflags=-buildid=", "-o", str(binary), str(source)],
                   cwd=build, env=env, check=True, capture_output=True, timeout=120)
    verify_static_elf(binary)
    binary.chmod(0o500)
    print(json.dumps({"check": "static_inspector_build", "status": "PASS",
                      "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
                     sort_keys=True), flush=True)
    return binary


def inspector_arguments(args, image, command, inspector, mount):
    require(command and args[-len(command):] == command)
    index = args.index(image)
    require(index + 1 == len(args) - len(command))
    target = "/tmp/agentops-static-inspector"
    return (args[:index] + mount(inspector, target) + [image, target,
            json.dumps(runtime_prefixes(command[0]), separators=(",", ":"))] + command)


def directory_class(path, prefix):
    target = Path(path)
    if not target.is_absolute():
        return "RELATIVE"
    if target.is_relative_to(prefix / "lib"):
        return "PYTHON_PREFIX_LIB"
    if target.is_relative_to(prefix):
        return "PYTHON_PREFIX_OTHER"
    if any(target.is_relative_to(root) for root in
           ("/lib", "/lib64", "/usr/lib", "/usr/local/lib")):
        return "SYSTEM"
    return "OTHER"


def python_inspection(binary, container_args, env_file, host_library_path):
    binary = Path(binary)
    prefix = binary.parent.parent
    mounted = []
    for index, value in enumerate(container_args[:-1]):
        if value == "--mount":
            fields = container_args[index + 1].split(",")
            if "readonly" in fields:
                target = next((part[7:] for part in fields if part.startswith("target=")), None)
                if target:
                    mounted.append(Path(target))
    def is_mounted(path):
        # Match the sealed envelope's fixed usr-merge links, not host path spelling.
        for alias in ("/bin", "/sbin", "/lib", "/lib64"):
            if path.is_relative_to(alias):
                path = Path("/usr") / path.relative_to("/")
                break
        return any(path.is_relative_to(target) for target in mounted)
    with binary.open("rb") as stream:
        elf = stream.read(4) == b"\x7fELF"
    with env_file.open("rb") as stream:
        child_library_path_set = any(line.startswith(b"LD_LIBRARY_PATH=")
                                     for line in stream.read(65536).splitlines())
    record = {
        "check": "python_startup_inspection", "elf": elf,
        "python_prefix_lib_exists": (prefix / "lib").is_dir(),
        "python_prefix_lib_readonly_mounted": is_mounted(prefix / "lib"),
        "host_ld_library_path_set": bool(host_library_path),
        "host_ld_library_path_classes": sorted({
            directory_class(value, prefix) for value in host_library_path.split(":")[:32]
            if value
        }),
        "child_ld_library_path_set": child_library_path_set,
    }
    for tool, flags in (("readelf", ["-l", "-d"]), ("ldd", [])):
        executable = shutil.which(tool)
        if executable is None:
            record[tool] = {"status": "UNAVAILABLE"}
            continue
        try:
            result = subprocess.run([executable, *flags, str(binary)], check=False,
                                    capture_output=True, timeout=10)
            info = {"status": "PASS" if result.returncode == 0 else "NONZERO",
                    "returncode": result.returncode}
            text = result.stdout[:65536].decode("utf-8", errors="replace")
            if tool == "readelf":
                info["needed"] = sorted(set(re.findall(r"Shared library: \[(" + SONAME + r")\]", text)))[:32]
                interpreter = re.search(r"Requesting program interpreter: ([^\]\n]+)\]", text)
                if interpreter:
                    name = Path(interpreter[1]).name
                    if re.fullmatch(r"ld[A-Za-z0-9_.+-]{1,96}\.so(?:\.[0-9]+)*", name):
                        info["interpreter"] = name
                    info["interpreter_readonly_mounted"] = is_mounted(Path(interpreter[1]))
                rpaths = re.findall(r"\((?:RPATH|RUNPATH)\)[^\n]*\[([^\]\n]+)\]", text)
                info["rpath_classes"] = sorted({
                    "ORIGIN_RELATIVE" if "$ORIGIN" in value else directory_class(value, prefix)
                    for paths in rpaths[:8] for value in paths.split(":")[:32] if value
                })
            else:
                libraries = []
                for match in re.finditer(r"^\s*(" + SONAME + r") => (not found|/\S+)", text, re.MULTILINE):
                    location = match[2]
                    item = {"soname": match[1]}
                    if location == "not found":
                        item["directory_class"] = "NOT_FOUND"
                    else:
                        directory = Path(location).parent
                        item["directory_class"] = directory_class(directory, prefix)
                        item["directory_readonly_mounted"] = is_mounted(directory)
                    libraries.append(item)
                info["libraries"] = libraries[:32]
            record[tool] = info
        except (OSError, subprocess.TimeoutExpired) as failure:
            diagnostic_error(failure, "python_inspection")
            record[tool] = {"status": "ERROR"}
    print(json.dumps(record, sort_keys=True), flush=True)


def case_diagnostics(root, binary=None):
    for name in ("attempts/primary/transcript.log", "execution-finished.json"):
        try:
            path = root / name
            require(not path.is_symlink())
            with path.open("rb") as stream:
                raw = stream.read(65536 if name.endswith(".log") else 4096)
            if name.endswith(".log"):
                present = b"AGENTOPS_CI_ISOLATION=FAIL TOOL_COHORT" in raw.splitlines()
                emit("tool_cohort_marker", "FAIL" if present else "NOT_OBSERVED")
                print(json.dumps(startup_classification(raw), sort_keys=True), flush=True)
                if binary is not None:
                    for record in static_path_diagnostics(raw, binary):
                        print(json.dumps(record, sort_keys=True), flush=True)
            else:
                value = json.loads(raw)
                require(isinstance(value, dict))
                require(type(value.get("exit_code")) is int)
                require(type(value.get("container_removed")) is bool)
                print(json.dumps({"check": "container_result",
                                  "exit_code": value["exit_code"],
                                  "container_removed": value["container_removed"]},
                                 sort_keys=True), flush=True)
        except FileNotFoundError:
            emit("tool_cohort_marker" if name.endswith(".log") else "container_result",
                 "NOT_RECORDED")
        except (OSError, ValueError, TypeError) as failure:
            diagnostic_error(failure, "case_diagnostics")


def module(source):
    spec = importlib.util.spec_from_file_location(
        "inert_isolation", source / "scripts/agentops-ci-isolation.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, timeout=120, **kwargs)


def git(args, cwd):
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(key, None)
    return command(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd, env=env).stdout


def load_manifest(package):
    manifest = json.loads((package / "manifest.json").read_text())
    require(manifest["repository"] == REPOSITORY)
    require(re.fullmatch("[0-9a-f]{40}", manifest["base_sha"]))
    require(hashlib.sha256((package / "snapshot.patch").read_bytes()).hexdigest()
            == manifest["patch_sha256"])
    require(hashlib.sha256((package / "validate.py").read_bytes()).hexdigest()
            == manifest["harness_sha256"])
    return manifest


def verify_source(source, manifest):
    actual = {}
    for name, digest in manifest["files"].items():
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts)
        target = source / relative
        require(target.is_file() and not target.is_symlink())
        actual[name] = hashlib.sha256(target.read_bytes()).hexdigest()
        require(actual[name] == digest)
    snapshot = hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(snapshot == manifest["snapshot_sha256"])
    require(git(["write-tree"], source).decode().strip() == manifest["snapshot_tree"])


def prepare(package, work, repository):
    manifest = load_manifest(package)
    work.mkdir(mode=0o700)
    source = work / "source"
    source.mkdir(mode=0o700)
    (work / "ownership.json").write_text(json.dumps({
        "manifest_sha256": hashlib.sha256((package / "manifest.json").read_bytes()).hexdigest(),
        "cases": list(CASES),
    }))
    git(["init", "--quiet"], source)
    git(["fetch", "--quiet", "--no-tags", "--depth=1", str(repository), manifest["base_sha"]], source)
    git(["checkout", "--quiet", "--detach", manifest["base_sha"]], source)
    require(git(["rev-parse", "HEAD"], source).decode().strip() == manifest["base_sha"])
    patch_path = package / "snapshot.patch"
    paths = {line.split("\t", 2)[2] for line in
             git(["apply", "--numstat", str(patch_path)], source).decode().splitlines()}
    require(paths == set(manifest["files"]))
    git(["apply", "--index", "--check", str(patch_path)], source)
    git(["apply", "--index", str(patch_path)], source)
    verify_source(source, manifest)
    emit("snapshot", "PASS")
    return source


def child():
    isolation = module(Path(os.environ["GITHUB_WORKSPACE"]))
    root = Path(os.environ["AGENTOPS_CI_ROOT"])
    workspace = root / "workspaces" / os.environ["AGENTOPS_CI_WORKSPACE"]
    mode = os.environ["INERT_CASE"]
    require(mode in CASES)
    require(os.environ["AZURE_CONFIG_DIR"] == str(root / "azure"))
    require(os.environ["AZD_CONFIG_DIR"] == str(root / "azd"))
    for key in ("GITHUB_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
                "COPILOT_PROVIDER_BEARER_TOKEN", "AZURE_CLIENT_SECRET"):
        require(key not in os.environ)
    for target in (root / "initialized.json", root / "execution-started",
                   root / "custody", root / "attempts/primary/transcript.log"):
        require(not target.exists())
        try:
            target.unlink()
        except OSError:
            pass
        else:
            raise ValueError("host evidence exposed")
    calls = []
    name = "ci-smoke-agentops-pa-" + workspace.name
    def create(**kwargs):
        require(kwargs == {"agent_name": name})
        calls.append(1)
        return SimpleNamespace(name=name, version="1")
    if mode == "missing_ack":
        os.environ["AGENTOPS_CI_CUSTODY_TOKEN"] = "inert-rejected-token"
        try:
            isolation.custody.create_and_record(create, agent_name=name)
        except (OSError, ValueError):
            require(calls == [])
            return 23
        raise ValueError("missing ACK accepted")
    if mode == "native_timeout":
        def timeout(**kwargs):
            create(**kwargs)
            raise TimeoutError("synthetic native timeout")
        try:
            isolation.custody.create_and_record(timeout, agent_name=name)
        except TimeoutError:
            require(calls == [1])
            return 24
        raise ValueError("native timeout accepted")
    if mode == "signal":
        isolation.custody.submit("create_intent", {})
        os.kill(os.getpid(), signal.SIGKILL)
    isolation.custody.create_and_record(create, agent_name=name)
    require(calls == [1])
    local = workspace / "synthetic-payload"
    local.write_text("INERT_PRIVATE_PIPE_CANARY")
    require(local.stat().st_mode & 0o777 == 0o600)
    if mode in ("workspace_only", "primary_and_workspace"):
        for entry in workspace.iterdir():
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
    if mode == "primary_and_workspace":
        for entry in (root / "attempts/primary").iterdir():
            if entry.name != "workspace-pointer":
                shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
    if mode in ("root_cleanup", "root_cleanup_then_init"):
        require(not isolation.delivery.cleanup(root))
        if mode == "root_cleanup_then_init":
            try:
                isolation.delivery.initialize(root, root.parent / "public")
            except (OSError, ValueError):
                pass
            else:
                raise ValueError("child initialization accepted")
    if mode == "env_redirect_only":
        os.environ["AGENTOPS_CI_ROOT"] = "/inert-not-the-host"
        os.chdir("/tmp")
    print("INERT_PRIVATE_PIPE_CANARY", flush=True)
    return 0


def cohort_result(source, record):
    isolation = module(source)
    report = {}
    for name, tool in record.items():
        result = command([tool["path"], *isolation.TOOLS[name]])
        require(hashlib.sha256(result.stdout).hexdigest() == tool["version_sha256"])
        if name == "az":
            value = json.loads(result.stdout)["azure-cli"]
        else:
            found = re.search(r"(?<!\d)(\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?)", result.stdout.decode())
            require(found is not None)
            value = found[1]
        require(re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", value))
        if name in ("copilot", "uv"):
            require(value == {"copilot": "1.0.57-3", "uv": "0.12.6"}[name])
        report[name] = {"version": value, "binary_sha256": tool["sha256"],
                        "version_output_sha256": tool["version_sha256"]}
    print(json.dumps({"same_run_tool_cohort": report}, sort_keys=True), flush=True)


def case(source, work, mode, inspector=None):
    emit(mode, "START")
    emit("case_setup", "START")
    host_library_path = os.environ.get("LD_LIBRARY_PATH", "")
    isolation = module(source)
    delivery = isolation.delivery
    parent = work / mode
    parent.mkdir(mode=0o700)
    root, public = parent / "agentops-ci-123-1", parent / "agentops-ci-public-123-1"
    delivery.initialize(root, public)
    delivery.prepare(root, "primary")
    delivery.write(root / "owner-approval.json", root, b"{}")
    event = parent / "event.json"
    event.write_text("{}")
    home = parent / "home"
    home.mkdir(mode=0o700)
    env = {
        "PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": str(parent),
        "PYTHONDONTWRITEBYTECODE": "1", "RUNNER_TEMP": str(parent),
        "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKSPACE": str(source), "GITHUB_EVENT_PATH": str(event),
        "AGENTOPS_CI_ROOT": str(root), "AZURE_CONFIG_DIR": str(root / "azure"),
        "AZD_CONFIG_DIR": str(root / "azd"), "AZURE_TOKEN_CREDENTIALS": "AzureCliCredential",
        "COPILOT_AUTO_UPDATE": "false",
        "APPLICATIONINSIGHTS_STATSBEAT_DISABLED_ALL": "true",
        "APPLICATIONINSIGHTS_CONTROLPLANE_DISABLED": "true",
    }
    original_command = isolation.checked_command
    original_args = isolation.container_arguments
    original_capture = isolation.capture
    original_docker = isolation.docker
    observed = []
    def inert_command(root, tools, producer_command):
        require(producer_command[0] == tools["copilot"]["path"])
        require(producer_command[1] == "-p")
        observed.append(json.loads((root / "tool-cohort.json").read_text()))
        if mode == "cohort_mismatch":
            bad = json.loads((root / "tool-cohort.json").read_text())
            bad["copilot"]["sha256"] = "0" * 64
            (root / "tool-cohort.json").write_text(json.dumps(bad))
        return original_command(root, tools, [
            tools["python3"]["path"], "-I", str(source / HARNESS), "--child",
        ])
    def inert_args(root, attempt, image, env_file, inputs, paths, command, **kwargs):
        kwargs["network"] = "none"
        result = original_args(root, attempt, image, env_file, inputs, paths, command, **kwargs)
        index = result.index("--env-file")
        result[index:index] = ["--env", "INERT_CASE=" + mode]
        with diagnostic_phase("python_inspection"):
            python_inspection(observed[-1]["python3"]["path"], result, env_file, host_library_path)
        if inspector is not None:
            require(command[0] == observed[-1]["python3"]["path"])
            result = inspector_arguments(result, image, command, inspector, isolation.mount)
        return result
    def bounded_capture(*args, **kwargs):
        kwargs["seconds"] = 30
        return original_capture(*args, **kwargs)
    def diagnostic_docker(argv, **kwargs):
        label = command_label(["docker", *argv]) or "docker_other"
        with diagnostic_phase(label):
            return original_docker(argv, **kwargs)
    emit("case_setup", "PASS")
    with patch.dict(os.environ, env, clear=True), \
            patch.object(isolation, "checked_command",
                         side_effect=traced("checked_command", inert_command)), \
            patch.object(isolation, "container_arguments",
                         side_effect=traced("container_arguments", inert_args)), \
            patch.object(isolation, "capture",
                         side_effect=traced("container_capture", bounded_capture)), \
            patch.object(isolation, "docker", side_effect=diagnostic_docker), \
            contextlib.ExitStack() as diagnostics:
        for name in ("tool_cohort", "scaffold", "child_environment", "build_envelope",
                     "mount", "remove_container", "cleanup_runtime"):
            diagnostics.enter_context(patch.object(
                isolation, name, side_effect=traced(name, getattr(isolation, name))))
        try:
            result = isolation.run(root, "primary")
            emit("case_assertions", "START")
            expected = {"missing_ack": 125, "native_timeout": 24,
                        "signal": 137, "cohort_mismatch": 125}.get(mode, 0)
            require(result == expected)
            require(len(observed) == 1 and not delivery.retry_allowed(root))
            require((root / "initialized.json").is_file())
            require((root / "execution-started").read_bytes() == b"primary\n")
            require(json.loads((root / "execution-finished.json").read_text()) ==
                    {"attempt": "primary", "exit_code": expected, "container_removed": True})
            receipt = root / "custody/identity.json"
            if mode in ("missing_ack", "native_timeout", "signal", "cohort_mismatch"):
                require(not receipt.exists())
                if mode == "cohort_mismatch":
                    require(b"AGENTOPS_CI_ISOLATION=FAIL TOOL_COHORT" in
                            (root / "attempts/primary/transcript.log").read_bytes())
            else:
                value = json.loads(receipt.read_text())
                require(value["provenance"] == "untrusted_agent_writable")
                require(value["payload"]["version"] == "1")
                require(b"INERT_PRIVATE_PIPE_CANARY" in
                        (root / "attempts/primary/transcript.log").read_bytes())
            if mode in ("workspace_only", "primary_and_workspace"):
                key = (root / "attempts/primary/workspace-pointer").read_text().strip()
                require(not list((root / "workspaces" / key).iterdir()))
            if mode == "preserve":
                with diagnostic_phase("cohort_report"):
                    cohort_result(source, observed[0])
            emit("case_assertions", "PASS")
            emit(mode, "PASS")
        except Exception as failure:
            diagnostic_error(failure, "case")
            raise
        finally:
            case_diagnostics(root, observed[-1]["python3"]["path"] if observed else None)
            isolation.cleanup_runtime(root)


def cleanup(package, work):
    if not work.exists():
        emit("cleanup", "NOT_STARTED")
        return
    manifest = load_manifest(package)
    ownership = json.loads((work / "ownership.json").read_text())
    require(ownership == {
        "manifest_sha256": hashlib.sha256((package / "manifest.json").read_bytes()).hexdigest(),
        "cases": list(CASES),
    })
    source = work / "source"
    verify_source(source, manifest)
    isolation = module(source)
    for mode in CASES:
        root = work / mode / "agentops-ci-123-1"
        if root.exists():
            isolation.cleanup_runtime(root)
    require(work.is_dir() and not work.is_symlink())
    shutil.rmtree(work)
    require(not work.exists())
    emit("cleanup", "PASS")


def main():
    sys.dont_write_bytecode = True
    os.umask(0o077)
    if sys.argv[1:] == ["--child"]:
        return child()
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("verify", "run", "cleanup"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    work = args.work.absolute()
    require(work.parent == Path(os.environ["RUNNER_TEMP"]).resolve())
    require(re.fullmatch("agentops-custody-validation-[1-9][0-9]*-[1-9][0-9]*", work.name))
    def interrupted(_signum, _frame):
        raise TimeoutError("inert job deadline")
    signal.signal(signal.SIGTERM, interrupted)
    if args.action == "cleanup":
        cleanup(package, work)
        return 0
    try:
        with diagnostic_phase("snapshot_prepare"):
            source = prepare(package, work, args.repository.resolve())
        if args.action == "run":
            require(sys.platform == "linux")
            require(not any(os.environ.get(key) for key in (
                "AZURE_CLIENT_SECRET", "AZURE_FEDERATED_TOKEN_FILE",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "COPILOT_PROVIDER_BEARER_TOKEN")))
            with diagnostic_phase("custody_regressions"):
                result = command([sys.executable, "-B", "-m", "unittest", "discover",
                                  "-s", str(source / "scripts/tests"),
                                  "-p", "test_agentops_ci_custody.py"], cwd=source)
            require(b"FAILED" not in result.stderr)
            count = re.search(rb"Ran (\d+) tests", result.stderr)
            skipped = re.search(rb"skipped=(\d+)", result.stderr)
            require(count is not None)
            print(json.dumps({"check": "custody_regressions", "status": "PASS",
                              "total": int(count[1]), "skipped": int(skipped[1]) if skipped else 0}),
                  flush=True)
            with diagnostic_phase("static_inspector_build"):
                inspector = build_static_inspector(work)
            for mode in CASES:
                case(source, work, mode, inspector)
        return 0
    finally:
        with diagnostic_phase("exact_cleanup"):
            cleanup(package, work)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as failure:
        diagnostic_error(failure, "validation")
        emit("validation", "FAIL")
        sys.exit(1)
