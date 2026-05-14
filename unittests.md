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
1. Accepts valid kebab-case (`a`, `ab-c`, `1page`, `mitochondria`). ✅ (covered by `test_write_and_read_page` via `write_page`)
2. Rejects invalid forms: spaces, slashes, uppercase, empty, leading hyphen, `..`. ✅ (`test_invalid_slug_rejected`)
3. Strips surrounding whitespace before matching. ❌
4. Returns the *stripped* name so callers see canonical form. ❌

#### `Wiki.__init__(root: Path) -> None` 🟡
1. Expands `~` in the supplied root. ❌
2. Resolves relative paths to absolute. ❌
3. Does not touch the filesystem (no `ensure()` side effect). ❌

#### `Wiki.ensure() -> None` ✅
1. Creates `root/`, `raw/`, `wiki/`. ✅ (`test_ensure_creates_layout`)
2. Creates `index.md`, `log.md`, `SCHEMA.md` when missing. ✅
3. Idempotent — preserves existing content on second call. ✅ (`test_ensure_is_idempotent_and_preserves_content`)
4. Default `index.md` contains the four section headers (Entities, Concepts, Sources, Reports). ❌
5. Default `SCHEMA.md` equals the `DEFAULT_SCHEMA` constant. ❌
6. Default `log.md` is `"# Log\n\n"`. ❌

#### `Wiki._safe_path(*parts: str) -> Path` 🟡
1. Returns a path under `root` for normal parts. ❌ (positive case)
2. Raises `ValueError` for `..` traversal. ✅ (`test_path_traversal_blocked`)
3. Raises `ValueError` when an absolute path is passed (e.g. `_safe_path("/etc/passwd")`). ❌

#### `Wiki.list_pages() -> list[str]` 🟡
1. Returns sorted slug stems of `wiki/*.md`. ✅
2. Returns `[]` when no pages exist. ❌
3. Ignores non-`.md` files and subdirectories under `wiki/`. ❌

#### `Wiki.page_exists(name: str) -> bool` ✅
1. `True` after `write_page`. ✅
2. `False` for missing page. ✅
3. Raises `ValueError` for invalid slug. ❌

#### `Wiki.read_page(name: str) -> str` ✅
1. Returns UTF-8 content of an existing page. ✅
2. Raises `FileNotFoundError` for missing page. ✅ (`test_read_missing_page_raises`)
3. Raises `ValueError` for invalid slug (e.g. `".."`). ✅ (`test_path_traversal_blocked`)
4. Round-trips non-ASCII (emoji, accents). ❌

#### `Wiki.write_page(name: str, content: str) -> None` ✅
1. Creates a new page. ✅
2. Overwrites an existing page (no append). ❌
3. Rejects invalid slug with `ValueError`. ✅
4. Persists content as UTF-8 (round-trips emoji / accents). ❌

#### `Wiki.delete_page(name: str) -> None` ✅
1. Removes an existing page. ✅ (`test_delete_page`)
2. No-op when page is missing (no exception). ✅
3. Rejects invalid slug. ❌

#### `Wiki.read_index() -> str` / `Wiki.write_index(content: str) -> None` 🟡
1. `write_index` then `read_index` round-trips the supplied content exactly. ❌
2. `read_index` reads what `ensure()` seeded. (indirectly ✅ via `test_ensure_is_idempotent_and_preserves_content`)

#### `Wiki.read_log() -> str` / `Wiki.append_log(entry: str) -> None` 🟡
1. Appended entry shows up in `read_log()`. ✅ (`test_append_log_adds_dated_entry`)
2. Inserts a blank line separator before the new entry when the file did not already end with `\n\n`. ❌
3. Strips trailing whitespace from `entry` and ensures the file ends with exactly one trailing newline. ❌
4. Initialises log with `"# Log\n\n"` when `log.md` does not exist on disk. ❌
5. Two successive calls produce two distinct entries with the blank-line separator between them. ❌

#### `Wiki.log_entry_header(op: str, title: str) -> str` ✅
1. Format is `## [YYYY-MM-DD] <op> | <title>` using today's ISO date. ✅ (indirectly) — add a direct test.

#### `Wiki.read_schema() -> str` / `Wiki.write_schema(content: str) -> None` ❌
1. `write_schema` then `read_schema` round-trips. ❌
2. `ensure()` does not overwrite a custom schema (already covered by idempotent-ensure, but assert it specifically for `SCHEMA.md`). ❌

