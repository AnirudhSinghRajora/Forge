# 04 — Build Timeline (≈46 hours, 3 owners)

`H0` = kickoff. The confirmed deadline is "~2 days left", so **set H46 = the exact submission cutoff minus 1 hour** and shift the table if needed. The plan protects the last **8 hours** for packaging and buffer.

## Gates (non-negotiable)

| Gate | Hour | Must be true | If not true |
|---|---|---|---|
| **G0 Contracts** | H1 | Repo created; API contract (02 §4) and Evidence schema (02 §5) merged; keys working (Gemini, DB, Open-Meteo); model IDs confirmed | Don't start feature work |
| **G1 Walking skeleton** | **H6** | **Deployed** web app → draw polygon → deployed backend → real pre/post NDVI for that polygon (with QA) shown on the map | Drop the P1 list entirely; all hands on the skeleton |
| **G2 End-to-end** | **H16** | Voice note → parsed case → plot → full investigation graph streaming to UI → verdict with neighbours/history/SAR → Hindi text + TTS → intimation draft + countdown. Deployed. | Cut P1 except re-check; simplify SAR to inundation-only |
| **G3 Feature freeze** | **H32** | All P0 done; thresholds calibrated & frozen; PDF works; test matrix ≥ 80% pass | No new features after this, only fixes |
| **G4 Code freeze** | **H38** | Test matrix 100% pass or known-issue noted; README complete; demo path rehearsed twice | Ship what passes; hide broken paths |
| **G5 Submitted** | **H44** | Form submitted with all links; video uploaded; tag `v1.0` | — |

At every gate: a 15-min demo by each owner to the other two (this is also the "everyone can explain everything" training), plus a decision note in `docs/plan/decisions.md`.

## Hour-by-hour

