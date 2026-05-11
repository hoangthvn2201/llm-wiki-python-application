"""FastAPI app: serves a single HTML page and a small JSON API."""
from __future__ import annotations

from pathlib import Path

import markdown as md
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.config import get_settings
from app.operations import chat, ingest, ingest_pdf, lint, query
from app.schemas import (
    ChatRequest,
    ChatResponse,
    IndexView,
    IngestRequest,
    IngestResult,
    LintResult,
    LogView,
    PageView,
    QueryRequest,
    QueryResult,
    SchemaUpdate,
    SchemaView,
)
from app.wiki import Wiki

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="LLM Wiki")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _wiki() -> Wiki:
    w = Wiki(get_settings().workspace_path)
    w.ensure()
    return w


def _render_md(text: str) -> str:
    return md.markdown(text, extensions=["fenced_code", "tables", "toc"])


@app.on_event("startup")
def _startup() -> None:
    _wiki()  # ensure workspace exists on first launch


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ----------------------------------------------------------------- API

@app.post("/api/ingest", response_model=IngestResult)
def api_ingest(req: IngestRequest) -> IngestResult:
    try:
        return ingest(req.source_name, req.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/ingest/pdf", response_model=IngestResult)
async def api_ingest_pdf(
    source_name: str = Form(...),
    file: UploadFile = File(...),
) -> IngestResult:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="file must be a .pdf")
    data = await file.read()
    try:
        return ingest_pdf(source_name, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/query", response_model=QueryResult)
def api_query(req: QueryRequest) -> QueryResult:
    return query(req.question)


@app.post("/api/chat", response_model=ChatResponse)
def api_chat(req: ChatRequest) -> ChatResponse:
    try:
        return chat(req.messages)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/lint", response_model=LintResult)
def api_lint() -> LintResult:
    return lint()


@app.get("/api/pages", response_model=list[str])
def api_pages() -> list[str]:
    return _wiki().list_pages()


@app.get("/api/page/{name}", response_model=PageView)
def api_page(name: str) -> PageView:
    wiki = _wiki()
    try:
        content = wiki.read_page(name)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PageView(name=name, content_md=content, content_html=_render_md(content))


@app.get("/api/index", response_model=IndexView)
def api_index() -> IndexView:
    content = _wiki().read_index()
    return IndexView(content_md=content, content_html=_render_md(content))


@app.get("/api/log", response_model=LogView)
def api_log() -> LogView:
    return LogView(content_md=_wiki().read_log())


@app.get("/api/schema", response_model=SchemaView)
def api_schema_get() -> SchemaView:
    return SchemaView(content_md=_wiki().read_schema())


@app.put("/api/schema", response_model=SchemaView)
def api_schema_put(req: SchemaUpdate) -> SchemaView:
    wiki = _wiki()
    wiki.write_schema(req.content_md)
    return SchemaView(content_md=wiki.read_schema())
