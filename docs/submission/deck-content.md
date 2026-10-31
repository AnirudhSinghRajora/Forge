# Deck content

**For:** the people building the deck. Six slides (the limit is 5-7). One idea per slide. Every number below has a source. If you want to add a number, take it from `docs/submission/facts.md` or `docs/validation/engine-results.md`, with its wording, or leave it out.

**Screenshots** are paths under the shots folder the lead shared (`r5/`, `r6/`). That folder isn't in the repo, so copy what you use. Most are in Hindi. For the deck, **recapture from the live app in English** where you can. The table says which ones must be recaptured.

| Screenshot | Use it? |
|---|---|
| `r6/two.png` | Yes. Corrected wording, and the p-values match the sealed case. Hindi only |
| `r6/stored-d.png` | Yes. Stored check, 104 of 104 |
| `r6/stage-d.png` | Yes. 20 of 20 field numbers at 00:51 |
| `r5/strong/foot-d.png` | **Map only: crop off the right column.** Its right column has wording we corrected and p-values from a different polygon |
| `r5/strong/van-end-d.png` | **Recapture.** Its 10 m row shows an old value (-0.437). The live record shows -0.3701 |
| `r5/typical/van-end-d.png` | **Recapture.** Its reading sentence has wording we corrected |
| `r5/strong/draw-end-d.png` | Usable. Its numbers differ a little from the sealed case, so use only what's on the image if you quote it. Keep the "strongest of 200" box in the crop |
| `r5/strong/top-d.png` | **Do not use.** Its testimony has wording we corrected. Recapture |

## Slide 1. Title and team

**Title:** FasalSaakshi (फसल साक्षी)

**Line:** A field's own satellite evidence, which anyone can recompute.

**Team:** [team to add names and roles]

**Footer:** Forge '26 Gen AI Buildathon · Theme 2, Problem 2

**Image:** none, or a recaptured testimony panel from the live app, with the caption "Strongest of 200 scanned".

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
3. **Anyone can check it.** A QR code opens a public page that re-downloads the same scenes and recomputes the numbers.

**One line under them:** We did not find a farmer-side tool that gives a field its own placebo-tested satellite evidence and lets anyone recompute it.

**Image:** a recaptured cross-examination card showing a concession, from the live app. Add `r6/stored-d.png` if there's room.

**Speaker note:** Name the close neighbours if asked: Proof of Loss (farmer-side, photos), CropSnap (same satellites, aimed at insurers), Farmonaut (field monitoring, vendor claims, not tested by us). Sources: `facts.md` section 7.

## Slide 4. Footprint and method

**Headline:** Two questions: unlike fields outside the storm? Unlike its neighbours?

**Left:** the footprint map, cropped from `r5/strong/foot-d.png`, or recaptured. Caption: "Hail of 2-3 March 2024, Bhiwani. Change in greenness, 28 Feb to 9 Mar. Consistent with a hail swath, not proof of cause. Plot marked: strongest of 200 scanned."

**Right:** the two answers (recapture in English, or `r6/two.png`):

| Question | Answer on this plot (2.12 ha square, strongest of 200 scanned) |
|---|---|
| Far test, 5-12 km: did it fall more than comparable fields outside the storm? | Yes: 1 of 200, p = 0.010 |
| Ring test, nearby: did it fall more than its neighbours? | No: 5 of 200, p = 0.0299, line 0.025 |

**Below:** "The band does not repeat in 2022, 2023 or 2025." Rule: change at threshold and either test at p ≤ 0.025, then corroboration, then no conceded objection.

**Optional small panel, the Vanishing (strongest beside typical):**

| Cell | Strongest of 200 scanned | Typical, chosen by rule |
|---|---|---|
| Plot | -0.37 | -0.13 |
| 3 km | -0.10 | -0.08 |

Caption: "Our illustration from public satellite data, not output of YES-TECH."

**Sources:** live API case `5f8ccaa5d7da407fb3dd2672434d6a3f`; engine-results sections 3c and 3e.

**Speaker note:** If you add the Draw, use only: "the average depends heavily on who is on the list, and nobody outside the insurer can see that list." Across 40 plots, all cropland averages -0.07 and fields that visibly dropped -0.245. Those are bounds, not an estimate. One draw moves about ±0.035. It doesn't say the rule is unfair. No rupee figures.

## Slide 5. Validation and limits

**Headline:** What held up, and what didn't.

**Two columns:**

| Held up | Did not, or not yet |
|---|---|
| Corrupt scene with about 0% metadata cloud rejected | **No plot-level ground truth.** This shows consistency, not accuracy |
| p ≤ 0.05 fired on 5.0% of 299 no-event squares (CI 3.1-8.1; one scene pair, so the CI is too narrow) | p ≤ 0.10 fired on 15.4%, so we removed it |
| Band contrast of -0.146 in 2024 (mask set on this pair, so inflated), against +0.007 to +0.052 in other years | **Radar does not confirm it.** Orbits disagree: +0.50 dB and -0.47 dB |
| 104 of 104 sealed numbers recomputed from the archive, within 0.001 | Full check took about 18 minutes on our link. Field numbers, under a minute |
| Typical plot chosen by rule, shown beside the strongest of 200 | Typical plot is weak |
| | **Cyclone Arnab: no signal established yet** |
| | **Rubric v3 holdout: pending.** Independent event: pending |

**Footer:** Far test and post-scene rule were designed after seeing Bhiwani. Bhiwani is a signal case, not a PMFBY claim case.

**Image:** `r6/stage-d.png` or `r6/stored-d.png`, small.

**Sources:** engine-results sections 1, 2, 3c, 3e, 4, 6, 7; live API for the verification counts.

**Update before submitting:** when section 7 of `engine-results.md` lands, replace the "pending" lines with what it shows, whatever it shows.

## Slide 6. Impact and roadmap

**Headline:** Who this could help, and what comes next.

**Who:**
- PMFBY had "241.38 lakh farmers" insured in Kharif 2026, as of 27 Aug 2026 (PIB).
- Of 2024-25 applications, 17.6% marginal, 6.5% tenant, 48% loanee (PIB, 25 Jul 2025).
- The state with most pending claims is where Arnab just hit: 74% of ₹4,107.47 crore is in Andhra Pradesh (Lok Sabha Q662, our arithmetic). This isn't a claim that satellite assessment caused them, and FasalSaakshi doesn't fix a State's unpaid share.

**Say plainly:** no measured farmer outcomes yet. No insurer or State has reviewed this.

**Roadmap (in order):**
1. Finish the locked holdout runs, and publish them whatever they show.
2. Re-check Arnab when the next usable radar arrives, about 4 Nov.
3. Test against real records: crop-cutting or joint survey results for specific plots.
4. Verify the Gemini paths, and get Telugu reviewed by a native speaker.
5. Pilot with an FPO or KVK, and ask an insurer and a State team what they'd need from this record.
6. Verify State notifications, so routes stop saying "confirm with 14447".

**Image:** none, or the live URL as a QR code `TODO(deploy)`.

**Close:** Anyone can check what it said.

## Before the deck goes out

- [ ] One person spends 15 minutes on Google Scholar with: "localized calamity" PMFBY sample survey; "wide-spread localized"; PMFBY "10" parcels loss assessment. `facts.md` asks for this before any "we did not find" line goes in a final deck.
- [ ] "Strongest of 200 scanned" appears beside that plot wherever it's shown.
- [ ] Every hail mention says "consistent with".
- [ ] No rupee payout figures. No 70/30 as a selling point. No named AP insurer. No "CSC".
- [ ] Check each number on the slides against what the live app shows for the same case.
