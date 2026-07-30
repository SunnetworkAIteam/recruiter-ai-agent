import pytest

from app.core.auth import AuthenticatedUser, get_current_user
from app.main import app as fastapi_app
from app.models.job import Job, JobStatus


def _fake_user(org_id: str = "org_test123"):
    return AuthenticatedUser(user_id="user_abc", org_id=org_id, claims={})


@pytest.fixture
def authed_client(client):
    fastapi_app.dependency_overrides[get_current_user] = lambda: _fake_user()
    yield client
    fastapi_app.dependency_overrides.pop(get_current_user, None)


class TestJobsCRUD:
    def test_create_job_requires_auth(self, client):
        response = client.post(
            "/api/v1/jobs",
            json={"title": "Backend Engineer", "description": "desc", "required_skills": "Python"},
        )
        assert response.status_code == 401

    def test_create_and_list_job(self, authed_client):
        create_resp = authed_client.post(
            "/api/v1/jobs",
            json={
                "title": "Backend Engineer",
                "description": "Build scalable APIs",
                "required_skills": "Python, FastAPI",
                "min_years_experience": 3,
            },
        )
        assert create_resp.status_code == 201
        job_id = create_resp.json()["id"]
        assert create_resp.json()["candidate_count"] == 0

        list_resp = authed_client.get("/api/v1/jobs")
        assert list_resp.status_code == 200
        assert any(j["id"] == job_id for j in list_resp.json())

    def test_rejects_blank_title(self, authed_client):
        response = authed_client.post(
            "/api/v1/jobs",
            json={"title": "   ", "description": "desc"},
        )
        assert response.status_code == 422

    def test_org_isolation_on_job_list(self, client, db_session):
        """
        Org A creates a job; Org B must never see it in their list.
        This is the exact IDOR class of bug flagged in candidates.py —
        testing it here for jobs too, since it's the same risk pattern.
        """
        job_a = Job(
            owner_org_id="org_A",
            title="Org A Job",
            description="desc",
            required_skills="",
            min_years_experience=0,
            status=JobStatus.OPEN,
        )
        db_session.add(job_a)
        db_session.commit()

        fastapi_app.dependency_overrides[get_current_user] = lambda: _fake_user(org_id="org_B")
        try:
            response = client.get("/api/v1/jobs")
            assert response.status_code == 200
            assert all(j["id"] != job_a.id for j in response.json())
        finally:
            fastapi_app.dependency_overrides.pop(get_current_user, None)

    def test_get_public_job_hides_owner_org(self, client, db_session):
        job = Job(
            owner_org_id="org_A",
            title="Public Job",
            description="desc",
            required_skills="Python",
            min_years_experience=2,
            status=JobStatus.OPEN,
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/v1/jobs/{job.id}/public")
        assert response.status_code == 200
        assert "owner_org_id" not in response.json()

    def test_get_public_job_hides_closed_jobs(self, client, db_session):
        job = Job(
            owner_org_id="org_A",
            title="Closed Job",
            description="desc",
            required_skills="",
            min_years_experience=0,
            status=JobStatus.CLOSED,
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/v1/jobs/{job.id}/public")
        assert response.status_code == 404
