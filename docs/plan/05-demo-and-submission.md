# 05 — Demo, Testing & Submission

## 1. Demo script (2:45 video; the same flow is used live for judges)

| Time | Beat | On screen | Words (roughly) |
|---|---|---|---|
| 0:00–0:20 | **Problem** | Haryana protest headline; the line "YES-TECH: insurance-unit level, not individual small farms"; the 72-hour rule | "Satellites already help decide farmers' insurance claims, but at village level, and farmers can't see or contest them. Report a loss late, and the claim can be rejected." |
| 0:20–0:35 | **The ask** | Phone: a team member records a Hindi voice note about hail on their cotton/paddy near Sirsa and drops a pin | "A farmer just speaks." |
| 0:35–1:30 | **Agent investigates (live trace)** | Plot drawn → weather (rain, hail-code hours) → Sentinel-2 search → **"28 Oct image rejected: infrared band invalid"** → falls back to Sentinel-1 radar (16 vs 28 Oct, same orbit) → neighbours + 2025 history → self-check "is this just harvest?" → verdict | "It checks its own data, and when a satellite image is broken it says so and switches sensors." |
| 1:30–2:00 | **Evidence** | Before/after chips, neighbour histogram with the plot marker, weather strip, cited clauses, confidence level, caveats | "Every number links back to its source. It compares the field with its neighbours, so normal harvest isn't mistaken for damage." |
| 2:00–2:25 | **Action** | Hindi TTS plays; intimation draft; 72-hour countdown; "I submitted" with reference no.; evidence PDF opens; re-check scheduled for the next pass | "It gets the claim in on time, and keeps watching the field." |
| 2:25–2:45 | **Impact + close** | Numbers slide: ₹4,107 cr pending (Dec 2025), crore-scale enrolment; roadmap | "FasalSaakshi gives the farmer the same satellite evidence the insurer has." |

**If the ~2 Nov Sentinel-2 pass arrives clean:** add the moment "the agent re-checked automatically when a new satellite pass landed", showing the optical before/after for Sirsa.

**Live judging extras:** let a judge drop a pin anywhere. Expect an honest "insufficient / likely harvest / no event" result in most places, and say up front that this is the correct behaviour.

## 2. Test matrix (run at H20, H32, H36 on the deployed build)

| # | Scenario | Expected |
|---|---|---|
| T1 | Sirsa plot, event 25 Oct 2026 | Optical post rejected (28 Oct, QA) → SAR pair used → verdict ≤ moderate unless SAR + weather support it; trace shows the fallback |
| T2 | Same plot after a new clean optical pass | Optical post accepted → full rubric |
| T3 | Plot in a normal area, no weather event | weak / insufficient, with a clear explanation |
| T4 | Plot that was harvested (bare post) | `not_damage_likely_harvest` + question to the farmer |
| T5 | Tiny plot (< 0.2 ha) | Caveat + photo-evidence suggestion |
| T6 | Plot over a water body / urban area | "No crop detected before the event" → asks to re-check the boundary |
| T7 | Pin outside India / in the sea | Graceful rejection |
| T8 | Event date wrong by 3 days | Agent proposes the corrected date from weather |
| T9 | Voice note in Hindi with background noise; English text; Hinglish | Parsed correctly, or a clarifying question |
| T10 | Planetary Computer slow/timeout | Retries, then partial evidence + "re-check scheduled" |
| T11 | Open-Meteo 429 | NASA POWER fallback, noted in provenance |
| T12 | Gemini error/timeout | Deterministic verdict still shown; explanation retried; no crash |
| T13 | Double-click investigate / refresh mid-stream | Idempotent runs; trace replay from `run_events` |
| T14 | Mobile on 3G-like throttle | Usable; images lazy-loaded |
| T15 | Explanation contains a number not in the evidence | Validator blocks it and regenerates |
| T16 | "I submitted" without a reference number | Not marked filed |
| T17 | Policy question outside PMFBY | "Not covered by the documents I have" + no hallucination |

## 3. Judge Q&A prep (every member must be able to answer)

