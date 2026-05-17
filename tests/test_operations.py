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
from app.prompts import (
    CHAT_SYSTEM,
    HALLUCINATION_SYSTEM,
    INGEST_SYSTEM,
    LINT_SYSTEM,
    QUERY_SYSTEM,
)
from app.schemas import (
    ChatMessage,
    ChatResponse,
    HallucinationCheckResult,
    IngestResult,
    LintResult,
    QueryResult,
)
from app.tools import HALLUCINATION_TOOLS, INGEST_TOOLS, LINT_TOOLS, READ_ONLY_TOOLS


# ================================================================ fixtures

@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point app.operations at a temp workspace by patching get_settings."""
    ws = tmp_path / "ws"
    monkeypatch.setattr(
        operations,
        "get_settings",
        lambda: SimpleNamespace(
            workspace_path=ws,
            max_tool_iterations=25,
            max_tool_iterations_ingest=25,
            max_tool_iterations_query=25,
            max_tool_iterations_chat=25,
            max_tool_iterations_lint=50,
            max_tool_iterations_hallucination=150,
        ),
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

    def fake_run_agent(*, wiki, system_prompt, user_prompt, allowed_tools, **extra):
        captured.update(
            wiki=wiki,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allowed_tools=allowed_tools,
            **extra,
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

    def fake_run_loop(*, wiki, messages, allowed_tools, **extra):
        # Snapshot messages so later mutation doesn't confuse the assertion.
        captured.update(
            wiki=wiki,
            messages=[dict(m) for m in messages],
            allowed_tools=allowed_tools,
            **extra,
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

    def fake_run_agent(*, wiki, **_kw):  # noqa: ARG001 — kwargs absorbed for forward compat
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


def test_query_uses_query_iteration_cap(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.query("q")

    assert captured.get("max_iterations") == 25


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


# ====================================================== hallucination_check

def _capture_run_agent_with_findings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    findings: list[dict[str, Any]],
    final_text: str = "sweep done",
) -> dict[str, Any]:
    """Spy that also injects findings onto the wiki instance, mimicking what
    `report_finding` would do during a real agent run."""
    captured: dict[str, Any] = {}

    def fake_run_agent(*, wiki, system_prompt, user_prompt, allowed_tools, **extra):
        captured.update(
            wiki=wiki,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allowed_tools=allowed_tools,
            **extra,
        )
        wiki._hallucination_findings = list(findings)
        return AgentResult(final_text=final_text, trace=[])

    monkeypatch.setattr(operations, "run_agent", fake_run_agent)
    return captured


def test_hallucination_check_uses_correct_system_and_tools(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.hallucination_check()

    assert captured["system_prompt"] == HALLUCINATION_SYSTEM
    assert captured["allowed_tools"] == HALLUCINATION_TOOLS


def test_hallucination_check_uses_hallucination_iteration_cap(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.hallucination_check()

    # Per-op cap — defaults to 150 in Settings; the fixture sets the same value.
    assert captured.get("max_iterations") == 150


def test_ingest_uses_ingest_iteration_cap(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.ingest("my-src", "body")

    assert captured.get("max_iterations") == 25


def test_lint_uses_lint_iteration_cap(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_agent(monkeypatch)

    operations.lint()

    assert captured.get("max_iterations") == 50


def test_chat_uses_chat_iteration_cap(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    captured = _capture_run_loop(monkeypatch)

    operations.chat([ChatMessage(role="user", content="hi")])

    assert captured.get("max_iterations") == 25


def test_hallucination_check_writes_report_file(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    findings = [
        {
            "page": "napoleon",
            "claim": "Napoleon was born in 1769",
            "type": "quantitative",
            "layer": 3,
            "verdict": "supported",
            "evidence": "raw/napoleon.md confirms",
        },
        {
            "page": "napoleon",
            "claim": "Napoleon authored War and Peace",
            "type": "relational",
            "layer": 3,
            "verdict": "hallucination",
            "evidence": "no source supports this",
        },
    ]
    _capture_run_agent_with_findings(monkeypatch, findings=findings)

    operations.hallucination_check()

    report_path = workspace / "hallucination-report.md"
    assert report_path.is_file()
    body = report_path.read_text(encoding="utf-8")
    assert "# Hallucination Report" in body
    assert "## Statistics" in body
    assert "Total findings: 2" in body
    assert "hallucination: 1" in body
    assert "supported: 1" in body
    assert "Layer 3: Claim Verification" in body
    assert "Napoleon was born in 1769" in body
    assert "War and Peace" in body


def test_hallucination_check_returns_result_schema(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    findings = [
        {
            "page": "p",
            "claim": "c",
            "type": "factual",
            "layer": 1,
            "verdict": "supported",
            "evidence": "",
        }
    ]
    _capture_run_agent_with_findings(monkeypatch, findings=findings, final_text="summary")

    result = operations.hallucination_check()

    assert isinstance(result, HallucinationCheckResult)
    assert result.summary == "summary"
    assert result.report_path == "hallucination-report.md"
    assert len(result.findings) == 1
    assert result.findings[0].page == "p"
    assert result.findings[0].verdict == "supported"


def test_hallucination_check_handles_no_findings(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    _capture_run_agent_with_findings(monkeypatch, findings=[])

    result = operations.hallucination_check()

    assert result.findings == []
    body = (workspace / "hallucination-report.md").read_text(encoding="utf-8")
    assert "Total findings: 0" in body
    assert "No findings were recorded" in body


def test_hallucination_report_renders_evidence_when_present():
    findings = [
        {
            "page": "p",
            "claim": "the claim with evidence",
            "type": "factual",
            "layer": 3,
            "verdict": "contradicted",
            "evidence": "raw/foo.md disagrees",
        }
    ]

    md = operations._format_hallucination_report(findings)

    assert "the claim with evidence" in md
    assert "- Evidence: raw/foo.md disagrees" in md


def test_hallucination_report_omits_evidence_line_when_empty():
    findings = [
        {
            "page": "p",
            "claim": "claim without evidence",
            "type": "factual",
            "layer": 3,
            "verdict": "unverifiable",
            "evidence": "",
        }
    ]

    md = operations._format_hallucination_report(findings)

    assert "claim without evidence" in md
    # No evidence sub-line when the field is empty.
    assert "Evidence:" not in md


def test_hallucination_check_does_not_modify_wiki_or_raw(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
):
    # Pre-seed an existing wiki page and raw source; verify they survive the sweep.
    operations._wiki()  # ensure() creates the directories
    (workspace / "wiki" / "alpha.md").write_text("# Alpha\noriginal", encoding="utf-8")
    (workspace / "raw" / "src.md").write_text("source body", encoding="utf-8")

    findings = [
        {
            "page": "alpha",
            "claim": "claim",
            "type": "factual",
            "layer": 1,
            "verdict": "supported",
            "evidence": "",
        }
    ]
    _capture_run_agent_with_findings(monkeypatch, findings=findings)

    operations.hallucination_check()

    # Wiki page and raw source untouched.
    assert (workspace / "wiki" / "alpha.md").read_text(encoding="utf-8") == "# Alpha\noriginal"
    assert (workspace / "raw" / "src.md").read_text(encoding="utf-8") == "source body"
