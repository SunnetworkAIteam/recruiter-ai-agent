from enum import Enum as PyEnum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUID_PK, TimestampMixin, new_uuid


class CandidateStage(str, PyEnum):
    APPLIED = "applied"
    SCREENED = "screened"
    SHORTLISTED = "shortlisted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWED = "interviewed"
    REJECTED = "rejected"
    HIRED = "hired"


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(UUID_PK, primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Path within Supabase Storage, NOT a public URL — signed URLs are
    # generated on demand server-side so resumes are never publicly listable.
    resume_storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    stage: Mapped[CandidateStage] = mapped_column(
        Enum(CandidateStage, name="candidate_stage"), nullable=False, default=CandidateStage.APPLIED
    )

    # Consent flags — required before ANY biometric/video processing happens.
    # These must be explicitly set true by a real consent action, never
    # defaulted true. See ConsentRecord for the full audit trail.
    consent_recording: Mapped[bool] = mapped_column(nullable=False, default=False)
    consent_biometric_proctoring: Mapped[bool] = mapped_column(nullable=False, default=False)

    job = relationship("Job", back_populates="candidates")
    resume_score = relationship(
        "ResumeScore", back_populates="candidate", uselist=False, cascade="all, delete-orphan"
    )
    interviews = relationship("Interview", back_populates="candidate", cascade="all, delete-orphan")
