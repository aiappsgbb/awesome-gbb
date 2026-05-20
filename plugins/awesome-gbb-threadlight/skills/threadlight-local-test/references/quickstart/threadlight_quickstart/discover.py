"""Auto-discover a threadlight-designed PoC layout.

Walks upward from the operator's cwd looking for the canonical structure
that ``threadlight-design`` emits:

    <poc-root>/
    ├── specs/
    │   ├── SPEC.md                    (optional — informational)
    │   ├── sample-data/<entity>.json  (REQUIRED — at least one)
    │   └── prep-guide.html            (optional — simulator source)
    └── src/agent/
        ├── container.py               (optional — Pattern 0 does NOT call)
        └── skills/<name>/SKILL.md     (optional — wired via SkillsProvider)

Fails fast with a clear message naming the missing artifact and which
``threadlight-design`` SPEC section produces it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class PoCLayoutError(RuntimeError):
    """Raised when the cwd doesn't look like a threadlight PoC."""


@dataclass(frozen=True)
class PoCLayout:
    """Resolved paths inside a threadlight-designed PoC."""

    root: Path
    specs_dir: Path
    sample_data_dir: Path
    sample_data_files: tuple[Path, ...]
    skills_dir: Path | None
    skill_subdirs: tuple[Path, ...] = field(default_factory=tuple)
    spec_md: Path | None = None
    prep_guide_html: Path | None = None
    demo_prompts_txt: Path | None = None

    @property
    def entity_names(self) -> tuple[str, ...]:
        """Entity name for each sample-data file (filename without .json)."""
        return tuple(p.stem for p in self.sample_data_files)

    @property
    def skill_names(self) -> tuple[str, ...]:
        return tuple(d.name for d in self.skill_subdirs)

    def summary(self) -> str:
        skills = ", ".join(self.skill_names) or "(none)"
        entities = ", ".join(self.entity_names) or "(none)"
        return (
            f"PoC root      : {self.root}\n"
            f"  entities    : {entities}\n"
            f"  skills      : {skills}\n"
            f"  prep-guide  : {'yes' if self.prep_guide_html else 'no'}\n"
            f"  demo-prompts: {'yes' if self.demo_prompts_txt else 'no'}"
        )


def _walk_up_for(start: Path, marker: Path) -> Path | None:
    """Return the first ancestor of ``start`` that contains ``marker``."""
    for parent in (start, *start.parents):
        if (parent / marker).exists():
            return parent
    return None


def discover(start: Path | str | None = None) -> PoCLayout:
    """Resolve the PoC layout by walking up from ``start`` (default: cwd).

    Raises ``PoCLayoutError`` with an actionable message if the cwd
    doesn't look like a threadlight PoC.
    """
    cwd = Path(start) if start else Path.cwd()
    cwd = cwd.resolve()

    # The cheapest unambiguous marker is specs/sample-data/. Any
    # threadlight-design Fast-PoC output has it; nothing else does.
    root = _walk_up_for(cwd, Path("specs/sample-data"))
    if root is None:
        raise PoCLayoutError(
            f"No threadlight PoC found at or above {cwd}.\n"
            "Looked for: specs/sample-data/ (SPEC § 4 + threadlight-design Phase A).\n"
            "Run threadlight-design first, then re-run from the PoC root."
        )

    specs_dir = root / "specs"
    sample_data_dir = specs_dir / "sample-data"
    sample_data_files = tuple(sorted(sample_data_dir.glob("*.json")))
    if not sample_data_files:
        raise PoCLayoutError(
            f"specs/sample-data/ exists at {root} but has no *.json files.\n"
            "Re-run threadlight-demo-data-factory or hand-author at least one entity."
        )

    # Validate each sample-data file is a JSON list of dict records.
    for path in sample_data_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PoCLayoutError(
                f"sample-data file is not valid JSON: {path}\n  {exc}"
            ) from exc
        if not isinstance(data, list):
            raise PoCLayoutError(
                f"sample-data file must be a JSON array (got {type(data).__name__}): {path}"
            )

    skills_dir = root / "src" / "agent" / "skills"
    skill_subdirs: tuple[Path, ...] = ()
    if skills_dir.is_dir():
        skill_subdirs = tuple(
            sorted(
                d
                for d in skills_dir.iterdir()
                if d.is_dir() and (d / "SKILL.md").exists()
            )
        )
    else:
        skills_dir = None

    spec_md = specs_dir / "SPEC.md"
    if not spec_md.exists():
        spec_md = None

    prep_guide = specs_dir / "prep-guide.html"
    if not prep_guide.exists():
        prep_guide = None

    demo_prompts = root / "tests" / "demo-prompts.txt"
    if not demo_prompts.exists():
        demo_prompts = None

    return PoCLayout(
        root=root,
        specs_dir=specs_dir,
        sample_data_dir=sample_data_dir,
        sample_data_files=sample_data_files,
        skills_dir=skills_dir,
        skill_subdirs=skill_subdirs,
        spec_md=spec_md,
        prep_guide_html=prep_guide,
        demo_prompts_txt=demo_prompts,
    )
