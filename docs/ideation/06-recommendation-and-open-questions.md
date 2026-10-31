# 06 — Recommendation & Open Questions

## Head-to-head: the top 3

| | **#1 FasalSaakshi** | **#2 TraceBack** | **#3 Nigrani** |
|---|---|---|---|
| Theme / problem | T2 · P2 | T1 · P4 (+P1) | T1 · P2 |
| Score | 84 | 84 | 75 |
| Likely competitor overlap | **Low.** Few student teams attempt satellite work. | **High.** "Fake news detectors" will be everywhere. | **High.** Pothole apps are a staple. |
| Demand evidence | Protests, ₹ crore pending claims, fresh Sirsa hail (25 Oct 2026) | Rajnath deepfake debunked today; APK scams; IT Rules 2026 | CPGRAMS dissatisfaction 37–46%; HC monitoring |
| Live-demo risk | **Low.** Archives are stable; "drop any pin" works | **Medium.** A wrong verdict on an unknown input is fatal | Medium. Portal filing is fragile; escalation needs time |
| Agentic showcase | Optical → radar fallback, baselines, deadline actions | Claim routing, iterative search, evidence thresholds | Stateful escalation over days |
| Named-in-rubric depth | **Geospatial models** ✓ | Custom RAG / complex graph ✓ | Browser automation ✓ |
| Audience-award potential | Medium-high (satellite before/after reels) | **Highest** | High |
| Data compliance | All open official data, verified live | Real user forwards + live sources | Real reports must be collected |

## Recommendation: build #1, FasalSaakshi

1. **Differentiation is the biggest lever we control.** In a pool of IIT/NIT/BITS teams, the obvious ideas will appear many times. FasalSaakshi is unlikely to have a near-duplicate, and its core idea (*"put the satellite on the farmer's side"*) is easy to remember.
2. **It's the safest of the three on the biggest pillar (Live Demo, 30 points).** Satellite archives don't have captchas, OTPs or closing deadlines, and judges can pick any location in India.
3. **The rubric names it.** "Geospatial models" is listed as an example of genuine depth, and the problem statement names Copernicus.
4. **The timing works.** There's a real hail event (Sirsa/Fatehabad, 25 Oct 2026), with cloud-free before (18 Oct) and after (28 Oct) imagery already verified.
5. **It has a visual story** for the audience award: before/after imagery of a destroyed field from space.

### When to pick #2 instead
Choose TraceBack if **any two** of these are true:
- The team rates the **audience award** as highly as the judges' prizes, and has real social reach (big LinkedIn/Instagram followings, college pages willing to reshare).
- Someone on the team is strong in **multimodal / audio / CV pipelines** and nobody has any appetite for geospatial work.
- The team is confident it can make the "Unverified" path feel trustworthy and avoid a wrong verdict live.

### When to pick #3
Only if the team has strong **city-specific access**: real reports from a ward or city, contacts at a civic body, or a campus community willing to file 50+ real reports in the next few hours.

### On ScholarFlow (the existing plan)
It ranked #4. The deciding issue is timing: **NSP's 2026-27 deadline for most scholarships is today, and OTR needs Aadhaar face authentication**, so a live end-to-end application demo is unlikely to hold up during judging. If the team still wants Theme 1 P3, it needs to retarget to a portal with an open window and no biometric step, and that has to be confirmed in the next hour. `HACKATHON_PLAYBOOK.md` contains a lot of process material that isn't specific to ScholarFlow (phases, checkpoints, handoffs). It can be reused for any of these ideas by swapping the project-specific sections.

## Open questions for the team

These are the questions that could change the recommendation. We didn't want to guess the answers:

1. **Are you open to dropping ScholarFlow?** The playbook was committed yesterday. Has anything been built or validated since, e.g. a working portal flow?
2. **Exact submission deadline and time zone?** The screenshot says ~31 h left. Is there a separate deadline for the video, deck and form?
3. **Skills:** has anyone worked with geospatial/raster data (GDAL, rasterio, xarray, Earth Engine), or with audio/vision ML? This decides between #1 and #2.
4. **Languages:** which Indian languages do team members speak fluently? The demo voice notes should be in a language you can check yourselves (Hindi/Punjabi fits the Sirsa demo).
5. **Audience award:** roughly what social reach does the team have across X/Instagram/LinkedIn? Is the audience award a goal or a bonus?
6. **API budget:** are you willing to spend a small amount on paid tiers (an LLM API, reverse-image search, a higher Open-Meteo quota)? #2 needs this more than #1.
7. **Field contacts:** does anyone know a farmer, FPO or KVK (for #1), or a city ward/community (for #3)? Even one real user quote in the pitch helps the impact score a lot.

## Next steps once the idea is locked

1. Freeze scope to the "MVP cut" section of the chosen idea's doc.
2. Assign owners. For #1: geospatial engine / agent + RAG + channel / UX + evidence PDF + demo.
3. Prove the hardest real-data path first. For #1: plot polygon → S2 before/after NDVI on Sirsa within the first 3–4 hours.
4. Start the audience-award content pipeline on day 1, not at the end.
