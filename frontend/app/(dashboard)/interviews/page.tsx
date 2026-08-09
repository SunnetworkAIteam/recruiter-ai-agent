"use client";

import { useEffect, useState } from "react";
import { Mic, Loader2, AlertTriangle, X, RefreshCw, Play } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { useApi } from "@/lib/useApi";
import { ApiError } from "@/lib/api";
import type { InterviewDetail } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  in_progress: "In Progress",
  completed: "Completed",
  abandoned: "Abandoned",
  failed: "Failed",
};

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-info-dim text-info",
  in_progress: "bg-amber-dim text-amber",
  completed: "bg-teal-dim text-teal",
  abandoned: "bg-surface-3 text-ink-2",
  failed: "bg-danger-dim text-danger",
};

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="font-mono text-ink-2">—</span>;
  const color =
    score >= 60 ? "text-teal" : score >= 50 ? "text-amber" : "text-danger";
  return (
    <span className={`font-mono font-semibold ${color}`}>{score}%</span>
  );
}

export default function InterviewsPage() {
  const { call } = useApi();
  const [interviews, setInterviews] = useState<InterviewDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<InterviewDetail | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  function refresh() {
    call<InterviewDetail[]>("/interviews")
      .then(setInterviews)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load interviews.")
      );
  }

  async function handleSync(interviewId: string) {
    setSyncingId(interviewId);
    setSyncMessage(null);
    try {
      const result = await call<{ synced: boolean; reason?: string }>(
        `/interviews/${interviewId}/sync`,
        { method: "POST" }
      );
      if (result.synced) {
        setSyncMessage(" Synced — transcript and scores pulled from Vapi.");
        refresh();
      } else {
        setSyncMessage(result.reason ?? "Nothing to sync yet.");
      }
    } catch (err) {
      setSyncMessage(err instanceof ApiError ? err.message : "Sync failed.");
    } finally {
      setSyncingId(null);
    }
  }

  useEffect(refresh, [call]);

  return (
    <>
      <Topbar title="Interviews" />
      <main className="flex-1 overflow-y-auto p-6">
        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 text-danger text-sm card p-6 mb-4">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Loading */}
        {!error && interviews === null && (
          <div className="flex items-center justify-center gap-2 text-ink-2 text-sm p-12">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading interviews…
          </div>
        )}

        {/* Empty */}
        {!error && interviews !== null && interviews.length === 0 && (
          <div className="card p-12 text-center max-w-lg mx-auto mt-12">
            <div className="w-12 h-12 rounded-xl bg-accent-dim flex items-center justify-center mx-auto mb-4">
              <Mic className="w-5 h-5 text-accent-light" />
            </div>
            <h2 className="text-base font-bold text-ink mb-1.5">No interviews yet</h2>
            <p className="text-sm text-ink-2">
              Send an interview from the Candidates page to get started — completed interviews
              with transcripts and AI scoring will show up here.
            </p>
          </div>
        )}

        {/* Table */}
        {!error && interviews !== null && interviews.length > 0 && (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-2 text-xs uppercase tracking-wide border-b border-border">
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Candidate</th>
                  <th className="px-4 py-3 font-medium">Role</th>
                  <th className="px-4 py-3 font-medium">Overall</th>
                  <th className="px-4 py-3 font-medium">Tech</th>
                  <th className="px-4 py-3 font-medium">Comm.</th>
                  <th className="px-4 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((iv) => (
                  <tr
                    key={iv.id}
                    className="border-t border-border hover:bg-surface-2 transition-colors cursor-pointer"
                    onClick={() => iv.transcript && setSelected(iv)}
                  >
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_STYLES[iv.status]}`}
                      >
                        {STATUS_LABELS[iv.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-ink font-medium">
                      {iv.candidate_name ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-ink-2">
                      {iv.job_title ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge score={iv.overall_score}  />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge score={iv.tech_score}  />
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge score={iv.communication_score}  />
                    </td>
                    <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                      {iv.transcript ? (
                        <button
                          onClick={() => setSelected(iv)}
                          className="inline-flex items-center gap-1 text-xs text-accent-light hover:underline"
                        >
                          <Play className="w-3 h-3" />
                          View Report
                        </button>
                      ) : (
                        <button
                          onClick={() => handleSync(iv.id)}
                          disabled={syncingId === iv.id}
                          className="inline-flex items-center gap-1.5 text-xs text-accent-light hover:underline disabled:opacity-50"
                        >
                          {syncingId === iv.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <RefreshCw className="w-3.5 h-3.5" />
                          )}
                          Sync from Vapi
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Sync message */}
        {syncMessage && (
          <div className="text-xs text-ink-2 bg-surface-2 border border-border rounded-lg px-3 py-2 mt-3">
            {syncMessage}
          </div>
        )}
      </main>

      {/* Report slide-over */}
      {selected && (
        <div className="fixed inset-0 bg-black/60 flex justify-end z-50">
          <div className="w-full max-w-xl h-full bg-surface border-l border-border overflow-y-auto flex flex-col">

            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-border sticky top-0 bg-surface z-10">
              <div>
                <h2 className="text-sm font-bold text-ink">Interview Report</h2>
                <p className="text-xs text-ink-2 mt-0.5">
                  {selected.candidate_name ?? ""} — {selected.job_title ?? ""}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                aria-label="Close"
                className="text-ink-2 hover:text-ink"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-5 flex-1">

              {/* Scores */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Overall", value: selected.overall_score },
                  { label: "Technical", value: selected.tech_score },
                  { label: "Communication", value: selected.communication_score },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-surface-2 rounded-xl p-3 text-center border border-border">
                    <div className="text-xs text-ink-2 mb-1">{label}</div>
                    <div
                      className={`text-xl font-bold font-mono ${
                        value === null
                          ? "text-ink-2"
                          : value >= 80
                          ? "text-teal"
                          : value >= 60
                          ? "text-amber"
                          : "text-danger"
                      }`}
                    >
                      {value !== null ? `${value}%` : "—"}
                    </div>
                  </div>
                ))}
              </div>

              {/* Recording */}
              {selected.recording_url && (
                <div>
                  <div className="text-xs font-semibold text-ink-2 uppercase tracking-wide mb-2">
                    Recording
                  </div>
                  <audio
                    controls
                    src={selected.recording_url}
                    className="w-full rounded-lg"
                  />
                </div>
              )}

              {/* AI Summary */}
              {selected.ai_report && (
                <div>
                  <div className="text-xs font-semibold text-ink-2 uppercase tracking-wide mb-2">
                    AI Summary
                  </div>
                  <p className="text-sm text-ink whitespace-pre-line leading-relaxed bg-surface-2 rounded-xl p-3 border border-border">
                    {selected.ai_report}
                  </p>
                </div>
              )}

              {selected.identity_mismatch_flagged && (
                <div className="flex items-center gap-2 bg-danger-dim text-danger text-xs px-3 py-2 rounded-lg mb-3">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  Identity check flagged: the face detected at interview start didn&apos;t clearly match the
                  application selfie. Review the recording before making a decision.
                </div>
              )}
              
              {/* Transcript */}
              {selected.transcript && (
                <div>
                  <div className="text-xs font-semibold text-ink-2 uppercase tracking-wide mb-2">
                    Transcript
                  </div>
                  <div className="bg-surface-2 rounded-xl p-3 border border-border max-h-80 overflow-y-auto">
                    <p className="text-xs text-ink-2 whitespace-pre-line font-mono leading-relaxed">
                      {selected.transcript}
                    </p>
                  </div>
                </div>
              )}

              {/* Sync button inside report */}
              {!selected.transcript && (
                <button
                  onClick={() => handleSync(selected.id)}
                  disabled={syncingId === selected.id}
                  className="w-full flex items-center justify-center gap-2 text-sm text-accent-light border border-accent-light rounded-xl py-2.5 hover:bg-accent-dim transition-colors disabled:opacity-50"
                >
                  {syncingId === selected.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Sync from Vapi
                </button>
              )}

            </div>
          </div>
        </div>
      )}
    </>
  );
}
