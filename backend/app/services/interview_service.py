"""
Shared interview-scheduling and result-processing logic.

WHY this is its own service instead of living inline in routes:
- schedule_interview_for_candidate is called from two places — the
  recruiter's manual "Send Interview" button and the automatic
  score-threshold trigger. One function, two callers, no drift.
- process_completed_transcript is called from two places too — the
  Vapi webhook (push) and the active-sync endpoint (pull). Vapi's
  webhook can fail to arrive (dropped, metadata missing from payload,
  ngrok tunnel restarted mid-call). Rather than only ever waiting
  passively for a push that might never come, a recruiter can trigger
  a pull via /interviews/{id}/sync, which fetches the call directly
  from Vapi's REST API and runs through this exact same processing
  path — consistent results no matter which route got us here.
"""

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.logging_config import get_logger
from app.models.candidate import Candidate, CandidateStage
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job
from app.services import email_service

logger = get_logger(__name__)
settings = get_settings()


def schedule_interview_for_candidate(db, candidate: Candidate, job: Job, *, frontend_base_url: str) -> Interview:
    """
    Creates an Interview row, advances the candidate's stage, and emails
    the invite. Does NOT commit — the caller's existing transaction
    commits it, so this stays atomically consistent with whatever
    triggered it (a resume score, a recruiter click, etc.).
    """
    interview = Interview(
        candidate_id=candidate.id,
        status=InterviewStatus.SCHEDULED,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.INTERVIEW_LINK_EXPIRY_DAYS),
    )
    db.add(interview)
    db.flush()

    candidate.stage = CandidateStage.INTERVIEW_SCHEDULED

    interview_url = f"{frontend_base_url}/interview/{interview.id}"
    email_sent = email_service.send_interview_invite(
        to_email=candidate.email,
        candidate_name=candidate.full_name,
        job_title=job.title,
        company_name=settings.COMPANY_DISPLAY_NAME,
        interview_url=interview_url,
    )
    if not email_sent:
        logger.warning("interview_invite_email_failed", interview_id=interview.id, candidate_id=candidate.id)

    return interview


def process_completed_transcript(db, interview: Interview, transcript: str, vapi_call_id: str | None = None, recording_url: str | None = None) -> None:
    """
    Saves a transcript, scores it via Claude, advances the candidate's
    stage, and sends the follow-up email. Shared by the webhook handler
    and the active-sync endpoint — see module docstring.
    """
    from app.models.decision_log import DecisionStepType
    from app.services import claude_service
    from app.services.decision_log_service import record_decision

    if vapi_call_id:
        interview.vapi_call_id = vapi_call_id
    if recording_url:
        interview.recording_storage_path = recording_url
    interview.transcript = transcript
    interview.status = InterviewStatus.COMPLETED

    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(Job).filter(Job.id == candidate.job_id).first() if candidate else None

    if transcript and job:
        try:
            result = claude_service.score_interview_transcript(
                transcript=transcript,
                job_title=job.title,
                required_skills=job.required_skills,
                min_years_experience=job.min_years_experience,
                interview_id=interview.id,
            )
            interview.tech_score = result.tech_score
            interview.communication_score = result.communication_score
            interview.overall_score = result.overall_score
            interview.ai_report = result.summary + "\n\nStrengths: " + result.strengths + "\n\nConcerns: " + result.concerns

            record_decision(
                db,
                entity_type="interview",
                entity_id=interview.id,
                step_name="interview_scoring",
                step_type=DecisionStepType.PROBABILISTIC,
                outcome=f"tech={result.tech_score} comm={result.communication_score} overall={result.overall_score}",
                confidence=result.confidence,
                model_version=settings.CLAUDE_MODEL,
            )
        except Exception as exc:
            logger.error("interview_scoring_failed", interview_id=interview.id, error=str(exc))


    # Apply violation-based score deduction — the missing half of the
    # rule you specified: escalation (auto-end at 3 violations) already
    # existed, but nothing was actually deducting marks. Capped at
    # MAX_INTEGRITY_VIOLATIONS so a runaway violation count can't push
    # the score negative for reasons beyond the stated rule.
    from app.models.interview import InterviewEvent
    violation_count = db.query(InterviewEvent).filter(InterviewEvent.interview_id == interview.id).count()
    if violation_count > 0 and interview.overall_score is not None:
        deduction = min(violation_count, settings.MAX_INTEGRITY_VIOLATIONS) * settings.VIOLATION_SCORE_DEDUCTION
        interview.overall_score = max(0, interview.overall_score - deduction)

    # Auto-route the candidate based on final (post-deduction) overall
    # score. Recruiters can still change this manually afterward via
    # PATCH /candidates/{id}/stage — this just sets the starting point
    # instead of leaving every interviewed candidate stuck at
    # INTERVIEWED with no next step.
    
    if candidate:
        if interview.overall_score is not None:
            if interview.overall_score >= settings.AUTO_SHORTLIST_SCORE_THRESHOLD:
                candidate.stage = CandidateStage.RECOMMENDED
            else:
                candidate.stage = CandidateStage.REJECTED
        else:
            candidate.stage = CandidateStage.INTERVIEWED

    if candidate and job:
        if candidate.stage == CandidateStage.RECOMMENDED:
            email_service.send_interview_followup(
                to_email=candidate.email,
                candidate_name=candidate.full_name,
                job_title=job.title,
                company_name=settings.COMPANY_DISPLAY_NAME,
            )
        elif candidate.stage == CandidateStage.REJECTED:
            email_service.send_interview_rejection(
                to_email=candidate.email,
                candidate_name=candidate.full_name,
                job_title=job.title,
                company_name=settings.COMPANY_DISPLAY_NAME,
            )
        # candidate.stage == INTERVIEWED (no score available) intentionally
        # sends nothing — no pass/fail email should go out without a real score.


