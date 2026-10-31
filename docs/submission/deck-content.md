# Deck content

**For:** the people building the deck. Six slides (the limit is 5-7). One idea per slide. Every number below has a source. If you want to add a number, take it from `docs/submission/facts.md` or `docs/validation/engine-results.md`, with its wording, or leave it out.

**Screenshots** are in `docs/submission/screens/`. They are real English captures of the final sealed records, with Hindi versions of some. Check any number you quote against the image. Keep the selection note in the crop wherever it appears.

## Slide 1. Title and team

**Title:** FasalSaakshi (फसल साक्षी)

**Line:** A field's own satellite evidence, which anyone can recompute.

**Team:** [team to add names and roles]

**Footer:** Forge '26 Gen AI Buildathon · Theme 2, Problem 2

**Image:** none, or `strongest-testimony-hi.png`, with the caption "Strongest of 200 scanned".

**Speaker note:** "Saakshi" means witness. A witness must survive cross-examination, and anyone must be able to check what it said.

## Slide 2. The problem

**Headline:** Farmers can contest, but they have no evidence of their own to contest with.

**Three facts:**

| Fact | Source |
|---|---|
| "more than 92.46 crore farmer applications have been insured" since Kharif 2016 | PIB backgrounder, 29 Aug 2026 |
| ₹4,107.47 crore of claims pending, as on 31.12.2025 | Lok Sabha Q662, 3 Feb 2026 |
| "In 2025, Bhiwani and Charkhi Dadri farmers sat on dharna from 16 July. They say satellite-based yield cut about ₹350 crore from CCE-based claims" | The Tribune, Aug 2025 |

**Small print on the slide:** Applications are not farmers. Pending claims have official causes that are mainly State share, bank data and yield disputes.

**Image:** none. Keep the text large.

**Speaker note:** Tell the two systems apart. YES-TECH sets yield at Gram Panchayat level under basic cover. A localized claim goes to a joint survey or a 10-parcel sample. Don't say the ₹4,107 crore comes from satellites, because the source doesn't say that. Before printing the Q662 link, check `sansad.in` (we read it through a mirror).

## Slide 3. The witness idea

**Headline:** A witness who can say "your field doesn't show this".

**Three boxes:**

1. **It testifies.** The field's own record, with caveats, in Hindi, Telugu or English.
2. **It's cross-examined.** Nine objections from a hostile surveyor, each answered by a test on real values. It can concede.
3. **Anyone can check it.** A QR code opens a public page that re-downloads the same scenes and recomputes the satellite numbers. The verdict and weather are checked for tampering only.

**One line under them:** We did not find a farmer-side tool that gives a field its own placebo-tested satellite evidence and lets anyone recompute it.

**Image:** the conceded card, cropped from `typical-cross-exam-en.png`, with the caption "Median of the original 40". Add `strongest-verify-stored-en.png` if there's room.

**Speaker note:** Name the close neighbours if asked: Proof of Loss (farmer-side, photos), CropSnap (same satellites, aimed at insurers), Farmonaut (field monitoring, vendor claims, not tested by us). Sources: `facts.md` section 7.

## Slide 4. Footprint and method

**Headline:** Two questions: unlike fields outside the storm? Unlike its neighbours?

**Left:** `strongest-footprint-map-en.png`. Caption: "Hail of 2-3 March 2024, Bhiwani. Change in greenness, 28 Feb to 9 Mar. Consistent with a hail swath, not proof of cause. Plot marked: strongest of 200 scanned."

**Right:** `strongest-two-answers-en.png`, or this table:

| Question | Answer on this plot (strongest of 200 scanned) |
|---|---|
| Far test, 5-12 km: did it fall more than comparable fields outside the storm? | Yes: 0 of 200, p = 0.005 |
| Ring test, nearby: did it fall more than its neighbours? | No, but near the line: 11 of 200, p = 0.0597, threshold 0.025 |

**Below:** "The band does not repeat in 2022, 2023 or 2025." Rule: change at threshold and either test at p ≤ 0.025, then corroboration from the weather model or a matching official alert, then no conceded objection. A deciding p from 0.01 to 0.075 is marked as near the threshold.

**Optional small panel, the Vanishing (strongest beside typical):**

| Cell | Strongest of 200 scanned | Typical, median of the original 40 |
|---|---|---|
| Plot | -0.37 | -0.13 |
| 3 km | -0.10 | -0.08 |

Caption: "Our illustration from public satellite data, not output of YES-TECH." Images: `strongest-vanishing-end-en.png`, `typical-vanishing-end-en.png`.

