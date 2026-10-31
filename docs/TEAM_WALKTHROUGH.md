# FasalSaakshi: team walkthrough

**For:** the three of us who must each explain all of this to a judge. The rules as we recorded them say every member must understand and independently explain the project. If you didn't write a part, learn it here and say honestly who wrote it if asked.

**How to use this:** read it once with the code open. Then answer section 5 out loud without looking.

**Where numbers come from:**
- Engine numbers: `docs/validation/engine-results.md` or the live API.
- External numbers: `docs/submission/facts.md`, with its attribution. Do not quote a number from memory or from older plan files.
- The final sealed records, through `GET /api/cases/{id}`:

| Record | Case id | Hash starts | Verdict | Full check |
|---|---|---|---|---|
| Strongest of 200 scanned | `1ce7e64b754248abb18f0d29ac6203eb` | `6092fe1c9ef1` | `strong` | 104 of 104 |
| Typical, median of the original 40 | `c157d2d75ce94501ad08930624a10e76` | `56aadcb68360` | `weak` | 104 of 104 |
| Arnab, near Anaparthi, strongest of 51 usable | `3ea2ca9c8ef14a05af4a407ab4003230` | `17a3b0d203d5` | `weak` | 85 of 85 |

Independent runs from a clean database produced identical hashes.

## 1. The product in five sentences

A farmer reports a crop loss and outlines the field. The app compares that field's change in greenness with look-alike fields on the same dates. A hostile surveyor then attacks the evidence with nine objections, and the app can concede. A fixed rubric gives the verdict, a router finds the PMFBY route, and the numbers are sealed with a hash. Anyone can open the QR link and recompute those satellite numbers from the public archive. The verdict and weather are checked for tampering only.

Three things we never claim: that hail caused it, that an insurer has to accept it, or that anyone gets money.

## 2. Guided tour of one request

Follow this with the files open. All paths are from the repo root.

### Step 1. The report

| What | Where |
|---|---|
| Screen | `web/src/screens/Start.tsx`. Takes text, or voice through the browser's speech recognition or a recording |
| API call | `web/src/api.ts`, `POST /api/cases` |
| Route | `create_case` in `backend/app/main.py` |
| Pin check | `check_pin` in `backend/app/agent/plot.py`, which keeps the pin in the service area |
| Parsing | `parse_text` in `backend/app/agent/parse.py`: keywords and date patterns, no LLM needed. If Gemini is on, `llm.parse_text` or `llm.parse_audio` result is merged in |

If something is missing, the response carries `needs` and `questions`. It never invents a crop or a date. Shortcuts in `web/src/places.ts` only move the map and show a reported date with its source. They set no date, and create no case and no evidence.

### Step 2. The field and the questions

| What | Where |
|---|---|
| Draw the plot | `web/src/screens/Plot.tsx`, `web/src/map/PlotMap.tsx` |
| Save it | `put_plot` in `main.py`, `validate_polygon` in `agent/plot.py`. Warns under 0.2 ha and over 10 ha |
| Confirm details | `web/src/screens/Confirm.tsx`, then `patch_case` in `main.py`. Insured? Crop stage? These decide the claim route |

### Step 3. Starting the investigation

`investigate` in `main.py` calls `start_run` in `backend/app/agent/runner.py`. It is idempotent while a run is active, so a double click doesn't start two runs. Runs live in a thread pool, so a closed browser doesn't stop one.

Events are written to the `run_events` table by `Tracer` (`agent/trace.py`). The browser reads them over SSE (`stream_run` in `main.py`, `web/src/sse.ts`, `web/src/screens/Investigate.tsx`). A refresh replays from the table.

### Step 4. The graph

`run_investigation` and `build_graph` in `backend/app/agent/graph.py`. Every node is wrapped by `guard`: an exception becomes a trace event and partial evidence, never a crash. Evidence is persisted after each node.

| Node | Function | What it does |
|---|---|---|
| `parse` | `n_parse` | Loads the case. If no date was given, proposes one from the weather and asks for confirmation |
| `resolve_plot` | `n_resolve_plot` | `geo.plot_info`, creates `Evidence`, sets the seed with `make_seed` |
| `gather_context` | `n_gather_context` | District, weather, alerts and related reports, in parallel. Related reports need Gemini and never change a level |
| `planner` | `n_planner` | Takes the default path: search optical images. An LLM choice exists only under `LLM_PLANNER=true`, which is off by default, because it could move which images are read |
| `search_optical` | `n_search_optical` | Finds scenes, runs QA, picks the pre and post scenes |
| `optical_compare` | `n_optical_compare` | The core statistic and both placebo tests. Starts radar in the background |
| `sensor_switch`, `sar_compare` | `n_sensor_switch`, `n_sar_compare`, `run_sar` | Radar when no optical pair is available. Same orbit and direction only (`_pick_sar_pairs`) |
| `history` | `n_history` | The same calendar window in past years, in the background |
| `cross_examine` | `n_cross_examine` | The nine objections. May loop back to search if more data could settle a concession (`_pick_followup`) |
| `verdict` | `n_verdict`, `decide` | Applies the rubric |
| `policy` | `n_policy` | Claim route and cited clauses |
| `act` | `n_act` | Intimation draft and re-check. Nothing is filed |
| `explain` | `n_explain` | Deterministic templates in Hindi, English and Telugu. Polish runs only under `LLM_POLISH=true`, which is off by default |
| `exhibits` | `n_exhibits`, `_exhibit_runners` | Draw, Vanishing, chips and timeline, as they land. Late radar or history triggers `_reexamine` |
| `seal` | `n_seal`, `seal_core`, `evidence_hash` | Builds `ReplayCore` and hashes it |

