# Geo engine: results on real data

Last updated 31 Oct 2026, by the GEO owner. Engine version `geo-1.1.0`. Every number here came from running the engine on public Sentinel archives. Scripts are in `backend/tests/` (`geo_*.py`). Raw per-plot output and maps are in `backend/var/geo_validation/` and are not committed.

**There is no plot-level ground truth for any event here.** News and official reports give villages and district-level loss bins. This work can show consistency, not accuracy.

## Status

| Item | Result |
|---|---|
| Sirsa 28 Oct 2026 corrupted pass | Rejected, despite about 0% metadata cloud |
| False-positive rate, design window | p<=0.05 at 5.0%. p<=0.10 at 15.4%, above nominal, so that tier was removed from the rubric |
| Bhiwani hail 2024 | A coherent band, consistent with a hail swath. It does not repeat in other years. Radar does not confirm it |
| Cyclone Arnab | No signal established. One optical scene after landfall. Next radar about 4 Nov |
| Rubric v3 false positives, locked | 2.0% strong and 2.5% moderate field conditions, on both no-event windows |
| Independent event (Sirsa hail 14 Mar 2025) | No signal. Consistent with "minor" damage, so not a positive test. Sensitivity is shown only on Bhiwani, the design event |
| Cold read time | Well over target on this machine. See "Read time" |

## 1. Scene QA regression

Pass of 28 Oct 2026 over Sirsa (75.03 E, 29.53 N), `S2B_MSIL2A_20261028T053929_R005_T43REN_20261028T092239`, metadata cloud 0.001%:

- **Rejected.** `Q3: infrared band (B08) median reflectance -0.087 is outside [0.05, 0.60]`, the same for red (B04), and `Q4: pixels classified as vegetation have median NDVI undefined`.
- Scene classification looks normal over the plot (valid fraction 1.0), which is why Q3 and Q4 exist.
- Live test: `tests/test_geo_live.py`.

## 2. False-positive rate (design window)

Sirsa, `S2C_MSIL2A_20251018T053841_R005_T43REN_20251018T085916` to `S2B_MSIL2A_20251023T053809_R005_T43REN_20251023T075858`, no reported event. 300 random squares of 1-2 ha on ESA WorldCover 2021 cropland, in an 18 km region east of Sirsa town. Scripts: `geo_fpr_sirsa.py`, `geo_fpr_report.py`.

| Method | Plots | p<=0.05 | p<=0.10 | Uniform standing crop p<=0.05 | Uniform standing crop p<=0.10 |
|---|---|---|---|---|---|
| Placebos match pre-event median only | 300 | 5.3% (CI 3.3-8.5) | 13.0% (CI 9.7-17.3) | 8.2% | 20.4% |
| Median and pre-event IQR (current) | 299 | **5.0%** (CI 3.1-8.1) | **15.4%** (CI 11.7-19.9) | 7.1% | 18.4% |

**What changed and why.** My first hypothesis was that NDVI change depends on the starting level. The data rejected it: change does depend on level (Spearman -0.45), but the p-value does not (-0.05, not significant). The real driver was within-plot uniformity: p<=0.10 fell from about 21% for uniform plots to 3.5% for mixed ones (p vs IQR Spearman 0.16, p=0.006). So placebos must now also match the plot's pre-event IQR within 0.05, which removed that gradient (Spearman -0.02, p=0.73).

**What it did not fix.** p<=0.10 still over-rejects. That tier was removed in rubric v3 and the threshold moved to p<=0.025 across two tests. These thresholds were set after seeing this window, which is why the holdout below exists.

**Why these confidence intervals are too narrow.**
- One scene pair, so all plots share that pair's conditions.
- Plots and placebos sit in the same region and are spatially correlated.
- Placebos beyond the non-overlapping ones overlap each other and are correlated. `n_non_overlapping` reports how many do not. Here 81% of plots had every placebo non-overlapping; the median was 200 and the lowest quartile below 156.

**What random squares cannot show.** A square lies across field boundaries. A real plot follows one field, so it can move as a unit more than a square does. Matching on uniformity narrows this gap without proving it closed.

## 3. Hail, 2-3 March 2024, Bhiwani and Hisar

Reports: `docs/validation/events.md` C1. Farmers named Maneharu among villages "completely destroyed" (a claim). A Congress leader said no insurer covered Hisar that season, so this is a signal case, not a PMFBY claim case.

