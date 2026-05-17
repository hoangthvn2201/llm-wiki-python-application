"""Tests for app.schemas — pin the field-shape contract we depend on.

We trust pydantic to enforce types; these tests pin the few decisions where
*our* code depends on a specific behaviour:
- which fields are required vs optional
- which fields have default factories
- whether arbitrary strings are accepted (validation moved into orchestrators)
"""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    HallucinationCheckResult,
    HallucinationFinding,
    IndexView,
    IngestRequest,
    IngestResult,
    LintResult,
    LogView,
    PageView,
    QueryRequest,
    QueryResult,
    SchemaUpdate,
    SchemaView,
    TraceStep,
)


# -------------------------------------------------------------- ChatMessage

def test_chat_message_constructs_with_role_and_content():
    msg = ChatMessage(role="user", content="hi")

    assert msg.role == "user"
    assert msg.content == "hi"


def test_chat_message_accepts_arbitrary_role_strings():
    # Validation that role is in {"user", "assistant"} lives in operations.chat,
    # not in the schema. Pin that contract here so the validation doesn't
    # accidentally migrate.
    msg = ChatMessage(role="something-weird", content="x")

    assert msg.role == "something-weird"


def test_chat_message_rejects_missing_role():
    with pytest.raises(ValidationError):
        ChatMessage(content="x")  # type: ignore[call-arg]


def test_chat_message_rejects_missing_content():
    with pytest.raises(ValidationError):
        ChatMessage(role="user")  # type: ignore[call-arg]


# -------------------------------------------------------------- ChatRequest

def test_chat_request_accepts_empty_messages_list():
    # Empty list parses at the schema layer; the orchestrator is what raises.
    req = ChatRequest(messages=[])

    assert req.messages == []


def test_chat_request_preserves_message_order():
    msgs = [
        ChatMessage(role="user", content="a"),
        ChatMessage(role="assistant", content="b"),
        ChatMessage(role="user", content="c"),
    ]
    req = ChatRequest(messages=msgs)

    assert [m.content for m in req.messages] == ["a", "b", "c"]


def test_chat_request_rejects_missing_messages():
    with pytest.raises(ValidationError):
        ChatRequest()  # type: ignore[call-arg]


# -------------------------------------------------------------- ChatResponse

def test_chat_response_constructs_with_reply_and_trace():
    resp = ChatResponse(reply="hello", trace=[])

    assert resp.reply == "hello"
    assert resp.trace == []


def test_chat_response_rejects_missing_reply():
    with pytest.raises(ValidationError):
        ChatResponse(trace=[])  # type: ignore[call-arg]


# ----------------------------------------------------------------- TraceStep

def test_trace_step_args_defaults_to_empty_dict():
    step = TraceStep(tool="read_index", result_preview="...")

    assert step.args == {}


def test_trace_step_args_default_is_not_shared():
    # Default factory must produce a new dict per instance — otherwise mutating
    # one trace step would silently leak into another.
    a = TraceStep(tool="t", result_preview="r")
    b = TraceStep(tool="t", result_preview="r")
    a.args["x"] = 1

    assert b.args == {}


def test_trace_step_rejects_missing_tool():
    with pytest.raises(ValidationError):
        TraceStep(result_preview="r")  # type: ignore[call-arg]


def test_trace_step_rejects_missing_result_preview():
    with pytest.raises(ValidationError):
        TraceStep(tool="t")  # type: ignore[call-arg]


# --------------------------------------------------------------- Ingest/Query

def test_ingest_request_rejects_missing_source_name():
    with pytest.raises(ValidationError):
        IngestRequest(content="body")  # type: ignore[call-arg]


def test_ingest_request_rejects_missing_content():
    with pytest.raises(ValidationError):
        IngestRequest(source_name="my-source")  # type: ignore[call-arg]


def test_ingest_request_round_trips_fields():
    req = IngestRequest(source_name="my-source", content="# Body")

    assert req.source_name == "my-source"
    assert req.content == "# Body"


def test_ingest_result_constructs_with_summary_and_trace():
    result = IngestResult(summary="done", trace=[])

    assert result.summary == "done"
    assert result.trace == []


