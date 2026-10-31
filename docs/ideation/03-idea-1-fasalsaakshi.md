# 03 — Idea #1: FasalSaakshi (फसल साक्षी, "crop witness")

> **Insurers and states already use satellites to judge a farmer's claim. FasalSaakshi gives the farmer the same satellite evidence for their own plot, then an agent makes sure the claim is filed correctly and on time.**

**Theme 2 · Problem 2** (Predictive Climate & Micro-Location Yield Engine). It also covers Problem 1 (multilingual advisory) through the voice layer.

---

## 1. The problem

### What happens today
1. A localized calamity hits: hail, inundation, unseasonal rain, cyclonic rain on harvested crop.
2. Under PMFBY, a farmer must **intimate the loss within 72 hours** (localized calamities and post-harvest losses; the window was 48 h before 2018). They can do this through the insurer, bank, agriculture office, CSC, the Crop Insurance app, or the toll-free helpline. **Late intimation is a standard rejection ground, whatever the actual damage.**
3. Losses are then assessed through crop-cutting experiments (CCEs), surveys, and increasingly **satellite-based yield (YES-TECH, minimum 30% weightage in claim settlement)**.
4. YES-TECH and similar models work at **insurance-unit level** on moderate-resolution inputs (5–30 m). One explainer notes that this suits unit-level aggregation **but not individual small farms**. A hail strip that destroys one farmer's field can be averaged away across the village.
5. The farmer has **no independent evidence**. It's their word against the model's.

### Evidence that people are asking for a fix
| Evidence | Source |
|---|---|
| Haryana 2025: farmers protested from 16 Jul. They say CCEs estimated claims at **₹450 cr**, and satellite (HARSAC) assessment **cut that by about ₹350 cr**. They cite a state order that claims be settled on CCEs, not satellite alone. | Tribune India |
| Rajasthan 2025: **₹947.72 cr** in claims pending (Jul 2025), well past the 2-month timeline. Farmers allege rejections without field surveys, and that damaged areas get assessed as "green and healthy" by satellite. | IASGyan / Global Agriculture (secondary) |
| Nationally: of ₹1,00,085 cr of claims reported, **₹4,107 cr was still pending as of 31 Dec 2025** (74% of it in Andhra Pradesh). | Lok Sabha answer |
| Scale: **4,992.79 lakh farmer applications** enrolled from 2020-21 to Kharif 2024. ₹86,306 cr paid to 1,423 lakh applications. | Lok Sabha answer (Jul 2025) |
| **Right now:** unseasonal rain and hail damaged standing paddy and cotton in **Sirsa & Fatehabad, Haryana (reported 25 Oct 2026)**. MP Kumari Selja demanded immediate loss assessment and compensation. | UNI, 25 Oct 2026 |
| UP ordered a digital crop-damage survey after cyclone, rain and floods (Oct 2026). | UNI, 6 Oct 2026 |

### Who is affected
- **Primary:** small and marginal farmers enrolled in PMFBY (crore-scale enrolment per season), especially those hit by **localized** events: hail, waterlogging, post-harvest rain. Area-averaged assessment hurts these farmers most.
- **Secondary:** FPOs, Krishi Vigyan Kendras, farmer-rights groups, and agriculture officers who need defensible evidence quickly. Banks (KCC lenders) also have a stake, since crop loss drives loan stress.

---

## 2. Existing solutions and the gap

| Existing | Who it serves | Gap FasalSaakshi fills |
|---|---|---|
| **YES-TECH** (govt satellite yield estimation) | States / insurers, at unit level | Not plot-level, and the farmer can't see or contest it |
| **CROPIC** (govt photo-of-crop app; pilot in 50 districts for Kharif 2025 / Rabi 2025-26, nationwide in 2026) | Ministry / insurers; photos taken 4–5× per season | Photos aren't independent time-series evidence, and there's no claim agent |
| Crop Insurance app / Krishi Rakshak helpline | Intimation channel | The farmer must know the rule, the deadline, the right format, and what to say. Nothing helps them do it right. |
| CropSnap (ESA), EOfactory–Bajaj Allianz, AgRISE (IWMI) | Insurers' dashboards | Insurer-side or B2B. A government document says outright that farmers "benefit indirectly." |
| Farmer advisory bots (Kisan e-Mitra, Farmer.Chat) | Q&A | No evidence and no claims |

**USP in one line:** *the first farmer-side, plot-level, multi-sensor crop-loss witness that also acts on it.* It turns satellite evidence into a filed, deadline-compliant, well-documented claim in the farmer's language.

Why this beats "another farmer chatbot":
1. **Flips who holds the evidence.** The same Copernicus data the system uses is now on the farmer's side.
2. **Plot-level, not unit-level.** At 10 m Sentinel-2 pixels, a 1-acre plot is about 40 pixels and a 1-hectare plot about 100. That's enough for a statistically meaningful change signal, and it can be compared against the farmer's *neighbours* and *their own field's history*.
3. **Cloud-proof.** Calamities come with clouds, so optical alone fails exactly when it's needed. The agent falls back to **Sentinel-1 radar** (all-weather) for inundation and lodging signals. That's a real agentic decision judges can watch happen.
4. **Deadline-aware action.** The 72-hour clock is the biggest silent killer of claims.

