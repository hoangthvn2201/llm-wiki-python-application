# Unit Test Catalogue

This document is the **source of truth for desired behaviour** of every Python function in `app/`. Each function has a short stanza with its contract and a numbered list of tests we want. The test suite under `tests/` is the implementation of this catalogue.

Legend:
- ✅ — a test exists today (referenced in the existing-tests column)
- 🟡 — partially covered (some cases tested, others missing)
- ❌ — missing, must be added

When you add a function, add a stanza here first. When you add a test, flip the corresponding entry to ✅. The gap matrix at the bottom of the file is what you scan to know where work remains.

---

## 1. How to read this file

Every module in `app/` has its own section under §3. Inside a section, each function gets a sub-stanza:

```
**function_name(args) -> ReturnType** STATUS
1. Behaviour the test should pin. STATUS
2. Another behaviour. STATUS
```

Statuses on individual bullets reflect the *test*, not the production code. Production code is assumed correct; tests assert that it stays correct.

---

## 2. Conventions

- **File layout**: one `tests/test_<module>.py` per source module. New files in this iteration: `test_llm.py`, `test_config.py`, `test_operations.py`, `test_main.py`, `test_prompts.py`, `test_schemas.py`.
- **Test name pattern**: `test_<function>_<behaviour_in_snake_case>`. Example: `test_run_loop_returns_final_text_when_model_emits_no_tool_calls`.
- **AAA layout**: arrange / act / assert separated by a blank line. **One behaviour per test** — multiple `assert`s in a single test are fine only if they all describe one logical behaviour.
- **Fixtures**: keep per-file pytest fixtures (`wiki(tmp_path)` etc.) for now. Only promote to a shared `conftest.py` when the same fixture is duplicated in three or more test files.
- **FS isolation**: every test that touches the wiki uses `tmp_path` — never the real `workspace/`.
- **Mocking strategy**:
  - **LLM**: monkeypatch `app.llm._client` to return a stub whose `chat.completions.create` returns a scripted sequence of responses (each carrying `choices[0].message.content` and/or `.tool_calls`). Build a `_FakeClient` helper in `tests/test_llm.py` and reuse it.
  - **Orchestrator-as-unit**: when testing routes or the non-LLM portion of `chat()` / `query()` / `lint()`, monkeypatch `app.operations.run_agent` / `app.operations.run_loop` to return a canned `AgentResult`.
  - **PDF**: reuse the `_FakeExtractor` pattern from `tests/test_ingest_pdf.py`.
  - **Settings**: monkeypatch `app.config._settings = None` and `monkeypatch.setenv(...)` to test env-var loading; reset after.
- **Determinism**: anything that depends on `date.today()` or random state must be patched or asserted against a regex / format predicate, not an exact value.
- **No network**: tests must run with `OPENAI_API_KEY` unset. Anything that would call the real OpenAI API must be mocked.

---

## 3. Per-module catalogue

### 3.1 `app/wiki.py`

#### `_ensure_slug(name: str) -> str` ✅
1. Accepts valid kebab-case. ✅
2. Rejects invalid forms. ✅
3. Strips surrounding whitespace before matching. ✅
4. Returns the *stripped* name so callers see canonical form. ✅

#### `Wiki.__init__(root: Path) -> None` ✅
1. Expands `~` in the supplied root. ✅
2. Resolves relative paths to absolute. ✅
3. Does not touch the filesystem. ✅

#### `Wiki.ensure() -> None` ✅
1. Creates `root/`, `raw/`, `wiki/`. ✅
2. Creates `index.md`, `log.md`, `SCHEMA.md` when missing. ✅
3. Idempotent — preserves existing content on second call. ✅
4. Default `index.md` contains the four section headers (Entities, Concepts, Sources, Reports). ✅
5. Default `SCHEMA.md` equals the `DEFAULT_SCHEMA` constant. ✅
6. Default `log.md` is `"# Log\n\n"`. ✅
7. Does not overwrite a custom schema on re-ensure. ✅

#### `Wiki._safe_path(*parts: str) -> Path` ✅
1. Returns a path under `root` for normal parts. ✅
2. Raises `ValueError` for `..` traversal. ✅
3. Raises `ValueError` when an absolute path is passed. ✅

#### `Wiki.list_pages() -> list[str]` ✅
1. Returns sorted slug stems of `wiki/*.md`. ✅
2. Returns `[]` when no pages exist. ✅
3. Ignores non-`.md` files and subdirectories under `wiki/`. ✅

#### `Wiki.page_exists(name: str) -> bool` ✅
1. `True` after `write_page`. ✅
2. `False` for missing page. ✅
3. Raises `ValueError` for invalid slug. ✅

#### `Wiki.read_page(name: str) -> str` ✅
1. Returns UTF-8 content of an existing page. ✅
2. Raises `FileNotFoundError` for missing page. ✅
3. Raises `ValueError` for invalid slug. ✅
4. Round-trips non-ASCII (emoji, accents). ✅ (via `write_page` test)

