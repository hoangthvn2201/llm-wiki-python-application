"""PDF text extraction: ABC, concrete backends, factory."""
from app.ingest.pdf.base import ExtractedPdf, PdfExtractionError, PdfExtractor
from app.ingest.pdf.pypdf_backend import PypdfExtractor


def get_pdf_extractor(backend: str = "pypdf") -> PdfExtractor:
    """Return a PDF extractor for the given backend.

    Add new backends here as they are implemented. Caller passes the backend
    name; unknown names raise ValueError.
    """
    if backend == "pypdf":
        return PypdfExtractor()
    raise ValueError(f"unknown PDF backend: {backend!r}")


__all__ = [
    "ExtractedPdf",
    "PdfExtractionError",
    "PdfExtractor",
    "PypdfExtractor",
    "get_pdf_extractor",
]
