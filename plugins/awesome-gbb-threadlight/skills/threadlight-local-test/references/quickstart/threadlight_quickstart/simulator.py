"""Demo-script prompt pump.

Two sources, in priority order:

  1. ``<poc-root>/tests/demo-prompts.txt`` — one prompt per line, blank
     lines and ``#`` comments ignored. The canonical Pattern 0 source
     because it survives ``prep-guide.html`` regenerations.
  2. ``<poc-root>/specs/prep-guide.html`` — extracts literal prompts
     from ``<strong>Type this:</strong>`` blocks (the convention
     ``threadlight-design`` § 10 emits). Fallback only — fragile to
     HTML structure changes.

The simulator is **optional**: Pattern 0 runs fine without any source,
and the Streamlit UI just hides the "Next demo prompt" button.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .discover import PoCLayout

log = logging.getLogger(__name__)

_TYPE_THIS_RE = re.compile(
    r"<strong>\s*Type this:\s*</strong>\s*(.+?)(?=</p>|<br|<strong>|$)",
    flags=re.IGNORECASE | re.DOTALL,
)
_CLICK_HERE_RE = re.compile(
    r"<strong>\s*Click here:\s*</strong>\s*(.+?)(?=</p>|<br|<strong>|$)",
    flags=re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub("", html).strip()


def _from_demo_prompts_txt(path: Path) -> list[str]:
    prompts: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        prompts.append(line)
    log.info("Loaded %d simulator prompts from %s", len(prompts), path)
    return prompts


def _from_prep_guide_html(path: Path) -> list[str]:
    html = path.read_text(encoding="utf-8")
    matches = _TYPE_THIS_RE.findall(html) + _CLICK_HERE_RE.findall(html)
    prompts = [p for p in (_strip_tags(m) for m in matches) if p]
    log.info("Loaded %d simulator prompts from %s", len(prompts), path)
    return prompts


def load_simulator_prompts(layout: PoCLayout) -> list[str]:
    """Return the demo-script prompts for this PoC (empty if none found)."""
    if layout.demo_prompts_txt is not None:
        return _from_demo_prompts_txt(layout.demo_prompts_txt)
    if layout.prep_guide_html is not None:
        return _from_prep_guide_html(layout.prep_guide_html)
    return []


class PromptCursor:
    """Cycles through a list of prompts, returning each in order."""

    def __init__(self, prompts: list[str]) -> None:
        self._prompts = list(prompts)
        self._idx = 0

    @property
    def total(self) -> int:
        return len(self._prompts)

    @property
    def remaining(self) -> int:
        return max(0, self.total - self._idx)

    def peek(self) -> str | None:
        if self._idx >= self.total:
            return None
        return self._prompts[self._idx]

    def advance(self) -> str | None:
        nxt = self.peek()
        if nxt is not None:
            self._idx += 1
        return nxt

    def reset(self) -> None:
        self._idx = 0
