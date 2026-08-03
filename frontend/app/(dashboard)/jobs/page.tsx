"use client";

import { useEffect, useState } from "react";
import { Plus, Loader2, AlertTriangle, Copy, Check, Users, Trash2 } from "lucide-react";
import Link from "next/link";
import { Topbar } from "@/components/layout/Topbar";
import { JobStatusBadge } from "@/components/ui/Badge";
import { CreateJobModal } from "@/components/jobs/CreateJobModal";
import { useApi } from "@/lib/useApi";
import { ApiError } from "@/lib/api";
import type { Job } from "@/types";

function ApplyLinkButton({ jobId }: { jobId: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    const url = `${window.location.origin}/apply/${jobId}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 text-xs text-ink-2 hover:text-accent-light transition-colors"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-teal" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "Copied" : "Copy application link"}
    </button>
  );
}

export default function JobsPage() {
  const { call } = useApi();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [publishingId, setPublishingId] = useState<string | null>(null);

  function refresh() {
    setError(null);
    call<Job[]>("/jobs")
      .then(setJobs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load jobs."));
  }

  useEffect(refresh, [call]);

  async function handlePublish(jobId: string) {
    setPublishingId(jobId);
    try {
      const updated = await call<Job>(`/jobs/${jobId}`, {
        method: "PATCH",
        body: { status: "open" },
      });
      setJobs((prev) => prev?.map((j) => (j.id === jobId ? updated : j)) ?? prev);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to publish job.");
    } finally {
      setPublishingId(null);
    }
  }

  async function handleDeleteJob(jobId: string, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Delete this job and all its candidates permanently? This cannot be undone.")) return;
    try {
      await call(`/jobs/${jobId}`, { method: "DELETE" });
      refresh();
    } catch {
      alert("Failed to delete job.");
    }
  }

  return (
    <>
      <Topbar
        title="Jobs"
        actions={
          <button onClick={() => setModalOpen(true)} className="btn-primary">
            <Plus className="w-4 h-4" />
            New Job
          </button>
        }
      />
      <main className="flex-1 overflow-y-auto p-6">
        {error && (
          <div className="flex items-center gap-2 text-danger text-sm card p-6 mb-4">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        )}

        {!error && jobs === null && (
          <div className="flex items-center justify-center gap-2 text-ink-2 text-sm p-12">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading jobs…
          </div>
        )}

        {!error && jobs !== null && jobs.length === 0 && (
          <div className="card text-center text-ink-2 text-sm p-12">
            No job postings yet.{" "}
            <button onClick={() => setModalOpen(true)} className="text-accent-light hover:underline">
              Create your first one
            </button>
          </div>
        )}

        {!error && jobs !== null && jobs.length > 0 && (
          <div className="grid grid-cols-2 gap-4">
            {jobs.map((job) => (
              <Link key={job.id} href={`/jobs/${job.id}`} className="card p-4 block hover:border-border-2 transition-colors">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-sm font-bold text-ink">{job.title}</h3>
                  <div className="flex items-center gap-2">
                    <JobStatusBadge status={job.status} />
                    <button
                      onClick={(e) => handleDeleteJob(job.id, e)}
                      aria-label={`Delete ${job.title}`}
                      className="text-ink-3 hover:text-danger transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                <p className="text-xs text-ink-2 line-clamp-2 mb-3">{job.description}</p>
                {job.required_skills && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {job.required_skills
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean)
                      .slice(0, 6)
                      .map((skill) => (
                        <span key={skill} className="text-[11px] px-2 py-0.5 rounded-full bg-surface-3 text-ink-2">
                          {skill}
                        </span>
                      ))}
                  </div>
                )}
                <div className="flex items-center justify-between pt-3 border-t border-border">
                  <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
                    <Users className="w-3.5 h-3.5" />
                    {job.candidate_count} candidate{job.candidate_count === 1 ? "" : "s"}
                  </span>
                  {job.status === "draft" ? (
                    <button
                      onClick={() => handlePublish(job.id)}
                      disabled={publishingId === job.id}
                      className="inline-flex items-center gap-1.5 text-xs text-accent-light hover:underline disabled:opacity-50"
                    >
                      {publishingId === job.id && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      Publish to accept applications
                    </button>
                  ) : (
                    <ApplyLinkButton jobId={job.id} />
                  )}
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>

      {modalOpen && (
        <CreateJobModal
          onClose={() => setModalOpen(false)}
          onCreated={(job) => {
            setJobs((prev) => (prev ? [job, ...prev] : [job]));
            setModalOpen(false);
          }}
        />
      )}
    </>
  );
}
