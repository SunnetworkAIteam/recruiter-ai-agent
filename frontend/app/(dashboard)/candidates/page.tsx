"use client";

import { useEffect, useMemo, useState } from "react";
import { Users, Star, CheckCircle2, Target, Loader2, AlertTriangle, Send, Trash2, Download } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { StatCard } from "@/components/ui/StatCard";
import { StageBadge } from "@/components/ui/Badge";
import { useApi } from "@/lib/useApi";
import { ApiError } from "@/lib/api";
import type { CandidateDetail, CandidateStage } from "@/types";

const STAGE_FILTERS: { value: CandidateStage | "all"; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "screened", label: "Screened" },
  { value: "shortlisted", label: "Shortlisted" },
  { value: "interview_scheduled", label: "Interview Scheduled" },
  { value: "interviewed", label: "Interviewed" },
  { value: "hired", label: "Hired" },
  { value: "rejected", label: "Rejected" },
];

export default function CandidatesPage() {
  const { call } = useApi();
  const [candidates, setCandidates] = useState<CandidateDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState<CandidateStage | "all">("all");
  const [schedulingId, setSchedulingId] = useState<string | null>(null);
  const [scheduledIds, setScheduledIds] = useState<Set<string>>(new Set());
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    call<CandidateDetail[]>("/candidates")
      .then((data) => {
        if (!cancelled) setCandidates(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load candidates.");
      });
    return () => {
      cancelled = true;
    };
  }, [call]);

  const filtered = useMemo(() => {
    if (!candidates) return [];
    return candidates.filter((c) => {
      const matchesSearch =
        !search ||
        c.full_name.toLowerCase().includes(search.toLowerCase()) ||
        c.email.toLowerCase().includes(search.toLowerCase());
      const matchesStage = stageFilter === "all" || c.stage === stageFilter;
      return matchesSearch && matchesStage;
    });
  }, [candidates, search, stageFilter]);

  const kpis = useMemo(() => {
    const list = candidates ?? [];
    const shortlisted = list.filter((c) => c.stage === "shortlisted").length;
    const scored = list.filter((c) => c.role_match_score !== null);
    const avgMatch = scored.length
      ? Math.round(scored.reduce((sum, c) => sum + (c.role_match_score ?? 0), 0) / scored.length)
      : 0;
    const strong = scored.filter((c) => (c.role_match_score ?? 0) >= 80).length;
    return { total: list.length, shortlisted, avgMatch, strong };
  }, [candidates]);

  async function handleScheduleInterview(candidateId: string) {
    setSchedulingId(candidateId);
    try {
      await call(`/candidates/${candidateId}/interview`, { method: "POST" });
      setScheduledIds((prev) => new Set(prev).add(candidateId));
      setCandidates(
        (prev) => prev?.map((c) => (c.id === candidateId ? { ...c, stage: "interview_scheduled" } : c)) ?? prev
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to schedule interview.");
    } finally {
      setSchedulingId(null);
    }
  }

  async function handleDownloadResume(candidateId: string) {
    try {
      const result = await call<{ url: string }>(`/candidates/${candidateId}/resume-download`);
      window.open(result.url, "_blank");
    } catch {
      alert("Failed to get resume download link.");
    }
  }

  async function handleDeleteCandidate(candidateId: string) {
    setDeletingId(candidateId);
    try {
      await call(`/candidates/${candidateId}`, { method: "DELETE" });
      setCandidates((prev) => prev?.filter((c) => c.id !== candidateId) ?? prev);
      setConfirmDeleteId(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to delete candidate.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <>
      <Topbar title="Candidates" />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Total Candidates"
            value={kpis.total}
            icon={Users}
            accentClassName="border-t-info"
            accentBgClassName="bg-info-dim"
            accentTextClassName="text-info"
          />
          <StatCard
            label="Shortlisted"
            value={kpis.shortlisted}
            icon={Star}
            accentClassName="border-t-amber"
            accentBgClassName="bg-amber-dim"
            accentTextClassName="text-amber"
          />
          <StatCard
            label="Strong Matches (80%+)"
            value={kpis.strong}
            icon={CheckCircle2}
            accentClassName="border-t-purple"
            accentBgClassName="bg-purple-dim"
            accentTextClassName="text-purple"
          />
          <StatCard
            label="Avg Match Score"
            value={`${kpis.avgMatch}%`}
            icon={Target}
            accentClassName="border-t-teal"
            accentBgClassName="bg-teal-dim"
            accentTextClassName="text-teal"
          />
        </div>

        <div className="card">
          <div className="flex items-center gap-3 p-4 border-b border-border">
            <input
              placeholder="Search candidates…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field max-w-xs"
            />
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value as CandidateStage | "all")}
              className="input-field max-w-[200px]"
            >
              {STAGE_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-danger text-sm p-6">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          {!error && candidates === null && (
            <div className="flex items-center justify-center gap-2 text-ink-2 text-sm p-12">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading candidates…
            </div>
          )}

          {!error && candidates !== null && filtered.length === 0 && (
            <div className="text-center text-ink-2 text-sm p-12">
              {candidates.length === 0
                ? "No applications yet. Share a job's application link to start receiving candidates."
                : "No candidates match your filters."}
            </div>
          )}

          {!error && filtered.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-2 text-xs uppercase tracking-wide">
                  <th className="px-4 py-3 font-medium">Candidate</th>
                  <th className="px-4 py-3 font-medium">Job</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Resume Score</th>
                  <th className="px-4 py-3 font-medium">Resume</th>
                  <th className="px-4 py-3 font-medium"></th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id} className="border-t border-border hover:bg-surface-2 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-medium text-ink">{c.full_name}</div>
                      <div className="text-xs text-ink-2">{c.email}</div>
                    </td>
                    <td className="px-4 py-3 text-ink-2">{c.job_title}</td>
                    <td className="px-4 py-3">
                      <StageBadge stage={c.stage} />
                    </td>

                    <td className="px-4 py-3 font-mono font-semibold text-ink">
                      {c.role_match_score !== null ? `${c.role_match_score}%` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleDownloadResume(c.id)}
                        className="inline-flex items-center gap-1.5 text-xs text-accent-light hover:underline"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download
                      </button>
                    </td>

                    <td className="px-4 py-3">
                      {(c.stage === "applied" || c.stage === "screened" || c.stage === "shortlisted") && !c.has_interview ? (
                        <button
                          onClick={() => handleScheduleInterview(c.id)}
                          disabled={schedulingId === c.id}
                          className="inline-flex items-center gap-1.5 text-xs text-accent-light hover:underline disabled:opacity-50"
                        >
                          {schedulingId === c.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Send className="w-3.5 h-3.5" />
                          )}
                          Send Interview
                        </button>
                      ) : scheduledIds.has(c.id) ? (
                        <span className="text-xs text-teal">Sent ✓</span>
                      ) : null}
                      <button
                        onClick={() => setConfirmDeleteId(c.id)}
                        aria-label={`Delete ${c.full_name}`}
                        className="ml-3 text-ink-3 hover:text-danger transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {confirmDeleteId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-sm p-5">
            <h2 className="text-sm font-bold text-ink mb-1.5">Delete this candidate?</h2>
            <p className="text-xs text-ink-2 mb-4">
              This permanently removes the candidate, their resume score, and any interview data. This
              can&apos;t be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setConfirmDeleteId(null)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => handleDeleteCandidate(confirmDeleteId)}
                disabled={deletingId === confirmDeleteId}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-danger text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {deletingId === confirmDeleteId && <Loader2 className="w-4 h-4 animate-spin" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
