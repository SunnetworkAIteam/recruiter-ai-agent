"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart, Bar, CartesianGrid, XAxis, YAxis, ResponsiveContainer, Tooltip } from "recharts";
import { Loader2, AlertTriangle, Download } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { useApi } from "@/lib/useApi";
import { ApiError } from "@/lib/api";
import type { CandidateDetail, Job } from "@/types";

// Cumulative funnel: a candidate who's Rejected still counts toward
// Uploaded/Screened/Shortlisted/Interviewed, since they genuinely passed
// through those steps. Stage is mutually-exclusive on the model, but the
// funnel needs "reached this far or beyond," same fix as the per-job
// pipeline page.
const FUNNEL_STAGES = [
  { key: "uploaded", label: "Uploaded" },
  { key: "screened", label: "Screened" },
  { key: "shortlisted", label: "Email Sent" },
  { key: "interviewed", label: "Interviewed" },
  { key: "rejected", label: "Rejected" },
  { key: "recommended", label: "Selected" },
];

function reachedStage(c: CandidateDetail, key: string): boolean {
  const beyondScreened = new Set(["shortlisted", "interview_scheduled", "interviewed", "rejected", "recommended"]);
  const beyondShortlisted = new Set(["interview_scheduled", "interviewed", "rejected", "recommended"]);
  switch (key) {
    case "uploaded":
      return true;
    case "screened":
      return c.tech_score !== null || c.communication_score !== null || c.role_match_score !== null;
    case "shortlisted":
      return beyondScreened.has(c.stage);
    case "interviewed":
      return beyondShortlisted.has(c.stage) || c.stage === "rejected" || c.stage === "recommended";
    case "rejected":
      return c.stage === "rejected";
    case "recommended":
      return c.stage === "recommended";
    default:
      return false;
  }
}

