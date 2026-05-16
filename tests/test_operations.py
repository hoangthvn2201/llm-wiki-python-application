"""Tests for app.operations — ingest, query, chat, lint orchestrators.

The LLM is never called. `run_agent` and `run_loop` are monkeypatched to capture
the arguments they receive and return a canned `AgentResult`. The wiki is rooted
at `tmp_path` via a patched `get_settings`.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app import operations
from app.llm import AgentResult
from app.prompts import CHAT_SYSTEM, INGEST_SYSTEM, LINT_SYSTEM, QUERY_SYSTEM
from app.schemas import ChatMessage, ChatResponse, IngestResult, LintResult, QueryResult
from app.tools import INGEST_TOOLS, LINT_TOOLS, READ_ONLY_TOOLS


# ================================================================ fixtures

@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point app.operations at a temp workspace by patching get_settings."""
    ws = tmp_path / "ws"
    monkeypatch.setattr(
        operations,
        "get_settings",
        lambda: SimpleNamespace(workspace_path=ws),
    )
    return ws


def _capture_run_agent(
    monkeypatch: pytest.MonkeyPatch,
    *,
    final_text: str = "ok",
    trace: list | None = None,
) -> dict[str, Any]:
    """Replace operations.run_agent with a spy. Returns a dict the test can
    inspect after the call (`wiki`, `system_prompt`, `user_prompt`, `allowed_tools`)."""
    captured: dict[str, Any] = {}

    def fake_run_agent(*, wiki, system_prompt, user_prompt, allowed_tools):
        captured.update(
            wiki=wiki,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allowed_tools=allowed_tools,
        )
        return AgentResult(final_text=final_text, trace=trace or [])

    monkeypatch.setattr(operations, "run_agent", fake_run_agent)
    return captured


def _capture_run_loop(
    monkeypatch: pytest.MonkeyPatch,
    *,
    final_text: str = "ok",
    trace: list | None = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_run_loop(*, wiki, messages, allowed_tools):
        # Snapshot messages so later mutation doesn't confuse the assertion.
        captured.update(
            wiki=wiki,
            messages=[dict(m) for m in messages],
            allowed_tools=allowed_tools,
        )
        return AgentResult(final_text=final_text, trace=trace or [])

    monkeypatch.setattr(operations, "run_loop", fake_run_loop)
    return captured


# ==================================================================== _wiki

def test_wiki_returns_initialized_wiki(workspace: Path):
    w = operations._wiki()

    # ensure() has run.
    assert (workspace / "index.md").is_file()
    assert (workspace / "log.md").is_file()
    assert (workspace / "SCHEMA.md").is_file()
    assert w.root == workspace.resolve()


# =================================================================== ingest

def test_ingest_writes_raw_source_before_calling_run_agent(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    seen: dict[str, bool] = {}

    def fake_run_agent(*, wiki, **_kw):
        seen["raw_exists_when_agent_runs"] = (workspace / "raw" / "my-src.md").is_file()
        return AgentResult(final_text="ok", trace=[])

    monkeypatch.setattr(operations, "run_agent", fake_run_agent)

    operations.ingest("my-src", "# Body\n")

    assert seen["raw_exists_when_agent_runs"] is True


def test_ingest_uses_ingest_system_and_ingest_tools(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.ingest("my-src", "# Body")

    assert captured["system_prompt"] == INGEST_SYSTEM
    assert captured["allowed_tools"] == INGEST_TOOLS


def test_ingest_user_prompt_embeds_content_between_markers(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)
    body = "this is the source body"

    operations.ingest("my-src", body)

    prompt = captured["user_prompt"]
    assert "raw/my-src.md" in prompt
    assert "--- BEGIN SOURCE ---" in prompt
    assert body in prompt
    assert "--- END SOURCE ---" in prompt
    # The content must sit between the markers.
    assert prompt.index("--- BEGIN SOURCE ---") < prompt.index(body) < prompt.index("--- END SOURCE ---")


def test_ingest_returns_ingest_result_wrapping_agent_output(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    _capture_run_agent(monkeypatch, final_text="summary text")

    result = operations.ingest("my-src", "body")

    assert isinstance(result, IngestResult)
    assert result.summary == "summary text"
    assert result.trace == []


def test_ingest_invalid_slug_raises_value_error_before_calling_agent(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    called = {"flag": False}

    def fake_run_agent(**_kw):
        called["flag"] = True
        return AgentResult(final_text="x", trace=[])

    monkeypatch.setattr(operations, "run_agent", fake_run_agent)

    with pytest.raises(ValueError):
        operations.ingest("Bad Slug", "body")

    assert called["flag"] is False


# ==================================================================== query

def test_query_uses_query_system_and_read_only_tools(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.query("what is X?")

    assert captured["system_prompt"] == QUERY_SYSTEM
    assert captured["allowed_tools"] == READ_ONLY_TOOLS


def test_query_user_prompt_contains_question(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.query("what is X?")

    assert "what is X?" in captured["user_prompt"]


def test_query_returns_query_result(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    _capture_run_agent(monkeypatch, final_text="the answer")

    result = operations.query("q")

    assert isinstance(result, QueryResult)
    assert result.answer == "the answer"


# ===================================================================== chat

def test_chat_rejects_empty_history(workspace: Path):
    with pytest.raises(ValueError, match="at least one message"):
        operations.chat([])


def test_chat_rejects_invalid_role(workspace: Path):
    bad = [ChatMessage(role="robot", content="hi")]

    with pytest.raises(ValueError, match="robot"):
        operations.chat(bad)


def test_chat_prepends_system_prompt(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_loop(monkeypatch)

    operations.chat([ChatMessage(role="user", content="hi")])

    assert captured["messages"][0] == {"role": "system", "content": CHAT_SYSTEM}


def test_chat_preserves_history_order_after_system_prompt(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_loop(monkeypatch)
    history = [
        ChatMessage(role="user", content="a"),
        ChatMessage(role="assistant", content="b"),
        ChatMessage(role="user", content="c"),
    ]

    operations.chat(history)

    sent = captured["messages"]
    assert sent[0]["role"] == "system"
    assert [(m["role"], m["content"]) for m in sent[1:]] == [
        ("user", "a"),
        ("assistant", "b"),
        ("user", "c"),
    ]


def test_chat_uses_read_only_tools(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_loop(monkeypatch)

    operations.chat([ChatMessage(role="user", content="hi")])

    assert captured["allowed_tools"] == READ_ONLY_TOOLS


def test_chat_returns_chat_response_with_reply_and_trace(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    _capture_run_loop(monkeypatch, final_text="hello back")

    resp = operations.chat([ChatMessage(role="user", content="hi")])

    assert isinstance(resp, ChatResponse)
    assert resp.reply == "hello back"
    assert resp.trace == []


# ===================================================================== lint

def test_lint_uses_lint_system_and_lint_tools(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.lint()

    assert captured["system_prompt"] == LINT_SYSTEM
    assert captured["allowed_tools"] == LINT_TOOLS


def test_lint_returns_lint_result(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    _capture_run_agent(monkeypatch, final_text="lint report")

    result = operations.lint()

    assert isinstance(result, LintResult)
    assert result.report == "lint report"
