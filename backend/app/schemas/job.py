from pydantic import BaseModel, Field, field_validator

from app.models.job import JobStatus


class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    required_skills: str = Field(default="", max_length=2000)
    min_years_experience: int = Field(default=0, ge=0, le=50)

    @field_validator("title", "description")
    @classmethod
    def strip_and_require(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("cannot be blank")
        return v


class JobUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)
    required_skills: str | None = Field(default=None, max_length=2000)
    min_years_experience: int | None = Field(default=None, ge=0, le=50)
    status: JobStatus | None = None


class JobResponse(BaseModel):
    id: str
    title: str
    description: str
    required_skills: str
    min_years_experience: int
    status: JobStatus
    candidate_count: int = 0

    model_config = {"from_attributes": True}
