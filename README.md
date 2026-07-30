# RecruiterAI

AI-powered recruitment platform: automated resume screening (Claude) →
AI voice interviews (Vapi) → real-time integrity proctoring → automated
pipeline routing → recruiter dashboard.

## What this project does

A recruiter posts a job. Candidates apply and upload a resume, which is
automatically scored by Claude (technical fit, communication signal,
role match). Shortlisted candidates receive an interview invite by
email. The candidate joins a web-based interview room, camera on, and
has a real spoken conversation with an AI voice interviewer (via Vapi).
The interview is recorded, transcribed, scored by Claude, and the
candidate is automatically routed to Shortlisted or Rejected based on
a configurable score threshold — all visible on a live recruiter
dashboard, with recruiters able to override any stage manually.

## Architecture

Candidate → Next.js frontend → FastAPI backend → PostgreSQL (Supabase)
│
├─→ Claude API (resume + interview scoring)
├─→ Vapi (voice interview: STT → LLM → TTS)
├─→ Supabase Storage (resumes, interview recordings)
└─→ Email (interview invites)


## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Clerk (auth) |
| Backend | FastAPI (Python 3.11) |
| Database | PostgreSQL (via Supabase) |
| ORM / Migrations | SQLAlchemy + Alembic |
| AI Scoring | Claude API (resume + interview transcript scoring) |
| Voice Agent | Vapi (web-embedded voice interview, STT → LLM → TTS) |
| Email | Gmail SMTP (interim transport; Resend planned once a sending domain is verified) |
| Auth | Clerk (JWT-based, org-scoped multi-tenancy) |
| Object Storage | Supabase Storage (resumes, interview recordings) |
| Logging | structlog (structured JSON logs, automatic secret redaction) |

## Ports (local development)

| Service | Port | URL |
|---|---|---|
| Frontend (Next.js) | 3000 | http://localhost:3000 |
| Backend (FastAPI/uvicorn) | 8000 | http://localhost:8000 |
| Backend API docs (Swagger) | 8000 | http://localhost:8000/docs |

The frontend calls the backend at whatever `NEXT_PUBLIC_API_URL` is set
to — in local development this is `http://localhost:8000/api/v1`. In
any environment where the frontend and backend run on different hosts
(e.g. production), this must point to the backend's real public URL,
and the backend's CORS `ALLOWED_ORIGINS` must include the frontend's
real public URL.

## Prerequisites

