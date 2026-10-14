# HTML presentation

Create continuous, evidence-backed browser narratives for guided talks and
independent reading. Native scrolling, chapter anchors and purposeful explorers
support the argument rather than imitating a paginated slide deck.

Use `web-experience-design` for general websites, applications and task-first
web UX; use `gbb-pptx` for editable native PowerPoint. This skill's original
HTML-specific planning synthesis was conceptually inspired by
[`gbb-pptx`](../gbb-pptx/SKILL.md), not copied from its implementation.

## Requirements and evidence limits

Python 3.9+, filesystem/shell access and browser automation are required for the
complete workflow. The bundler and checker use Python's standard library.
Microsoft-specific research explicitly consults WorkIQ, Seismic and Microsoft
Learn. Record unavailable tools, failed searches and missing proof; never
substitute a synthetic example for observed customer outcomes.

The skill does not deploy Azure infrastructure or invoke Azure models.
Bundler/checker and packaging tests verify technical contracts, not generated
design quality, source-system authentication or audience comprehension.
Saved model/trigger evaluations are **deferred**, not passing evidence.

## Lean Cowork upload

From the awesome-gbb root, select a fresh output directory:

```sh
python3 scripts/package_cowork.py --output-dir /tmp/html-presentation-cowork
```

The output contains an upload ZIP and extracted skill folder with **exactly
20 files: SKILL.md plus 19 companions**. It includes three references, two
authoring scripts, palette PDF/manifest/CSS/runtime/template, five authentic
icons and the Light Apps, Chart-Up and Cloud-Lock illustrations. Tests,
evaluations, this README and the remaining illustration variants are excluded.
The generated instructions and manifest describe only the selected subset.
SKILL.md stays below 20,000 characters, each companion at most 5 MB, and all
companions at most 10 MB. Generated output is not committed.

Cowork must provide Python/filesystem execution to bundle the artifact.
Browser verification and authenticated research may be unavailable there;
disclose those gaps instead of claiming full acceptance.

## Assets and rights

The contributor explicitly approved public redistribution of the supplied
palette PDF and illustrations. Native graphics and their SHA-256 provenance
are preserved in `assets/asset-manifest.json`. Microsoft graphics retain their
original rights and applicable terms; this repository's MIT license does
**not** relicense third-party graphics. Architecture icons are for diagrams,
training and documentation, not arbitrary marketing-logo use. See:

- https://learn.microsoft.com/en-us/azure/architecture/icons/
- https://learn.microsoft.com/en-us/entra/architecture/architecture-icons

Private presentations, source evidence, session artifacts and the original
workspace README are not part of this reusable skill.

## Local checks

```sh
python3 -m unittest discover -s skills/html-presentation/scripts -p 'test_*.py'
python3 -m unittest scripts.tests.test_package_cowork
node --check skills/html-presentation/assets/story.js
```

Follow `SKILL.md` for separate-installation staging, bundling and whole-narrative
browser acceptance. Static checks alone do not establish an offline browser,
print, reduced-motion or accessibility acceptance claim.
