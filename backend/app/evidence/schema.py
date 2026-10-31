"""The Evidence contract shared by the geo engine, the agent, the PDF and the web app.

Rules:
- Numeric fields are only ever filled by deterministic tool code, never by an LLM.
- `None` means "not measured". Never substitute a default number for a missing measurement.
- Every model round-trips through JSON; canonical JSON of `ReplayCore` is what gets hashed.
"""
from __future__ import annotations

from datetime import date as Date, datetime
from typing import Literal

from pydantic import BaseModel, Field

QAStatus = Literal["accepted", "suspect", "rejected"]
Pattern = Literal["patchy", "uniform", "none"]
VerdictLevel = Literal["strong", "moderate", "weak", "insufficient", "not_damage_likely_harvest"]
EventType = Literal["hail", "unseasonal_rain", "flood", "cyclone", "wind", "pest", "drought", "other", "unknown"]
ObjectionOutcome = Literal["rebutted", "conceded", "unresolved"]


class Provenance(BaseModel):
    field: str
    source: str
    asset: str | None = None
    url: str | None = None
    retrieved_at: datetime


class PlotInfo(BaseModel):
    geometry: dict  # GeoJSON Polygon in EPSG:4326
    area_ha: float
    centroid: tuple[float, float]  # lon, lat
    crs: str  # local UTM used for computation
    warnings: list[str] = []


class EventInfo(BaseModel):
    type: EventType = "unknown"
    date: Date
    date_source: Literal["farmer", "weather_proposed", "news"] = "farmer"
    crop: str | None = None


class SceneQA(BaseModel):
    id: str
    collection: Literal["sentinel-2-l2a", "sentinel-1-rtc"]
    date: Date
    status: QAStatus
    reasons: list[str] = []
    metadata_cloud_pct: float | None = None
    plot_valid_frac: float | None = None
    context_ndvi_median: float | None = None


class PlotStats(BaseModel):
    scene_id: str
    date: Date
    valid_frac: float
    n_pixels: int
    ndvi_median: float
    ndvi_p25: float
    ndvi_p75: float
    bsi_median: float | None = None
    ndmi_median: float | None = None
    ndre_median: float | None = None


class PlaceboTest(BaseModel):
    """Randomization inference. The headline statistical claim of the product.

    Same-shape pseudo-plots are placed on comparable cropland around the farmer's plot, and the
    identical statistic is computed for each. `p_value` is the share of pseudo-plots whose
    statistic is at least as extreme as the real plot's, using (k + 1) / (n + 1).
    """
    n_placebos: int
    n_non_overlapping: int | None = None  # placebos whose boxes do not overlap; the rest are correlated
    n_at_least_as_extreme: int
    p_value: float  # 1.0 only together with insufficient_reason
    statistic: str  # e.g. "median_delta_ndvi"
    plot_value: float
    placebo_median: float | None = None  # None only when n_placebos is 0
    placebo_p05: float | None = None
    placebo_p95: float | None = None
    histogram_edges: list[float]
    histogram_counts: list[int]
    seed: int
    insufficient_reason: str | None = None


class CounterfactualPoint(BaseModel):
    date: Date
    observed: float | None
    expected: float | None  # the field's twin: what comparable fields did
    expected_low: float | None = None
    expected_high: float | None = None


class Counterfactual(BaseModel):
    """"Field twin": comparable pixels matched on the pre-event trajectory."""
    n_control_pixels: int
    pre_fit_rmse: float | None
    gap_at_post: float | None  # observed - expected at the post scene (negative = worse than twin)
    series: list[CounterfactualPoint]
    method: str


class OpticalEvidence(BaseModel):
    scenes_considered: list[SceneQA] = []
    pre: PlotStats | None = None
    post: PlotStats | None = None
    plot_delta_ndvi: float | None = None
    drop_frac: float | None = None
    iqr_delta: float | None = None
    within_plot_pattern: Pattern | None = None
    post_bare_fraction: float | None = None


class NeighbourEvidence(BaseModel):
    ring_m: tuple[int, int] = (300, 1500)
    n_comparable_pixels: int
    neighbour_median_delta: float | None
    plot_minus_neighbour: float | None
    neighbour_bare_fraction_post: float | None = None
    placebo: PlaceboTest | None = None  # ring: is this field different from its immediate neighbours?
    far_placebo: PlaceboTest | None = None  # 5-12 km: is it different from fields outside the storm area?
    pretrend_delta: float | None = None  # same statistic on the last accepted pre-event pair
    pretrend_placebo: PlaceboTest | None = None
    counterfactual: Counterfactual | None = None


