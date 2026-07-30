"""
Structured logging setup.

WHY structlog + JSON instead of print() or basic logging:
- In production (Koyeb, Render, anywhere), your logs are aggregated by a
  log collector. JSON logs are queryable ("show me all errors for
  candidate_id=X"); print() output is not.
- Every log line carries context (request_id, candidate_id, job_id) so
  you can trace a single request across resume upload -> Claude scoring
  -> DB write without grepping blindly.
- print() statements are also a common way secrets accidentally leak
  into logs. Centralizing logging means we can redact known secret
  field names in one place (see `_redact_processor`).
"""

import logging
import sys

import structlog

_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "anthropic_api_key",
    "vapi_api_key",
    "resend_api_key",
    "clerk_secret_key",
    "password",
    "token",
}


def _redact_processor(logger, method_name, event_dict):
    """Redact anything that looks like a secret before it ever hits stdout."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
