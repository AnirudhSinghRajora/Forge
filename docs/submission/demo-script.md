# Demo script

**For:** whoever records the video and presents live. Length: under 3 minutes (the requirement is 2-3).

**The video must be a real screen recording of the live app.** No mock-ups or staged screens. Don't edit a number. If you cut waiting time, say so on the recording.

Set the app to English (`En`, top right) for the recording, and play the testimony in Hindi.

## Before you record

Do these in order. Hosted timing: `TODO(deploy)`. Measure it here, and use your own number in the QR beat.

1. **Deploy, following `deploy/README.md`.** A new deployment starts empty.
2. **Check `/api/health`.** If `gemini` is false, the banner says language help is off. Leave it, and don't claim Gemini features.
3. **Warm the three cases:** `cd backend && uv run python scripts/warm_demo.py --base-url https://your-url --verify`. It creates each case through the public API with its exact polygon, and runs each full check once. Note the case ids it prints.
4. **Compare each result with the table below.** With the same polygon and date, you should get these numbers and hashes.

| Case | Date to type | Hash starts | Verdict | Change | Far p | Ring p |
|---|---|---|---|---|---|---|
| Strongest of 200 scanned, Bhiwani, 28.700911 N, 76.215719 E | 2024-03-03 | `6092fe1c9ef1` | `strong` | -0.3689 | 0.005 | 0.0597 |
| Typical, median of the original 40, Bhiwani, 28.715212 N, 76.231138 E | 2024-03-03 | `56aadcb68360` | `weak`, near the threshold | -0.1259 | 0.039 | 0.1859 |
| Arnab, strongest of 51 usable, near Anaparthi, 16.906738 N, 81.975164 E | 2026-10-28 | `17a3b0d203d5` | `weak`, near the threshold | -0.3419 | 0.0292 | 0.0945 |

**If you make a case by hand in the app:** a map shortcut moves the map and shows a reported date with its source. It presets nothing, so you type the date from the table. Any other date re-samples and can change the numbers, and so can a field drawn even slightly differently. On a re-sampled result, say what's on your screen. Don't answer "insured" for these cases.

5. **Test the PDF.** Download it for the strongest case, and test the QR with a phone on mobile data. If the QR doesn't open the deployed URL, check `PUBLIC_WEB_URL`.
6. **Know the limits.** New investigations are limited to 12 per IP per hour, and new verify downloads to 3. If judges share a network, raise `RATE_INVESTIGATIONS_PER_HOUR` and `RATE_VERIFY_PER_HOUR` first (`deploy/README.md`).
7. **Practise the wait-free path:** have all tabs open, in story order.

## The script

Word counts fit about 2.5 words a second. Numbers in [brackets] come from the final records: if your screen differs, say your screen. Cut words, not labels.

### 0:00-0:22. The Field Testifies

**Screen:** strongest case, verdict page, top, with the selection note in shot. Press play on the testimony. Let about 4 seconds of Hindi play, then lower it and speak.

**Say:**
> This is a wheat field in Bhiwani, testifying about itself, from public satellite data. Three things up front. It's the strongest of 200 plots we scanned, not a typical field. It's a signal case, not an insurance claim. And we ran it earlier, because a fresh run takes minutes.

### 0:22-0:50. The footprint and two questions

**Screen:** scroll to Exhibit 1, The storm's footprint. Show the map, with the SW-NE band. Point to the stamp "Consistent with the event, not proof of cause". Then the two answers beside it.

**Say:**
> One change map, after the hail of 2-3 March 2024. The red band is consistent with a hail swath, and it doesn't repeat in other years. Nobody has checked these fields. Two questions. Did this field fall more than comparable fields outside the storm? [Yes: 0 of 200.] More than its neighbours? [No, but near the line: 11 of 200.] So the effect doesn't look limited to this field.

### 0:50-1:15. The Vanishing, both plots

**Screen:** Exhibit 2 on the strongest case. Drag the slider from 10 m to 3 km. Keep the selection note in shot. Switch tab to the typical case, same exhibit, and drag again. Its note reads "the median of the original 40 random plots".

**Say:**
> Same data, bigger cells. Our illustration, not YES-TECH output. The strongest of 200 goes from [-0.37] to [-0.10] at 3 kilometres. Now a plot chosen by rule, the median of our original 40: [-0.13] to [-0.08]. When a field falls harder than its surroundings, area averages can't show it. When a wider stretch falls together, they mostly can.

### 1:15-1:40. The Ten-Field Draw

**Screen:** Exhibit 3 on the strongest case, note in shot. Let real draws land on the map. Then the two scenario cards. Hold on the limits panel.

**Say:**
> Para 21.5.8: above 25%, a survey samples 10 parcels from the intimation list. This is what it would do if it applied here. On the strongest of 200, about [-0.08] from all cropland, [-0.24] from fields that visibly dropped. Those are bounds. The average depends heavily on who is on the list, and nobody outside the insurer can see that list. That doesn't make the rule unfair.

### 1:40-2:00. Cross-examination

**Screen:** cross-examination record on the typical case. Open harvest, then the conceded regional-trend card. Then the verdict's near-threshold caveat.

