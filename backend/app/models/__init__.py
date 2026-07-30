"""
Import all models here so Alembic's autogenerate and Base.metadata.create_all
can discover every table. If a model isn't imported somewhere that
eventually gets imported by main.py, Alembic will silently miss it in
migrations — this file exists specifically to prevent that class of bug.
"""

from app.models.candidate import Candidate, CandidateStage  # noqa: F401
from app.models.decision_log import DecisionLog, DecisionStepType  # noqa: F401
from app.models.interview import (  # noqa: F401
    Interview,
    InterviewEvent,
    InterviewEventType,
    InterviewStatus,
)
from app.models.job import Job, JobStatus  # noqa: F401
from app.models.resume_score import ResumeScore  # noqa: F401
