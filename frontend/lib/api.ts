/**
 * API client for the RecruiterAI backend.
 *
 * WHY a single wrapper instead of scattering fetch() calls through
 * components: every request needs the Clerk bearer token attached and
 * every error needs to be parsed against the backend's consistent
 * { error_code, message, details } shape (see backend/app/core/exceptions.py).
 * Centralizing this means that shape only needs to be handled once, and
 * a future change (e.g. adding request-id tracing headers) touches one
 * file instead of every component that calls the API.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  errorCode: string;
  details: Record<string, unknown>;

  constructor(status: number, errorCode: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.details = details;
  }
}

type FetchOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  /** Pass the Clerk token directly — components get it from useAuth().getToken() (a hook, so it can't live in this module). */
  token?: string | null;
};

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { token, body, headers, ...rest } = options;

  const isFormData = body instanceof FormData;

  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...rest,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      "ngrok-skip-browser-warning": "true",
      ...headers,
    },
    body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let parsed: { error_code?: string; message?: string; details?: Record<string, unknown> } = {};
    try {
      parsed = await response.json();
    } catch {
      // Response wasn't JSON (e.g. a raw 502 from the platform, not our app) — fall through to generic message.
    }
    throw new ApiError(
      response.status,
      parsed.error_code ?? "unknown_error",
      parsed.message ?? `Request failed with status ${response.status}`,
      parsed.details ?? {}
    );
  }

  // 204 No Content etc.
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