#### `Wiki.write_page(name: str, content: str) -> None` ✅
1. Creates a new page. ✅
2. Overwrites an existing page (no append). ✅
3. Rejects invalid slug with `ValueError`. ✅
4. Persists content as UTF-8 (round-trips emoji / accents). ✅

#### `Wiki.delete_page(name: str) -> None` ✅
1. Removes an existing page. ✅
2. No-op when page is missing. ✅
3. Rejects invalid slug. ✅

#### `Wiki.read_index() -> str` / `Wiki.write_index(content: str) -> None` ✅
1. `write_index` then `read_index` round-trips the supplied content exactly. ✅

#### `Wiki.read_log() -> str` / `Wiki.append_log(entry: str) -> None` ✅
1. Appended entry shows up in `read_log()`. ✅
2. Inserts a blank line separator before the new entry when the file did not already end with `\n\n`. ✅
3. Strips trailing whitespace from `entry` and ensures the file ends with exactly one trailing newline. ✅
4. Initialises log with `"# Log\n\n"` when `log.md` does not exist on disk. ✅
5. Two successive calls produce two distinct entries with the blank-line separator between them. ✅

#### `Wiki.log_entry_header(op: str, title: str) -> str` ✅
1. Format is `## [YYYY-MM-DD] <op> | <title>` using today's ISO date — asserted directly. ✅

#### `Wiki.read_schema() -> str` / `Wiki.write_schema(content: str) -> None` ✅
1. `write_schema` then `read_schema` round-trips. ✅
2. `ensure()` does not overwrite a custom schema. ✅

#### `Wiki.list_raw() -> list[str]` / `Wiki.read_raw(name) -> str` / `Wiki.write_raw(name, content) -> Path` ✅
1. Round-trip (`write_raw` → `list_raw` → `read_raw`). ✅
2. `write_raw` returns the resolved `Path` of the written file. ✅
3. `read_raw` raises `FileNotFoundError` for a missing source. ✅
4. `read_raw` rejects invalid slug. ✅
5. `list_raw` returns sorted slugs and `[]` when empty. ✅

---

### 3.2 `app/config.py`

All tests in a new `tests/test_config.py`. Each test resets `app.config._settings = None` before instantiating `Settings()` so env-var changes are picked up.

#### `Settings` field defaults ✅
1. `openai_api_key` defaults to `"sk-missing"` when env var is unset. ✅
2. `openai_base_url` defaults to `"https://api.openai.com/v1"`. ✅
3. `model_name` defaults to `"gpt-4o-mini"`. ✅
4. `workspace_dir` defaults to `Path("./workspace")`. ✅
5. `max_tool_iterations` defaults to `25` (int). ✅
6. Per-op iteration caps default sensibly: `_ingest=25`, `_query=25`, `_chat=25`, `_lint=50`, `_hallucination=150`. ✅ (`test_settings_per_op_iteration_cap_defaults`)

#### `Settings` env-var binding ✅
1. `OPENAI_API_KEY=abc` is read into `openai_api_key`. ✅
2. `MAX_TOOL_ITERATIONS=5` is parsed as `int` (not str). ✅
3. `WORKSPACE_DIR=/tmp/foo` is coerced to `Path("/tmp/foo")`. ✅
4. Unknown env vars are ignored (`extra="ignore"`). ✅
5. `MAX_TOOL_ITERATIONS_HALLUCINATION=200` binds to `max_tool_iterations_hallucination` as int (parametrized across all five per-op caps). ✅ (`test_settings_per_op_iteration_caps_bind_from_env`)

#### `Settings.workspace_path` ✅
1. Expands `~` in `workspace_dir`. ✅
2. Resolves relative paths to absolute (anchored to CWD at access time). ✅

#### `get_settings()` ✅
1. First call constructs a `Settings`; subsequent calls return the same instance (`is` check). ✅
2. After resetting `_settings = None`, the next call constructs a fresh instance. ✅

---

### 3.3 `app/tools.py`

#### `Tool.schema()` ✅
1. Returns `{"type": "function", "function": {"name", "description", "parameters"}}` shape. ✅
2. `parameters.type == "object"`. ✅

#### `schemas_for(allowed: list[str]) -> list[dict]` ✅
1. Returns only schemas whose name is in `allowed`. ✅
2. `READ_ONLY_TOOLS` result excludes mutating tools. ✅
3. Silently drops unknown names in `allowed` (does not raise). ✅

