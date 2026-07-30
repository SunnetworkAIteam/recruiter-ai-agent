"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, AlertTriangle } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { useApi } from "@/lib/useApi";
import type { CandidateDetail, CandidateStage } from "@/types";

type StageCounts = Record<CandidateStage, number>;

const STAGE_LABELS: { key: CandidateStage; label: string; color: string }[] = [
  { key: "applied", label: "Uploaded", color: "bg-danger text-white" },
  { key: "screened", label: "Screened", color: "bg-teal text-white" },
  { key: "shortlisted", label: "Shortlisted", color: "bg-blue-600 text-white" },
  { key: "interview_scheduled", label: "Interviewing", color: "bg-amber text-white" },
  { key: "interviewed", label: "Interviewed", color: "bg-orange-500 text-white" },
  { key: "hired", label: "Hired", color: "bg-surface-3 text-ink-2" },
];

const STAGE_BADGE_STYLES: Record<CandidateStage, string> = {
  applied: "bg-surface-2 text-ink-2",
  screened: "bg-surface-2 text-ink-2",
  shortlisted: "bg-amber/20 text-amber",
  interview_scheduled: "bg-accent/20 text-accent-light",
  interviewed: "bg-accent/20 text-accent-light",
  rejected: "bg-danger/20 text-danger",
  hired: "bg-teal/20 text-teal",
};

export default function JobPipelinePage() {
  const params = useParams<{ jobId: string }>();
  const { call } = useApi();
  const [candidates, setCandidates] = useState<CandidateDetail[] | null>(null);
  const [counts, setCounts] = useState<StageCounts | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      call<CandidateDetail[]>(`/candidates?job_id=${params.jobId}`),
      call<StageCounts>(`/candidates/stage-counts?job_id=${params.jobId}`),
    ])
      .then(([candidateList, stageCounts]) => {
        setCandidates(candidateList);
        setCounts(stageCounts);
      })
      .catch(() => setError("Failed to load this job's candidate pipeline."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.jobId]);

  return (
    <>
      <Topbar title="Candidate Pipeline" />
      <main className="p-6">
        {!candidates && !error && (
          <div className="flex justify-center py-16">
            <Loader2 className="w-6 h-6 text-ink-2 animate-spin" />
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-danger text-sm py-4">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}

        {counts && (
          <div className="card p-6 mb-6">
            <h2 className="text-sm font-bold text-ink mb-4">Candidate Pipeline</h2>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
              {STAGE_LABELS.map(({ key, label, color }) => (
                <div key={key} className="flex flex-col items-center gap-2">
                  <div className={`w-14 h-14 rounded-full flex items-center justify-center font-bold text-lg ${color}`}>
                    {counts[key] ?? 0}
                  </div>
                  <div className="text-xs text-ink-2">{label}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {candidates && candidates.length > 0 && (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-2 text-xs uppercase tracking-wide">
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Resume Match</th>
                  <th className="px-4 py-3 font-medium">Tech</th>
                  <th className="px-4 py-3 font-medium">Comm.</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.id} className="border-t border-border hover:bg-surface-2 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-medium text-ink">{c.full_name}</div>
                      <div className="text-xs text-ink-2">{c.email}</div>
                    </td>
                    <td className="px-4 py-3 text-ink-3">
                      {c.role_match_score !== null ? `${c.role_match_score}%` : "—"}
                    </td>
                    <td className="px-4 py-3 font-medium text-ink">
                      {c.tech_score !== null ? `${c.tech_score}%` : "—"}
                    </td>
                    <td className="px-4 py-3 font-medium text-ink">
                      {c.communication_score !== null ? `${c.communication_score}%` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${STAGE_BADGE_STYLES[c.stage]}`}>
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
    </>
  );
}