### 3a. What the scan looked at

200 random squares of 1-2 ha on cropland in a 14 km window around the named villages. Pre `S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503`. Scripts: `geo_event_scan.py`, `geo_scan_report.py`.

| Post scene | Plots usable | Median change | Change <= -0.15 | Ring p<=0.05 | Both |
|---|---|---|---|---|---|
| 4 Mar 2024 | 165 of 200 (35 clouded) | +0.003 | 0.0% | 3.6% | 0.0% |
| 9 Mar 2024 | 200 | -0.031 | 5.5% (11) | 4.5% | 1.5% (3) |
| 14 Mar 2024 | 200 | -0.065 | 9.5% | 2.0% | 2.0% |

**Across the whole window the ring test sits at its no-event rate.** It fired on few of the plots that visibly dropped, because the ring shares the damage. This is the low power that led to the far test.

**The named points.** A plot at Umrawat (28.76654, 76.18455) on 4 Mar shows nothing: NDVI 0.8325 to 0.8276, ring p 0.64, VH +0.29 dB (p 0.39). Umrawat and Dhareru lie outside the band. This is not evidence against those farmers: this was one 1.4 ha square on one date, and hail is patchy.

### 3b. The band

The 28 Feb to 9 Mar map shows a coherent SW-NE band, about 2-3 km wide and over 15 km long, with damage visible field by field. Maneharu sits on its edge. The most extreme plots of the random scan fell beside Maneharu without the scan being aimed there, which is an independent cross-check against the farmers' report. It is still only consistent with hail. Nobody has checked these fields.

### 3c. Attacking the band (`geo_c1_controls.py`)

Could this be ordinary mustard ripening on the region's SW-NE dunes, repeating every year? The band mask was defined once from the 9 Mar 2024 map (6.9% of the window). Median NDVI change on green pixels (pre NDVI >= 0.5), band minus far field:

| Pair | Band | Far | Contrast |
|---|---|---|---|
| 23 to 28 Feb 2024, before the hail | +0.010 | +0.001 | **+0.008** |
| 28 Feb to 4 Mar 2024 | -0.068 | -0.003 | **-0.066** |
| 28 Feb to 9 Mar 2024 (defines the mask, so inflated by selection) | -0.177 | -0.031 | **-0.146** |
| 28 Feb to 14 Mar 2024 | -0.232 | -0.071 | **-0.161** |
| 28 Feb to 10 Mar 2022 | -0.067 | -0.092 | +0.025 |
| 23 Feb to 5 Mar 2023 | -0.068 | -0.094 | +0.027 |
| 5 to 10 Mar 2023 | -0.065 | -0.072 | +0.007 |
| 4 to 14 Mar 2025 | -0.019 | -0.071 | +0.052 |

- **The band does not repeat.** In other years this strip drops less than its surroundings. The 2022 map on the same dates shows scattered single fields, which is what ordinary ripening looks like.
- **It begins at the right time.** The contrast is flat before the hail, and has already moved 1-2 days after it.
- **Pre-event greenness is similar** inside and outside (0.74 and 0.71).
- **It cannot rule out** a crop pattern specific to 2024. We have no crop-type or field data.

**Radar does not confirm it.** VH contrast is +0.50 dB ascending (22 Feb to 5 Mar) and -0.47 dB descending (25 Feb to 8 Mar). The orbits disagree. At the extreme plot VH is +1.17 dB, p 0.66. This is a real miss.

### 3d. The extreme plot (selected: strongest of 200 scanned)

28.700911 N, 76.215719 E, 113 m square.

- NDVI 0.7525 to 0.3857, change -0.3689, every pixel down at least 0.15, no bare soil.
- Series: 0.7566 (23 Feb), 0.7525 (28 Feb), 0.6069 (4 Mar), 0.3857 (9 Mar), 0.3396 (14 Mar), 0.284 (19 Mar).
- Field twin: expected 0.5665, gap -0.1808. Pre-fit RMSE 0.0008, but on only 2 pre-event scenes.
- Ring p 0.0348. Far p 0.005 (200 placebos, far median -0.0508). Pre-trend +0.0074.
- Same plot, same window in other years: -0.0365 (2022), -0.1753 (2023). Excess vs history -0.263.

These are design data. The far test and the post-scene rule were designed after seeing this event (see section 6).

### 3e. Distribution across in-band plots (`geo_band_distribution.py`)

