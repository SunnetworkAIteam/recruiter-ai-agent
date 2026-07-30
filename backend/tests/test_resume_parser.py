import io

import pytest
from docx import Document

from app.core.exceptions import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    ValidationFailedError,
)
from app.services.resume_parser import (
    MAX_RESUME_SIZE_BYTES,
    extract_text_from_resume,
    validate_resume_file,
)


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestValidateResumeFile:
    def test_rejects_unsupported_extension(self):
        with pytest.raises(UnsupportedFileTypeError):
            validate_resume_file("resume.exe", b"some bytes")

    def test_rejects_missing_extension(self):
        with pytest.raises(UnsupportedFileTypeError):
            validate_resume_file("resume", b"some bytes")

    def test_rejects_empty_file(self):
        with pytest.raises(ValidationFailedError):
            validate_resume_file("resume.pdf", b"")

    def test_rejects_oversized_file(self):
        oversized = b"x" * (MAX_RESUME_SIZE_BYTES + 1)
        with pytest.raises(FileTooLargeError):
            validate_resume_file("resume.pdf", oversized)

    def test_accepts_valid_pdf_extension(self):
        # validate_resume_file only checks extension/size, not content —
        # content correctness is exercised by extract_text_from_resume tests.
        assert validate_resume_file("resume.pdf", b"%PDF-1.4 fake") == ".pdf"

    def test_case_insensitive_extension(self):
        assert validate_resume_file("resume.PDF", b"content") == ".pdf"


class TestExtractTextFromResume:
    def test_extracts_text_from_docx(self):
        content = _make_docx_bytes(
            [
                "Jane Doe - Senior Software Engineer",
                "5 years of experience in Python, FastAPI, and distributed systems.",
                "Previously at Acme Corp leading the payments infrastructure team.",
            ]
        )
        text = extract_text_from_resume("resume.docx", content)
        assert "Jane Doe" in text
        assert "Python" in text

    def test_rejects_docx_with_too_little_text(self):
        content = _make_docx_bytes(["Hi"])
        with pytest.raises(ValidationFailedError, match="little to no extractable text"):
            extract_text_from_resume("resume.docx", content)

    def test_rejects_corrupted_pdf(self):
        with pytest.raises(ValidationFailedError, match="corrupted"):
            extract_text_from_resume("resume.pdf", b"this is not a real pdf file at all")

    def test_rejects_unsupported_extension_before_parsing(self):
        with pytest.raises(UnsupportedFileTypeError):
            extract_text_from_resume("resume.txt", b"plain text resume content here")