#### `dispatch(wiki, name, raw_args) -> str` ✅
1. Unknown tool → string starting with `ERROR`. ✅
2. Invalid JSON → string starting with `ERROR`. ✅
3. Non-object JSON args (`"42"`, `"[1, 2]"`) → `ERROR: tool arguments must be a JSON object`. ✅
4. Handler `ValueError` → `ERROR: <msg>`. ✅
5. Handler `FileNotFoundError` → `ERROR: <msg>`. ✅
6. Unexpected exception → `ERROR: unexpected <Type>: <msg>`. ✅ (monkeypatched handler raises `RuntimeError`)
7. Empty `raw_args` (`""`) defaults to `{}`. ✅

#### `_report_finding(wiki, args) -> str` ✅
1. Records a well-formed finding on `wiki._hallucination_findings` (lazy-inits the list if absent). ✅ (`test_report_finding_accumulates_on_wiki`)
2. Two successive calls produce two distinct entries in order. ✅
3. Rejects unknown `type` with `ERROR:` mentioning the bad value. ✅ (`test_report_finding_rejects_bad_type`)
4. Rejects unknown `verdict` with `ERROR:`. ✅ (`test_report_finding_rejects_bad_verdict`)
5. Rejects `layer` outside `{1, 2, 3}` with `ERROR:`. ✅ (`test_report_finding_rejects_bad_layer`)
6. Missing required field (`page` / `claim` / `type` / `layer` / `verdict`) → `ERROR:` mentioning the field. ✅ (`test_report_finding_missing_required_field`)
7. `evidence` is optional and defaults to `""`. ✅ (covered in accumulation test)
8. Return string includes `type`, `verdict`, `page`, and the layer (acks a human-readable record). ✅

#### Tool handlers (`_list_pages`, `_read_page`, `_write_page`, `_read_index`, `_write_index`, `_append_log`, `_read_schema`, `_list_raw`, `_read_raw`, `_finish`) ✅

1. `_list_pages` empty → `"(no wiki pages yet)"`. ✅
2. `_list_pages` with pages → newline-joined sorted slugs. ✅
3. `_read_page` returns the page content. ✅
4. `_write_page` returns `"created wiki/<name>.md (...)"` for new page. ✅
5. `_write_page` returns `"updated ..."` when page already exists. ✅
6. `_read_index` returns current `index.md` content. ✅
7. `_write_index` writes and returns confirmation string with char count. ✅
8. `_append_log` returns `"appended <n> chars to log.md"`. ✅
9. `_read_schema` returns current schema. ✅
10. `_list_raw` empty → `"(no raw sources)"`; with raws → newline-joined sorted slugs. ✅
11. `_read_raw` returns raw content; missing raw → `ERROR: ...` via dispatch. ✅
12. `_finish` returns `"FINISHED: <summary>"`; missing summary → `"FINISHED: (no summary)"`. ✅

#### Tool sets ✅
1. `READ_ONLY_TOOLS` excludes every mutating tool (`write_page`/`write_index`/`append_log`). ✅
2. `INGEST_TOOLS` is a superset of `READ_ONLY_TOOLS`. ✅
3. `LINT_TOOLS` covers all tools except hallucination-only ones (`set(LINT_TOOLS) == set(ALL_TOOLS) - {"report_finding"}`). ✅ (`test_lint_tools_covers_all_except_hallucination_only`)
4. Every name in `READ_ONLY_TOOLS`/`INGEST_TOOLS`/`LINT_TOOLS`/`HALLUCINATION_TOOLS` exists in `ALL_TOOLS`. ✅
5. `INGEST_TOOLS` and `LINT_TOOLS` both exclude `report_finding`. ✅ (`test_ingest_and_lint_tools_exclude_report_finding`)
6. `HALLUCINATION_TOOLS` excludes `write_page` and `write_index` (read-only over wiki) but includes `report_finding` and `append_log`. ✅ (`test_hallucination_tools_excludes_write_pages`)

---

### 3.4 `app/llm.py`

All tests in a new `tests/test_llm.py`. Use a `_FakeClient` helper that lets each test script a sequence of fake completions. Monkeypatch `app.llm._client` to return the fake.

```python
# Sketch — actual implementation lives in test_llm.py
class _FakeChoice:
    def __init__(self, content=None, tool_calls=None):
        self.message = SimpleNamespace(content=content, tool_calls=tool_calls or [])

class _FakeResp:
    def __init__(self, choice): self.choices = [choice]

class _FakeClient:
    def __init__(self, scripted: list[_FakeResp]):
        self._scripted = scripted
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.calls = []
    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._scripted.pop(0)
```

#### `_preview(text: str, limit: int = 400) -> str` ✅
1. Returns input unchanged when `len(text) <= limit`. ✅
2. Returns `text[:limit] + "... (N more chars)"` when longer; `N` equals `len(text) - limit`. ✅
3. Treats `None` / empty as `""` (no exception). ✅
4. `limit` is honoured when passed explicitly. ✅

#### `AgentResult` dataclass ✅
1. Default `trace` is a fresh empty list per instance (not a shared mutable default). ✅

