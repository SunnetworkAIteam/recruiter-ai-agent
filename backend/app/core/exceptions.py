"""
Custom exception hierarchy.

WHY: Bare `except Exception` and generic 500s tell you (and the frontend)
nothing. Every domain error here maps to a specific HTTP status and a
machine-readable `error_code` the frontend can branch on — instead of
parsing English error strings, which breaks the moment someone edits
a message.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.logging_config import get_logger

logger = get_logger(__name__)


class RecruiterAIError(Exception):
    """Base class for all application-specific errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ValidationFailedError(RecruiterAIError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "validation_failed"


class ResourceNotFoundError(RecruiterAIError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class UnauthorizedError(RecruiterAIError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"


class ForbiddenError(RecruiterAIError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"


class FileTooLargeError(RecruiterAIError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    error_code = "file_too_large"


class UnsupportedFileTypeError(RecruiterAIError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    error_code = "unsupported_file_type"


class ClaudeAPIError(RecruiterAIError):
    """Raised when the Claude API call fails after all retries."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "ai_scoring_failed"


class VapiWebhookError(RecruiterAIError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "invalid_webhook"


class InterviewLinkInvalidError(RecruiterAIError):
    """Interview link expired, already used, or otherwise no longer valid."""

    status_code = status.HTTP_410_GONE
    error_code = "interview_link_invalid"


class StorageError(RecruiterAIError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = "storage_failed"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RecruiterAIError)
    async def handle_app_error(request: Request, exc: RecruiterAIError):
        logger.warning(
            "handled_application_error",
            error_code=exc.error_code,
            message=exc.message,
            path=request.url.path,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def handle_pydantic_validation_error(request: Request, exc: PydanticValidationError):
        # WHY THIS EXISTS: FastAPI auto-handles validation errors raised while
        # parsing request bodies/query params declared directly on a route.
        # But here we validate manually inside the handler (e.g. re-validating
        # multipart Form(...) fields against a stricter Pydantic model for
        # cross-field rules). Pydantic's own ValidationError raised THERE is
        # NOT a FastAPI RequestValidationError and is not caught by FastAPI's
        # default handler — without this, it falls through to the generic
        # Exception handler and returns an opaque 500 instead of a clean 422.
        # This exact bug shipped and was caught by the test suite before
        # merge; see tests/test_candidates_api.py::test_rejects_invalid_email.
        logger.info("request_validation_failed", path=request.url.path, errors=exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error_code": "validation_failed",
                "message": "One or more fields are invalid.",
                "details": {"errors": exc.errors(include_url=False, include_context=False)},
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # Never leak internal exception details to the client in production —
        # log the full trace server-side, return a generic message client-side.
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "internal_error",
                "message": "An unexpected error occurred. Our team has been notified.",
            },
        )
