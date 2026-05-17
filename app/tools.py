"""Tool registry exposed to the LLM via OpenAI function-calling.

Each tool has a JSON schema (sent to the model) and a Python implementation
(invoked by the dispatcher). Errors are returned as strings so the LLM can
recover instead of the loop crashing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from app.wiki import Wiki


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[Wiki, dict[str, Any]], str]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------- handlers

def _list_pages(wiki: Wiki, _args: dict[str, Any]) -> str:
    pages = wiki.list_pages()
    if not pages:
        return "(no wiki pages yet)"
    return "\n".join(pages)


def _read_page(wiki: Wiki, args: dict[str, Any]) -> str:
    return wiki.read_page(args["name"])


def _write_page(wiki: Wiki, args: dict[str, Any]) -> str:
    name = args["name"]
    content = args["content"]
    existed = wiki.page_exists(name)
    wiki.write_page(name, content)
    return f"{'updated' if existed else 'created'} wiki/{name}.md ({len(content)} chars)"


def _read_index(wiki: Wiki, _args: dict[str, Any]) -> str:
    return wiki.read_index()


def _write_index(wiki: Wiki, args: dict[str, Any]) -> str:
    wiki.write_index(args["content"])
    return f"updated index.md ({len(args['content'])} chars)"


def _append_log(wiki: Wiki, args: dict[str, Any]) -> str:
    entry = args["entry"]
    wiki.append_log(entry)
    return f"appended {len(entry)} chars to log.md"


def _read_schema(wiki: Wiki, _args: dict[str, Any]) -> str:
    return wiki.read_schema()


def _list_raw(wiki: Wiki, _args: dict[str, Any]) -> str:
    raws = wiki.list_raw()
    if not raws:
        return "(no raw sources)"
    return "\n".join(raws)


def _read_raw(wiki: Wiki, args: dict[str, Any]) -> str:
    return wiki.read_raw(args["name"])


_FINDING_TYPES = {"factual", "quantitative", "relational", "temporal", "negation", "synthesis"}
_FINDING_VERDICTS = {"supported", "contradicted", "unverifiable", "hallucination"}
_FINDING_LAYERS = {1, 2, 3}


def _report_finding(wiki: Wiki, args: dict[str, Any]) -> str:
    """Record one hallucination-check finding on the per-call wiki instance.

    Findings accumulate on `wiki._hallucination_findings`; the orchestrator
    reads the list after the agent loop returns and writes the report file.
    """
    required = ("page", "claim", "type", "layer", "verdict")
    missing = [k for k in required if k not in args]
    if missing:
        raise ValueError(f"report_finding missing fields: {missing}")
    ftype = args["type"]
    if ftype not in _FINDING_TYPES:
        raise ValueError(
            f"invalid type {ftype!r}; must be one of {sorted(_FINDING_TYPES)}"
        )
    verdict = args["verdict"]
    if verdict not in _FINDING_VERDICTS:
        raise ValueError(
            f"invalid verdict {verdict!r}; must be one of {sorted(_FINDING_VERDICTS)}"
        )
    try:
        layer = int(args["layer"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"invalid layer {args['layer']!r}: not an integer") from e
    if layer not in _FINDING_LAYERS:
        raise ValueError(f"invalid layer {layer}; must be 1, 2, or 3")
    if not hasattr(wiki, "_hallucination_findings"):
        wiki._hallucination_findings = []
    finding = {
        "page": str(args["page"]),
        "claim": str(args["claim"]),
        "type": ftype,
        "layer": layer,
        "verdict": verdict,
        "evidence": str(args.get("evidence", "")),
    }
    wiki._hallucination_findings.append(finding)
    return f"recorded {ftype}/{verdict} for {finding['page']} (layer {layer})"


def _finish(_wiki: Wiki, args: dict[str, Any]) -> str:
    # The agent loop intercepts `finish` to terminate; the result is unused but
    # we still return something readable for completeness.
    return f"FINISHED: {args.get('summary', '(no summary)')}"


# ----------------------------------------------------------------- registry

ALL_TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            name="list_pages",
            description="List the slugs of every page currently in the wiki.",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_list_pages,
        ),
        Tool(
            name="read_page",
            description="Read the markdown content of a wiki page by its slug.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "kebab-case slug"}},
                "required": ["name"],
            },
            handler=_read_page,
        ),
        Tool(
            name="write_page",
            description=(
                "Create a new wiki page or overwrite an existing one. The content "
                "should be a complete markdown document (the previous content is replaced)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "kebab-case slug, no extension"},
                    "content": {"type": "string", "description": "full markdown body"},
                },
                "required": ["name", "content"],
            },
            handler=_write_page,
        ),
        Tool(
            name="read_index",
            description="Read index.md, the catalog of every wiki page.",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_read_index,
        ),
        Tool(
            name="write_index",
            description="Overwrite index.md with new content. Always pass the complete file.",
            parameters={
                "type": "object",
                "properties": {"content": {"type": "string"}},
                "required": ["content"],
            },
            handler=_write_index,
        ),
        Tool(
            name="append_log",
            description=(
                "Append an entry to log.md. The entry should start with a header line "
                "like '## [YYYY-MM-DD] ingest | <title>' followed by a short body."
            ),
            parameters={
                "type": "object",
                "properties": {"entry": {"type": "string"}},
                "required": ["entry"],
            },
            handler=_append_log,
        ),
        Tool(
            name="read_schema",
            description="Read SCHEMA.md (the wiki's conventions).",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_read_schema,
        ),
        Tool(
            name="list_raw",
            description="List the slugs of every raw source document.",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=_list_raw,
        ),
        Tool(
            name="read_raw",
            description="Read the markdown content of a raw source by its slug.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=_read_raw,
        ),
        Tool(
            name="report_finding",
            description=(
                "Record one hallucination-check finding. Call once per claim you "
                "evaluate during a hallucination sweep. Only available to the "
                "hallucination-check operation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "page": {
                        "type": "string",
                        "description": "wiki page slug the claim is from",
                    },
                    "claim": {
                        "type": "string",
                        "description": "short paraphrase or quote of the claim being verified",
                    },
                    "type": {
                        "type": "string",
                        "enum": sorted(_FINDING_TYPES),
                        "description": "claim taxonomy bucket",
                    },
                    "layer": {
                        "type": "integer",
                        "enum": sorted(_FINDING_LAYERS),
                        "description": "1=entity, 2=description, 3=claim",
                    },
                    "verdict": {
                        "type": "string",
                        "enum": sorted(_FINDING_VERDICTS),
                    },
                    "evidence": {
                        "type": "string",
                        "description": "one-sentence justification pointing to the source",
                    },
                },
                "required": ["page", "claim", "type", "layer", "verdict"],
            },
            handler=_report_finding,
        ),
        Tool(
            name="finish",
            description=(
                "Signal that the operation is complete. Provide a short summary of what "
                "you did (for ingest/lint) or your final answer (for query)."
            ),
            parameters={
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
            handler=_finish,
        ),
    ]
}


# report_finding is only meaningful inside a hallucination sweep — it would
# just clutter the ingest/lint tool surface, so it's excluded from those sets.
_HALLUCINATION_ONLY = {"report_finding"}

READ_ONLY_TOOLS = ["list_pages", "read_page", "read_index", "read_schema", "list_raw", "read_raw", "finish"]
INGEST_TOOLS = [name for name in ALL_TOOLS if name not in _HALLUCINATION_ONLY]
LINT_TOOLS = [name for name in ALL_TOOLS if name not in _HALLUCINATION_ONLY]
HALLUCINATION_TOOLS = [
    "list_pages",
    "read_page",
    "read_index",
    "read_schema",
    "list_raw",
    "read_raw",
    "report_finding",
    "append_log",
    "finish",
]


def schemas_for(allowed: list[str]) -> list[dict[str, Any]]:
    return [ALL_TOOLS[name].schema() for name in allowed if name in ALL_TOOLS]


def dispatch(wiki: Wiki, name: str, raw_args: str) -> str:
    """Run a tool call and return its result as a string.

    Errors (invalid args, missing pages, validation failures) are returned as
    text so the agent loop can keep going.
    """
    tool = ALL_TOOLS.get(name)
    if tool is None:
        return f"ERROR: unknown tool {name!r}"
    try:
        args = json.loads(raw_args) if raw_args else {}
    except json.JSONDecodeError as e:
        return f"ERROR: invalid JSON arguments: {e}"
    if not isinstance(args, dict):
        return "ERROR: tool arguments must be a JSON object"
    try:
        return tool.handler(wiki, args)
    except (ValueError, FileNotFoundError) as e:
        return f"ERROR: {e}"
    except Exception as e:  # noqa: BLE001 — surface anything else to the LLM
        return f"ERROR: unexpected {type(e).__name__}: {e}"