#### `_client()` ✅
1. Constructs `OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)`. ✅ (spy on `app.llm.OpenAI`)

#### `run_agent(wiki, system_prompt, user_prompt, allowed_tools, max_iterations=None)` ✅
1. Builds messages `[{role:"system", ...}, {role:"user", ...}]` and delegates to `run_loop`. ✅
2. Returns the `AgentResult` returned by `run_loop` verbatim. ✅
3. Passes `allowed_tools` through unchanged. ✅
4. Forwards an explicit `max_iterations` value to `run_loop`. ✅ (`test_run_agent_forwards_max_iterations_to_run_loop`)

#### `run_loop(wiki, messages, allowed_tools, max_iterations=None)` ✅
1. **Plain final answer**: when the model emits content with no `tool_calls`, returns `AgentResult(final_text=content, trace=[])`. Messages list grows by one assistant entry. ✅
2. **`finish` short-circuit**: when the model emits a `finish` tool_call, the loop returns `AgentResult(final_text=summary, trace=[<one step>])` after one round. ✅
3. **Single tool call**: model calls `list_pages`, loop dispatches it, appends `{role:"tool", tool_call_id, content}`, then the next round's plain content becomes `final_text`. ✅
4. **Trace shape**: every trace entry has `tool` (str), `args` (dict), `result_preview` (str ≤ 400 chars plus optional suffix). ✅
5. **Trace truncation does not affect model context**: a tool result of >400 chars is sent verbatim to the model (in the `tool` message) but truncated in the returned `trace`. ✅
6. **Unknown tool name** in a tool_call still produces a trace entry whose `result_preview` starts with `ERROR`; the loop continues. ✅
7. **Max iterations**: returns the `"(agent hit MAX_TOOL_ITERATIONS [N]...)"` fallback after the effective cap rounds (`max_iterations` arg if provided, else `settings.max_tool_iterations`). ✅
7a. When called with an explicit `max_iterations=N`, exactly `N` `chat.completions.create` calls happen before the fallback is returned. ✅ (`test_run_loop_explicit_max_iterations_overrides_settings`)
8. **Multiple tool calls in one response**: all dispatched in order; tool messages appended in same order before the next request. ✅
9. **Invalid JSON in tool args**: `parsed_args` becomes `{"_raw": "<raw string>"}` in the trace; the `tool` message contains the dispatch error string. ✅ (also covered: non-dict JSON `42` → `{"_raw": 42}`)
10. **In-place mutation**: caller's `messages` list grows; previously-appended messages are preserved. ✅
11. **Tools filtered by `allowed_tools`**: the OpenAI call receives schemas only for the allowed names; `write_page` never visible in a read-only run. ✅
12. **Model name & tool_choice**: each `create` call uses `settings.model_name` and `tool_choice="auto"`. ✅
13. **Assistant turn with tool_calls is appended verbatim** so the next OpenAI request includes the `tool_calls` block required by the protocol. ✅

---

### 3.5 `app/prompts.py` ✅

One sanity test per prompt to lock the workflow contract. These catch accidental edits that delete a step.

1. `INGEST_SYSTEM` is non-empty and mentions every tool the workflow names: `read_schema`, `read_index`, `read_page`, `write_page`, `write_index`, `append_log`, `finish`. ✅
2. `INGEST_SYSTEM` mentions the kebab-case slug rule and `[[page-name]]` cross-reference syntax. ✅
3. `QUERY_SYSTEM` is non-empty, mentions `read_index`, `read_page`, `finish`, and explicitly states "READ-ONLY". ✅
4. `QUERY_SYSTEM` does NOT mention any write tool (`write_page`, `write_index`, `append_log`). ✅
5. `CHAT_SYSTEM` is non-empty, mentions "READ-ONLY", `read_index`, `read_page`, `finish`, the cross-reference syntax, and redirects writes to Ingest/Lint tabs. ✅
6. `LINT_SYSTEM` is non-empty, mentions `read_schema`, `read_index`, `read_page`, `write_page`, `write_index`, `append_log`, `finish`. ✅
7. `HALLUCINATION_SYSTEM` is non-empty, declares "READ-ONLY" over the wiki, names every tool the workflow invokes (`read_schema`, `read_index`, `read_page`, `list_raw`, `read_raw`, `report_finding`, `append_log`, `finish`), and names every claim-type bucket (`factual`, `quantitative`, `relational`, `temporal`, `negation`, `synthesis`) and every verdict (`supported`, `contradicted`, `unverifiable`, `hallucination`). ✅ (parametrized `test_hallucination_system_mentions_required_tool`, `_mentions_claim_type`, `_mentions_verdict`, plus `_is_non_empty` and `_declares_read_only`)
8. `HALLUCINATION_SYSTEM` actively forbids the write tools — the strings appear only under a "MUST NOT" / "do not" instruction, not as a recommended action. ✅ (`test_hallucination_system_forbids_write_tools_explicitly`)
9. `HALLUCINATION_SYSTEM` describes the three layers in order (entity → description → claim). ✅ (`test_hallucination_system_describes_layers_in_order`)

