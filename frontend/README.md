# RecruiterAI — Frontend

Next.js 14 (App Router) + TypeScript + Tailwind + Clerk.

## Design

Dark theme following your reference mockup's direction: near-black
surfaces (`#080B12` base), indigo/teal accent pair, Inter for UI text,
JetBrains Mono for scores/data. Tokens live in `tailwind.config.ts` —
change them there, not by hardcoding hex values in components.

## What's real vs. placeholder in this build

| Page | Data source |
|---|---|
| Candidates | **Live** — real backend data, KPIs computed from it |
| Jobs | **Live** — real create/list/publish, wired to backend |
| Apply (public) | **Live** — real submission to `/candidates/apply` |
| Analytics — Hiring Funnel, Score Distribution | **Live** — computed from real candidate data |
| Analytics — Interviews per Week | **Sample data**, clearly labeled in the UI. Needs Phase 3 (Vapi) to be real. |
| Interviews | **Empty state**, honest about not being connected yet |
| Settings — AI interviewer prompt | **UI scaffold only** — not yet wired to a backend or to Vapi. This is where you'll manage interview system prompts once Phase 3 ships. |

Nothing here fakes live data as real — anything not backed by your
actual database says so on screen.

## 1. Setup

```bash
cd frontend
npm install
cp .env.example .env.local
```

Fill in `.env.local`:
- `NEXT_PUBLIC_API_URL` — your backend URL (`http://localhost:8000` locally, or your ngrok/Koyeb URL)
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` — from your Clerk dashboard

**Important — Clerk Organizations must be enabled.** This app uses
`org_id` for multi-tenant data isolation (each recruiter org only sees
its own jobs/candidates — enforced server-side in the backend). In your
Clerk dashboard: Configure → Organizations → enable, and make sure users
create/join an organization on sign-up. Without this, `require_org_membership`
on the backend will reject every request with 401.

## 2. Run locally

```bash
npm run dev
```

Visit `http://localhost:3000`. Make sure the backend is running on the
URL set in `NEXT_PUBLIC_API_URL` — this app has no mock-data fallback
mode by design (see note below).

## 3. Build

```bash
npm run build
```

This has been run and passes clean (TypeScript strict mode + ESLint) as
of this delivery — verified before handoff, not just assumed.

## Why no mock/offline mode

Some starter templates ship a "demo mode" with fake data so the UI looks
alive with no backend running. Deliberately didn't do that here — for a
product handling real candidate PII, I'd rather you see a clear
loading/error state than get used to trusting numbers that aren't real.
Every screen either shows live data or explicitly labels what isn't.

## Project structure

```
app/
  (dashboard)/          Recruiter-facing pages, protected by Clerk middleware
    candidates/
    jobs/
    interviews/
    analytics/
    settings/
    layout.tsx           Sidebar + shell
  apply/[jobId]/         Public candidate application page (no auth)
  sign-in/, sign-up/     Clerk auth pages
  layout.tsx              Root layout, fonts, ClerkProvider
components/
  layout/                Sidebar, Topbar
  ui/                    StatCard, Badge — shared primitives
  jobs/                  CreateJobModal
lib/
  api.ts                  Fetch wrapper + typed ApiError
  useApi.ts                Client hook: attaches Clerk token to apiFetch
  utils.ts                 cn() class merge helper
types/
  index.ts                  Types mirroring backend Pydantic schemas
middleware.ts                Clerk route protection (allow-list of public routes)
```

## Security notes

- **`middleware.ts` uses an allow-list, not a block-list**, for public
  routes. Any new recruiter-facing page is protected by default — if you
  add one and it isn't showing a sign-in redirect, check the matcher
  isn't accidentally excluding it, don't "fix" it by adding it to the
  public list.
- **Never read `owner_org_id` or any tenant-scoping value from client
  state.** The frontend never needs to send an org ID — the backend
  derives it from the verified Clerk JWT. If you ever find yourself
  adding an `org_id` field to a request body, stop — that's how the IDOR
  class of bug gets reintroduced.