---

## 3. Solution: the user journey

1. **Farmer (or FPO/KVK volunteer) reaches FasalSaakshi** on WhatsApp or by phone, speaking Hindi, Punjabi, Marathi, Telugu, and so on. They say what happened ("ओले गिरे, धान गिर गया") and share a location pin or draw/tap the plot on a map. They can optionally send field photos.
2. **Plot capture:** The agent snaps to the field boundary. It can segment field parcels from imagery (e.g. a SAM-style model on a recent clear Sentinel-2 scene) and ask the farmer to confirm, or the farmer draws the polygon.
3. **Investigation (the agent):** See §4 below.
4. **Verdict and evidence pack**, in plain language plus a PDF:
   - Before/after satellite images of *their* plot, with the damage date bracketed, e.g. "clear on 18 Oct, damaged by 28 Oct".
   - NDVI/NDWI/radar-backscatter change for the plot vs. its own previous seasons and vs. its neighbours, with the confidence stated.
   - Weather corroboration: rainfall and hail-proxy signals and official alerts (IMD/SACHET) for that location and date.
   - Matching PMFBY clause: localized calamity or post-harvest loss, and which deadline applies.
5. **Action:**
   - Generate the **intimation** in the format required, with the farmer's details, and file it through the channel the farmer chooses. Show the 72-hour countdown.
   - Track the claim. If a survey isn't scheduled or the claim is rejected, draft a **grievance or appeal** with the evidence pack attached, citing the guideline clauses.
   - Optional: inform the local agriculture officer or FPO.
6. **Follow-ups:** The agent re-checks new satellite passes (S2 every ~5 days, S1 every ~6–12) and updates the evidence. It also sends a **voice note** summary in the farmer's language.

---

## 4. The agent: where the 25 "AI Reasoning & Agentic Execution" points come from

Planner–executor loop. Every step is a real tool call, and it branches on what the data says:

```
Goal: produce defensible evidence of crop loss for plot P and event window W, then act on it.

1  parse_report(voice/text/photo)        → crop, event type, claimed date, location (ASR + LLM)
2  resolve_plot(location)                 → polygon (segmentation or user-drawn; validate area, warn if < ~0.2 ha)
3  get_weather(P, W±10d)                  → rainfall, temperature, wind (Open-Meteo / NASA POWER / IMD)
   get_alerts(P, W)                       → SACHET/IMD CAP alerts in the region (official corroboration)
4  search_optical(P, W-20d … today)       → Sentinel-2 L2A scenes, cloud % per *plot* (not per tile)
   ├─ if clear before & after scenes exist → compute NDVI/NDRE/NDWI change, SCL-mask clouds/shadows
   └─ else (cloudy)                       → search_sar(P) → Sentinel-1 RTC VV/VH change (inundation, lodging)
5  baseline(P)                            → same-date indices from previous 2–3 seasons (is this drop abnormal?)
   neighbours(P)                          → ring buffer of similar fields (was the damage local or regional?)
6  attribute()                            → LLM reasons over all signals; states the hypothesis, confidence, and
                                            what would falsify it (e.g. "drop is consistent with harvest, not hail")
7  self_check()                           → contradiction tests: harvest-date confusion, cloud-shadow artefacts,
                                            crop type mismatch; if it fails, gather more (another scene, SAR) or downgrade the claim
8  policy_rag(event, state, season)       → PMFBY guideline clauses + state notification (RAG with citations)
9  act()                                  → draft intimation / grievance; file via chosen channel; schedule re-checks
10 explain()                              → farmer-language voice note + evidence-pack PDF with every number cited
```

What judges will see: **self-correction** (cloudy, so switch to radar; the drop looks like harvest, so check the crop calendar and downgrade), **multi-tool orchestration**, **guardrails** (no verdict without two independent signals; confidence levels; "insufficient evidence" is a valid answer), and **source attribution** (every number links to its scene ID, date, and API).

---

## 5. Technical architecture (indicative)

| Layer | Choice (suggested) | Notes |
|---|---|---|
| Channel | WhatsApp Cloud API (Meta test number) and/or a web PWA; optional IVR | Voice in / voice out |
| Speech + language | Bhashini / Sarvam / AI4Bharat IndicTrans2 + IndicWhisper / IndicTTS, or a frontier LLM for reasoning | Hindi/Punjabi first, since the Haryana demo calls for it |
| Agent orchestration | LangGraph-style state graph (or equivalent) with typed tools, retries, timeouts | "Complex state graphs" are named in the rubric |
| Geospatial engine | **Microsoft Planetary Computer STAC** (Sentinel-2 L2A, Sentinel-1 RTC; free, no key for search) via `pystac-client` + `odc-stac`/`stackstac` + `rasterio`/`xarray`. Fallback: **Copernicus Data Space** (Sentinel Hub Statistical API). | Per-plot zonal stats only, never whole tiles, to keep latency low |
| Field boundaries | Segment-Anything-style model on S2 RGB, or user-drawn polygon (Leaflet/MapLibre) | User-drawn is the robust fallback |
| Weather / alerts | Open-Meteo (forecast + archive), NASA POWER (agro-met, daily), **NDMA SACHET CAP RSS** | Open-Meteo's archive hit a 429 daily limit in our test, so cache responses and keep NASA POWER as the fallback |
| Policy RAG | PMFBY operational guidelines + state notifications, chunked with clause IDs | Citation-first answers |
| Storage | Postgres + PostGIS (plots, cases, evidence), object storage for PNG/PDF | Case history for re-checks |
| Scheduler | Cron/worker that re-checks new passes and deadlines | Shows autonomy over time |
| Output | Evidence-pack PDF (before/after chips, charts, citations), voice note | This is the visual asset for the audience award |

