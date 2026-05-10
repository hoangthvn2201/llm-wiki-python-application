import json
from pathlib import Path

import pytest

from app.tools import (
    ALL_TOOLS,
    INGEST_TOOLS,
    READ_ONLY_TOOLS,
    dispatch,
    schemas_for,
)
from app.wiki import Wiki


@pytest.fixture
def wiki(tmp_path: Path) -> Wiki:
    w = Wiki(tmp_path / "ws")
    w.ensure()
    return w


def test_schemas_for_filters_to_allowed(wiki: Wiki):
    schemas = schemas_for(READ_ONLY_TOOLS)
    names = {s["function"]["name"] for s in schemas}
    assert names == set(READ_ONLY_TOOLS)
    # Read-only set excludes write_page.
    assert "write_page" not in names


def test_dispatch_unknown_tool_returns_error_string(wiki: Wiki):
    out = dispatch(wiki, "nonexistent", "{}")
    assert out.startswith("ERROR")


def test_dispatch_invalid_json_returns_error(wiki: Wiki):
    out = dispatch(wiki, "list_pages", "{not json")
    assert out.startswith("ERROR")


def test_write_page_via_dispatch_then_list(wiki: Wiki):
    args = json.dumps({"name": "alpha", "content": "# Alpha"})
    out = dispatch(wiki, "write_page", args)
    assert "created" in out
    pages = dispatch(wiki, "list_pages", "{}")
    assert "alpha" in pages


def test_write_page_invalid_slug_returns_error(wiki: Wiki):
    args = json.dumps({"name": "Bad Name", "content": "x"})
    out = dispatch(wiki, "write_page", args)
    assert out.startswith("ERROR")


def test_read_index_via_dispatch(wiki: Wiki):
    out = dispatch(wiki, "read_index", "{}")
    assert "# Index" in out


def test_append_log_via_dispatch(wiki: Wiki):
    out = dispatch(wiki, "append_log", json.dumps({"entry": "## [2026-01-01] ingest | x\n\nbody"}))
    assert "appended" in out
    log = wiki.read_log()
    assert "## [2026-01-01] ingest | x" in log


def test_all_tool_schemas_well_formed():
    for name, tool in ALL_TOOLS.items():
        schema = tool.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == name
        assert "parameters" in schema["function"]
        assert schema["function"]["parameters"]["type"] == "object"


def test_ingest_tools_is_superset_of_read_only():
    assert set(READ_ONLY_TOOLS).issubset(set(INGEST_TOOLS))
