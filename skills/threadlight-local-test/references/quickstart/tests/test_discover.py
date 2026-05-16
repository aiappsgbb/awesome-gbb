"""Smoke tests for discover.py against fixture-poc.

Run with: ``pytest references/quickstart/tests`` from the skill root,
or ``pytest tests`` from inside ``references/quickstart``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from threadlight_quickstart.discover import PoCLayoutError, discover
from threadlight_quickstart.stub_tools import InMemoryStore, build_stub_tools

FIXTURE = Path(__file__).resolve().parent.parent / "fixture-poc"


def test_discover_finds_fixture():
    layout = discover(FIXTURE)
    assert layout.root == FIXTURE.resolve()
    assert layout.entity_names == ("tickets",)
    assert layout.skill_names == ("triage",)
    assert layout.spec_md is not None
    assert layout.demo_prompts_txt is not None
    assert layout.prep_guide_html is None  # not shipped in fixture


def test_discover_walks_up(tmp_path):
    nested = FIXTURE / "src" / "agent"
    layout = discover(nested)
    assert layout.root == FIXTURE.resolve()


def test_discover_raises_outside_poc(tmp_path):
    with pytest.raises(PoCLayoutError) as ei:
        discover(tmp_path)
    assert "specs/sample-data" in str(ei.value)


def test_discover_rejects_bad_json(tmp_path):
    (tmp_path / "specs" / "sample-data").mkdir(parents=True)
    (tmp_path / "specs" / "sample-data" / "bogus.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    with pytest.raises(PoCLayoutError) as ei:
        discover(tmp_path)
    assert "valid JSON" in str(ei.value)


def test_discover_rejects_non_array(tmp_path):
    (tmp_path / "specs" / "sample-data").mkdir(parents=True)
    (tmp_path / "specs" / "sample-data" / "obj.json").write_text(
        '{"a": 1}', encoding="utf-8"
    )
    with pytest.raises(PoCLayoutError) as ei:
        discover(tmp_path)
    assert "JSON array" in str(ei.value)


def test_in_memory_store_loads():
    store = InMemoryStore.load(FIXTURE / "specs" / "sample-data" / "tickets.json")
    assert len(store.records) == 5
    assert "T-1001" in store.records
    assert store.records["T-1001"]["status"] == "open"


def test_in_memory_store_filters():
    store = InMemoryStore.load(FIXTURE / "specs" / "sample-data" / "tickets.json")
    opens = store.list_all(status="open")
    assert len(opens) == 5
    closed = store.list_all(status="closed")
    assert closed == []


def test_in_memory_store_update_and_reset():
    path = FIXTURE / "specs" / "sample-data" / "tickets.json"
    store = InMemoryStore.load(path)
    store.update("T-1001", severity="urgent", assignee="oncall@example.com")
    assert store.records["T-1001"]["severity"] == "urgent"
    store.reset()
    assert store.records["T-1001"]["severity"] is None


def test_build_stub_tools_creates_crud_triple():
    layout = discover(FIXTURE)
    tools, stores = build_stub_tools(layout.sample_data_files)
    names = sorted(t.__name__ for t in tools)
    assert names == ["get_tickets", "list_tickets", "update_tickets"]
    assert set(stores.keys()) == {"tickets"}
