import type { AskResponse, CreateCaseResponse, Evidence, PlotResponse, GeoPolygon } from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
  /** A message the server wrote for the farmer, in the reader's language where it has one. */
  localized(lang: string): string {
    const d = this.detail && typeof this.detail === "object" && "detail" in this.detail ? (this.detail as { detail: unknown }).detail : this.detail;
    if (d && typeof d === "object") {
      const m = d as Record<string, unknown>;
      const v = m[`message_${lang}`] ?? m.message_en ?? m.message_hi;
      if (typeof v === "string") return v;
    }
    return this.message;
  }
  /** True when the server was never reached: the honest message is "no connection". */
  get isNetwork() {
    return this.status === 0;
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 45000): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  const outer = init.signal;
  if (outer) outer.addEventListener("abort", () => ctl.abort(), { once: true });
  let res: Response;
  try {
    res = await fetch(path, { ...init, signal: ctl.signal });
  } catch (e) {
    throw new ApiError(0, e instanceof Error ? e.message : "network");
  } finally {
    clearTimeout(timer);
  }
  const type = res.headers.get("content-type") ?? "";
  const body: unknown = type.includes("json") ? await res.json().catch(() => null) : await res.text().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailText(body) ?? `HTTP ${res.status}`, body);
  return body as T;
}

function detailText(body: unknown): string | null {
  if (typeof body === "string") {
    // A proxy or platform error page is not a message anyone should read.
    return body.length && body.length < 300 && !body.trimStart().startsWith("<") ? body : null;
  }
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message_en" in d) return String((d as { message_en: unknown }).message_en);
    if (Array.isArray(d)) {
      return d
        .map((x) => (x && typeof x === "object" && "msg" in x ? String((x as { msg: unknown }).msg) : String(x)))
        .join("; ");
    }
  }
  return null;
}

const json = (body: unknown): RequestInit => ({
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export interface Health { status: string; gemini: boolean; version: string }
export const getHealth = () => request<Health>("/api/health", {}, 8000);

export interface CreateCaseInput { audio?: Blob | null; text?: string; lat: number; lon: number; lang: string }

export function createCase(input: CreateCaseInput): Promise<CreateCaseResponse> {
  const fd = new FormData();
  if (input.audio) {
    const ext = input.audio.type.includes("mp4") ? "m4a" : input.audio.type.includes("ogg") ? "ogg" : "webm";
    fd.append("audio", input.audio, `statement.${ext}`);
  }
  if (input.text?.trim()) fd.append("text", input.text.trim());
  fd.append("lat", String(input.lat));
  fd.append("lon", String(input.lon));
  fd.append("lang", input.lang);
  // Speech parsing can be slow on a poor uplink, so this waits longer than ordinary calls.
  return request<CreateCaseResponse>("/api/cases", { method: "POST", body: fd }, 120000);
}

export interface ExhibitStatus { status: "pending" | "done" | "failed" | "not_applicable"; reason?: string | null; updated_at?: string | null }
export interface CaseEnvelope {
  case: CaseRecord; evidence: Evidence | null; actions: ActionRecord[] | null;
  sealed?: boolean; verdict_ready?: boolean; exhibits?: Record<string, ExhibitStatus>;
  rubric?: { version?: string; p_field?: number; strong_delta?: number; moderate_delta?: number } | null;
}

/** The case row from _case_dict in backend/app/main.py. */
export interface CaseRecord {
  id: string; lat?: number | null; lon?: number | null; lang?: string | null;
  crop?: string | null; event_type?: string | null; event_date?: string | null; event_time?: string | null;
  date_source?: string | null; proposed_event_date?: string | null;
  insured?: string | null; crop_stage?: string | null;
  transcript?: string | null; status?: string | null; district?: string | null; state?: string | null;
  needs?: string[] | null; questions?: Record<string, Record<string, string>> | null;
  parsed?: { confidence?: number | null; date_note?: string | null } | null;
  plot?: { geometry: GeoPolygon; area_ha: number; centroid: [number, number]; crs: string; warnings: string[] } | null;
  active_run_id?: string | null;
  latest_run?: { id: string; status: string; trigger?: string; started_at?: string; finished_at?: string | null; error?: string | null } | null;
}
export interface ActionRecord { id?: string; type: string; status?: string; payload?: Record<string, unknown> | null; due_at?: string | null; created_at?: string }
export interface IntimationDraft {
  available: boolean; needed?: boolean; reason?: string; text_hi?: string; text_en?: string; text_te?: string;
  whatsapp_url_hi?: string; whatsapp_url_en?: string; whatsapp_url_te?: string;
  fields_to_fill?: string[]; partial_allowed_note_hi?: string; partial_allowed_note_en?: string; partial_allowed_note_te?: string; channels?: unknown[]; basis?: string | null;
  deadline_status?: string | null; due_at?: string | null; time_assumed?: boolean;
  lapsed_note_hi?: string | null; lapsed_note_en?: string | null; lapsed_note_te?: string | null; lapsed_basis?: string | null;
}

export const getCase = (id: string, signal?: AbortSignal) => request<CaseEnvelope>(`/api/cases/${encodeURIComponent(id)}`, { signal });
export const patchCase = (id: string, patch: Record<string, unknown>) =>
  request<CaseRecord>(`/api/cases/${encodeURIComponent(id)}`, { method: "PATCH", ...json(patch) });
export const putPlot = (id: string, polygon: GeoPolygon) =>
  request<PlotResponse>(`/api/cases/${encodeURIComponent(id)}/plot`, { method: "PUT", ...json({ polygon }) });
export const startInvestigation = (id: string) =>
  request<{ run_id: string }>(`/api/cases/${encodeURIComponent(id)}/investigate`, { method: "POST" });
export const postSubmission = (id: string, body: { channel: string; reference_no: string; submitted_at: string }) =>
  request<CaseRecord>(`/api/cases/${encodeURIComponent(id)}/submission`, { method: "POST", ...json(body) });
export const askPolicy = (id: string, question: string, lang: string) =>
  request<AskResponse>(`/api/cases/${encodeURIComponent(id)}/ask`, { method: "POST", ...json({ question, lang }) }, 60000);

export const retryExhibit = (id: string, name: string) =>
  request<{ run_id: string; exhibit: string; status: string }>(`/api/cases/${encodeURIComponent(id)}/exhibits/${encodeURIComponent(name)}/retry`, { method: "POST" });

export const artifactUrl = (path: string) => {
  // The server's path may be relative to the artifact root or a full path under it.
  const rel = path.replace(/^.*\/artifacts\//, "").replace(/^\/+/, "");
  return `/api/artifacts/${rel.split("/").map(encodeURIComponent).join("/")}`;
};
export const pdfUrl = (id: string, lang: string) => `/api/cases/${encodeURIComponent(id)}/evidence.pdf?lang=${lang}`;
export const audioUrl = (id: string, lang: string) => `/api/cases/${encodeURIComponent(id)}/summary.mp3?lang=${lang}&kind=summary`;

/** Audio is optional on the server: a 404 means the components fall back to browser speech. */
export const testimonyAudioUrl = (id: string, lang: string) => `/api/cases/${encodeURIComponent(id)}/summary.mp3?lang=${lang}&kind=testimony`;

export const getRadar = (signal?: AbortSignal) => request<unknown>("/api/radar", { signal });