- Python 3.11
- Node.js 18+
- A Supabase project (PostgreSQL database + Storage bucket)
- A Clerk account/application (auth)
- An Anthropic API key (Claude)
- A Vapi account (voice interviews) with an assistant configured
- A Gmail account with an App Password generated

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` / `SUPABASE_KEY` | Supabase project URL and service key (Storage access) |
| `CLERK_SECRET_KEY` | Clerk backend secret key, for verifying auth tokens |
| `ANTHROPIC_API_KEY` | Claude API key |
| `CLAUDE_MODEL` | Claude model identifier used for scoring |
| `VAPI_API_KEY` | Vapi API key |
| `VAPI_API_BASE_URL` | Vapi API base URL (default: `https://api.vapi.ai`) |
| `VAPI_WEBHOOK_SECRET` | Shared secret Vapi sends in the `x-vapi-secret` header on every webhook call — must exactly match the "Server URL Secret" configured in the Vapi assistant's dashboard settings |
| `GMAIL_ADDRESS` | Gmail address used for sending interview-invite emails via SMTP |
| `GMAIL_APP_PASSWORD` | Gmail App Password (not the regular account password) — generate via Google Account → Security → App Passwords |
| `COMPANY_DISPLAY_NAME` | Company name shown in candidate-facing emails and interview prompts |
| `MAX_INTEGRITY_VIOLATIONS` | Number of logged proctoring violations (tab-switch, window-blur, face-detection issues) before an interview is auto-ended |
| `VIOLATION_SCORE_DEDUCTION` | Points deducted from the overall interview score per violation, capped at `MAX_INTEGRITY_VIOLATIONS` |
| `AUTO_SHORTLIST_SCORE_THRESHOLD` | Overall interview score (0–100) at or above which a candidate is automatically moved to Shortlisted; below it, automatically Rejected |
| `ALLOWED_ORIGINS` | Comma-separated list of frontend URLs allowed to call the API (CORS) |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | Full base URL of the backend API, e.g. `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk frontend publishable key |
| `NEXT_PUBLIC_VAPI_PUBLIC_KEY` | Vapi public key, used by the browser to start voice calls |

None of these values are committed to the repository. Copy `.env.example`
in each directory (if present) and fill in real values before running
either service.

## Local Setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt --break-system-packages
alembic upgrade head          # applies all database migrations
uvicorn app.main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000`, with interactive
API docs at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`.

### Exposing the backend for Vapi webhooks (local dev only)

Vapi needs a public URL to send webhook callbacks (interview
completion, transcript delivery). In local development this is done
via a tunnel (e.g. ngrok) pointed at port 8000. The resulting public
URL must be set as the assistant's Server URL in the Vapi dashboard,
with the Server URL Secret matching `VAPI_WEBHOOK_SECRET` above. This
requirement goes away once the backend is deployed to a stable public
URL (see Deployment below).

## Testing

```bash
cd backend
pytest
```

```bash
cd frontend
npm run build   # production build; also runs TypeScript + ESLint checks
```

CI runs dependency checks, secret scanning, type checking, lint, and
build on every push — it verifies the code compiles and passes tests,
but does not verify end-to-end functional behavior (e.g. a real
interview completing successfully), which still requires manual
verification against a real Vapi call.

## Deployment Notes

- **Backend**: containerized via the included `Dockerfile`, which pins
  Python 3.11 explicitly. Currently deployed on Koyeb; any container
  host that supports a standard Dockerfile deploy will work.
- **Frontend**: deployed on Vercel. Note that deploying from a private
  GitHub organization repository requires either a Vercel Pro plan, a
  personal (non-org) repository, or deploying via the Vercel CLI
  directly from a local machine (`vercel --prod`), which bypasses the
  GitHub integration entirely and works on the free tier.
- **Database**: Supabase free tier auto-pauses after 7 days of
  inactivity, which surfaces as unrelated-looking 500 errors on first
  request after a pause — this is expected behavior on the free tier,
  not a bug.
- **Email**: currently Gmail SMTP (capped around 500 sends/day, no
  domain verification required). Migrating to Resend once a verified
  sending domain (DNS access) is available — this removes the send cap
  and improves deliverability (SPF/DKIM/DMARC).
- Whichever environment the backend runs in, its `ALLOWED_ORIGINS` must
  include the frontend's real deployed URL, and the frontend's
  `NEXT_PUBLIC_API_URL` must point to the backend's real deployed URL —
  mismatches here are the most common source of CORS and "everything
  is 404" errors after deployment.

## Current Status

**Phase 1 — Backend Foundation:** complete. Project structure,
environment-driven config, structured logging, custom exception
handling, database models, Clerk auth middleware, Alembic migrations,
test infrastructure.

**Phase 2 — Resume Scoring + Core Dashboard:** complete. Candidate
application endpoint, resume parsing and validation, Claude-powered
resume scoring, job posting CRUD, org-scoped candidate listing and
filtering, live Analytics dashboard, automated interview-invite emails.

**Phase 3 — AI Voice Interviews + Proctoring:** complete. Full Vapi
integration (adaptive voice interviewer, webhook ingestion with
signature verification), Claude-based interview scoring, real-time
integrity monitoring (tab-switch, window-blur, face-count detection)
with automatic call-ending and score penalties on violations, automatic
candidate routing based on score threshold, per-job candidate pipeline
view, explicit itemized candidate consent flow.

**Phase 4 — Production Hardening:** in progress. Verified email
sending domain, stable production deployment (replacing local
tunnel-based webhook delivery), dark/light theme support, rate
limiting and load testing, expanded per-role scoring rubrics.

## Security Notes

- Every data-modifying and data-reading endpoint is scoped to the
  authenticated user's organization via a join on the owning `Job`
  record — this prevents one organization's recruiter from reading or
  modifying another organization's candidate data (IDOR prevention).
- Face-detection proctoring runs entirely client-side; only a face
  *count*, never a video frame or image, is ever sent to the backend.
- Candidate video/audio recording and biometric proctoring require
  explicit, itemized consent (separate checkboxes for recording and
  monitoring) before an interview can begin.
- Webhook requests from Vapi are verified against a shared secret
  header before being processed.
- All secrets are supplied via environment variables; none are
  committed to source control.