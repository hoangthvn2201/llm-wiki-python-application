"""pypdf-based PdfExtractor."""
from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingest.pdf.base import ExtractedPdf, PdfExtractionError, PdfExtractor


class PypdfExtractor(PdfExtractor):
    @property
    def name(self) -> str:
        return "pypdf"

    def extract(self, data: bytes, *, filename: str | None = None) -> ExtractedPdf:
        if not data:
            raise PdfExtractionError("PDF data is empty")

        try:
            reader = PdfReader(BytesIO(data))
        except PdfReadError as e:
            raise PdfExtractionError(f"Failed to parse PDF: {e}") from e
        except Exception as e:
            raise PdfExtractionError(f"Failed to read PDF: {e}") from e

        if reader.is_encrypted:
            raise PdfExtractionError("PDF is password-protected")

        page_texts: list[str] = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                text = f"[page {i}: extraction failed: {e}]"
            page_texts.append(text)

        joined = "\n\n".join(
            f"## Page {i}\n\n{t.strip()}"
            for i, t in enumerate(page_texts, start=1)
            if t.strip()
        )
        if not joined.strip():
            raise PdfExtractionError(
                "PDF contains no extractable text (scanned/image-only?)"
            )

        metadata: dict[str, str] = {}
        try:
            meta = reader.metadata
            if meta:
                for k, v in meta.items():
                    if isinstance(v, str):
                        metadata[str(k).lstrip("/")] = v
        except Exception:
            pass

        return ExtractedPdf(text=joined, page_count=len(reader.pages), metadata=metadata)
