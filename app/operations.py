"""Orchestrators for the three operations."""
from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.llm import run_agent, run_loop
from app.prompts import CHAT_SYSTEM, INGEST_SYSTEM, LINT_SYSTEM, QUERY_SYSTEM
from app.schemas import ChatMessage, ChatResponse, IngestResult, LintResult, QueryResult
from app.tools import INGEST_TOOLS, LINT_TOOLS, READ_ONLY_TOOLS
from app.wiki import Wiki


def _wiki() -> Wiki:
    w = Wiki(get_settings().workspace_path)
    w.ensure()
    return w


def ingest(source_name: str, content: str) -> IngestResult:
    wiki = _wiki()
    wiki.write_raw(source_name, content)

    user_prompt = (
        f"A new source has been added: `raw/{source_name}.md`.\n\n"
        f"Its full content is below. Integrate it into the wiki following the workflow.\n\n"
        f"--- BEGIN SOURCE ---\n{content}\n--- END SOURCE ---\n"
    )
    result = run_agent(
        wiki=wiki,
        system_prompt=INGEST_SYSTEM,
        user_prompt=user_prompt,
        allowed_tools=INGEST_TOOLS,
    )
    return IngestResult(summary=result.final_text, trace=result.trace)


def query(question: str) -> QueryResult:
    wiki = _wiki()
    user_prompt = f"Question:\n\n{question}\n"
    result = run_agent(
        wiki=wiki,
        system_prompt=QUERY_SYSTEM,
        user_prompt=user_prompt,
        allowed_tools=READ_ONLY_TOOLS,
    )
    return QueryResult(answer=result.final_text, trace=result.trace)


def chat(history: list[ChatMessage]) -> ChatResponse:
    """Multi-turn chat against the wiki with read-only tools.

    The client owns conversation state and POSTs the full history each turn.
    """
    wiki = _wiki()
    if not history:
        raise ValueError("chat history must contain at least one message")

    messages: list[dict[str, Any]] = [{"role": "system", "content": CHAT_SYSTEM}]
    for m in history:
        if m.role not in ("user", "assistant"):
            raise ValueError(f"invalid role {m.role!r}; expected 'user' or 'assistant'")
        messages.append({"role": m.role, "content": m.content})

    result = run_loop(
        wiki=wiki,
        messages=messages,
        allowed_tools=READ_ONLY_TOOLS,
    )
    return ChatResponse(reply=result.final_text, trace=result.trace)


def lint() -> LintResult:
    wiki = _wiki()
    user_prompt = "Run a lint pass on the wiki. Report problems and fix small ones."
    result = run_agent(
        wiki=wiki,
        system_prompt=LINT_SYSTEM,
        user_prompt=user_prompt,
        allowed_tools=LINT_TOOLS,
    )
    return LintResult(report=result.final_text, trace=result.trace)