**Sources:** live records `1ce7e64b754248abb18f0d29ac6203eb` and `c157d2d75ce94501ad08930624a10e76`; engine-results sections 3c and 3e.

**Speaker note:** If you add the Draw, use only: "the average depends heavily on who is on the list, and nobody outside the insurer can see that list." On the strongest of 200 scanned, all cropland averages -0.080 and fields that visibly dropped -0.239. Across 40 plots, the medians are -0.069 and -0.245. Those are bounds, not an estimate. One draw moves about ±0.035. It doesn't say the rule is unfair. No rupee figures.

## Slide 5. Validation and limits

**Headline:** What held up, and what didn't.

**Two columns:**

| Held up | Did not, or not established |
|---|---|
| **False alarms: 2.0% strong and 2.5% moderate field conditions**, on two no-event windows, 200 plots each, rules frozen in advance | Each window is one scene pair with correlated plots, so the CIs (0.8-5.0, 1.1-5.7) are too narrow |
| Band contrast of -0.146 in 2024 (mask set on this pair, so inflated), against +0.007 to +0.052 in other years | **Radar does not confirm it.** Orbits disagree: +0.50 dB and -0.47 dB |
| Punjab floods, pre-registered: new water on 28.3% of plots against 0.0% in the control year | **Punjab is partial.** Radar placebo fails: 1.7% against 8.3%. Pass timing differs between the years, and one site of three shows almost nothing |
| Clear cases are stable across 30 seeds. Far p on the strongest of 200 scanned is 0.005 on all 30 | Near 0.025, the level flips on up to a third of seeds, so those results carry a caveat |
| Corrupt scene with about 0% metadata cloud rejected | **Independent hail event, Sirsa: 0 of 200.** Damage was reported as "minor", so this isn't a pass |
| 104 of 104 satellite numbers recomputed within 0.001. Clean-database runs gave identical hashes | Verdict and weather are checked for tampering only |
| Typical plot, median of the original 40, shown beside the strongest of 200 | **Sensitivity via the field-signal test is shown only on Bhiwani, the design event** |
| | **No plot-level ground truth.** This shows consistency, not accuracy |
| | **Cyclone Arnab: no signal established.** A later pass will help |

**Footer:** Far test and post-scene rule were designed after seeing Bhiwani. Bhiwani is a signal case, not a PMFBY claim case.

**Image:** `strongest-verify-stored-en.png`, small.

**Sources:** engine-results sections 1, 2, 3c, 4, 6, 7, 7a, 7b; live API for the verification counts.

## Slide 6. Impact and roadmap

**Headline:** Who this could help, and what comes next.

**Who:**
- PMFBY had "241.38 lakh farmers" insured in Kharif 2026, as of 27 Aug 2026 (PIB).
- Of 2024-25 applications, 17.6% marginal, 6.5% tenant, 48% loanee (PIB, 25 Jul 2025).
- The state with most pending claims is where Arnab just hit: 74% of ₹4,107.47 crore is in Andhra Pradesh (Lok Sabha Q662, our arithmetic). This isn't a claim that satellite assessment caused them, and FasalSaakshi doesn't fix a State's unpaid share.

**Say plainly:** no measured farmer outcomes yet. No insurer or State has reviewed this.

**Roadmap (in order):**
1. Re-check Arnab when the next clear passes arrive: Sentinel-2 about 2 Nov, radar about 4 Nov.
2. Test sensitivity on an independent event with real damage, because that is what this validation lacks.
3. Test against real records: crop-cutting or joint survey results for specific plots.
4. Verify the Gemini paths, and get Telugu reviewed by a native speaker.
5. Pilot with an FPO or KVK, and ask an insurer and a State team what they'd need from this record.
6. Verify State notifications, so routes stop saying "confirm with 14447".

**Image:** none, or the live URL as a QR code: `TODO(deploy)`.

**Close:** Anyone can check what it said.

## Before the deck goes out

- [ ] One person spends 15 minutes on Google Scholar with: "localized calamity" PMFBY sample survey; "wide-spread localized"; PMFBY "10" parcels loss assessment. `facts.md` asks for this before any "we did not find" line goes in a final deck.
- [ ] "Strongest of 200 scanned", "median of the original 40" and "strongest of 51 usable" appear beside those plots wherever they're shown.
- [ ] Every hail mention says "consistent with".
- [ ] No rupee payout figures. No 70/30 as a selling point. No named AP insurer. No "CSC".
- [ ] Check each number on the slides against what the live app shows for the same case.
