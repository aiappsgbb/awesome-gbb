#!/usr/bin/env python3
"""Sync tests/killer-prompts.md → azure.yaml STARTER_{1,2,3}_TITLE/PROMPT env vars.

Emitted by the `threadlight-design` skill alongside `tests/killer-prompts.md`.
Wired into `threadlight-deploy` Phase 6.7 ("Live MVP Walkthrough" back-fill)
so the deployed agent's home surface (Teams chip / Workspace starter pill /
Foundry playground prompt) picks up evolution of the wow-prompts on the
next `azd up` without hand-editing the deploy manifest.

Idempotent. Parses the K1/K2/K3 rows from the killer-prompts markdown table,
writes a single `# region: killer-prompts (managed by refresh_killer_prompts.py)`
block in azure.yaml. Re-running with no source change is a no-op.

Usage:
    python infra/scripts/refresh_killer_prompts.py
    python infra/scripts/refresh_killer_prompts.py --check       # exit 1 if drift
    python infra/scripts/refresh_killer_prompts.py --max-prompts 5

The Teams chip-rendering limit on titles is ~30 chars; over-length titles
are truncated and a warning is printed (but the run does not fail).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE = REPO_ROOT / "tests" / "killer-prompts.md"
TARGET = REPO_ROOT / "azure.yaml"
REGION_BEGIN = "# region: killer-prompts (managed by refresh_killer_prompts.py)"
REGION_END = "# endregion: killer-prompts"
TITLE_LIMIT = 30


def parse_killer_prompts(path: Path) -> list[tuple[str, str]]:
    """Return [(title, prompt), ...] from the markdown table rows ranked K1, K2, ..."""
    if not path.exists():
        sys.exit(f"ERROR: source file not found: {path}")
    rows: list[tuple[str, str]] = []
    pattern = re.compile(r"^\|\s*K(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", re.MULTILINE)
    text = path.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        _rank, prompt, br = match.group(1), match.group(2), match.group(3)
        title = derive_title(prompt, br)
        rows.append((title, prompt.strip()))
    rows.sort(key=lambda _r: text.index(_r[1]))
    return rows


def derive_title(prompt: str, br: str) -> str:
    """Short Teams-chip-friendly title — first 4-5 words, or BR tag if prompt is long."""
    words = prompt.strip().split()
    candidate = " ".join(words[:5])
    if len(candidate) > TITLE_LIMIT:
        candidate = br.strip()
    if len(candidate) > TITLE_LIMIT:
        print(f"WARN: title over {TITLE_LIMIT} chars, truncating: {candidate!r}")
        candidate = candidate[:TITLE_LIMIT - 1] + "…"
    return candidate


def render_region(rows: list[tuple[str, str]], max_prompts: int) -> str:
    """Render the env-var block that lives between region markers in azure.yaml."""
    lines = [REGION_BEGIN]
    for idx, (title, prompt) in enumerate(rows[:max_prompts], start=1):
        safe_prompt = prompt.replace('"', '\\"')
        lines.append(f'        STARTER_{idx}_TITLE: "{title}"')
        lines.append(f'        STARTER_{idx}_PROMPT: "{safe_prompt}"')
    lines.append(REGION_END)
    return "\n".join(lines)


def splice(yaml_text: str, region: str) -> str:
    """Replace existing managed region; append (with indent context) if absent."""
    pattern = re.compile(
        rf"{re.escape(REGION_BEGIN)}.*?{re.escape(REGION_END)}",
        re.DOTALL,
    )
    if pattern.search(yaml_text):
        return pattern.sub(region, yaml_text)
    sys.exit(
        "ERROR: azure.yaml is missing the killer-prompts region markers. "
        "Add the following two lines (indented under the agent service env block) "
        "before re-running:\n"
        f"  {REGION_BEGIN}\n"
        f"  {REGION_END}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="exit 1 if drift, no write")
    parser.add_argument("--max-prompts", type=int, default=3, help="STARTER chip count (Teams: 3)")
    args = parser.parse_args(argv)

    rows = parse_killer_prompts(SOURCE)
    if not rows:
        sys.exit(f"ERROR: no K1/K2/K3 rows found in {SOURCE}")

    region = render_region(rows, args.max_prompts)
    current = TARGET.read_text(encoding="utf-8")
    updated = splice(current, region)

    if args.check:
        if updated != current:
            print(f"DRIFT: {TARGET.relative_to(REPO_ROOT)} is out of sync with {SOURCE.relative_to(REPO_ROOT)}")
            return 1
        print("OK: azure.yaml matches killer-prompts.md")
        return 0

    if updated == current:
        print("no-op: azure.yaml already in sync")
        return 0

    TARGET.write_text(updated, encoding="utf-8")
    print(f"updated: {TARGET.relative_to(REPO_ROOT)} ({len(rows[:args.max_prompts])} starters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
