"""In-memory Azure AI Search shim for local PoC dev.

Drop-in replacement for `azure.search.documents.SearchClient.search()`
that returns canned hits from a local JSON corpus. Lets you smoke-test
RAG-flavoured agents offline.

Wire into your MCP server / agent code:

    if os.environ.get("USE_MOCK_SEARCH") == "1":
        from tests.mock_search import MockSearchClient as SearchClient
    else:
        from azure.search.documents import SearchClient

Corpus JSON shape (one file per index):

    {
      "index_name": "kb-reg-ez-corpus",
      "documents": [
        {"id": "doc1", "title": "Reg E §1005.11", "content": "...", "url": "...", "score_seed": 0.92},
        ...
      ]
    }

Scoring is intentionally trivial — substring match over `content` +
`title`, weighted by the optional `score_seed` field. Good enough to
exercise the agent's citation-formatting / chunk-selection logic; NOT
representative of hybrid/vector ranking. Do not use for relevance
benchmarking.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass
class _Hit:
    score: float
    doc: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        if key == "@search.score":
            return self.score
        return self.doc[key]

    def get(self, key: str, default: Any = None) -> Any:
        if key == "@search.score":
            return self.score
        return self.doc.get(key, default)


class MockSearchClient:
    """Stand-in for azure.search.documents.SearchClient.

    Constructor signature is loose — accepts whatever the real client
    accepts but only honours `index_name` and (optionally) the
    corpus path via env var `MOCK_SEARCH_CORPUS`.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        index_name: str | None = None,
        credential: Any = None,
        **kwargs: Any,
    ) -> None:
        self.index_name = index_name
        self._corpus_path = Path(os.environ.get("MOCK_SEARCH_CORPUS", "tests/sample-data/search-corpus.json"))
        self._docs = self._load_docs()

    def _load_docs(self) -> list[dict[str, Any]]:
        if not self._corpus_path.exists():
            return []
        data = json.loads(self._corpus_path.read_text(encoding="utf-8"))
        # Support either a single-index file or a list of indexes
        if isinstance(data, dict) and data.get("index_name") == self.index_name:
            return data.get("documents", [])
        if isinstance(data, list):
            for entry in data:
                if entry.get("index_name") == self.index_name:
                    return entry.get("documents", [])
        return data.get("documents", []) if isinstance(data, dict) else []

    def search(
        self,
        search_text: str | None = None,
        top: int = 5,
        select: Iterable[str] | None = None,
        **kwargs: Any,
    ) -> list[_Hit]:
        text = (search_text or "").lower().strip()
        terms = [t for t in re.findall(r"\w+", text) if len(t) > 2]
        hits: list[_Hit] = []
        for doc in self._docs:
            blob = " ".join(str(doc.get(f, "")) for f in ("title", "content", "summary")).lower()
            n_matches = sum(1 for t in terms if t in blob)
            if n_matches == 0 and terms:
                continue
            seed = float(doc.get("score_seed", 0.5))
            score = seed * (1 + 0.15 * n_matches)
            if select:
                slim = {k: doc.get(k) for k in select if k in doc}
                hits.append(_Hit(score=score, doc=slim))
            else:
                hits.append(_Hit(score=score, doc=dict(doc)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top]
