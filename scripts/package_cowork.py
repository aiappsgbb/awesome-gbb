#!/usr/bin/env python3
"""Package the presentation skill with at most 20 total files for Cowork."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile


PROJECT = Path(__file__).resolve().parents[1]
FILES = (
    "SKILL.md",
    "references/planning.md", "references/visuals.md", "references/interaction.md",
    "scripts/bundle.py", "scripts/check_story.py",
    "assets/Azure-ColorPalette-2026.pdf", "assets/asset-manifest.json",
    "assets/palette.css", "assets/story.css", "assets/story.js", "assets/template.html",
    "assets/icons/ai-gateway.svg", "assets/icons/entra-id.svg",
    "assets/icons/foundry.svg", "assets/icons/sql-database.svg", "assets/icons/tenant.svg",
    "assets/illustrations/Azure-Illcon-Light-Apps-512.png",
    "assets/illustrations/Azure-Illcon-Light-Chart-Up-512.png",
    "assets/illustrations/Azure-Illcon-Light-Cloud-Lock-512.png",
)


def validate(folder):
    files = sorted(path for path in folder.rglob("*") if path.is_file())
    if {path.relative_to(folder).as_posix() for path in files} != set(FILES):
        raise ValueError("Deployment file set differs from the declared 20-file selection.")
    if len(files) > 20:
        raise ValueError("Cowork deployment exceeds 20 total files.")
    companions = [path for path in files if path.name != "SKILL.md"]
    if any(path.stat().st_size > 5_000_000 for path in companions):
        raise ValueError("A companion exceeds 5 MB.")
    if sum(path.stat().st_size for path in companions) > 10_000_000:
        raise ValueError("Companions exceed 10 MB total.")
    text = (folder / "SKILL.md").read_text(encoding="utf-8")
    if len(text) >= 20_000:
        raise ValueError("SKILL.md exceeds Cowork's instruction limit.")
    if not re.search(r"^name: html-presentation$", text, re.M):
        raise ValueError("Skill identity must remain html-presentation.")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if not target.startswith("https://") and not (folder / target).is_file():
            raise ValueError(f"Missing instruction reference: {target}")
    if "evals/" in text:
        raise ValueError("Deployment instructions reference excluded evaluations.")
    manifest = json.loads((folder / "assets/asset-manifest.json").read_text())
    artwork = {name.removeprefix("assets/") for name in FILES
               if name.startswith(("assets/icons/", "assets/illustrations/"))}
    manifest_paths = [item["path"] for item in manifest["assets"]]
    if set(manifest_paths) != artwork or len(manifest_paths) != len(artwork):
        raise ValueError("Asset manifest differs from the selected artwork.")
    for item in manifest["assets"]:
        asset = folder / "assets" / item["path"]
        if hashlib.sha256(asset.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Asset provenance hash mismatch: {item['path']}")
    return files


def package(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    destination, archive = output / "html-presentation", output / "html-presentation.zip"
    if destination.exists() or destination.is_symlink() or archive.exists():
        raise ValueError("Output already exists; choose a fresh --output-dir.")
    with tempfile.TemporaryDirectory(prefix="cowork-skill-") as temporary:
        staged = Path(temporary) / "html-presentation"
        for relative in FILES:
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target)

        main = staged / "SKILL.md"
        text, marker, tail = main.read_text(encoding="utf-8").partition("- `evals/evals.json`:")
        if not marker or "evals/trigger-evals.json" not in tail:
            raise ValueError("Source evaluation-resource section changed; review packaging.")
        text = text.replace(
            "# HTML presentation\n",
            "# HTML presentation\n\n"
            "This Cowork edition includes three supplied Light illustrations "
            "(Apps, Chart-Up and Cloud-Lock), five authentic product icons, "
            "the original palette PDF and the complete authoring runtime. "
            "Use the bundled asset manifest to choose available artwork.\n",
            1,
        )
        main.write_text(text, encoding="utf-8")

        visuals = staged / "references/visuals.md"
        text = visuals.read_text(encoding="utf-8").replace(
            "Inspect Light and Dark variants on the actual background. Choose concepts that\n"
            "explain the subject: Apps, Cloud-Lock, Chart-Up, Connectivity or Tools.",
            "Inspect the available Light artwork on the actual background. Choose concepts\n"
            "that explain the subject: Apps, Cloud-Lock or Chart-Up.",
        )
        visuals.write_text(text, encoding="utf-8")

        manifest_path = staged / "assets/asset-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["assets"] = [
            item for item in manifest["assets"] if "assets/" + item["path"] in FILES
        ]
        manifest["note"] = (
            "Cowork edition: three supplied Light illustrations and five official product icons. "
            "Original collection metadata records provenance; additional files are available "
            "only when supplied separately. Preserve native colors and aspect ratios. "
            "Product icons are for architecture, training and documentation. "
            "The contributor confirmed public redistribution of the supplied palette "
            "and illustrations. Microsoft graphics retain their original rights and "
            "applicable terms; the repository MIT license does not relicense them."
        )
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        files = validate(staged)
        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, destination)
        with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, "html-presentation/" + path.relative_to(staged).as_posix())
    return destination, archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=PROJECT / "skills/html-presentation")
    parser.add_argument("--output-dir", type=Path, default=PROJECT / "dist/cowork")
    args = parser.parse_args()
    try:
        folder, archive = package(args.source, args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Packaging failed: {error}\n")
    files = validate(folder)
    print(f"Packaged {len(files)} total files ({len(files) - 1} companions).")
    print(f"Uncompressed bundle: {sum(path.stat().st_size for path in files):,} bytes")
    print(f"Skill folder: {folder}\nUpload archive: {archive}")


if __name__ == "__main__":
    main()
