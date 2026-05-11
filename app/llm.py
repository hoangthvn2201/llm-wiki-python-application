"""OpenAI-compatible client and the agentic tool-use loop.

The same loop drives ingest, query, and lint — only the system prompt and the
allowed tool subset change.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.schemas import TraceStep
from app.tools import dispatch, schemas_for
from app.wiki import Wiki


@dataclass
class AgentResult:
    final_text: str
    trace: list[TraceStep] = field(default_factory=list)


def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url)


def _preview(text: str, limit: int = 400) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"... ({len(text) - limit} more chars)"


def run_agent(
    *,
    wiki: Wiki,
    system_prompt: str,
    user_prompt: str,
    allowed_tools: list[str],
) -> AgentResult:
    """Single-turn entry point: builds a fresh [system, user] thread."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return run_loop(wiki=wiki, messages=messages, allowed_tools=allowed_tools)


def run_loop(
    *,
    wiki: Wiki,
    messages: list[dict[str, Any]],
    allowed_tools: list[str],
) -> AgentResult:
    """Run the tool-use loop on a pre-built message list.

    Caller is responsible for building the full thread (system prompt + any
    prior conversation history). The loop appends assistant turns and tool
    results in place; the final assistant content (or `finish` summary) is
    returned.
    """
    settings = get_settings()
    client = _client()
    tools = schemas_for(allowed_tools)
    trace: list[TraceStep] = []

    for _ in range(settings.max_tool_iterations):
        response = client.chat.completions.create(
            model=settings.model_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        # Append the assistant turn verbatim so the next round sees its tool_calls.
        assistant_entry: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        if not msg.tool_calls:
            # No tool calls: model is done. Use its plain content as the final answer.
            return AgentResult(final_text=msg.content or "(no response)", trace=trace)

        finish_summary: str | None = None
        for call in msg.tool_calls:
            name = call.function.name
            raw_args = call.function.arguments or "{}"
            try:
                parsed_args = json.loads(raw_args)
                if not isinstance(parsed_args, dict):
                    parsed_args = {"_raw": parsed_args}
            except json.JSONDecodeError:
                parsed_args = {"_raw": raw_args}

            if name == "finish":
                finish_summary = parsed_args.get("summary", "")
                result_str = f"FINISHED: {finish_summary}"
            else:
                result_str = dispatch(wiki, name, raw_args)

            trace.append(
                TraceStep(tool=name, args=parsed_args, result_preview=_preview(result_str))
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result_str,
                }
            )

        if finish_summary is not None:
            return AgentResult(final_text=finish_summary, trace=trace)

    return AgentResult(
        final_text="(agent hit MAX_TOOL_ITERATIONS without calling finish)",
        trace=trace,
    )