#### `Wiki.list_raw() -> list[str]` / `Wiki.read_raw(name) -> str` / `Wiki.write_raw(name, content) -> Path` 🟡
1. Round-trip (`write_raw` → `list_raw` → `read_raw`). ✅ (`test_raw_round_trip`)
2. `write_raw` returns the resolved `Path` of the written file. ❌
3. `read_raw` raises `FileNotFoundError` for a missing source. ❌
4. `read_raw` rejects invalid slug. ❌
5. `list_raw` returns sorted slugs and `[]` when empty. ❌

---

### 3.2 `app/config.py`

All tests in a new `tests/test_config.py`. Each test resets `app.config._settings = None` before instantiating `Settings()` so env-var changes are picked up.

#### `Settings` field defaults ✅
1. `openai_api_key` defaults to `"sk-missing"` when env var is unset. ✅
2. `openai_base_url` defaults to `"https://api.openai.com/v1"`. ✅
3. `model_name` defaults to `"gpt-4o-mini"`. ✅
4. `workspace_dir` defaults to `Path("./workspace")`. ✅
5. `max_tool_iterations` defaults to `25` (int). ✅

#### `Settings` env-var binding ✅
1. `OPENAI_API_KEY=abc` is read into `openai_api_key`. ✅
2. `MAX_TOOL_ITERATIONS=5` is parsed as `int` (not str). ✅
3. `WORKSPACE_DIR=/tmp/foo` is coerced to `Path("/tmp/foo")`. ✅
4. Unknown env vars are ignored (`extra="ignore"`). ✅

#### `Settings.workspace_path` ✅
1. Expands `~` in `workspace_dir`. ✅
2. Resolves relative paths to absolute (anchored to CWD at access time). ✅

#### `get_settings()` ✅
1. First call constructs a `Settings`; subsequent calls return the same instance (`is` check). ✅
2. After resetting `_settings = None`, the next call constructs a fresh instance. ✅

---

### 3.3 `app/tools.py`

#### `Tool.schema()` ✅
1. Returns `{"type": "function", "function": {"name", "description", "parameters"}}` shape. ✅ (`test_all_tool_schemas_well_formed`)
2. `parameters.type == "object"`. ✅

#### `schemas_for(allowed: list[str]) -> list[dict]` ✅
1. Returns only schemas whose name is in `allowed`. ✅ (`test_schemas_for_filters_to_allowed`)
2. `READ_ONLY_TOOLS` result excludes mutating tools (`write_page`, `write_index`, `append_log`). ✅ (partial)
3. Silently drops unknown names in `allowed` (does not raise). ❌

#### `dispatch(wiki, name, raw_args) -> str` 🟡
1. Unknown tool → string starting with `ERROR`. ✅ (`test_dispatch_unknown_tool_returns_error_string`)
2. Invalid JSON → string starting with `ERROR`. ✅ (`test_dispatch_invalid_json_returns_error`)
3. Non-object JSON args (`"42"`, `"[1, 2]"`) → `ERROR: tool arguments must be a JSON object`. ❌
4. Handler `ValueError` → `ERROR: <msg>`. ✅ (`test_write_page_invalid_slug_returns_error`)
5. Handler `FileNotFoundError` → `ERROR: <msg>` (e.g. `read_page` of a missing page). ❌
6. Unexpected exception → `ERROR: unexpected <Type>: <msg>` (simulate by monkeypatching a handler to raise `RuntimeError`). ❌
7. Empty `raw_args` (`""`) defaults to `{}`. ❌

#### Tool handlers (`_list_pages`, `_read_page`, `_write_page`, `_read_index`, `_write_index`, `_append_log`, `_read_schema`, `_list_raw`, `_read_raw`, `_finish`)

Each handler is exercised via `dispatch(wiki, name, json.dumps(args))` to also pin the JSON-parsing contract.

1. `_list_pages` empty → `"(no wiki pages yet)"`. ❌
2. `_list_pages` with pages → newline-joined slugs. ❌
3. `_read_page` returns the page content. ❌ (covered indirectly only)
4. `_write_page` returns `"created wiki/<name>.md (<n> chars)"` for new page. ✅ (`test_write_page_via_dispatch_then_list`)
5. `_write_page` returns `"updated wiki/<name>.md (<n> chars)"` when page already exists. ❌
6. `_read_index` returns current `index.md` content. ✅
7. `_write_index` writes and returns confirmation string with char count. ❌
8. `_append_log` returns `"appended <n> chars to log.md"`. ✅ (`test_append_log_via_dispatch`)
9. `_read_schema` returns current schema. ❌
10. `_list_raw` empty → `"(no raw sources)"`; with raws → newline-joined slugs. ❌
11. `_read_raw` returns raw content; missing raw → `ERROR: ...` via dispatch. ❌
12. `_finish` returns `"FINISHED: <summary>"`; missing summary → `"FINISHED: (no summary)"`. ❌