**Why this counts as an agent:** branching is an explicit state graph, and the branches are real. A rejected scene leads to a sensor switch. A conceded objection leads to a new search. A weather peak on another date leads to a redate and a re-run. All of it is visible in the trace. The budget is 12 counted tool calls, with a 150 s soft limit.

### Step 5. The geo engine (`backend/app/tools/geo/`)

| File | What to know |
|---|---|
| `stac.py` | Searches Planetary Computer, with Earth Search as Sentinel-2 fallback. `scene_archive` tells you which archive a scene id belongs to |
| `qa.py` | Q1 bands present. Q2 plot clear. Q3 reflectance physically plausible. Q4 vegetation pixels look like vegetation. Q5 sudden area-wide shift against the previous scene, which makes a scene suspect |
| `optical.py` | `optical_compare`, `history`, `timeline` |
| `placebo.py` | `sample_placements` and `p_value`. Pure numpy, seeded |
| `far.py` | Placebos in a 5-12 km annulus, read from seeded windows, one per sector so they can't all land on one side of a storm |
| `twin.py` | `field_twin`: control pixels that matched the plot's pre-event NDVI path, and what they did afterwards |
| `sar.py` | Radar VH change, radar placebo, new water |
| `village.py` | `village_witness`, `simulate_surveys`: the Ten-Field Draw and the affected share |
| `scale.py` | `scale_fade`, `block_average`: the Vanishing |
| `replay.py`, `replay_field.py` | `flatten_numbers`, `replay`, `FieldReplay`: recomputing the sealed numbers |

The Draw's result sits under `Evidence.village` in `backend/app/evidence/schema.py`. Its sub-field there still has an old working name that we dropped on purpose (Addendum 2 of the contract explains why). You will see it in code and raw JSON. If asked, say that: it was an early working word, and it implies unfairness we do not claim.

### Step 6. Cross-examination and verdict

`backend/app/agent/cross_exam.py`, `run`. Pure functions over `Evidence`. Each objection records the test it ran and the values it measured.

| Objection | Conceded when |
|---|---|
| `harvest` | Over 60% of the plot is bare, the whole field fell, and neighbours or history support it |
| `wrong_plot` | Pre-event NDVI under 0.3, or images show water before the event |
| `wrong_date` | Weather shows nothing near the date but does show a peak on another nearby date. Then the graph may redate. No signal at all never counts against the farmer |
| `cloud_shadow` | Under 80% of the plot is clear on an image used |
| `corrupt_scene` | Scene suspect, with no second sensor backing it |
| `regional_trend` | Neither far nor ring is significant |
| `pre_trend` | The field was already falling by -0.10 or more before the event |
| `too_small` | Under 0.2 ha |
| `stale_crop` | Past years' greenness differs by over 0.2 |

`backend/app/agent/rubric.py`, `decide_level`, reads top to bottom:

1. Harvest conceded: `not_damage_likely_harvest`.
2. No usable data, or too few placebos and no other signal: `insufficient`.
3. No crop visible before the event: `weak`.
4. Accepted optical pair, change ≤ -0.15, field signal, corroborated, nothing conceded: `strong`.
5. Corroborated, and one of: change ≤ -0.10 with field signal; radar p ≤ 0.05; new water ≥ 0.2: `moderate`.
6. Otherwise: `weak`.

Field signal = far p ≤ 0.025 **or** ring p ≤ 0.025. A test only counts with at least 30 placebos.

Corroborated = the weather model, or an official alert whose hazard matches the report (`corroboration`, `matching_alerts`). News is shown as related reports and never changes a level, because search hits carry no reliable date, place or peril check. So a hail report that the weather model misses and no alert covers stays `weak`, and the text says why.

A deciding p from 0.01 to 0.075 is reported as near the threshold (`near_threshold`, `near_line_decides`). The thresholds don't move. The caveat reads: "a slightly different drawing of this field could change this result".

### Step 7. Claim path

`backend/app/agent/claim_path.py`. `route_claim` picks the route. `with_deadline` adds the countdown only on an add-on route and only while the time is open.

| Situation | Route | Intimation |
|---|---|---|
| Not insured | `not_insured` | Not relevant |
| Insured unknown or stage unknown | `undetermined`, asks the questions | Warns that if an add-on applies, the rule asks for 72 hours |
| Standing crop, hail or other localized peril | `localized_addon`, if the State notified it | Essential |
| Cut and spread, listed peril | `post_harvest_addon`, if the State notified it | Essential |
| Standing crop, cyclone or other perils | `area_yield_basic` | Not essential (para 5.5) |
| Standing paddy, inundation | `area_yield_basic`, with a note that official statements conflict | Unknown |
| Crop already off the field | `outside_cover`, citing PIB's wording that losses after removal from the field are not covered | Not relevant |