def test_query_request_rejects_missing_question():
    with pytest.raises(ValidationError):
        QueryRequest()  # type: ignore[call-arg]


def test_query_result_constructs_with_answer_and_trace():
    result = QueryResult(answer="42", trace=[])

    assert result.answer == "42"


def test_lint_result_constructs_with_report_and_trace():
    result = LintResult(report="ok", trace=[])

    assert result.report == "ok"


# ---------------------------------------------------------------- Page views

def test_page_view_requires_all_fields():
    view = PageView(name="alpha", content_md="# A", content_html="<h1>A</h1>")

    assert view.name == "alpha"
    assert view.content_md == "# A"
    assert view.content_html == "<h1>A</h1>"


def test_page_view_rejects_missing_name():
    with pytest.raises(ValidationError):
        PageView(content_md="x", content_html="y")  # type: ignore[call-arg]


def test_index_view_requires_md_and_html():
    view = IndexView(content_md="md", content_html="<p>html</p>")

    assert view.content_md == "md"
    assert view.content_html == "<p>html</p>"


def test_log_view_is_md_only():
    # LogView intentionally has no content_html field; pin that contract so we
    # notice if someone adds rendering to the log view.
    view = LogView(content_md="md")

    assert view.content_md == "md"
    assert not hasattr(view, "content_html")


def test_schema_view_is_md_only():
    view = SchemaView(content_md="schema")

    assert view.content_md == "schema"
    assert not hasattr(view, "content_html")


def test_schema_update_rejects_missing_content_md():
    with pytest.raises(ValidationError):
        SchemaUpdate()  # type: ignore[call-arg]


def test_schema_update_accepts_content_md():
    upd = SchemaUpdate(content_md="# New schema")

    assert upd.content_md == "# New schema"


# ------------------------------------------------------- HallucinationFinding

def _valid_finding(**overrides: Any) -> dict[str, Any]:
    base = {
        "page": "napoleon",
        "claim": "Napoleon was born in 1769",
        "type": "quantitative",
        "layer": 3,
        "verdict": "supported",
        "evidence": "raw/napoleon.md confirms 1769",
    }
    base.update(overrides)
    return base


def test_hallucination_finding_accepts_fully_specified_record():
    f = HallucinationFinding(**_valid_finding())

    assert f.page == "napoleon"
    assert f.type == "quantitative"
    assert f.layer == 3
    assert f.verdict == "supported"
    assert f.evidence == "raw/napoleon.md confirms 1769"


def test_hallucination_finding_rejects_unknown_type():
    with pytest.raises(ValidationError):
        HallucinationFinding(**_valid_finding(type="made-up-bucket"))


def test_hallucination_finding_rejects_unknown_verdict():
    with pytest.raises(ValidationError):
        HallucinationFinding(**_valid_finding(verdict="maybe"))


@pytest.mark.parametrize("bad_layer", [0, 4, 7, -1])
def test_hallucination_finding_rejects_layer_out_of_range(bad_layer: int):
    with pytest.raises(ValidationError):
        HallucinationFinding(**_valid_finding(layer=bad_layer))


def test_hallucination_finding_evidence_defaults_to_empty_string():
    payload = _valid_finding()
    payload.pop("evidence")

    f = HallucinationFinding(**payload)

    assert f.evidence == ""


# ----------------------------------------------------- HallucinationCheckResult

def test_hallucination_check_result_constructs_with_required_fields():
    result = HallucinationCheckResult(
        summary="ok",
        findings=[],
        report_path="hallucination-report.md",
        trace=[],
    )

    assert result.summary == "ok"
    assert result.findings == []
    assert result.report_path == "hallucination-report.md"


@pytest.mark.parametrize("missing", ["summary", "findings", "report_path", "trace"])
def test_hallucination_check_result_rejects_missing_field(missing: str):
    payload: dict[str, Any] = {
        "summary": "ok",
        "findings": [],
        "report_path": "hallucination-report.md",
        "trace": [],
    }
    payload.pop(missing)

    with pytest.raises(ValidationError):
        HallucinationCheckResult(**payload)