---

### 3.6 `app/schemas.py` ✅

Trust Pydantic; pin only the fields *we* depend on.

1. `ChatMessage(role="user", content="hi")` constructs successfully; `role` accepts arbitrary strings (validation lives in `operations.chat`). ✅
2. `ChatMessage` rejects missing `role` or `content`. ✅
3. `ChatRequest(messages=[])` parses successfully (empty list is allowed at the schema layer; rejected at the orchestrator). ✅
4. `ChatResponse(reply="x", trace=[])` constructs; `trace` defaults sensibly. ✅
5. `TraceStep(tool="t", result_preview="r")` has `args == {}` by default (field default factory). ✅ — also pin that the default dict is not shared between instances.
6. `IngestRequest` rejects missing `source_name` or `content`. ✅
7. `SchemaUpdate` rejects missing `content_md`. ✅
8. `PageView`/`IndexView`/`LogView`/`SchemaView` accept their expected fields without surprise. ✅ — `LogView`/`SchemaView` pinned to be md-only (no `content_html`).
9. `HallucinationFinding` accepts a fully-specified record (`page`, `claim`, `type`, `layer`, `verdict`, `evidence`). ✅ (`test_hallucination_finding_accepts_fully_specified_record`)
10. `HallucinationFinding` rejects an unknown `type` literal (Pydantic `Literal` validation). ✅ (`test_hallucination_finding_rejects_unknown_type`)
11. `HallucinationFinding` rejects an unknown `verdict` literal. ✅ (`test_hallucination_finding_rejects_unknown_verdict`)
12. `HallucinationFinding` rejects a `layer` outside `[1, 3]` (Pydantic `ge=1, le=3`). ✅ (parametrized `test_hallucination_finding_rejects_layer_out_of_range`)
13. `HallucinationFinding.evidence` defaults to `""`. ✅ (`test_hallucination_finding_evidence_defaults_to_empty_string`)
14. `HallucinationCheckResult` requires `summary`, `findings`, `report_path`, `trace`. ✅ (parametrized `test_hallucination_check_result_rejects_missing_field` + happy-path constructor test)

---

### 3.7 `app/operations.py`

All tests in a new `tests/test_operations.py`. Monkeypatch `app.config.get_settings` to point `workspace_path` at `tmp_path`. Monkeypatch `app.operations.run_agent` (and `run_loop` for `chat`) to capture arguments and return canned `AgentResult`s.

#### `_wiki()` ✅
1. Returns a `Wiki` rooted at `settings.workspace_path` with the workspace already initialised (after the call, `index.md`/`log.md`/`SCHEMA.md` exist on disk). ✅

#### `ingest(source_name, content)` ✅
1. Writes `raw/<source_name>.md` with the supplied content **before** calling `run_agent`. ✅
2. Calls `run_agent` with `system_prompt=INGEST_SYSTEM`, `allowed_tools=INGEST_TOOLS`. ✅
3. User prompt embeds the raw content between `--- BEGIN SOURCE ---` and `--- END SOURCE ---` markers and names the raw path as `raw/<source_name>.md`. ✅
4. Returns `IngestResult(summary=run_agent.final_text, trace=run_agent.trace)`. ✅
5. Propagates a `ValueError` from `Wiki.write_raw` (bad slug) without calling `run_agent`. ✅
6. Passes `max_iterations=settings.max_tool_iterations_ingest` to `run_agent`. ✅ (`test_ingest_uses_ingest_iteration_cap`)

#### `ingest_pdf(source_name, pdf_bytes, *, backend="pypdf")` ✅
1. Calls extractor returned by `get_pdf_extractor(backend)`, then delegates to `ingest`. ✅
2. When metadata is non-empty, includes a `## Document metadata` section in the content. ✅
3. When metadata is empty, omits the `## Document metadata` section. ✅
4. Wraps `PdfExtractionError` as `ValueError` (preserving message); does NOT call `ingest`. ✅
5. Content starts with `# <source_name>` heading. ✅
6. Default `backend="pypdf"`; unknown backend raises `ValueError` from `get_pdf_extractor`. ✅
7. Filename passed to the extractor is `<source_name>.pdf`. ✅

#### `query(question)` ✅
1. Calls `run_agent` with `system_prompt=QUERY_SYSTEM`, `allowed_tools=READ_ONLY_TOOLS`. ✅
2. User prompt contains the question. ✅
3. Returns `QueryResult(answer=..., trace=...)`. ✅
4. Passes `max_iterations=settings.max_tool_iterations_query` to `run_agent`. ✅ (`test_query_uses_query_iteration_cap`)