The demo records never set insured, because Bhiwani is a signal case and insurance is the farmer's answer in Godavari. So their route reads "not determined yet", and the Draw is labelled as an illustration. State notification always stays unknown. Rule text and `do_not_say` entries are in `backend/data/policy/key_rules.json`. If the 72 hours have passed, the wording comes from that file: report now, keep the reference number, and intimations received during the survey would also be considered.

### Step 8. Words

- `agent/explain.py`: headlines, `tests_line` (the two answers in words), templates. Deterministic.
- `agent/testimony.py`: The Field Testifies. Deterministic.
- `agent/validate.py`: any LLM text goes through this, such as policy answers. Every digit sequence must match the evidence, and payout talk and banned claims are rejected. On failure the template is used.
- `backend/app/disclosures.py`: the selection label ("strongest of 200", "median of the original 40", "strongest of 51 usable"), shown wherever such a plot's result appears, including the PDF. It is not part of the hash.

### Step 9. What the farmer sees

- `web/src/screens/Verdict.tsx`, with `components/Testimony.tsx`, `components/TwoQuestions.tsx`, `map/Vanishing.tsx`, `components/TenFieldDraw.tsx`, `components/ObjectionCard.tsx`.
- `web/src/screens/Action.tsx`: route, draft, and "I submitted". `POST /api/cases/{id}/submission` refuses without a reference number, so we never claim a filing that didn't happen.
- `backend/app/pdf/render.py`: the evidence PDF with the QR code. The QR uses `PUBLIC_WEB_URL`.

### Step 10. Verification

`backend/app/verify.py`, with `web/src/screens/Verify.tsx`.

1. `_prepare` recomputes the hash from the stored core, and checks `verdict_digest` against the stored verdict and weather. A difference means `tampered`, before any download.
2. It checks each scene would still be read from its sealed archive.
3. If a full check already exists and no re-run was asked for, it shows that check with its time, labelled as stored.
4. Otherwise `_Job.run` starts a background job. It clears GDAL's HTTP cache and reads with `fresh=True`, so the bytes come from the archive.
5. Groups run from cheapest to most expensive, each with its own time budget: `field_pre`, `field_post`, `field_extra`, `sar_field`, `history`, `ring`, `far_twin`, `radar`, `village`, `scale_fade`.
6. Results: `verified`, `field_verified`, `partial`, `mismatch`, `engine_changed`, or `upstream_unavailable`. An outage is never shown as a mismatch.

**Scope, as the page says it:** "Satellite numbers are recomputed; the verdict and weather are checked for tampering only." New downloads are limited per IP (`RATE_VERIFY_PER_HOUR`, default 3), so a stored check is what most visitors see.

### Step 11. Background jobs

`backend/app/jobs.py`: archive SACHET alerts, re-run open re-checks when due, keep deadlines current. `POST /api/jobs/tick`, or in-process APScheduler.

## 3. The statistics in plain words

### NDVI and the statistic

NDVI is a greenness index from red and near-infrared light, roughly 0 to 1 here. We take the median over the plot before and after, and subtract. On the sealed record of the plot that is the strongest of 200 scanned: 0.7525 to 0.3857, a change of -0.3689.

A drop alone means nothing in harvest season. Ripening and cutting both lower NDVI. So we need a comparison.

### The placebo test

Take the plot's exact shape. Drop it at random onto comparable land nearby, on the same two dates. Compute the same statistic each time. That gives up to 200 "what a field like this did anyway" numbers.

"Comparable" means pre-event NDVI within 0.15 of the plot's and pre-event spread (IQR) within 0.05, with at least 80% of pixels valid in both scenes.

Then ask: how many placebos dropped at least as much as our plot?

**p = (k + 1) / (n + 1)**, where k is that count and n is the number of placebos.

Worked from the sealed record: far test, k = 0 of n = 200, so p = 1/201 = 0.005. Ring test, k = 11 of 200, so p = 12/201 = 0.0597.

The +1 means p is never zero. The far p of 0.005 is the smallest possible value with 200 placebos, not a measure of how far past the placebos the plot went.

### Why two tests, far and ring

They answer different questions.

- **Ring (300 m to 1.5 km from the plot edge):** did it change more than its immediate neighbours? This says how local the loss is.
- **Far (5-12 km away):** did it change more than comparable fields outside the storm area? This detects the event.

We added far because of a real failure. Inside a swath, the ring shares the damage, so a badly hit plot looks ordinary against its neighbours. On the Bhiwani scan, the ring test sat at its no-event rate across the window and fired on few of the plots that visibly dropped (engine-results section 3a).

How to read the four outcomes:

| Far | Ring | Say |
|---|---|---|
| Yes | Yes | Different from distant fields and from neighbours |
| Yes | No | **The effect does not look limited to your field.** Not "all the neighbours were hit". A ring test that misses its line doesn't show neighbours changed as much. On the sealed record, they fell -0.12 against the field's -0.3689 |
| No | Yes | Looks local to this field |
| No | No | Doesn't stand out. That doesn't mean no damage happened |

