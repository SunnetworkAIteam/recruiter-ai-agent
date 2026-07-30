import pytest

from app.core.auth import AuthenticatedUser, get_current_user
from app.main import app as fastapi_app
from app.models.candidate import Candidate, CandidateStage
from app.models.interview import Interview, InterviewStatus
from app.models.job import Job, JobStatus
from app.services import claude_service


def _fake_user(org_id: str = "org_test123"):
    return AuthenticatedUser(user_id="user_abc", org_id=org_id, claims={})


@pytest.fixture
def authed_client(client):
    fastapi_app.dependency_overrides[get_current_user] = lambda: _fake_user()
    yield client
    fastapi_app.dependency_overrides.pop(get_current_user, None)


def _make_candidate(db_session, org_id="org_test123"):
    job = Job(
        owner_org_id=org_id,
        title="Backend Engineer",
        description="desc",
        required_skills="Python",
        min_years_experience=2,
        status=JobStatus.OPEN,
    )
    db_session.add(job)
    db_session.flush()
    candidate = Candidate(
        job_id=job.id,
        full_name="Jane Doe",
        email="jane@example.com",
        resume_storage_path="path.pdf",
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate, job


class TestScheduleInterview:
    def test_schedule_interview_success(self, authed_client, db_session, mocker):
        candidate, job = _make_candidate(db_session)
        mocker.patch("app.services.email_service.send_interview_invite", return_value=True)

        response = authed_client.post(f"/api/v1/candidates/{candidate.id}/interview")
        assert response.status_code == 201
        body = response.json()
        assert body["candidate_id"] == candidate.id
        assert body["status"] == "scheduled"
        assert body["interview_url"].endswith(f"/interview/{body['id']}")

        db_session.refresh(candidate)
        assert candidate.stage == CandidateStage.INTERVIEW_SCHEDULED

    def test_schedule_interview_org_isolation(self, client, db_session):
        candidate, job = _make_candidate(db_session, org_id="org_A")
        fastapi_app.dependency_overrides[get_current_user] = lambda: _fake_user(org_id="org_B")
        try:
            response = client.post(f"/api/v1/candidates/{candidate.id}/interview")
            assert response.status_code == 404
        finally:
            fastapi_app.dependency_overrides.pop(get_current_user, None)

    def test_schedule_interview_survives_email_failure(self, authed_client, db_session, mocker):
        candidate, job = _make_candidate(db_session)
        mocker.patch("app.services.email_service.send_interview_invite", return_value=False)

        response = authed_client.post(f"/api/v1/candidates/{candidate.id}/interview")
        assert response.status_code == 201


class TestListInterviews:
    def test_list_interviews_org_scoped(self, client, db_session):
        candidate_a, _ = _make_candidate(db_session, org_id="org_A")
        candidate_b, _ = _make_candidate(db_session, org_id="org_B")
        db_session.add(Interview(candidate_id=candidate_a.id, status=InterviewStatus.COMPLETED))
        db_session.add(Interview(candidate_id=candidate_b.id, status=InterviewStatus.COMPLETED))
        db_session.commit()

        fastapi_app.dependency_overrides[get_current_user] = lambda: _fake_user(org_id="org_A")
        try:
            response = client.get("/api/v1/interviews")
            assert response.status_code == 200
            body = response.json()
            assert len(body) == 1
            assert body[0]["candidate_id"] == candidate_a.id
        finally:
            fastapi_app.dependency_overrides.pop(get_current_user, None)


class TestInterviewLinkTamperingDefense:
    def test_expired_link_rejected(self, client, db_session):
        from datetime import datetime, timedelta, timezone

        candidate, job = _make_candidate(db_session)
        interview = Interview(
            candidate_id=candidate.id,
            status=InterviewStatus.SCHEDULED,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(interview)
        db_session.commit()

        response = client.get(f"/api/v1/interviews/{interview.id}/public")
        assert response.status_code == 410
        assert response.json()["error_code"] == "interview_link_invalid"

    def test_start_transitions_to_in_progress(self, client, db_session):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.SCHEDULED)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        response = client.post(f"/api/v1/interviews/{interview.id}/start")
        assert response.status_code == 200

        db_session.refresh(interview)
        assert interview.status == InterviewStatus.IN_PROGRESS

    def test_link_cannot_be_started_twice(self, client, db_session):
        """
        Core reuse-defense regression test: a second /start call on the
        same interview_id — whether from a reopened tab, a shared link,
        or a replay attempt — must be rejected.
        """
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.SCHEDULED)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        first = client.post(f"/api/v1/interviews/{interview.id}/start")
        assert first.status_code == 200

        second = client.post(f"/api/v1/interviews/{interview.id}/start")
        assert second.status_code == 410
        assert second.json()["error_code"] == "interview_link_invalid"

    def test_completed_interview_link_rejected(self, client, db_session):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.COMPLETED)
        db_session.add(interview)
        db_session.commit()

        response = client.get(f"/api/v1/interviews/{interview.id}/public")
        assert response.status_code == 410


