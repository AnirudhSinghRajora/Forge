# 03 — Evidence Engine (Owner A, reviewed by B)

> **Superseded in part.** This file is an early working draft and some claims here were later corrected against the official guidelines and real data. For current facts see [`docs/submission/facts.md`](../submission/facts.md), and for the current design see [`docs/plan/07-build-contract.md`](07-build-contract.md).

This is the heart of FasalSaakshi and what the judges will probe. Rule: **numbers come from deterministic code. Gemini only interprets them.**

## 0. Spike findings (31 Oct 2026, scripts in [`/spikes`](../../spikes))

| Finding | Detail | Consequence for the design |
|---|---|---|
| **Corrupted scene that looks perfect in metadata** | Sentinel-2 pass of **2026-10-28** (tiles 43REN, 43RDN) has `eo:cloud_cover` ≈ 0% and SCL classes look normal (vegetation/soil). But over Sirsa, B02/B08/B11 are empty and B03/B04 ≈ 74–192 DN (garbage). Over Fatehabad the bands exist, but NDVI ≈ 0.00 everywhere. | **Mandatory radiometric QA (§2).** Without it, the agent would report "100% of crop destroyed". |
| **Harvest looks like damage** | 2025, Sirsa (no reported event): median NDVI 0.60 (18 Oct) → 0.58 (20 Oct) → 0.51 (23 Oct). The share of pixels < 0.25 rose from 17% to 20%. | Before/after alone is meaningless in harvest season. **Neighbour + history comparison is the key discriminator (§5, §6).** |
| **Reflectance offset** | Processing baselines 05.11 (2025) and 05.13 (2026) carry the +1000 DN offset (baselines ≥ 04.00). | `reflectance = (DN − 1000) / 10000`. Read the baseline per item and never hardcode. Skipping this distorts NDVI badly. |
| **Radar is clean** | Sentinel-1 RTC over Sirsa: 12 Oct (desc), 16 Oct (asc), 24 Oct (desc), 28 Oct (asc). Median VV ≈ −9.3 to −10.0 dB, VH −15.2 to −16.3 dB, no NaNs. Water-like pixels (VV < −18 dB) ~0.5%, so no widespread inundation. | SAR is the reliable post-event source right now. Use **same-orbit pairs only** (16 Oct asc vs 28 Oct asc). |
| **Optical cadence** | Clear/usable passes over Sirsa: 13, 18 Oct (good); 15, 23 Oct (partly cloudy); 28 Oct (corrupt). **The next pass is expected ~2 Nov.** | The scheduled re-check (P1) has a real chance to fire *during* the hackathon. If 2 Nov is clean, that's the demo's "agent updated your evidence automatically" moment. |
| **No Oct 30 pass over Sirsa** (an Oct 30 pass exists further east, around 76.08 E) | Orbit coverage differs across the district | Always search by plot geometry, never by assumed dates |