#### `chat(history)` ✅
1. Empty history → raises `ValueError`. ✅
2. Role other than `"user"` / `"assistant"` → raises `ValueError` mentioning the bad role. ✅
3. Calls `run_loop` with messages starting with `{role:"system", content: CHAT_SYSTEM}` followed by every history entry in order. ✅
4. Passes `allowed_tools=READ_ONLY_TOOLS` (chat is read-only). ✅
5. Returns `ChatResponse(reply=final_text, trace=trace)`. ✅
6. Multi-turn: a history with two user + one assistant message is preserved verbatim in the messages list. ✅
7. Passes `max_iterations=settings.max_tool_iterations_chat` to `run_loop`. ✅ (`test_chat_uses_chat_iteration_cap`)

#### `lint()` ✅
1. Calls `run_agent` with `system_prompt=LINT_SYSTEM`, `allowed_tools=LINT_TOOLS`. ✅
2. Returns `LintResult(report=final_text, trace=trace)`. ✅
3. Passes `max_iterations=settings.max_tool_iterations_lint` to `run_agent`. ✅ (`test_lint_uses_lint_iteration_cap`)

#### `_format_hallucination_report(findings) -> str` ✅
1. Empty findings list produces a report whose statistics block reads `Total findings: 0` and includes a "No findings were recorded" notice. ✅ (`test_hallucination_check_handles_no_findings`)
2. Non-empty findings produce per-verdict and per-layer counts; pages with contradictions / hallucinations are listed. ✅ (covered by `test_hallucination_check_writes_report_file`)
3. Findings are grouped under their layer header (`## Layer 1/2/3`) and sub-grouped by page within Layer 3. ✅ (`test_hallucination_check_writes_report_file`)
4. Each finding line includes the `[type / verdict]` tag and the claim verbatim. ✅
5. When `evidence` is non-empty, an `- Evidence:` sub-line is rendered; when empty, it is omitted. ✅ (`test_hallucination_report_renders_evidence_when_present`, `test_hallucination_report_omits_evidence_line_when_empty`)

#### `hallucination_check()` ✅
1. Calls `run_agent` with `system_prompt=HALLUCINATION_SYSTEM`, `allowed_tools=HALLUCINATION_TOOLS`. ✅ (`test_hallucination_check_uses_correct_system_and_tools`)
2. Passes `max_iterations=settings.max_tool_iterations_hallucination` to `run_agent`. ✅ (`test_hallucination_check_uses_hallucination_iteration_cap`)
3. Initialises `wiki._hallucination_findings = []` before the agent run so `report_finding` always finds the accumulator. ✅ (implicit — tests would crash on attribute error otherwise)
4. Writes `<workspace>/hallucination-report.md` containing `# Hallucination Report` + `## Statistics` after the run. ✅ (`test_hallucination_check_writes_report_file`)
5. Report stats reflect counts per verdict (e.g. `hallucination: 1`, `supported: 1` for a 2-finding fixture). ✅
6. Returns `HallucinationCheckResult` with `summary`, populated `findings: list[HallucinationFinding]`, `report_path="hallucination-report.md"`, and the agent `trace`. ✅ (`test_hallucination_check_returns_result_schema`)
7. Handles zero-findings gracefully: still writes the report file with a placeholder body and returns an empty `findings` list. ✅ (`test_hallucination_check_handles_no_findings`)
8. Does **not** modify any `wiki/<page>.md` or `raw/<page>.md` — pre-existing files are byte-for-byte unchanged after a sweep. ✅ (`test_hallucination_check_does_not_modify_wiki_or_raw`)

---

### 3.8 `app/main.py` — FastAPI routes

All tests in a new `tests/test_main.py` using `starlette.testclient.TestClient(app)`. Monkeypatch each `app.operations.*` callable so we never call the real LLM. Point `app.config.get_settings().workspace_dir` at `tmp_path` via `monkeypatch.setattr(app.config, "_settings", Settings(workspace_dir=tmp_path/"ws"))`.

#### `GET /` ✅
1. Returns 200 and HTML body containing the page shell. ✅

#### `POST /api/ingest` ✅
1. 200 with `IngestResult` shape on a valid body. ✅
2. 422 when `source_name` or `content` is missing. ✅
3. 400 with `detail` when `ingest` raises `ValueError`. ✅

#### `POST /api/ingest/file` and `POST /api/ingest/pdf` ✅
Both paths are bound to the same handler.
1. `.pdf` upload routes to `ingest_pdf` (asserted on both URLs via parametrize). ✅
2. `.md` and `.markdown` uploads route to `ingest`, decoded as UTF-8 (parametrized over both URLs × both extensions). ✅
3. Non-UTF-8 `.md` payload → 400 with detail mentioning UTF-8. ✅
4. Unknown extension → 400 with detail mentioning `.pdf`/`.md`. ✅
5. Empty/no extension filename → 400. ✅
6. `ValueError` from the underlying orchestrator → 400 with the message. ✅
7. Both URLs symmetric — same input produces same output. ✅