class HistoryYear(BaseModel):
    year: int
    pre_scene_id: str | None
    post_scene_id: str | None
    pre_ndvi: float | None
    delta_ndvi: float | None
    note: str | None = None


class HistoryEvidence(BaseModel):
    years: list[HistoryYear] = []
    typical_delta: float | None = None
    excess_vs_history: float | None = None
    downweighted: bool = False
    note: str | None = None


class SarEvidence(BaseModel):
    pre_scene_id: str | None = None
    post_scene_id: str | None = None
    pre_date: Date | None = None
    post_date: Date | None = None
    orbit_direction: str | None = None
    relative_orbit: int | None = None
    vv_pre_db: float | None = None
    vv_post_db: float | None = None
    vh_pre_db: float | None = None
    vh_post_db: float | None = None
    vh_change_db: float | None = None
    neighbour_vh_change_db: float | None = None
    vh_excess_db: float | None = None
    water_frac_pre: float | None = None
    water_frac_post: float | None = None
    new_water_frac: float | None = None
    placebo: PlaceboTest | None = None
    usable: bool = False
    reason: str | None = None


class WeatherDay(BaseModel):
    date: Date
    precip_mm: float | None
    gust_kmh: float | None = None
    weather_code: int | None = None


class WeatherEvidence(BaseModel):
    source: str
    fetched_at: datetime
    grid_note: str
    days: list[WeatherDay]
    precip_mm_event_window: float | None
    max_daily_mm: float | None
    hail_code_hours: int | None
    thunder_hours: int | None
    max_gust_kmh: float | None
    corroborated: bool
    proposed_event_date: Date | None = None
    fallback_used: bool = False


class Alert(BaseModel):
    source: str
    identifier: str
    issued: datetime | None = None
    area: str | None = None
    event: str | None = None  # the CAP event name: the alert's hazard
    headline: str | None = None
    severity: str | None = None
    url: str | None = None


class NewsItem(BaseModel):
    """A related report: shown with its link, and never an input to the verdict."""
    title: str
    url: str
    date: str | None = None


class TimelinePoint(BaseModel):
    date: Date
    sensor: Literal["s2", "s1"]
    ndvi: float | None = None
    vh_db: float | None = None
    vv_db: float | None = None
    qa: QAStatus | None = None


class Objection(BaseModel):
    """One round of the cross-examination: a hostile surveyor's challenge and the test that answers it."""
    id: str  # harvest | wrong_plot | wrong_date | cloud_shadow | corrupt_scene | regional_trend | too_small | stale_crop
    challenge_hi: str
    challenge_en: str
    test: str  # the concrete computation that was run
    measured: dict  # the numbers used, copied from the evidence
    outcome: ObjectionOutcome
    finding_hi: str
    finding_en: str
    # Not hashed. Telugu where it has been written; the screen falls back to English otherwise.
    challenge_te: str | None = None
    finding_te: str | None = None


class Verdict(BaseModel):
    level: VerdictLevel
    headline_hi: str
    headline_en: str
    headline_te: str | None = None
    reasons: list[str]
    caveats: list[str]
    falsifiers_checked: list[str]
    rubric_version: str


class PolicyClause(BaseModel):
    clause_id: str
    doc: str
    page: int | None = None
    text: str
    applies_because: str | None = None
    url: str | None = None


class Deadline(BaseModel):
    type: Literal["intimation_72h", "recheck", "other"]
    due_at: datetime
    basis: str  # clause id
    status: Literal["open", "met", "lapsed"]


class Chip(BaseModel):
    kind: Literal["true_colour_pre", "true_colour_post", "ndvi_pre", "ndvi_post", "delta_map", "sar_change", "region_map"]
    path: str  # served by GET /artifacts/{path}
    scene_id: str | None = None
    date: Date | None = None
    bounds: tuple[float, float, float, float] | None = None  # lon/lat west, south, east, north


class ReplayCore(BaseModel):
    """Everything needed for anyone to recompute the numbers from public satellite archives."""
    engine_version: str
    polygon: dict
    event_date: Date
    optical_pre_id: str | None = None
    optical_post_id: str | None = None
    sar_pre_id: str | None = None
    sar_post_id: str | None = None
    history_scene_ids: list[str] = []
    scene_archives: dict[str, str] = {}  # scene id -> public archive it was read from
    seed: int
    numbers: dict[str, float | None]  # flat "field.path" -> value, rounded to 4 dp
    # sha256 of the level and its corroboration inputs. Checked for tampering, never recomputed.
    verdict_digest: str | None = None


