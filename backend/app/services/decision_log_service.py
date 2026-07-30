"""
Decision log writer.

WHY a single function instead of callers constructing DecisionLog rows
directly: consistent shape, one place to change if the table evolves,
and it's a natural spot to add things later (e.g. shipping these to an
external audit sink) without touching every call site.

WHY this never raises: logging a decision must never be the reason a
real request fails. If writing an audit row fails, we log that failure
loudly (so it's visible in monitoring) but let the caller's actual work
proceed — an incomplete audit trail is bad; blocking a resume score
because the audit table had a blip is worse.
"""

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models.decision_log import DecisionLog, DecisionStepType

logger = get_logger(__name__)


def record_decision(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    step_name: str,
    step_type: DecisionStepType,
    outcome: str,
    confidence: float | None = None,
    model_version: str | None = None,
) -> None:
    """
    Adds a DecisionLog row to the session. Does NOT commit — caller's
    existing transaction commits it alongside the real work, so a
    decision log entry and the change it describes are always
    atomically consistent (never one without the other).
    """
    try:
        db.add(
            DecisionLog(
                entity_type=entity_type,
                entity_id=entity_id,
                step_name=step_name,
                step_type=step_type,
                outcome=outcome[:4000],
                confidence=confidence,
                model_version=model_version,
            )
        )
    except Exception as exc:
        logger.error("decision_log_write_failed", entity_type=entity_type, entity_id=entity_id, error=str(exc))
