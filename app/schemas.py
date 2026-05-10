"""Pydantic request/response models for the FastAPI surface."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    result_preview: str


class IngestRequest(BaseModel):
    source_name: str = Field(..., description="kebab-case slug for the source file")
    content: str = Field(..., description="raw markdown / text content of the source")


class IngestResult(BaseModel):
    summary: str
    trace: list[TraceStep]


class QueryRequest(BaseModel):
    question: str


class QueryResult(BaseModel):
    answer: str
    trace: list[TraceStep]


class LintResult(BaseModel):
    report: str
    trace: list[TraceStep]


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    trace: list[TraceStep]


class PageView(BaseModel):
    name: str
    content_md: str
    content_html: str


class IndexView(BaseModel):
    content_md: str
    content_html: str


class LogView(BaseModel):
    content_md: str


class SchemaView(BaseModel):
    content_md: str


class SchemaUpdate(BaseModel):
    content_md: str