For an event wider than 12 km, the far test loses power too, because the placebos are also hit. History and the pre-event trend carry that case. This matters for Arnab.

### Why Bonferroni

If you run two tests and accept either, you get two chances at a false alarm. Bonferroni is the simplest fix: split the budget. To keep the overall rate near 5%, each test must clear 0.05 / 2 = 0.025.

With 200 placebos that means k ≤ 4, since 5/201 = 0.0249. Small counts decide this. On the Arnab record, the far test has 3 of 136 placebos, so p = 4/137 = 0.0292, which misses. With 2 of 136, p = 3/137 = 0.0219 would have passed. Be ready to say so.

We also removed the old p ≤ 0.10 tier. It measured 15.4% false positives against a nominal 10% (engine-results section 2).

### What the p-value does and doesn't mean

**Does mean:** among comparable places on the same dates, this share dropped at least this much. If this field were just another such place, a drop this extreme would be this rare.

**Does not mean:**
- Not "99% sure there was damage". p = 0.01 is not the chance the claim is true.
- Not evidence of the cause. Disease, a management choice or a local crop pattern could also make a field stand out.
- Not the size of the loss. That is the change itself, and even that is an index, not yield.
- Not independent of place. Placebos sit in one region on one scene pair, and overlapping ones are correlated. So the real uncertainty is wider than the number suggests.

### Seed sensitivity

Placebo positions are random but seeded, so a replay gets the same answer. `make_seed` in `graph.py` hashes the polygon and event date. So the same record reproduces exactly, but a slightly different polygon or date re-samples.

We measured this: same data, 30 seeds, on 7 plots (engine-results 7a). Levels assume corroboration is present.

| Plot | Change | Far p (min, median, max) | Levels across 30 seeds |
|---|---|---|---|
| Strongest of 200 scanned | -0.3689 | 0.0050, 0.0050, 0.0050 | strong 30 |
| Typical, median of the original 40 | -0.1259 | 0.0244, 0.0537, 0.0732 | weak 29, moderate 1 |
| In-band plot 18, picked for being near the line | -0.2045 | 0.0050, 0.0249, 0.0448 | strong 20, weak 10 |

Clear cases are stable. Near 0.025, far p moves by a factor of about 4-8, because the seed picks both which far windows are read and which placements land in them. The level flips on up to a third of seeds. Five of the seven plots were picked for being near the line, so that's the worst case, not the typical one.

We did not change the method, because that would invalidate the locked runs. We also rejected multi-seed runs at seal time, which would multiply slow reads. Instead, a deciding p from 0.01 to 0.075 is labelled **near the threshold**.

Two things to know:
- The strongest plot's ring p is 0.0597 on its sealed record. The 30 seeds gave 0.0249 to 0.0498. So the sealed draw lies just outside the range those seeds showed. Thirty seeds don't cover every draw. Its verdict rests on the far test, which didn't move.
- The caveat shows on the typical and Arnab records, because their deciding far p (0.039 and 0.0292) is in the band. It doesn't show on the strongest plot's verdict, because far p 0.005 clearly passes. Its ring answer still reads "No, but near the line".

### The field's twin

`twin.py` picks 300 control pixels whose pre-event NDVI path best matches the plot's, then reports what they did after. It's a picture of "what your field might have looked like". On the extreme plot it rests on only 2 pre-event scenes, so treat it as illustration (engine-results 3d).

### False-positive rate

**Rubric v3, locked (engine-results 7).** Two no-event windows, 200 plots each, rules frozen in advance, run once. Both gave strong field conditions on 2.0% of plots (CI 0.8-5.0) and moderate on 2.5% (CI 1.1-5.7). "Field conditions" means the plot rule without corroboration.

Be careful with these numbers:
- Each window is one scene pair with correlated plots, so the CIs are too narrow.
- "No event" means none reported in our sources. We didn't search exhaustively for March 2025 around Bhiwani.
- In the October window, far p-values lean slightly low, so the far test may be slightly liberal there.

**Design window (engine-results 2).** Ring test on 299 random squares, Sirsa, Oct 2025. p ≤ 0.05 fired on 5.0% (CI 3.1-8.1), and p ≤ 0.10 on 15.4%. Thresholds were set after seeing this window, so it isn't the headline number.

**Sensitivity is a separate question, and the weak spot.** False-alarm rates say nothing about whether the method detects real events. See questions 8, 10 and 21.

### The Vanishing

The same change map, averaged into blocks of 10 m, 100 m, 500 m, 1 km and 3 km. The 10 m level reports the plot's own median. Blocks are centred on the plot, which is the kindest alignment for it, and a real administrative unit wouldn't be.

| Plot | 10 m | 100 m | 500 m | 1 km | 3 km | Source |
|---|---|---|---|---|---|---|
| Strongest of 200 scanned | -0.3689 | -0.3518 | -0.2667 | -0.1635 | -0.0983 | Live record |
| Typical, median of the original 40 | -0.1259 | -0.1233 | -0.1196 | -0.1300 | -0.0811 | Live record |
| Arnab, strongest of 51 usable | -0.3419 | -0.3403 | -0.2755 | not measured | not measured | Live record |

