from io import BytesIO
from pathlib import Path

import pytest

from app.ingest.pdf import (
    ExtractedPdf,
    PdfExtractionError,
    PdfExtractor,
    PypdfExtractor,
    get_pdf_extractor,
)
from app.ingest.pdf import pypdf_backend

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


@pytest.fixture
def sample_bytes() -> bytes:
    return FIXTURE.read_bytes()


@pytest.fixture
def encrypted_pdf_bytes() -> bytes:
    """Generate a password-protected single-page PDF on the fly so we don't
    commit a binary fixture."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password="secret")
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture
def blank_pdf_bytes() -> bytes:
    """Two pages, both blank — extractor should reject as no-extractable-text."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_pdf_extractor_is_abstract():
    with pytest.raises(TypeError):
        PdfExtractor()  # type: ignore[abstract]


def test_subclass_without_extract_is_abstract():
    class Half(PdfExtractor):
        @property
        def name(self) -> str:
            return "half"

    with pytest.raises(TypeError):
        Half()  # type: ignore[abstract]


def test_pypdf_extracts_text_from_fixture(sample_bytes: bytes):
    result = PypdfExtractor().extract(sample_bytes)
    assert isinstance(result, ExtractedPdf)
    assert "Hello from sample PDF" in result.text
    assert result.page_count == 2


def test_pypdf_includes_page_markers(sample_bytes: bytes):
    result = PypdfExtractor().extract(sample_bytes)
    assert "## Page 1" in result.text
    assert "## Page 2" in result.text


def test_pypdf_extracts_metadata(sample_bytes: bytes):
    result = PypdfExtractor().extract(sample_bytes)
    # pypdf surfaces keys with leading "/"; our extractor strips it.
    assert result.metadata.get("Title") == "Sample Wiki PDF"
    assert result.metadata.get("Author") == "Test"


def test_pypdf_raises_on_empty_bytes():
    with pytest.raises(PdfExtractionError):
        PypdfExtractor().extract(b"")


def test_pypdf_raises_on_corrupt_bytes():
    with pytest.raises(PdfExtractionError):
        PypdfExtractor().extract(b"not a pdf at all")


def test_get_pdf_extractor_default_is_pypdf():
    extractor = get_pdf_extractor()
    assert isinstance(extractor, PypdfExtractor)
    assert extractor.name == "pypdf"


def test_get_pdf_extractor_unknown_backend_raises():
    with pytest.raises(ValueError):
        get_pdf_extractor("nope")


def test_extractor_name_is_stable():
    assert PypdfExtractor().name == "pypdf"


# ============================================================== base extras

def test_subclass_without_name_is_abstract():
    class _NoName(PdfExtractor):
        def extract(self, data: bytes, *, filename: str | None = None) -> ExtractedPdf:
            return ExtractedPdf(text="", page_count=0)

    with pytest.raises(TypeError):
        _NoName()  # type: ignore[abstract]


def test_extracted_pdf_default_metadata_is_not_shared_between_instances():
    a = ExtractedPdf(text="a", page_count=1)
    b = ExtractedPdf(text="b", page_count=1)
    a.metadata["k"] = "v"

    assert b.metadata == {}


def test_pdf_extraction_error_is_an_exception():
    assert issubclass(PdfExtractionError, Exception)


def test_get_pdf_extractor_returns_pdf_extractor_subclass():
    extractor = get_pdf_extractor()

    assert isinstance(extractor, PdfExtractor)


# =================================================== pypdf edge-case PDFs

def test_pypdf_raises_on_password_protected_pdf(encrypted_pdf_bytes: bytes):
    with pytest.raises(PdfExtractionError, match="password-protected"):
        PypdfExtractor().extract(encrypted_pdf_bytes)


def test_pypdf_raises_on_blank_pages_with_image_only_hint(blank_pdf_bytes: bytes):
    with pytest.raises(PdfExtractionError, match="scanned/image-only"):
        PypdfExtractor().extract(blank_pdf_bytes)


def test_pypdf_continues_extracting_when_one_page_fails(monkeypatch: pytest.MonkeyPatch):
    """Per-page failure must not abort the whole extraction — the bad page is
    replaced with a `[page N: extraction failed: ...]` placeholder and the
    surrounding pages still extract."""

    class _FakePage:
        def __init__(self, text: str | None = None, exc: Exception | None = None):
            self._text = text
            self._exc = exc

        def extract_text(self) -> str:
            if self._exc is not None:
                raise self._exc
            return self._text or ""

    class _FakeReader:
        is_encrypted = False
        metadata = None

        def __init__(self, *_args, **_kwargs):
            self.pages = [
                _FakePage(text="Page one body"),
                _FakePage(exc=RuntimeError("boom on page 2")),
                _FakePage(text="Page three body"),
            ]

    monkeypatch.setattr(pypdf_backend, "PdfReader", _FakeReader)

    result = PypdfExtractor().extract(b"%PDF-fake")

    assert "Page one body" in result.text
    assert "Page three body" in result.text
    # Failed page surfaces as a placeholder, not a silent gap.
    assert "[page 2: extraction failed:" in result.text
    assert "boom on page 2" in result.text
    assert result.page_count == 3


def test_pypdf_accepts_filename_kwarg_without_changing_output(sample_bytes: bytes):
    a = PypdfExtractor().extract(sample_bytes)
    b = PypdfExtractor().extract(sample_bytes, filename="anything.pdf")

    assert a.text == b.text
    assert a.metadata == b.metadata
    assert a.page_count == b.page_count
