import { cn } from "@/lib/utils";
import type { CandidateStage, JobStatus } from "@/types";



const STAGE_STYLES: Record<CandidateStage, string> = {
  applied: "bg-info-dim text-info",
  screened: "bg-purple-dim text-purple",
  shortlisted: "bg-amber-dim text-amber",
  interview_scheduled: "bg-accent-dim text-accent-light",
  interviewed: "bg-teal-dim text-teal",
  recommended: "bg-teal-dim text-teal",
  hired: "bg-teal-dim text-teal",
  rejected: "bg-danger-dim text-danger",
};

const STAGE_LABELS: Record<CandidateStage, string> = {
  applied: "Applied",
  screened: "Screened",
  shortlisted: "Email Sent",
  interview_scheduled: "Interview Scheduled",
  interviewed: "Interviewed",
  recommended: "Selected",
  hired: "Hired",
  rejected: "Rejected",
};

export function StageBadge({ stage }: { stage: CandidateStage }) {
  return (
    <span className={cn("inline-flex px-2.5 py-1 rounded-full text-xs font-medium", STAGE_STYLES[stage])}>
      {STAGE_LABELS[stage]}
    </span>
  );
}

const JOB_STATUS_STYLES: Record<JobStatus, string> = {
  draft: "bg-surface-3 text-ink-2",
  open: "bg-teal-dim text-teal",
  closed: "bg-danger-dim text-danger",
  archived: "bg-surface-3 text-ink-3",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <span className={cn("inline-flex px-2.5 py-1 rounded-full text-xs font-medium capitalize", JOB_STATUS_STYLES[status])}>
      {status}
    </span>
  );
}
