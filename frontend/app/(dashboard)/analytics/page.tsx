"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from "recharts";
import { Loader2, AlertTriangle, Info } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { useApi } from "@/lib/useApi";
import { ApiError } from "@/lib/api";
import type { CandidateDetail, CandidateStage } from "@/types";

const FUNNEL_STAGES: { stage: CandidateStage; label: string; color: string }[] = [
  { stage: "applied", label: "Applied", color: "#3B82F6" },
  { stage: "screened", label: "Screened", color: "#8B5CF6" },
  { stage: "shortlisted", label: "Shortlisted", color: "#F59E0B" },
  { stage: "interview_scheduled", label: "Interview Scheduled", color: "#5B5FEF" },
  { stage: "interviewed", label: "Interviewed", color: "#00C9A7" },
  { stage: "hired", label: "Hired", color: "#00C9A7" },
];

// Placeholder shape only — clearly labeled in the UI as sample data.
// Replaces itself with real numbers once Phase 3 (Vapi interviews) is
// wired up and interview records start accumulating.
const SAMPLE_INTERVIEWS_PER_WEEK = [
  { week: "Wk 1", interviews: 4 },
  { week: "Wk 2", interviews: 7 },
  { week: "Wk 3", interviews: 5 },
  { week: "Wk 4", interviews: 9 },
  { week: "Wk 5", interviews: 6 },
];

function SampleDataNote() {
  return (
    <div className="flex items-center gap-1.5 text-[11px] text-amber bg-amber-dim px-2 py-1 rounded-full w-fit mb-3">
      <Info className="w-3 h-3" />
      Sample data — connects live once interviews launch
    </div>
  );
}

export default function AnalyticsPage() {
  const { call } = useApi();
  const [candidates, setCandidates] = useState<CandidateDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    call<CandidateDetail[]>("/candidates")
      .then(setCandidates)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load analytics data."));
  }, [call]);

  const funnelData = useMemo(() => {
    const list = candidates ?? [];
    return FUNNEL_STAGES.map((s) => ({
      label: s.label,
      count: list.filter((c) => c.stage === s.stage).length,
      color: s.color,
    }));
  }, [candidates]);

  const scoreDistribution = useMemo(() => {
    const scored = (candidates ?? []).filter((c) => c.role_match_score !== null);
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
  }, [candidates]);

  return (
    <>
      <Topbar title="Analytics" />
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
            <div className="grid grid-cols-2 gap-4">
              <div className="card p-4">
                <div className="text-sm font-bold text-ink mb-0.5">Hiring Funnel</div>
                <div className="text-xs text-ink-2 mb-4">Live — full pipeline from your candidate data</div>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={funnelData} layout="vertical" margin={{ left: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#232840" horizontal={false} />
                    <XAxis type="number" stroke="#4A4E65" fontSize={11} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" stroke="#8B8FA8" fontSize={11} width={110} />
                    <Tooltip
                      contentStyle={{ background: "#161B2E", border: "1px solid #232840", borderRadius: 8, fontSize: 12 }}
                      cursor={{ fill: "#161B2E" }}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                      {funnelData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="card p-4">
                <div className="text-sm font-bold text-ink mb-0.5">Match Score Distribution</div>
                <div className="text-xs text-ink-2 mb-4">Live — resume-screened candidates only</div>
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

            <div className="card p-4">
              <div className="text-sm font-bold text-ink mb-0.5">Interviews per Week</div>
              <SampleDataNote />
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={SAMPLE_INTERVIEWS_PER_WEEK} margin={{ left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#232840" vertical={false} />
                  <XAxis dataKey="week" stroke="#8B8FA8" fontSize={11} />
                  <YAxis stroke="#4A4E65" fontSize={11} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ background: "#161B2E", border: "1px solid #232840", borderRadius: 8, fontSize: 12 }}
                    cursor={{ fill: "#161B2E" }}
                  />
                  <Bar dataKey="interviews" fill="#00C9A7" radius={[4, 4, 0, 0]} opacity={0.55} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
