"""
Request/response schemas.

WHY strict validation here specifically: this is the candidate-facing
surface of the API — the one part of the system that untrusted, unauthenticated
members of the public can hit directly (anyone can apply to a job posting).
Every field is validated for length and shape BEFORE it touches the DB or
gets interpolated into a Claude prompt.
"""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.candidate import CandidateStage


class CandidateCreateRequest(BaseModel):
    job_id: str = Field(..., description="UUID of the job being applied to")
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("full_name")
    @classmethod
    def strip_and_validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name cannot be blank")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.fullmatch(r"[\d+\-() ]{6,32}", v):
            raise ValueError("phone contains invalid characters")
        return v


class CandidateResponse(BaseModel):
    id: str
    job_id: str
    full_name: str
    email: str
    stage: CandidateStage

    model_config = {"from_attributes": True}


class ResumeScoreResponse(BaseModel):
    tech_score: int
    communication_score: int
    role_match_score: int
    summary: str
    strengths: str
    concerns: str

    model_config = {"from_attributes": True}


class CandidateDetailResponse(BaseModel):
    id: str
    job_id: str
    job_title: str
    full_name: str
    email: str
    stage: CandidateStage
    tech_score: int | None = None
    communication_score: int | None = None
    role_match_score: int | None = None
    applied_at: str
