"""Format-specific source ingestion (bytes → markdown/text).

Per-format subpackages own their own ABC + concrete backends so we can add
docx/, html/, etc. later without restructuring.
"""
from app.ingest.pdf import (
    ExtractedPdf,
    PdfExtractionError,
    PdfExtractor,
    PypdfExtractor,
    get_pdf_extractor,
)

__all__ = [
    "ExtractedPdf",
    "PdfExtractionError",
    "PdfExtractor",
    "PypdfExtractor",
    "get_pdf_extractor",
]