40 plots with centres drawn at random from the band mask, with at least 80% WorldCover cropland (67 tried). **The pre-event NDVI >= 0.5 filter I intended was not applied**, so some plots may not have been green. That may explain a minimum plot change of -0.005.

| Measure (per plot) | Min | p25 | Median | p75 | Max |
|---|---|---|---|---|---|
| Plot change | -0.342 | -0.156 | **-0.125** | -0.109 | -0.005 |
| Block 100 m | -0.340 | -0.161 | -0.131 | -0.118 | -0.020 |
| Block 500 m | -0.265 | -0.162 | -0.134 | -0.119 | -0.096 |
| Block 1 km | -0.160 | -0.132 | -0.128 | -0.120 | -0.093 |
| Block 3 km | -0.109 | -0.092 | **-0.085** | -0.079 | -0.071 |
| Draw, all cropland: average | -0.097 | -0.072 | **-0.069** | -0.065 | -0.028 |
| Draw, all cropland: p05-p95 width | 0.039 | 0.068 | 0.072 | 0.077 | 0.111 |
| Draw, only visibly dropped: average | -0.264 | -0.252 | **-0.245** | -0.242 | -0.228 |
| Draw, only visibly dropped: width | 0.051 | 0.062 | 0.067 | 0.071 | 0.079 |
| Share of draws under half the plot's drop | 0.036 | 0.289 | 0.492 | 0.648 | 0.994 |
| Affected share within 3 km | 0.001 | 0.114 | 0.130 | 0.177 | 0.255 |

85% of in-band plots moved at least -0.10, and 32.5% at least -0.15. 2 of 40 Draws returned `insufficient_reason`. 6 of 40 had too few visibly dropped parcels for the second scenario.