class TestEscalation:
    def test_violations_below_threshold_do_not_escalate(self, client, db_session):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        for _ in range(2):  # default threshold is 3
            response = client.post(
                f"/api/v1/interviews/{interview.id}/events",
                json={"event_type": "tab_switch", "offset_ms": 1000, "metadata": {}},
            )
            assert response.json()["escalate"] is False

        db_session.refresh(interview)
        assert interview.status == InterviewStatus.IN_PROGRESS

    def test_violations_at_threshold_escalate_and_end_interview(self, client, db_session):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        last_response = None
        for _ in range(3):  # default MAX_INTEGRITY_VIOLATIONS
            last_response = client.post(
                f"/api/v1/interviews/{interview.id}/events",
                json={"event_type": "tab_switch", "offset_ms": 1000, "metadata": {}},
            )

        assert last_response.json()["escalate"] is True

        db_session.refresh(interview)
        assert interview.status == InterviewStatus.ABANDONED
        assert "auto-ended" in interview.ai_report.lower()

    def test_mixed_violation_types_count_toward_same_threshold(self, client, db_session):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        client.post(f"/api/v1/interviews/{interview.id}/events", json={"event_type": "tab_switch", "offset_ms": 1000, "metadata": {}})
        client.post(f"/api/v1/interviews/{interview.id}/events", json={"event_type": "multiple_faces", "offset_ms": 2000, "metadata": {}})
        response = client.post(f"/api/v1/interviews/{interview.id}/events", json={"event_type": "window_blur", "offset_ms": 3000, "metadata": {}})

        assert response.json()["escalate"] is True


class TestVapiSync:
    def test_sync_requires_vapi_call_id(self, authed_client, db_session):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        response = authed_client.post(f"/api/v1/interviews/{interview.id}/sync")
        assert response.status_code == 200
        assert response.json()["synced"] is False
        assert "no vapi_call_id" in response.json()["reason"]

    def test_sync_pulls_and_scores_transcript(self, authed_client, db_session, mocker):
        candidate, job = _make_candidate(db_session)
        interview = Interview(
            candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS, vapi_call_id="vapi-call-sync-1"
        )
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        mocker.patch(
            "app.services.interview_service.fetch_call_from_vapi",
            return_value={"status": "ended", "transcript": "Interviewer: Hi.\nCandidate: Hello."},
        )
        mocker.patch(
            "app.services.claude_service.score_interview_transcript",
            return_value=claude_service.InterviewScoreResult(
                tech_score=70, communication_score=80, overall_score=75, confidence=80,
                summary="Fine.", strengths="", concerns="",
            ),
        )
        mocker.patch("app.services.email_service.send_interview_followup", return_value=True)

        response = authed_client.post(f"/api/v1/interviews/{interview.id}/sync")
        assert response.status_code == 200
        assert response.json()["synced"] is True

        db_session.refresh(interview)
        assert interview.status == InterviewStatus.COMPLETED
        assert interview.overall_score == 75

    def test_sync_skips_if_call_not_ended_yet(self, authed_client, db_session, mocker):
        candidate, job = _make_candidate(db_session)
        interview = Interview(
            candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS, vapi_call_id="vapi-call-sync-2"
        )
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        mocker.patch(
            "app.services.interview_service.fetch_call_from_vapi",
            return_value={"status": "in-progress"},
        )
        response = authed_client.post(f"/api/v1/interviews/{interview.id}/sync")
        assert response.json()["synced"] is False


class TestInterviewPublicView:
    def test_get_public_interview(self, client, db_session):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.SCHEDULED)
        db_session.add(interview)
        db_session.commit()

        response = client.get(f"/api/v1/interviews/{interview.id}/public")
        assert response.status_code == 200
        body = response.json()
        assert body["candidate_name"] == "Jane Doe"
        assert body["job_title"] == "Backend Engineer"
        assert "vapi_assistant_id" in body