#### `POST /api/query` ✅
1. 200 with `QueryResult` shape. ✅
2. 422 when `question` is missing. ✅

#### `POST /api/chat` ✅
1. 200 with `ChatResponse` shape on valid history. ✅
2. 400 when orchestrator raises `ValueError`. ✅
3. 422 when any message lacks `role`/`content`. ✅

#### `POST /api/lint` ✅
1. 200 with `LintResult` shape. ✅

#### `POST /api/hallucination-check` ✅
1. 200 with `HallucinationCheckResult` shape on success (orchestrator monkeypatched). ✅ (`test_post_hallucination_check_returns_result_shape`)
2. Empty body is accepted (no request schema). ✅ (`test_post_hallucination_check_accepts_empty_body`)

#### `GET /api/hallucination-report` ✅
1. 200 with `IndexView` shape (`content_md` + `content_html`) when `hallucination-report.md` exists. ✅ (`test_get_hallucination_report_returns_index_view_when_file_exists`)
2. 404 with detail mentioning "no hallucination report yet" when the file does not exist. ✅ (`test_get_hallucination_report_returns_404_when_file_missing`)

#### `GET /api/pages` ✅
1. Returns `[]` for an empty workspace. ✅
2. Returns sorted slugs after seeding the wiki dir. ✅

#### `GET /api/page/{name}` ✅
1. 200 with `{name, content_md, content_html}` for an existing page; `content_html` contains `<h1>`. ✅
2. 404 when the page does not exist. ✅
3. 404 when the slug is invalid (`ValueError` → 404). ✅

#### `GET /api/index` ✅
1. Returns `IndexView` with both `content_md` and `content_html`. ✅

#### `GET /api/log` ✅
1. Returns `LogView` with `content_md` only (no `content_html`). ✅

#### `GET /api/schema` ✅
1. Returns the current `SCHEMA.md` content as `content_md`. ✅

#### `PUT /api/schema` ✅
1. Writes the new content and returns it back (also asserts persistence to disk). ✅
2. 422 when `content_md` is missing. ✅

#### `_render_md(text)` ✅
1. Fenced code block renders to `<pre><code>` markup. ✅
2. Pipe table renders to `<table>` / `<thead>`. ✅
3. Headers get TOC-style `id` attributes. ✅

---

### 3.9 `app/ingest/pdf/base.py`

#### `ExtractedPdf` dataclass ✅
1. Fields `text`, `page_count`, `metadata` constructible. ✅
2. Default `metadata` is a fresh dict per instance (not a shared mutable default). ✅

#### `PdfExtractor` ABC ✅
1. Cannot be instantiated directly. ✅
2. Subclass without `extract` cannot be instantiated. ✅
3. Subclass without `name` cannot be instantiated. ✅

#### `PdfExtractionError` ✅
1. Subclass of `Exception`. ✅
2. Raised explicitly by `PypdfExtractor`. ✅

---

### 3.10 `app/ingest/pdf/pypdf_backend.py`

#### `PypdfExtractor.name` ✅
1. Equal to `"pypdf"`. ✅ (`test_extractor_name_is_stable`)

#### `PypdfExtractor.extract(data, *, filename=None)` ✅
1. Returns `ExtractedPdf` with combined text and correct `page_count`. ✅
2. Includes `## Page N` markers between pages. ✅
3. Strips leading `/` from metadata keys (`/Title` → `Title`). ✅
4. Empty bytes → `PdfExtractionError("PDF data is empty")`. ✅
5. Corrupt bytes → `PdfExtractionError`. ✅
6. Password-protected PDF → `PdfExtractionError("PDF is password-protected")`. ✅ (fixture generated at test time via `PdfWriter.encrypt`).
7. All-blank pages → `PdfExtractionError` mentioning `scanned/image-only`. ✅ (fixture generated at test time).
8. Per-page failure does not abort extraction; placeholder `[page N: extraction failed: ...]` appears in the joined text alongside other pages. ✅ (monkeypatched `PdfReader` returns a mixed list of `_FakePage`s).
9. `filename` argument is accepted (kwarg-only) — passing it does not change output. ✅

---

### 3.11 `app/ingest/pdf/__init__.py`

#### `get_pdf_extractor(backend="pypdf")` ✅
1. Default backend returns `PypdfExtractor`. ✅
2. Unknown backend raises `ValueError`. ✅
3. Returned object is an instance of `PdfExtractor` (interface check). ✅

---

## 4. Cross-cutting tests ✅

All in `tests/test_cross_cutting.py`. Reuses `_FakeClient`/`_FakeMessage`/`_FakeToolCall` from `tests/test_llm.py` for end-to-end drives.

