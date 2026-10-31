# Demo script

**For:** whoever records the video and presents live. Length: under 3 minutes (the requirement is 2-3).

**The video must be a real screen recording of the live app.** No mock-ups or staged screens. Don't edit a number. If you cut waiting time, say so on the recording.

Set the app to English (`En`, top right) for the recording, and play the testimony in Hindi.

## Before you record

Do these in order. Allow time: on our development link, one case took about 10 minutes to settle and one full verify took about 18. Hosted times are not measured yet, so check them.

1. **Open the deployed app.** Check `/api/health`. Note whether `gemini` is true. If false, the banner says language help is off. Leave it, and don't claim Gemini features.
2. **Check `PUBLIC_WEB_URL`** matches the deployed URL, or the QR code won't open it.
3. **Create the three cases on the deployed app, and let each finish.** A new deployment starts empty.

| Case | Pin | Report | Plot |
|---|---|---|---|
| Strongest of 200 scanned | 28.700911 N, 76.215719 E | Hail, wheat, standing, 3 Mar 2024 | About 140 m square (2.12 ha) centred on the pin, as in the case quoted below |
| Typical, chosen by rule | 28.715212 N, 76.231138 E | Same | About 105 m square centred on the pin, as in `engine-results.md` |
| Arnab | A cropland point, such as Anaparthi, 16.90319 N, 81.97497 E | Cyclone, paddy, standing, 28 Oct 2026 | About 2 ha |

For an exact square, send the polygon with `PUT /api/cases/{id}/plot` instead of drawing it. The map shortcuts for these two plots preselect 2 Mar, and a different date gives a different seed, so choose one date and keep it.

For the two Bhiwani cases, answer "insured: yes" and "standing" so a route shows. We say out loud that this is a signal case, not a claim.

4. **Read every result before recording.** Numbers below come from recorded runs. Yours may differ a little, because the seed comes from the polygon and date, and archives can add passes. **Say what's on your screen, and keep every label.** Check the two lines most likely to differ: the far and ring p-values.
5. **Confirm the wording on your screen.** It must not say the neighbours were all hit, in any language. It should read "the effect does not look limited to your field". The record on the development database, case `5f8ccaa5…`, was sealed before this wording was fixed, so don't record from it.
6. **Run one full verify on the strongest case** and let it finish, so a stored check exists to show.
7. **Download the Hindi PDF** for that case and test the QR with a phone on mobile data.
8. **Practise the wait-free path:** have all tabs open, in story order.

## The script

Word counts fit about 2.5 words a second. Numbers in [brackets] come from recorded runs: replace them with what your screen shows. Cut words, not labels.

### 0:00-0:25. The Field Testifies

**Screen:** strongest case, verdict page, top. Press play on the testimony. Let about 4 seconds of Hindi play, then lower it and speak.

**Say:**
> This is a wheat field in Bhiwani, testifying about itself, from public satellite data. Three things up front. It's the strongest of 200 plots we scanned, not a typical field. It's a signal case, not an insurance claim. And we ran it earlier today, because a fresh run takes minutes.

### 0:25-0:55. The footprint and two questions

**Screen:** scroll to Exhibit 1, The storm's footprint. Show the map, with the SW-NE band. Point to the stamp "Consistent with the event, not proof of cause". Then the two answers beside it.

**Say:**
> One change map, after the hail of 2-3 March 2024. The red band is consistent with a hail swath, and it doesn't repeat in other years. Nobody has checked these fields. Two questions. Did this field fall more than comparable fields outside the storm? [Yes: 1 of 200.] More than its neighbours? [No: 5 of 200, just past our line.] So the effect doesn't look limited to this field.

### 0:55-1:25. The Vanishing, both plots

**Screen:** Exhibit 2 on the strongest case. Drag the slider from 10 m to 3 km. Keep the "strongest of 200" box in shot. Switch tab to the typical case, same exhibit, and drag again.

**Say:**
> Same data, bigger cells. Our illustration, not YES-TECH output. On the strongest of 200, [-0.37] falls to [-0.10] at 3 kilometres. Now the typical plot, chosen by a rule: [-0.13] to [-0.08]. It keeps most of its signal. So when a field is hit harder than its surroundings, area averages can't show it. When a wider stretch falls together, they mostly can.

### 1:25-1:50. The Ten-Field Draw

**Screen:** Exhibit 3 on either Bhiwani case. Let real draws land on the map. Then the two scenario cards. Hold on the limits panel.

**Say:**
> Para 21.5.8: above 25%, a survey samples 10 random parcels from the intimation list. We ran that on real pixels. Across forty plots: about minus 0.07 from all cropland, minus 0.245 from fields that visibly dropped. Those are bounds. The average depends heavily on who is on the list, and nobody outside the insurer can see that list. We don't say the rule is unfair.

### 1:50-2:15. Cross-examination

