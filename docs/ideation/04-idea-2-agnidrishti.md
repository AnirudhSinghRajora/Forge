# 04 — Idea #2: AgniDrishti (अग्नि दृष्टि, "fire sight"): the stubble-burning truth & prevention agent

> **Superseded in part.** This file is an early working draft and some claims here were later corrected against the official guidelines and real data. For current facts see [`docs/submission/facts.md`](../submission/facts.md), and for the current design see [`docs/plan/07-build-contract.md`](../plan/07-build-contract.md).

> **India's official farm-fire numbers come from satellites that pass overhead before most fires are lit. AgniDrishti measures what actually burned, field by field and every day, works out which fires are reaching Delhi today, and acts on the fields that haven't burned yet.**

**Theme 2** (Climate, Resource Infrastructure & Global Supply Resilience). The track concept covers "systemic operational and environmental challenges", and Problem 2 asks for satellite (Copernicus/ISRO) pipelines that forecast micro-climate risks and output mitigation plans. This idea is a **looser fit to the listed problem spectrum** than #1, so the pitch has to make the climate and resource link explicit: emissions, air-quality forecasting, soil carbon, and residue as a resource.

---

## 1. The problem: an unsolved measurement failure with national consequences

| Evidence | Source |
|---|---|
| Official active-fire counts show **over 90% fewer fires since 2021** in Punjab & Haryana (the Environment Minister claimed 93% / 91%) | iFOREST Stubble Burning Status Report 2025 (via The Week, The Wire, Tribune) |
| Over the same period, **actual burnt area fell only 25–37%**: Punjab from 31,447 km² (2022) to about 20,000 km² (2025); Haryana from 11,633 km² (2019) to 8,812 km² (2025) | iFOREST 2025 |
| **Over 90% of large farm fires in Punjab (2024, 2025) happened after 3 pm**, after the polar-orbiting satellite overpasses that the official counts rely on | iFOREST 2025 / Daily Pioneer |
| This led to **major underestimation of stubble burning's contribution to Delhi's air pollution** and errors in AQ forecasting | iFOREST 2025 |
| **Supreme Court (Nov 2025)** agreed to examine whether farmers burn after satellites pass. An amicus suggested officials may be sharing overpass timings. In Nov 2024 the bench took note of reports of officials advising burning after 4 pm. | Scroll, LiveLaw |
| SC pushed for round-the-clock monitoring and geostationary data. **CAQM says it is developing a burnt-area assessment protocol.** CAQM and ISRO are in talks on better tracking. | LiveLaw, ThePrint, CivilsDaily *(partly secondary)* |
| Prevention levers exist but are under-used or delayed: Haryana pays **₹1,200/acre** for in-situ/ex-situ residue management (2025-26), with reported payment delays; **42,000+ custom hiring centres** have CRM machines on 80% subsidy | Tribune, UNI (Jhajjar, Oct 2026), Lok Sabha answer |
| **Timing:** late Oct to mid-Nov is peak burning season, i.e. right now | Seasonal |

### Why it's "not solved yet"
- iFOREST's multi-sensor burnt-area analysis is an **annual, retrospective report**. It isn't live, field-level, or tied to action.
- CAQM's burnt-area protocol is **still being developed**. Official dashboards still publish **fire counts**.
- No public system links "what burned" to "what reached Delhi today" (wind-weighted impact), or to "which unburned harvested fields need help in the next 48 hours".

### Who is affected
- **Over 30M people in Delhi-NCR** breathing peak-season air, plus rural Punjab and Haryana, where exposure is highest.
- **Decision-makers:** CAQM, state pollution boards, district administrations, and the Supreme Court/amicus process, all of whom are working from numbers known to be wrong.
- **Farmers:** they need the residue-management machine, the incentive, or a biomass buyer *within days* of harvest, before the wheat-sowing window closes.

---

## 2. Existing efforts and the gap

| Existing | Gap |
|---|---|
| CREAMS/IARI & PRSC fire-count bulletins (MODIS/VIIRS) | Miss post-overpass fires; counts aren't area |
| iFOREST Status Report (MODIS/VIIRS + Sentinel-2 burnt area + Meteosat SEVIRI) | Annual and retrospective; not field-level or operational |
| CAQM burnt-area protocol | Not yet operational *(as reported)* |
| State CRM apps / CHC machine booking, incentive portals | Not targeted. They don't know *which* villages have unburned residue *right now*. |
| Academic burn-scar papers | Not productised, live, or agentic |

**USP:** the first **live, field-level, multi-sensor burnt-area engine** that (1) corrects the official count, (2) weights each fire by its likely impact on Delhi today from the wind field, and (3) turns the unburned-residue map into targeted prevention action. It's built on the method a credible research body has already validated, but operational, daily, and public.

---

## 3. Solution: three outputs from one engine

1. **Truth layer (public dashboard + API):** daily burnt-area polygons per village/district from Sentinel-2 burn indices (NBR/dNBR, SWIR), cross-checked with live FIRMS VIIRS/MODIS hotspots and, where accessible, geostationary data. Shows "official count vs. measured burnt area" side by side.
2. **Impact layer:** wind-driven back-trajectories (Open-Meteo/ERA5 winds) from Delhi, giving "these 1,800 hectares burned yesterday upwind of Delhi; these are likely contributors to tomorrow's AQI." This feeds AQ forecasters and GRAP decisions.
3. **Prevention layer (the agentic action):** a harvest-state classifier finds **harvested-but-not-yet-burned/sown** paddy fields (the at-risk residue inventory). For each at-risk village cluster, the agent drafts:
   - officer briefs: where to send CRM machines and teams in the next 48 h, ranked by residue area × Delhi-impact × days left before wheat sowing
   - farmer outreach in Punjabi/Hindi voice: incentive eligibility (e.g. Haryana ₹1,200/acre) with official links, nearest CHC/biomass options where the data exists, and the deadline