## 1. Inputs and windows
- Plot polygon (WGS84). Reproject to the local UTM zone. **Erode by 10 m** (1 pixel) to drop mixed edge pixels, unless that leaves fewer than 20 pixels.
- Event date `E` (from the farmer's report; if unknown, from weather or alerts; else ask).
- Windows: pre = `[E−25 d, E]`, post = `[E+1 d, min(E+20 d, today)]`, context = 1.5 km buffer around the plot.
- Plot-size rules: < 0.2 ha → warn ("too small for reliable satellite evidence; photo evidence advised") and still compute. 10 m bands (B02, B03, B04, B08) for everything plot-level. 20 m bands (B05, B8A, B11) only if the plot is ≥ 0.5 ha.

## 2. Scene quality assurance (mandatory)

Every candidate scene runs these checks over the **context window** (plot + 1.5 km). The result is cached in `scene_cache`.

| Check | Rule (initial thresholds; tune on calibration) | Fails on 28 Oct? |
|---|---|---|
| Q1 Assets | B02, B03, B04, B08, SCL present and readable (plus B05, B8A, B11 if needed) | Yes (Sirsa: B02/B08/B11 empty) |
| Q2 Plot validity | Share of plot pixels with SCL ∈ {4 vegetation, 5 bare soil} ≥ 0.80. Exclude SCL 3 (shadow), 8/9 (cloud), 10 (cirrus), 0/1 (nodata/saturated). | No (SCL looks fine, which is why Q3–Q5 exist) |
| Q3 Radiometric range | After offset: context median B08 ∈ [0.05, 0.60], B04 ∈ [0.01, 0.40]; NaN/zero share < 5% | Yes |
| Q4 Physical plausibility | Over SCL = 4 (vegetation) pixels in context: median NDVI ≥ 0.30 | **Yes** (≈ 0.0) |
| Q5 Temporal consistency | Context median NDVI shift vs. the previous accepted scene: \|Δ\| ≤ 0.35 within 10 days. Otherwise mark **suspect** and require SAR or another optical scene to confirm. | Yes |

Outcomes: `accepted` / `suspect` / `rejected`, with reasons. These go into the Evidence JSON and are **shown in the UI trace** ("Rejected 28 Oct image: infrared band invalid. Satellite data errors happen; falling back to radar."). That line is a strong agentic-robustness moment for judges.

## 3. Indices (after offset correction)

| Index | Formula (S2 bands) | Use |
|---|---|---|
| NDVI | (B08 − B04)/(B08 + B04) | Primary greenness |
| NDRE | (B8A − B05)/(B8A + B05) | Canopy chlorophyll; less saturated in dense canopy (≥ 0.5 ha plots) |
| NDMI | (B8A − B11)/(B8A + B11) | Canopy water/structure; lodging and leaf loss |
| BSI | ((B11 + B04) − (B08 + B02)) / ((B11 + B04) + (B08 + B02)) | Bare soil, i.e. **harvest detection** |

## 4. Pre/post selection and plot statistics
- **pre** = latest `accepted` scene in the pre window. **post** = earliest `accepted` scene in the post window. If post is missing, go to SAR (§7) and schedule a re-check for the next pass.
- Plot stats per scene: median, p25, p75 of each index; valid fraction.
- Change: `d = post − pre` per pixel (same grid; odc-stac loads both onto one grid).
- `plot_delta_ndvi` = median(d). `drop_frac` = share of pixels with d ≤ −0.15.
- **Within-plot pattern:** `patchy` if 0.2 ≤ drop_frac ≤ 0.8 and IQR(d) ≥ 0.12 (hail and lodging are often uneven); `uniform` if drop_frac > 0.8 and IQR(d) < 0.12 (typical of harvest or a whole-field event); `none` otherwise.
- `post_bare_fraction` = share of plot pixels with NDVI < 0.25 and BSI > 0 in post.

## 5. Neighbour comparison: the key discriminator
- Ring: 300 m to 1.5 km from the plot edge.
- **Comparable neighbours only:** pixels that were cropland at a similar stage before the event, i.e. pre NDVI within ±0.15 of the plot's pre median, and SCL valid in both scenes.
- Compute the neighbour distribution of d. Report:
  - `neighbour_median_delta`
  - `plot_minus_neighbour` = plot_delta_ndvi − neighbour_median_delta
  - `plot_percentile` = share of neighbour pixels whose d is *less negative* than the plot median (higher means the plot dropped more than its neighbours)
- Interpretation:
  - A plot that drops much more than similar neighbours on the same dates points to **localized damage**. Harvest happens across the area, so it shifts neighbours too.
  - If neighbours dropped just as much, it's a **regional event or regional harvest**. Use weather and history to tell them apart.

## 6. History baseline
- Same plot polygon, same calendar windows (pre/post) in **2024 and 2025**, using the same QA and stats.
- `history_deltas` = the plot's typical change in this calendar window. If this year's drop exceeds history by ≥ 0.10, the drop is **unusual for this field at this time of year**.
- Caveat: crop rotation may differ between years. If the history pre-NDVI differs a lot from this year's (> 0.2), down-weight this signal and say so.

## 7. Sentinel-1 SAR fallback and corroboration
- Search `sentinel-1-rtc`. Pick **same relative orbit and pass direction** pre/post (e.g. 16 Oct asc → 28 Oct asc).
- Convert to dB. Use the plot median (RTC is already terrain-corrected; apply a median filter or Lee filter if time allows).
- Signals:
  - **Inundation/waterlogging:** VV < −18 dB share in plot (tune the threshold with Otsu on context).
  - **Structural change (lodging / leaf loss / harvest):** ΔVH and Δ(VH−VV) vs. neighbours, using the same comparable-neighbour logic as §5 with pre-optical stage selection.
- SAR alone gives at most **moderate** confidence. It corroborates; it doesn't decide.

## 8. Self-check falsifiers

Run in code, and also reasoned over by Gemini.

| Falsifier | Test | Effect |
|---|---|---|
| Corrupted / suspect scene | QA status | Exclude the scene; try alternatives |
| Cloud shadow / haze residue | Valid fraction < 0.8 or SCL 3 present at the plot | Exclude, or downgrade one level |
| **Normal harvest** | `post_bare_fraction` > 0.6 AND pattern `uniform` AND neighbours also show rising bare fraction AND history shows a similar drop | Verdict → `not_damage_likely_harvest`, with explanation. If the farmer says the crop was still standing, ask: "did you harvest after the event?" |
| Wrong plot | Pre NDVI < 0.3 (no crop before) | Ask the farmer to re-check the boundary |
| Event date mismatch | Weather shows no rain/hail within ±3 days of `E`, but does at another nearby date | Propose the corrected date; re-run |
| Too small | < 0.2 ha | Caveat + recommend photo evidence |

## 9. Weather, alerts, news

| Signal | Source | Rule |
|---|---|---|
| Rain | Open-Meteo historical-forecast/archive hourly `precipitation` at the plot centroid, E−2 … E+2; NASA POWER daily `PRECTOTCORR` fallback | ≥ 10 mm/day, or ≥ 20 mm over the window, counts as "heavy rain corroborated" |
| Hail proxy | Open-Meteo `weather_code` 96/99 (thunderstorm with slight/heavy hail) | Any hour → "hail-conducive storm modelled". Wording: *model-indicated*, not observed. |
| Official alerts | Our SACHET archive (from day 1); for past events, IMD district warnings found via news search | Supporting only |
| News (P1) | Gemini + Google Search grounding: "<event> <district> <date range>" | Supporting only. Never proof for an individual plot. Cite URLs. |

## 10. Verdict rubric (implemented in code; Gemini writes the explanation)

| Level | Conditions (all must hold) |
|---|---|
| **strong** | Accepted pre & post optical; plot_delta_ndvi ≤ −0.15; plot_minus_neighbour ≤ −0.10; plot_percentile ≥ 90; not flagged harvest; weather corroborated (rain or hail code) |
| **moderate** | Weather corroborated AND (optical anomaly vs neighbours meeting 2 of the 3 optical thresholds above, OR SAR anomaly vs neighbours ≥ 1.5 dB VH with the same-orbit pair, OR inundation share ≥ 0.2) |
| **weak** | Weather corroborated but no plot-specific anomaly, OR a plot anomaly without weather corroboration |
| **not_damage_likely_harvest** | Harvest falsifier fires (§8) |
| **insufficient** | No accepted post optical AND no usable SAR pair. Schedule a re-check and tell the farmer when the next pass is expected. |

Every verdict carries `reasons[]` (which conditions passed, with values), `caveats[]`, and `falsifiers_checked[]`. Language rules: "your satellite evidence is **consistent with** hail damage", never "you will receive a claim".

## 11. Calibration protocol (H6–H14, Owner A)

There's **no ground-truth label set**. Say this openly; it's a strength in Q&A when backed by this protocol.

1. **False-positive rate on a normal window:** sample 300 random 1–2 ha squares over cropland around Sirsa for 18 → 23 Oct **2025** (no reported event). Run the rubric with weather gating *off*. Target: < 5% "strong/moderate" from optical criteria alone. Tune the neighbour thresholds until this holds. Report the measured rate in the README.
2. **Positive checks:** find **2–3 documented localized events** (hail or waterlogging) in Haryana/Punjab with named villages and dates (Tribune / Dainik Bhaskar / district agriculture notices, e.g. via Gemini Search grounding). Draw plots in those villages and check that the engine flags anomalies vs. neighbours. Record outcomes honestly, including misses.
3. **Current event:** run Sirsa/Fatehabad villages named in the 25 Oct 2026 reports, using SAR now and optical once the ~2 Nov pass lands.
4. Freeze thresholds at **G3** and record them in the README with the calibration results.

## 12. Tests
- Unit tests for index math, offset handling, QA rules, and the rubric, using **small real rasters saved from live API calls** (test fixtures are allowed in *tests*, never in the running app).
- A **regression test that the 2026-10-28 scene is rejected** by QA.
- Live smoke test: `python -m app.tools.geo.smoke --lat 29.53 --lon 75.03` prints QA + stats in < 30 s.
