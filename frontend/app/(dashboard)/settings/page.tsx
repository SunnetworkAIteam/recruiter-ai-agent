"use client";

import { useState } from "react";
import { Info, Save } from "lucide-react";
import { Topbar } from "@/components/layout/Topbar";
import { useOrganization } from "@clerk/nextjs";

const DEFAULT_SYSTEM_PROMPT = `You are an AI interviewer conducting a first-round screening interview for the {{job_title}} role at {{company_name}}.

Ask questions that probe the candidate's real experience with: {{required_skills}}.
Keep the tone conversational and professional. Ask one question at a time and
follow up naturally based on their answers. The interview should run
15-20 minutes. Do not reveal scoring criteria to the candidate.`;

export default function SettingsPage() {
  const { organization } = useOrganization();
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [interviewMinutes, setInterviewMinutes] = useState(20);

  return (
    <>
      <Topbar title="Settings" />
      <main className="flex-1 overflow-y-auto p-6 max-w-2xl space-y-6">
        <section className="card p-5">
          <div className="text-xs font-semibold text-ink-2 uppercase tracking-wide mb-4">Company Details</div>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">Organization</label>
              <input
                disabled
                value={organization?.name ?? "No organization"}
                className="input-field opacity-60 cursor-not-allowed"
              />
              <p className="text-[11px] text-ink-3 mt-1">Managed in Clerk — organization switcher in the sidebar.</p>
            </div>
          </div>
        </section>

        <section className="card p-5">
          <div className="text-xs font-semibold text-ink-2 uppercase tracking-wide mb-1">AI Interviewer Settings</div>
          <div className="flex items-start gap-2 bg-teal-dim text-teal text-xs rounded-lg px-3 py-2 mb-4 mt-3">
            <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>
              Editing this prompt updates the copy here, but doesn&apos;t push it to Vapi automatically yet — update the system prompt directly in your Vapi assistant&apos;s dashboard for it to take effect on
              live interviews.
            </span>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">Interview System Prompt</label>
              <textarea
                rows={8}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="input-field font-mono text-xs resize-none"
              />
              <p className="text-[11px] text-ink-3 mt-1">
                Variables like <code className="text-accent-light">{"{{job_title}}"}</code> and{" "}
                <code className="text-accent-light">{"{{required_skills}}"}</code> are filled in per-job at interview
                start — matching the &ldquo;Smart Question Generator&rdquo; pattern from your reference design.
              </p>
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-2 mb-1.5">Target Interview Length (minutes)</label>
              <input
                type="number"
                min={5}
                max={60}
                value={interviewMinutes}
                onChange={(e) => setInterviewMinutes(Number(e.target.value))}
                className="input-field max-w-[120px]"
              />
            </div>
          </div>

          <div className="flex justify-end pt-4 mt-4 border-t border-border">
            <button disabled className="btn-secondary opacity-50 cursor-not-allowed">
              <Save className="w-4 h-4" />
              Save (available in Phase 3)
            </button>
          </div>
        </section>
      </main>
    </>
  );
}
