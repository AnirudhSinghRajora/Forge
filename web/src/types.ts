// Hand mirror of backend/app/evidence/schema.py. `null` always means "not measured".
export type QAStatus = "accepted" | "suspect" | "rejected";
export type Pattern = "patchy" | "uniform" | "none";
export type VerdictLevel = "strong" | "moderate" | "weak" | "insufficient" | "not_damage_likely_harvest";
export type EventType = "hail" | "unseasonal_rain" | "flood" | "cyclone" | "wind" | "pest" | "drought" | "other" | "unknown";
export type ObjectionOutcome = "rebutted" | "conceded" | "unresolved";

export interface Provenance { field: string; source: string; asset?: string | null; url?: string | null; retrieved_at: string }
export interface GeoPolygon { type: "Polygon"; coordinates: number[][][] }
export interface PlotInfo { geometry: GeoPolygon; area_ha: number; centroid: [number, number]; crs: string; warnings: string[] }
export interface EventInfo { type: EventType; date: string; date_source: "farmer" | "weather_proposed" | "news"; crop?: string | null }
export interface SceneQA {
  id: string; collection: "sentinel-2-l2a" | "sentinel-1-rtc"; date: string; status: QAStatus; reasons: string[];
  metadata_cloud_pct?: number | null; plot_valid_frac?: number | null; context_ndvi_median?: number | null;
}
export interface PlotStats {
  scene_id: string; date: string; valid_frac: number; n_pixels: number; ndvi_median: number; ndvi_p25: number; ndvi_p75: number;
  bsi_median?: number | null; ndmi_median?: number | null; ndre_median?: number | null;
}
export interface PlaceboTest {
  n_placebos: number; n_at_least_as_extreme: number; p_value: number; statistic: string; plot_value: number;
  placebo_median: number; placebo_p05: number; placebo_p95: number; histogram_edges: number[]; histogram_counts: number[];
  seed: number; insufficient_reason?: string | null;
}
export interface CounterfactualPoint { date: string; observed: number | null; expected: number | null; expected_low?: number | null; expected_high?: number | null }
export interface Counterfactual { n_control_pixels: number; pre_fit_rmse: number | null; gap_at_post: number | null; series: CounterfactualPoint[]; method: string }
export interface OpticalEvidence {
  scenes_considered: SceneQA[]; pre?: PlotStats | null; post?: PlotStats | null; plot_delta_ndvi?: number | null; drop_frac?: number | null;
  iqr_delta?: number | null; within_plot_pattern?: Pattern | null; post_bare_fraction?: number | null;
}
export interface NeighbourEvidence {
  ring_m: [number, number]; n_comparable_pixels: number; neighbour_median_delta: number | null; plot_minus_neighbour: number | null;
  neighbour_bare_fraction_post?: number | null; placebo?: PlaceboTest | null; counterfactual?: Counterfactual | null;
}
export interface HistoryYear { year: number; pre_scene_id: string | null; post_scene_id: string | null; pre_ndvi: number | null; delta_ndvi: number | null; note?: string | null }
export interface HistoryEvidence { years: HistoryYear[]; typical_delta?: number | null; excess_vs_history?: number | null; downweighted?: boolean; note?: string | null }
export interface SarEvidence {
  pre_scene_id?: string | null; post_scene_id?: string | null; pre_date?: string | null; post_date?: string | null; orbit_direction?: string | null;
  relative_orbit?: number | null; vv_pre_db?: number | null; vv_post_db?: number | null; vh_pre_db?: number | null; vh_post_db?: number | null;
  vh_change_db?: number | null; neighbour_vh_change_db?: number | null; vh_excess_db?: number | null; water_frac_pre?: number | null;
  water_frac_post?: number | null; new_water_frac?: number | null; placebo?: PlaceboTest | null; usable?: boolean; reason?: string | null;
}
export interface WeatherDay { date: string; precip_mm: number | null; gust_kmh?: number | null; weather_code?: number | null }
export interface WeatherEvidence {
  source: string; fetched_at: string; grid_note: string; days: WeatherDay[]; precip_mm_event_window: number | null; max_daily_mm: number | null;
  hail_code_hours: number | null; thunder_hours: number | null; max_gust_kmh: number | null; corroborated: boolean;
  proposed_event_date?: string | null; fallback_used?: boolean;
}
export interface Alert { source: string; identifier: string; issued?: string | null; area?: string | null; headline?: string | null; severity?: string | null; url?: string | null }
export interface NewsItem { title: string; url: string; date?: string | null; snippet?: string | null }
export interface TimelinePoint { date: string; sensor: "s2" | "s1"; ndvi?: number | null; vh_db?: number | null; vv_db?: number | null; qa?: QAStatus | null }
export interface Objection {
  id: string; challenge_hi: string; challenge_en: string; test: string; measured: Record<string, unknown>; outcome: ObjectionOutcome;
  finding_hi: string; finding_en: string;
}
export interface Verdict {
  level: VerdictLevel; headline_hi: string; headline_en: string; headline_te?: string | null; reasons: string[]; caveats: string[];
  falsifiers_checked: string[]; rubric_version: string;
}
export interface PolicyClause { clause_id: string; doc: string; page?: number | null; text: string; applies_because?: string | null; url?: string | null }
export interface Deadline { type: "intimation_72h" | "recheck" | "other"; due_at: string; basis: string; status: "open" | "met" | "lapsed" }
export type ChipKind = "true_colour_pre" | "true_colour_post" | "ndvi_pre" | "ndvi_post" | "delta_map" | "sar_change";
export interface Chip { kind: ChipKind; path: string; scene_id?: string | null; date?: string | null; bounds?: [number, number, number, number] | null }
export interface ReplayCore {
  engine_version: string; polygon: GeoPolygon; event_date: string; optical_pre_id?: string | null; optical_post_id?: string | null;
  sar_pre_id?: string | null; sar_post_id?: string | null; history_scene_ids: string[]; seed: number; numbers: Record<string, number | null>;
}
export interface Evidence {
  case_id: string; run_id: string; created_at: string; plot: PlotInfo; event: EventInfo; optical: OpticalEvidence;
  neighbours?: NeighbourEvidence | null; history?: HistoryEvidence | null; sar?: SarEvidence | null; weather?: WeatherEvidence | null;
  alerts: Alert[]; news: NewsItem[]; timeline: TimelinePoint[]; chips: Chip[]; cross_examination: Objection[]; verdict?: Verdict | null;
  policy: PolicyClause[]; deadlines: Deadline[]; explanation_hi?: string | null; explanation_en?: string | null; explanation_te?: string | null;
  llm_used: boolean; provenance: Provenance[]; replay?: ReplayCore | null; evidence_hash?: string | null;
}

export type TraceType =
  | "step_started" | "tool_called" | "tool_result" | "decision" | "scene_rejected" | "sensor_switch"
  | "objection" | "verdict" | "action" | "warning" | "error" | "done";

export interface TraceEvent {
  seq: number; run_id: string; ts: string; type: TraceType; node: string; title_hi: string; title_en: string; detail: Record<string, unknown>;
}

export interface Parsed { crop?: string | null; event_type?: EventType | null; event_date?: string | null; transcript?: string | null; confidence?: number | null }
export interface CreateCaseResponse { case_id: string; parsed: Parsed; needs: string[] }
export interface PlotResponse { area_ha: number; warnings: string[] }
export interface AskCitation { clause_id?: string; doc?: string; page?: number | null; text?: string; url?: string | null }
export interface AskResponse { answer?: string | null; citations?: AskCitation[]; not_covered?: boolean }
