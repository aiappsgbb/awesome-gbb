import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "package_cowork.py"
SPEC = importlib.util.spec_from_file_location("package_cowork", SCRIPT)
packager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packager)
FILES, PROJECT, package, validate = (
    packager.FILES, packager.PROJECT, packager.package, packager.validate
)


class CoworkPackageTests(unittest.TestCase):
    def test_portable_twenty_file_archive(self):
        source = PROJECT / "skills/html-presentation"
        before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        with tempfile.TemporaryDirectory() as temporary:
            folder, archive = package(source, Path(temporary) / "output")
            self.assertEqual(len(validate(folder)), 20)
            for name in FILES:
                if name not in {"SKILL.md", "references/visuals.md", "assets/asset-manifest.json"}:
                    self.assertEqual((folder / name).read_bytes(), (source / name).read_bytes())
            with zipfile.ZipFile(archive) as packed:
                self.assertEqual(len(packed.namelist()), 20)
                self.assertIsNone(packed.testzip())
                packed.extractall(Path(temporary) / "extracted")
            extracted = Path(temporary) / "extracted/html-presentation"
            self.assertEqual(len(validate(extracted)), 20)
            for name in FILES:
                self.assertEqual(
                    hashlib.sha256((folder / name).read_bytes()).digest(),
                    hashlib.sha256((extracted / name).read_bytes()).digest(),
                )
            authoring = Path(temporary) / "authoring"
            authoring.mkdir()
            for name in FILES:
                if name.startswith("assets/"):
                    target = authoring / name.removeprefix("assets/")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((extracted / name).read_bytes())
            artwork = [name.removeprefix("assets/") for name in FILES
                       if name.startswith(("assets/icons/", "assets/illustrations/"))]
            template = (authoring / "template.html").read_text()
            images = "".join(f'<img src="{name}" alt="Synthetic artwork probe">' for name in artwork)
            source_html = authoring / "story.source.html"
            source_html.write_text(template.replace("</main>", images + "</main>"))
            output_html = authoring / "story.html"
            for command in (
                [sys.executable, str(extracted / "scripts/bundle.py"),
                 str(source_html), str(output_html), "--asset-root", str(authoring)],
                [sys.executable, str(extracted / "scripts/check_story.py"), str(output_html)],
            ):
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            bundled = output_html.read_text()
            self.assertEqual(bundled.count("data:image/png;base64,"), 3)
            self.assertEqual(bundled.count("data:image/svg+xml;base64,"), 5)
            with self.assertRaisesRegex(ValueError, "Output already exists"):
                package(source, Path(temporary) / "output")
            (extracted / "extra.txt").write_text("unexpected")
            with self.assertRaisesRegex(ValueError, "file set"):
                validate(extracted)
        after = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_instruction_limit_and_manifest_integrity(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder, _ = package(PROJECT / "skills/html-presentation", Path(temporary) / "output")
            main = folder / "SKILL.md"
            original = main.read_text()
            self.assertLess(len(original), 20_000)
            main.write_text(original + " " * (20_000 - len(original)))
            with self.assertRaisesRegex(ValueError, "instruction limit"):
                validate(folder)
            main.write_text(original)
            manifest_path = folder / "assets/asset-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["assets"].pop()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "selected artwork"):
                validate(folder)

    def test_companion_size_limits(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder, _ = package(PROJECT / "skills/html-presentation", Path(temporary) / "output")
            runtime = folder / "assets/story.js"
            original = runtime.read_bytes()
            runtime.write_bytes(b" " * 5_000_001)
            with self.assertRaisesRegex(ValueError, "companion exceeds"):
                validate(folder)
            runtime.write_bytes(original)
            for name in ("assets/story.css", "assets/story.js", "assets/template.html"):
                (folder / name).write_bytes(b" " * 3_500_000)
            with self.assertRaisesRegex(ValueError, "Companions exceed"):
                validate(folder)


if __name__ == "__main__":
    unittest.main()