def fetch_call_from_vapi(vapi_call_id: str) -> dict:
    """
    Actively pulls a call's status/transcript from Vapi's REST API using
    our private key — the "sync" half of the push/pull pair described in
    the module docstring. Raises on any HTTP failure; caller decides how
    to handle it.
    """
    import httpx

    response = httpx.get(
        f"{settings.VAPI_API_BASE_URL}/call/{vapi_call_id}",
        headers={"Authorization": f"Bearer {settings.VAPI_API_KEY}"},
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


def get_vapi_recording_url(vapi_call_id: str | None, kind: str = "mono") -> str | None:
    """
    Vapi recordings live in a private bucket and can't be fetched directly —
    https://docs.vapi.ai/assistants/retrieve-call-artifacts. We have to hit
    Vapi's own API with our private key; it responds with a 302 redirect to
    a short-lived, actually-playable signed URL. Must be requested fresh
    each time a report is viewed — never cache/store the redirect target,
    it expires quickly. Returns None (never raises) so a recording issue
    degrades to "no player shown" rather than breaking the whole report.
    """
    import httpx

    if not vapi_call_id:
        return None

    endpoint = f"{settings.VAPI_API_BASE_URL}/call/{vapi_call_id}/{kind}-recording"
    try:
        response = httpx.get(
            endpoint,
            headers={"Authorization": f"Bearer {settings.VAPI_API_KEY}"},
            timeout=15.0,
            follow_redirects=False,
        )
        if response.status_code in (301, 302, 303, 307, 308):
            return response.headers.get("location")
        logger.warning(
            "vapi_recording_unexpected_status",
            vapi_call_id=vapi_call_id,
            status_code=response.status_code,
        )
        return None
    except Exception as exc:
        logger.error("vapi_recording_fetch_failed", vapi_call_id=vapi_call_id, error=str(exc))
        return None


def run_pending_syncs(db) -> int:
    """
    One pass: finds every interview that has a vapi_call_id but no
    transcript yet, and tries to sync each from Vapi's API. Returns the
    count of interviews successfully synced this pass. Called on a
    timer by background_sync_loop — see main.py for how it's started.
    """
    pending = (
        db.query(Interview)
        .filter(
            Interview.vapi_call_id.isnot(None),
            Interview.transcript.is_(None),
            Interview.status.in_([InterviewStatus.SCHEDULED, InterviewStatus.IN_PROGRESS]),
        )
        .all()
    )
    synced_count = 0
    for interview in pending:
        try:
            call_data = fetch_call_from_vapi(interview.vapi_call_id)
        except Exception as exc:
            logger.warning("background_sync_fetch_failed", interview_id=interview.id, error=str(exc))
            continue
        if call_data.get("status") != "ended":
            continue
        transcript = call_data.get("transcript") or (call_data.get("artifact") or {}).get("transcript") or ""
        from app.api.routes.interviews import _extract_recording_url  # local import avoids a circular import at module load time

        recording_url = _extract_recording_url(call_data)
        process_completed_transcript(db, interview, transcript, vapi_call_id=interview.vapi_call_id, recording_url=recording_url)
        synced_count += 1
        logger.info("background_sync_completed", interview_id=interview.id)
    return synced_count

def abandon_stale_unconnected_interviews(db) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.STUCK_IN_PROGRESS_THRESHOLD_MINUTES)
    stale = (
        db.query(Interview)
        .filter(
            Interview.status == InterviewStatus.IN_PROGRESS,
            Interview.vapi_call_id.is_(None),
            Interview.updated_at < cutoff,
        )
        .all()
    )
    count = 0
    for interview in stale:
        interview.status = InterviewStatus.ABANDONED
        count += 1
    if count:
        db.commit()
        logger.info("abandoned_stale_unconnected_interviews", count=count)
    return count