**Say:**
> A hostile surveyor raises nine objections. Harvest? Wrong plot? Cloud? Each is answered by a test on real values, and it can concede. [The median plot concedes: weak, and near the threshold, so a slightly different drawing could change it.] On the strongest plot, radar doesn't support the optical result, and the verdict says so.

### 2:00-2:27. Arnab: not established yet

**Screen:** Arnab case verdict, top, with the selection note in shot.

**Say:**
> Cyclone Arnab. About 3.51 lakh hectares of crops damaged, per the Andhra Pradesh Agriculture Minister's preliminary assessment of 29 October. Here's the strongest of 51 plots near Anaparthi. [Minus 0.34 in 5 days], but the crop was days from harvest, and this plot also fell [0.20 and 0.24] in other years, over longer windows. Verdict: [weak]. No signal established. A later pass will help.

If asked: this was 3 days after landfall, and lodged paddy can stay green, so this doesn't contradict reports of flattened paddy.

### 2:27-3:00. The QR moment

**Screen:** PDF with the QR code. Scan on a phone, or open the link. The stored check appears: the hash, the line "Satellite numbers are recomputed; the verdict and weather are checked for tampering only", the time of the check, and VERIFIED.

**Say:**
> Every result is sealed with a hash. Scan it, no account needed. All [104] satellite numbers, re-downloaded from the public archive, matched. That took about [6] minutes on our link. The verdict and weather are only checked for tampering. On two no-event windows the field rule fired on 2 to 2.5% of plots, and on Punjab's floods our pre-registered test came back partial. There's no plot-level ground truth, and an insurer may not accept this. But anyone can check what it said.

Use your own hosted full-check time if you've measured one. "Check again from the archive" starts a real download and counts against the verify limit. Never say that every number recomputes in seconds.

## Claims check, before you publish

| Must hear or see | Must not say |
|---|---|
| "Strongest of 200" and "strongest of 51" each time those plots appear | Any payout amount, or that someone gets paid |
| "Median of the original 40" for the typical plot | "Random typical field", with no rule stated |
| "Consistent with" for hail | Hail caused it |
| "We ran it earlier" | That it's running live, if it isn't |
| Radar disagreement | That radar confirms it |
| "Signal case, not an insurance claim" for Bhiwani | That Bhiwani was a PMFBY claim |
| Near the threshold, where the screen says so | A clean pass or fail for those results |
| Verdict and weather only checked for tampering | That the whole result is verified |
| Punjab: "partial" | That the flood test passed |
| "No plot-level ground truth" | "Accuracy", "validated" |
| "We did not find" | Claims of being the only one or the earliest |

If asked about the independent hail event: 0 of 200 on Sirsa, 14 Mar 2025. Damage was reported as "minor", so that's consistent but isn't a pass. Sensitivity via the field-signal test is shown only on Bhiwani, the design event.

## Live presentation: risk plan

### Say this at the start

> We warmed these cases in advance, and we'll tell you when something is live. A fresh run depends on the public satellite archive and can take minutes.

### Bhiwani route panel

The route panel reads "The route is not determined yet", because we never enter insurance for this case. Say:

> This event is a signal case, not a PMFBY claim case. A Congress leader said no insurer covered Hisar that season. So we left insurance unanswered, and the app won't guess.

### If the archive is slow

The app is built for this. A slow read gives a "still computing" state, not a failure.

| You see | Do | Say |
|---|---|---|
| Verdict "still computing", or a provisional result | Keep it on screen for a moment, then open the warmed case | "The images are still downloading. This is the public archive's speed. Here's one we ran earlier." |
| Trace says it's switching to radar, on a cold run | Don't read this as a finding about bad images | "It hasn't got the optical images in time, and that work continues behind the result." |
| An exhibit "failed" with a retry button | Press retry once, then move on | "That exhibit didn't finish. It doesn't change the verdict." |
| A message that a limit was reached | Open a warmed case. Raise the limit afterwards if needed | "Each new run downloads satellite data, so we limit them per network." |
| Verify shows "could not be reached" | Show the stored check | "The archive is unavailable. That says nothing about the evidence." |
| Verify shows "partial" or "field verified" | Show the honest count | "These 20 match. The others weren't checked this time." |
| Verify shows a mismatch | Don't explain it away. Open the row | "That's what a failed check looks like. Here's the number that differs." Then tell the lead |
| The app won't load | Use the video, and say it's a recording | "This is our recording of the app. The live link is on the slide." |

Never pass off the video as live.

### Before a judge drops a random pin

Say this **before** the pin goes down:

> Please do. Most pins will correctly show little: there has to be a real event on that date, and a field that changed more than comparable fields. "Your field doesn't show this" is a correct answer. If neither the weather model nor a matching official alert backs the report, it stays weak. A new pin also has to read from the archive, so its verdict can take minutes and the exhibits longer. It only covers India. And it needs a date, so please tell me when something happened.

Then:
- Type the date the judge gives you. The app needs one, and shortcuts don't fill it in.
- Keep talking through the trace while it runs. Scene rejections and radar switches are worth pointing out.
- If it's a slow read, offer to leave it running and come back. Runs continue on the server, and the page can be reopened.
- Whatever comes back, read it out as is. A weak or insufficient result is a good moment: read the caveat aloud.

### If you're asked for something we don't have

Go to `docs/TEAM_WALKTHROUGH.md`, section 5. "We don't know" is an acceptable answer. Inventing one isn't.
