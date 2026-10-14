import shutil
import tempfile
import unittest
from pathlib import Path

from bundle import BundleError, bundle
from check_story import check


ASSETS = Path(__file__).resolve().parents[1] / "assets"
VALID_STORY = """<!doctype html>
<html lang="en"><head><title>Story</title>
<meta name="viewport" content="width=device-width">
<style>:root{--electric:#1A00E2;--navy:#0D0061;--white:#FFFFFF}</style>
</head><body><nav><a href="#start">Start</a></nav><main>
<section data-chapter id="start"><h1>Thesis</h1></section>
</main></body></html>"""


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.html"
        self.output = self.root / "output.html"

    def tearDown(self):
        self.temp.cleanup()

    def run_bundle(self, content):
        self.source.write_text(content, encoding="utf-8")
        bundle(self.source, self.output, self.root)
        return self.output.read_text(encoding="utf-8")

    def test_local_dependencies_and_citations(self):
        (self.root / "image.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        (self.root / "style.css").write_text('body{background:url("image.svg")}')
        (self.root / "story.js").write_text('document.body.dataset.ready="yes";')
        result = self.run_bundle('<!doctype html><link rel="stylesheet" href="style.css"><img src="image.svg" alt=""><script src="story.js" defer></script><a href="https://learn.microsoft.com">Source</a>')
        self.assertIn("data:image/svg+xml;base64,", result)
        self.assertIn("dataset.ready", result)
        self.assertIn('addEventListener("DOMContentLoaded"', result)
        self.assertIn('href="https://learn.microsoft.com"', result)
        self.assertNotIn('src="story.js"', result)

    def test_inline_css(self):
        (self.root / "image.png").write_bytes(b"fixture")
        result = self.run_bundle('<style>body{background:url(image.png)}</style>')
        self.assertIn("data:image/png;base64,", result)

    def test_reject_remote_missing_and_escaping_assets(self):
        for url in ("https://example.com/image.png", "//example.com/image.png", "missing.png", "../outside.png"):
            with self.subTest(url=url), self.assertRaises(BundleError):
                self.run_bundle(f'<img src="{url}" alt="">')

    def test_reject_unsupported_patterns(self):
        for content in ('<style>@import "theme.css";</style>', '<img srcset="a.png 1x">', '<iframe src="page.html"></iframe>'):
            with self.subTest(content=content), self.assertRaises(BundleError):
                self.run_bundle(content)

    def test_keep_svg_fragment(self):
        (self.root / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        result = self.run_bundle('<svg><use href="icon.svg#shape"/></svg>')
        self.assertIn("#shape", result)

    def test_static_check_detects_broken_contract(self):
        self.output.write_text('<html><section data-chapter id="same"></section><img src="remote.png"><p id="same"></p><a href="#missing">x</a></html>')
        errors, count = check(self.output)
        self.assertEqual(count, 1)
        self.assertTrue(any("Duplicate" in error for error in errors))
        self.assertTrue(any("Broken local" in error for error in errors))
        self.assertTrue(any("Unbundled" in error for error in errors))

    def test_continuous_story_contract(self):
        self.output.write_text(VALID_STORY)
        errors, count = check(self.output)
        self.assertEqual(errors, [])
        self.assertEqual(count, 1)

    def test_report_inaccessible_core_content(self):
        self.output.write_text('<html lang="en"><main><section data-chapter id="start" hidden></section><button data-inspect="missing">Inspect</button><div data-inspection hidden>Detail</div></main></html>')
        errors, _ = check(self.output)
        for message in ("chapters must", "start disabled", "explanations must", "Broken local"):
            self.assertTrue(any(message in error for error in errors), message)

    def test_reject_inline_modules_and_imports_in_both_tools(self):
        scripts = (
            '<script type="module">import "https://example.invalid/remote.js";</script>',
            '<script type="MODULE">document.body.dataset.ready="yes";</script>',
            '<script type="module" type="application/json">import "remote.js";</script>',
            '<script>import("https://example.invalid/remote.js");</script>',
            '<script>import /* dependency */ ("local.js");</script>',
            '<script>import // dependency\n("local.js");</script>',
            '<script>import {value} from "local.js";</script>',
            '<script>import "local.js";</script>',
            '<script>const message = `${import("local.js")}`;</script>',
        )
        for script in scripts:
            with self.subTest(script=script):
                with self.assertRaisesRegex(BundleError, "Module scripts|JavaScript imports|Script type"):
                    self.run_bundle(VALID_STORY.replace("</head>", script + "</head>"))
                self.output.write_text(VALID_STORY.replace("</head>", script + "</head>"))
                errors, _ = check(self.output)
                self.assertTrue(any("Module scripts" in error or "JavaScript imports" in error or "Script type" in error for error in errors))

    def test_reject_external_modules_imports_and_async_scripts(self):
        runtime = self.root / "story.js"
        for attrs, text in (
            ('type="module"', 'document.body.dataset.ready="yes";'),
            ("", 'import("local.js");'),
            ("", 'import /* dependency */ ("local.js");'),
            ("async", 'document.body.dataset.ready="yes";'),
        ):
            with self.subTest(attrs=attrs, text=text), self.assertRaises(BundleError):
                runtime.write_text(text)
                self.run_bundle(f'<script src="story.js" {attrs}></script>')

    def test_standalone_scripts_keep_attributes_and_ignore_strings_and_comments(self):
        text = """// import("unused.js");
/* import "unused.js"; */
document.body.dataset.message = "import('unused.js')";
document.body.dataset.ready = "yes";"""
        (self.root / "story.js").write_text(text)
        for script in (
            f'<script id="runtime" type="text/javascript">{text}</script>',
            '<script id="runtime" type="text/javascript" src="story.js" defer></script>',
        ):
            with self.subTest(script=script):
                result = self.run_bundle(VALID_STORY.replace("</head>", script + "</head>"))
                self.assertIn('id="runtime" type="text/javascript"', result)
                self.assertIn(text, result)
                self.assertEqual(check(self.output)[0], [])

    def test_json_scripts_remain_data(self):
        data = '{"example":"import(\'unused.js\')"}'
        (self.root / "data.json").write_text(data)
        for kind in ("application/json", "application/ld+json"):
            for script in (
                f'<script id="fixture" type="{kind}">{data}</script>',
                f'<script id="fixture" type="{kind}" src="data.json" defer></script>',
            ):
                with self.subTest(script=script):
                    result = self.run_bundle(VALID_STORY.replace("</head>", script + "</head>"))
                    self.assertIn(f'<script id="fixture" type="{kind}">{data}</script>', result)
                    self.assertEqual(check(self.output)[0], [])

    def test_reject_unsupported_and_unclosed_scripts(self):
        for script in (
            '<script type="importmap">{"imports":{"x":"https://example.invalid/x.js"}}</script>',
            '<script type="speculationrules">{"prefetch":[]}</script>',
            '<script>document.body.dataset.ready="yes";',
            '<script/>',
        ):
            with self.subTest(script=script):
                with self.assertRaises(BundleError):
                    self.run_bundle(VALID_STORY.replace("</head>", script + "</head>"))
                self.output.write_text(VALID_STORY.replace("</head>", script + "</head>"))
                self.assertTrue(any("script" in error.lower() for error in check(self.output)[0]))

    def test_static_check_inspects_style_attributes_and_import_case(self):
        for content, expected in (
            ('<p style="background:url(https://example.invalid/image.png)">Text</p>', "Unbundled CSS"),
            ('<style>@IMPORT "https://example.invalid/style.css";</style>', "CSS import"),
            ('<link rel="preload" imagesrcset="remote.png 1x">', "Unbundled srcset"),
        ):
            with self.subTest(content=content):
                self.output.write_text(VALID_STORY.replace("</main>", content + "</main>"))
                self.assertTrue(any(expected in error for error in check(self.output)[0]))

    def test_starter_and_separately_installed_asset_staging(self):
        installed = self.root / "installed-skill"
        authoring = self.root / "workspace" / "presentation"
        installed.mkdir()
        authoring.mkdir(parents=True)
        files = ("template.html", "palette.css", "story.css", "story.js",
                 "asset-manifest.json", "Azure-ColorPalette-2026.pdf")
        for filename in files:
            shutil.copyfile(ASSETS / filename, installed / filename)
            target = "story.source.html" if filename == "template.html" else filename
            shutil.copyfile(installed / filename, authoring / target)
        image = "Azure-Illcon-Light-Apps-512.png"
        (installed / "illustrations").mkdir()
        (authoring / "illustrations").mkdir()
        shutil.copyfile(ASSETS / "illustrations" / image, installed / "illustrations" / image)
        shutil.copyfile(installed / "illustrations" / image, authoring / "illustrations" / image)
        source, output = authoring / "story.source.html", authoring / "story.html"
        original = source.read_text()
        fixture = original.replace("</main>", f'<img src="illustrations/{image}" alt="Workflow illustration"></main>')
        source.write_text(fixture)
        self.assertEqual(bundle(source, output, authoring), 4)
        self.assertEqual(check(output), ([], 3))
        result = output.read_text()
        self.assertIn("data:image/png;base64,", result)
        self.assertEqual(result.count('data-inspect="'), 2)
        self.assertEqual(result.count(" data-inspection>"), 2)
        self.assertIn('data-source="source-pilot"', result)
        self.assertEqual((installed / "template.html").read_text(), original)
        source.write_text(fixture.replace(f'illustrations/{image}', f'../../installed-skill/illustrations/{image}'))
        with self.assertRaisesRegex(BundleError, "escapes --asset-root"):
            bundle(source, output, authoring)


if __name__ == "__main__":
    unittest.main()
