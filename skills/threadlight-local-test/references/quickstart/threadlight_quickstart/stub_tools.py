"""In-memory JSON-backed tool factory.

For every ``<entity>.json`` under ``specs/sample-data/``, register three
plain Python tools that the MAF Agent can call:

    list_<entity>(**filters)         -> list[dict]
    get_<entity>(id: str)            -> dict | None
    update_<entity>(id, **fields)    -> dict

The underlying ``InMemoryStore`` reads each JSON file once at boot,
holds a dict-of-records keyed by record ``id``, and accepts mutations
that live for the process lifetime (next launch re-reads from disk —
no Cosmos, no SQLite, no migrations).

PoCs that need richer semantics (cross-entity joins, derived fields,
business rules) drop in ``tests/quickstart_tools.py`` exposing a
``register(agent_tools: list)`` callable; ``agent_wiring`` will call
it after the auto-tools are registered.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)


@dataclass
class InMemoryStore:
    """Dict-of-records keyed by record ``id`` for one entity."""

    name: str
    source: Path
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, source: Path) -> "InMemoryStore":
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{source} must be a JSON array")
        store = cls(name=source.stem, source=source)
        for i, rec in enumerate(raw):
            if not isinstance(rec, dict):
                raise ValueError(
                    f"{source}[{i}] must be an object, got {type(rec).__name__}"
                )
            rid = str(rec.get("id") or f"{source.stem}-{i}")
            rec.setdefault("id", rid)
            store.records[rid] = dict(rec)
        log.info("Loaded %d records into in-memory store '%s'", len(store.records), store.name)
        return store

    def reset(self) -> None:
        """Re-read records from disk, discarding any in-process mutations."""
        fresh = InMemoryStore.load(self.source)
        self.records = fresh.records

    def list_all(self, **filters: Any) -> list[dict[str, Any]]:
        if not filters:
            return list(self.records.values())
        return [r for r in self.records.values() if _matches(r, filters)]

    def get(self, id: str) -> dict[str, Any] | None:  # noqa: A002 - mirror tool sig
        return self.records.get(str(id))

    def update(self, id: str, **fields: Any) -> dict[str, Any]:  # noqa: A002
        rid = str(id)
        if rid not in self.records:
            raise KeyError(f"{self.name} record not found: {rid}")
        self.records[rid].update(fields)
        return self.records[rid]


def _matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    for k, want in filters.items():
        got = record.get(k)
        if want is None and got is None:
            continue
        if got != want:
            return False
    return True


def build_stub_tools(
    sample_data_files: list[Path] | tuple[Path, ...],
) -> tuple[list[Callable[..., Any]], dict[str, InMemoryStore]]:
    """Construct the list-of-tools + dict-of-stores for a PoC.

    The return shape is ``(tools, stores)`` where ``tools`` is a list of
    MAF-compatible ``@tool``-decorated callables and ``stores`` is the
    by-name registry of ``InMemoryStore`` instances. Callers register
    the tools on the Agent and keep the store registry for ``--check``
    or test introspection.
    """
    try:
        from agent_framework import tool  # type: ignore[import-not-found]
    except ImportError:
        # Allow discover/store-only smoke tests without the full SDK.
        tool = _identity_decorator  # type: ignore[assignment]

    stores: dict[str, InMemoryStore] = {}
    tools: list[Callable[..., Any]] = []

    for path in sample_data_files:
        store = InMemoryStore.load(path)
        stores[store.name] = store
        tools.extend(_make_crud_tools(store, tool))

    return tools, stores


def _identity_decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    return func


def _make_crud_tools(
    store: InMemoryStore,
    tool: Callable[[Callable[..., Any]], Callable[..., Any]],
) -> list[Callable[..., Any]]:
    """Create list_/get_/update_ tools for one entity store.

    Tool names follow the convention SPEC § 6 documents: ``list_<entity>``,
    ``get_<entity>``, ``update_<entity>``. Pattern 0 hard-codes the triple
    because every entity used in a demo eventually needs all three.
    """
    name = store.name

    @tool
    def list_records(**filters: Any) -> list[dict[str, Any]]:  # noqa: ARG001
        """List records matching the given filters (e.g. status='open').

        Empty filter set returns every record. Filter values are matched
        with equality only — no fuzzy or substring semantics in v1.
        """
        return store.list_all(**filters)

    list_records.__name__ = f"list_{name}"
    list_records.__doc__ = (
        f"List `{name}` records. Pass kwargs to filter by equality "
        f"(e.g. `status='open'`). No filters → all records."
    )

    @tool
    def get_record(id: str) -> dict[str, Any] | None:  # noqa: A002
        """Get a single record by id, or None."""
        return store.get(id)

    get_record.__name__ = f"get_{name}"
    get_record.__doc__ = f"Get a single `{name}` record by id, or None."

    @tool
    def update_record(id: str, **fields: Any) -> dict[str, Any]:  # noqa: A002
        """Update fields on a record and return the mutated record."""
        return store.update(id, **fields)

    update_record.__name__ = f"update_{name}"
    update_record.__doc__ = (
        f"Update fields on one `{name}` record (in-memory; reset every "
        f"`python -m threadlight_quickstart` launch)."
    )

    return [list_records, get_record, update_record]
