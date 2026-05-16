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


# ============================================================== schemas_for

def test_schemas_for_silently_drops_unknown_names(wiki: Wiki):
    from app.tools import schemas_for

    schemas = schemas_for(["list_pages", "definitely-not-a-tool"])

    names = {s["function"]["name"] for s in schemas}
    assert names == {"list_pages"}


# ============================================================ dispatch edges

def test_dispatch_non_object_json_args_returns_error(wiki: Wiki):
    out = dispatch(wiki, "list_pages", "42")

    assert out.startswith("ERROR")
    assert "JSON object" in out


def test_dispatch_list_json_args_returns_error(wiki: Wiki):
    out = dispatch(wiki, "list_pages", "[1, 2]")

    assert out.startswith("ERROR")


def test_dispatch_file_not_found_returns_error(wiki: Wiki):
    out = dispatch(wiki, "read_page", json.dumps({"name": "missing-page"}))

    assert out.startswith("ERROR")
    assert "missing-page" in out


def test_dispatch_unexpected_exception_returns_typed_error(wiki: Wiki, monkeypatch: pytest.MonkeyPatch):
    # Swap a handler with one that raises a non-Value/non-FileNotFound error;
    # dispatch should catch it and surface it as a tagged ERROR string instead
    # of crashing the agent loop.
    def boom(_w, _args):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(ALL_TOOLS["list_pages"], "handler", boom)

    out = dispatch(wiki, "list_pages", "{}")

    assert out.startswith("ERROR: unexpected RuntimeError")
    assert "kaboom" in out


def test_dispatch_empty_raw_args_defaults_to_empty_object(wiki: Wiki):
    out = dispatch(wiki, "list_pages", "")

    # No-arg tool succeeds when raw_args is empty.
    assert "(no wiki pages yet)" in out


# ============================================================ tool handlers

def test_list_pages_empty_returns_placeholder(wiki: Wiki):
    out = dispatch(wiki, "list_pages", "{}")

    assert out == "(no wiki pages yet)"


def test_list_pages_returns_newline_joined_slugs(wiki: Wiki):
    wiki.write_page("beta", "b")
    wiki.write_page("alpha", "a")

    out = dispatch(wiki, "list_pages", "{}")

    assert out.splitlines() == ["alpha", "beta"]


def test_read_page_returns_content(wiki: Wiki):
    wiki.write_page("alpha", "# Alpha\n\nbody")

    out = dispatch(wiki, "read_page", json.dumps({"name": "alpha"}))

    assert "# Alpha" in out


def test_write_page_returns_created_for_new_page(wiki: Wiki):
    out = dispatch(wiki, "write_page", json.dumps({"name": "alpha", "content": "# A"}))

    assert "created" in out
    assert "wiki/alpha.md" in out


def test_write_page_returns_updated_for_existing_page(wiki: Wiki):
    dispatch(wiki, "write_page", json.dumps({"name": "alpha", "content": "v1"}))

    out = dispatch(wiki, "write_page", json.dumps({"name": "alpha", "content": "v2"}))

    assert "updated" in out


def test_write_index_returns_char_count(wiki: Wiki):
    content = "# New Index\n"

    out = dispatch(wiki, "write_index", json.dumps({"content": content}))

    assert "updated index.md" in out
    assert str(len(content)) in out
    assert wiki.read_index() == content


def test_read_schema_returns_default_schema_content(wiki: Wiki):
    out = dispatch(wiki, "read_schema", "{}")

    assert out.startswith("# Wiki Schema")


def test_list_raw_empty_returns_placeholder(wiki: Wiki):
    out = dispatch(wiki, "list_raw", "{}")

    assert out == "(no raw sources)"


def test_list_raw_returns_sorted_slugs(wiki: Wiki):
    wiki.write_raw("beta", "b")
    wiki.write_raw("alpha", "a")

    out = dispatch(wiki, "list_raw", "{}")

    assert out.splitlines() == ["alpha", "beta"]


def test_read_raw_returns_content(wiki: Wiki):
    wiki.write_raw("src", "raw body")

    out = dispatch(wiki, "read_raw", json.dumps({"name": "src"}))

    assert out == "raw body"


def test_read_raw_missing_returns_error(wiki: Wiki):
    out = dispatch(wiki, "read_raw", json.dumps({"name": "missing"}))

    assert out.startswith("ERROR")


def test_finish_returns_finished_with_summary(wiki: Wiki):
    out = dispatch(wiki, "finish", json.dumps({"summary": "all done"}))

    assert out == "FINISHED: all done"


def test_finish_without_summary_returns_placeholder(wiki: Wiki):
    out = dispatch(wiki, "finish", "{}")

    assert out == "FINISHED: (no summary)"


# ============================================================= tool sets

def test_read_only_tools_excludes_every_mutating_tool():
    forbidden = {"write_page", "write_index", "append_log"}

    assert forbidden.isdisjoint(READ_ONLY_TOOLS)


def test_lint_tools_equals_all_tools():
    from app.tools import LINT_TOOLS

    assert set(LINT_TOOLS) == set(ALL_TOOLS.keys())


def test_every_tool_name_in_sets_exists_in_registry():
    from app.tools import INGEST_TOOLS, LINT_TOOLS

    for tool_set in (READ_ONLY_TOOLS, INGEST_TOOLS, LINT_TOOLS):
        for name in tool_set:
            assert name in ALL_TOOLS, f"Tool set references unknown tool {name!r}"