**Screen:** Exhibit 9, cross-examination record, on the typical case or the strongest. Open harvest, regional trend, and any conceded card. If you warmed a harvest case, show its verdict for 3 seconds.

**Say:**
> A witness has to survive attack. A hostile surveyor raises nine objections. Harvest? Wrong plot? Cloud? Already falling before? Each is answered by a test on real values, and it can concede. [Here's the typical plot: it concedes, and the verdict stays weak.] On the strongest plot, radar doesn't support the optical result, and the verdict says so.

### 2:15-2:35. Arnab: not established yet

**Screen:** Arnab case verdict, then the route panel showing no countdown.

**Say:**
> Cyclone Arnab, this week. About 3.51 lakh hectares of crops damaged, per the Andhra Pradesh Agriculture Minister's preliminary assessment of 29 October. Our answer: no signal established yet. One optical scene after landfall, and the next usable radar is around 4 November. Lodged paddy can stay green, so this doesn't contradict those reports.

If this case's verdict comes back above `weak`, don't present it as cyclone damage. Tell the lead before recording.

### 2:35-3:00. The QR moment

**Screen:** PDF with the QR code. Scan on a phone, or open the link. The stored check appears: hash, "hash matches", time of the check, 104 of 104 (or your case's count). Press the re-check button, and leave it running while you speak. Show the field numbers arriving.

**Say:**
> Every result is sealed with a hash. Scan it, no account needed. This is the last full check, with its time: all [104] numbers, re-downloaded from the public archive, matched. That took about 18 minutes on our connection. The field's own 20 numbers take under a minute. There's no plot-level ground truth, and an insurer may not accept this. But anyone can check what it said.

Update the timings if you've measured them on the deployed host. Never say that every number recomputes in seconds.

## Claims check, before you publish

| Must hear or see | Must not say |
|---|---|
| "Strongest of 200 scanned" each time that plot appears | Any payout amount, or that someone gets paid |
| "Consistent with" for hail | Hail caused it |
| "We ran this earlier today" | That it's running live, if it isn't |
| Radar disagreement | That radar confirms it |
| Bhiwani is a signal case, if the route panel shows | That Bhiwani was a PMFBY claim |
| "No plot-level ground truth" | "Accuracy", "validated" |
| "We did not find" | Claims of being the only one or the earliest |

Holdout: if results are in `docs/validation/engine-results.md` by recording time, add one line in the QR beat, whatever they show. If they change the story, the lead decides the new order. Otherwise don't mention them as results, and say "our holdout results are pending" if asked.

## Live presentation: risk plan

### Say this at the start

> We warmed these cases in advance, and we'll tell you when something is live. A fresh run depends on the public satellite archive and can take minutes.

### Bhiwani route panel

The route panel may say "localized" because we entered "insured" for the demo. Say:

> This event is a signal case, not a PMFBY claim case. A Congress leader said no insurer covered Hisar that season. We entered "insured" to show how routing works.

### If the archive is slow

The app is built for this. A slow read gives a "still computing" state, not a failure.

| You see | Do | Say |
|---|---|---|
| Verdict "still computing", or a provisional result | Keep it on screen for a moment, then open the warmed case | "The images are still downloading. This is the public archive's speed. Here's one we ran earlier." |
| Trace says it's switching to radar, on a cold run | Don't read this as a finding about bad images | "It hasn't got the optical images in time, and that work continues behind the result." |
| An exhibit "failed" with a retry button | Press retry once, then move on | "That exhibit didn't finish. It doesn't change the verdict." |
| Verify shows "could not be reached" | Show the stored check | "The archive is unavailable. That says nothing about the evidence." |
| Verify shows "partial" or "field verified" | Show the honest count | "These 20 match. The others weren't checked this time." |
| Verify shows `mismatch` | Don't explain it away. Open the row | "That's what a failed check looks like. Here's the number that differs." Then tell the lead |
| The app won't load | Use the video, and say it's a recording | "This is our recording of the app. The live link is on the slide." |

Never pass off the video as live.

### Before a judge drops a random pin

Say this **before** the pin goes down:

> Please do. Most pins will correctly show little: there has to be a real event on that date, and a field that changed more than comparable fields. "Your field doesn't show this" is a correct answer. A new pin also has to read from the archive, so its verdict can take a few minutes and the exhibits longer. It only covers India. And it needs a date, so please tell me when something happened.

Then:
- Pick a date with the judge. With no date, the app proposes one from the weather and asks to confirm.
- Keep talking through the trace while it runs. Scene rejections and radar switches are worth pointing out.
- If it's a slow read, offer to leave it running and come back. Runs continue on the server, and the page can be reopened.
- Whatever comes back, read it out as is. A weak or insufficient result is a good moment: read the caveat aloud.

### If you're asked for something we don't have

Go to `docs/TEAM_WALKTHROUGH.md`, section 5. "We don't know" and "that's pending" are acceptable answers. Inventing one isn't.
