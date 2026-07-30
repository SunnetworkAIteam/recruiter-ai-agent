from pydantic import BaseModel, Field

from app.models.interview import InterviewStatus


class InterviewCreateResponse(BaseModel):
    id: str
    candidate_id: str
    status: InterviewStatus
    interview_url: str


class InterviewPublicResponse(BaseModel):
    """
    Unauthenticated, candidate-facing view. Deliberately minimal — no
    scoring criteria, no internal notes, no other candidates' data.
    """
    id: str
    status: InterviewStatus
    candidate_name: str
    job_title: str
    company_name: str
    required_skills: str
    min_years_experience: int
    vapi_assistant_id: str


class InterviewRecruiterResponse(BaseModel):
    id: str
    candidate_id: str
    candidate_name: str
    job_title: str
    status: InterviewStatus
    transcript: str | None
    recording_url: str | None = Field(default=None, validation_alias="recording_storage_path")
    tech_score: int | None
    communication_score: int | None
    overall_score: int | None
    violation_count: int = 0
    score_deducted: int = 0
    ai_report: str | None

    model_config = {"from_attributes": True, "populate_by_name": True}


class InterviewViolationEntry(BaseModel):
    event_type: str
    offset_ms: int
    occurred_at: str
    score_deducted: int

class DecisionLogEntry(BaseModel):
    id: str
    step_name: str
    step_type: str
    outcome: str
    confidence: float | None
    model_version: str | None
    created_at: str

    model_config = {"from_attributes": True, "protected_namespaces": ()}