function downloadCsv(candidates: CandidateDetail[]) {
  const headers = ["Name", "Email", "Job", "Stage", "Resume Match %", "Tech %", "Comm %"];
  const rows = candidates.map((c) => [
    c.full_name,
    c.email,
    c.job_title,
    c.stage,
    c.role_match_score ?? "",
    c.tech_score ?? "",
    c.communication_score ?? "",
  ]);
  const csv = [headers, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `recruiter-ai-report-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AnalyticsPage() {
  const { call } = useApi();
  const [candidates, setCandidates] = useState<CandidateDetail[] | null>(null);
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([call<CandidateDetail[]>("/candidates"), call<Job[]>("/jobs")])
      .then(([c, j]) => {
        setCandidates(c);
        setJobs(j);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load analytics data."));
  }, [call]);

  const filtered = useMemo(() => {
    const list = candidates ?? [];
    return selectedJobId === "all" ? list : list.filter((c) => c.job_id === selectedJobId);
  }, [candidates, selectedJobId]);

  const funnelData = useMemo(() => {
    const total = filtered.length || 1;
    return FUNNEL_STAGES.map((s) => {
      const count = filtered.filter((c) => reachedStage(c, s.key)).length;
      return { ...s, count, pct: Math.round((count / total) * 100) };
    });
  }, [filtered]);

  const scoreDistribution = useMemo(() => {
    const scored = filtered.filter((c) => c.role_match_score !== null);
    const buckets = [
      { label: "0-40%", min: 0, max: 40 },
      { label: "40-60%", min: 40, max: 60 },
      { label: "60-80%", min: 60, max: 80 },
      { label: "80-100%", min: 80, max: 101 },
    ];
    return buckets.map((b) => ({
      label: b.label,
      count: scored.filter((c) => (c.role_match_score ?? 0) >= b.min && (c.role_match_score ?? 0) < b.max).length,
    }));
  }, [filtered]);

  const kpis = useMemo(() => {
    const total = filtered.length;
    const scored = filtered.filter((c) => c.role_match_score !== null);
    const avgMatch = scored.length
      ? Math.round(scored.reduce((sum, c) => sum + (c.role_match_score ?? 0), 0) / scored.length)
      : null;
    const selected = filtered.filter((c) => c.stage === "recommended").length;
    const shortlisted = filtered.filter((c) => reachedStage(c, "shortlisted")).length;
    const conversionRate = total ? Math.round((selected / total) * 100) : 0;
    return { total, avgMatch, shortlisted, selected, conversionRate };
  }, [filtered]);

  const perRole = useMemo(() => {
    if (!jobs) return [];
    return jobs.map((job) => {
      const jobCandidates = (candidates ?? []).filter((c) => c.job_id === job.id);
      const interviewed = jobCandidates.filter((c) => reachedStage(c, "interviewed")).length;
      const selected = jobCandidates.filter((c) => c.stage === "recommended").length;
      const scored = jobCandidates.filter((c) => c.role_match_score !== null);
      const avgMatch = scored.length
        ? Math.round(scored.reduce((sum, c) => sum + (c.role_match_score ?? 0), 0) / scored.length)
        : null;
      const selectionRate = interviewed ? Math.round((selected / interviewed) * 100) : 0;
      return { job, interviewed, selectionRate, avgMatch };
    });
  }, [jobs, candidates]);

  return (
    <>
      <Topbar
        title="Analytics"
        actions={
          candidates && (
            <button onClick={() => downloadCsv(filtered)} className="btn-secondary">
              <Download className="w-4 h-4" />
              Export Report
            </button>
          )
        }
      />
      <main className="flex-1 overflow-y-auto p-6">
        {error && (
          <div className="flex items-center gap-2 text-danger text-sm card p-6 mb-4">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {!error && candidates === null && (
          <div className="flex items-center justify-center gap-2 text-ink-2 text-sm p-12">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading analytics…
          </div>
        )}

        {!error && candidates !== null && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <select
                value={selectedJobId}
                onChange={(e) => setSelectedJobId(e.target.value)}
                className="input-field w-64"
              >
                <option value="all">All Roles</option>
                {(jobs ?? []).map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div className="card p-4">
                <div className="text-xs text-ink-2 mb-1">Total Candidates</div>
                <div className="text-2xl font-extrabold text-ink">{kpis.total}</div>
              </div>
              <div className="card p-4">
                <div className="text-xs text-ink-2 mb-1">Avg Match Score</div>
                <div className="text-2xl font-extrabold text-ink">{kpis.avgMatch !== null ? `${kpis.avgMatch}%` : "—"}</div>
              </div>
              <div className="card p-4">
                <div className="text-xs text-ink-2 mb-1">Shortlisted</div>
                <div className="text-2xl font-extrabold text-ink">{kpis.shortlisted}</div>
              </div>
              <div className="card p-4">
                <div className="text-xs text-ink-2 mb-1">Conversion Rate</div>
                <div className="text-2xl font-extrabold text-ink">{kpis.conversionRate}%</div>
              </div>
            </div>

            <div className="card p-6">
              <div className="text-lg font-bold text-ink mb-4">Recruitment Funnel</div>
              <div className="space-y-4">
                {funnelData.map((s) => (
                  <div key={s.key}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-ink font-medium">{s.label}</span>
                      <span className="text-ink-2">
                        {s.count} ({s.pct}%)
                      </span>
                    </div>
                    <div className="w-full h-2.5 rounded-full bg-surface-2 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-danger via-amber to-teal"
                        style={{ width: `${s.pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="card p-4">
                <div className="text-sm font-bold text-ink mb-4">Performance by Role</div>
                <div className="space-y-3">
                  {perRole.map(({ job, interviewed, selectionRate, avgMatch }) => (
                    <div key={job.id} className="flex items-center justify-between border-t border-border pt-3 first:border-t-0 first:pt-0">
                      <div>
                        <div className="text-sm font-medium text-ink">{job.title}</div>
                        <div className="text-xs text-ink-2">
                          {interviewed} interview{interviewed === 1 ? "" : "s"} · Selection rate: {selectionRate}%
                        </div>
                      </div>
                      <div className="text-lg font-bold text-ink">{avgMatch !== null ? `${avgMatch}%` : "—"}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="card p-4">
                <div className="text-sm font-bold text-ink mb-0.5">Match Score Distribution</div>
                <div className="text-xs text-ink-2 mb-4">Resume-screened candidates only</div>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={scoreDistribution} margin={{ left: -20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#232840" vertical={false} />
                    <XAxis dataKey="label" stroke="#8B8FA8" fontSize={11} />
                    <YAxis stroke="#4A4E65" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: "#161B2E", border: "1px solid #232840", borderRadius: 8, fontSize: 12 }}
                      cursor={{ fill: "#161B2E" }}
                    />
                    <Bar dataKey="count" fill="#5B5FEF" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
}