Across the 40 in-band plots, the typical field barely fades until 3 km, where about a third goes. The Arnab plot's coarser cells have no value on that clouded image.

**The point:** when a field was hit harder than its surroundings, area averages can't show it. When a wider stretch fell together, they mostly can. It's our illustration, not YES-TECH output. It's context for area-yield cover, and has nothing to do with how a localized claim is assessed.

### The Ten-Field Draw

Para 21.5.8: above 25% of insured area under intimation, a sample survey runs at 10 randomly selected parcels using the loss intimation list, and the average applies to all intimations.

We simulate 10 random parcels 1000 times with a fixed seed, on two pools. Across 40 in-band plots (engine-results 3e, medians):

| Pool | Average | Spread of one draw (p05-p95 width) |
|---|---|---|
| All cropland | -0.069 | 0.072 |
| Only fields that visibly dropped | -0.245 | 0.067 |

So the luck of one draw is about ±0.035. On the live records: strongest of 200 scanned, -0.080 and -0.239. Typical, -0.0653 and -0.2309. These demo records aren't on a route where para 21.5.8 governs, so the app labels the Draw as what the rule would do if it applied.

**The second pool is partly mechanical.** Those parcels are below -0.15 by definition, so its average has to be low. These two are bounds, not an estimate.

**Allowed claim:** "the average depends heavily on who is on the list, and nobody outside the insurer can see that list."

**Not allowed:** that who is on the list matters more than luck, as a measured finding, or anything implying the rule is unfair. Random sampling is unbiased on average. We have no record of any real draw. No rupee figures: the formula and the guidelines' own illustration don't agree.

## 4. Why each design decision was made

| Decision | Why |
|---|---|
| Placebo test, not a threshold | Harvest moves whole regions. A fixed before/after line would fire on normal harvest. A case-specific comparison handles this by method |
| Placebo over plot-shaped pieces, not pixel percentile | Pixel variance isn't plot-median variance. Pixel percentiles overstate significance |
| Match placebos on spread too | The data showed false alarms depended on within-plot uniformity, not on starting level (engine-results section 2) |
| Far and ring | The ring alone misses swath damage. See section 3 |
| 0.025 on either test; p ≤ 0.10 removed | Bonferroni, and p ≤ 0.10 over-fired |
| Post scene at least 5 days after the event | Hail damage develops. Bhiwani's band contrast moved -0.066 on 4 Mar and -0.146 on 9 Mar. Chosen after seeing Bhiwani, which we disclose |
| Scene QA before any index | The 28 Oct 2026 Sirsa pass has about 0% metadata cloud and impossible reflectance |
| Cross-examination can concede | A witness who can't say "your field doesn't show this" isn't credible |
| Weather corroborates but never refutes | On the Sirsa reports of 24 Oct 2026, gridded models show under 1 mm. A coarse grid can miss a hail cell |
| Radar alone caps at moderate | It's a less direct signal for crop loss |
| Verdict before exhibits | A cold run takes minutes on a thin link. Exhibits that can't change the verdict shouldn't hold it up |
| At most 2 background reads at once | On a thin link, parallel reads meant every exhibit timed out and none landed |
| Verdict and its text are deterministic; LLM polish and planner off by default | The same evidence gives the same level with or without an LLM. A demo shouldn't depend on one API |
| News never changes a level | Search hits carry no reliable date, place or peril check. It's shown as related reports |
| Report thresholds unchanged, label 0.01-0.075 as near the threshold | Seeds showed results near 0.025 aren't stable. Changing the method would invalidate the locked runs. Multi-seed runs at seal would multiply slow reads |
| Map shortcuts set no date | A preset date would be our input presented as the farmer's. A different date also re-samples |
| Digit validator on LLM text | Policy answers can't introduce a number that isn't in the evidence |
| Route before any countdown | 72 hours applies only to the localized and post-harvest add-ons, where notified. For widespread loss, intimation "is not essential" (para 5.5) |
| Hash over the replay core, reads with caches bypassed, digest of verdict inputs | Reading our own cache would prove nothing. The verdict and weather can't be recomputed, so they are only checked for tampering, and the page says so |
| Earth Search as fallback, per-scene archive in the hash | Recent passes can appear there sooner. Its metadata still says `offset: -0.1` though the offset is already removed, so we trust its flag and fail if the flag is missing (engine-results section 4) |
| One container, SQLite default | One URL, no CORS, fewer ways for a live demo to fail |
| "Ten-Field Draw" as the name | The earlier word was ours, not the guidelines', and it implied unfairness |
| No rupee figures | The guideline text is inconsistent on the formula, and pixels aren't the survey's loss % |
| Typical plot beside the strongest | Showing only the strongest of 200 would mislead |

## 5. Hard questions

Answer the question that was asked. Say "we don't know" when that's the truth.

### 1. "Isn't your strongest plot cherry-picked?"

