from pathlib import Path

import pytest

from app.ingest.pdf import (
    ExtractedPdf,
    PdfExtractionError,
    PdfExtractor,
    PypdfExtractor,
    get_pdf_extractor,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.pdf"


@pytest.fixture
def sample_bytes() -> bytes:
    return FIXTURE.read_bytes()


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
