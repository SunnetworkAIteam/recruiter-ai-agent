"""
Public candidate application endpoint + recruiter-facing read endpoints.

WHY the apply endpoint is unauthenticated but rate-limited + validated:
Candidates apply without a Clerk account — that's a product requirement,
not an oversight. Because it's unauthenticated, it's the highest-risk
endpoint in the system, so it gets: strict multipart validation, file
type/size checks, rate limiting, and a Claude call wrapped in error
handling that never leaks internal details to the response.
"""

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.config import get_settings
from app.core.auth import require_org_membership, AuthenticatedUser
from app.core.exceptions import ResourceNotFoundError, ValidationFailedError
from app.core.rate_limit import limiter
from app.database import get_db
from app.logging_config import get_logger
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.resume_score import ResumeScore
from app.schemas.candidate import (
    CandidateCreateRequest,
    CandidateDetailResponse,
    CandidateResponse,
    ResumeScoreResponse,
)
from app.schemas.interview import DecisionLogEntry
from app.models.decision_log import DecisionLog
from app.models.interview import Interview
from app.services import claude_service, interview_service, storage_service
from app.services.decision_log_service import record_decision
from app.models.decision_log import DecisionStepType
from app.services.resume_parser import extract_text_from_resume
from app.models.candidate import CandidateStage
from app.services.storage_service import get_signed_resume_url
from app.core.exceptions import ValidationFailedError

