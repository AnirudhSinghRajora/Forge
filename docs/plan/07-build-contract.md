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

## Addendum, 31 Oct 2026, 9:15 PM: the claim path and the three new signatures

Priority order: finish the core path first (plot → investigation → verdict → PDF → verify). Then these, in the order listed. Do not start a signature until the core path runs end to end.

### Corrections from the guidelines (mandatory, `backend/data/policy/key_rules.json` is the source of truth)
Current document: PMFBY Operational Guidelines 2023. Honour every `do_not_say` in that file.
- **The 72-hour countdown is not universal.** It applies to the localized and post-harvest add-ons, only where the State notified them (21.5.x). For widespread losses under basic cover, intimation "is not essential" (5.5). Route first, then show a countdown only if it applies.
- **Never say or imply "late means rejected" or "silently kills claims".** 21.5.9.2 calls intimation a pre-condition but adds that intimations received during the survey would be considered.
- **Cyclone is not a localized peril for standing crop.** A Godavari farmer with standing paddy is on area-yield cover (crop cutting + technology, no individual intimation). Post-harvest cover needs cut-and-spread crop and a State notification we have not found.
- **Arnab's 72 hours have passed** if counted from the landfall window IMD gives (02:00-08:00 IST, 28 Oct). No live countdown on that case.
- **Ask "are you insured?" first.** Andhra Pradesh enrolment is voluntary now. Name no AP insurer; none is verified.
- YES-TECH is **Gram Panchayat level**, not insurance-unit level (2.17). CSC is not a listed channel. CROPIC damage assessment is still at pilot initiation.
- The 25% rule does not make everyone eligible; it pays those who gave intimation (21.5.8, 21.5.9.3).
- No clause provides for farmer-submitted satellite evidence. The honest hook is that the insurer collects "any other available evidence". Never say an insurer must accept ours.

### Claim path (`Evidence.claim_path`, deterministic, BACKEND + WEB)
Ask: insured? crop stage (standing / cut and spread / harvested and stored)? Combine with peril and event date. Output one route with cited clauses, whether intimation is essential, whether a countdown applies, what the evidence is useful for on that route, and everything still unknown. State-notification status is `unknown` unless verified: say "confirm with your bank or 14447". This correctness is a differentiator: other teams will just say "72 hours".

### Signature 1: The Ten-Field Lottery (`Evidence.village.lottery`, GEO + BACKEND + WEB). Our headline.
Para 21.5.8: above 25% of insured area under intimation, "the sample loss survey will be conducted at 10 different randomly selected crop-land parcels" and the average "shall be applicable to all intimations". Damage from hail and floods is patchy, so this average depends heavily on where 10 parcels land.
We run that rule on real pixels: draw 10 random farmer-shaped parcels from comparable cropland around the plot, average the change, repeat 1000 times with a fixed seed. Show the spread, how often the average falls below half of this field's change, and animate real draws landing on the map.
Honesty, printed beside the result every time: this draws from cropland, not the real intimation list; it uses a satellite change index, not assessed crop loss; we don't know insured area, so the affected share is an indicator and not the legal 25% test. Never say the survey is unfair as fact. Say "here is how much the average can move for this event".

### Signature 2: The Vanishing (`Evidence.scale_fade`, GEO + WEB)
The same real change map, block-averaged at 10 m, 100 m, 500 m, 1 km and 3 km, on a slider. The farmer's loss visibly dissolves as cells grow to Gram Panchayat scale. Report the plot cell's value at each scale. Label: "our illustration from public satellite data, not output of YES-TECH". If the field shows no local signal, show that honestly.

### Signature 3: The Field Testifies (`Evidence.testimony_*`, BACKEND + WEB)
The evidence read in the first person, by the field, in Hindi, Telugu, or English: "मैं आपका खेत हूँ। 18 अक्टूबर को उपग्रह ने मुझे देखा, तब मैं हरा था…". Built from a deterministic template over real values; Gemini may polish only through the digit validator. Played over a flipbook of every satellite pass of this plot with dates. It must carry the verdict's caveats and must also work for "no damage visible". Never claim the field "knows" the cause: "consistent with".

### Village witness (`Evidence.village`)
Share of comparable cropland around the plot showing change consistent with damage, excluding harvest-like bare soil, as an indicator beside the 25% line. `nearby_real_cases` counts only real cases in our DB. Add a share link so a neighbour can add a field. Under this rule only those who intimated are paid, so the message is "tell your neighbours to report", backed by 21.5.8.

### Machine safety (all owners)
Run anything memory-heavy (batch validation, large rasters, Playwright) in its own capped scope, so it can't take VS Code down with it:
`systemd-run --user --scope --quiet -p MemoryMax=6G -p MemorySwapMax=0 -- <command>`
Run at most one heavy batch job at a time. VS Code closing stops all builders.

## Addendum 2, 31 Oct 2026, 9:45 PM: research corrections (overrides Addendum 1 where they differ)
Full detail: `docs/submission/facts.md` and `docs/validation/events.md`.