Yes, it was selected, and we label it: the strongest of 200 scanned. So we also show a typical plot chosen by a rule fixed in advance: the median of the original 40 random in-band plots. That plot's change is about a third of the strongest one's. The dramatic fade belongs only to the strongest. Disclose this too: the pre-event filter we intended wasn't applied to those 40. With it, the median is 28.710543, 76.228524 at -0.1283, so the typical story barely changes. One point in its favour: the random scan's most extreme plots landed beside Maneharu without being aimed there, and farmers had named that village. That's a cross-check, not proof.

### 2. "Why is the typical plot only weak?"

Because the rubric says so, and we didn't change it. Its change is -0.1259, which misses the -0.15 line for strong. Moderate needs a field signal at p ≤ 0.025. Its far p is 0.039 (7 of 204) and ring p is 0.1859 (28 of 155). So the verdict is `weak`, and it's **near the threshold**: on 30 seeds, far p ran from 0.0244 to 0.0732, with 29 weak and 1 moderate. The app also concedes the regional trend and a likely different crop in past years. Median in-band change is -0.125, so many fields in this band are in the same position. At the single-field level, a typical in-band plot isn't separable with this test. That doesn't mean it wasn't damaged.

### 3. "Does radar confirm it?"

No. Across the band, VH contrast is +0.50 dB ascending and -0.47 dB descending, so the orbits disagree. On the sealed record of the strongest of 200 scanned, VH is +1.17 dB, radar p is 0.6617, and the verdict carries the caveat "Optical and radar disagree". We call that a real miss. We don't know why. Don't offer a theory as a finding.

### 4. "Has this been validated against ground truth?"

No. There's no plot-level ground truth for any event here. Reports give villages and district-level loss bins. Nobody has checked these fields. We can show consistency: the band doesn't repeat in 2022, 2023 or 2025, it starts at the right time, and it sits by a named village. Punjab's pre-registered test was against reported flooding, not field records, and it was partial. We can't state accuracy, and we don't have a crop-type map. A proper test would compare against crop-cutting or joint survey records for specific plots.

### 5. "Will an insurer accept this?"

We don't know, and none has said it would. No clause provides for farmer-submitted satellite evidence. The honest hook is that the insurer collects "any other available evidence" on occurrence and severity (para 21.5.6.2). Any stakeholder can give written notice with "proofs/data/reports" within 7 days. Do not use the 70/30 weighting (para 21.5.9.4) as a selling point. It runs through the State committee in a dispute, a farmer's PDF doesn't trigger it, and the result binds the farmer too.

### 6. "How is this different from Proof of Loss or CropSnap?"

Parts of this exist, and we say so.
- **Proof of Loss:** open-source, farmer-side, photos and a claim packet, 72-hour framing, and the same point about weather grids. It's the closest pitch. We saw no satellite placebo test or recomputation in the README we read.
- **CropSnap (Agtuall, ESA-supported):** farmer photos plus Sentinel-1, Sentinel-2 and weather. It's the closest technology, and its primary segment is insurers. We saw no public recomputation.
- **Farmonaut:** sells field-level monitoring to farmers, by its own vendor pages. We haven't tested it.

Our claim: "We did not find a farmer-side tool that gives a field its own placebo-tested satellite evidence and lets anyone recompute it." We don't claim to be the only ones, because we might have missed something.

### 7. "Did you build this during the event?"

Give the dates. Don't argue the rule.

- Our notes from the event page (`docs/ideation/01-competition-analysis.md`) say the window started 30 Oct at 7:30 PM, with builds of 48 hours.
- The earliest commit is 30 Oct, 22:45 IST: a playbook for a different idea, ScholarFlow, which we dropped.
- Idea research and the plan were committed 31 Oct, 16:57 to 17:27 IST, and merged at 17:37 IST.
- Application code enters at commit `2143406`, 31 Oct, 21:04 IST. It's one large commit, so history doesn't show how that code progressed before then.
- From 22:18 IST on 31 Oct, an automated job pushed snapshots about every 10 minutes, with generated messages like "Update backend". Those messages don't describe the work. Read the diffs.
- Libraries are open source (`backend/pyproject.toml`, `web/package.json`). Satellite and weather data are public. Nothing in the repo predates 30 Oct.

Limits: commit timestamps are set by the committing machine, so they aren't independent proof. Our copy of the rules is second-hand. `HACKATHON_PLAYBOOK.md` calls them "reported" and says to confirm the complete rules. **One of us must read the organisers' actual rules before judging**, including what they say about tools, outside help, and changes after submission. Check this history against them. Don't state any policy from memory. If a judge asks how something was made or who wrote it, tell the truth.

### 8. "What's your false-positive rate?"

Locked, on rubric v3's plot rule: 2.0% strong and 2.5% moderate field conditions, on both of two no-event windows, 200 plots each. CIs are 0.8-5.0 and 1.1-5.7, and they're too narrow, because each window is one scene pair with correlated plots. "No event" means none reported in our sources. These count field conditions without corroboration, so they aren't the rate of `strong` verdicts. Far p-values lean slightly low in the October window. An earlier design-window measure gave 5.0% for the ring test at p ≤ 0.05 and 15.4% at p ≤ 0.10, so we removed the second tier. Don't confuse any of this with sensitivity, which is the weak spot.

