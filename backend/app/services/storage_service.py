"""
Supabase Storage wrapper.

WHY server-side signed URLs, never public bucket URLs:
Resumes and interview recordings are PII/biometric data. Buckets are
kept PRIVATE, and every read goes through a short-lived signed URL
generated server-side after an authorization check — never a public,
guessable, permanent URL. This is the difference between "a recruiter
downloads a resume" and "anyone with the URL downloads every resume."
"""

import uuid

from supabase import Client, create_client

from app.config import get_settings
from app.core.exceptions import StorageError
from app.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_client


def upload_resume(candidate_id: str, filename: str, content: bytes) -> str:
    """Uploads resume bytes and returns the storage path (not a public URL)."""
    ext = filename.rsplit(".", 1)[-1].lower()
    storage_path = f"{candidate_id}/{uuid.uuid4()}.{ext}"

    try:
        client = get_supabase_client()
        client.storage.from_(settings.SUPABASE_STORAGE_BUCKET_RESUMES).upload(
            storage_path,
            content,
            file_options={"content-type": "application/octet-stream", "upsert": "false"},
        )
    except Exception as exc:
        logger.error("resume_upload_failed", candidate_id=candidate_id, error=str(exc))
        raise StorageError("Failed to store resume file. Please try again.")

    return storage_path


def get_signed_resume_url(storage_path: str, expires_in_seconds: int = 300) -> str:
    """
    Generates a short-lived signed URL for a recruiter to view a resume.
    Default 5-minute expiry — long enough for a single view/download,
    short enough that a leaked link isn't useful for long.
    """
    try:
        client = get_supabase_client()
        result = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET_RESUMES).create_signed_url(
            storage_path, expires_in_seconds
        )
        return result["signedURL"]
    except Exception as exc:
        logger.error("signed_url_generation_failed", storage_path=storage_path, error=str(exc))
        raise StorageError("Failed to generate resume access link.")
