# Deck content

**For:** the people finishing the deck. This matches `docs/submission/FasalSaakshi-deck.pptx` and its PDF: six slides (the limit is 5-7), one idea per slide. Numbers match the final sealed records. To add a number, take it from `docs/submission/facts.md` or `docs/validation/engine-results.md`, with its wording, or leave it out.

**Screenshots** are in `docs/submission/screens/`: real captures of the final records. Keep the selection note in the crop wherever it appears.

**One gap in the deck:** slide 3 describes the Gemini features with no note that they haven't been run against the real API, and slide 6 only lists verifying them as a next step. See slide 3 below.

## Slide 1. Title and team

**Title:** FasalSaakshi (फसल साक्षी). A witness for the farmer's field.

**Line:** A field's own satellite evidence, which anyone can recompute.

**Team:** [team to add team name, member names and roles]

**Footer:** Forge '26 Gen AI Buildathon · Theme 2, Problem 2

**Image:** the footprint map, `strongest-footprint-map-en.png`. Caption: "Hail of 2-3 March 2024, Bhiwani. A band consistent with a hail swath, not proof of cause. Marked plot: strongest of 200 scanned."

**Speaker note:** "Saakshi" means witness. A witness must survive cross-examination, and anyone must be able to check what it said.

## Slide 2. The problem

**Headline:** Farmers can contest, but they have no evidence of their own to contest with

| Number | Wording | Source |
|---|---|---|
| 92.46 crore | "more than 92.46 crore farmer applications have been insured" since Kharif 2016. Applications are not farmers | PIB backgrounder, 29 Aug 2026 |
| ₹4,107.47 crore | Claims pending, as on 31.12.2025. Official causes are mainly State share, bank data and yield disputes | Lok Sabha Q662, 3 Feb 2026; Q3825, 11 Aug 2026 |
| About ₹350 crore | In 2025, Bhiwani and Charkhi Dadri farmers sat on dharna from 16 July. They say satellite-based yield cut about ₹350 crore from CCE-based claims | The Tribune, Aug 2025 |

**Two systems, kept apart:**
- **YES-TECH, basic cover.** Yield estimated "at Gram Panchayat (GP) level", rolled out from Kharif 2023. This is area yield, not a survey of one claim (para 2.17).
- **Localized claims, individual farm.** A joint survey, or above 25% of insured area under intimation, a sample of 10 randomly selected parcels. Satellite indices enter only in a dispute (paras 21.5.8, 21.5.9.4).

**Speaker note:** Don't say the ₹4,107 crore comes from satellites, because the source doesn't say that. Before printing the Q662 link, check `sansad.in` (we read it through a mirror).

## Slide 3. The witness idea

**Headline:** A witness who can say "your field doesn't show this"

**Boxes:**
1. **The field testifies.** Its own record, with its caveats, in Hindi, Telugu or English.
2. **The surveyor cross-examines.** Nine objections, tested on real values. It can concede: typical plot.
3. **Anyone can recompute it.** Public recompute of satellite numbers. Verdict, weather: tamper check. Separate clean-database runs gave identical hashes on all three records.

**Gen AI line, on the slide:** "Gemini understands, explains and questions. Code measures and decides. A model can't talk the verdict up."

**Bullets, on the slide:**
- Understands Hindi, Telugu and Hinglish reports
- "Ask the witness" answers from the farmer's own record, with a number check
- Flags contradictions as a question
- Advisory second opinion on images
- Reads the testimony aloud

**Add to the slide:** "Not yet run against the real API: `TODO(gemini)`". Remove it only if the selftest passes. Related reports are also a Gemini feature, and aren't listed on the slide.

**Images:** `strongest-testimony-hi.png`, captioned "The testimony, in Hindi. Strongest of 200 scanned". The conceded card from `typical-cross-exam-en.png`, captioned as the typical plot, the median of the original 40. `strongest-verify-stored-en.png`, captioned "A stored full check. Strongest of 200 scanned".

**Sources:** live records `1ce7e64b754248abb18f0d29ac6203eb` and `c157d2d75ce94501ad08930624a10e76`; verify hash `6092fe1c9ef12f2933ac9aa7fbc8b0737e9a306fdd6a071b159e64ea4dd7c58b`; README final sealed records; contract Addenda 8 and 9.

**Speaker note:** We did not find a farmer-side tool that gives a field its own placebo-tested satellite evidence and lets anyone recompute it. Name the close neighbours if asked: Proof of Loss (farmer-side, photos), CropSnap (same satellites, aimed at insurers), Farmonaut (field monitoring, vendor claims, not tested by us). Sources: `facts.md` section 7.

## Slide 4. Footprint and method

**Headline:** Two questions, and what a wider average keeps

**Left:** the footprint map. Caption: "Hail of 2-3 March 2024, Bhiwani. Consistent with a hail swath, not proof of cause. Plot: strongest of 200 scanned."

**Right, top:**

| Question | Answer (strongest of 200 scanned) |
|---|---|
| Unlike comparable fields outside the storm? | **Yes.** 0 of 200 changed as much. p = 0.005 |
| Unlike its own neighbours? | **No, but near the line.** 11 of 200 changed as much. p = 0.0597 |

