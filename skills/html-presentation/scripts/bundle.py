#!/usr/bin/env python3
"""Embed local presentation dependencies without introducing a build toolchain."""

import argparse
import base64
from html import escape
from html.parser import HTMLParser
import mimetypes
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


class BundleError(ValueError):
    pass


CLASSIC_SCRIPT_TYPES = {"", "text/javascript", "application/javascript", "text/ecmascript", "application/ecmascript"}
DATA_SCRIPT_TYPES = {"application/json", "application/ld+json"}
SCRIPT_TOKENS = re.compile(
    r"""//[^\r\n]*|/\*[\s\S]*?\*/|'(?:\\[\s\S]|[^'\\])*'|"(?:\\[\s\S]|[^"\\])*"|"""
    r"""(?P<import>(?<![\w$.])import\b(?:\s|/\*[\s\S]*?\*/|//[^\r\n]*(?:[\r\n]|$))*(?=[({*'"]))"""
)


def get_script_type(attrs):
    kinds = [value or "" for name, value in attrs if name == "type"]
    if len(kinds) > 1:
        raise BundleError("Script type must be declared once.")
    return kinds[0] if kinds else ""


def validate_script(text, script_type):
    kind = script_type.strip().lower()
    if kind in DATA_SCRIPT_TYPES:
        return
    if kind == "module":
        raise BundleError("Module scripts are unsupported; use a classic standalone script.")
    if kind not in CLASSIC_SCRIPT_TYPES:
        raise BundleError(f"Unsupported script type: {script_type}")
    if any(match.group("import") for match in SCRIPT_TOKENS.finditer(text)):
        raise BundleError("JavaScript imports are unsupported; use a standalone script.")


class Bundler(HTMLParser):
    def __init__(self, source, root):
        super().__init__(convert_charrefs=False)
        self.source = source.resolve()
        self.root = root.resolve()
        self.parts = []
        self.dependencies = set()
        self.inline_style = False
        self.inline_style_parts = []
        self.script_type = None
        self.script_parts = []
        self.external_script = False

    def local_path(self, url, base):
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc:
            raise BundleError(f"Remote or unsupported dependency: {url}")
        if not parsed.path or parsed.query:
            raise BundleError(f"Unsupported asset URL: {url}")
        path = (base / unquote(parsed.path)).resolve()
        if not path.is_relative_to(self.root):
            raise BundleError(f"Asset escapes --asset-root: {url}")
        if not path.is_file():
            raise BundleError(f"Asset not found: {path}")
        self.dependencies.add(path)
        return path

    def data_url(self, url, base):
        if url.startswith("data:"):
            return url
        path = self.local_path(url, base)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}" + (f"#{urlsplit(url).fragment}" if urlsplit(url).fragment else "")

    def css(self, text, base):
        if re.search(r"@import\b", text, re.I):
            raise BundleError("CSS @import is unsupported; link stylesheets directly.")
        if re.search(r"</style", text, re.I):
            raise BundleError("Stylesheet contains an unsafe closing style tag.")

        def replace(match):
            url = match.group(2).strip()
            if url.startswith("#"):
                return match.group(0)
            return f'url("{self.data_url(url, base)}")'

        return re.sub(r"url\(\s*(['\"]?)(.*?)\1\s*\)", replace, text, flags=re.I)

    def handle_decl(self, decl):
        self.parts.append(f"<!{decl}>")

    def handle_comment(self, data):
        self.parts.append(f"<!--{data}-->")

    def handle_data(self, data):
        if self.script_type is not None:
            if not self.external_script:
                self.script_parts.append(data)
        elif self.inline_style:
            self.inline_style_parts.append(data)
        else:
            self.parts.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")

    def handle_starttag(self, tag, attrs):
        self.start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self.start(tag, attrs, True)

    def start(self, tag, attrs, closed):
        values = dict(attrs)
        base = self.source.parent
        if tag in {"iframe", "object", "embed"}:
            raise BundleError(f"Unsupported embedded resource: <{tag}>")
        if "srcset" in values or "imagesrcset" in values:
            raise BundleError("srcset is unsupported; use a local img src.")
        if tag == "link":
            if values.get("rel", "").lower() == "stylesheet":
                path = self.local_path(values.get("href", ""), base)
                self.parts.append(f"<style>{self.css(path.read_text(encoding='utf-8'), path.parent)}</style>")
                return
            if values.get("rel", "").lower() in {"preload", "prefetch", "preconnect", "dns-prefetch", "modulepreload"}:
                raise BundleError("Network hints are not needed in an offline presentation.")
        if tag == "script":
            if closed:
                raise BundleError("Use a paired opening and closing script tag.")
            self.script_type = get_script_type(attrs)
            validate_script("", self.script_type)
            self.script_parts = []
            self.external_script = "src" in values
            if self.external_script:
                path = self.local_path(values["src"], base)
                if "async" in values:
                    raise BundleError("Async scripts are unsupported; use defer for a presentation runtime.")
                text = path.read_text(encoding="utf-8")
                if re.search(r"</script", text, re.I):
                    raise BundleError("Script contains an unsafe closing script tag.")
                if "defer" in values and self.script_type.strip().lower() not in DATA_SCRIPT_TYPES:
                    text = 'document.addEventListener("DOMContentLoaded", () => {\n' + text + '\n}, {once: true});'
                self.script_parts.append(text)
                attrs = [(name, value) for name, value in attrs if name not in {"src", "defer"}]
        if tag == "style":
            self.inline_style = True
            self.inline_style_parts = []
        rendered = []
        for name, value in attrs:
            if value is not None:
                if name in {"src", "poster"} or (tag in {"image", "use"} and name in {"href", "xlink:href"} and not value.startswith("#")):
                    value = self.data_url(value, base)
                elif tag == "link" and name == "href":
                    value = self.data_url(value, base)
                elif name == "style":
                    value = self.css(value, base)
                rendered.append(f'{name}="{escape(value, quote=True)}"')
            else:
                rendered.append(name)
        self.parts.append("<" + tag + (" " + " ".join(rendered) if rendered else "") + ("/>" if closed else ">"))

    def handle_endtag(self, tag):
        if tag == "script" and self.script_type is not None:
            text = "".join(self.script_parts)
            validate_script(text, self.script_type)
            self.parts.append(text)
            self.script_type = None
            self.external_script = False
        if tag == "style" and self.inline_style:
            self.parts.append(self.css("".join(self.inline_style_parts), self.source.parent))
            self.inline_style = False
        self.parts.append(f"</{tag}>")


def bundle(source, output, root):
    source, output, root = Path(source).resolve(), Path(output).resolve(), Path(root).resolve()
    if source == output:
        raise BundleError("Source and output must differ; preserve editable source.")
    if not source.is_relative_to(root):
        raise BundleError("Source must be inside --asset-root.")
    parser = Bundler(source, root)
    parser.feed(source.read_text(encoding="utf-8"))
    parser.close()
    if parser.script_type is not None:
        raise BundleError("Script tag is not closed.")
    result = "".join(parser.parts)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8")
    return len(parser.dependencies)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("source", type=Path)
    cli.add_argument("output", type=Path)
    cli.add_argument("--asset-root", required=True, type=Path)
    args = cli.parse_args()
    try:
        count = bundle(args.source, args.output, args.asset_root)
    except (BundleError, OSError, UnicodeError) as error:
        cli.exit(1, f"Bundle failed: {error}\n")
    print(f"Embedded {count} local dependencies into {args.output}")


if __name__ == "__main__":
    main()
