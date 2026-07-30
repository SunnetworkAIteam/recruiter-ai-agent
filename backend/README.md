# RecruiterAI — Backend

FastAPI backend: candidate application intake, Claude-powered resume scoring,
(Vapi interviews / proctoring / email land in Phases 3-5 — see project root README).

## Stack

FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL (Supabase) · Claude API (Anthropic) ·
Clerk (auth) · Supabase Storage · slowapi (rate limiting) · pytest

## 1. Local setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# now fill in .env with your real Supabase / Clerk / Anthropic / Vapi / Resend keys
```

## 2. Database migrations

We use Alembic, not `Base.metadata.create_all()`. **Why this matters:**
`create_all()` only ever adds tables — it cannot alter an existing column,
rename anything, or be rolled back. The moment you need to change a
column type in production, `create_all()` can't help you and you're
hand-writing SQL under pressure. Alembic gives you versioned,
reviewable, revertible schema changes from day one — set this up now,
not after your first painful manual migration.

```bash
# Once DATABASE_URL in .env points at your real Supabase Postgres:
alembic revision --autogenerate -m "initial schema"
# Review the generated file in alembic/versions/ before applying — always
# read what autogenerate produced, it occasionally gets defaults/renames wrong.
alembic upgrade head
```

For every future model change: edit the model → `alembic revision --autogenerate -m "..."` →
review the diff → `alembic upgrade head`. Commit the migration file to git.

## 3. Run locally

```bash
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive API docs (dev only —
disabled automatically when `ENVIRONMENT=production`).

## 4. Testing

```bash
pytest -v                     # run all tests
pytest --cov=app tests/       # with coverage (pip install pytest-cov first)
```

Tests use an in-memory SQLite DB and mock all external calls (Claude,
Supabase Storage) — no real API keys or network calls needed to run the
suite. This is deliberate: tests that depend on live external services
are slow, flaky, and cost money to run in CI.

**Rule for this codebase, including for the interns:** no PR merges to
`dev` without the test suite passing. Add a test for every new endpoint
and every new service function that touches an external API.

## 5. Exposing locally via ngrok (for Vapi webhook testing in Phase 3)

```bash
ngrok http 8000
```
Use the `https://xxxx.ngrok-free.app` URL as your Vapi webhook target
while developing. Note the URL changes every time you restart ngrok
(free tier) — update your Vapi assistant config each time, or upgrade
ngrok for a static domain if this gets annoying during interview testing.

## 6. Deployment (Koyeb)

1. Push to GitHub (`main` branch).
2. In Koyeb: create a new service from your GitHub repo, select
   Dockerfile-based build (uses the `Dockerfile` in this directory).
3. Set every variable from `.env.example` as a Koyeb environment
   variable/secret — **never** commit a real `.env` file.
4. Set `ENVIRONMENT=production`.
5. After first deploy, run `alembic upgrade head` against production
   `DATABASE_URL` (from your local machine or a one-off Koyeb job) before
   the app receives traffic — the app does not auto-migrate on boot,
   deliberately: auto-migrating on every container start is how you get
   two replicas racing to run the same migration simultaneously.

## Project structure

```
app/
  main.py              FastAPI app, middleware, router registration
  config.py            All env-driven settings (Pydantic Settings)
  database.py          SQLAlchemy engine/session
  logging_config.py    Structured JSON logging (structlog)
  models/              SQLAlchemy ORM models (jobs, candidates, resume_scores, interviews)
  schemas/             Pydantic request/response schemas
  services/            External integrations (Claude, Supabase Storage, resume parsing)
  core/
    auth.py            Clerk JWT verification
    exceptions.py       Custom exception hierarchy + global handlers
    rate_limit.py       slowapi limiter instance
  api/routes/           FastAPI routers
alembic/                DB migrations
tests/                  pytest suite (mirrors app/ structure)
```

## Security notes (read before extending this)

- **Every DB query that returns tenant data must filter by `owner_org_id`.**
  See `candidates.py::get_resume_score` for the pattern. Forgetting this
  is an IDOR vulnerability — one recruiter org reading another's data.
- **Never log secrets.** `logging_config.py` redacts known secret field
  names automatically, but don't rely on that as your only line of
  defense — don't pass raw request headers or full config objects into
  log calls.
- **The `/candidates/apply` endpoint is intentionally unauthenticated**
  (candidates don't have accounts) but is rate-limited and strictly
  validates file type/size. Any new unauthenticated endpoint needs the
  same treatment — don't add one without rate limiting.
- **Consent flags (`consent_recording`, `consent_biometric_proctoring`)
  must be set via an explicit candidate action**, never defaulted true.
  This is a legal requirement (BIPA and similar biometric privacy laws),
  not a style preference — see the project-level README for the full note.

## What's NOT here yet (see project root README for phased plan)

Vapi interview integration, proctoring event ingestion, Resend email
automation, and the Next.js frontend are Phases 3–6 and come next.
