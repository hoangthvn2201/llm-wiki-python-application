"""Tests for FastAPI routes in app.main.

The LLM is never called. Each test patches the relevant orchestrator on
`app.main` (where it was imported by name) and points the wiki at a tmp
workspace by patching `app.main.get_settings`.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import _render_md, app
from app.schemas import ChatResponse, IngestResult, LintResult, QueryResult, TraceStep
from app.wiki import Wiki


# ================================================================ fixtures

@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point app.main at a fresh wiki rooted under tmp_path."""
    ws = tmp_path / "ws"
    Wiki(ws).ensure()
    monkeypatch.setattr(
        main, "get_settings", lambda: SimpleNamespace(workspace_path=ws)
    )
    return ws


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _patch(monkeypatch: pytest.MonkeyPatch, name: str, fn: Any) -> dict[str, Any]:
    """Replace an attribute on app.main and return a kwargs-capture dict bound
    to the replacement when `fn` is a capture builder."""
    monkeypatch.setattr(main, name, fn)
    return {}


# ===================================================================== GET /

def test_get_root_returns_html_shell(workspace: Path, client: TestClient):
    res = client.get("/")

    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert b"<html" in res.content.lower()


# =========================================================== POST /api/ingest

def test_post_ingest_returns_ingest_result_on_valid_body(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    captured: dict[str, Any] = {}

    def fake_ingest(source_name: str, content: str) -> IngestResult:
        captured["source_name"] = source_name
        captured["content"] = content
        return IngestResult(summary="done", trace=[])

    monkeypatch.setattr(main, "ingest", fake_ingest)

    res = client.post("/api/ingest", json={"source_name": "my-src", "content": "body"})

    assert res.status_code == 200
    assert res.json() == {"summary": "done", "trace": []}
    assert captured == {"source_name": "my-src", "content": "body"}


def test_post_ingest_returns_422_on_missing_fields(
    workspace: Path, client: TestClient
):
    res = client.post("/api/ingest", json={"source_name": "x"})

    assert res.status_code == 422


def test_post_ingest_maps_value_error_to_400(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def fake_ingest(source_name: str, content: str) -> IngestResult:
        raise ValueError("invalid slug")

    monkeypatch.setattr(main, "ingest", fake_ingest)

    res = client.post("/api/ingest", json={"source_name": "Bad", "content": "x"})

    assert res.status_code == 400
    assert res.json()["detail"] == "invalid slug"


# ============================================ POST /api/ingest/{file,pdf}

@pytest.mark.parametrize("url", ["/api/ingest/file", "/api/ingest/pdf"])
def test_pdf_upload_routes_to_ingest_pdf(
    url: str, workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    captured: dict[str, Any] = {}

    def fake_ingest_pdf(source_name: str, data: bytes) -> IngestResult:
        captured["source_name"] = source_name
        captured["data"] = data
        return IngestResult(summary="pdf ok", trace=[])

    monkeypatch.setattr(main, "ingest_pdf", fake_ingest_pdf)
    monkeypatch.setattr(main, "ingest", lambda *a, **k: pytest.fail("ingest should not be called for a .pdf upload"))

    res = client.post(
        url,
        data={"source_name": "my-src"},
        files={"file": ("doc.pdf", b"%PDF-fake", "application/pdf")},
    )

    assert res.status_code == 200
    assert res.json()["summary"] == "pdf ok"
    assert captured == {"source_name": "my-src", "data": b"%PDF-fake"}


@pytest.mark.parametrize("url", ["/api/ingest/file", "/api/ingest/pdf"])
@pytest.mark.parametrize("filename", ["notes.md", "notes.markdown"])
def test_markdown_upload_routes_to_ingest(
    url: str,
    filename: str,
    workspace: Path,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    def fake_ingest(source_name: str, content: str) -> IngestResult:
        captured["source_name"] = source_name
        captured["content"] = content
        return IngestResult(summary="md ok", trace=[])

    monkeypatch.setattr(main, "ingest", fake_ingest)
    monkeypatch.setattr(main, "ingest_pdf", lambda *a, **k: pytest.fail("ingest_pdf should not be called for a .md upload"))

    res = client.post(
        url,
        data={"source_name": "my-src"},
        files={"file": (filename, "# Hello, world!".encode("utf-8"), "text/markdown")},
    )

    assert res.status_code == 200
    assert captured == {"source_name": "my-src", "content": "# Hello, world!"}


def test_markdown_upload_rejects_non_utf8(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(main, "ingest", lambda *a, **k: pytest.fail("should not reach ingest"))

    res = client.post(
        "/api/ingest/file",
        data={"source_name": "my-src"},
        # Lone surrogate / Latin-1 byte that's invalid UTF-8.
        files={"file": ("notes.md", b"\xff\xfe\xfd", "text/markdown")},
    )

    assert res.status_code == 400
    assert "UTF-8" in res.json()["detail"]


def test_upload_rejects_unknown_extension(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(main, "ingest", lambda *a, **k: pytest.fail("should not reach ingest"))
    monkeypatch.setattr(main, "ingest_pdf", lambda *a, **k: pytest.fail("should not reach ingest_pdf"))

    res = client.post(
        "/api/ingest/file",
        data={"source_name": "my-src"},
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert res.status_code == 400
    assert "pdf" in res.json()["detail"].lower()


def test_upload_with_no_extension_is_rejected(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(main, "ingest", lambda *a, **k: pytest.fail("should not reach ingest"))

    res = client.post(
        "/api/ingest/file",
        data={"source_name": "my-src"},
        files={"file": ("notes", b"hi", "text/plain")},
    )

    assert res.status_code == 400


def test_upload_value_error_from_orchestrator_maps_to_400(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def fake_ingest_pdf(source_name: str, data: bytes) -> IngestResult:
        raise ValueError("PDF extraction failed: corrupt")

    monkeypatch.setattr(main, "ingest_pdf", fake_ingest_pdf)

    res = client.post(
        "/api/ingest/file",
        data={"source_name": "my-src"},
        files={"file": ("x.pdf", b"junk", "application/pdf")},
    )

    assert res.status_code == 400
    assert "corrupt" in res.json()["detail"]


def test_file_and_pdf_urls_are_symmetric(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(main, "ingest_pdf", lambda s, d: IngestResult(summary="same", trace=[]))

    payload = {
        "data": {"source_name": "my-src"},
        "files": {"file": ("doc.pdf", b"%PDF", "application/pdf")},
    }

    res_a = client.post("/api/ingest/file", **payload)
    res_b = client.post("/api/ingest/pdf", **payload)

    assert res_a.status_code == res_b.status_code == 200
    assert res_a.json() == res_b.json()


# ============================================================ POST /api/query

def test_post_query_returns_query_result(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def fake_query(question: str) -> QueryResult:
        return QueryResult(answer=f"answer to: {question}", trace=[])

    monkeypatch.setattr(main, "query", fake_query)

    res = client.post("/api/query", json={"question": "what is X?"})

    assert res.status_code == 200
    assert res.json() == {"answer": "answer to: what is X?", "trace": []}


def test_post_query_returns_422_on_missing_question(
    workspace: Path, client: TestClient
):
    res = client.post("/api/query", json={})

    assert res.status_code == 422


# ============================================================= POST /api/chat

def test_post_chat_returns_chat_response(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def fake_chat(history):
        return ChatResponse(
            reply="hi back",
            trace=[TraceStep(tool="list_pages", result_preview="...")],
        )

    monkeypatch.setattr(main, "chat", fake_chat)

    res = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["reply"] == "hi back"
    assert body["trace"][0]["tool"] == "list_pages"


def test_post_chat_maps_value_error_to_400(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    def fake_chat(history):
        raise ValueError("chat history must contain at least one message")

    monkeypatch.setattr(main, "chat", fake_chat)

    res = client.post("/api/chat", json={"messages": []})

    assert res.status_code == 400
    assert "at least one message" in res.json()["detail"]


def test_post_chat_returns_422_when_message_missing_fields(
    workspace: Path, client: TestClient
):
    res = client.post("/api/chat", json={"messages": [{"role": "user"}]})

    assert res.status_code == 422


# ============================================================= POST /api/lint

def test_post_lint_returns_lint_result(
    workspace: Path, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(main, "lint", lambda: LintResult(report="all good", trace=[]))

    res = client.post("/api/lint")

    assert res.status_code == 200
    assert res.json() == {"report": "all good", "trace": []}


# ======================================================== GET /api/pages

def test_get_pages_returns_empty_list_for_fresh_workspace(
    workspace: Path, client: TestClient
):
    res = client.get("/api/pages")

    assert res.status_code == 200
    assert res.json() == []


def test_get_pages_returns_sorted_slugs(workspace: Path, client: TestClient):
    (workspace / "wiki" / "beta.md").write_text("# b")
    (workspace / "wiki" / "alpha.md").write_text("# a")

    res = client.get("/api/pages")

    assert res.json() == ["alpha", "beta"]


# ===================================================== GET /api/page/{name}

def test_get_page_returns_md_and_html_for_existing_page(
    workspace: Path, client: TestClient
):
    (workspace / "wiki" / "alpha.md").write_text("# Alpha\n\nBody.\n")

    res = client.get("/api/page/alpha")

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "alpha"
    assert "# Alpha" in body["content_md"]
    assert "<h1" in body["content_html"]


def test_get_page_returns_404_for_missing_page(
    workspace: Path, client: TestClient
):
    res = client.get("/api/page/does-not-exist")

    assert res.status_code == 404


def test_get_page_returns_404_for_invalid_slug(
    workspace: Path, client: TestClient
):
    # Uppercase fails the slug regex → ValueError → handler maps to 404.
    res = client.get("/api/page/Bad")

    assert res.status_code == 404


# ========================================================= GET /api/index

def test_get_index_returns_md_and_html(workspace: Path, client: TestClient):
    res = client.get("/api/index")

    assert res.status_code == 200
    body = res.json()
    assert "content_md" in body and "content_html" in body
    assert body["content_md"].startswith("# Index")


# =========================================================== GET /api/log

def test_get_log_returns_md_only(workspace: Path, client: TestClient):
    res = client.get("/api/log")

    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) == {"content_md"}
    assert body["content_md"].startswith("# Log")


# ========================================================== GET /api/schema

def test_get_schema_returns_default_schema(
    workspace: Path, client: TestClient
):
    res = client.get("/api/schema")

    assert res.status_code == 200
    assert res.json()["content_md"].startswith("# Wiki Schema")


# ========================================================== PUT /api/schema

def test_put_schema_writes_and_returns_new_value(
    workspace: Path, client: TestClient
):
    res = client.put("/api/schema", json={"content_md": "# Custom Schema"})

    assert res.status_code == 200
    assert res.json()["content_md"] == "# Custom Schema"
    # Persists to disk.
    assert (workspace / "SCHEMA.md").read_text() == "# Custom Schema"


def test_put_schema_returns_422_on_missing_content_md(
    workspace: Path, client: TestClient
):
    res = client.put("/api/schema", json={})

    assert res.status_code == 422


# ============================================================== _render_md

def test_render_md_supports_fenced_code():
    out = _render_md("```\nhello\n```")

    assert "<pre>" in out
    assert "<code>" in out


def test_render_md_supports_tables():
    out = _render_md("| a | b |\n|---|---|\n| 1 | 2 |\n")

    assert "<table>" in out
    assert "<thead>" in out


def test_render_md_supports_toc_heading_ids():
    # The `toc` extension assigns `id="..."` to headings so they can be linked.
    out = _render_md("# Hello World\n")

    assert 'id="hello-world"' in out