### 9. "How do you know it's damage and not harvest?"

Sometimes we don't, and the app says so. A cut field leaves bare soil: if over 60% of the plot is bare, the whole field fell, and neighbours or history agree, we concede harvest and the verdict is `not_damage_likely_harvest`. Ripening is harder, because a ripening crop isn't bare. If the drop is real and past years don't settle it, the objection stays `unresolved`, the verdict carries a caveat, and a later pass is scheduled. On Bhiwani the band also fails to repeat in other years, which argues against ordinary ripening. It can't rule out a crop pattern specific to 2024. Be careful on Arnab: the card says harvest is rebutted, because no bare soil shows and the fall exceeds past years. But those past-year windows are longer, and the crop was days from harvest. We don't treat that as settled, and the selection note says normal ripening could look similar.

### 10. "You designed the test after seeing the data. Isn't that p-hacking?"

That's a fair worry, and it's disclosed. The far test and post-scene rule came after seeing Bhiwani. The 0.025 threshold came after seeing Sirsa 2025. So those are design data, and we don't present them as confirmation. We froze the rules and set separate runs: a holdout window, a no-event March window, and an independent event, Sirsa hail of 14 Mar 2025. They were reported as they came out, with no retuning. False alarms held at 2.0% and 2.5% on both no-event windows. The independent hail event gave 0 of 200, and with damage reported as "minor", that's consistent but isn't a pass. So sensitivity via the field-signal test is shown only on Bhiwani, the event the method was designed on. Treat the method as promising, not validated.

### 11. "Your run took minutes. How does this scale?"

Honestly, we haven't load-tested it. On one development machine on a slow shared link, a verdict on warm data takes 10 to 20 s, and a warm run with part of the data cached gave verdicts at about 70-75 s. Our 90 s cold target wasn't met from this machine (engine-results 8 has the tool times). Hosted timing isn't in this document until it's measured. Reads are windowed, and each byte is downloaded once per run. Runs, rate limits and the scheduler live in one process, so it's one instance today. Scaling further would mean separate workers and a shared cache, which we haven't built.

### 12. "Weather shows no hail codes. Why say corroborated?"

Corroborated means weather, or an official alert whose hazard matches the report. Cited news is shown as related reports and never moves a level. On the sealed Bhiwani records, it's weather alone: 18.4 mm in a day from a gridded model, with zero hail-code hours. So that's support that a storm system passed, not evidence of hail on this field. It's weak corroboration, and we say "model-indicated". No signal never counts against a farmer, since a 9-25 km grid can miss a hail cell. But it also can't lift the verdict: a report with neither weather nor a matching alert stays `weak`, and the text says why.

### 13. "Isn't this just a pipeline with a chat front end?"

Look at the trace. Decisions change the path: a bad scene gets rejected, radar takes over, a conceded objection triggers a new search, a weather peak on another date triggers a re-run, and late evidence can revise the verdict. The surveyor's objections can be conceded. Branching is an explicit state graph, and it works with no LLM, because the reasoning that matters is code. There's an LLM planner option, and it's off by default. What's fair to say: the agent's value here is in checking itself, not in a model's prose.

### 14. "What does Gemini actually do? Have you tested it?"

Parsing voice and text, policy answers under validation, speech, and finding related reports. **It doesn't decide the verdict, and it doesn't write verdict or testimony text.** Those are deterministic. Polish and the planner exist behind `LLM_POLISH` and `LLM_PLANNER`, off by default. **The running app has been on `gemini: false`, and tests use stubs. So these paths are unverified until a key is tested** (`deploy/README.md` has the self-test). Without a key, the verdict, cross-examination and templated Hindi, Telugu and English still run, and the banner says language help is off. Related reports never change a level. Any LLM text must pass a validator: every digit has to exist in the evidence.

### 15. "Isn't this what YES-TECH already does?"

No, it's a different job. YES-TECH estimates yield at Gram Panchayat level (para 2.17), for States and insurers under area-yield cover. We don't estimate yield. We make a record of one field's change between two dates, tested against look-alike fields, for the farmer. Don't claim a better sensor. Sentinel-2's 10 m pixels are in the same range YES-TECH inputs are described with. Our difference is the unit of analysis and the placebo test. Also keep the two systems apart: a localized hail claim goes to a joint survey or the 10-parcel sample, not YES-TECH.

### 16. "Are you saying the 10-parcel survey is unfair?"

No. Random sampling is unbiased on average. We show how far one draw's average can move in a patchy event, on a satellite index, from cropland, not the real list. We have no data on any real draw and can't say anyone lost money from one. The useful finding is modest: the average depends heavily on who is on the list, and nobody outside the insurer can see that list. "We did not find a published simulation of it" is as far as we go. We searched the web, not Scholar or Scopus.

### 17. "It's a huge cyclone. Why can't you show Arnab damage?"

