from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUID_PK, TimestampMixin, new_uuid


class InterviewStatus(str, PyEnum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class Interview(Base, TimestampMixin):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(UUID_PK, primary_key=True, default=new_uuid)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    vapi_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    status: Mapped[InterviewStatus] = mapped_column(
        Enum(InterviewStatus, name="interview_status"), nullable=False, default=InterviewStatus.SCHEDULED
    )
    # Link tampering / reuse defense: an interview link is valid for a
    # limited window and can only be started once. See interviews.py
    # `_ensure_interview_is_startable` for enforcement — this column
    # alone does nothing without that server-side check.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # Tracks the last time a reminder email was sent, so the background
    # loop knows when the next one is due. NULL means never reminded yet.
    last_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Storage path, not public URL — same reasoning as resume_storage_path.
    recording_storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    tech_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    communication_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate = relationship("Candidate", back_populates="interviews")
    events = relationship("InterviewEvent", back_populates="interview", cascade="all, delete-orphan")


class InterviewEventType(str, PyEnum):
    TAB_SWITCH = "tab_switch"
    MULTIPLE_FACES = "multiple_faces"
    NO_FACE_DETECTED = "no_face_detected"
    SCREEN_SHARE_DETECTED = "screen_share_detected"
    UNUSUAL_EYE_MOVEMENT = "unusual_eye_movement"
    WINDOW_BLUR = "window_blur"
    COPY_PASTE = "copy_paste"
    CAMERA_OFF = "camera_off"
    FULLSCREEN_EXIT = "fullscreen_exit"
    IDENTITY_MISMATCH = "identity_mismatch"  # face at interview start didn't match application selfie — flag only, never auto-escalates


class InterviewEvent(Base, TimestampMixin):
    """
    Raw proctoring signal log. This table is intentionally append-only
    and never edited — it's the evidentiary record behind the Integrity
    Report. If a candidate disputes a flag, this table (with timestamps)
    is what you show them, not a derived summary.
    """

    __tablename__ = "interview_events"

    id: Mapped[str] = mapped_column(UUID_PK, primary_key=True, default=new_uuid)
    interview_id: Mapped[str] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[InterviewEventType] = mapped_column(
        Enum(InterviewEventType, name="interview_event_type"), nullable=False
    )
    # Client-reported timestamp offset (ms from interview start) — lets you
    # correlate the event to the exact moment in the recording/transcript.
    offset_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    interview = relationship("Interview", back_populates="events")
