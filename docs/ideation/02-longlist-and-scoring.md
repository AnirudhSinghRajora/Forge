# 02 — Longlist & Scoring

## Method

1. Generated 11 candidate ideas across both themes: each listed problem, plus cross-cutting variants and the team's existing ScholarFlow direction.
2. Researched each one for demand evidence, existing solutions, and data availability. Probed the key data sources live on 31 Oct 2026 (see [07](07-sources.md#live-api-checks-31-oct-2026)).
3. Scored each idea 1–5 on seven weighted criteria (weights in [01 §7](01-competition-analysis.md#7-selection-criteria-derived-from-the-above)). Weighted total = Σ(score × weight) / 5, out of 100.
4. Applied one hard gate: **any idea whose core output would need non-public or fabricated data is flagged as a disqualification risk**, whatever its score.

The scores are our judgement grounded in the evidence. They are not a prediction of judges' marks.

## The longlist

| ID | Idea | Theme · Problem | Core concept |
|---|---|---|---|
| A | **FasalSaakshi** (crop-loss evidence & claim agent) | T2 · P2 (+P1) | Plot-level satellite (optical + radar) and weather evidence of crop damage. An agent files PMFBY intimation and grievance within the deadlines, with voice in the farmer's language. |
| B | **TraceBack** (provenance-first misinformation & scam verifier) | T1 · P4 (+P1) | WhatsApp-first investigator agent: traces origin, checks official registries and fact-checks, analyses links/APKs, returns a forwardable debunk in local language |
| C | **Nigrani** (civic accountability agent) | T1 · P2 | Multimodal civic report, then severity, de-dup, jurisdiction resolution, official filing, SLA tracking, and an escalation ladder ending in an RTI draft |
| D | ScholarFlow (scholarship application agent) | T1 · P3 | Browser agent that fills scholarship applications from a student profile (existing team plan) |
| E | Mandi "Sell-or-Hold" agent | T2 · P1 | Live mandi prices across nearby markets, short-term forecast, transport cost, and rain risk, producing a recommendation of where and when to sell |
| F | Gazette-to-Citizen change explainer | T1 · P1 | Monitors eGazette/PIB notifications, diffs them against prior rules, and pushes a personalised "what changed for you" voice explainer |
| G | Outdoor-worker heat & air-quality guardian | T2 · P3 | Hyperlocal WBGT and AQI for shift planning by contractors and gig platforms, with worker voice alerts |
| H | Disaster relief logistics swarm | T2 · P4 | SACHET alerts, then flood-aware routing, relief dispatch |
| I | Edge smart-grid / water controller | T2 · P3 | Edge agent reallocating micro-grid or water during heatwaves |
| J | Generic farmer advisory voice bot | T2 · P1 | Weather + mandi + soil, served as conversational advice |
| K | Read-only "Sarkari status" agent | T1 · P3 | Browser agent that checks status across legacy portals (PM-Kisan, eCourts, EPFO) over WhatsApp |

## Scoring matrix

Scores are 1–5. Weights: Uniq 20 · Demand 15 · Impact 15 · Agentic 15 · Tech 10 · Demo/Data 15 · Viral 10.

| ID | Uniq | Demand | Impact | Agentic | Tech | Demo/Data | Viral | **Total** | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **A** FasalSaakshi | 5 | 4 | 4 | 4 | 5 | 4 | 3 | **84** | ✅ all-open data |
| **B** TraceBack | 3 | 5 | 5 | 5 | 4 | 3 | 5 | **84** | ✅ (inputs are real user forwards) |
| **C** Nigrani | 2 | 5 | 4 | 4 | 3 | 4 | 5 | **75** | ✅ (needs real reports collected during the event) |
| D ScholarFlow | 3 | 4 | 4 | 5 | 4 | 2 | 4 | **73** | ⚠ live-portal dependency |
| E Mandi Sell-or-Hold | 3 | 4 | 5 | 4 | 3 | 4 | 2 | **73** | ⚠ data.gov.in timed out from our container; verify from an Indian network |
| G Heat/AQI guardian | 4 | 4 | 4 | 3 | 3 | 3 | 3 | **70** | ✅ but off-season for heat |
| F Gazette-to-Citizen | 3 | 3 | 4 | 3 | 3 | 5 | 2 | **67** | ✅ |
| H Relief logistics swarm | 3 | 3 | 4 | 5 | 4 | 2 | 2 | **66** | ❌ supplier inventory / fleet APIs don't exist publicly → dummy-data risk |
| K Sarkari status agent | 3 | 3 | 4 | 4 | 3 | 2 | 2 | **61** | ⚠ captchas/OTP |
| J Generic farmer bot | 1 | 4 | 5 | 3 | 2 | 4 | 2 | **60** | ✅ but saturated |
| I Edge grid controller | 3 | 3 | 3 | 3 | 4 | 1 | 1 | **52** | ❌ no real telemetry → dummy-data risk |

## Why each idea landed where it did

### A — FasalSaakshi (84): most differentiated
- **Demand:** Farmers have protested satellite-based claim cuts. In Haryana 2025, they say crop-cutting experiments put claims at ₹450 cr and satellite-based assessment cut that by about ₹350 cr. Rajasthan claims were pending well beyond the 2-month timeline. Nationally, ₹4,107 cr of claims were still pending as of 31 Dec 2025.
- **Gap:** Satellites are used *on* farmers. YES-TECH runs at insurance-unit level (moderate 5–30 m inputs, a minimum 30% weightage), which suits unit aggregation but not individual small farms. No mainstream tool gives the farmer plot-level evidence.
- **Rubric fit:** "Geospatial models" is literally named in the depth criterion, and Copernicus is named in the problem text.
- **Lower virality (3):** farmers aren't the hackathon's social audience. A satellite before/after visual still makes a strong reel.

### B — TraceBack (84): most viral, most timely, most crowded
- **Demand:** A PIB debunk of a Rajnath Singh deepfake went out *today*. McAfee (Feb 2026) says 1 in 5 Indians have encountered a voice-clone scam. Fake PM-Kisan APKs have caused real losses (₹1.95 lakh in a single Hyderabad case), and police alerts are out in multiple states.
- **Key insight from data:** the Deepfakes Analysis Unit found only **2% deepfakes** among tipline submissions; 9% were manipulated media and 55% were spam. **Most misinformation is cheapfakes and miscontext, not deepfakes.** So a *provenance and official-source* engine beats yet another deepfake classifier. That's our USP over the crowd.
- **Uniqueness only 3:** "fake news detector" will be among the most common submissions. Live-demo robustness is also only 3, because detectors on unknown live inputs are unreliable and verdicts must be guarded carefully.

### C — Nigrani (75): high demand, crowded concept
- **Demand:** In CPGRAMS feedback, 46% of citizens (Aug 2025) and 37% (Nov 2025) were dissatisfied after "resolution". State/UT pendency was 1,92,877 (Feb 2026). The Karnataka HC is monitoring Bengaluru potholes (Aug 2026), and Bengaluru tops NCRB civic-negligence deaths.
- **Uniqueness only 2:** pothole-reporting apps are a hackathon staple. What lifts it is the **accountability agent** (jurisdiction resolution, SLA watch, escalation, RTI). The concept still reads as familiar on first impression.

### Why ScholarFlow dropped to #4
- **Demand is real.** SC Post-Matric Scholarship beneficiaries fell from 48 lakh (2024-25) to 36 lakh (2025-26), and the ministry blamed poor awareness (The Wire). Agentic depth is excellent (5).
- **But live-demo robustness is 2/5 right now:**
  1. **NSP 2026-27's last date for most scholarships is 31 Oct 2026, today.** Institute verification closes 15 Nov. During judging, there may be no open NSP application to demo against. *(Secondary sources; confirm on scholarships.gov.in.)*
  2. **NSP One-Time Registration requires face authentication** (Aadhaar FaceRD). An agent cannot and should not automate that, so the "end-to-end" claim breaks at step 1.
  3. Aadhaar OTPs, captchas, and the ethics of submitting real applications on someone's behalf during a public demo.
  4. The playbook itself says "no suitable portal or authorized end-to-end workflow has yet been established."
- **If the team still prefers it:** pivot to state scholarship portals with windows still open, or reframe as eligibility, documents and pre-filled review with the human doing OTP/face-auth. That turns the 25-point agentic story into "preparation", which the playbook itself warns against overselling.

### E — Mandi Sell-or-Hold (73): solid, but less differentiated
- Real pain: May 2026 coverage says farmers received about 37% of the retail price; tomato price crashes led to highway blockades in Karnataka (Aug 2026).
- But "crop price prediction" is a common hackathon build. The live dependency (data.gov.in mandi API) **timed out from our container**, so it needs verifying from India. **Can be folded into A** as a post-loss "salvage sale" feature if wanted.

### G — Heat/AQI guardian (70)
High impact (around 380M heat-exposed workers; 40,000+ heatstroke cases and 700+ deaths in 2024). But in November the live heat signal is weak, and AQI is a stretch for Theme 2's wording. Strong idea for a summer hackathon.

### F, K (67, 61)
F is robust but low on agentic depth and virality. K has the same captcha/OTP problem as D, with a weaker story.

### H, I: gated out
Both need data (supplier inventories, fleet telemetry, grid/sensor feeds) that is not publicly available. Building them would mean simulated data, which is a **zero-tolerance disqualification** under the rules.

### J (60)
Saturated: Kisan e-Mitra has handled 8.2M+ queries, Digital Green's Farmer.Chat has reached 460k users, and many startups do the same. No clear USP is available in a 30-hour window.