Because we haven't established it, and the sealed record says `weak`. It's the strongest of 51 usable plots near Anaparthi: -0.3419 in 5 days, 3 days after landfall. Far p is 0.0292 and ring p 0.0945, so it's near the threshold. The crop was days from harvest, and this same plot fell -0.20 and -0.24 in other years, over longer windows. At tile scale, about -0.1 is the normal drop for these weeks.

Three more things. On a different Sentinel-2 tile of the same pass, this plot read -0.3595 with far p 0.0049 and ring p 0.005, which shows how much tile choice can matter. There's no radar pair yet, and the next usable one is about 4 Nov. For an event this wide, the far test loses power too.

The honest line: no signal established, and a later pass will help. This doesn't contradict reports of flattened paddy, because lodged paddy can stay green. Standing paddy under a cyclone would be on area-yield cover, so para 21.5.8 wouldn't govern it, and the app labels the Draw as what the rule would do if it applied.

### 18. "What does your verify page actually prove? How long does it take?"

It proves that the sealed satellite numbers follow from those public scenes and this code. Independent runs from a clean database produced identical hashes. The page says the scope plainly: "Satellite numbers are recomputed; the verdict and weather are checked for tampering only." It doesn't prove the cause, or that the verdict is right. Explanation text, claim route and related reports aren't sealed.

Timing on our link: the field's own 20 numbers took 31 to 41 s. Full checks took 395 s and 338 s (104 numbers), and 281 s (85 numbers, no radar). A repeat scan shows the last full check, labelled with its time, and you can ask for a re-run. Don't say "every number recomputes in seconds".

### 19. "Is any of this fake or cached?"

No dummy data in the running app: no fixtures, no seeded cases. Test fixtures live only in `backend/tests/`. Cached real API responses and raster reads keep their provenance, and verification bypasses our caches. In a demo, we open cases that were run earlier, and we say so. The "Sources" exhibit lists scene ids and retrieval times.

### 20. "On basic cover a claim comes from unit yield. So what does a farmer gain?"

On that route, this evidence doesn't decide the outcome, and the app says so. What the farmer gets is:
- The right route, instead of a blanket 72-hour warning. The official wording: "Enrolled farmer has no need to file the claims" on area-based losses (Lok Sabha Q25, 21 Jul 2026).
- A dated record of the field they can show at a grievance or to an officer.

On the localized and post-harvest routes, it's a supporting record to keep with the intimation. "Farmers can contest, but they have no evidence of their own to contest with." It can also honestly say "your field doesn't show this", and that's useful too. We have no measured farmer outcomes, and the repo records no field trial.

### 21. "What did Punjab show?"

A pre-registered test, written before any Punjab data was opened, and run once. Floods of Aug 2025, 60 plots at three named sites, against the same plots in 2024. The result is **partial**, and we report it as partial.

- **New water passes:** at least 0.2 of the plot on 28.3% of plots in 2025, against 0.0% in 2024.
- **SAR placebo fails:** p ≤ 0.05 on 1.7% against 8.3%. The ring flooded too, and radar has no far test. That explains the failure, but doesn't change the score.

Limits: the pair rule picked different timing in the two years, so the 2024 control doesn't sample early September and its 0.0% may be cleaner than a same-dates comparison. One site of three, Pakhoke Mehmaran, shows almost nothing (5%). And 2025 pairs start up to 5 days before the breach, so earlier rain may be included. It's a positive radar case for new water. It isn't evidence for the optical field-signal test: optical showed no discrimination there.

### 22. "What did the independent review find?"

The contract's Addendum 8 records the decisions that came out of it. Stick to these, and say who did the review truthfully if asked:

- The verdict had to be deterministic. Corroboration is now the weather model or a matching official alert, and news never changes a level.
- LLM text no longer carries the verdict. Polish is off by default.
- "Verified" had to mean what it says. Satellite numbers are recomputed. Verdict and weather are only checked for tampering, through a digest in the seal.
- Map shortcuts no longer preset dates. They show a reported date with its source.

The repo records these decisions, not a separate report of findings, so don't describe more than this.

## 6. Words to use and words to avoid

| Say | Don't say |
|---|---|
| Consistent with hail | Hail caused this |
| Strongest of 200 scanned; median of the original 40; strongest of 51 usable | Our best case, or the plot, with no label |
| Near the threshold (p from 0.01 to 0.075) | Passed, or failed, with no caveat |
| Satellite numbers recomputed; verdict and weather checked for tampering | The whole result is verified |
| The effect does not look limited to your field | All the neighbours were hit |
| The rule asks for intimation within 72 hours | Missing it ends your claim |
| Report it now anyway and keep the reference number | Being overdue doesn't matter |
| We did not find | Nobody has, or we're the earliest |
| The Ten-Field Draw | Anything suggesting chance is unfair |
| Applications (for PMFBY counts) | Farmers, when the source says applications |
| Gram Panchayat level (YES-TECH) | Insurance-unit level |
| 24 Oct 2026 (Sirsa and Fatehabad) | 25 Oct, which is only a dateline |
| Farmers say (Haryana's ₹350 crore) | Satellites cut ₹350 crore, as a plain fact |
| Your bank or 14447 can confirm | Naming an AP insurer |

The `do_not_say` entries in `backend/data/policy/key_rules.json` bind everything we say.
