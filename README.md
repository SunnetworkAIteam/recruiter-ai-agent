# RecruiterAI

AI-powered recruitment platform: resume screening (Claude) → AI voice
interviews (Vapi) → integrity proctoring → automated pipeline routing →
recruiter dashboard.

## Overview

RecruiterAI automates the full early-stage hiring loop: a candidate
applies to a job, their resume is scored by Claude, shortlisted
candidates receive an interview invite, they complete a real spoken
interview with an AI voice agent (camera on, proctored), the interview
is scored, and the candidate is automatically routed to Shortlisted or
Rejected based on their score — all visible on a live recruiter
dashboard.

## Phase 1 — Backend Foundation

Project structure, environment-driven configuration, structured JSON
logging (with automatic secret redaction), a custom exception hierarchy
mapped to proper HTTP status codes, database models, Clerk
authentication middleware with org-scoped multi-tenancy, Alembic
migrations, and test infrastructure.

## Phase 2 — Resume Scoring + Core Dashboard

- Candidate application endpoint with strict resume validation
  (PDF/DOCX), rate limiting, and Claude-powered scoring with
  prompt-injection defense
- Job posting CRUD, org-scoped candidate listing and filtering
- Supabase Storage integration for resumes
- Next.js dashboard: Candidates page, Jobs page, public application
  page, Analytics page (live hiring funnel and score distribution)
- Automated interview-invite emails on shortlist, sent via Gmail SMTP
  as an interim transport pending verified-domain email (Resend)

## Phase 3 — AI Voice Interviews + Proctoring

- Full Vapi integration: adaptive AI voice interviewer, webhook
  ingestion with signature verification, automatic transcript capture
- Claude-based interview scoring (technical, communication, overall)
- Real-time integrity monitoring: tab-switch detection, window-blur
  detection, face-count monitoring (in-browser, only face counts are
  ever sent to the backend — never frames or video), with automatic
  call-ending after repeated violations and a scoring penalty applied
  per violation
- Automatic candidate routing: after an interview completes, the
  candidate is moved to Shortlisted or Rejected based on a configurable
  score threshold, with recruiters able to override any stage manually
- Explicit, itemized candidate consent (camera, recording, monitoring)
  required before any interview begins
- Per-job candidate pipeline view: stage counts and full candidate
  table (resume match, technical score, communication score, current
  stage) for every job posting

## Phase 4 — Production Hardening

- Verified sending domain for transactional email (migrating off Gmail
  SMTP once DNS access is available), removing the daily send-volume
  cap and provider-side deliverability issues
- Deployment to a stable, persistent hosting environment (replacing
  local tunnel-based development), so webhook URLs no longer change on
  every restart
- Dark/light theme support across the full dashboard
- Rate limiting, load testing, and monitoring for production traffic
- Expanded interview scoring rubrics and structured per-role question
  banks

## Repository Conventions

- Branch strategy: `feature/*` → `dev` → `main`
- No merges to `dev` without tests passing (`pytest` in `backend/`,
  `npm run build` in `frontend/`)
- Every secret goes through environment variables — never commit `.env`
  files or hardcoded keys
- Commit messages: `<scope>: <what changed>`, e.g.
  `interview-scoring: add auto-routing based on score threshold`

See `backend/README.md` and `frontend/README.md` for setup, testing,
and deployment instructions specific to each service.