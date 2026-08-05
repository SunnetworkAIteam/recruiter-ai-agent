"""
Interview endpoints: recruiter-triggered scheduling, candidate-facing
public view, and the Vapi webhook receiver.

THREE THINGS THAT MATTER MOST IN THIS FILE:

1. WEBHOOK SIGNATURE VERIFICATION IS NOT OPTIONAL.
   Without it, anyone who finds our webhook URL (which lives in the
   public internet, in Vapi's dashboard config) could POST a fake
   "end-of-call-report" with a fabricated transcript and score, and our
   system would silently accept it as a real interview result. We
   verify the `x-vapi-secret` header against VAPI_WEBHOOK_SECRET using
   a constant-time comparison (hmac.compare_digest) — a naive `==`
   comparison leaks timing information an attacker could exploit to
   guess the secret one character at a time.

2. WEBHOOKS MUST BE IDEMPOTENT.
   Vapi (like most webhook providers) may retry a delivery if it doesn't
   get a fast 200 response, or a network blip could cause a duplicate.
   If we're not careful, a duplicate `end-of-call-report` would re-score
   the interview (wasting a Claude API call) and send the candidate a
   duplicate follow-up email. We guard this by checking whether the
   interview already has a transcript before doing any work.

3. THE WEBHOOK HANDLER MUST NEVER 500 ON A CLAUDE/EMAIL FAILURE.
   If Claude scoring fails, we still want to save the transcript and
   mark the interview reviewable — a recruiter can read the transcript
   even without an AI score. If email fails, that must never affect
   whether the interview data itself gets saved. Partial success is
   the correct behavior here, not all-or-nothing.
"""

import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, require_org_membership
from app.core.exceptions import InterviewLinkInvalidError, ResourceNotFoundError, VapiWebhookError
from app.core.rate_limit import limiter
from app.config import get_settings
from app.database import get_db
from app.logging_config import get_logger
from app.models.candidate import Candidate, CandidateStage
from app.models.interview import Interview, InterviewEvent, InterviewStatus
from app.models.job import Job
from app.schemas.interview import InterviewCreateResponse, InterviewPublicResponse, InterviewRecruiterResponse, InterviewViolationEntry
from app.schemas.interview_event import InterviewEventCreateRequest
from app.services import claude_service, email_service, interview_service
from app.services.decision_log_service import record_decision
from app.models.decision_log import DecisionStepType

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(tags=["interviews"])

FRONTEND_BASE_URL = settings.FRONTEND_URL