**The name is "The Ten-Field Draw" (दस खेतों का ड्रॉ), not "lottery"** in everything users or judges see. "Lottery" is our word, not the guidelines', and it implies unfairness. Random sampling is unbiased on average. We show how far one draw's average can move, never that the rule is unfair. No rupee payout figures anywhere: the formula's "X 25%" and the p.111 illustration do not agree, and pixels are not the survey's loss %.

**Para 21.5.8 does not govern standing Godavari paddy.** It covers localized and post-harvest claims in a unit over 25% under intimation, where the State notified the cover. Cyclone is not a localized peril, and Note 2 excludes paddy from localized inundation. `SurveyLottery.rule_applicability` is `may_apply` only on those routes; otherwise it is `illustration_only` and the UI says "what this rule would do if it applied here".

**Paddy inundation for Kharif 2026 is officially contradicted** (PIB 18 Nov 2025 vs. Lok Sabha 4 Aug 2026). The app never says it is covered.

**Demo cases, in order:**
1. **Hail, 2-3 March 2024, Bhiwani and Hisar** (events.md C1): standing wheat and mustard, official damage bins from under 25% to over 76%. Lead case for the Ten-Field Draw and the Vanishing. A signal case, not a PMFBY claim case: a Congress leader said no insurer covered Hisar that season. Say so.
2. **Cyclone Arnab, this week:** claim path, radar and sensor fallback. Landfall 02:00-08:00 IST on 28 Oct near 16.45 N, 81.90 E. Best crop figure: about 3.51 lakh ha, preliminary (Agriculture Minister, 29 Oct).
3. **Sirsa/Fatehabad:** the hard case. The storm was **Saturday evening 24 Oct**; 25 Oct is only UNI's dateline. The named villages appear to sit in Ratia tehsil, Fatehabad, about 50 km from our old point. Check whether the 24 Oct Sentinel-1 pass preceded the storm.

**The pitch, corrected:**
- Not "no farmer-side tool exists": Proof of Loss, CropSnap and Farmonaut are nearby. Say "we found no farmer-owned, placebo-tested, recomputable record of a specific loss".
- Not "first simulation of the rule": say "we did not find a published simulation of it".
- Not "farmers can't contest": written notice and grievance routes exist. Say "they have no evidence of their own".
- Keep the two systems separate. YES-TECH sets area yield under basic cover, and that is the Vanishing's context. A localized claim goes to a joint survey, or the 10-parcel sample above 25%. The 70/30 satellite weighting (21.5.9.4) is run by the State committee in a dispute; a farmer's PDF does not trigger it and the result binds the farmer too. Do not use 70/30 as a selling point.
- Rajasthan pending claims in old docs are wrong (official table: ₹1,525.2 cr). Use `facts.md` for every number. Haryana's ₹450 cr and ₹350 cr are farmers' claims in one report and must be attributed as such.

## Addendum 3, 31 Oct 2026, 10:35 PM: cold-run speed is the top priority
A first run on a new pin took about 240 s and still lost the signature tools to timeouts; a repeat took 8.7 s. Judges will drop their own pins, so warming demo cases does not solve this.

**Hosting region:** Sentinel data on Planetary Computer is served from Amsterdam. Host the container in the Netherlands or West Europe (e.g. Cloud Run `europe-west4`, Fly `ams`), not Mumbai. This replaces the `asia-south1` decision.

**Run shape, targets measured cold on a new pin from this machine:**
1. Verdict-relevant evidence first; first useful trace within 5 s and a verdict inside 90 s.
2. Each context window is read once per run and shared by compare, village, scale fade and chips.
3. Exhibits that do not affect the verdict (village, scale fade, chips, history where optional) finish after the verdict and fill in live. The hash is sealed only when they settle, with a clear "still computing" state. An exhibit that fails later says so and offers a retry; it never takes the verdict down.
4. No tool may report success with fewer real numbers than it claims.

## Addendum 4, 31 Oct 2026, 10:40 PM: the evidence method, corrected
GEO's validation found two faults. (1) Field-vs-ring placebo has low power inside a swath, because the ring shares the damage: plots with NDVI 0.75 → 0.39 reached only p≈0.035, and most damaged plots missed p≤0.05. (2) p≤0.10 is not trustworthy: measured false-positive rate 15.4% against a nominal 10%, while p≤0.05 measured 5.0% (one scene pair; holdout pending).

**The witness answers two different questions, and both answers are useful:**
- **Far test: did this field change more than comparable fields outside the storm area?** Same-shape placebos in a 5-12 km annulus (`NeighbourEvidence.far_placebo`). This detects the event.
- **Ring test: did it change more than its immediate neighbours?** The existing placebo. This describes how local the loss is. "Far yes, ring no" is reported as "your whole area was hit, not only your field". It is never presented as weakness.
- For events bigger than 12 km (a whole delta under a cyclone) the far test loses power as well, so history and the pre-event trend carry that case. Say so.

