"""
Shared model mixins.

WHY a TimestampMixin: every table needs created_at/updated_at for
auditability (a recruiter WILL ask "when was this candidate scored?"
and "was this record changed after the interview?" — especially once
you have a proctoring/integrity dispute).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def new_uuid() -> str:
    return str(uuid.uuid4())


UUID_PK = UUID(as_uuid=False)
