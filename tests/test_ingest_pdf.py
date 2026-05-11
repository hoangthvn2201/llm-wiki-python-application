"""Tests for ingest_pdf orchestrator — fake extractor, monkeypatched ingest, no LLM."""
from __future__ import annotations

import pytest

from app import operations
from app.ingest.pdf import ExtractedPdf, PdfExtractionError, PdfExtractor
from app.schemas import IngestResult


class _FakeExtractor(PdfExtractor):
    def __init__(self, result: ExtractedPdf | None = None, exc: Exception | None = None):
        self._result = result
        self._exc = exc

    @property
    def name(self) -> str:
        return "fake"

    def extract(self, data: bytes, *, filename: str | None = None) -> ExtractedPdf:
        if self._exc is not None:
            raise self._exc
        assert self._result is not None
        return self._result


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch):
    """Capture args passed to operations.ingest without running the LLM."""
    captured: dict = {}

    def fake_ingest(source_name: str, content: str) -> IngestResult:
        captured["source_name"] = source_name
        captured["content"] = content
        return IngestResult(summary="ok", trace=[])

    monkeypatch.setattr(operations, "ingest", fake_ingest)
    return captured


def _install_extractor(monkeypatch: pytest.MonkeyPatch, extractor: PdfExtractor) -> None:
    monkeypatch.setattr(operations, "get_pdf_extractor", lambda backend="pypdf": extractor)


def test_ingest_pdf_calls_extractor_then_ingest(monkeypatch, captured):
    extracted = ExtractedPdf(text="## Page 1\n\nHello", page_count=1, metadata={})
    _install_extractor(monkeypatch, _FakeExtractor(result=extracted))

    result = operations.ingest_pdf("my-source", b"%PDF-...")

    assert result.summary == "ok"
    assert captured["source_name"] == "my-source"
    assert "Hello" in captured["content"]


def test_ingest_pdf_includes_metadata_header_when_present(monkeypatch, captured):
    extracted = ExtractedPdf(
        text="## Page 1\n\nBody",
        page_count=1,
        metadata={"Title": "My Doc", "Author": "Alice"},
    )
    _install_extractor(monkeypatch, _FakeExtractor(result=extracted))

    operations.ingest_pdf("my-source", b"%PDF-...")

    content = captured["content"]
    assert "## Document metadata" in content
    assert "Title" in content and "My Doc" in content
    assert "Author" in content and "Alice" in content


def test_ingest_pdf_omits_metadata_section_when_empty(monkeypatch, captured):
    extracted = ExtractedPdf(text="## Page 1\n\nBody", page_count=1, metadata={})
    _install_extractor(monkeypatch, _FakeExtractor(result=extracted))

    operations.ingest_pdf("my-source", b"%PDF-...")

    assert "## Document metadata" not in captured["content"]


def test_ingest_pdf_wraps_extraction_error_as_value_error(monkeypatch, captured):
    _install_extractor(
        monkeypatch,
        _FakeExtractor(exc=PdfExtractionError("PDF is password-protected")),
    )

    with pytest.raises(ValueError, match="password-protected"):
        operations.ingest_pdf("my-source", b"%PDF-...")

    # ingest() must NOT have been called when extraction fails.
    assert "source_name" not in captured