class ScaleLevel(BaseModel):
    block_m: int  # 10, 100, 500, 1000, 3000
    plot_cell_value: float | None  # change at the block containing the plot centroid
    context_min: float | None = None
    chip_path: str | None = None  # served by GET /api/artifacts/{path}


class ScaleFade(BaseModel):
    """The same change map block-averaged to coarser cells. Our illustration, not YES-TECH output."""
    sensor: Literal["s2", "s1"]
    statistic: str  # e.g. "delta_ndvi" or "vh_change_db"
    bounds: tuple[float, float, float, float]  # lon/lat west, south, east, north
    levels: list[ScaleLevel]


class SurveyDraw(BaseModel):
    parcels: list[tuple[float, float]]  # lon/lat centres of the 10 parcels in this draw
    average: float


class SurveyLottery(BaseModel):
    """Para 21.5.8 simulated: 10 random parcels, averaged, repeated with a fixed seed."""
    n_simulations: int
    parcels_per_survey: int = 10
    statistic: str
    plot_value: float | None
    n_candidate_parcels: int
    average_median: float | None
    average_p05: float | None
    average_p95: float | None
    share_below_half_of_plot: float | None  # share of surveys whose average change is under half of this plot's
    # Second scenario: parcels drawn only from fields that visibly dropped, closer to who reports a loss.
    affected_only_n_candidates: int | None = None
    affected_only_median: float | None = None
    affected_only_p05: float | None = None
    affected_only_p95: float | None = None
    # Why that scenario is empty. Separate from insufficient_reason, which hides the whole Draw.
    affected_only_reason: str | None = None
    histogram_edges: list[float] = []
    histogram_counts: list[int] = []
    sample_draws: list[SurveyDraw] = []  # a few real draws, for the map animation
    seed: int
    insufficient_reason: str | None = None
    # Set by the backend from the claim path. Para 21.5.8 only governs localized/post-harvest claims.
    rule_applicability: Literal["may_apply", "illustration_only"] = "illustration_only"


class VillageWitness(BaseModel):
    radius_m: int
    sensor: Literal["s2", "s1"]
    n_cropland_pixels: int
    affected_share: float | None  # indicator only, not the legal 25%-of-insured-area test
    affected_definition: str
    nearby_real_cases: int | None = None  # filled by the backend from real cases only
    lottery: SurveyLottery | None = None


ClaimRoute = Literal[
    "not_insured", "localized_addon", "post_harvest_addon", "area_yield_basic", "outside_cover",
    "undetermined",
]


class ClaimPath(BaseModel):
    route: ClaimRoute
    insured: Literal["yes", "no", "unknown"] = "unknown"
    crop_stage: Literal["standing", "cut_and_spread", "harvested_stored", "unknown"] = "unknown"
    intimation: Literal["essential", "not_essential", "unknown"] = "unknown"
    countdown_applies: bool = False
    reasons: list[str] = []
    next_steps: list[str] = []
    evidence_use: str | None = None  # what this evidence is honestly useful for on this route
    unknowns: list[str] = []
    clause_ids: list[str] = []


class Evidence(BaseModel):
    scale_fade: ScaleFade | None = None
    village: VillageWitness | None = None
    claim_path: ClaimPath | None = None
    testimony_hi: str | None = None
    testimony_en: str | None = None
    testimony_te: str | None = None
    case_id: str
    run_id: str
    created_at: datetime
    plot: PlotInfo
    event: EventInfo
    optical: OpticalEvidence = Field(default_factory=OpticalEvidence)
    neighbours: NeighbourEvidence | None = None
    history: HistoryEvidence | None = None
    sar: SarEvidence | None = None
    weather: WeatherEvidence | None = None
    alerts: list[Alert] = []
    news: list[NewsItem] = []
    timeline: list[TimelinePoint] = []
    chips: list[Chip] = []
    cross_examination: list[Objection] = []
    verdict: Verdict | None = None
    policy: list[PolicyClause] = []
    deadlines: list[Deadline] = []
    explanation_hi: str | None = None
    explanation_en: str | None = None
    explanation_te: str | None = None
    llm_used: bool = False
    provenance: list[Provenance] = []
    replay: ReplayCore | None = None
    evidence_hash: str | None = None  # sha256 of canonical ReplayCore JSON


# SSE events on GET /runs/{id}/stream. `seq` is monotonic so a client can resume or replay.
TraceType = Literal[
    "step_started", "tool_called", "tool_result", "decision", "scene_rejected", "sensor_switch",
    "objection", "verdict", "action", "warning", "error", "done",
]


class TraceEvent(BaseModel):
    seq: int
    run_id: str
    ts: datetime
    type: TraceType
    node: str
    title_hi: str
    title_en: str
    detail: dict = {}
