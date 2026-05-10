# LLM Wiki

A Python MVP of the [LLM Wiki](./llm-wiki.md) idea: an LLM that incrementally builds and maintains a persistent markdown wiki from raw sources, instead of re-deriving knowledge per query like classical RAG.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env       # then edit .env to set OPENAI_API_KEY
uvicorn app.main:app --reload
```

Open <http://localhost:8000/>.

## How it works

Three layers (see [llm-wiki.md](./llm-wiki.md)):

- **`workspace/raw/`** — your source documents. Immutable.
- **`workspace/wiki/`** — LLM-generated pages. Owned by the LLM.
- **`workspace/SCHEMA.md`** — conventions the LLM follows. Co-evolved with you.

Plus `workspace/index.md` (catalog) and `workspace/log.md` (chronological record).

Three operations, all driven by a tool-using agentic loop:

- **Ingest** — read a source, write/update wiki pages, refresh the index, append the log.
- **Query** — read-only synthesis from wiki pages, with citations.
- **Lint** — health-check the wiki for contradictions, orphans, missing pages.

## Provider swap

This uses an OpenAI-compatible client. Point at any compatible endpoint by changing `.env`:

```env
OPENAI_BASE_URL=http://localhost:11434/v1   # Ollama
MODEL_NAME=llama3.1
```

No code change required.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests cover the filesystem and tool-dispatcher layers; they do not call the LLM.
