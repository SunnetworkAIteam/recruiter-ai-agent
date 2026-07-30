"""
Job posting CRUD.

WHY every query here filters by owner_org_id: same IDOR reasoning as
candidates.py — a job_id is a guessable-ish UUID a recruiter could pass
in manually; ownership must be enforced server-side on every read AND
write, not just on create.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import require_org_membership, AuthenticatedUser
from app.core.exceptions import ResourceNotFoundError
from app.database import get_db
from app.logging_config import get_logger
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.job import JobCreateRequest, JobResponse, JobUpdateRequest

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_response(job: Job, candidate_count: int) -> JobResponse:
    return JobResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        required_skills=job.required_skills,
        min_years_experience=job.min_years_experience,
        status=job.status,
        candidate_count=candidate_count,
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    job = Job(
        owner_org_id=user.org_id,
        title=payload.title,
        description=payload.description,
        required_skills=payload.required_skills,
        min_years_experience=payload.min_years_experience,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("job_created", job_id=job.id, org_id=user.org_id)
    return _to_response(job, candidate_count=0)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    rows = (
        db.query(Job, func.count(Candidate.id).label("candidate_count"))
        .outerjoin(Candidate, Candidate.job_id == Job.id)
        .filter(Job.owner_org_id == user.org_id)
        .group_by(Job.id)
        .order_by(Job.created_at.desc())
        .all()
    )
    return [_to_response(job, count) for job, count in rows]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    job = db.query(Job).filter(Job.id == job_id, Job.owner_org_id == user.org_id).first()
    if job is None:
        raise ResourceNotFoundError("Job not found")
    count = db.query(func.count(Candidate.id)).filter(Candidate.job_id == job.id).scalar()
    return _to_response(job, count or 0)


@router.patch("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    payload: JobUpdateRequest,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    job = db.query(Job).filter(Job.id == job_id, Job.owner_org_id == user.org_id).first()
    if job is None:
        raise ResourceNotFoundError("Job not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(job, field, value)

    db.commit()
    db.refresh(job)
    count = db.query(func.count(Candidate.id)).filter(Candidate.job_id == job.id).scalar()
    return _to_response(job, count or 0)


@router.get("/{job_id}/public", response_model=dict)
def get_job_public(job_id: str, db: Session = Depends(get_db)):
    """
    Unauthenticated, minimal view for the public application page — a
    candidate applying doesn't have a Clerk account. Deliberately returns
    only fields safe to show publicly (no owner_org_id, no internal notes).
    """
    job = db.query(Job).filter(Job.id == job_id, Job.status == "open").first()
    if job is None:
        raise ResourceNotFoundError("This job posting is not available")
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills,
        "min_years_experience": job.min_years_experience,
    }
