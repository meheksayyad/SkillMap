"""Turn an uploaded resume file (PDF, DOCX or TXT) into plain text. No Django imports."""

import io
import logging
import re
from pathlib import Path

# pypdf logs noisy warnings for malformed files; we report those as clean errors instead.
logging.getLogger("pypdf").setLevel(logging.ERROR)

MAX_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 10
MAX_CHARS = 30_000
MIN_CHARS = 20


class ExtractError(Exception):
    """The file can't be read. The message is safe to show to the user."""


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractError("This PDF is password-protected. Remove the password and retry.")
        pages = reader.pages[:MAX_PDF_PAGES]
        return "\n".join((page.extract_text() or "") for page in pages)
    except ExtractError:
        raise
    except Exception as exc:  # pypdf raises many different error types
        raise ExtractError("Could not read this PDF. Try exporting it again or upload a DOCX.") from exc


def _from_docx(data: bytes) -> str:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractError("Could not read this DOCX file.") from exc
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def extract_text(filename: str, data: bytes) -> str:
    """Return cleaned text from `data`, choosing the reader by file extension."""
    if len(data) > MAX_BYTES:
        raise ExtractError(f"File is too large (limit {MAX_BYTES // (1024 * 1024)} MB).")
    ext = Path(filename or "").suffix.lower()
    if ext == ".txt":
        raw = data.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        raw = _from_pdf(data)
    elif ext == ".docx":
        raw = _from_docx(data)
    else:
        raise ExtractError("Please upload a .pdf, .docx or .txt file.")
    text = _clean(raw)
    if len(text) < MIN_CHARS:
        raise ExtractError(
            "No readable text found. If this is a scanned image, export a text-based PDF instead."
        )
    return text[:MAX_CHARS]
