"""Abstract base class for PDF text extractors."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExtractedPdf:
    text: str
    page_count: int
    metadata: dict[str, str] = field(default_factory=dict)


class PdfExtractionError(Exception):
    """Raised when a PDF cannot be parsed: corrupt, encrypted, empty, image-only."""


class PdfExtractor(ABC):
    """Boundary between PDF bytes and the wiki ingest pipeline.

    Implementations wrap a specific PDF library (pypdf, pdfplumber, pymupdf, ...).
    The contract: take bytes, return ExtractedPdf, or raise PdfExtractionError.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable identifier used by the factory, e.g. 'pypdf'."""

    @abstractmethod
    def extract(self, data: bytes, *, filename: str | None = None) -> ExtractedPdf:
        """Extract text and metadata from PDF bytes."""
