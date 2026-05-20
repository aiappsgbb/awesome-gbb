"""Tests for cli._load_env_local + ui_streamlit._append_transcript."""

from __future__ import annotations

import json
import os
from pathlib import Path

from threadlight_quickstart import cli


def test_load_env_local_parses_basic(tmp_path, monkeypatch):
    (tmp_path / ".env.local").write_text(
        "# a comment\n"
        "FOO=bar\n"
        "BAZ=\"quoted value\"\n"
        "export QUX='single quoted'\n"
        "\n"
        "MULTI_WORD=hello world\n",
        encoding="utf-8",
    )
    for k in ("FOO", "BAZ", "QUX", "MULTI_WORD"):
        monkeypatch.delenv(k, raising=False)
    n = cli._load_env_local(tmp_path)
    assert n == 4
    assert os.environ["FOO"] == "bar"
    assert os.environ["BAZ"] == "quoted value"
    assert os.environ["QUX"] == "single quoted"
    assert os.environ["MULTI_WORD"] == "hello world"


def test_load_env_local_existing_env_wins(tmp_path, monkeypatch):
    (tmp_path / ".env.local").write_text("FOO=from_file\n", encoding="utf-8")
    monkeypatch.setenv("FOO", "from_shell")
    n = cli._load_env_local(tmp_path)
    assert n == 0
    assert os.environ["FOO"] == "from_shell"


def test_load_env_local_missing_file_is_noop(tmp_path):
    assert cli._load_env_local(tmp_path) == 0


def test_load_env_local_ignores_malformed_lines(tmp_path, monkeypatch):
    (tmp_path / ".env.local").write_text(
        "= no key\n"
        "lower_case_ignored=because-of-regex\n"
        "VALID=ok\n"
        "STRAY_NO_EQUALS\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("VALID", raising=False)
    n = cli._load_env_local(tmp_path)
    assert n == 1
    assert os.environ["VALID"] == "ok"


def test_append_transcript_writes_row(tmp_path, monkeypatch):
    # Import locally so the test only exercises the helper.
    monkeypatch.delenv("THREADLIGHT_QUICKSTART_NO_TRANSCRIPT", raising=False)
    import importlib.util
    here = Path(__file__).resolve().parent.parent / "threadlight_quickstart" / "ui_streamlit.py"
    spec = importlib.util.spec_from_file_location("ui_streamlit_under_test", here)
    mod = importlib.util.module_from_spec(spec)
    # ui_streamlit imports streamlit at module load; skip if streamlit is absent.
    try:
        spec.loader.exec_module(mod)
    except (ImportError, ModuleNotFoundError):
        import pytest
        pytest.skip("streamlit not installed; skipping ui_streamlit smoke test")
    mod._append_transcript(tmp_path, "what is the urgent ticket?", "T-1001 is urgent.")
    path = tmp_path / "tests" / "quickstart.jsonl"
    assert path.is_file()
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["query"] == "what is the urgent ticket?"
    assert row["response"] == "T-1001 is urgent."
    assert "ts" in row


def test_append_transcript_disable_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("THREADLIGHT_QUICKSTART_NO_TRANSCRIPT", "1")
    import importlib.util
    here = Path(__file__).resolve().parent.parent / "threadlight_quickstart" / "ui_streamlit.py"
    spec = importlib.util.spec_from_file_location("ui_streamlit_under_test", here)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except (ImportError, ModuleNotFoundError):
        import pytest
        pytest.skip("streamlit not installed; skipping ui_streamlit smoke test")
    mod._append_transcript(tmp_path, "q", "r")
    assert not (tmp_path / "tests" / "quickstart.jsonl").exists()