### Phase 0 — Kickoff (H0–H1): everyone
- Create the monorepo (02 §3). Branch rules: short-lived feature branches, PR + 1 review (or pair-merge), `main` always deployable.
- Accounts and keys: Gemini (confirm current Pro/Flash/TTS model IDs), Supabase project (enable PostGIS, pgvector), Open-Meteo commercial key, Cloud Run project (asia-south1), Vercel project, optional Planetary Computer subscription key.
- Merge `evidence/schema.py` (Pydantic) and the API route stubs.
- **B:** download the PMFBY Operational Guidelines PDF + FAQ from pmfby.gov.in. Record the version/date. Confirm the **exact intimation fields and channels** and the **grievance mechanism** from the official text.
- **C:** start the SACHET archiver as a tiny cron (P1, but it's 30 min of work and builds real history from now).

### Phase 1 — Spines (H1–H6)

| Owner A: Geo | Owner B: Agent/Backend | Owner C: Experience |
|---|---|---|
| `stac.py`: search by plot bbox; signed loads with odc-stac; windowed reads | FastAPI app, DB models, migrations; `/cases`, `/plot`, `/investigate`, SSE stream | Next.js app shell, mobile-first layout; MapLibre with satellite basemap |
| `qa.py`: Q1–Q5 + offset handling; **regression: 2026-10-28 rejected** | `llm.py`: Gemini Flash audio → JSON parse (Hindi voice); Pro function-calling hello-world with 2 real tools | terra-draw polygon drawing, area display, pin from GPS |
| `indices.py`: NDVI/BSI on plot + context; pre/post selection | Dockerfile; deploy to Cloud Run; CORS; health check | Voice recorder (MediaRecorder → upload); call real `/cases` |
| Smoke CLI on Sirsa | Wire geo pre/post into `/investigate` as the first real tool | Deploy to Vercel; show pre/post NDVI result on the map |

**→ G1 at H6.**

### Phase 2 — Full investigation (H6–H16)

| Owner A | Owner B | Owner C |
|---|---|---|
| `compare.py`: neighbour ring with comparable-pixel selection; plot percentile; within-plot pattern | LangGraph graph (02 §7): nodes, conditional edges, budgets, timeouts, retries; `run_events` persistence | **Live trace UI**: SSE → timeline of steps with icons, tool inputs/outputs, decisions, rejected scenes |
| History baseline (2024, 2025 same window) | `weather.py` (Open-Meteo hourly precip + weather_code 96/99; NASA POWER fallback); `alerts.py` reading the SACHET archive | Evidence view: before/after chips, NDVI chips, neighbour histogram (plot marker), weather strip, verdict card |
| `sar.py`: same-orbit pair search, dB, inundation share, ΔVH vs neighbours | `policy.py`: chunk guidelines by clause → embeddings → retrieval; `/ask` endpoint with cited answers | Hindi UI strings; TTS playback of the summary |
| `chips.py`: true-colour + NDVI PNGs (plot outline, scene date stamp) | Verdict rubric in code (03 §10) + Gemini explanation with a **number-validator** | Countdown component (72 h from the event / farmer-reported time) |
| **Calibration step 1** (FPR on 2025 normal window) | `actions.py`: intimation draft from official fields; deadline computation with clause citation | Intimation screen: pre-filled text, `tel:14447`, share, download; "I submitted, reference no." form |

**→ G2 at H16.**

### Sleep rotation (H16–H24)
Staggered 5-hour blocks so someone is always awake to keep things running:
- A sleeps H16–H21 · B sleeps H18–H23 · C sleeps H19–H24.
- The awake person on watch at ~H20–H22 runs the **live test matrix** (05 §2) against the deployed build and files issues.
- If the ~2 Nov Sentinel-2 pass lands during anyone's watch, run the Sirsa plots immediately and note the QA result.

### Phase 3 — Robustness and actions (H24–H32)

| Owner A | Owner B | Owner C |
|---|---|---|
| Edge cases: cloudy post, corrupt post, no scenes, tiny plot, plot outside India, plot over water/urban, very large plot (> 50 ha cap) | Self-check node + loop-back (03 §8); event-date mismatch proposal | **Evidence-pack PDF** (WeasyPrint, Devanagari font): plot map, chips, charts, weather, verdict, clauses, provenance table |
| Performance: parallel S2/S1/history, caching by scene ID, context at 20 m | `jobs.py`: scheduled **re-check** of open cases (new accepted scene → new run → notify); deadline reminders | Error and empty states everywhere (no data, timeouts, offline); retry buttons |
| **Calibration steps 2–3** (documented events + Sirsa SAR) | News corroboration via Gemini Search grounding (P1), cached per district × date | **WhatsApp channel (P1)**: webhook → same `/cases` flow; send verdict text + TTS audio + PDF link |
| Freeze thresholds; write the calibration results into README | Grievance draft (P1) citing the guideline clause + evidence | Case list page (P2 lite): my cases, status, deadlines |

**→ G3 at H32.**

### Phase 4 — Harden and package (H32–H38)
- **Adversarial testing swap:** A tests C's UI, B tests A's engine, C tests B's agent. Run the full matrix in 05 §2. Fix only what breaks the demo path or produces a wrong claim.
- B writes the README (setup, architecture diagram, calibration results, data sources, limitations). C drafts the deck. A prepares the "how the evidence works" slide and the judge Q&A answers.
- Two full demo rehearsals on the deployed build, timed.

**→ G4 at H38.**

### Phase 5 — Submit (H38–H44)
- Record the **2–3 min demo video**: live screen recording of the deployed app, real inputs, no cuts that hide failures.
- Fill the submission template (05 §4), upload the deck, check every link from an incognito window and from a phone on mobile data.
- Tag `v1.0`; deploy that tag; don't deploy after submission unless the rules allow it.

**→ G5 at H44.** H44–H46 is buffer only.

## Integration points (dependencies to watch)

| When | Producer → Consumer | Artifact |
|---|---|---|
| H1 | B → A, C | Evidence schema + API routes |
| H5 | A → B | `pre_post(plot, event_date) -> OpticalResult` callable |
| H6 | B → C | Deployed `/cases` + `/investigate` + SSE |
| H12 | A → B | `neighbours()`, `history()`, `sar()` callables |
| H14 | B → C | Final SSE event types + verdict payload |
| H24 | B → C | PDF data endpoint + re-check notifications |

## Daily stand-up questions (every 3–4 h, 5 minutes)
1. What works on the **deployed** build now?
2. What's unproven?
3. What could stop us submitting?
4. What are we cutting?
