from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUID_PK, TimestampMixin, new_uuid


class ResumeScore(Base, TimestampMixin):
    __tablename__ = "resume_scores"

    id: Mapped[str] = mapped_column(UUID_PK, primary_key=True, default=new_uuid)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    tech_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    communication_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    role_match_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[str] = mapped_column(Text, nullable=False, default="")
    concerns: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Full raw Claude response, kept for auditability/debugging — if a
    # recruiter disputes a score, you need to see exactly what the model
    # said and why, not just the three numbers.
    raw_model_response: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    candidate = relationship("Candidate", back_populates="resume_score")
