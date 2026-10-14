"""Canonical Azure AI Search Toolbox citation extraction.

Source of truth for the prose example in `../../SKILL.md § Extract Azure AI Search citations`.
Accepts the normalized MCP result object, not its JSON-RPC envelope.
"""

from collections.abc import Mapping
from typing import Any, TypedDict
from urllib.parse import urlsplit


class SearchCitation(TypedDict):
    title: str
    url: str


def extract_search_citations(result: Mapping[str, Any]) -> list[SearchCitation]:
    if result.get("isError"):
        raise ValueError("Cannot extract citations from an MCP error result")
    content = result.get("structuredContent")
    if not isinstance(content, Mapping) or not isinstance(content.get("documents"), list):
        raise ValueError("Expected structuredContent.documents from Azure AI Search")
    citations: list[SearchCitation] = []
    for document in content["documents"]:
        if not isinstance(document, Mapping):
            raise ValueError("Search document must be an object")
        title, url = document.get("title"), document.get("url")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Search citation requires a nonempty title")
        if (
            not isinstance(url, str)
            or not url
            or "\\" in url
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url)
        ):
            raise ValueError("Search citation requires a URL without whitespace or control characters")
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("Search citation requires an HTTP(S) URL without credentials")
        citations.append({"title": title, "url": url})
    return citations
