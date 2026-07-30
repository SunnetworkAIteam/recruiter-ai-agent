"use client";

import { useState } from "react";
import { X, Loader2 } from "lucide-react";
import { useApi } from "@/lib/useApi";
import { ApiError } from "@/lib/api";
import type { Job } from "@/types";

interface CreateJobModalProps {
  onClose: () => void;
  onCreated: (job: Job) => void;
}

export function CreateJobModal({ onClose, onCreated }: CreateJobModalProps) {
  const { call } = useApi();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [requiredSkills, setRequiredSkills] = useState("");
  const [minYears, setMinYears] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const job = await call<Job>("/jobs", {
        method: "POST",
        body: {
          title,
          description,
          required_skills: requiredSkills,
          min_years_experience: minYears,
        },
      });
      onCreated(job);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create job. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-sm font-bold text-ink">New Job Posting</h2>
          <button onClick={onClose} aria-label="Close" className="text-ink-2 hover:text-ink">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">Job Title</label>
            <input
              required
              maxLength={255}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Backend Engineer"
              className="input-field"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">Description</label>
            <textarea
              required
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Role responsibilities and requirements…"
              className="input-field resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">
              Required Skills
              <span className="text-ink-3 font-normal"> — used by the AI to score resumes and generate interview questions</span>
            </label>
            <input
              maxLength={2000}
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
              placeholder="e.g. Python, FastAPI, PostgreSQL, distributed systems"
              className="input-field"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">Minimum Years Experience</label>
            <input
              type="number"
              min={0}
              max={50}
              value={minYears}
              onChange={(e) => setMinYears(Number(e.target.value))}
              className="input-field max-w-[120px]"
            />
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn-primary">
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
              Create Job
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
