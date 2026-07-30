# RecruiterAI

AI-powered recruitment platform: resume screening (Claude) → AI voice
interviews (Vapi) → proctoring → recruiter dashboard.

## Status: Phase 1, 2 & Frontend Batch 1 complete (this delivery)

✅ **Phase 1 — Backend foundation**: project structure, env-driven config,
structured logging, custom exception handling, DB models, Clerk auth
middleware, Alembic migrations, Docker, test infrastructure.

✅ **Phase 2 — Resume scoring pipeline + Jobs/Candidates CRUD**: candidate
application endpoint, resume parsing (PDF/DOCX) with strict validation,
Claude-powered scoring with prompt-injection defense and cost controls,
Supabase Storage integration, job posting CRUD, org-scoped candidate
listing. 28 passing tests including two IDOR-prevention regression tests.

✅ **Frontend Batch 1 — Next.js dashboard**: Clerk auth, dark theme
matching your reference design, Candidates page (live data + KPIs),
Jobs page (live create/list/publish), public candidate application page,
Analytics page (live hiring funnel + score distribution; honestly-labeled
sample data for interview-dependent charts), Interviews page (honest
empty state), Settings page (AI interviewer prompt UI scaffold).
Production build verified clean — TypeScript strict mode + ESLint pass.

⬜ **Phase 3 — Vapi interview integration** (webhook handler, signature
verification, transcript scoring) — next up. Unlocks: Interviews page,
live "Interviews per Week" chart, working Settings save.

⬜ **Phase 4 — Proctoring event ingestion** (tab-switch/face-detection
event logging feeding the Integrity Report). **Blocked on your consent-flow
and data-retention decisions — see below.**

⬜ **Phase 5 — Resend email automation**.

⬜ **Phase 6 — Koyeb deployment + CI**.

See `backend/README.md` and `frontend/README.md` for setup, testing, and
deployment instructions specific to each.

## Why phased, not all at once

Each phase is independently reviewable and testable before the next one
is built on top of it. This also means your 4 interns can each own a
phase without stepping on each other's work — e.g. one intern could take
Phase 3 (Vapi) while another starts on frontend interview-room UI once
the API contract from Phase 3 exists.

## Before Phase 3 (Vapi + proctoring): two decisions only you can make

I did not make these calls for you because they're legal/product
decisions, not engineering ones — but Phase 4 (proctoring) cannot start
without them:

1. **Consent flow copy and mechanism.** The `Candidate.consent_recording`
   and `Candidate.consent_biometric_proctoring` fields exist in the schema
   already, defaulted to `False`. You need an actual UI screen where the
   candidate explicitly opts in — itemized ("we record video," "we detect
   faces and eye movement," "we log tab switches"), not a bundled generic
   checkbox — before they can start an interview. HireVue's 2019 BIPA
   lawsuit (Illinois) is the cautionary example here; this is a real
   exposure, not theoretical.

2. **Data retention policy.** How long do you keep interview video and
   proctoring event logs after a hiring decision is made? Who can request
   deletion, and what's the process? This needs an answer before Phase 4
   ships, because the deletion mechanism needs to be built into the
   schema/storage design, not bolted on after you have real candidate
   data sitting in Supabase.

Bring me answers to both and we'll build the consent gate + retention
job as part of Phase 4.

## Repository conventions

- Branch strategy: `feature/*` → `dev` → `main`, as you specified.
- No PR merges to `dev` without tests passing (`pytest` in `backend/`,
  `npm run build` in `frontend/`).
- Every secret goes through environment variables — grep the codebase
  before any commit if you're unsure (`git diff --staged | grep -i key`
  is a cheap habit that prevents a leaked-secret incident).
- Commit messages: `<scope>: <what changed>`, e.g.
  `resume-scoring: add retry backoff for Claude rate limits`.

