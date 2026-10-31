# 07 — Build Contract (supersedes conflicting parts of 02–05)

Written 31 Oct 2026, 8:30 PM IST. This is what everyone (humans and agents) builds against.

## Deadline
Unstop shows both **1 Nov 6:00 PM IST** (stage timeline) and **1 Nov 11:59 PM IST** (at a glance). We plan for **submitted by 5:00 PM IST on 1 Nov**.

## What makes this more than a satellite dashboard

"Witness" is the organizing metaphor. A witness has to survive cross-examination, and anyone can check what it said.

1. **Placebo-tested evidence (the field's twin).** Before/after thresholds are not defensible in harvest season. We drop same-shape pseudo-plots on comparable cropland around the farmer's field and compute the identical statistic on each. The result is a case-specific false-alarm rate: "only 4 of 200 look-alike fields dropped this much." Regional harvest widens that distribution, so it is handled by the method and not by a tuned threshold. A matched-pixel counterfactual ("what your field would have looked like") is the visual form of this.
2. **Cross-examination.** Before giving a verdict the agent is attacked by a hostile insurance surveyor. Each objection (harvest? wrong plot? wrong date? cloud shadow? corrupt scene? regional trend?) is answered by a real computation on real data, and the outcome can be `conceded`. The witness will tell a farmer "your field doesn't show this."
3. **Replayable evidence.** The evidence hash covers polygon + scene IDs + seed + engine version + numbers. The PDF carries a QR code to `/verify/{hash}`, which re-downloads the public satellite data and recomputes every number live in front of an insurer, officer or judge. It isn't "AI said so"; it is a result anybody can reproduce.
4. **Honest about what models can't see.** Gridded weather (~9–25 km) routinely misses a hail cell. On the 25 Oct 2026 Sirsa reports, Open-Meteo shows under 1 mm and no hail codes, and NASA POWER shows under 0.4 mm. So weather **corroborates when present but its absence never refutes**; the product says "the weather model can't see a storm this small."

## Decisions that change the plan (also in decisions.md)

| Was | Now | Why |
|---|---|---|
| Next.js on Vercel + FastAPI on Cloud Run + Supabase | **One container:** FastAPI serves the built Vite + React app. `DATABASE_URL` defaults to SQLite and accepts Postgres. Deployable to any container host. | One URL, no CORS, fewer accounts, fewer ways for a live demo to fail with under 24 h left |
| PostGIS + pgvector | shapely in-process; hybrid BM25 + Gemini embeddings over a small clause corpus | We have one polygon per case and a ~60-page corpus; neither extension earns its setup time |
| Rubric requires weather corroboration | Corroboration = weather **or** official alert **or** cited news | See point 4 above |
| `plot_percentile` of neighbour pixels | Placebo p-value over same-shape pseudo-plots | Pixel variance is not plot-median variance; pixel percentile overstates significance |
| Sirsa 25 Oct as the only demo event | Sirsa stays as the honest hard case. Positive cases come from documented events with clean data. See `docs/validation/`. | Sirsa has no clean post-event optical and no weather signal |

## Non-negotiables
1. **No dummy data in the running app.** No fixture JSON, no seeded cases, no placeholder numbers. A cache of real API responses is fine and must keep provenance. Test fixtures live in `backend/tests/` only.
2. **The product works with no LLM.** Gemini improves parsing, narrative and news. If `GEMINI_API_KEY` is absent or Gemini fails, the deterministic verdict, cross-examination, and templated Hindi still appear, with `llm_used: false`. The UI never crashes on this path.
3. **Numbers come from code.** Any LLM text passes a validator: every digit sequence must exist in the evidence numbers, or the text is rejected and the deterministic template is used.
4. **Never claim what didn't happen.** "Filed" only after the farmer enters a reference number. Say "consistent with", never "you will be paid".
5. **Nothing invented about PMFBY.** Every rule shown cites a clause from the official document in `backend/data/policy/`.
6. Secrets only through env vars. Never commit them.
7. **Do not `git commit` or `git push`.** The human owner handles this.

## Layout and ownership (agents: stay inside your paths)

```
backend/app/evidence/schema.py     SHARED CONTRACT. Change only with a note in docs/plan/decisions.md.
backend/app/tools/geo/             GEO
backend/app/config.py, main.py, db.py, jobs.py, agent/, tools/{weather,alerts,news,policy,actions}.py, pdf/, verify.py   BACKEND
backend/data/policy/               RESEARCH produces, BACKEND consumes
web/                               WEB
docs/validation/                   RESEARCH + GEO
Dockerfile, README.md, docs/submission/   PACKAGING (last)
```

Python env: `cd backend && uv sync` then `uv run ...`. Python 3.12.

## Geo engine interface (`app.tools.geo`), called by the agent

All functions are synchronous, deterministic given inputs, raise `GeoUnavailable` on upstream failure after retries, and never return invented values.

```python
search_optical(polygon, start: date, end: date) -> list[SceneRef]
qa_scene(scene: SceneRef, polygon, previous_accepted: SceneQA | None = None) -> SceneQA
optical_compare(polygon, pre_id, post_id, seed) -> tuple[OpticalEvidence, NeighbourEvidence]
history(polygon, event_date, years=(y-1, y-2)) -> HistoryEvidence
search_sar(polygon, start, end) -> list[SceneRef]
sar_compare(polygon, pre_id, post_id, seed) -> SarEvidence
timeline(polygon, start, end) -> list[TimelinePoint]
render_chips(polygon, pre_id, post_id, out_dir, sar_pre_id=None, sar_post_id=None) -> list[Chip]
replay(core: ReplayCore) -> dict[str, float | None]     # recompute the same flat numbers
```

Grid: local UTM; 10 m bands for plot stats; context = plot bbox + 1.5 km. Target under 25 s per compare for a plot up to 10 ha.

## API

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/api/health` | | `{status, gemini: bool, version}` |
| POST | `/api/cases` | multipart: `audio?`, `text?`, `lat`, `lon`, `lang` | `{case_id, parsed:{crop,event_type,event_date,transcript,confidence}, needs:[...]}` |
| PUT | `/api/cases/{id}/plot` | `{polygon}` | `{area_ha, warnings[]}` |
| PATCH | `/api/cases/{id}` | `{crop?, event_type?, event_date?, event_time?}` | case |
| POST | `/api/cases/{id}/investigate` | | `{run_id}` (idempotent while a run is active) |
| GET | `/api/runs/{run_id}/stream` | `?after=seq` | SSE of `TraceEvent` as JSON; replays from `run_events` |
| GET | `/api/cases/{id}` | | `{case, evidence, actions}` |
| GET | `/api/cases/{id}/evidence.pdf` | `?lang=hi` | PDF |
| GET | `/api/cases/{id}/summary.mp3` | `?lang=hi` | audio; 404 if no TTS available (web falls back to browser speech) |
| POST | `/api/cases/{id}/submission` | `{channel, reference_no, submitted_at}` | case; 422 without a reference number |
| POST | `/api/cases/{id}/ask` | `{question, lang}` | `{answer, citations[]}` or an explicit "not covered" |
| GET | `/api/verify/{hash}` | | SSE: live recomputation with stored vs. recomputed per number |
| GET | `/api/artifacts/{path}` | | chips |
| POST | `/api/jobs/tick` | `X-Scheduler-Token` | job report |

`POST /api/cases` must work with `text` alone. If audio cannot be parsed, return `needs` instead of failing.

## Agent graph

```
parse → resolve_plot → gather_context(weather, alerts, news) → search_optical+QA
  ├─ good pre & post → optical_compare → (corroborate with SAR in parallel)
  └─ post missing/cloudy/corrupt → sensor_switch → sar_compare
→ history → cross_examine ─┬─ objection needs more data and budget remains → loop to search (other scene / wider window)
                           └─ done → verdict → policy → act(draft, deadline, re-check) → explain(hi/en, TTS) → seal(hash)
```

Real branching only. Budget: max 12 tool calls, 150 s soft limit. Each tool emits `tool_called` / `tool_result` trace events carrying the actual numbers. Rejecting a scene emits `scene_rejected` with reasons; changing sensors emits `sensor_switch`.

## Verdict rubric v2 (code, `agent/rubric.py`)

Let `p` be the placebo p-value and `corroborated` = weather or official alert or cited news.

| Level | Conditions |
|---|---|
| **not_damage_likely_harvest** | Harvest objection conceded. Evaluated first. |
| **insufficient** | No accepted optical post **and** no usable SAR pair; or fewer than 30 placebos and no other signal. Schedules a re-check. |
| **strong** | Accepted optical pre & post; `plot_delta_ndvi ≤ −0.15`; optical `p ≤ 0.05`; `corroborated`; no conceded objection |
| **moderate** | `corroborated` and one of: optical `p ≤ 0.10` with delta ≤ −0.10; SAR placebo `p ≤ 0.05`; `new_water_frac ≥ 0.2`. Or strong's field conditions without corroboration **and** the farmer's event date is unresolved by any source. |
| **weak** | Anything else with some signal |

SAR alone never exceeds moderate. Thresholds are frozen after calibration; record the measured false-positive rate in the README.

## Model IDs (checked 31 Oct 2026 at ai.google.dev/gemini-api/docs/models; all overridable by env)

`GEMINI_MODEL_PRO=gemini-3.1-pro-preview`, `GEMINI_MODEL_FLASH=gemini-3.8-flash`, `GEMINI_MODEL_TTS=gemini-3.8-flash-tts`, `GEMINI_MODEL_EMBED=gemini-embedding-2`. Hindi TTS support was not stated on that page; verify at first key use.
