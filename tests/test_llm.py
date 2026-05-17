"""Tests for app.llm — _preview, AgentResult, _client, run_agent, run_loop.

The OpenAI client is replaced with a scripted `_FakeClient` so the loop can be
driven deterministically and we never hit the network. Each test that needs
the loop installs its own list of `_FakeMessage`s in the order the (fake)
model will emit them.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app import llm
from app.llm import AgentResult, _preview, run_agent, run_loop
from app.tools import INGEST_TOOLS, READ_ONLY_TOOLS
from app.wiki import Wiki


# ============================================================== FakeClient

class _FakeToolCall:
    """Shape-compatible stand-in for openai.types.chat.ChatCompletionMessageToolCall."""

    def __init__(self, *, id: str, name: str, arguments: str = "{}"):
        self.id = id
        self.type = "function"
        self.function = SimpleNamespace(name=name, arguments=arguments)


class _FakeMessage:
    def __init__(
        self,
        *,
        content: str | None = None,
        tool_calls: list[_FakeToolCall] | None = None,
    ):
        self.content = content
        self.tool_calls = tool_calls


class _FakeResp:
    def __init__(self, message: _FakeMessage):
        self.choices = [SimpleNamespace(message=message)]


class _FakeClient:
    """Scripted OpenAI client. Each call to `chat.completions.create` pops the
    next response off the script and records the kwargs it was called with."""

    def __init__(self, scripted: list[_FakeMessage]):
        self._scripted: list[_FakeMessage] = list(scripted)
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs: Any) -> _FakeResp:
        # Deep-copy so callers see the messages exactly as they were at this
        # call, not after the loop appends more turns to the live list.
        self.calls.append({**kwargs, "messages": copy.deepcopy(kwargs["messages"])})
        if not self._scripted:
            raise AssertionError("FakeClient ran out of scripted responses")
        return _FakeResp(self._scripted.pop(0))


def _install_fake_client(monkeypatch: pytest.MonkeyPatch, fake: _FakeClient) -> None:
    monkeypatch.setattr(llm, "_client", lambda: fake)


# ================================================================ fixtures

@pytest.fixture
def wiki(tmp_path: Path) -> Wiki:
    w = Wiki(tmp_path / "ws")
    w.ensure()
    return w


# ================================================================== _preview

def test_preview_returns_text_unchanged_when_under_limit():
    assert _preview("hello") == "hello"


def test_preview_truncates_with_suffix_when_over_limit():
    long = "x" * 500

    out = _preview(long, limit=400)

    assert out.startswith("x" * 400)
    assert out.endswith("... (100 more chars)")
    assert len(out) == 400 + len("... (100 more chars)")


def test_preview_respects_custom_limit():
    out = _preview("abcdefghij", limit=4)

    assert out == "abcd... (6 more chars)"


def test_preview_handles_none_as_empty_string():
    assert _preview(None) == ""  # type: ignore[arg-type]


def test_preview_handles_empty_string():
    assert _preview("") == ""


# =============================================================== AgentResult

def test_agent_result_default_trace_is_fresh_empty_list():
    a = AgentResult(final_text="a")
    b = AgentResult(final_text="b")
    a.trace.append("contamination")  # type: ignore[arg-type]

    assert b.trace == []


# =================================================================== _client

def test_client_constructs_openai_with_settings(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    class _SpyOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm, "OpenAI", _SpyOpenAI)
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="sk-test",
            openai_base_url="https://example.test/v1",
        ),
    )

    llm._client()

    assert captured == {"api_key": "sk-test", "base_url": "https://example.test/v1"}


# =================================================================== run_agent

def test_run_agent_builds_system_user_thread_and_returns_final_text(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([_FakeMessage(content="final answer")])
    _install_fake_client(monkeypatch, fake)

    result = run_agent(
        wiki=wiki,
        system_prompt="SYS",
        user_prompt="USER",
        allowed_tools=READ_ONLY_TOOLS,
    )

    assert result.final_text == "final answer"
    # The very first request the model sees is exactly [system, user].
    sent_messages = fake.calls[0]["messages"]
    assert sent_messages[0] == {"role": "system", "content": "SYS"}
    assert sent_messages[1] == {"role": "user", "content": "USER"}


def test_run_agent_forwards_max_iterations_to_run_loop(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    captured: dict[str, Any] = {}

    def fake_run_loop(*, wiki, messages, allowed_tools, max_iterations=None):
        captured["max_iterations"] = max_iterations
        return AgentResult(final_text="ok", trace=[])

    monkeypatch.setattr(llm, "run_loop", fake_run_loop)

    run_agent(
        wiki=wiki,
        system_prompt="s",
        user_prompt="u",
        allowed_tools=READ_ONLY_TOOLS,
        max_iterations=7,
    )

    assert captured["max_iterations"] == 7


def test_run_loop_explicit_max_iterations_overrides_settings(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    # Settings says 25; the explicit kwarg should win and cap at 3.
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(model_name="m", max_tool_iterations=25),
    )
    fake = _FakeClient([
        _FakeMessage(tool_calls=[_FakeToolCall(id="a", name="list_pages")]),
        _FakeMessage(tool_calls=[_FakeToolCall(id="b", name="list_pages")]),
        _FakeMessage(tool_calls=[_FakeToolCall(id="c", name="list_pages")]),
    ])
    _install_fake_client(monkeypatch, fake)

    result = run_loop(
        wiki=wiki,
        messages=[{"role": "user", "content": "x"}],
        allowed_tools=READ_ONLY_TOOLS,
        max_iterations=3,
    )

    # Exactly N create calls happen before the fallback fires.
    assert len(fake.calls) == 3
    assert "MAX_TOOL_ITERATIONS" in result.final_text
    assert "[3]" in result.final_text


def test_run_agent_passes_allowed_tools_through(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([_FakeMessage(content="done")])
    _install_fake_client(monkeypatch, fake)

    run_agent(
        wiki=wiki,
        system_prompt="x",
        user_prompt="y",
        allowed_tools=["list_pages", "finish"],
    )

    tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert tool_names == {"list_pages", "finish"}


# ==================================================================== run_loop

def test_run_loop_returns_final_text_when_model_emits_no_tool_calls(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([_FakeMessage(content="here is the answer")])
    _install_fake_client(monkeypatch, fake)
    messages = [{"role": "user", "content": "hi"}]

    result = run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    assert result.final_text == "here is the answer"
    assert result.trace == []
    # No tool_calls means the model only emits an assistant message, appended in place.
    assert messages[-1] == {"role": "assistant", "content": "here is the answer"}


def test_run_loop_finish_short_circuits_with_summary(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="finish", arguments=json.dumps({"summary": "all done"})),
        ]),
    ])
    _install_fake_client(monkeypatch, fake)
    messages = [{"role": "user", "content": "go"}]

    result = run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    assert result.final_text == "all done"
    assert len(result.trace) == 1
    assert result.trace[0].tool == "finish"
    assert result.trace[0].args == {"summary": "all done"}


def test_run_loop_executes_single_tool_call_then_returns_next_content(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="list_pages", arguments="{}"),
        ]),
        _FakeMessage(content="reply after tool"),
    ])
    _install_fake_client(monkeypatch, fake)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "x"}]

    result = run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    assert result.final_text == "reply after tool"
    # Messages should now contain: original user, assistant (tool_call), tool result, assistant final.
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert messages[2]["tool_call_id"] == "t1"


def test_run_loop_trace_records_tool_name_args_and_preview(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    wiki.write_page("alpha", "# alpha")
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="read_page", arguments=json.dumps({"name": "alpha"})),
        ]),
        _FakeMessage(content="ok"),
    ])
    _install_fake_client(monkeypatch, fake)

    result = run_loop(
        wiki=wiki,
        messages=[{"role": "user", "content": "x"}],
        allowed_tools=READ_ONLY_TOOLS,
    )

    [step] = result.trace
    assert step.tool == "read_page"
    assert step.args == {"name": "alpha"}
    assert isinstance(step.result_preview, str)
    assert step.result_preview.startswith("# alpha")


def test_run_loop_truncates_trace_but_sends_full_result_to_model(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    big = "x" * 1000
    wiki.write_page("big", big)
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="read_page", arguments=json.dumps({"name": "big"})),
        ]),
        _FakeMessage(content="done"),
    ])
    _install_fake_client(monkeypatch, fake)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "x"}]

    result = run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    # Trace is truncated...
    assert "more chars" in result.trace[0].result_preview
    assert len(result.trace[0].result_preview) < len(big)
    # ...but the tool message sent to the next model call carries the full text.
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert tool_msg["content"] == big
    # And the second create() call received that full tool message.
    assert fake.calls[1]["messages"][-1]["content"] == big


def test_run_loop_unknown_tool_name_produces_error_preview_and_continues(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="totally-fake-tool", arguments="{}"),
        ]),
        _FakeMessage(content="recovered"),
    ])
    _install_fake_client(monkeypatch, fake)

    result = run_loop(
        wiki=wiki,
        messages=[{"role": "user", "content": "x"}],
        allowed_tools=READ_ONLY_TOOLS,
    )

    assert result.final_text == "recovered"
    assert result.trace[0].result_preview.startswith("ERROR")


def test_run_loop_hits_max_iterations_returns_fallback(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    # Force a low cap so we don't burn 25 scripted responses.
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(model_name="m", max_tool_iterations=2),
    )
    fake = _FakeClient([
        _FakeMessage(tool_calls=[_FakeToolCall(id="t1", name="list_pages")]),
        _FakeMessage(tool_calls=[_FakeToolCall(id="t2", name="list_pages")]),
    ])
    _install_fake_client(monkeypatch, fake)

    result = run_loop(
        wiki=wiki,
        messages=[{"role": "user", "content": "x"}],
        allowed_tools=READ_ONLY_TOOLS,
    )

    assert "MAX_TOOL_ITERATIONS" in result.final_text
    assert len(result.trace) == 2


def test_run_loop_dispatches_multiple_tool_calls_in_one_response(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="a", name="list_pages"),
            _FakeToolCall(id="b", name="read_index"),
        ]),
        _FakeMessage(content="ok"),
    ])
    _install_fake_client(monkeypatch, fake)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "x"}]

    result = run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    # Two trace entries, in order.
    assert [s.tool for s in result.trace] == ["list_pages", "read_index"]
    # Two tool messages appended, in order, before the next assistant turn.
    tool_msgs = [m for m in messages if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["a", "b"]


def test_run_loop_invalid_json_args_become_raw_in_trace(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="list_pages", arguments="not json{"),
        ]),
        _FakeMessage(content="ok"),
    ])
    _install_fake_client(monkeypatch, fake)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "x"}]

    run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    # The dispatch error is what gets sent back to the model as the tool result.
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert tool_msg["content"].startswith("ERROR")


def test_run_loop_non_dict_json_args_become_raw_in_trace(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([
        _FakeMessage(tool_calls=[
            _FakeToolCall(id="t1", name="list_pages", arguments="42"),
        ]),
        _FakeMessage(content="ok"),
    ])
    _install_fake_client(monkeypatch, fake)

    result = run_loop(
        wiki=wiki,
        messages=[{"role": "user", "content": "x"}],
        allowed_tools=READ_ONLY_TOOLS,
    )

    # 42 isn't a dict, so the loop boxes it as {"_raw": 42}.
    assert result.trace[0].args == {"_raw": 42}


def test_run_loop_mutates_caller_messages_in_place(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([_FakeMessage(content="done")])
    _install_fake_client(monkeypatch, fake)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "x"}]
    original_id = id(messages)

    run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    assert id(messages) == original_id  # same list, not replaced
    assert len(messages) == 2  # user + assistant
    assert messages[0] == {"role": "user", "content": "x"}


def test_run_loop_filters_tools_to_allowed_set(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    fake = _FakeClient([_FakeMessage(content="done")])
    _install_fake_client(monkeypatch, fake)

    run_loop(
        wiki=wiki,
        messages=[{"role": "user", "content": "x"}],
        allowed_tools=READ_ONLY_TOOLS,
    )

    sent_tool_names = {t["function"]["name"] for t in fake.calls[0]["tools"]}
    assert sent_tool_names == set(READ_ONLY_TOOLS)
    # Crucial: the LLM cannot see mutating tools in a read-only session.
    assert "write_page" not in sent_tool_names


def test_run_loop_uses_model_name_and_tool_choice_auto(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    monkeypatch.setattr(
        llm,
        "get_settings",
        lambda: SimpleNamespace(model_name="custom-model", max_tool_iterations=5),
    )
    fake = _FakeClient([_FakeMessage(content="done")])
    _install_fake_client(monkeypatch, fake)

    run_loop(
        wiki=wiki,
        messages=[{"role": "user", "content": "x"}],
        allowed_tools=READ_ONLY_TOOLS,
    )

    assert fake.calls[0]["model"] == "custom-model"
    assert fake.calls[0]["tool_choice"] == "auto"


def test_run_loop_assistant_entry_includes_tool_calls_on_replay(
    monkeypatch: pytest.MonkeyPatch, wiki: Wiki
):
    # The assistant turn that triggered a tool_call must be appended verbatim
    # so the next round's request includes the tool_calls block (required by
    # OpenAI's tool-use protocol).
    fake = _FakeClient([
        _FakeMessage(tool_calls=[_FakeToolCall(id="t1", name="list_pages")]),
        _FakeMessage(content="done"),
    ])
    _install_fake_client(monkeypatch, fake)
    messages: list[dict[str, Any]] = [{"role": "user", "content": "x"}]

    run_loop(wiki=wiki, messages=messages, allowed_tools=READ_ONLY_TOOLS)

    assistant_entry = messages[1]
    assert assistant_entry["role"] == "assistant"
    assert assistant_entry["tool_calls"][0]["id"] == "t1"
    assert assistant_entry["tool_calls"][0]["function"]["name"] == "list_pages"