class TestVapiWebhook:
    def _headers(self, secret="test-vapi-webhook-secret"):
        return {"x-vapi-secret": secret}

    def test_rejects_missing_secret(self, client):
        response = client.post("/api/v1/webhooks/vapi", json={"message": {"type": "end-of-call-report"}})
        assert response.status_code == 400

    def test_rejects_wrong_secret(self, client):
        response = client.post(
            "/api/v1/webhooks/vapi",
            json={"message": {"type": "end-of-call-report"}},
            headers=self._headers(secret="wrong-secret"),
        )
        assert response.status_code == 400

    def test_ignores_non_report_message_types(self, client):
        response = client.post(
            "/api/v1/webhooks/vapi",
            json={"message": {"type": "status-update"}},
            headers=self._headers(),
        )
        assert response.status_code == 200
        assert response.json()["handled"] is False

    def test_processes_end_of_call_report_and_scores(self, client, db_session, mocker):
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        mocker.patch(
            "app.services.claude_service.score_interview_transcript",
            return_value=claude_service.InterviewScoreResult(
                tech_score=80, communication_score=75, overall_score=78,
                summary="Solid interview.", strengths="Clear communicator.", concerns="",
            ),
        )
        mocker.patch("app.services.email_service.send_interview_followup", return_value=True)

        payload = {
            "message": {
                "type": "end-of-call-report",
                "transcript": "Interviewer: Tell me about yourself.\nCandidate: I'm a backend engineer...",
                "call": {"id": "vapi-call-123", "metadata": {"interview_id": interview.id}},
            }
        }
        response = client.post("/api/v1/webhooks/vapi", json=payload, headers=self._headers())
        assert response.status_code == 200
        assert response.json()["handled"] is True

        db_session.refresh(interview)
        assert interview.status == InterviewStatus.COMPLETED
        assert interview.tech_score == 80
        assert interview.vapi_call_id == "vapi-call-123"

        db_session.refresh(candidate)
        assert candidate.stage == CandidateStage.INTERVIEWED

    def test_duplicate_webhook_is_ignored(self, client, db_session, mocker):
        """
        Regression guard for webhook idempotency — see module docstring
        point 2 in interviews.py. A second delivery of the same report
        must not re-score or re-email.
        """
        candidate, job = _make_candidate(db_session)
        interview = Interview(
            candidate_id=candidate.id,
            status=InterviewStatus.COMPLETED,
            transcript="already processed",
            vapi_call_id="vapi-call-999",
        )
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        score_mock = mocker.patch("app.services.claude_service.score_interview_transcript")
        email_mock = mocker.patch("app.services.email_service.send_interview_followup")

        payload = {
            "message": {
                "type": "end-of-call-report",
                "transcript": "duplicate delivery",
                "call": {"id": "vapi-call-999", "metadata": {"interview_id": interview.id}},
            }
        }
        response = client.post("/api/v1/webhooks/vapi", json=payload, headers=self._headers())
        assert response.status_code == 200
        assert response.json()["handled"] is False
        score_mock.assert_not_called()
        email_mock.assert_not_called()

    def test_missing_interview_id_in_metadata(self, client):
        payload = {
            "message": {
                "type": "end-of-call-report",
                "transcript": "some transcript",
                "call": {"id": "vapi-call-1", "metadata": {}},
            }
        }
        response = client.post("/api/v1/webhooks/vapi", json=payload, headers=self._headers())
        assert response.status_code == 200
        assert response.json()["handled"] is False

    def test_scoring_failure_still_saves_transcript(self, client, db_session, mocker):
        """
        See module docstring point 3 — a Claude failure must not lose
        the transcript itself.
        """
        candidate, job = _make_candidate(db_session)
        interview = Interview(candidate_id=candidate.id, status=InterviewStatus.IN_PROGRESS)
        db_session.add(interview)
        db_session.commit()
        db_session.refresh(interview)

        mocker.patch(
            "app.services.claude_service.score_interview_transcript",
            side_effect=Exception("Claude is down"),
        )
        mocker.patch("app.services.email_service.send_interview_followup", return_value=True)

        payload = {
            "message": {
                "type": "end-of-call-report",
                "transcript": "Interviewer: Hello.\nCandidate: Hi.",
                "call": {"id": "vapi-call-2", "metadata": {"interview_id": interview.id}},
            }
        }
        response = client.post("/api/v1/webhooks/vapi", json=payload, headers=self._headers())
        assert response.status_code == 200

        db_session.refresh(interview)
        assert interview.transcript == "Interviewer: Hello.\nCandidate: Hi."
        assert interview.tech_score is None
        assert interview.status == InterviewStatus.COMPLETED