logger = get_logger(__name__)
router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post(
    "/apply",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def apply_to_job(
    request: Request,  # required positional arg for slowapi's decorator to read client IP
    job_id: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str | None = Form(default=None),
    resume: UploadFile = File(...),
    selfie: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    
    """
    Candidate application flow:
    1. Validate the job exists and is open.
    2. Validate + parse the uploaded resume file.
    3. Persist the candidate record and store the resume file.
    4. Score the resume via Claude synchronously.

    NOTE ON SYNCHRONOUS SCORING: for an MVP with moderate application
    volume, scoring inline (blocking the HTTP response) is acceptable and
    simpler to reason about/debug. Once you're seeing meaningful concurrent
    traffic, move this to a background job (e.g. a queue + worker) so a
    slow Claude response doesn't hold open an HTTP connection. Flagging
    this now so it's a deliberate future change, not a surprise rewrite.
    """
    payload = CandidateCreateRequest(job_id=job_id, full_name=full_name, email=email, phone=phone)

    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if job is None:
        raise ResourceNotFoundError("Job not found")
    if job.status.value != "open":
        raise ValidationFailedError("This job is no longer accepting applications")

    content = await resume.read()
    resume_text = extract_text_from_resume(resume.filename or "resume", content)

    candidate = Candidate(
        job_id=job.id,
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        resume_storage_path="",  # set after upload below
    )

    db.add(candidate)
    db.flush()  # assigns candidate.id without committing yet
    storage_path = storage_service.upload_resume(candidate.id, resume.filename or "resume", content)
    candidate.resume_storage_path = storage_path

    selfie_content = await selfie.read()
    candidate.selfie_storage_path = storage_service.upload_selfie(candidate.id, selfie_content)

    try:
        score_result = claude_service.score_resume(
            resume_text=resume_text,
            job_title=job.title,
            job_description=job.description,
            required_skills=job.required_skills,
            min_years_experience=job.min_years_experience,
            candidate_id=candidate.id,
        )
        db.add(
            ResumeScore(
                candidate_id=candidate.id,
                tech_score=score_result.tech_score,
                communication_score=score_result.communication_score,
                role_match_score=score_result.role_match_score,
                summary=score_result.summary,
                strengths=score_result.strengths,
                concerns=score_result.concerns,
                raw_model_response=score_result.raw_response,
                model_version=score_result.model_version,
            )
        )
        candidate.stage = "screened"

        record_decision(
            db,
            entity_type="candidate",
            entity_id=candidate.id,
            step_name="resume_scoring",
            step_type=DecisionStepType.PROBABILISTIC,
            outcome=(
                f"tech={score_result.tech_score} comm={score_result.communication_score} "
                f"match={score_result.role_match_score}"
            ),
            confidence=score_result.confidence,
            model_version=score_result.model_version,
        )

        # Automatic interview invite — see AUTO_INVITE_SCORE_THRESHOLD docstring
        # in config.py. This is a real automated decision affecting a real
        # candidate, so it gets its own explicit, separately-tagged audit
        # entry — distinct from the scoring decision above — so a review
        # of "why was this candidate auto-advanced" is answerable without
        # conflating it with "why did they get this score."
        settings = get_settings()
        if settings.AUTO_INVITE_SCORE_THRESHOLD > 0 and score_result.role_match_score >= settings.AUTO_INVITE_SCORE_THRESHOLD:
            interview_service.schedule_interview_for_candidate(
                db, candidate, job, frontend_base_url=settings.FRONTEND_URL
            )
            record_decision(
                db,
                entity_type="candidate",
                entity_id=candidate.id,
                step_name="auto_invite_threshold",
                step_type=DecisionStepType.DETERMINISTIC,
                outcome=(
                    f"auto-invited: role_match_score {score_result.role_match_score} "
                    f">= threshold {settings.AUTO_INVITE_SCORE_THRESHOLD}"
                ),
            )
    except Exception as exc:
        # Deliberate design choice: the candidate record and resume upload
        # ALREADY succeeded above. If scoring fails, we do not roll back the
        # application — the candidate should not be penalized for an AI
        # outage. We commit what succeeded and log loudly so a recruiter
        # (or a retry job) can trigger re-scoring later.
        logger.error("resume_scoring_failed_after_application_saved", candidate_id=candidate.id, error=str(exc))
        db.commit()
        db.refresh(candidate)
        return candidate

    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("", response_model=list[CandidateDetailResponse])
def list_candidates(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
    job_id: str | None = None,
    stage: str | None = None,
):
    """
    Recruiter-facing candidate pipeline, scoped to the authenticated org
    via the Job join — same IDOR-prevention pattern as everywhere else in
    this file. Supports optional filtering by job and pipeline stage,
    which the frontend uses for the Candidates page filters.
    """

    query = (
        db.query(Candidate, Job.title, ResumeScore)
        .join(Job, Job.id == Candidate.job_id)
        .outerjoin(ResumeScore, ResumeScore.candidate_id == Candidate.id)
        .filter(Job.owner_org_id == user.org_id)
    )
    if job_id:
        query = query.filter(Candidate.job_id == job_id)
    if stage:
        query = query.filter(Candidate.stage == stage)

    rows = query.order_by(Candidate.created_at.desc()).all()

    # A candidate's stage alone can't distinguish "manually shortlisted,
    # not yet interviewed" from "shortlisted because they passed the
    # interview" — both currently use the same stage value. has_interview
    # lets the frontend hide "Send Interview" once one has actually
    # happened, regardless of what the stage says.
    candidate_ids_with_interview = {
        row[0]
        for row in db.query(Interview.candidate_id)
        .filter(Interview.candidate_id.in_([c.id for c, _, _ in rows]))
        .all()
    }

    return [
        CandidateDetailResponse(
            id=candidate.id,
            job_id=candidate.job_id,
            job_title=job_title,
            full_name=candidate.full_name,
            email=candidate.email,
            stage=candidate.stage,
            tech_score=score.tech_score if score else None,
            communication_score=score.communication_score if score else None,
            role_match_score=score.role_match_score if score else None,
            has_interview=candidate.id in candidate_ids_with_interview,
            applied_at=candidate.created_at.isoformat(),
        )
        for candidate, job_title, score in rows
    ]


@router.get("/stage-counts")
def get_candidate_stage_counts(
    job_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    """
    Pipeline stat-card counts for a single job's candidates — cumulative,
    not "currently sitting at this exact stage." A candidate who's been
    interviewed still counts toward Uploaded and Screened, since they
    genuinely passed through those steps — stage is mutually-exclusive
    on the model, but the funnel view needs "reached this far or beyond."
    """
    candidates = (
        db.query(Candidate)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Job.owner_org_id == user.org_id, Candidate.job_id == job_id)
        .all()
    )
    interviewed_candidate_ids = {
        row[0]
        for row in db.query(Interview.candidate_id)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .filter(Candidate.job_id == job_id, Interview.transcript.isnot(None))
        .all()
    }

    reached_shortlist_or_beyond = {
        CandidateStage.SHORTLISTED,
        CandidateStage.INTERVIEW_SCHEDULED,
        CandidateStage.INTERVIEWED,
        CandidateStage.REJECTED,
        CandidateStage.HIRED,
    }

    counts = {
        "uploaded": len(candidates),
        "screened": sum(1 for c in candidates if c.resume_score is not None),
        "shortlisted": sum(1 for c in candidates if c.stage in reached_shortlist_or_beyond),
        "interview_scheduled": sum(1 for c in candidates if c.stage == CandidateStage.INTERVIEW_SCHEDULED),
        "interviewed": sum(1 for c in candidates if c.id in interviewed_candidate_ids),
        "rejected": sum(1 for c in candidates if c.stage == CandidateStage.REJECTED),
        "hired": sum(1 for c in candidates if c.stage == CandidateStage.HIRED),
    }
    return counts




@router.get("/{candidate_id}/audit-log", response_model=list[DecisionLogEntry])
def get_candidate_audit_log(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    """
    Full decision trail for a candidate: resume scoring, any linked
    interview's scoring, and any security-relevant rejections (link
    tampering/reuse attempts) — everything needed to answer "why did
    this candidate get this score" without an engineer grepping logs.
    Org-scoped like every other candidate read in this file.
    """
    candidate = (
        db.query(Candidate)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Candidate.id == candidate_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if candidate is None:
        raise ResourceNotFoundError("Candidate not found")

    interview_ids = [
        row[0] for row in db.query(Interview.id).filter(Interview.candidate_id == candidate.id).all()
    ]
    entity_ids = [candidate.id] + interview_ids

    entries = (
        db.query(DecisionLog)
        .filter(DecisionLog.entity_id.in_(entity_ids))
        .order_by(DecisionLog.created_at.asc())
        .all()
    )
    return [
        DecisionLogEntry(
            id=e.id,
            step_name=e.step_name,
            step_type=e.step_type.value,
            outcome=e.outcome,
            confidence=e.confidence,
            model_version=e.model_version,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]


@router.get("/{candidate_id}/resume-score", response_model=ResumeScoreResponse)
def get_resume_score(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_org_membership),
):
    """
    Recruiter-only: fetch a candidate's resume score.
    SECURITY NOTE: we deliberately join through Job.owner_org_id and filter
    on the authenticated user's org — NOT just check "is this user logged
    in." Without the org filter, this is an IDOR (Insecure Direct Object
    Reference): any authenticated recruiter could enumerate candidate_id
    values and read every other company's candidate data. Multi-tenant
    systems must scope every query by tenant, on every read, every time —
    there is no such thing as "we'll add the tenant check later."
    """
    score = (
        db.query(ResumeScore)
        .join(Candidate, Candidate.id == ResumeScore.candidate_id)
        .join(Job, Job.id == Candidate.job_id)
        .filter(ResumeScore.candidate_id == candidate_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if score is None:
        raise ResourceNotFoundError("No resume score found for this candidate yet")
    return score

@router.get("/{candidate_id}/resume-download")
def get_resume_download_url(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    """
    Returns a fresh, short-lived signed URL to download a candidate's
    resume. Same org-scoping as every other candidate endpoint — a
    recruiter can only download resumes for candidates in their own org.
    Generated on demand, not stored, since the resume file itself is
    never publicly listable (see Candidate.resume_storage_path).
    """
    candidate = (
        db.query(Candidate)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Candidate.id == candidate_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if candidate is None:
        raise ResourceNotFoundError("Candidate not found")
    url = get_signed_resume_url(candidate.resume_storage_path)
    return {"url": url}

@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    """
    Org-scoped hard delete. Cascades to ResumeScore/Interview/InterviewEvent
    rows via the FK ondelete="CASCADE" already defined on those models —
    deleting a candidate cleanly removes their scoring and interview
    history too, not orphaned rows. Does NOT delete the resume file from
    Supabase Storage yet (noted as a follow-up, not silently skipped).
    """
    candidate = (
        db.query(Candidate)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Candidate.id == candidate_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if candidate is None:
        raise ResourceNotFoundError("Candidate not found")
    db.delete(candidate)
    db.commit()


@router.patch("/{candidate_id}/stage")
def update_candidate_stage(
    candidate_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(require_org_membership),
):
    """
    Recruiter-only: manually move a candidate to a new pipeline stage
    (e.g. HIRED, REJECTED) after reviewing their interview report.
    Same org-scoping requirement as get_resume_score above — a candidate
    row must only be mutable by a recruiter in the same org that owns
    the job they applied to.
    """
    candidate = (
        db.query(Candidate)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Candidate.id == candidate_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if candidate is None:
        raise ResourceNotFoundError("Candidate not found")

    new_stage = payload.get("stage")
    valid_stages = {s.value for s in CandidateStage}
    if new_stage not in valid_stages:
        raise ValidationFailedError(f"stage must be one of: {sorted(valid_stages)}")

    candidate.stage = new_stage
    db.commit()
    return {"id": candidate.id, "stage": candidate.stage}