#### Tool sets ✅
1. `READ_ONLY_TOOLS` excludes all write/append tools. ✅ (partial — pin every excluded name)
2. `INGEST_TOOLS` is a superset of `READ_ONLY_TOOLS`. ✅ (`test_ingest_tools_is_superset_of_read_only`)
3. `LINT_TOOLS == list(ALL_TOOLS.keys())` (i.e. lint can do anything). ❌
4. Every name in `READ_ONLY_TOOLS`/`INGEST_TOOLS`/`LINT_TOOLS` exists in `ALL_TOOLS`. ❌

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

#### `run_agent(wiki, system_prompt, user_prompt, allowed_tools)` ✅
1. Builds messages `[{role:"system", ...}, {role:"user", ...}]` and delegates to `run_loop`. ✅
2. Returns the `AgentResult` returned by `run_loop` verbatim. ✅
3. Passes `allowed_tools` through unchanged. ✅

#### `run_loop(wiki, messages, allowed_tools)` ✅
1. **Plain final answer**: when the model emits content with no `tool_calls`, returns `AgentResult(final_text=content, trace=[])`. Messages list grows by one assistant entry. ✅
2. **`finish` short-circuit**: when the model emits a `finish` tool_call, the loop returns `AgentResult(final_text=summary, trace=[<one step>])` after one round. ✅
3. **Single tool call**: model calls `list_pages`, loop dispatches it, appends `{role:"tool", tool_call_id, content}`, then the next round's plain content becomes `final_text`. ✅
4. **Trace shape**: every trace entry has `tool` (str), `args` (dict), `result_preview` (str ≤ 400 chars plus optional suffix). ✅
5. **Trace truncation does not affect model context**: a tool result of >400 chars is sent verbatim to the model (in the `tool` message) but truncated in the returned `trace`. ✅
6. **Unknown tool name** in a tool_call still produces a trace entry whose `result_preview` starts with `ERROR`; the loop continues. ✅
7. **Max iterations**: returns the `"(agent hit MAX_TOOL_ITERATIONS...)"` fallback after `settings.max_tool_iterations` rounds. ✅
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

#### `chat(history)` ✅
1. Empty history → raises `ValueError`. ✅
2. Role other than `"user"` / `"assistant"` → raises `ValueError` mentioning the bad role. ✅
3. Calls `run_loop` with messages starting with `{role:"system", content: CHAT_SYSTEM}` followed by every history entry in order. ✅
4. Passes `allowed_tools=READ_ONLY_TOOLS` (chat is read-only). ✅
5. Returns `ChatResponse(reply=final_text, trace=trace)`. ✅
6. Multi-turn: a history with two user + one assistant message is preserved verbatim in the messages list. ✅

#### `lint()` ✅
1. Calls `run_agent` with `system_prompt=LINT_SYSTEM`, `allowed_tools=LINT_TOOLS`. ✅
2. Returns `LintResult(report=final_text, trace=trace)`. ✅

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
1. Fields `text`, `page_count`, `metadata` constructible. ✅ (used throughout)
2. Default `metadata` is a fresh dict per instance (not a shared mutable default). ❌

#### `PdfExtractor` ABC ✅
1. Cannot be instantiated directly. ✅ (`test_pdf_extractor_is_abstract`)
2. Subclass without `extract` cannot be instantiated. ✅ (`test_subclass_without_extract_is_abstract`)
3. Subclass without `name` cannot be instantiated. ❌

#### `PdfExtractionError` ✅
1. Subclass of `Exception`. ❌
2. Raised explicitly by `PypdfExtractor` (covered transitively). ✅

---

### 3.10 `app/ingest/pdf/pypdf_backend.py`

#### `PypdfExtractor.name` ✅
1. Equal to `"pypdf"`. ✅ (`test_extractor_name_is_stable`)

