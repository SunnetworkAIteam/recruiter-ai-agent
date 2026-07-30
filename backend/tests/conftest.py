"""
Shared test fixtures.

WHY set env vars in conftest before any app import: Settings() validates
required fields at construction time. Tests must never depend on a real
.env file existing (that breaks CI, which has no .env) — every required
var gets a safe dummy value here instead.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("CLERK_SECRET_KEY", "test-clerk-secret")
os.environ.setdefault("CLERK_JWKS_URL", "https://test.clerk.dev/.well-known/jwks.json")
os.environ.setdefault("CLERK_ISSUER", "https://test.clerk.dev")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("VAPI_API_KEY", "test-vapi-key")
os.environ.setdefault("VAPI_WEBHOOK_SECRET", "test-vapi-webhook-secret")
os.environ.setdefault("VAPI_ASSISTANT_ID", "test-assistant-id")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("RESEND_FROM_EMAIL", "test@example.com")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  ensures all models are registered on Base.metadata
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402  (aliased: avoids shadowing the `app` package)


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
