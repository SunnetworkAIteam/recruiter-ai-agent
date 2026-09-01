"""
Centralized application configuration.

WHY THIS EXISTS:
Every secret and environment-dependent value lives here, sourced from
environment variables. Nothing is ever hardcoded. This is the single
place you (or an intern) look to know what env vars the app needs —
and Pydantic validates them at startup, so a missing/malformed secret
fails FAST at boot, not silently at 2am when a candidate is mid-interview.

Fail-fast on config errors is a deliberate design choice: it's far
cheaper to crash on `uvicorn` startup with a clear message than to
crash 40 minutes into production traffic.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    APP_NAME: str = "RecruiterAI"
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # --- CORS ---
    # Comma-separated list in the env var, e.g. "https://app.recruiterai.com,https://staging.recruiterai.com"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # WHY this is separate from ALLOWED_ORIGINS: that setting is a
    # comma-separated CORS allow-list, and interview links were
    # previously built from its FIRST entry — which silently broke the
    # moment localhost:3000 was kept in the list alongside a real public
    # ngrok URL for CORS purposes. Interview links need their own
    # explicit, single source of truth, independent of how many origins
    # CORS happens to allow.
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Database (Supabase Postgres) ---
    DATABASE_URL: str = Field(..., description="Supabase Postgres connection string")

    # --- Supabase Storage ---
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_SERVICE_ROLE_KEY: str = Field(
        ..., description="Supabase service role key — server-side ONLY, never exposed to frontend"
    )
    SUPABASE_STORAGE_BUCKET_RESUMES: str = "resumes"
    SUPABASE_STORAGE_BUCKET_SELFIES: str = "selfies"
    SUPABASE_STORAGE_BUCKET_RECORDINGS: str = "interview-recordings"

    # --- Clerk (Auth) ---
    CLERK_SECRET_KEY: str = Field(..., description="Clerk backend secret key")
    CLERK_JWKS_URL: str = Field(..., description="Clerk JWKS endpoint for verifying session tokens")
    CLERK_ISSUER: str = Field(..., description="Expected `iss` claim in Clerk JWTs")

    # --- Anthropic (Claude) ---
    ANTHROPIC_API_KEY: str = Field(..., description="Claude API key")
    CLAUDE_MODEL: str = "claude-haiku-4-5"
    CLAUDE_MAX_TOKENS: int = 2048
    # Hard ceiling on Claude spend per resume-scoring call, enforced in code, not just monitored after the fact.
    CLAUDE_MAX_RETRIES: int = 3

    # --- Vapi ---
    VAPI_API_KEY: str = Field(..., description="Vapi private API key (server-side)")
    VAPI_WEBHOOK_SECRET: str = Field(
        ..., description="Shared secret used to verify Vapi webhook signatures"
    )
    VAPI_ASSISTANT_ID: str = Field(..., description="Default Vapi assistant ID for interviews")
    # HireVue defaults to 3 days and their own forums show recruiters
    # constantly re-sending links because candidates miss that window —
    # 5 days is a more forgiving default. Configurable, not hardcoded,
    # since this is a product/ops decision that may change.
    INTERVIEW_LINK_EXPIRY_DAYS: int = 12

    REMINDER_INTERVAL_DAYS: int = 3

    # Automatically send an interview invite when a candidate's resume
    # role_match_score meets or exceeds this threshold — no recruiter
    # click needed. Set to 0 to disable and require manual review of
    # every candidate before an invite goes out. This is a real policy
    # choice with real consequences (see decision_log entries tagged
    # "auto_invite_threshold" for the audit trail of every automatic
    # decision this setting causes) — not a default to leave unexamined.
    AUTO_INVITE_SCORE_THRESHOLD: int = 20

    # Real display name shown to candidates (emails, interview room) —
    # NOT the Clerk org_id. Using the raw org_id here was a real bug:
    # candidates were literally seeing "org_3GaBKth..." in their invite
    # emails. Single-org MVP, so a config value is the right fix now;
    # a multi-org SaaS would look this up from Clerk's Organizations API
    # instead — flagged as future work, not needed yet.
    COMPANY_DISPLAY_NAME: str = "AmeriSource"

    # Auto-escalation: after this many logged integrity violations
    # (tab_switch, window_blur, multiple_faces, no_face_detected combined)
    # in a single interview, the call is auto-ended and the interview is
    # flagged for recruiter review. This does NOT delete or silently
    # reject the candidate — a human still makes the hiring call — but
    # it does stop the interview immediately rather than let it continue.


    # Only counts genuine integrity violations (tab_switch, window_blur,
    # multiple_faces) toward auto-escalation. no_face_detected is tracked
    # separately with its own, much higher threshold — camera/lighting
    # hiccups shouldn't end an interview the same way deliberately
    # switching tabs does.
    MAX_INTEGRITY_VIOLATIONS: int = 5
    MAX_NO_FACE_VIOLATIONS: int = 3

    
    # Points deducted from overall_score per logged violation, applied
    # when the transcript is scored. Configurable, not hardcoded — you
    # may want a harsher or lighter penalty later without a code change.
    VIOLATION_SCORE_DEDUCTION: int = 2
    AUTO_SHORTLIST_SCORE_THRESHOLD: int = 45

    VAPI_API_BASE_URL: str = "https://api.vapi.ai"

    # How often the background job checks Vapi for completed interviews
    # that haven't synced yet. This is what replaces manually clicking
    # "Sync from Vapi" — it now runs automatically in the background.
    BACKGROUND_SYNC_INTERVAL_SECONDS: int = 10

    # Any interview stuck at IN_PROGRESS with no vapi_call_id for longer
    # than this never actually connected to Vapi (denied mic permission,
    # closed tab, connection failure, etc.) and will never self-resolve —
    # nothing else revisits it. Marking it ABANDONED after this window is
    # a factual statement (it never connected), not a judgment call.
    STUCK_IN_PROGRESS_THRESHOLD_MINUTES: int = 30

    # --- Resend (Email) ---
    # Optional now — email currently sends via Gmail SMTP (see
    # GMAIL_ADDRESS/GMAIL_APP_PASSWORD below). These stay here, made
    # optional rather than deleted, so switching back to Resend later
    # (once the domain is DNS-verified) is a config change, not a code
    # change — just re-add real values and swap email_service.py back.
    RESEND_API_KEY: str | None = Field(default=None, description="Resend API key (optional — unused while on Gmail SMTP)")
    RESEND_FROM_EMAIL: str | None = Field(default=None, description="Verified sender email (optional — unused while on Gmail SMTP)")
    GMAIL_ADDRESS: str = Field(..., description="Gmail address used for sending via SMTP (temporary, until Resend domain is verified)")
    GMAIL_APP_PASSWORD: str = Field(..., description="Gmail App Password — NOT your regular Gmail password")

    # --- Rate limiting ---
    RATE_LIMIT_RESUME_UPLOAD: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        return v.lower()

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings singleton. lru_cache ensures env vars are parsed once,
    not re-read from disk/env on every request (this matters under load).
    """
    return Settings()