### 4.1 Path traversal — security ✅
1. `Wiki.read_page(...)` rejects `..`, `../escape`, `Bad Slug`, `etc/passwd`, empty string. ✅
2. `dispatch(wiki, "read_page", ...)` with a bad slug returns `ERROR ...`. ✅
3. `GET /api/page/Bad` → 404 (handler maps `ValueError` to 404). ✅
4. `Wiki.write_raw` also rejects bad slugs — boundary is symmetric across read and write. ✅

### 4.2 Read-only contract ✅
1. `schemas_for(READ_ONLY_TOOLS)` contains no `write_page` / `write_index` / `append_log`. ✅
2. End-to-end `operations.chat(...)` drives the real `run_loop`; the actual OpenAI request never names a mutating tool in its `tools` list — even when the user asks for one. ✅
3. End-to-end `operations.query(...)` — same contract pinned independently. ✅

### 4.3 Trace contract ✅
1. Every `TraceStep` has `tool: str`, `args: dict`, `result_preview: str`. ✅
2. `result_preview` is either ≤ 400 chars or ends with `" more chars)"` suffix — pinned across an entire end-to-end trace. ✅
3. Reading a 10 000-char page leaves the full body absent from every trace preview (no content leakage). ✅
4. Invalid JSON args still surface as a dict (`{"_raw": "<raw>"}`) so consumers can serialise without special-casing. ✅

---

## 5. Gap matrix

| Module | Status | Notes |
|---|---|---|
| `app/wiki.py` | ✅ | Full coverage — schema r/w, `append_log` edges, UTF-8, slug validation on every read path, `_safe_path` injection, `__init__` resolution. |
| `app/config.py` | ✅ | `test_config.py` — defaults (incl. all five per-op caps), env-var binding (incl. `MAX_TOOL_ITERATIONS_*` per-op), `workspace_path` resolution, singleton. |
| `app/tools.py` | ✅ | Full coverage — every handler (incl. `_report_finding` enum/missing-field validation and accumulation), every dispatch error branch, every tool set contract, `HALLUCINATION_TOOLS` exclusions. |
| `app/llm.py` | ✅ | `test_llm.py` — `_preview`, `AgentResult`, `_client`, `run_agent`, `run_loop` (12+ behaviours) via scripted `_FakeClient`, plus `max_iterations` kwarg forwarded by `run_agent` and honoured exactly by `run_loop`. |
| `app/prompts.py` | ✅ | `test_prompts.py` — required-tool mentions per prompt, READ-ONLY declarations, cross-reference syntax, plus `HALLUCINATION_SYSTEM` workflow tools / claim-type / verdict / layer-order / write-tool-forbidden contract. |
| `app/schemas.py` | ✅ | `test_schemas.py` — required-field contract, default-factory isolation, md-only views, `HallucinationFinding` literal + range validation, `HallucinationCheckResult` required fields. |
| `app/operations.py` | ✅ | `test_operations.py` — every orchestrator (`ingest`, `query`, `chat`, `lint`, `hallucination_check`) covered with `run_agent`/`run_loop` spies; per-op iteration cap pass-through pinned for every operation. `_format_hallucination_report` exercised across empty/non-empty findings and the evidence-rendering branch. |
| `app/main.py` | ✅ | `test_main.py` — every route via `TestClient`, error mapping, file-upload routing, `_render_md` extensions, plus `POST /api/hallucination-check` (shape + empty-body) and `GET /api/hallucination-report` (200 + 404). |
| `app/ingest/pdf/base.py` | ✅ | Full coverage incl. missing-`name` ABC + `ExtractedPdf` default-dict isolation. |
| `app/ingest/pdf/pypdf_backend.py` | ✅ | Encrypted, blank, and per-page-failure cases covered; fixtures are generated at runtime (no binary blobs in git). |
| `app/ingest/pdf/__init__.py` | ✅ | Default + unknown backend + `isinstance(result, PdfExtractor)`. |

---

## 6. Implementation order (suggested)

When implementing the missing tests, work in this order — each step builds the helpers the next step needs:

1. **`test_config.py`** — small, no helpers; warms up monkeypatching `_settings`.
2. **`test_schemas.py`** — trivial; pins request/response shapes used by the API tests.
3. **`test_llm.py`** — defines `_FakeClient`. Largest single new file but unlocks everything downstream.
4. **`test_operations.py`** — reuses `_FakeClient` (or simpler `run_agent` monkeypatch) to test orchestrators.
5. **`test_main.py`** — depends on patched orchestrators; routes are the highest-level surface.
6. **`test_prompts.py`** — trivial sanity, but only meaningful once orchestrators are tested (because we now know what tools each prompt must mention).
7. **`tools.py` / `wiki.py` extensions** — fill in 🟡 gaps in the existing files.
8. **PDF fixtures (`encrypted.pdf`, `blank.pdf`)** — generate once, commit, then add the missing cases to `test_pdf_extractor.py`.