def send_pending_reminders(db) -> int:
    """
    Re-sends the interview invite email to any candidate who hasn't
    started their interview yet, every REMINDER_INTERVAL_DAYS, until
    they either start/complete the interview (status changes away from
    SCHEDULED) or the link expires — both already naturally stop this
    query from matching, no separate stop logic needed.
    """
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=settings.REMINDER_INTERVAL_DAYS)

    candidates_due = (
        db.query(Interview)
        .filter(
            Interview.status == InterviewStatus.SCHEDULED,
            Interview.expires_at > now,
            Interview.last_reminder_sent_at.is_(None),
            Interview.created_at <= cutoff,
        )
        .all()
    )

    sent_count = 0
    for interview in candidates_due:
        candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
        if candidate is None:
            continue
        job = db.query(Job).filter(Job.id == candidate.job_id).first()
        if job is None:
            continue

        interview_url = f"{settings.FRONTEND_URL}/interview/{interview.id}"
        email_sent = email_service.send_interview_invite(
            to_email=candidate.email,
            candidate_name=candidate.full_name,
            job_title=job.title,
            company_name=settings.COMPANY_DISPLAY_NAME,
            interview_url=interview_url,
        )
        if email_sent:
            interview.last_reminder_sent_at = now
            sent_count += 1

    if sent_count:
        db.commit()
    return sent_count


async def background_sync_loop() -> None:
    """
    Runs forever in the background, started once at app startup (see
    main.py lifespan). Never crashes the app on a single failure — one
    bad iteration logs and waits for the next tick rather than killing
    the loop, since this must keep running for the lifetime of the process.
    """
    import asyncio

    from app.database import SessionLocal

    while True:
        await asyncio.sleep(settings.BACKGROUND_SYNC_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            count = run_pending_syncs(db)
            abandoned_count = abandon_stale_unconnected_interviews(db)
            if abandoned_count:
                logger.info("background_abandon_pass_completed", abandoned_count=abandoned_count)
            if count:
                logger.info("background_sync_pass_completed", synced_count=count)
        except Exception as exc:
            logger.error("background_sync_loop_error", error=str(exc))
        finally:
            db.close()

        db = SessionLocal()
        try:
            reminder_count = await asyncio.to_thread(send_pending_reminders, db)
            if reminder_count:
                logger.info("reminder_emails_sent", count=reminder_count)
        except Exception as exc:
            logger.error("reminder_loop_error", error=str(exc))
        finally:
            db.close()

    
