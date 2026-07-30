"""
Resume parsing service.

WHY validate size/type BEFORE parsing:
Accepting arbitrary uploaded files and running a parser on them is a
classic attack surface — malformed PDFs can cause parser libraries to
hang or consume excessive memory (a cheap DoS vector). We enforce:
1. A hard file-size ceiling, checked on the raw bytes before parsing.
2. An allow-list of extensions/MIME types, not a deny-list.
3. A wrapped try/except around the parser call so a malformed file
   raises a clean, typed error instead of crashing the worker.
"""

import io

import pypdf
from docx import Document

from app.core.exceptions import UnsupportedFileTypeError, ValidationFailedError
from app.logging_config import get_logger

logger = get_logger(__name__)

MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024  # 5MB — generous for a resume, tight enough to block abuse
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MIN_EXTRACTED_TEXT_LENGTH = 50  # guards against near-empty/scanned-image resumes silently passing through


def validate_resume_file(filename: str, content: bytes) -> str:
    """Validates a raw upload and returns its normalized extension, or raises."""
    if not filename or "." not in filename:
        raise UnsupportedFileTypeError("File must have a valid extension (.pdf or .docx)")

    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(f"Unsupported file type '{ext}'. Only .pdf and .docx are accepted.")

    if len(content) == 0:
        raise ValidationFailedError("Uploaded file is empty")

    if len(content) > MAX_RESUME_SIZE_BYTES:
        from app.core.exceptions import FileTooLargeError

        raise FileTooLargeError(
            f"File exceeds the {MAX_RESUME_SIZE_BYTES // (1024 * 1024)}MB size limit"
        )

    return ext


def extract_text_from_resume(filename: str, content: bytes) -> str:
    """
    Extracts plain text from a validated resume file.
    Raises ValidationFailedError if extraction yields suspiciously little
    text (e.g. a scanned image PDF with no OCR layer) — better to reject
    at upload time than to silently score a resume Claude never actually saw.
    """
    ext = validate_resume_file(filename, content)

    try:
        if ext == ".pdf":
            text = _extract_pdf_text(content)
        else:
            text = _extract_docx_text(content)
    except Exception as exc:
        logger.warning("resume_parse_failed", filename=filename, error=str(exc))
        raise ValidationFailedError(
            "Could not read this file. It may be corrupted, password-protected, or an image-only scan."
        )

    text = text.strip()
    if len(text) < MIN_EXTRACTED_TEXT_LENGTH:
        raise ValidationFailedError(
            "This resume appears to contain little to no extractable text "
            "(common with scanned/image-only PDFs). Please upload a text-based PDF or DOCX."
        )

    return text


def _extract_pdf_text(content: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("PDF is password-protected")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)
