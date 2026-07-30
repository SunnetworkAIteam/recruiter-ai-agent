"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Upload, Loader2, CheckCircle2, AlertTriangle } from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";

interface PublicJob {
  id: string;
  title: string;
  description: string;
  required_skills: string;
  min_years_experience: number;
}

export default function ApplyPage() {
  const params = useParams<{ jobId: string }>();
  const [job, setJob] = useState<PublicJob | null | "not_found">(null);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    apiFetch<PublicJob>(`/jobs/${params.jobId}/public`)
      .then(setJob)
      .catch(() => setJob("not_found"));
  }, [params.jobId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!resumeFile) {
      setError("Please attach your resume (PDF or DOCX).");
      return;
    }
    setSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.append("job_id", params.jobId);
    formData.append("full_name", fullName);
    formData.append("email", email);
    if (phone) formData.append("phone", phone);
    formData.append("resume", resumeFile);

    try {
      await apiFetch("/candidates/apply", { method: "POST", body: formData });
      setSubmitted(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong submitting your application. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (job === null) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <Loader2 className="w-6 h-6 text-ink-2 animate-spin" />
      </div>
    );
  }

  if (job === "not_found") {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center px-4">
        <div className="card p-8 max-w-md text-center">
          <AlertTriangle className="w-8 h-8 text-amber mx-auto mb-3" />
          <h1 className="text-lg font-bold text-ink mb-1">This job posting isn&apos;t available</h1>
          <p className="text-sm text-ink-2">
            It may have closed, or the link may be incorrect. Check with the recruiter who shared it with you.
          </p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center px-4">
        <div className="card p-8 max-w-md text-center">
          <CheckCircle2 className="w-8 h-8 text-teal mx-auto mb-3" />
          <h1 className="text-lg font-bold text-ink mb-1">Application received</h1>
          <p className="text-sm text-ink-2">
            Thanks for applying to <span className="text-ink">{job.title}</span>. We&apos;ll be in touch if you&apos;re
            shortlisted for the next step.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-lg">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-ink mb-1">{job.title}</h1>
          <p className="text-sm text-ink-2 whitespace-pre-line">{job.description}</p>
          {job.required_skills && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {job.required_skills.split(",").map((s) => s.trim()).filter(Boolean).map((skill) => (
                <span key={skill} className="text-[11px] px-2 py-0.5 rounded-full bg-surface-3 text-ink-2">
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="card p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">Full Name</label>
            <input
              required
              maxLength={255}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="input-field"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">Email</label>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">Phone (optional)</label>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">Resume (PDF or DOCX, max 5MB)</label>
            <label className="flex items-center gap-2 border border-dashed border-border-2 rounded-lg px-3 py-3 cursor-pointer hover:border-accent transition-colors text-sm text-ink-2">
              <Upload className="w-4 h-4 shrink-0" />
              {resumeFile ? resumeFile.name : "Choose a file…"}
              <input
                type="file"
                accept=".pdf,.docx"
                className="hidden"
                onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}

          <button type="submit" disabled={submitting} className="btn-primary w-full justify-center">
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
            Submit Application
          </button>
        </form>
      </div>
    </div>
  );
}
