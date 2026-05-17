"""Cross-cutting tests — security, the read-only contract, and the trace contract.

These ride on top of the per-function tests and pin behaviour that spans
modules. If any one of them ever fails, the production code has crossed a
boundary it must not cross.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import llm, main, operations
from app.main import app
from app.schemas import ChatMessage
from app.tools import READ_ONLY_TOOLS, dispatch
from app.wiki import Wiki
from tests.test_llm import _FakeClient, _FakeMessage, _FakeToolCall


# ================================================================ fixtures

@pytest.fixture
def wiki(tmp_path: Path) -> Wiki:
    w = Wiki(tmp_path / "ws")
    w.ensure()
    return w


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point both operations and main at a temp workspace."""
    ws = tmp_path / "ws"
    Wiki(ws).ensure()
    settings = SimpleNamespace(
        workspace_path=ws,
        max_tool_iterations=25,
        max_tool_iterations_ingest=25,
        max_tool_iterations_query=25,
        max_tool_iterations_chat=25,
        max_tool_iterations_lint=50,
        max_tool_iterations_hallucination=150,
    )
    monkeypatch.setattr(operations, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return ws


# ================================================================== security

@pytest.mark.parametrize("name", ["..", "../escape", "Bad Slug", "etc/passwd", ""])
def test_path_traversal_rejected_at_wiki_layer(wiki: Wiki, name: str):
    with pytest.raises(ValueError):
        wiki.read_page(name)


@pytest.mark.parametrize("name", ["..", "../escape", "Bad Slug"])
def test_path_traversal_rejected_via_dispatch(wiki: Wiki, name: str):
    out = dispatch(wiki, "read_page", json.dumps({"name": name}))

    assert out.startswith("ERROR")


def test_path_traversal_rejected_via_http_route(workspace: Path):
    # Uppercase / spaces flow through to the slug validator and the
    # `(ValueError, FileNotFoundError)` handler maps to 404.
    client = TestClient(app)

    res = client.get("/api/page/Bad")

    assert res.status_code == 404


def test_write_raw_also_rejects_bad_slug(wiki: Wiki):
    # Pin that the boundary is consistent across read AND write entry points.
    with pytest.raises(ValueError):
        wiki.write_raw("../escape", "x")


# ====================================================== read-only contract

def test_schemas_for_read_only_excludes_every_mutating_tool():
    from app.tools import schemas_for

    schemas = schemas_for(READ_ONLY_TOOLS)
    names = {s["function"]["name"] for s in schemas}

    for forbidden in ("write_page", "write_index", "append_log"):
        assert forbidden not in names


def test_chat_never_exposes_write_tools_to_the_llm(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    # End-to-end: drive operations.chat through the real run_loop with a
    # scripted fake client. Assert that the `tools` array we send to the
    # model never names a mutating tool — even when the user explicitly
    # asks to write something. That's the actual enforcement boundary.
    fake = _FakeClient([_FakeMessage(content="I can't write — use Ingest.")])
    monkeypatch.setattr(llm, "_client", lambda: fake)

    operations.chat([ChatMessage(role="user", content="please write a page for me")])

    sent_tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    for forbidden in ("write_page", "write_index", "append_log"):
        assert forbidden not in sent_tool_names


def test_query_never_exposes_write_tools_to_the_llm(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    fake = _FakeClient([_FakeMessage(content="answer")])
    monkeypatch.setattr(llm, "_client", lambda: fake)

    operations.query("anything")

    sent_tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    for forbidden in ("write_page", "write_index", "append_log"):
        assert forbidden not in sent_tool_names


# ======================================================== trace contract

PREVIEW_LIMIT = 400


def _preview_within_contract(preview: str) -> bool:
    return len(preview) <= PREVIEW_LIMIT or preview.endswith(" more chars)")


def test_trace_step_preview_never_exceeds_limit_or_carries_suffix(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    # Seed a page with a very long body so the tool result blows past the cap.
    wiki = Wiki(workspace)
    big_body = "x" * 10_000
    wiki.write_page("bigpage", big_body)

    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="read_page", arguments=json.dumps({"name": "bigpage"})),
        ]),
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t2", name="finish", arguments=json.dumps({"summary": "done"})),
        ]),
    ])
    monkeypatch.setattr(llm, "_client", lambda: fake)

    result = operations.query("show the big page")

    # Trace shape: every step has the three fields with the right types.
    for step in result.trace:
        assert isinstance(step.tool, str)
        assert isinstance(step.args, dict)
        assert isinstance(step.result_preview, str)
        assert _preview_within_contract(step.result_preview)

    # No leakage: the full 10kB body must not appear in any preview.
    for step in result.trace:
        assert big_body not in step.result_preview


def test_trace_preserves_args_as_dict_even_for_invalid_json(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    # Bad JSON args become {"_raw": "<raw>"}; the trace still surfaces a dict
    # so downstream consumers can serialise it without special-casing.
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="list_pages", arguments="garbage{"),
        ]),
        _FakeMessage(content="ok"),
    ])
    monkeypatch.setattr(llm, "_client", lambda: fake)

    result = operations.query("anything")

    assert isinstance(result.trace[0].args, dict)
    assert result.trace[0].args == {"_raw": "garbage{"}
