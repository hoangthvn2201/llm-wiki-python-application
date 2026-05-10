"""Orchestrators for the three operations."""
from __future__ import annotations

from app.config import get_settings
from app.llm import run_agent
from app.prompts import INGEST_SYSTEM, LINT_SYSTEM, QUERY_SYSTEM
from app.schemas import IngestResult, LintResult, QueryResult
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