**What this says.**
1. **The typical plot barely fades until 3 km,** where about a third of the signal goes (3 km value is a median 0.67 of the plot's own change). The -0.369 to -0.098 fade belongs to the strongest of 200 plots.
2. **The two Draw scenarios are bounds, not an estimate.** Across plots the all-cropland average has a median of -0.069 and the only-dropped average a median of -0.245, with a sampling spread of about 0.07 within each. Parcels in the second scenario are at or below -0.15 by construction, so its average must be too, and the gap between the scenarios is partly built in. It is not a measured effect of who reports. The real intimation list lies somewhere between, and we do not know where.

**Typical demo plot, by rule (median of the 40 by plot change):** 28.715212 N, 76.231138 E, 104.7 m square. Plot change -0.1259. Blocks: -0.1233 (100 m), -0.1196 (500 m), -0.1300 (1 km), -0.0811 (3 km). Draw, all cropland: -0.0654 (p05 -0.1067, p95 -0.0335). Draw, only dropped: -0.2382 (p05 -0.2653, p95 -0.2141), from 37 parcels. Affected share 0.2034.

The Draw draws from cropland, not the real intimation list. It uses a satellite index, not assessed loss. Its share is an indicator, not the legal 25% test. Random sampling is unbiased on average: the Draw shows how far one average can move, never that the rule is unfair.

## 4. Cyclone Arnab

Landfall 02:00-08:00 IST on 28 Oct 2026 near 16.45 N, 81.90 E.

### What exists

| Source | Pass | Status |
|---|---|---|
| Sentinel-2 | 26 Oct (47%) | Latest before landfall |
| Sentinel-2 | **31 Oct, S2C (tile 44QND, 40%)** | On Earth Search at time of writing, not yet on Planetary Computer |
| Sentinel-2 | About 2 Nov (S2A, orbit 119) | Expected from the repeat pattern, not confirmed |
| Sentinel-1 RTC | 23 Oct, desc, orbit 19 | Latest over the delta. Before landfall |
| Sentinel-1 | 28 Oct, S1D, orbit 92 | EW mode (coarse wide swath), no RTC, not comparable with its IW history |
| Sentinel-1 | 31 Oct, S1C, asc, orbit 56 | IW GRD upstream. Footprint reaches only the NE corner. **Planetary Computer's RTC has carried only S1D over India since 20 Oct**, and no pre-event partner was found on this orbit |
| Sentinel-1 RTC | **About 4 Nov, S1D, orbit 19** | Next usable radar, from the 12-day repeat. After the deadline |

### What the 31 Oct image shows (whole tile at 160 m, from overviews, not plot statistics)

- Clear land 23.8% of the tile, broken by popcorn cumulus. 44% cloud or cirrus. Clear in both scenes: 15-17%.
- Land that became water: 3.7% of clear pixels against 23 Oct, 2.0% against 26 Oct. Most water on the map was already there, probably aquaculture ponds (not confirmed).

Median NDVI change on clear green pixels by longitude:

| Pair | All | 81.0-81.2 E | 81.8-82.03 E |
|---|---|---|---|
| **2026** 26 to 31 Oct | -0.092 | -0.069 | -0.135 |
| 2024 26 to 31 Oct | -0.083 | -0.051 | -0.101 |
| **2026** 23 to 31 Oct | -0.112 | -0.011 | -0.153 |
| 2024 21 to 31 Oct | -0.085 | -0.083 | -0.103 |
| 2023 22 Oct to 1 Nov | -0.104 | -0.102 | -0.127 |

**No Arnab signal is established.** About -0.1 is the normal drop for these weeks, mildly stronger in the east every year. The excess is about 0.03-0.05 in the east. The 23 Oct scene has its own opposite gradient against 11 Oct (+0.089 east, -0.031 west), and in 2026 red and NIR both rose, which fits haze better than crop loss. The fall in SCL vegetation from 41% to 4% while land NDVI stays at 0.54 should not be quoted as crop loss.

**This does not contradict reports of flattened paddy.** Lodged paddy can stay green, this is 3 days after landfall, and a harvest was due within days. 2025 was not used as a control because Cyclone Montha hit the same delta on 28 Oct 2025. A 10 m scan was started and stopped to free bandwidth for the locked runs; it has no results.

For an event wider than 12 km the far test loses power too, so history and the pre-event trend carry such a case.

### Earth Search fallback

Planetary Computer stays primary. On identical pixels of the same pass, PC minus Earth Search is **exactly 1000 DN** on B04, B08 and B11, and 0 on SCL. So Earth Search has already removed the offset, as `earthsearch:boa_offset_applied` says. Its `raster:bands` metadata still says `offset: -0.1`, and trusting it would subtract the offset twice. The engine uses the flag, and treats a missing flag as an error. A scene id names its archive, and `ReplayCore.scene_archives` records it.

## 5. Sirsa and Fatehabad, 24 Oct 2026 (hard case)

The storm was the evening of Saturday 24 Oct. **The 24 Oct Sentinel-1 pass was at 00:59 UTC (06:29 IST), about 12 hours before it, so it is pre-event.** The first true post-event radar is 28 Oct, 13:03 UTC, ascending, orbit 100, which pairs with 16 Oct on the same orbit. The first optical pass after the storm is the rejected 28 Oct one.

## 6. Disclosures

- **The far test and the post-scene rule were designed after seeing Bhiwani.** So were the p<=0.025 thresholds, after seeing Sirsa 2025. They are tested on separate windows below.
- **Selected plots are labelled.** The -0.369 plot is the strongest of 200 scanned.
- **Blocks in the Vanishing are centred on the plot,** the kindest alignment for its own cell. A real administrative unit would not be centred on it. The first level is the plot's own median change, not a pixel.
- **Comparable cropland means pre-event NDVI and uniformity,** with no land-cover map inside the engine. WorldCover was used to sample test plots only.
- **Thin haze passes QA.** One no-event plot read 0.67, 0.49, 0.86 on consecutive scenes in Oct 2025. The twin tracked it (expected 0.52) because haze is regional, but a raw before-and-after would not.

## 7. Locked runs

Rubric v3 (`app/agent/rubric.py`, `cross_exam.py`) and all engine settings were frozen before these started. Each ran once on 200 random cropland plots. Scripts: `geo_holdout.py`, `geo_holdout_report.py`. "Field conditions" means the rubric's plot rule without corroboration: change at threshold, either test at p<=0.025, and no conceded pre-trend. The rubric's actual `strong` and `moderate` also need corroboration.

| Run | Scenes | Strong | Moderate | Ring p<=0.05 | Far p<=0.05 |
|---|---|---|---|---|---|
| No event, around 29.40 N 75.45 E (outside the design region) | `S2B_MSIL2A_20251013T053659_R005_T43REN_20251013T081845` to `S2C_MSIL2A_20251018T053841_R005_T43REN_20251018T085916` | 4/200 = 2.0% (CI 0.8-5.0) | 5/200 = 2.5% (CI 1.1-5.7) | 5.0% | 6.0% |
| No event, Bhiwani region, a year after the hail | `S2B_MSIL2A_20250304T052649_R105_T43RFM_20250304T073919` to `S2B_MSIL2A_20250314T052649_R105_T43RFM_20250314T095315` | 4/200 = 2.0% (CI 0.8-5.0) | 5/200 = 2.5% (CI 1.1-5.7) | 3.5% | 3.5% |
| Sirsa hail, 14 Mar 2025, around 29.66 N 74.88 E (events.md C2) | `S2C_MSIL2A_20250312T053701_R005_T43RDN_20250312T104508` to `S2C_MSIL2A_20250322T053701_R005_T43RDN_20250322T104614` | 0/200 (CI 0.0-1.9) | 0/200 (CI 0.0-1.9) | 2.0% | 3.0% |

**No-event windows.** Both sit under the 5% the Bonferroni split allows. In the October window the far p-values lean slightly low (deciles 23, 28, 21, 25, 26, 17, 24, 11, 17, 8), so the far test may be slightly liberal there; March does not show it. Each window is one scene pair with correlated plots, so the CIs are too narrow. "No event" means none reported in our sources. I did not search exhaustively for March 2025 around Bhiwani.

**Sirsa hail, the independent event: no signal, and that does not validate sensitivity.** The Tribune called the damage "minor", so the engine not claiming anything is consistent with the report. I cannot distinguish little damage from a miss.
- Without the pre-trend check, 3 plots would have met field conditions (2 strong, 3 moderate). All 3 were already falling (pre-trend -0.104 to -0.170) with bare soil at 0.41-0.56, which looks like ripening or harvest. Mustard harvest had begun.
- 33 of 200 plots dropped at least 0.15; 13 of them were already falling. 21 of 200 were flagged as already falling overall.
- Near the named villages: Kharian 38 plots within 3 km, median change -0.040, no signal. Panniwala 27 plots, median -0.070, 1 signal.
- Scene rule, fixed before results: post is 22 Mar, because 17 Mar is under 5 days. Pre is 12 Mar, because 14 Mar is 84.5% cloud. 9 plot attempts were skipped because QA rejected the 12 Mar scene over them.

**So sensitivity is shown only on Bhiwani, the event the far test and post-scene rule were designed on.** That is the main thing this validation does not establish.

**One restart.** The March run was stopped after 40 plots and restarted to fix a harness omission: it was re-downloading the pass between pre and post for every plot. Only placebo counts and pre-event NDVI had been looked at. All 40 rows matched the restarted run exactly. Method, plots and seeds did not change.

## 7a. Seed sensitivity (`geo_seed_sensitivity.py`)

The placebo draw is random. Same data, same method, 30 seeds. Plots: the two demo plots, plus the 5 in-band plots of the 40 whose far p at their own seed fell closest to 0.025, chosen by that rule. Levels assume corroboration is present, and leave out the pre-trend check, which does not depend on the seed's placements.

| Plot | Change | Far p (min, median, max) | Far <=0.025 | Ring p (min, median, max) | Ring <=0.025 | Levels across seeds | Differs from majority |
|---|---|---|---|---|---|---|---|
| Extreme, strongest of 200 (28.700911, 76.215719) | -0.3689 | 0.0050, 0.0050, 0.0050 | 100% | 0.0249, 0.0348, 0.0498 | 13% | strong 30 | 0% |
| Typical, median of 40 (28.715212, 76.231138) | -0.1259 | 0.0244, 0.0537, 0.0732 | 3% | 0.1585, 0.2017, 0.2284 | 0% | weak 29, moderate 1 | 3% |
| In-band 3 (28.705132, 76.228052) | -0.1574 | 0.0149, 0.0398, 0.0597 | 23% | 0.1592, 0.1841, 0.2239 | 0% | weak 23, strong 7 | 23% |
| In-band 7 (28.718677, 76.227288) | -0.1627 | 0.0149, 0.0348, 0.0746 | 20% | 0.0597, 0.0896, 0.1144 | 0% | weak 24, strong 6 | 20% |
| In-band 18 (28.711909, 76.227209) | -0.2045 | 0.0050, 0.0249, 0.0448 | 67% | 0.1045, 0.1294, 0.1542 | 0% | strong 20, weak 10 | 33% |
| In-band 25 (28.720533, 76.231610) | -0.1595 | 0.0199, 0.0448, 0.0746 | 13% | 0.0498, 0.0697, 0.0995 | 0% | weak 26, strong 4 | 13% |
| In-band 26 (28.702952, 76.199466) | -0.1560 | 0.0050, 0.0199, 0.0398 | 93% | 0.3582, 0.3881, 0.4179 | 0% | strong 28, weak 2 | 7% |

`n_placebos` is stable: far 200-204 on all plots; ring 200, except the typical plot at 157-174.

**What this means.** Clear cases are stable. Near the 0.025 line the seed can decide the level: far p moves by a factor of about 4-8, because the seed picks both which far windows are read and which placements land in them. 5 of these 7 plots change level on at least 7% of seeds. These 5 were picked for being near the line, so they are the worst case, not typical. At their own seeds, 12 of the 40 in-band plots had a field signal.

**The app's seed comes from the polygon and the event date** (`make_seed` in `app/agent/graph.py`). So the same record reproduces exactly, which `replay` confirms, but a slightly different polygon re-samples. The same field drawn a little differently can land on the other side of the line near it. A p-value near 0.025 should be read as "near the line", not as a pass or a fail. The method has not been changed to reduce this, because that would invalidate the locked runs.

The strongest plot also differs by polygon: this 113 m square gives far 0.005 and ring 0.0348; the 2.12 ha square in the live case gave far 0.010 and ring 0.0299 (BACKEND's record).

## 7b. Punjab floods, August 2025: pre-registered independent positive test

Written before any Punjab data was opened. Frozen rubric v3. Run once. Script: `tests/geo_punjab.py`.

- **Sites** (`events.md` C5, named villages with reported dates only): Pakhoke Mehmaran 32.01496, 75.01210; Dera Baba Nanak 32.03325, 75.02517; Kot Gurbaksh 31.98063, 74.91547. Fazilka is excluded because the source gives no exact flood date.
- **Event date:** 27 Aug 2025. The sources differ by up to a day on when the flooding began.
- **Plots:** 60 random squares of 1-2 ha, 20 per site, centres within 1.5 km of the point, at least 80% WorldCover cropland, seed 20250827.
- **Control:** the same 60 plots over the same calendar window in 2024. No comparable flood is documented in our sources. That has not been exhaustively verified.
- **Radar pair, per plot, by rule:** for each relative orbit and pass direction, the last pass before 26 Aug and the first pass after 27 Aug. Use the orbit whose post pass comes soonest; ties go to the shorter gap, then the lower orbit number. The same rule applies in 2024.
- **Optical pair, per plot, by rule:** latest accepted scene before 26 Aug; first accepted scene at least 5 days after the event, else the earliest accepted scene within 20 days. Monsoon cloud may leave few.
- **Reported, 2025 against 2024:** `new_water_frac`, SAR placebo p, optical availability, and verdict-level field conditions (optical: rubric v3 field conditions; radar: placebo p<=0.05 or new water >= 0.2).

**What counts, fixed now:**

| Outcome | Criterion, on plots with a usable radar pair in that year |
|---|---|
| **New-water part passes** | Share of plots with `new_water_frac` >= 0.2 in 2025 is at least 3 times the 2024 share and at least 15 percentage points above it |
| **SAR-signal part passes** | Share of plots with SAR placebo p<=0.05 in 2025 is at least 2 times the 2024 share and at least 15 percentage points above it |
| **Pass** | Both parts pass |
| **Partial** | Exactly one part passes. Reported as partial, not as a pass |
| **Miss** | Neither part passes |

If either year has under 30 of the 60 plots with a usable radar pair, the result is **not testable** rather than a pass or a miss.

A miss is reported as a miss. Silt, ponding that drained before the pass, or orbit gaps may explain one, but do not convert it into a pass. The placebo may have low power in a flood wider than its ring, as in Bhiwani. That is a reason to expect a partial result. It does not change the score.

## 8. Read time

Measured on this machine, whose link to the blob store measured about 0.39 MB/s, shared with other jobs. Cold timings are upper bounds and depend on who else is downloading. Tracked separately below once the read-time work is done.

Verify timings from BACKEND's records (`backend/var`; the live record's hash starts `97b0da03e868`): all 20 field numbers in 41 s and 26 s on two runs; all 104 numbers in 1066 s while sharing the link. My own full `replay` of the typical plot also matched all 104 numbers exactly, in 1587 s while sharing the link with a locked run's download.