**Rules, fixed before the holdout runs (rubric v3):**
- Field signal = `plot_delta_ndvi` at threshold AND (`far p ≤ 0.025` OR `ring p ≤ 0.025`), Bonferroni across the two tests.
- `strong`: delta ≤ −0.15, field signal, corroborated, no conceded objection.
- `moderate`: delta ≤ −0.10, field signal, corroborated; or SAR placebo p ≤ 0.05 with corroboration; or new water ≥ 0.2 with corroboration. **The p ≤ 0.10 tier is removed.**
- Add a pre-trend check: the same statistic on the last accepted pre-event pair. A field already falling before the event gets a conceded objection.
- **Post scene:** first accepted scene at least 5 days after the event; if none exists, the earliest accepted scene, with the verdict noting it may be too early. Hail damage develops: Bhiwani's band moved −0.066 on 4 Mar and −0.146 on 9 Mar. This rule was chosen after seeing Bhiwani, which must be disclosed, so it gets tested on an event not used to design it.

**Validation order, each reported whatever it shows, no retuning after the holdout:**
1. Other-year controls at Bhiwani (2022, 2023, 2025). Until they clear, nobody calls the band hail.
2. Holdout false-positive rate for rubric v3 on 13 → 18 Oct 2025, plus a no-event March window.
3. An independent event not used in design: Sirsa hail, 14 Mar 2025 (events.md C2).

**Second data source:** Earth Search (`earth-search.aws.element84.com/v1`, public, no account) has Sentinel-2 `S2C_44QND_20261031_0_L2A` over the Godavari delta, 40% tile cloud, not yet on Planetary Computer. Add it as a fallback source for Sentinel-2. `ReplayCore` and provenance record which archive each scene came from, and QA and offset handling apply unchanged. Planetary Computer stays primary.

## Addendum 5, 31 Oct 2026, 11:00 PM: what the real numbers say, and the new order
Measured on the Bhiwani in-swath plot (28.700911 N, 76.215719 E, the most extreme of 200 scanned): the Vanishing runs −0.437 (10 m), −0.352, −0.267, −0.164, −0.098 (3 km). The Ten-Field Draw averages −0.080 with a p05-p95 of −0.129 to −0.039.

**New exhibit order: (1) The storm's footprint and the Vanishing, (2) the Ten-Field Draw.** The Vanishing is the stronger and simpler result. Its question is about area-yield scale (Gram Panchayat), as Addendum 2 requires.

**The Draw gets a second scenario.** Real surveys sample the intimation list, and reporting farmers are likely to be the damaged ones, so drawing from all cropland understates the average. Show both side by side: "all cropland" and "only fields that visibly dropped" (`affected_only_*`). The true list lies somewhere between, and we don't know it. Report the spread within each. Do not lean on the plot-vs-average gap as a survey finding.

**Selection must be disclosed.** Any plot chosen from a scan is labelled as such, with the count ("strongest of 200 scanned"). Add a typical in-band plot beside the extreme one, chosen by rule (the median in-band plot), and report the distribution of the Draw and Vanishing results across in-band plots.

**Arnab:** at tile scale, the east-west gradient is mostly seasonal (about −0.1 is normal for these weeks in 2023 and 2024). No Arnab signal is established at tile scale. Do not present the 31 Oct gradient as storm damage. Reports of flattened paddy are not contradicted: lodged paddy can stay green.

## Addendum 6, 31 Oct 2026, 11:27 PM: typical plots and what we may claim
Forty plots drawn at random from the band (rule fixed in advance; note the intended pre-NDVI filter was not applied) give: plot change median −0.125; Vanishing median at 100 m to 1 km about −0.13, at 3 km −0.085, so a typical field loses about a third at 3 km. **The dramatic fade (−0.437 to −0.098) belongs to the strongest of 200 scanned plots and must never be shown without that label.**

**Story order, final unless the holdout changes it:**
1. **The storm's footprint and the two questions.** The band on the region map (labelled "consistent with"), then far test vs ring test. This is the lead: a field being unlike fields outside the storm is the result that held up (design plot far p 0.005; holdout pending).
2. **The Vanishing, shown honestly.** Works on whatever case is open. In the pitch, show the labelled strongest plot and the typical plot side by side. The point: when a field was hit harder than its surroundings, area averages can't show it; when a whole area was hit, they mostly can. That is more credible than a single dramatic slider.
3. **The Ten-Field Draw.** All cropland averages −0.07, fields that visibly dropped −0.245, luck of the draw about ±0.035. **The second scenario is partly mechanical:** those parcels are below −0.15 by definition, so these two are bounds, not an estimate. Allowed claim: "the average depends heavily on who is on the list, and nobody outside the insurer can see that list". Not allowed: "who is on the list matters more than luck" as a measured finding, or anything implying the rule is unfair.

Demo plots: typical 28.715212 N, 76.231138 E (chosen by rule; moderate at best) and strongest 28.700911 N, 76.215719 E (labelled). Live pins from judges will mostly and correctly show little.

**Wording correction to Addendum 4:** "far yes, ring no" reads "the effect does not look limited to your field", not "your whole area was hit". A ring test that misses its threshold does not show the neighbours changed as much; on the strongest plot they fell −0.12 against the field's −0.369. Exhibits other than the two answers make no claim about who was hit.