---

## 4. The agent

```
Daily loop (and on-demand for any district/village):
1  pull_hotspots(region, 24h)          → FIRMS VIIRS/MODIS NRT (live, free MAP_KEY)
2  search_optical(region, last 10 d)   → Sentinel-2 L2A scenes; per-field cloud check
   ├─ clear pre & post               → NBR/dNBR + SWIR burn classification per field
   └─ cloudy                          → defer; use hotspots + previous clear scene; flag uncertainty
3  classify_fields()                   → standing crop / harvested-unburned (residue) / burned / tilled-sown
4  self_check()                        → reject static hotspots (brick kilns, industry: persistent across seasons),
                                          bare-soil vs burn confusion (SWIR/NIR tests), require 2 signals for "burned"
5  attribute_impact()                  → wind back-trajectories from Delhi → weight burned area by transport likelihood
6  reconcile_with_official()           → compare against published fire counts → "missed" estimate with confidence
7  plan_prevention()                   → rank at-risk residue clusters (area × impact × sowing-window); retrieve
                                          incentive rules (RAG on state notifications) and CHC/buyer data where available
8  act()                               → officer brief (PDF/WhatsApp), farmer voice outreach, public dashboard + open API
9  explain()                           → every number linked to scene IDs, hotspot IDs, wind data, and rule citations
```

What judges see: sensor selection and fallback, false-positive self-checks, confidence-scored reconciliation against the official numbers, and a planner that turns analysis into ranked actions with cited rules.

---

## 5. Architecture (indicative)

Planetary Computer STAC (Sentinel-2 L2A; Sentinel-1 RTC optional) via `odc-stac`/`xarray` · NASA FIRMS API · Open-Meteo / ERA5 winds + a simple trajectory model (e.g. HYSPLIT-style back-trajectory or a wind-advection approximation) · PostGIS (village/field grids, results) · state-graph agent with tools · RAG over state CRM/incentive notifications · MapLibre dashboard · Punjabi/Hindi TTS for outreach.

**Shared stack with #1:** the STAC + per-field index pipeline is the same core engine as FasalSaakshi. The first 3–4 hours of building are identical, which de-risks deciding between the two.

## 6. Data: verified 31 Oct 2026

| Source | Status |
|---|---|
| Sentinel-2 L2A over **Sangrur, Punjab** (peak burning district) | ✅ clear scenes on 18, 20, 22, 25, 28 Oct 2026 (0% cloud) |
| NASA FIRMS area API | ✅ reachable; **needs a free MAP_KEY** (returned "Invalid MAP_KEY" for DEMO_KEY) |
| Open-Meteo forecast (winds) | ✅ |
| Geostationary (Meteosat IODC SEVIRI, INSAT-3D/3DR via MOSDAC) | ⚠ not tested. Access and registration need checking; it's optional for the MVP. |
| CHC / machine availability data | ⚠ not confirmed as open data. Use only official published lists, and don't fabricate. |

## 7. Demo script

1. **Hook:** "The government says farm fires fell 90%. The ground fell 30%. Here's why." Show the iFOREST chart, then the after-3-pm overpass gap.
2. **Live:** pick a Punjab block. FIRMS shows N hotspots in the last 10 days. The Sentinel-2 burn map shows M hectares burned, with field polygons where *no hotspot was ever recorded*.
3. **Impact:** today's wind field shows which burned clusters fall in Delhi's upwind cone.
4. **Prevention:** the agent lists at-risk unburned harvested fields, ranks clusters, generates an officer brief, and plays a Punjabi voice message about the ₹1,200/acre incentive.
5. **Judge interaction:** "Pick any village in Punjab or Haryana."

## 8. Rubric mapping

| Pillar | Assessment |
|---|---|
| Live demo (30) | Strong: live season, live data, any-village queries |
| Agentic (25) | **Medium-strong.** Analysis is the heart; the action layer (briefs, outreach) must be real and visible to score well. |
| Impact & USP (25) | Very high impact. An unsolved, Supreme Court–level problem; clear differentiation. **Theme-fit needs a careful pitch.** |
| Tech (20) | Very high: multi-sensor fusion, change detection, trajectories |

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Seen as surveilling or policing farmers** | Frame as *accurate accounting + prevention help*. Publish at village/block level by default; field level only for officials. Lead with the farmer-help layer. |
| Theme-fit questioned | Tie it to Problem 2 (satellite micro-risk + mitigation plans), plus emissions and resource (residue as biomass) |
| Burn scars disappear once fields are tilled or sown | Use every clear S2 pass (2–3 day effective revisit here), FIRMS for dates, SWIR persistence |
| False positives (bare soil, kilns, shadows) | SWIR/NIR tests, persistent-hotspot masks, two-signal rule, confidence levels |
| Validation ("how do you know?") | Benchmark against iFOREST's published 2025 district totals and FIRMS overlap; report agreement honestly |
| Prevention data (CHC lists) may not be open | Only use official published lists; otherwise give officer-level guidance without machine-level routing |

## 10. MVP cut

Must-have: block/village selection → FIRMS hotspots + S2 burn map per field → official-count vs. measured comparison → wind-weighted impact → at-risk residue map → officer brief + one-language farmer voice note, all cited. Nice-to-have: geostationary fusion, CHC routing, open API.
