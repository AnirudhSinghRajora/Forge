import type { AskResponse, CreateCaseResponse, Evidence, PlotResponse, GeoPolygon } from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
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

export interface CaseEnvelope<C = CaseRecord> { case: C; evidence: Evidence | null; actions: ActionRecord[] | Record<string, unknown> | null }

/** The case row. Only the fields this UI reads are named, and all of them may be absent. */
export interface CaseRecord {
  id?: string; case_id?: string; lat?: number | null; lon?: number | null; lang?: string | null;
  crop?: string | null; event_type?: string | null; event_date?: string | null; event_time?: string | null;
  transcript?: string | null; polygon?: GeoPolygon | null; area_ha?: number | null; status?: string | null;
  run_id?: string | null; active_run_id?: string | null; latest_run_id?: string | null;
  submission?: SubmissionRecord | null; reference_no?: string | null; needs?: string[] | null;
  [k: string]: unknown;
}
export interface SubmissionRecord { channel?: string; reference_no?: string; submitted_at?: string }
export interface ActionRecord { type?: string; kind?: string; status?: string; payload?: unknown; text?: string; [k: string]: unknown }

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

export const artifactUrl = (path: string) =>
  `/api/artifacts/${path.split("/").map(encodeURIComponent).join("/")}`;
export const pdfUrl = (id: string, lang: string) => `/api/cases/${encodeURIComponent(id)}/evidence.pdf?lang=${lang}`;
export const audioUrl = (id: string, lang: string) => `/api/cases/${encodeURIComponent(id)}/summary.mp3?lang=${lang}`;

export const getRadar = (signal?: AbortSignal) => request<unknown>("/api/radar", { signal });