| Likely question | Answer core |
|---|---|
| "How do you know it's damage and not harvest?" | Neighbour comparison on the same dates + the plot's own 2024/2025 history + bare-soil test + within-plot pattern; harvest moves the whole area, a localized event doesn't. Show the 2025 calibration numbers. |
| "What's your accuracy?" | No public plot-level ground truth exists (that's part of the problem). We measured the false-positive rate on a known-normal window (X%) and checked N documented events (results). We report confidence levels, not certainty. |
| "Isn't this what YES-TECH/CROPIC do?" | Those serve insurers/states at insurance-unit level. We're farmer-side, plot-level, and action-oriented (deadline + documentation). |
| "Why should an insurer accept it?" | We don't replace CCEs. We give the farmer timely documentation and a trigger for survey/grievance, with transparent provenance. Roadmap: FPO/insurer partnership. |
| "Where's the agent, beyond a pipeline?" | Sensor selection & fallback, QA rejection, self-check loops, event-date correction, policy-grounded deadlines, scheduled autonomous re-checks. Show the trace. |
| "No dummy data?" | Every number on screen has provenance (scene ID / API / timestamp). Show the provenance table in the PDF. |
| "Cloud cover in monsoon?" | Sentinel-1 radar fallback (demonstrated live because of the 28 Oct corruption). |
| "Scalability?" | Stateless workers, per-plot windowed COG reads, scene-QA caching; cost per investigation ≈ a few Gemini calls + free open data. |
| "Privacy?" | No Aadhaar/bank credentials; minimal PII; farmer controls submission. |

## 4. Submission checklist (maps to the official template)

| Item | Owner | Done when |
|---|---|---|
| 1. Problem statement (issue, context, target audience) | B | Text below, refined |
| 2. Solution description (overview + technical architecture) | B | Text below + architecture diagram |
| 3. Prototype link (live) | C | Opens on a phone over mobile data; no login wall (or demo login shown) |
| 4. Demo video (2–3 min, live end-to-end) | C | Uploaded unlisted on YouTube/Drive with public access; checked in incognito |
| 5. GitHub repo (public) | B | README: setup, env vars, architecture diagram/flowchart, data sources, calibration results, limitations; all source/config; no secrets committed |
| 6. Deck (5–7 slides) | C (A for the tech slide) | Link with view access |

### Draft text: Problem statement
> **Target issue:** Under PMFBY, India's crop insurance scheme, farmers hit by localized calamities (hail, waterlogging, unseasonal rain on harvested crop) must report losses within 72 hours, and claims are increasingly settled using satellite-based yield estimates (YES-TECH, minimum 30% weightage) computed at insurance-unit level, not for individual farms. Farmers can't see or contest this evidence. In 2025, Haryana farmers protested after satellite assessments cut crop-cutting-based claim estimates by about ₹350 crore. Nationally, ₹4,107 crore of claims were still pending in December 2025. On 25 Oct 2026, hail and rain damaged paddy and cotton in Sirsa and Fatehabad.
> **Target audience:** Small and marginal PMFBY-insured farmers, and the FPOs, KVKs and agriculture officers who support them.

### Draft text: Solution overview
> FasalSaakshi is a voice-first agent that acts as a farmer's independent "crop witness". A farmer describes the loss in Hindi and marks their field. The agent plans and runs an investigation: it retrieves Sentinel-2 optical and Sentinel-1 radar imagery for that exact plot, rejects corrupted or cloudy scenes, compares the plot against similar neighbouring fields and its own history to separate calamity damage from normal harvest, corroborates with weather data and official alerts, and produces a confidence-graded, fully cited verdict. It then grounds the next steps in the PMFBY guidelines, drafts the loss intimation, tracks the 72-hour deadline, and re-checks the plot automatically when new satellite passes arrive.
> **Architecture:** Next.js + MapLibre PWA → FastAPI on Cloud Run → LangGraph investigation graph with typed tools → Planetary Computer STAC (Sentinel-2 L2A, Sentinel-1 RTC), Open-Meteo/NASA POWER, NDMA SACHET, Gemini (planning, audio understanding, Search grounding, Hindi TTS) → Postgres/PostGIS/pgvector; evidence-pack PDF with full provenance.

## 5. Deck outline (6 slides)
1. **Title & team:** FasalSaakshi, "the farmer's crop witness"; team names and roles
2. **Problem:** the 72-hour rule, unit-level satellite assessment, protests and pending claims, the Sirsa hail this week
3. **Solution & key features:** voice → plot → investigation → verdict → action → re-check (one visual flow)
4. **Architecture & innovation:** the diagram; the three innovations: scene QA, neighbour/history discrimination, SAR fallback; calibration result
5. **Demo summary & impact:** screenshots of the trace and evidence pack; who benefits and at what scale
6. **Roadmap:** FPO/KVK dashboard, insurer/state integration, more languages, field-boundary auto-detection, Rabi season
