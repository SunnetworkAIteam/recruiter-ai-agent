"""
Decision log — the auditability backbone.

WHY THIS TABLE EXISTS:
For a system that scores real people's employability, "the AI said 82%"
is not an acceptable answer to "why did this candidate get this score."
Every consequential step — whether it's a deterministic rule (file
validation, org-ownership check) or a probabilistic one (a Claude score)
— gets a row here. This is what makes the system answerable to a
recruiter, a candidate dispute, or a compliance review, instead of
requiring an engineer to grep logs.

step_type matters: deterministic steps are 100% reproducible given the
same input (a file-size check either passes or doesn't); probabilistic
steps are not (the same resume sent to Claude twice can score
differently). Recruiters and compliance reviewers need to know which
kind of decision they're looking at — treating an LLM score with the
same certainty as a rule-based check is exactly the failure mode this
table exists to prevent.
"""

from enum import Enum as PyEnum

from sqlalchemy import Enum, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUID_PK, TimestampMixin, new_uuid


class DecisionStepType(str, PyEnum):
    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"


class DecisionLog(Base, TimestampMixin):
    __tablename__ = "decision_logs"

    id: Mapped[str] = mapped_column(UUID_PK, primary_key=True, default=new_uuid)

    # e.g. "candidate", "interview" — kept as a plain string rather than
    # a foreign key, deliberately: this table must be able to log a
    # decision about any entity type without a schema migration every
    # time we add one, and it must survive even if the referenced row is
    # later deleted (the log is the audit trail, not a live reference).
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    step_type: Mapped[DecisionStepType] = mapped_column(Enum(DecisionStepType, name="decision_step_type"), nullable=False)

    outcome: Mapped[str] = mapped_column(Text, nullable=False)  # human-readable summary of what happened
    # Self-reported model confidence (0-100), null for deterministic steps
    # or when a probabilistic step didn't return one. See module docstring
    # — this is a soft signal, not a calibrated statistic.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
