"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Vapi from "@vapi-ai/web";
import { Video, Mic, CheckCircle2, AlertTriangle, Loader2, PhoneOff, ShieldAlert } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { InterviewPublic } from "@/types";

type RoomState =
  | "loading"
  | "not_found"
  | "consent"
  | "ready"
  | "connecting"
  | "active"
  | "ended"
  | "escalated"
  | "error";

const VAPI_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPI_PUBLIC_KEY ?? "";

// Public CDN mirror of face-api.js's model weights — no server hosting
// needed, loaded once on mount. Detection runs entirely in the browser;
// we only ever send face COUNTS to our backend, never frames or video.
const FACE_MODEL_URL = "https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@master/weights";
const FACE_CHECK_INTERVAL_MS = 4000;

export default function InterviewRoomPage() {
  const params = useParams<{ interviewId: string }>();
  const [state, setState] = useState<RoomState>("loading");
  const [interview, setInterview] = useState<InterviewPublic | null>(null);
  const [consentChecks, setConsentChecks] = useState({ camera: false, recording: false, monitoring: false });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [faceBlocked, setFaceBlocked] = useState(false);


  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const vapiRef = useRef<Vapi | null>(null);
  const callStartRef = useRef<number>(0);
  const faceModelsLoadedRef = useRef(false);
  const lastFaceCountRef = useRef<number | null>(null);
  const faceCheckIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    apiFetch<InterviewPublic>(`/interviews/${params.interviewId}/public`)
      .then((data) => {
        setInterview(data);
        setState("consent");
      })
      .catch(() => setState("not_found"));
  }, [params.interviewId]);

  // FIX: re-attach the camera stream to the <video> element every time it
  // actually mounts. The old code only tried to attach it once, at the
  // moment permission was granted — but the <video> element doesn't exist
  // yet at that point (it's not rendered during "consent"), so the
  // assignment silently did nothing and the preview stayed black.
  useEffect(() => {
    if ((state === "ready" || state === "connecting" || state === "active") && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [state]);

  // Load face-api.js models once, in the background, as soon as the page
  // is ready — so detection can start immediately once the interview
  // begins, with no load delay mid-interview.
  useEffect(() => {
    let cancelled = false;
    import("face-api.js").then(async (faceapi) => {
      try {
        await faceapi.nets.tinyFaceDetector.loadFromUri(FACE_MODEL_URL);
        if (!cancelled) faceModelsLoadedRef.current = true;
      } catch (err) {
        console.error("Failed to load face detection models", err);
        // Deliberately non-fatal — the interview still works without
        // face detection, it just won't log multiple_faces/no_face events.
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function logEvent(eventType: string) {
    const offsetMs = Date.now() - callStartRef.current;
    try {
      const result = await apiFetch<{ escalate: boolean; violation_count: number }>(
        `/interviews/${params.interviewId}/events`,
        { method: "POST", body: { event_type: eventType, offset_ms: Math.max(0, offsetMs), metadata: {} } }
      );
      if (result.escalate) {
        vapiRef.current?.stop();
        document.exitFullscreen?.().catch(() => {});
        setState("escalated");
      }
    } catch {
      // A failed proctoring-log call must never interrupt the candidate's
      // live interview — swallow deliberately.
    }
  }

  // Passive proctoring: tab-switch / focus-loss detection.
  useEffect(() => {
    if (state !== "active") return;

    function handleVisibilityChange() {
      if (document.hidden) logEvent("tab_switch");
    }
    function handleBlur() {
      logEvent("window_blur");
    }
    function handleFullscreenChange() {
      if (!document.fullscreenElement) logEvent("fullscreen_exit");
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", handleBlur);
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", handleBlur);
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  // Active proctoring: face-count detection. Runs on an interval against
  // the candidate's own camera feed entirely in-browser — only the
  // resulting COUNT is ever sent to our backend, never a frame or the
  // video itself.
  useEffect(() => {
    if (state !== "active") return;

    faceCheckIntervalRef.current = setInterval(async () => {
      if (!faceModelsLoadedRef.current || !videoRef.current) return;
      try {
        const faceapi = await import("face-api.js");
        const detections = await faceapi.detectAllFaces(videoRef.current, new faceapi.TinyFaceDetectorOptions());
        const count = detections.length;

        // Only log on a CHANGE from the last reading, so a candidate who
        // is legitimately alone the whole time doesn't generate a
        // violation every 4 seconds — only transitions count.


        if (count !== lastFaceCountRef.current) {
          lastFaceCountRef.current = count;
          if (count === 0) {
            logEvent("no_face_detected");
            vapiRef.current?.setMuted(true);
            setFaceBlocked(true);
          } else {
            if (faceBlocked) {
              vapiRef.current?.setMuted(false);
              setFaceBlocked(false);
            }
            if (count > 1) logEvent("multiple_faces");
          }
        }


      } catch (err) {
        console.error("Face detection check failed", err);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, FACE_CHECK_INTERVAL_MS);

    return () => {
      if (faceCheckIntervalRef.current) clearInterval(faceCheckIntervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state]);

  async function handleConsentAndContinue() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      setState("ready");
    } catch {
      setErrorMessage("Camera access is required to start the interview. Please allow camera permissions and try again.");
      setState("error");
    }
  }

  async function handleStartInterview() {
    if (!interview) return;
    if (!VAPI_PUBLIC_KEY) {
      setErrorMessage("Interview voice service isn't configured yet. Please contact the recruiter.");
      setState("error");
      return;
    }

    setState("connecting");

    try {
      await apiFetch(`/interviews/${interview.id}/start`, { method: "POST" });
    } catch {
      setErrorMessage("This interview link has already been used or has expired. Please contact the recruiter.");
      setState("error");
      return;
    }

    const vapi = new Vapi(VAPI_PUBLIC_KEY);
    vapiRef.current = vapi;

    vapi.on("call-start", () => {
      callStartRef.current = Date.now();
      setState("active");

    // Fullscreen
    document.documentElement.requestFullscreen?.().catch(() => {});

    // Camera off detection
    const videoTrack = streamRef.current?.getVideoTracks()[0];
    if (videoTrack)
      {
      videoTrack.addEventListener("ended", () => logEvent("camera_off"));
      videoTrack.addEventListener("mute", () => logEvent("camera_off"));
      }
    });

      
    // FIX (reliability): capture the real Vapi call ID the instant the
    // call actually starts and persist it immediately — don't rely
    // solely on the webhook's metadata to link this later, since that
    // metadata isn't guaranteed to arrive. This is what makes manual
    // "Sync" recovery possible if the webhook itself never fires.
    vapi.on("message", (message: unknown) => {
      const msg = message as { call?: { id?: string } };
      if (msg?.call?.id) {
        apiFetch(`/interviews/${interview.id}/link-call`, {
          method: "POST",
          body: { vapi_call_id: msg.call.id },
        }).catch(() => {});
      }
    });
    vapi.on("call-end", () => {
      setState("ended");
      streamRef.current?.getTracks().forEach((t) => t.stop());
      document.exitFullscreen?.().catch(() => {});
    });
    vapi.on("error", (err) => {
      console.error("Vapi error", err);
      setErrorMessage("The interview connection was interrupted. Please contact the recruiter if this persists.");
      setState("error");
    });


    const call = await vapi.start(interview.vapi_assistant_id, 
      {
      variableValues: 
      {
        candidate_name: interview.candidate_name,
        job_title: interview.job_title,
        company_name: interview.company_name,
        required_skills: interview.required_skills,
        min_years_experience: interview.min_years_experience,
      },
      metadata: { interview_id: interview.id },
      } as never);

    if (call && typeof call === "object" && "id" in call && call.id) 
      {
      apiFetch(`/interviews/${interview.id}/link-call`, 
        {
        method: "POST",
        body: { vapi_call_id: (call as { id: string }).id },
      }).catch(() => {});
      }
  }

   

  function handleEndInterview() {
    vapiRef.current?.stop();
  }

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      vapiRef.current?.stop();
      if (faceCheckIntervalRef.current) clearInterval(faceCheckIntervalRef.current);
    };
  }, []);

  if (state === "loading") {
    return (
      <Centered>
        <Loader2 className="w-6 h-6 text-ink-2 animate-spin" />
      </Centered>
    );
  }

  if (state === "not_found") {
    return (
      <Centered>
        <Card>
          <AlertTriangle className="w-8 h-8 text-amber mx-auto mb-3" />
          <h1 className="text-lg font-bold text-ink mb-1">This interview link isn&apos;t available</h1>
          <p className="text-sm text-ink-2">
            It may have expired, already been used, or the link may be incorrect. Contact the recruiter who
            shared it with you.
          </p>
        </Card>
      </Centered>
    );
  }

  if (state === "error") {
    return (
      <Centered>
        <Card>
          <AlertTriangle className="w-8 h-8 text-danger mx-auto mb-3" />
          <h1 className="text-lg font-bold text-ink mb-1">Something went wrong</h1>
          <p className="text-sm text-ink-2">{errorMessage}</p>
        </Card>
      </Centered>
    );
  }

  if (state === "escalated") {
    return (
      <Centered>
        <Card>
          <ShieldAlert className="w-8 h-8 text-danger mx-auto mb-3" />
          <h1 className="text-lg font-bold text-ink mb-1">Interview ended</h1>
          <p className="text-sm text-ink-2">
            This interview was ended automatically after multiple integrity signals were detected (such as
            switching away from this tab or camera anomalies). This has been flagged for the recruiting team
            to review manually — no automatic decision has been made about your application.
          </p>
        </Card>
      </Centered>
    );
  }

  if (state === "ended") {
    return (
      <Centered>
        <Card>
          <CheckCircle2 className="w-8 h-8 text-teal mx-auto mb-3" />
          <h1 className="text-lg font-bold text-ink mb-1">Interview complete</h1>
          <p className="text-sm text-ink-2">
            Thanks for taking the time to speak with us, {interview?.candidate_name}. The recruiting team will
            follow up with next steps.
          </p>
        </Card>
      </Centered>
    );
  }

  if (state === "consent" && interview) {
    const allChecked = consentChecks.camera && consentChecks.recording && consentChecks.monitoring;
    return (
      <Centered wide>
        <Card wide>
          <h1 className="text-lg font-bold text-ink mb-1">Before you begin</h1>
          <p className="text-sm text-ink-2 mb-5">
            Interview for <span className="text-ink">{interview.job_title}</span> — please review and confirm each
            item below.
          </p>
          <div className="space-y-3 mb-6">
            <ConsentRow
              checked={consentChecks.camera}
              onChange={(v) => setConsentChecks((c) => ({ ...c, camera: v }))}
              label="My camera will be on for the full interview"
              description="Video is used to verify your identity is consistent throughout the interview."
            />
            <ConsentRow
              checked={consentChecks.recording}
              onChange={(v) => setConsentChecks((c) => ({ ...c, recording: v }))}
              label="This interview will be recorded (audio and video)"
              description="Recordings are stored securely and reviewed by the hiring team."
            />
            <ConsentRow
              checked={consentChecks.monitoring}
              onChange={(v) => setConsentChecks((c) => ({ ...c, monitoring: v }))}
              label="Activity signals are monitored during the interview"
              description="This interview runs in fullscreen. Switching tabs, losing window focus, exiting fullscreen, turning off your camera, or additional people/no face visible on camera are all logged. Repeated signals may end the interview early and flag it for recruiter review — this does not automatically reject your application."
            />
          </div>
          <button disabled={!allChecked} onClick={handleConsentAndContinue} className="btn-primary w-full justify-center">
            I Agree — Continue
          </button>
        </Card>
      </Centered>
    );
  }

  if ((state === "ready" || state === "connecting" || state === "active") && interview) {
    return (
      <div className="min-h-screen bg-bg flex flex-col items-center justify-center px-4 py-10 gap-6">
        <div className="text-center">
          <h1 className="text-xl font-bold text-ink">{interview.job_title}</h1>
          <p className="text-sm text-ink-2">{interview.candidate_name}</p>
        </div>

        {/* Larger video — was max-w-md (small), now fills much more of the
            viewport so the candidate can actually see themselves clearly. */}

        <div className="relative w-full max-w-3xl aspect-video rounded-card overflow-hidden border border-border bg-surface-2">
          <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
          <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/50 px-2.5 py-1.5 rounded-full text-xs text-white">
            <Video className="w-3.5 h-3.5" /> Camera on
          </div>
          {state === "active" && (
            <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-danger/90 px-2.5 py-1.5 rounded-full text-xs text-white">
              <Mic className="w-3.5 h-3.5" /> Live
            </div>
          )}
          {faceBlocked && state === "active" && (
            <div className="absolute inset-0 bg-black/85 flex flex-col items-center justify-center text-center px-6 z-10">
              <ShieldAlert className="w-8 h-8 text-amber mb-2" />
              <p className="text-sm font-medium text-white">We can't see you</p>
              <p className="text-xs text-ink-2 mt-1">
                Please stay visible in the camera — the interview is paused and will resume automatically.
              </p>
            </div>
          )}
        </div>
   

        {state === "ready" && (
          <button onClick={handleStartInterview} className="btn-primary">
            Start Interview
          </button>
        )}
        {state === "connecting" && (
          <div className="flex items-center gap-2 text-ink-2 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Connecting…
          </div>
        )}
        {state === "active" && (
          <button onClick={handleEndInterview} className="btn-secondary text-danger">
            <PhoneOff className="w-4 h-4" /> End Interview
          </button>
        )}
      </div>
    );
  }

  return null;
}

function Centered({ children, wide }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <div className={`min-h-screen bg-bg flex items-center justify-center px-4 ${wide ? "py-10" : ""}`}>{children}</div>
  );
}

function Card({ children, wide }: { children: React.ReactNode; wide?: boolean }) {
  return <div className={`card p-8 text-center ${wide ? "max-w-lg text-left" : "max-w-md"}`}>{children}</div>;
}

function ConsentRow({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <label className="flex items-start gap-3 p-3 rounded-lg border border-border hover:border-border-2 cursor-pointer transition-colors">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 w-4 h-4 accent-accent shrink-0"
      />
      <div>
        <div className="text-sm font-medium text-ink">{label}</div>
        <div className="text-xs text-ink-2">{description}</div>
      </div>
    </label>
  );
}
