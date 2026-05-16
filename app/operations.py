"""Orchestrators for the three operations."""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from app.config import get_settings
from app.ingest import PdfExtractionError, get_pdf_extractor
from app.llm import run_agent, run_loop
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
    HallucinationFinding,
    IngestResult,
    LintResult,
    QueryResult,
)
from app.tools import HALLUCINATION_TOOLS, INGEST_TOOLS, LINT_TOOLS, READ_ONLY_TOOLS
from app.wiki import Wiki

HALLUCINATION_REPORT_FILENAME = "hallucination-report.md"


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


def ingest_pdf(
    source_name: str,
    pdf_bytes: bytes,
    *,
    backend: str = "pypdf",
) -> IngestResult:
    """Extract a PDF to markdown then delegate to the existing ingest flow."""
    extractor = get_pdf_extractor(backend)
    try:
        extracted = extractor.extract(pdf_bytes, filename=f"{source_name}.pdf")
    except PdfExtractionError as e:
        raise ValueError(f"PDF extraction failed: {e}") from e

    parts = [f"# {source_name}", ""]
    if extracted.metadata:
        parts.append("## Document metadata")
        for k, v in extracted.metadata.items():
            parts.append(f"- **{k}**: {v}")
        parts.append("")
    parts.append(extracted.text)
    content = "\n".join(parts)

    return ingest(source_name, content)


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


def _format_hallucination_report(findings: list[dict[str, Any]]) -> str:
    today = date.today().isoformat()
    total = len(findings)
    by_verdict = Counter(f["verdict"] for f in findings)
    by_type = Counter(f["type"] for f in findings)
    by_layer = Counter(f["layer"] for f in findings)
    pages_with_issues = sorted({
        f["page"]
        for f in findings
        if f["verdict"] in ("contradicted", "hallucination")
    })

    lines: list[str] = []
    lines.append("# Hallucination Report")
    lines.append("")
    lines.append(f"*Generated {today}*")
    lines.append("")
    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- Total findings: {total}")
    if total:
        lines.append("- By verdict:")
        for verdict in ("supported", "contradicted", "unverifiable", "hallucination"):
            lines.append(f"  - {verdict}: {by_verdict.get(verdict, 0)}")
        lines.append("- By layer:")
        for layer in (1, 2, 3):
            lines.append(f"  - layer {layer}: {by_layer.get(layer, 0)}")
        lines.append("- By type:")
        for ftype in ("factual", "quantitative", "relational", "temporal", "negation", "synthesis"):
            count = by_type.get(ftype, 0)
            if count:
                lines.append(f"  - {ftype}: {count}")
        lines.append(f"- Pages with contradictions or hallucinations: {len(pages_with_issues)}")
        if pages_with_issues:
            for page in pages_with_issues:
                lines.append(f"  - {page}")
    lines.append("")

    if not findings:
        lines.append("## Findings")
        lines.append("")
        lines.append("_No findings were recorded. The wiki may be empty or the agent did not call `report_finding`._")
        lines.append("")
        return "\n".join(lines)

    for layer, title in ((1, "Entity Verification"), (2, "Description Verification"), (3, "Claim Verification")):
        layer_findings = [f for f in findings if f["layer"] == layer]
        if not layer_findings:
            continue
        lines.append(f"## Layer {layer}: {title}")
        lines.append("")
        # Group by page within the layer.
        by_page: dict[str, list[dict[str, Any]]] = {}
        for f in layer_findings:
            by_page.setdefault(f["page"], []).append(f)
        for page in sorted(by_page):
            lines.append(f"### Page: {page}")
            lines.append("")
            for f in by_page[page]:
                lines.append(f"- **[{f['type']} / {f['verdict']}]** {f['claim']}")
                if f["evidence"]:
                    lines.append(f"  - Evidence: {f['evidence']}")
            lines.append("")

    return "\n".join(lines)


def hallucination_check() -> HallucinationCheckResult:
    """Sweep the wiki for hallucinations against raw sources.

    Read-only over wiki and raw. Writes only `hallucination-report.md` at the
    workspace root plus a single `log.md` entry — never touches wiki pages.
    """
    wiki = _wiki()
    wiki._hallucination_findings = []

    user_prompt = (
        "Run a hallucination check sweep over the wiki using the 3-layer "
        "verification workflow. Call `report_finding` once per claim you "
        "evaluate, then `append_log` once, then `finish`."
    )
    result = run_agent(
        wiki=wiki,
        system_prompt=HALLUCINATION_SYSTEM,
        user_prompt=user_prompt,
        allowed_tools=HALLUCINATION_TOOLS,
    )

    findings = list(getattr(wiki, "_hallucination_findings", []))
    report_md = _format_hallucination_report(findings)
    (wiki.root / HALLUCINATION_REPORT_FILENAME).write_text(report_md, encoding="utf-8")

    return HallucinationCheckResult(
        summary=result.final_text,
        findings=[HallucinationFinding(**f) for f in findings],
        report_path=HALLUCINATION_REPORT_FILENAME,
        trace=result.trace,
    )


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
