// TEST FIXTURE ONLY. Synthetic values for checking layouts. Never imported by src/, never shipped.
const ring = [[75.03, 29.53], [75.0322, 29.53], [75.0322, 29.5318], [75.03, 29.5318], [75.03, 29.53]];
const days = ["2026-09-28", "2026-10-03", "2026-10-08", "2026-10-13", "2026-10-18", "2026-10-23", "2026-10-28", "2026-10-29"];
const SCENE = (d: string) => `S2B_MSIL2A_${d.replace(/-/g, "")}T053719_R105_T43RDM_TEST`;

function parcels(seed: number) {
  const out: [number, number][] = [];
  let x = seed * 9301 + 49297;
  const r = () => { x = (x * 9301 + 49297) % 233280; return x / 233280; };
  for (let i = 0; i < 10; i++) out.push([75.031 + (r() - 0.5) * 0.035, 29.531 + (r() - 0.5) * 0.03]);
  return out;
}

export const evidence = (over: Record<string, unknown> = {}) => ({
  case_id: "testcase0001", run_id: "testrun0001", created_at: "2026-10-30T10:00:00Z",
  plot: { geometry: { type: "Polygon", coordinates: [ring] }, area_ha: 4.31, centroid: [75.0311, 29.5309], crs: "EPSG:32643", warnings: [] },
  event: { type: "hail", date: "2026-10-25", date_source: "farmer", crop: "धान" },
  optical: {
    scenes_considered: [
      { id: SCENE("2026-10-23"), collection: "sentinel-2-l2a", date: "2026-10-23", status: "accepted", reasons: [], metadata_cloud_pct: 1.2, plot_valid_frac: 1.0 },
      { id: SCENE("2026-10-28"), collection: "sentinel-2-l2a", date: "2026-10-28", status: "rejected", reasons: ["infrared band invalid over the context window"], metadata_cloud_pct: 0, plot_valid_frac: 0 },
      { id: SCENE("2026-10-29"), collection: "sentinel-2-l2a", date: "2026-10-29", status: "accepted", reasons: [], metadata_cloud_pct: 3.1, plot_valid_frac: 0.98 },
    ],
    pre: { scene_id: SCENE("2026-10-23"), date: "2026-10-23", valid_frac: 1, n_pixels: 431, ndvi_median: 0.71, ndvi_p25: 0.66, ndvi_p75: 0.74 },
    post: { scene_id: SCENE("2026-10-29"), date: "2026-10-29", valid_frac: 0.98, n_pixels: 422, ndvi_median: 0.41, ndvi_p25: 0.33, ndvi_p75: 0.5 },
    plot_delta_ndvi: -0.3, drop_frac: 0.82, iqr_delta: 0.09, within_plot_pattern: "patchy", post_bare_fraction: 0.08,
  },
  neighbours: {
    ring_m: [300, 1500], n_comparable_pixels: 12042, neighbour_median_delta: -0.06, plot_minus_neighbour: -0.24, neighbour_bare_fraction_post: 0.11,
    placebo: {
      n_placebos: 200, n_at_least_as_extreme: 4, p_value: 0.0249, statistic: "median_delta_ndvi", plot_value: -0.3, placebo_median: -0.06, placebo_p05: -0.21, placebo_p95: 0.03,
      histogram_edges: [-0.34, -0.31, -0.28, -0.25, -0.22, -0.19, -0.16, -0.13, -0.1, -0.07, -0.04, -0.01, 0.02, 0.05, 0.08],
      histogram_counts: [1, 2, 1, 3, 4, 8, 15, 23, 34, 41, 33, 22, 10, 3], seed: 1234,
    },
    far_placebo: {
      n_placebos: 200, n_at_least_as_extreme: 0, p_value: 0.005, statistic: "median_delta_ndvi", plot_value: -0.3, placebo_median: -0.02, placebo_p05: -0.1, placebo_p95: 0.04,
      histogram_edges: [-0.32, -0.28, -0.24, -0.2, -0.16, -0.12, -0.08, -0.04, 0, 0.04, 0.08], histogram_counts: [0, 0, 0, 1, 3, 12, 40, 70, 55, 15, 4].slice(0, 10), seed: 1234,
    },
    pretrend_delta: 0.01,
    counterfactual: {
      n_control_pixels: 1520, pre_fit_rmse: 0.018, gap_at_post: -0.25, method: "matched pixels on the pre-event trajectory",
      series: days.map((d, i) => ({ date: d, observed: i === 6 ? null : [0.62, 0.66, 0.69, 0.71, 0.72, 0.71, 0, 0.41][i], expected: [0.63, 0.66, 0.68, 0.7, 0.71, 0.71, 0.68, 0.66][i], expected_low: [0.6, 0.63, 0.65, 0.67, 0.68, 0.68, 0.64, 0.61][i], expected_high: [0.66, 0.69, 0.71, 0.73, 0.74, 0.74, 0.72, 0.71][i] })),
    },
  },
  history: { years: [{ year: 2025, pre_scene_id: "A", post_scene_id: "B", pre_ndvi: 0.68, delta_ndvi: -0.05 }, { year: 2024, pre_scene_id: null, post_scene_id: null, pre_ndvi: null, delta_ndvi: null, note: "no clear pair" }], typical_delta: -0.05, excess_vs_history: -0.25, downweighted: false },
  sar: { usable: true, pre_scene_id: "S1A_A", post_scene_id: "S1A_B", pre_date: "2026-10-16", post_date: "2026-10-28", orbit_direction: "ascending", relative_orbit: 100, vh_change_db: -2.4, neighbour_vh_change_db: -0.3, vh_excess_db: -2.1, new_water_frac: 0.02, placebo: null },
  weather: {
    source: "Open-Meteo (test)", fetched_at: "2026-10-30T09:00:00Z", grid_note: "A gridded model at about 9 km can miss a small hail cell.",
    days: ["2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28"].map((d, i) => ({ date: d, precip_mm: [0, 0, 1.2, 18.4, 3.1, 0, 0][i], gust_kmh: 40, weather_code: 3 })),
    precip_mm_event_window: 21.5, max_daily_mm: 18.4, hail_code_hours: 2, thunder_hours: 5, max_gust_kmh: 62, corroborated: true,
  },
  alerts: [], news: [],
  timeline: [
    ...days.map((d, i) => ({ date: d, sensor: "s2", ndvi: i === 6 ? 0.03 : [0.62, 0.66, 0.69, 0.71, 0.72, 0.71, 0, 0.41][i], qa: i === 6 ? "rejected" : "accepted" })),
    ...["2026-10-04", "2026-10-16", "2026-10-28"].map((d, i) => ({ date: d, sensor: "s1", vh_db: [-16.2, -15.7, -18.1][i], vv_db: -9 })),
  ],
  chips: [
    { kind: "true_colour_pre", path: "test/true_colour_pre.png", scene_id: SCENE("2026-10-23"), date: "2026-10-23", bounds: [75.028, 29.528, 75.034, 29.534] },
    { kind: "true_colour_post", path: "test/true_colour_post.png", scene_id: SCENE("2026-10-29"), date: "2026-10-29", bounds: [75.028, 29.528, 75.034, 29.534] },
    { kind: "ndvi_pre", path: "test/ndvi_pre.png", scene_id: SCENE("2026-10-23"), date: "2026-10-23", bounds: [75.028, 29.528, 75.034, 29.534] },
    { kind: "ndvi_post", path: "test/ndvi_post.png", scene_id: SCENE("2026-10-29"), date: "2026-10-29", bounds: [75.028, 29.528, 75.034, 29.534] },
    { kind: "region_map", path: "test/region_map.png", scene_id: SCENE("2026-10-29"), date: "2026-10-29", bounds: [74.9, 29.42, 75.15, 29.64] },
    { kind: "delta_map", path: "test/delta_map.png", scene_id: SCENE("2026-10-29"), date: "2026-10-29", bounds: [75.012, 29.515, 75.05, 29.548] },
  ],
  cross_examination: [
    { id: "harvest", challenge_hi: "यह नुकसान नहीं, कटाई है। फ़सल कट गई तो हरियाली तो घटेगी ही।", challenge_en: "This isn't damage, it's harvest. Of course greenness falls once a crop is cut.", test: "Bare fraction after the event > 0.5 and uniform pattern, and comparable neighbours also bare.", measured: { post_bare_fraction: 0.08, within_plot_pattern: "patchy", neighbour_bare_fraction_post: 0.11, history_typical_delta: -0.05, excess_vs_history: -0.25, history_downweighted: false }, outcome: "rebutted", finding_hi: "कटाई जैसा नहीं दिखता: खेत का 8% हिस्सा ही खाली मिट्टी है।", finding_en: "This does not look like harvest: only 8% of the plot is bare." },
    { id: "regional_trend", challenge_hi: "पूरे इलाके में ऐसा हुआ होगा।", challenge_en: "The whole area must have fallen.", test: "Placebo test against same-shape plots.", measured: { p_value: 0.0249, neighbour_median_delta: -0.06 }, outcome: "rebutted", finding_hi: "आस-पास के 200 में से 4 ही इतना गिरे।", finding_en: "Only 4 of 200 nearby fell this much." },
    { id: "wrong_date", challenge_hi: "तारीख़ पक्की है?", challenge_en: "Are you sure of the date?", test: "Compare the weather peak with the reported date.", measured: { max_daily_mm: 18.4, proposed_event_date: null }, outcome: "unresolved", finding_hi: "तारीख़ की पूरी पुष्टि नहीं हो सकी।", finding_en: "The date could not be fully confirmed." },
  ],
  verdict: { level: "strong", headline_hi: "आपके खेत में हरियाली ऐसी गिरी जो नुकसान से मेल खाती है, और यह आसपास से अलग है।", headline_en: "Your field lost greenness in a way consistent with damage, unlike the fields around it.", headline_te: "మీ పొలంలో పచ్చదనం నష్టంతో సరిపోయేలా తగ్గింది, చుట్టుపక్కలకు భిన్నంగా.", reasons: ["plot NDVI change -0.30 (threshold -0.15)", "optical placebo p = 0.025 (threshold 0.05)", "corroborated by weather", "accepted optical scenes before and after", "no objection conceded"], caveats: ["This is evidence consistent with damage, not a claim decision. Crop-cutting and insurer assessment remain separate."], falsifiers_checked: ["harvest", "regional_trend", "wrong_date"], rubric_version: "v2" },
  policy: [
    { clause_id: "21.5.8", doc: "PMFBY Operational Guidelines 2023 (effective Kharif 2023)", page: 105, url: "https://pmfby.amnex.co.in/pmfby/pdf/operational_guidelines_pmfby.pdf", text: "the sample loss survey will be conducted at 10 different randomly selected crop-land parcels" },
    { clause_id: "21.5.5.1", doc: "PMFBY Operational Guidelines 2023 (effective Kharif 2023)", page: 103, text: "Immediate intimation (within 72 hours) by the insured farmer as detailed in Para 21.5.5.4 below." },
  ],
  deadlines: [{ type: "intimation_72h", due_at: new Date(Date.now() + 41 * 3600 * 1000).toISOString(), basis: "21.5.5.1", status: "open" }],
  explanation_hi: "आपके खेत की हरियाली 25 अक्टूबर के बाद गिरी, जबकि आसपास के ज़्यादातर खेतों में ऐसा नहीं हुआ।",
  explanation_en: "Your field's greenness fell after 25 October, while most fields around it did not.",
  explanation_te: null,
  llm_used: false,
  provenance: [{ field: "optical.plot_delta_ndvi", source: "Microsoft Planetary Computer, Sentinel-2 L2A", asset: "B04,B08", url: "https://planetarycomputer.microsoft.com", retrieved_at: "2026-10-30T09:00:00Z" }],
  replay: { engine_version: "test", polygon: { type: "Polygon", coordinates: [ring] }, event_date: "2026-10-25", history_scene_ids: [], seed: 1234, numbers: { "optical.plot_delta_ndvi": -0.3, "neighbours.placebo.p_value": 0.0249 } },
  evidence_hash: "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
  scale_fade: {
    sensor: "s2", statistic: "delta_ndvi", bounds: [75.012, 29.515, 75.05, 29.548],
    levels: [10, 100, 500, 1000, 3000].map((b, i) => ({ block_m: b, plot_cell_value: [-0.3, -0.27, -0.14, -0.09, -0.06][i], context_min: [-0.5, -0.42, -0.2, -0.12, -0.08][i], chip_path: `test/fade_${b}.png` })),
  },
  village: {
    radius_m: 3000, sensor: "s2", n_cropland_pixels: 84210, affected_share: 0.14, affected_definition: "NDVI change below -0.15 and not bare after the event", nearby_real_cases: null,
    lottery: {
      n_simulations: 1000, parcels_per_survey: 10, statistic: "mean_delta_ndvi", plot_value: -0.3, n_candidate_parcels: 2200, average_median: -0.07, average_p05: -0.13, average_p95: -0.02, share_below_half_of_plot: 0.97, affected_only_n_candidates: 300, affected_only_median: -0.245, affected_only_p05: -0.28, affected_only_p95: -0.21,
      histogram_edges: Array.from({ length: 19 }, (_, i) => Number((-0.2 + i * 0.012).toFixed(3))),
      histogram_counts: [2, 4, 8, 15, 30, 52, 88, 121, 148, 152, 131, 98, 66, 42, 24, 12, 5, 2],
      sample_draws: [0, 1, 2, 3, 4, 5].map((s) => ({ parcels: parcels(s + 1), average: [-0.05, -0.11, -0.07, -0.03, -0.09, -0.06][s] })),
      seed: 1234, rule_applicability: "may_apply",
    },
  },
  claim_path: {
    route: "localized_addon", insured: "yes", crop_stage: "standing", intimation: "essential", countdown_applies: true,
    reasons: ["Hail is a listed localized peril when the State has notified the add-on cover."], next_steps: ["Give intimation through the Crop Insurance App, KRPH 14447, your bank, or the agriculture office.", "Keep the reference number."],
    evidence_use: "Something to show an officer, and to support a request for an individual survey.", unknowns: ["Whether your State notified this add-on cover for this crop."], clause_ids: ["21.5.5.1"],
  },
  testimony_hi: "मैं आपका खेत हूँ। 23 अक्टूबर को उपग्रह ने मुझे देखा, तब मैं हरा था। 25 अक्टूबर के बाद मेरी हरियाली गिरी, और 29 अक्टूबर को मैं बदला हुआ दिखा। आसपास के ज़्यादातर खेतों में ऐसा नहीं हुआ। यह नुकसान से मेल खाता है; कारण मैं पक्का नहीं बता सकता।",
  testimony_en: "I am your field. On 23 October the satellite saw me, and I was green. After 25 October my greenness fell, and on 29 October I looked changed. Most fields around me did not. This is consistent with damage; I cannot state the cause for certain.",
  testimony_te: null,
  ...over,
});
