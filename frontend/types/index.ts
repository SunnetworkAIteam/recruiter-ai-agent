// Kept in sync manually with backend/app/schemas/*.py — if you add a
// field on the backend response, add it here too. (A future upgrade:
// generate this file from the backend's OpenAPI schema instead of
// hand-syncing it — flagging that as a nice-to-have, not blocking.)

export type JobStatus = "draft" | "open" | "closed" | "archived";

export interface Job {
  id: string;
  title: string;
  description: string;
  required_skills: string;
  min_years_experience: number;
  status: JobStatus;
  candidate_count: number;
}

export type CandidateStage =
  | "applied"
  | "screened"
  | "shortlisted"
  | "interview_scheduled"
  | "interviewed"
  | "rejected"
  | "hired";

export interface CandidateDetail {
  id: string;
  job_id: string;
  job_title: string;
  full_name: string;
  email: string;
  stage: CandidateStage;
  tech_score: number | null;
  communication_score: number | null;
  role_match_score: number | null;
  applied_at: string;
}

export interface ResumeScore {
  tech_score: number;
  communication_score: number;
  role_match_score: number;
  summary: string;
  strengths: string;
  concerns: string;
}

export type InterviewStatus = "scheduled" | "in_progress" | "completed" | "abandoned" | "failed";

export interface InterviewPublic {
  id: string;
  status: InterviewStatus;
  candidate_name: string;
  job_title: string;
  company_name: string;
  required_skills: string;
  min_years_experience: number;
  vapi_assistant_id: string;
}


export interface InterviewDetail {
  id: string;
  status: string;
  overall_score: number | null;
  tech_score: number | null;
  communication_score: number | null;
  transcript: string | null;
  ai_report: string | null;
  recording_url: string | null;
  candidate_name: string | null;  // ← add
  job_title: string | null;        // ← add
  created_at: string;
}
