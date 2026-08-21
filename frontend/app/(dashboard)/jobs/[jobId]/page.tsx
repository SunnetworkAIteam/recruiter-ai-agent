"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Loader2, AlertTriangle, ArrowLeft } from "lucide-react";
import { useApi } from "@/lib/useApi";
import type { CandidateDetail } from "@/types";

type StageCounts = Record<string, number>;

interface JobDetail {
  id: string;
  title: string;
  description: string;
  required_skills: string;
  min_years_experience: number;
  status: string;
  candidate_count: number;
}

const STAGE_LABELS: { key: string; label: string; color: string }[] = [
  { key: "uploaded", label: "Uploaded", color: "bg-danger text-white" },
  { key: "screened", label: "Screened", color: "bg-teal text-white" },
  { key: "shortlisted", label: "Email Sent", color: "bg-blue-600 text-white" },
  { key: "interview_scheduled", label: "Interviewing", color: "bg-amber text-white" },
  { key: "interviewed", label: "Interviewed", color: "bg-orange-500 text-white" },
  { key: "rejected", label: "Rejected", color: "bg-red-600 text-white" },
  { key: "selected", label: "Shortlisted", color: "bg-green-600 text-white" },

 
];

const STAGE_BADGE_STYLES: Record<string, string> = {
  applied: "bg-surface-2 text-ink-2",
  screened: "bg-surface-2 text-ink-2",
  shortlisted: "bg-amber/20 text-amber",
  interview_scheduled: "bg-accent/20 text-accent-light",
  interviewed: "bg-accent/20 text-accent-light",
  rejected: "bg-danger/20 text-danger",
  recommended: "bg-teal/20 text-teal",

};

export default function JobPipelinePage() {
  const params = useParams<{ jobId: string }>();
  const { call } = useApi();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [candidates, setCandidates] = useState<CandidateDetail[] | null>(null);
  const [counts, setCounts] = useState<StageCounts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      call<JobDetail>(`/jobs/${params.jobId}`),
      call<CandidateDetail[]>(`/candidates?job_id=${params.jobId}`),
      call<StageCounts>(`/candidates/stage-counts?job_id=${params.jobId}`),
    ])
      .then(([jobDetail, candidateList, stageCounts]) => {
        setJob(jobDetail);
        setCandidates(candidateList);
        setCounts(stageCounts);
      })
      .catch(() => setError("Failed to load this job's candidate pipeline."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.jobId]);

  return (
    <main className="flex-1 overflow-y-auto p-6">
      <Link href="/jobs" className="inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink mb-4 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to Jobs
      </Link>

      {!job && !error && (
        <div className="flex justify-center py-16">
          <Loader2 className="w-6 h-6 text-ink-2 animate-spin" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-danger text-sm py-4">
          <AlertTriangle className="w-4 h-4" /> {error}
        </div>
      )}

      {job && (
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-3xl font-extrabold text-ink mb-1">{job.title}</h1>
            <p className="text-sm text-ink-2">
              {job.min_years_experience}+ years &middot; {job.required_skills}
            </p>
          </div>
          <span
            className={`px-3 py-1.5 rounded-full text-xs font-semibold ${
              job.status === "published" ? "bg-teal/20 text-teal" : "bg-surface-3 text-ink-2"
            }`}
          >
            {job.status === "published" ? "Actively Recruiting" : job.status}
          </span>
        </div>
      )}

      {counts && (
        <div className="card p-6 mb-6">
          <h2 className="text-lg font-bold text-ink mb-5">Candidate Pipeline</h2>
          <div className="grid grid-cols-3 md:grid-cols-7 gap-4">
            {STAGE_LABELS.map(({ key, label, color }) => (
              <div key={key} className="flex flex-col items-center gap-2">
                <div className={`w-16 h-16 rounded-full flex items-center justify-center font-bold text-xl ${color}`}>
                  {counts[key] ?? 0}
                </div>
                <div className="text-sm text-ink-2">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {candidates && candidates.length > 0 && (
        <div className="card overflow-hidden">
          <table className="w-full text-base">
            <thead>
              <tr className="text-left text-ink-2 text-sm uppercase tracking-wide">
                <th className="px-4 py-3 font-semibold">Name</th>
                <th className="px-4 py-3 font-semibold">Resume Match</th>
                <th className="px-4 py-3 font-semibold">Tech</th>
                <th className="px-4 py-3 font-semibold">Comm.</th>
                <th className="px-4 py-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.id} className="border-t border-border hover:bg-surface-2 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-semibold text-ink">{c.full_name}</div>
                    <div className="text-sm text-ink-2">{c.email}</div>
                  </td>
                  <td className="px-4 py-3 text-ink-3">
                    {c.role_match_score !== null ? `${c.role_match_score}%` : "—"}
                  </td>
                  <td className="px-4 py-3 font-semibold text-ink">
                    {c.tech_score !== null ? `${c.tech_score}%` : "—"}
                  </td>
                  <td className="px-4 py-3 font-semibold text-ink">
                    {c.communication_score !== null ? `${c.communication_score}%` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2.5 py-1 rounded-full text-sm font-semibold ${STAGE_BADGE_STYLES[c.stage]}`}>
                      {c.stage.replace("_", " ")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {candidates && candidates.length === 0 && (
        <div className="text-ink-2 text-sm py-8 text-center">No candidates have applied to this job yet.</div>
      )}
    </main>
  );
}