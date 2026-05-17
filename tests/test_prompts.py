"""Workflow-contract tests for the system prompts.

These are not style tests. Each assertion pins a workflow step that the rest
of the system depends on: if a tool name disappears from a prompt, the agent
loop silently stops using it. This catches accidental deletion of a step
during prompt edits.
"""
from __future__ import annotations

import pytest

from app.prompts import (
    CHAT_SYSTEM,
    HALLUCINATION_SYSTEM,
    INGEST_SYSTEM,
    LINT_SYSTEM,
    QUERY_SYSTEM,
)


# ============================================================== INGEST_SYSTEM

INGEST_REQUIRED_TOOLS = (
    "read_schema",
    "read_index",
    "read_page",
    "write_page",
    "write_index",
    "append_log",
    "finish",
)


def test_ingest_system_is_non_empty():
    assert INGEST_SYSTEM.strip()


@pytest.mark.parametrize("tool", INGEST_REQUIRED_TOOLS)
def test_ingest_system_mentions_required_tool(tool: str):
    assert tool in INGEST_SYSTEM, f"INGEST_SYSTEM is missing reference to {tool}"


def test_ingest_system_mentions_kebab_case_slug_rule():
    assert "kebab-case" in INGEST_SYSTEM.lower()


def test_ingest_system_mentions_cross_reference_syntax():
    assert "[[page-name]]" in INGEST_SYSTEM


# =============================================================== QUERY_SYSTEM

QUERY_REQUIRED_TOOLS = ("read_index", "read_page", "finish")
QUERY_FORBIDDEN_TOOLS = ("write_page", "write_index", "append_log")


def test_query_system_is_non_empty():
    assert QUERY_SYSTEM.strip()


def test_query_system_declares_read_only():
    assert "READ-ONLY" in QUERY_SYSTEM


@pytest.mark.parametrize("tool", QUERY_REQUIRED_TOOLS)
def test_query_system_mentions_required_tool(tool: str):
    assert tool in QUERY_SYSTEM, f"QUERY_SYSTEM is missing reference to {tool}"


@pytest.mark.parametrize("tool", QUERY_FORBIDDEN_TOOLS)
def test_query_system_does_not_mention_write_tools(tool: str):
    # Naming a write tool in the read-only prompt is a bug — the model will
    # be told to use a tool it has no schema for.
    assert tool not in QUERY_SYSTEM, f"QUERY_SYSTEM should not mention {tool}"


# ================================================================ CHAT_SYSTEM

CHAT_REQUIRED_TOOLS = ("read_index", "read_page", "finish")


def test_chat_system_is_non_empty():
    assert CHAT_SYSTEM.strip()


def test_chat_system_declares_read_only():
    assert "READ-ONLY" in CHAT_SYSTEM


@pytest.mark.parametrize("tool", CHAT_REQUIRED_TOOLS)
def test_chat_system_mentions_required_tool(tool: str):
    assert tool in CHAT_SYSTEM, f"CHAT_SYSTEM is missing reference to {tool}"


def test_chat_system_mentions_cross_reference_syntax():
    assert "[[cross-references]]" in CHAT_SYSTEM


def test_chat_system_redirects_writes_to_other_tabs():
    # The user-visible escape hatch when chat can't fulfil a write request.
    text = CHAT_SYSTEM.lower()
    assert "ingest" in text and "lint" in text


# ================================================================ LINT_SYSTEM

LINT_REQUIRED_TOOLS = (
    "read_schema",
    "read_index",
    "read_page",
    "write_page",
    "write_index",
    "append_log",
    "finish",
)


def test_lint_system_is_non_empty():
    assert LINT_SYSTEM.strip()


@pytest.mark.parametrize("tool", LINT_REQUIRED_TOOLS)
def test_lint_system_mentions_required_tool(tool: str):
    assert tool in LINT_SYSTEM, f"LINT_SYSTEM is missing reference to {tool}"


# ====================================================== HALLUCINATION_SYSTEM

HALLUCINATION_REQUIRED_TOOLS = (
    "read_schema",
    "read_index",
    "read_page",
    "list_raw",
    "read_raw",
    "report_finding",
    "append_log",
    "finish",
)

HALLUCINATION_CLAIM_TYPES = (
    "factual",
    "quantitative",
    "relational",
    "temporal",
    "negation",
    "synthesis",
)

HALLUCINATION_VERDICTS = (
    "supported",
    "contradicted",
    "unverifiable",
    "hallucination",
)


def test_hallucination_system_is_non_empty():
    assert HALLUCINATION_SYSTEM.strip()


def test_hallucination_system_declares_read_only():
    assert "READ-ONLY" in HALLUCINATION_SYSTEM


@pytest.mark.parametrize("tool", HALLUCINATION_REQUIRED_TOOLS)
def test_hallucination_system_mentions_required_tool(tool: str):
    assert tool in HALLUCINATION_SYSTEM, (
        f"HALLUCINATION_SYSTEM is missing reference to {tool}"
    )


def test_hallucination_system_forbids_write_tools_explicitly():
    # The prompt should actively warn the agent off the write tools — they're
    # not in HALLUCINATION_TOOLS so calling them is futile, but a defensive
    # "MUST NOT" sentence catches drift if the tool set is ever widened.
    text = HALLUCINATION_SYSTEM.lower()
    assert "must not" in text or "do not" in text
    assert "write_page" in HALLUCINATION_SYSTEM
    assert "write_index" in HALLUCINATION_SYSTEM


@pytest.mark.parametrize("claim_type", HALLUCINATION_CLAIM_TYPES)
def test_hallucination_system_mentions_claim_type(claim_type: str):
    assert claim_type in HALLUCINATION_SYSTEM, (
        f"HALLUCINATION_SYSTEM is missing claim type {claim_type}"
    )


@pytest.mark.parametrize("verdict", HALLUCINATION_VERDICTS)
def test_hallucination_system_mentions_verdict(verdict: str):
    assert verdict in HALLUCINATION_SYSTEM, (
        f"HALLUCINATION_SYSTEM is missing verdict {verdict}"
    )


def test_hallucination_system_describes_layers_in_order():
    # Layer 1 → entity, Layer 2 → description, Layer 3 → claim. The agent loop
    # depends on this ordering for the report grouping.
    text = HALLUCINATION_SYSTEM
    l1 = text.find("Layer 1")
    l2 = text.find("Layer 2")
    l3 = text.find("Layer 3")

    assert l1 != -1 and l2 != -1 and l3 != -1
    assert l1 < l2 < l3
