#!/usr/bin/env python3
"""Check a bundled visual story; browser and editorial review are separate."""

import argparse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re

from bundle import BundleError, get_script_type, validate_script


class StoryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.chapter_ids = []
        self.source_targets = []
        self.fragments = []
        self.errors = []
        self.has_title = False
        self.has_lang = False
        self.has_viewport = False
        self.has_main = False
        self.styles = []
        self.in_style = False
        self.script_type = None
        self.script_parts = []
        self.script_type_valid = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if "data-chapter" in values:
            if not values.get("id"):
                self.errors.append("Each chapter needs a stable id.")
            if "hidden" in values:
                self.errors.append("Core chapters must be visible without JavaScript.")
            self.chapter_ids.append(values.get("id"))
        if tag == "html":
            self.has_lang = bool(values.get("lang"))
        if tag == "main":
            self.has_main = True
        if tag == "title":
            self.has_title = True
        if tag == "meta" and values.get("name") == "viewport":
            self.has_viewport = True
        if tag == "img" and "alt" not in values:
            self.errors.append("Image lacks alt text.")
        if "data-source" in values:
            self.source_targets.append(values["data-source"])
        if "data-inspect" in values:
            self.source_targets.append(values["data-inspect"])
            if "disabled" not in values:
                self.errors.append("Inspector controls must start disabled until enhanced.")
        if "data-inspection" in values and "hidden" in values:
            self.errors.append("Inspector explanations must be readable without JavaScript.")
        if values.get("href", "").startswith("#") and values["href"] != "#":
            self.fragments.append(values["href"][1:])
        if "srcset" in values or "imagesrcset" in values:
            self.errors.append("Unbundled srcset remains.")
        for key in ("src", "poster"):
            if key in values and not values[key].startswith("data:"):
                self.errors.append(f"Unbundled {tag} {key}: {values[key]}")
        if tag == "link" and values.get("href") and not values["href"].startswith("data:"):
            self.errors.append("Unbundled link dependency remains.")
        if tag in {"iframe", "object", "embed"}:
            self.errors.append(f"Unsupported embedded resource: {tag}")
        if tag in {"image", "use"}:
            for key in ("href", "xlink:href"):
                if key in values and not values[key].startswith(("data:", "#")):
                    self.errors.append(f"Unbundled SVG resource: {values[key]}")
        if tag == "style":
            self.in_style = True
        if values.get("style"):
            self.styles.append(values["style"])
        if tag == "script":
            self.script_type = ""
            self.script_parts = []
            self.script_type_valid = False
            try:
                self.script_type = get_script_type(attrs)
                validate_script("", self.script_type)
                self.script_type_valid = True
            except BundleError as error:
                self.errors.append(str(error))

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag == "script" and self.script_type is not None:
            if self.script_type_valid:
                try:
                    validate_script("".join(self.script_parts), self.script_type)
                except BundleError as error:
                    self.errors.append(str(error))
            self.script_type = None
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.script_type is not None:
            self.script_parts.append(data)
        elif self.in_style:
            self.styles.append(data)


def check(path):
    parser = StoryParser()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    parser.close()
    errors = parser.errors
    if parser.script_type is not None:
        errors.append("Script tag is not closed.")
    ids = set(parser.ids)
    for value, count in Counter(parser.ids).items():
        if count > 1:
            errors.append(f"Duplicate id: {value}")
    for value in parser.source_targets + parser.fragments:
        if value not in ids:
            errors.append(f"Broken local target: {value}")
    if not parser.has_title or not parser.has_lang or not parser.has_viewport:
        errors.append("Title, language and viewport metadata are required.")
    if not parser.has_main or not parser.chapter_ids:
        errors.append("A main landmark and stable story chapters are required.")
    css = "\n".join(parser.styles)
    if re.search(r"@import\b", css, re.I):
        errors.append("CSS import remains.")
    for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, re.I):
        if not match[2].strip().startswith(("data:", "#")):
            errors.append(f"Unbundled CSS dependency: {match[2]}")
    for color in ("#1A00E2", "#0D0061", "#FFFFFF"):
        if color.lower() not in css.lower():
            errors.append(f"Approved palette token absent: {color}")
    return errors, len(parser.chapter_ids)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("presentation", type=Path)
    args = cli.parse_args()
    try:
        errors, count = check(args.presentation)
    except (OSError, UnicodeError) as error:
        cli.exit(1, f"Check failed: {error}\n")
    if errors:
        cli.exit(1, "Static contract failed:\n" + "\n".join(f"- {error}" for error in errors) + "\n")
    print(f"Static contract passed: {count} story chapters. Browser/editorial review still required.")


if __name__ == "__main__":
    main()
