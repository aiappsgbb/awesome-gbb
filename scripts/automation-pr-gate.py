#!/usr/bin/env python3
"""
automation-pr-gate.py — CI gate enforcing AGENTS.md § 4 mass-edit invariants.

This is the safety net that makes the FSI-EIN normalization incident
(and similar mass-edit damage) structurally impossible. It runs on
every PR that touches `skills/**` and rejects:

  1. Multi-skill PRs              — without `[multi-skill]` opt-in
  2. Reference data edits         — without `[scrub-canon]` opt-in
  3. SKILL.md body edits          — without `[skill-rewrite]` opt-in
  4. Non-PATCH version bumps      — for metadata-only PRs
  5. Description length > 1024    — AGENTS.md § 2.3

The gate reads ALL commit messages on the PR branch (not just the head
commit) for opt-in tags — any commit on the branch with the tag is
sufficient.

Invoke:
    python automation-pr-gate.py --base main
    python automation-pr-gate.py --base origin/main --diff-from-file diff.txt

Exits 0 on pass, 1 on any violation.
"""

from __future__ import annotations

import argparse
import io
import pathlib
import re
import subprocess
import sys
from typing import Iterable

# Force UTF-8 stdout/stderr so emoji in pass/fail messages (✅ ❌) work on
# Windows consoles that default to cp1252. The GitHub Actions runner is
# already UTF-8, but local contributors would otherwise crash with
# `UnicodeEncodeError` on the very first reject message.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR_RE = re.compile(r"^skills/([^/]+)/")
SKILL_MD_RE = re.compile(r"^skills/([^/]+)/SKILL\.md$")
PIN_FILE_RE = re.compile(r"^skills/([^/]+)/references/upstream-pin\.md$")
CANON_RE = re.compile(r"^skills/[^/]+/references/data-realism/")

OPT_IN_MULTI_SKILL = "[multi-skill]"
OPT_IN_SCRUB_CANON = "[scrub-canon]"
OPT_IN_SKILL_REWRITE = "[skill-rewrite]"

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MAX_DESCRIPTION_CHARS = 1024


# ──────────────────────────── git helpers ───────────────────────────


def run_git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        return out.stdout
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git {' '.join(args)} failed: {e.stderr}", file=sys.stderr)
        raise


def changed_files(base: str) -> list[str]:
    out = run_git("diff", "--name-only", f"{base}...HEAD")
    return [line.strip() for line in out.splitlines() if line.strip()]


def commit_messages(base: str) -> list[str]:
    out = run_git("log", "--format=%B%x1f", f"{base}..HEAD")
    return [m.strip() for m in out.split("\x1f") if m.strip()]


def file_at_revision(rev: str, path: str) -> str | None:
    try:
        return run_git("show", f"{rev}:{path}")
    except subprocess.CalledProcessError:
        return None


# ──────────────────────────── frontmatter ───────────────────────────


