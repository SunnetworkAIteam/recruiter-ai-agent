from enum import Enum as PyEnum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUID_PK, TimestampMixin, new_uuid


class JobStatus(str, PyEnum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(UUID_PK, primary_key=True, default=new_uuid)

    # Clerk org/user ID of the recruiter/org that owns this job — used for
    # row-level authorization checks (never trust a job_id from the client
    # alone; always verify org ownership server-side).
    owner_org_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured requirements passed verbatim into the Claude scoring prompt
    # AND the Vapi "Smart Question Generator" variable set — single source
    # of truth instead of duplicating requirement text in two places.
    required_skills: Mapped[str] = mapped_column(Text, nullable=False, default="")
    min_years_experience: Mapped[int] = mapped_column(nullable=False, default=0)

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), nullable=False, default=JobStatus.DRAFT
    )

    candidates = relationship("Candidate", back_populates="job", cascade="all, delete-orphan")