@router.post(
    "/candidates/{candidate_id}/interview",
    response_model=InterviewCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def schedule_interview(
    candidate_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    """
    Recruiter action: creates an Interview record and emails the
    candidate their unique interview link. Org-scoped via the Job join,
    same pattern as every other recruiter-facing query in this codebase.
    """
    candidate = (
        db.query(Candidate)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Candidate.id == candidate_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if candidate is None:
        raise ResourceNotFoundError("Candidate not found")

    job = db.query(Job).filter(Job.id == candidate.job_id).first()

    interview = interview_service.schedule_interview_for_candidate(
        db, candidate, job, frontend_base_url=FRONTEND_BASE_URL
    )

    interview_url = f"{FRONTEND_BASE_URL}/interview/{interview.id}"

    record_decision(
        db,
        entity_type="candidate",
        entity_id=candidate.id,
        step_name="interview_scheduled",
        step_type=DecisionStepType.DETERMINISTIC,
        outcome="manually scheduled by recruiter",
    )

    db.commit()
    db.refresh(interview)

    return InterviewCreateResponse(
        id=interview.id,
        candidate_id=candidate.id,
        status=interview.status,
        interview_url=interview_url,
    )


def _ensure_interview_is_startable(db: Session, interview: Interview) -> None:
    """
    Central enforcement point for interview-link tampering/reuse defense.
    Both get_interview_public and start_interview call this — one place
    to keep the rules consistent, since duplicating this check risks the
    two endpoints silently drifting apart. Every rejection is logged as
    a deterministic decision — this is the security-relevant half of the
    audit trail (tampering/reuse attempts), distinct from the scoring
    audit trail (probabilistic decisions) logged elsewhere.
    """
    if interview.status in (InterviewStatus.COMPLETED, InterviewStatus.IN_PROGRESS, InterviewStatus.ABANDONED):
        record_decision(
            db,
            entity_type="interview",
            entity_id=interview.id,
            step_name="interview_link_access_check",
            step_type=DecisionStepType.DETERMINISTIC,
            outcome=f"rejected: status is already {interview.status.value}, link reuse blocked",
        )
        db.commit()
        raise InterviewLinkInvalidError("This interview link has already been used.")
    if interview.expires_at:
        expires_at = interview.expires_at
        # SQLite (used in tests) doesn't preserve tzinfo on round-trip the
        # way Postgres does — a naive datetime here is assumed UTC, since
        # that's what we always write. Without this, expiry checks work
        # in tests but the comparison itself is the thing under test, so
        # get it right for both databases rather than only the one we
        # happen to run CI against.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            record_decision(
                db,
                entity_type="interview",
                entity_id=interview.id,
                step_name="interview_link_access_check",
                step_type=DecisionStepType.DETERMINISTIC,
                outcome="rejected: link expired",
            )
            db.commit()
            raise InterviewLinkInvalidError("This interview link has expired. Please contact the recruiter for a new one.")


@router.get("/interviews/{interview_id}/public", response_model=InterviewPublicResponse)
@limiter.limit("30/minute")
def get_interview_public(request: Request, interview_id: str, db: Session = Depends(get_db)):
    """
    Unauthenticated — candidates don't have accounts. Returns only what
    the candidate's browser needs to render the interview room and start
    the Vapi call: names for personalization, and the assistant ID.
    Never returns scoring criteria or any other candidate's data.

    SECURITY: interview_id is a UUIDv4 (128 bits of randomness, not
    sequential/guessable) — that alone stops naive enumeration. But a
    valid, correctly-guessed-nothing link must still not be reusable
    forever or after the interview is already done — see
    _ensure_interview_is_startable for that enforcement.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if interview is None:
        raise ResourceNotFoundError("Interview not found")

    _ensure_interview_is_startable(db, interview)

    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(Job).filter(Job.id == candidate.job_id).first()

    return InterviewPublicResponse(
        id=interview.id,
        status=interview.status,
        candidate_name=candidate.full_name,
        job_title=job.title,
        company_name=settings.COMPANY_DISPLAY_NAME,
        required_skills=job.required_skills,
        min_years_experience=job.min_years_experience,
        vapi_assistant_id=settings.VAPI_ASSISTANT_ID,
    )


@router.post("/interviews/{interview_id}/start", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
def start_interview(request: Request, interview_id: str, db: Session = Depends(get_db)):
    """
    Called by the candidate's browser right before opening the Vapi call.
    This is the actual reuse-blocking transition: SCHEDULED -> IN_PROGRESS.
    Once this succeeds, the SAME link cannot start a second call — a
    second attempt (double-click, reused link, two tabs) hits the
    IN_PROGRESS check in _ensure_interview_is_startable and is rejected.
    This is enforced server-side, not just disabled in the UI — a client-
    side-only guard is not a real guard, see the browser-monitoring
    discussion on why client state can never be trusted alone.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if interview is None:
        raise ResourceNotFoundError("Interview not found")

    _ensure_interview_is_startable(db, interview)

    interview.status = InterviewStatus.IN_PROGRESS
    db.commit()
    return {"started": True}



def _to_recruiter_response(interview: Interview, candidate_name: str, job_title: str, db: Session) -> InterviewRecruiterResponse:
    violation_count = db.query(InterviewEvent).filter(InterviewEvent.interview_id == interview.id).count()
    return InterviewRecruiterResponse(
        id=interview.id,
        candidate_id=interview.candidate_id,
        candidate_name=candidate_name,
        job_title=job_title,
        status=interview.status,
        transcript=interview.transcript,
        recording_url=interview.recording_storage_path,
        tech_score=interview.tech_score,
        communication_score=interview.communication_score,
        overall_score=interview.overall_score,
        violation_count=violation_count,
        score_deducted=min(violation_count, settings.MAX_INTEGRITY_VIOLATIONS) * settings.VIOLATION_SCORE_DEDUCTION,
        ai_report=interview.ai_report,
    )


@router.get("/interviews", response_model=list[InterviewRecruiterResponse])
def list_interviews(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    rows = (
        db.query(Interview, Candidate.full_name, Job.title)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Job.owner_org_id == user.org_id)
        .order_by(Interview.created_at.desc())
        .all()
    )
    return [_to_recruiter_response(iv, name, title, db) for iv, name, title in rows]


@router.get("/interviews/{interview_id}/violations", response_model=list[InterviewViolationEntry])
def get_interview_violations(
    interview_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    interview = (
        db.query(Interview)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Interview.id == interview_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if interview is None:
        raise ResourceNotFoundError("Interview not found")
    events = (
        db.query(InterviewEvent)
        .filter(InterviewEvent.interview_id == interview.id)
        .order_by(InterviewEvent.created_at.asc())
        .all()
    )
    return [
        InterviewViolationEntry(
            event_type=e.event_type.value,
            offset_ms=e.offset_ms,
            occurred_at=e.created_at.isoformat(),
            score_deducted=settings.VIOLATION_SCORE_DEDUCTION,
        )
        for e in events
    ]



@router.get("/interviews/{interview_id}", response_model=InterviewRecruiterResponse)
def get_interview(
    interview_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    row = (
        db.query(Interview, Candidate.full_name, Job.title)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Interview.id == interview_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if row is None:
        raise ResourceNotFoundError("Interview not found")
    interview, candidate_name, job_title = row
    return _to_recruiter_response(interview, candidate_name, job_title, db)


@router.post("/interviews/{interview_id}/events", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
def log_interview_event(request: Request, interview_id: str, payload: InterviewEventCreateRequest, db: Session = Depends(get_db)):
    """
    Unauthenticated — called from the candidate's browser during a live
    interview (tab-switch, window-blur, multiple-faces, no-face-detected).

    ESCALATION: after settings.MAX_INTEGRITY_VIOLATIONS logged events for
    this interview, the response tells the frontend to end the call
    immediately and the interview is marked ABANDONED with a note in
    ai_report explaining why. This is real automated action, not just
    logging — but it stops the interview and flags it for a human
    recruiter to review, it does NOT delete the candidate or silently
    reject their application. That distinction is deliberate.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if interview is None:
        raise ResourceNotFoundError("Interview not found")


    event = InterviewEvent(
        interview_id=interview.id,
        event_type=payload.event_type,
        offset_ms=payload.offset_ms,
        metadata_json=str(payload.metadata),
    )
    db.add(event)
    db.flush()

    total_count = db.query(InterviewEvent).filter(InterviewEvent.interview_id == interview.id).count()
    no_face_count = (
        db.query(InterviewEvent)
        .filter(InterviewEvent.interview_id == interview.id, InterviewEvent.event_type == "no_face_detected")
        .count()
    )
    real_violation_count = total_count - no_face_count

    escalate = False
    if (
        real_violation_count >= settings.MAX_INTEGRITY_VIOLATIONS
        or no_face_count >= settings.MAX_NO_FACE_VIOLATIONS
    ) and interview.status not in (InterviewStatus.COMPLETED, InterviewStatus.ABANDONED):
        escalate = True
        interview.status = InterviewStatus.ABANDONED
        interview.ai_report = (
            f"Interview auto-ended after {real_violation_count} integrity violation(s) "
            f"(tab switches or focus loss) and {no_face_count} camera-visibility event(s) were logged. "
            f"Flagged for recruiter review â€” "

    
        )
        record_decision(
            db,
            entity_type="interview",
            entity_id=interview.id,
            step_name="integrity_auto_escalation",
            step_type=DecisionStepType.DETERMINISTIC,
            outcome=f"auto-ended: {violation_count} violations >= threshold {settings.MAX_INTEGRITY_VIOLATIONS}",
        )

    db.commit()
    return {"logged": True, "violation_count": violation_count, "escalate": escalate}

def _extract_recording_url(payload: dict) -> str | None:
    """Vapi's recording URL has moved location before (their own changelog
    shows deprecation) — check every known shape defensively."""
    artifact = payload.get("artifact") or {}
    recording = artifact.get("recording") or {}
    if isinstance(recording, dict):
        mono = recording.get("mono") or {}
        if isinstance(mono, dict) and mono.get("combinedUrl"):
            return mono["combinedUrl"]
        if recording.get("stereoUrl"):
            return recording["stereoUrl"]
    if artifact.get("recordingUrl"):
        return artifact["recordingUrl"]
    call = payload.get("call") or {}
    if call.get("recordingUrl"):
        return call["recordingUrl"]
    return None

def _verify_vapi_secret(request: Request) -> None:
    provided = request.headers.get("x-vapi-secret", "")
    if not provided or not hmac.compare_digest(provided, settings.VAPI_WEBHOOK_SECRET):
        raise VapiWebhookError("Invalid webhook signature")


@router.post("/webhooks/vapi", status_code=status.HTTP_200_OK)
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):
    _verify_vapi_secret(request)

    payload = await request.json()
    message = payload.get("message", {})
    message_type = message.get("type")

    # We only act on the final report; ignore status-update, tool-calls,
    # etc. — returning 200 for unhandled types so Vapi doesn't retry them.
    if message_type != "end-of-call-report":
        return {"received": True, "handled": False}

    call = message.get("call", {})
    vapi_call_id = call.get("id")
    # We pass our own interview_id through as call metadata when the
    # frontend starts the call (assistantOverrides.metadata) — this is
    # how we map a Vapi call back to our Interview row.
    interview_id = (call.get("metadata") or {}).get("interview_id")

    if not interview_id:
        logger.warning("vapi_webhook_missing_interview_id", vapi_call_id=vapi_call_id)
        return {"received": True, "handled": False, "reason": "missing interview_id in call metadata"}

    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if interview is None:
        logger.warning("vapi_webhook_unknown_interview", interview_id=interview_id)
        return {"received": True, "handled": False, "reason": "unknown interview_id"}

    # Idempotency guard — see module docstring point 2.
    if interview.transcript is not None:
        logger.info("vapi_webhook_duplicate_ignored", interview_id=interview_id)
        return {"received": True, "handled": False, "reason": "already processed"}

    transcript = message.get("transcript") or message.get("artifact", {}).get("transcript") or ""
    recording_url = _extract_recording_url(message)
    interview_service.process_completed_transcript(
        db, interview, transcript, vapi_call_id=vapi_call_id, recording_url=recording_url
    )

    return {"received": True, "handled": True}


@router.post("/interviews/{interview_id}/link-call", status_code=status.HTTP_200_OK)
def link_vapi_call(interview_id: str, payload: dict, db: Session = Depends(get_db)):
    """
    Unauthenticated — called by the candidate's browser the instant the
    Vapi call actually starts (the SDK's 'call-start' event gives us the
    real call.id). Storing this immediately, rather than waiting for it
    to arrive via the webhook's metadata, is what makes /sync reliable
    even if the webhook never fires or its payload doesn't include
    metadata — a known inconsistency in some Vapi configurations.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if interview is None:
        raise ResourceNotFoundError("Interview not found")
    vapi_call_id = payload.get("vapi_call_id")
    if vapi_call_id:
        interview.vapi_call_id = vapi_call_id
        db.commit()
    return {"linked": bool(vapi_call_id)}


@router.post("/interviews/{interview_id}/sync", status_code=status.HTTP_200_OK)
def sync_interview_from_vapi(
    interview_id: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_org_membership),
):
    """
    Recruiter-triggered: actively pulls the call's transcript/status
    directly from Vapi's API instead of waiting for a webhook that may
    never arrive. This is the fix for "interview finished, no score
    after hours" — a real, common failure mode when a webhook drops.
    """
    interview = (
        db.query(Interview)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .join(Job, Job.id == Candidate.job_id)
        .filter(Interview.id == interview_id, Job.owner_org_id == user.org_id)
        .first()
    )
    if interview is None:
        raise ResourceNotFoundError("Interview not found")
    if interview.transcript is not None:
        return {"synced": False, "reason": "already has a transcript"}
    if not interview.vapi_call_id:
        return {
            "synced": False,
            "reason": "no vapi_call_id on record yet — this interview started before the call-linking fix, or the candidate hasn't started the call. Check Vapi's dashboard Call Logs for the matching call and use /interviews/{id}/link-call to attach it manually.",
        }

    try:
        call_data = interview_service.fetch_call_from_vapi(interview.vapi_call_id)
    except Exception as exc:
        logger.error("vapi_sync_failed", interview_id=interview.id, error=str(exc))
        raise VapiWebhookError("Could not reach Vapi to sync this call. Try again shortly.")

    if call_data.get("status") != "ended":
        return {"synced": False, "reason": f"call status is still '{call_data.get('status')}', not ended yet"}


    transcript = call_data.get("transcript") or (call_data.get("artifact") or {}).get("transcript") or ""
    recording_url = _extract_recording_url(call_data)
    interview_service.process_completed_transcript(
        db, interview, transcript, vapi_call_id=interview.vapi_call_id, recording_url=recording_url
    )
    return {"synced": True}