def split_frontmatter(text: str) -> tuple[str, str, str] | None:
    """Return (pre, fm, post) or None if no frontmatter."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[0], parts[1], parts[2]


def parse_fm(text: str) -> dict | None:
    split = split_frontmatter(text)
    if not split:
        return None
    try:
        data = yaml.safe_load(split[1]) or {}
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


# ──────────────────────────── diff analysis ─────────────────────────


def skill_md_body_changed(base: str, path: str) -> bool:
    """True if the SKILL.md diff includes any line OUTSIDE the YAML
    frontmatter block."""
    head_text = pathlib.Path(REPO_ROOT / path).read_text(encoding="utf-8")
    base_text = file_at_revision(base, path) or ""

    def body_only(text: str) -> str:
        split = split_frontmatter(text)
        if not split:
            return text
        # body is everything after the closing `---`
        return split[2]

    return body_only(head_text) != body_only(base_text)


def description_length(text: str) -> int | None:
    fm = parse_fm(text)
    if not fm:
        return None
    desc = fm.get("description")
    if not isinstance(desc, str):
        return None
    return len(desc)


def version_tuple(text: str) -> tuple[int, int, int] | None:
    fm = parse_fm(text)
    if not fm:
        return None
    meta = fm.get("metadata") or {}
    v = meta.get("version")
    if not isinstance(v, str):
        return None
    m = SEMVER_RE.match(v)
    if not m:
        return None
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


# ──────────────────────────── gates ─────────────────────────────────


def gate_one_skill_per_pr(
    files: list[str], opts: set[str]
) -> list[str]:
    skills_touched: set[str] = set()
    for f in files:
        m = SKILLS_DIR_RE.match(f)
        if m:
            skills_touched.add(m.group(1))

    if len(skills_touched) > 1 and OPT_IN_MULTI_SKILL not in opts:
        return [
            f"❌ Multi-skill PR ({len(skills_touched)} skills: "
            f"{sorted(skills_touched)}). Add `{OPT_IN_MULTI_SKILL}` to "
            f"any commit message on this branch to opt in (AGENTS.md § 4)."
        ]
    return []


def gate_no_canon_edits(
    files: list[str], opts: set[str]
) -> list[str]:
    canon = [f for f in files if CANON_RE.match(f)]
    if canon and OPT_IN_SCRUB_CANON not in opts:
        return [
            f"❌ Reference data canon edits in {canon}. Reference data "
            "under `references/data-realism/` is canonical per AGENTS.md "
            f"§ 2.2. Add `{OPT_IN_SCRUB_CANON}` to a commit message to "
            "opt in (requires a human reviewer)."
        ]
    return []


def gate_skill_md_body(
    files: list[str], opts: set[str], base: str
) -> list[str]:
    errors: list[str] = []
    for f in files:
        m = SKILL_MD_RE.match(f)
        if not m:
            continue
        if skill_md_body_changed(base, f) and OPT_IN_SKILL_REWRITE not in opts:
            errors.append(
                f"❌ {f}: body changed outside YAML frontmatter. Add "
                f"`{OPT_IN_SKILL_REWRITE}` to a commit message to opt in "
                "(AGENTS.md § 4)."
            )
    return errors


def gate_patch_only_for_metadata_diff(
    files: list[str], opts: set[str], base: str
) -> list[str]:
    """For PRs whose ONLY SKILL.md change is a `metadata.version` bump
    (no body change) AND that touch a pin file, the bump must be PATCH."""
    errors: list[str] = []

    # Group changes by skill
    by_skill: dict[str, set[str]] = {}
    for f in files:
        m = SKILLS_DIR_RE.match(f)
        if m:
            by_skill.setdefault(m.group(1), set()).add(f)

    for skill, paths in by_skill.items():
        skill_md = f"skills/{skill}/SKILL.md"
        pin = f"skills/{skill}/references/upstream-pin.md"
        if skill_md not in paths or pin not in paths:
            continue

        # SKILL.md must be frontmatter-only (body unchanged)
        if skill_md_body_changed(base, skill_md):
            continue  # gate_skill_md_body handles this case

        # version bump must be PATCH
        old_text = file_at_revision(base, skill_md) or ""
        new_text = pathlib.Path(REPO_ROOT / skill_md).read_text(encoding="utf-8")
        old_v = version_tuple(old_text)
        new_v = version_tuple(new_text)
        if not (old_v and new_v):
            continue
        if (new_v[0], new_v[1]) != (old_v[0], old_v[1]):
            errors.append(
                f"❌ {skill_md}: metadata-only PR but version bumped "
                f"{old_v} → {new_v} (MAJOR/MINOR). Pin refresh must be "
                "PATCH (AGENTS.md § 5)."
            )
        elif new_v[2] != old_v[2] + 1:
            errors.append(
                f"❌ {skill_md}: PATCH version bumped {old_v} → {new_v}; "
                f"expected {(old_v[0], old_v[1], old_v[2] + 1)}."
            )
    return errors


def gate_description_length(
    files: list[str], base: str
) -> list[str]:
    errors: list[str] = []
    for f in files:
        m = SKILL_MD_RE.match(f)
        if not m:
            continue
        new_text = pathlib.Path(REPO_ROOT / f).read_text(encoding="utf-8")
        new_len = description_length(new_text)
        if new_len is None:
            continue
        if new_len > MAX_DESCRIPTION_CHARS:
            errors.append(
                f"❌ {f}: description is {new_len} chars, max is "
                f"{MAX_DESCRIPTION_CHARS} (AGENTS.md § 2.3)."
            )
    return errors


# ──────────────────────────── main ──────────────────────────────────


def collect_opt_ins(messages: Iterable[str]) -> set[str]:
    blob = "\n".join(messages)
    opts: set[str] = set()
    for opt in (OPT_IN_MULTI_SKILL, OPT_IN_SCRUB_CANON, OPT_IN_SKILL_REWRITE):
        if opt in blob:
            opts.add(opt)
    return opts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="origin/main", help="base ref")
    ap.add_argument(
        "--files-from",
        type=pathlib.Path,
        help="newline-separated file list (for tests)",
    )
    ap.add_argument(
        "--commit-messages-from",
        type=pathlib.Path,
        help="newline-separated commit-message file (for tests)",
    )
    args = ap.parse_args(argv)

    if args.files_from:
        files = [
            line.strip()
            for line in args.files_from.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        files = changed_files(args.base)

    if args.commit_messages_from:
        messages = [
            args.commit_messages_from.read_text(encoding="utf-8").strip()
        ]
    else:
        messages = commit_messages(args.base)

    opts = collect_opt_ins(messages)

    print(f"Changed files ({len(files)}):")
    for f in files:
        print(f"  {f}")
    print(f"Opt-in tags found: {sorted(opts) or '(none)'}")

    errors: list[str] = []
    errors.extend(gate_one_skill_per_pr(files, opts))
    errors.extend(gate_no_canon_edits(files, opts))
    errors.extend(gate_skill_md_body(files, opts, args.base))
    errors.extend(gate_patch_only_for_metadata_diff(files, opts, args.base))
    errors.extend(gate_description_length(files, args.base))

    if errors:
        print(f"\n❌ {len(errors)} gate violation(s):\n", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    print("\n✅ All automation PR gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
