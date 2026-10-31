# 06 — Recommendation & Open Questions

> **Superseded in part.** This file is an early working draft and some claims here were later corrected against the official guidelines and real data. For current facts see [`docs/submission/facts.md`](../submission/facts.md), and for the current design see [`docs/plan/07-build-contract.md`](../plan/07-build-contract.md).

> **Revision 2 (31 Oct 2026):** the team's priorities are **judge impression, impact, and a problem that's not fully solved yet**. The audience award is not a goal.

## Head-to-head: the top 3

| | **#1 FasalSaakshi** | **#2 AgniDrishti** | **#3 TraceBack** |
|---|---|---|---|
| Theme | T2 · P2 (exact fit) | T2 (environmental; P2-adjacent) | T1 · P4 (+P1) (exact fit) |
| Score | **87** | 81 | 80 |
| How unsolved? | **Unsolved for farmers.** Satellites only work for insurers/states, at unit level. | **Unsolved operationally.** Official data still counts fires; burnt-area work exists only as an annual research report. | Partly solved. Many fact-checkers and detectors exist; the long tail is unserved. |
| Likely competitor overlap | Low | Very low | **High** ("fake news detector") |
| Impact | Crore-scale PMFBY enrolment; ₹ thousands of crores in disputed or pending claims | 30M+ people in Delhi-NCR; national emissions accounting; Supreme Court-level issue | Hundreds of millions of WhatsApp users; scam losses |
| Agentic showcase | **Strong:** optical → radar fallback, baselines, deadline-driven filing | **Medium:** analysis-heavy; prevention actions must be real | **Strongest:** claim routing, iterative search, evidence thresholds |
| Live-demo risk | Low | Low | Medium (a wrong verdict live is fatal) |
| Rubric-named depth | Geospatial ✓ | Geospatial ✓ | RAG / state graph ✓ |
| Main weakness | Satellite signal ≠ yield, so it must be presented as evidence with confidence | Theme fit; can read as "policing farmers" | Crowded first impression |

## Recommendation: build #1, FasalSaakshi

It is the best match for all three of your criteria:

1. **Not solved yet, and clearly so.** The government's own satellite systems (YES-TECH, CROPIC) serve insurers and states at insurance-unit level. No farmer-side, plot-level evidence tool exists. Farmers protested in Haryana and Rajasthan in 2025 precisely because they couldn't contest the satellite numbers.
2. **Judge impression.**
   - It matches Theme 2 Problem 2 almost word for word (satellite + weather → micro-location risk → mitigation and action).
   - It uses the rubric's own example of depth ("geospatial models").
   - It has a real agentic story: the agent switches from optical to radar when it's cloudy, checks baselines, self-checks, and acts on deadlines.
   - Few or no other teams will have built anything like it.
3. **Impact.** Crore-scale enrolment, a 72-hour rule that silently kills valid claims, ₹4,107 cr pending (Dec 2025), and a real hail event in Sirsa this week to demo on. Cloud-free before (18 Oct) and after (28 Oct) imagery is already verified.
4. **Safest live demo:** no OTP, captcha, closing portals, or rate-limited single source.

### Choose #2 (AgniDrishti) instead if…
- The team is most energised by **air pollution and climate accountability**, and is comfortable pitching the theme fit (Theme 2's "environmental challenges" plus Problem 2's satellite risk and mitigation framing).
- You want the **highest "nobody has done this live" factor**. The iFOREST report and the Supreme Court hearings give judges instant context.
- You commit to making the **prevention/action layer real** (officer briefs, farmer outreach with official incentive rules). Otherwise the agentic score suffers.

**Useful fact:** #1 and #2 share the same core engine (Sentinel-2 STAC search + per-field index time series). **The first 3–4 hours of work are identical**, so you can start now and make the final call after the engine runs on real fields.

### Choose #3 (TraceBack) instead if…
- Nobody on the team wants to touch raster/geospatial data, and you have strong multimodal/audio skills.
- You are confident in making "Unverified" an honest, well-designed outcome. A wrong verdict in front of judges is the main risk.
- You can lead the pitch with the *provenance + official-source + scam* angle (the DAU "only 2% are deepfakes" insight), not "deepfake detection".

### On ScholarFlow (the existing plan)
It's now **#5 (71)**. NSP's 2026-27 deadline for most scholarships is **today**, and One-Time Registration requires **Aadhaar face authentication**, so a live end-to-end application demo is unlikely to survive judging. The process parts of `HACKATHON_PLAYBOOK.md` (phases, checkpoints, handoffs) can be reused for any idea above.

## Decision log: team answers (31 Oct 2026)

| Question | Answer | Effect |
|---|---|---|
| Anything built for ScholarFlow? | **No** | Nothing is sunk. Pivoting costs nothing; ScholarFlow stays out of the top 3. |
| Submission deadline | **~2 days left** | A bit more room than the ~31 h estimate. The MVP can include some nice-to-haves (neighbour analysis, scheduled re-checks, grievance drafting for #1). |
| Paid API budget | **Gemini paid APIs available** | Covers reasoning, function calling, Search grounding, vision, audio in, and Hindi TTS. Helps all three ideas. The ranking is unchanged: Search grounding helps TraceBack's retrieval, but its crowding problem remains. For #1, Gemini adds a **news-corroboration signal** and a **visual second opinion** (see [03 §5a](03-idea-1-fasalsaakshi.md#5a-gemini-mapping-paid-access-confirmed)). |

**Gemini caution:** Gemini 2.5 models shut down in October 2026. Use current 3.x models and confirm the exact IDs in AI Studio.

## Still-open questions for the team

1. **Skills:** has anyone worked with raster/geospatial data (rasterio, xarray, GDAL, Earth Engine), or with audio/vision ML? This is the main tie-breaker between #1/#2 and #3.
2. **Languages:** which Indian languages can the team verify? Hindi/Punjabi suits both Sirsa (#1) and Punjab (#2).
3. **Field contacts:** any farmer, FPO, KVK or agriculture officer you could get one real quote from? A single real user voice makes the impact pillar much stronger.

## Next steps once the idea is locked

1. Freeze scope to the "MVP cut" section of the chosen idea's doc.
2. Assign owners. For #1: geospatial engine / agent + policy RAG + filing actions / channel + voice + evidence PDF + demo.
3. **Hours 0–4:** prove the real-data core first. STAC search → per-plot NDVI before/after on Sirsa (#1) or burn index on Sangrur (#2).
4. Integrate continuously, keep a deployed build from early on, and protect the last few hours for the video, deck and rehearsal.
