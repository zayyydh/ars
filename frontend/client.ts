// api/client.ts — all HTTP calls to the Flask backend in one place.
//
// Why centralise API calls?
//   If the backend URL changes (e.g. dev → staging → prod), you change it once here.
//   If an endpoint changes shape, you update the type and the caller in one file.
//   Routes never import fetch() directly — they call these functions.

import type {
  CreateJobResponse,
  UploadResponse,
  PollResponse,
} from "../types";

// Base URL — reads from Vite env var (VITE_API_URL) or falls back to localhost.
// In production, set VITE_API_URL=https://your-api.domain.com in your .env.production
const BASE_URL = (import.meta as any).env?.VITE_API_URL ?? "http://localhost:5000";

// ──────────────────────────────────────────────────────────────────
// Core fetch wrapper
// ──────────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path:    string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      // Don't set Content-Type for FormData — browser sets it with boundary
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });

  // Parse JSON even for error responses (Flask returns JSON errors)
  const data = await res.json().catch(() => ({ error: "Invalid JSON response" }));

  if (!res.ok) {
    throw new Error(data.error ?? `HTTP ${res.status}`);
  }

  return data as T;
}

// ──────────────────────────────────────────────────────────────────
// API functions
// ──────────────────────────────────────────────────────────────────

/**
 * Create a job by submitting a job description.
 * Returns a job_id used in subsequent resume uploads.
 */
export async function createJob(jdText: string): Promise<CreateJobResponse> {
  return apiFetch<CreateJobResponse>("/api/jobs", {
    method: "POST",
    body:   JSON.stringify({ jd_text: jdText }),
  });
}

/**
 * Upload a resume file and screen it against a job.
 * Uses multipart/form-data — the browser sets the Content-Type header.
 */
export async function uploadResume(
  file:   File,
  jobId:  string,
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file",   file);
  form.append("job_id", jobId);

  return apiFetch<UploadResponse>("/api/resumes/upload", {
    method: "POST",
    body:   form,
  });
}

/**
 * Poll for a screening result.
 * Call every 2s until status === "completed" or "failed".
 */
export async function pollResult(resultId: string): Promise<PollResponse> {
  return apiFetch<PollResponse>(`/api/results/${resultId}`);
}

/**
 * Convenience: poll until done, calling onProgress on each tick.
 * Resolves with the final ScreeningResult.
 * Rejects on failure or timeout.
 */
export async function pollUntilDone(
  resultId:    string,
  onProgress?: (status: string) => void,
  intervalMs:  number = 2000,
  maxAttempts: number = 60,   // 2 min max
): Promise<PollResponse> {
  for (let i = 0; i < maxAttempts; i++) {
    const response = await pollResult(resultId);
    onProgress?.(response.status);

    if (response.status === "completed" || response.status === "failed") {
      return response;
    }

    await new Promise(r => setTimeout(r, intervalMs));
  }
  throw new Error("Timed out waiting for screening result");
}
