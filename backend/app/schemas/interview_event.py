from pydantic import BaseModel, Field

from app.models.interview import InterviewEventType


class InterviewEventCreateRequest(BaseModel):
    event_type: InterviewEventType
    offset_ms: int = Field(..., ge=0)
    metadata: dict = Field(default_factory=dict)