---

## 6. Data: verified live on 31 Oct 2026

| Source | Status | What we saw |
|---|---|---|
| Planetary Computer `sentinel-2-l2a` | ✅ 200 | Over **Sirsa (75.03 E, 29.53 N)**: scenes on 13, 15, 18, 23, **28 Oct 2026**. 18 Oct ≈ 0% cloud (before), 28 Oct ≈ 0% cloud (after the ~25 Oct hail) |
| Planetary Computer `sentinel-1-rtc` | ✅ 200 | Sirsa radar passes on 12, 16, 24, 28 Oct 2026 |
| NDMA SACHET CAP RSS | ✅ 200 | 100 live alerts, in Telugu, Kannada, etc. |
| NASA POWER daily point API | ✅ 200 | Daily agro-met for Haryana |
| Open-Meteo forecast | ✅ 200 | Archive endpoint returned **429 (daily limit)**, so cache it or use a paid key |

All official, open data. **No dummy data anywhere** in the pipeline.

---

## 7. Demo script (2–3 min video, also run live for judges)

1. **Hook (15 s):** "On 25 Oct, hail hit Sirsa. Farmers have 72 hours to report or lose their claim, and the satellite models deciding their claims work at village level, not their field."
2. **Live (60 s):** A teammate sends a Hindi/Punjabi voice note on WhatsApp with a location pin in Sirsa. The agent's trace streams on screen: plot resolved, weather and SACHET checked, S2 scenes found, before/after chips rendered, baseline and neighbour comparison, confidence.
3. **Self-correction moment (20 s):** Pick a plot where the "after" scene is cloudy. The agent switches to Sentinel-1 on its own and explains why.
4. **Action (30 s):** Intimation drafted, the countdown shows, the evidence PDF opens, and a voice note goes back in Hindi.
5. **Judge interaction:** "Drop a pin anywhere in India." The robustness pillar is earned live.
6. **Close (15 s):** Impact numbers and roadmap: FPO dashboard, the insurer side as a B2B revenue path, post-loss salvage-sale advice (folds in idea E).

---

## 8. Rubric mapping

| Pillar | How FasalSaakshi earns it |
|---|---|
| Live Demo & Robustness (30) | Satellite archives are stable and global, so any pin works. Cloud and missing-scene paths are designed in. There are no OTP or captcha steps in the core path. |
| AI Reasoning & Agentic (25) | Real branching (optical → SAR), baselines, contradiction checks, cited outputs, deadline-driven actions, scheduled re-checks |
| Impact & USP (25) | Crore-scale enrolment; live protests; the farmer-side evidence flip is novel |
| Tech Depth (20) | Geospatial time-series, SAR, segmentation, RAG, state graph: all named-in-rubric categories |
| Audience award | Before/after satellite reels of real hail damage, with the line "the satellite is on the farmer's side now" |

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Satellite signal ≠ yield loss (harvest, irrigation, crop stage confound it) | Crop-calendar check, neighbour and baseline comparison, explicit confidence, "insufficient evidence" output. Present it as **evidence**, not a payout decision. |
| Small or mixed plots (<0.2 ha) | Warn the user and widen to a contextual buffer. Photo evidence (with EXIF/geo-verification) as a supplement. |
| Cloud cover during events | Sentinel-1 fallback; multiple post-event dates |
| Filing channels lack public APIs | Generate an exact-format intimation and file through the channel the farmer chooses. Browser-automate only where it's permitted, and **never claim filing that didn't happen** (same principle as the playbook). |
| Geospatial learning curve | Planetary Computer + odc-stac per-plot stats is a small, well-documented code surface. Keep zonal stats simple: mean/percentiles over SCL-masked pixels. |
| API rate limits (Open-Meteo 429) | Cache, NASA POWER fallback, pre-warm the demo locations |
| Over-claiming legal outcomes | Language like "supports your claim with evidence" rather than "you will get paid" |

## 10. MVP cut for the remaining window (if chosen)

Must-have: pin/polygon in → S2 before/after + NDVI change + baseline → SAR fallback → weather/SACHET corroboration → cited verdict → intimation draft → Hindi voice note. Nice-to-have: field segmentation, scheduled re-checks, grievance drafting, neighbour analysis.
