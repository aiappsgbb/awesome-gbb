#!/usr/bin/env bash
set -euo pipefail

AGE_VERSION="1.3.2"
AGE_ARCHIVE_URL="https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz"
AGE_ARCHIVE_SHA256="cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10"

validate_platform() {
  [ "$(uname -s)" = "Linux" ] && [ "$(uname -m)" = "x86_64" ] || {
    echo "setup-agentops-age: only Linux x86_64 is supported" >&2
    return 1
  }
}

download_archive() {
  curl --fail --silent --show-error --location \
    --proto '=https' --tlsv1.2 \
    --output "$1" "$AGE_ARCHIVE_URL"
}

install_age() {
  [ "$#" -eq 1 ] || {
    echo "usage: setup-agentops-age.sh ABSOLUTE_DESTINATION" >&2
    return 2
  }
  validate_platform

  local destination="$1"
  case "$destination" in
    /*) ;;
    *)
      echo "setup-agentops-age: destination must be absolute" >&2
      return 2
      ;;
  esac
  [ ! -e "$destination" ] && [ ! -L "$destination" ] || {
    echo "setup-agentops-age: destination must not exist" >&2
    return 1
  }

  umask 077
  mkdir -m 700 -- "$destination"
  local archive="$destination/.age-v${AGE_VERSION}-linux-amd64.tar.gz"
  trap 'rm -f -- "$archive"' RETURN
  download_archive "$archive"
  chmod 600 "$archive"

  local actual_archive_sha
  actual_archive_sha="$(
    python3 -I - "$archive" <<'PY'
import hashlib
import pathlib
import sys

print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
  )"
  if [ "$actual_archive_sha" != "$AGE_ARCHIVE_SHA256" ]; then
    echo "setup-agentops-age: archive SHA-256 mismatch" >&2
    return 1
  fi

  python3 -I - "$archive" "$destination" <<'PY'
import os
from pathlib import Path
import stat
import sys
import tarfile

archive = Path(sys.argv[1])
destination = Path(sys.argv[2])
required = {"age/age": "age", "age/age-keygen": "age-keygen"}
created = []
try:
    with tarfile.open(archive, mode="r:gz") as bundle:
        members = {member.name: member for member in bundle.getmembers()}
        if len(members) != len(bundle.getmembers()):
            raise ValueError("duplicate archive member")
        for member_name, output_name in required.items():
            member = members.get(member_name)
            if member is None or not member.isfile() or member.size > 32 * 1024 * 1024:
                raise ValueError("invalid required archive member")
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError("unreadable required archive member")
            output = destination / output_name
            fd = os.open(
                output,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o700,
            )
            created.append(output)
            with os.fdopen(fd, "wb") as stream:
                while chunk := source.read(1024 * 1024):
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(output, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
except Exception:
    for output in reversed(created):
        try:
            output.unlink()
        except OSError:
            pass
    raise
PY

  rm -f -- "$archive"
  trap - RETURN
  local binary_sha
  binary_sha="$(
    python3 -I - "$destination/age" <<'PY'
import hashlib
import pathlib
import sys

print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())
PY
  )"
  printf 'AGENTOPS_CI_AGE_BIN=%s\n' "$destination/age"
  printf 'AGENTOPS_CI_AGE_SHA256=%s\n' "$binary_sha"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  install_age "$@"
fi