#### `PypdfExtractor.extract(data, *, filename=None)` 🟡
1. Returns `ExtractedPdf` with combined text and correct `page_count`. ✅
2. Includes `## Page N` markers between pages. ✅
3. Strips leading `/` from metadata keys (`/Title` → `Title`). ✅
4. Empty bytes → `PdfExtractionError("PDF data is empty")`. ✅
5. Corrupt bytes → `PdfExtractionError`. ✅
6. **Password-protected PDF** → `PdfExtractionError("PDF is password-protected")`. ❌ Requires `tests/fixtures/encrypted.pdf` (generate once with pypdf, commit).
7. **All-blank pages** → `PdfExtractionError("PDF contains no extractable text...")`. ❌ Requires `tests/fixtures/blank.pdf`.
8. **Per-page failure** does not abort extraction; the failing page is replaced by `[page N: extraction failed: ...]` and other pages still extract. ❌ (simulate by monkeypatching `PdfReader.pages` with a list whose item N raises on `extract_text()`).
9. `filename` argument is accepted (kwarg-only) and currently unused — passing it does not change output. ❌

---

### 3.11 `app/ingest/pdf/__init__.py`

#### `get_pdf_extractor(backend="pypdf")` ✅
1. Default backend returns `PypdfExtractor`. ✅
2. Unknown backend raises `ValueError`. ✅
3. Returned object is an instance of `PdfExtractor` (interface check). ❌

---

## 4. Cross-cutting tests

These ride on top of the per-function tests and pin behaviour that spans modules.

### 4.1 Path traversal — security
1. Every entry point that takes a `name` slug rejects `..`, absolute paths, and paths with separators:
   - `Wiki.read_page("..")`, `Wiki.read_page("/etc/passwd")`, `Wiki.read_raw(...)` (covered for `..`).
   - `dispatch(wiki, "read_page", json.dumps({"name": ".."}))` → `ERROR`.
   - `GET /api/page/..` → 404 (FastAPI path validation may make this a 404 by URL parsing; assert behaviour).

### 4.2 Read-only contract
1. `schemas_for(READ_ONLY_TOOLS)` returns no tool whose name contains `"write"` or `"append"`.
2. With a `_FakeClient` that tries to emit a `write_page` tool_call during a `chat` session, the loop dispatches it (because dispatch doesn't filter — the model just shouldn't see it). Assert that the OpenAI request did NOT include `write_page` in its `tools` list. This is the actual enforcement boundary.

### 4.3 Trace contract
1. Every `TraceStep` in any `run_loop` output has:
   - `tool` is a `str`.
   - `args` is a `dict`.
   - `result_preview` is a `str` and either `len(result_preview) <= 400` or it ends with the `"... (N more chars)"` suffix.
2. Trace never contains the full text of a file longer than 400 chars (write a 10kB page, read it via a tool call, assert truncation).

### 4.4 End-to-end smoke (single test, optional)
1. With a scripted `_FakeClient` that emits one `read_index` call then `finish`, drive `operations.query("what's here?")` end-to-end and assert the `QueryResult.answer` and `trace` shapes.

---

## 5. Gap matrix

| Module | Status | Notes |
|---|---|---|
| `app/wiki.py` | 🟡 | Most behaviour covered; missing `read_schema`/`write_schema`, edge cases for `append_log`, UTF-8 round-trip, slug validation on read paths. |
| `app/config.py` | ✅ | `test_config.py` — defaults, env-var binding, `workspace_path` resolution, singleton. |
| `app/tools.py` | 🟡 | Dispatch + sets covered; need error branches, "updated" vs "created" path, every handler's happy path, `_finish`/`_list_raw`/`_read_schema` direct tests. |
| `app/llm.py` | ✅ | `test_llm.py` — `_preview`, `AgentResult`, `_client`, `run_agent`, `run_loop` (12+ behaviours) via scripted `_FakeClient`. |
| `app/prompts.py` | ✅ | `test_prompts.py` — required-tool mentions per prompt, READ-ONLY declarations, cross-reference syntax. |
| `app/schemas.py` | ✅ | `test_schemas.py` — required-field contract, default-factory isolation, md-only views. |
| `app/operations.py` | ✅ | `test_operations.py` + extended `test_ingest_pdf.py` — every orchestrator covered with `run_agent`/`run_loop` spies. |
| `app/main.py` | ✅ | `test_main.py` — every route via `TestClient`, error mapping, file-upload routing, `_render_md` extensions. |
| `app/ingest/pdf/base.py` | ✅ | Extend ABC tests for missing `name` property; pin default-dict-not-shared. |
| `app/ingest/pdf/pypdf_backend.py` | 🟡 | Add encrypted-PDF and blank-PDF fixtures; add per-page-failure simulation test. |
| `app/ingest/pdf/__init__.py` | ✅ | Add an `isinstance(result, PdfExtractor)` assertion. |

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