**Right, middle. The Vanishing: same change, 3 km cells. Our illustration, not YES-TECH.**

| | Strongest of 200 scanned | Typical, median of original 40 |
|---|---|---|
| Field | -0.369 | -0.126 |
| 3 km | -0.098 | -0.081 |
| Remains | 27% | 64% |
| Verdict | `strong` | `weak` |

Images: `strongest-vanishing-end-en.png`, `typical-vanishing-end-en.png`.

**Under the left map:** "Corroboration on the strongest plot: modelled rain of 18.4 mm in a day, with zero hail-code hours (live record)."

**Right, bottom:** Ten-Field Draw, bounds not an estimate: -0.07 for all cropland, -0.245 for only fields that visibly dropped. The average depends heavily on who is on the list, and nobody outside the insurer can see that list.

**Sources:** sealed records `6092fe1c` (strongest of 200 scanned, 1.27 ha) and `56aadcb6` (typical, 1.09 ha), live app. Draw medians across 40 in-band plots: `engine-results.md` section 3e.

**Speaker note:** Those Draw figures are medians across 40 plots. On the strongest of 200 scanned, the live record reads -0.080 and -0.239. The rule is only illustrated here. It isn't called unfair. No rupee figures. The typical plot is near the threshold, and with the intended filter the median plot was 28.710543, 76.228524 at -0.1283.

## Slide 5. Validation and limits

**Headline:** What we measured, and what we didn't

| Item | Result | Reading |
|---|---|---|
| False alarms, two locked no-event windows | **2.0-2.5%** | 2.0% strong, 2.5% moderate field conditions, 200 plots per window, rubric frozen beforehand. Each window is one scene pair, so the CIs are too narrow |
| Independent event: Sirsa hail, 14 Mar 2025 | **0 of 200** | Not a pass. The Tribune called the damage "minor", and we cannot tell little damage from a miss |
| Punjab floods 2025, pre-registered | **Partial** | New water on 28.3% of plots against 0.0% in the control: passes. Radar placebo 1.7% against 8.3%: fails |
| Detection through the field test | **Bhiwani only** | Shown only on Bhiwani, the event the far test and post-scene rule were designed on. Radar there does not confirm it: the orbits disagree |
| Verdicts near the threshold | **Fragile** | Near p 0.025 the level flipped on up to a third of 30 seeds, on plots picked for being near that line. A slightly different drawing can change the result. Clear cases held |
| Ground truth | **None** | No plot-level ground truth for any event. This work shows consistency, not accuracy |

**Small print:** CIs 0.8-5.0% strong, 1.1-5.7% moderate. Field conditions: the plot rule without corroboration. Sirsa report: The Tribune, via `events.md` C2.

**Sources:** `engine-results.md` sections 3c, 7, 7a, 7b, 7c; contract Addendum 7. Thirty seeds do not bound another seed: the sealed strongest plot's ring p 0.0597 sits just above that table's range, with no change of level (7c).

**Speaker note:** Punjab's two years used different pass timing, and one site of three shows almost nothing. Cyclone Arnab: no signal established. All three records' satellite numbers were recomputed (104, 104 and 85), and independent runs from a clean database gave identical hashes.

## Slide 6. Impact and roadmap

**Headline:** Who this could help, and what comes next

**Who:**
- **241.38 lakh** farmers insured in Kharif 2026, as of 27 Aug 2026 (PIB).
- Of 2024-25 farmer applications, 17.6% are marginal, 6.5% tenant and 48% loanee (PIB, 25 Jul 2025).
- 74% of the ₹4,107.47 crore pending is in Andhra Pradesh, where Arnab just hit (Lok Sabha Q662, our arithmetic: ₹3,041.66 crore). That is not a claim that satellites caused it, and this does not fix a State's unpaid share.
- No measured farmer outcomes yet. No insurer or State has reviewed this.

**Next, in order:**
1. Re-check Arnab at the next clear passes: Sentinel-2 about 2 Nov, radar about 4 Nov. No signal is established yet.
2. Test sensitivity on an independent event with real damage.
3. Test against real records: crop-cutting or joint survey results for specific plots.
4. Verify the Gemini paths, and get Telugu reviewed by a native speaker.
5. Pilot with an FPO or KVK. Ask an insurer and a State team what they'd need.
6. Verify State notifications, so routes stop saying "confirm with 14447".

**QR and live URL:** `TODO(deploy)`

**Close:** Anyone can check what it said.

## Before the deck goes out

- [ ] Replace the placeholders on slide 1, and the `TODO(deploy)` QR and URL on slide 6.
- [ ] Add the "not yet run" note to slide 3, and settle `TODO(gemini)`.
- [ ] One person spends 15 minutes on Google Scholar with: "localized calamity" PMFBY sample survey; "wide-spread localized"; PMFBY "10" parcels loss assessment. `facts.md` asks for this before any "we did not find" line goes in a final deck.
- [ ] "Strongest of 200 scanned", "median of the original 40" and "strongest of 51 usable" appear beside those plots wherever they're shown.
- [ ] Every hail mention says "consistent with".
- [ ] No rupee payout figures. No 70/30 as a selling point. No named AP insurer. No "CSC".
- [ ] Check each number on the slides against what the live app shows for the same case.
