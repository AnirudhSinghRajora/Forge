# 02 — Longlist & Scoring

> **Revision 2 (31 Oct 2026):** the team said the **audience award is not a priority**. The goal is a strong impression on judges, real impact, and a problem that is **not fully solved yet**. Virality was removed as a criterion, weight moved to "unsolved gap" and to the rubric's heaviest pillars, and a new candidate (**L, AgniDrishti**) was added. Result: **AgniDrishti enters at #2, TraceBack moves to #3, and Nigrani drops out of the top 3** (its rank depended on virality).

## Method

1. Generated 12 candidate ideas across both themes, including the team's existing ScholarFlow direction.
2. Researched demand evidence, existing solutions (**how much of the problem is already solved**), and data availability. Probed key data sources live (see [07](07-sources.md#live-api-checks-31-oct-2026)).
3. Scored each idea 1–5 per criterion. Weighted total = Σ(score × weight) / 5, out of 100.
4. Hard gate: any idea whose core output would need non-public or fabricated data is flagged as a **disqualification risk**.

### Criteria and weights (revision 2)

| Criterion | Weight | What a 5 means |
|---|---:|---|
| **Unsolved gap / USP** | 25 | No existing product or government system addresses the core gap, and few competing teams will attempt it |
| Demand evidence | 10 | Protests, court cases, official reports, or parliamentary questions show people actively want a fix |
| Impact & reach | 15 | Crores of people affected, or severe harm (money, health, life) |
| Agentic depth | 20 | Real multi-step planning, tool use, fallback, and self-correction (rubric: 25 pts) |
| Technical depth | 10 | Matches the rubric's "genuine technical execution" examples |
| Live-demo robustness & data compliance | 20 | No OTP/captcha/closed-portal dependency; all data live and official (rubric: 30 pts + disqualification rules) |

Scores are evidence-grounded judgement, not a prediction of judges' marks.

## Longlist

| ID | Idea | Theme · Problem | How solved is it today? |
|---|---|---|---|
| **A** | **FasalSaakshi**: farmer-side satellite crop-loss evidence + claim agent | T2 · P2 | **Unsolved for farmers.** Satellite assessment exists only on the insurer/state side, at unit level. |
| **L** | **AgniDrishti**: live burnt-area truth + Delhi-impact + prevention agent for stubble burning | T2 (P2-adjacent) | **Unsolved operationally.** Official data still uses fire counts; burnt-area analysis exists only as an annual research report; CAQM protocol pending. |
| **B** | **TraceBack**: provenance-first misinformation & scheme-scam verifier | T1 · P4 (+P1) | **Partly solved.** Human fact-checkers, DAU tipline, enterprise detectors exist; the long tail and regional languages are unserved. |
| C | Nigrani: civic accountability agent | T1 · P2 | Partly solved. Many reporting channels exist; escalation and follow-through don't. |
| D | ScholarFlow: scholarship application agent | T1 · P3 | Partly solved (myScheme, NSP, scholarship aggregators); execution unsolved but blocked by biometrics |
| E | Mandi "Sell-or-Hold" agent | T2 · P1 | **Mostly solved for price discovery.** The eNAM app already shows prices at mandis within 100 km with route maps. Net-realisation and timing advice remain open. |
| F | Gazette-to-Citizen change explainer | T1 · P1 | Partly solved (myScheme, Haqdarshak, Jugalbandi) |
| G | Outdoor-worker heat & AQI guardian | T2 · P3 | Unsolved, but off-season for heat |
| H | Disaster relief logistics swarm | T2 · P4 | Unsolved, but needs non-public data |
| I | Edge smart-grid / water controller | T2 · P3 | Needs non-public telemetry |
| J | Generic farmer advisory voice bot | T2 · P1 | **Solved/saturated** (Kisan e-Mitra, Farmer.Chat, many startups) |
| K | Read-only "Sarkari status" agent | T1 · P3 | Partly solved (UMANG, DigiLocker); captcha-heavy |

## Scoring matrix (revision 2)

Weights: Unsolved 25 · Demand 10 · Impact 15 · Agentic 20 · Tech 10 · Demo/Data 20.

| Rank | ID | Unsolved | Demand | Impact | Agentic | Tech | Demo/Data | **Total** | Gate |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | **A** FasalSaakshi | 5 | 4 | 4 | 4 | 5 | 4 | **87** | ✅ all-open data, verified |
| 2 | **L** AgniDrishti | 4 | 4 | 5 | 3 | 5 | 4 | **81** | ✅ open data (FIRMS needs a free key) |
| 3 | **B** TraceBack | 3 | 5 | 5 | 5 | 4 | 3 | **80** | ✅ |
| 4 | E Mandi Sell-or-Hold | 3 | 4 | 5 | 4 | 3 | 3 | **72** | ⚠ agmarknet.gov.in 403 / data.gov.in timeout from non-Indian network |
| 5 | D ScholarFlow | 3 | 4 | 4 | 5 | 4 | 2 | **71** | ⚠ live-portal dependency, NSP deadline today |
| 5 | F Gazette-to-Citizen | 3 | 3 | 4 | 3 | 3 | 5 | **71** | ✅ |
| 7 | C Nigrani | 2 | 5 | 4 | 4 | 3 | 4 | **70** | ✅ (needs real reports collected) |
| 7 | G Heat/AQI guardian | 4 | 4 | 4 | 3 | 3 | 3 | **70** | ✅ |
| — | H Relief logistics swarm | 3 | 3 | 4 | 5 | 4 | 2 | 69 | ❌ dummy-data risk |
| 10 | K Sarkari status agent | 3 | 3 | 4 | 4 | 3 | 2 | **63** | ⚠ captchas/OTP |
| 11 | J Generic farmer bot | 1 | 4 | 5 | 3 | 2 | 4 | **60** | ✅ but saturated |
| — | I Edge grid controller | 3 | 3 | 3 | 3 | 4 | 1 | 54 | ❌ dummy-data risk |

**How close are the scores?** A leads clearly. L and B are effectively tied (one point apart, well within judgement error). The choice between them is a trade-off, explained in [06](06-recommendation-and-open-questions.md). Everything from #4 down is clustered at 70–72, and none of those ideas is a strong contender.

## Rationale per idea

### A — FasalSaakshi (87)
- **Unsolved:** satellites are used *on* farmers, never *for* them. YES-TECH works at insurance-unit level (5–30 m inputs, at least 30% weightage) and "not individual small farms".
- **Demand:** the Haryana 2025 protest says CCE estimates were cut by about ₹350 cr after satellite assessment. ₹4,107 cr pending nationally (Dec 2025). A fresh Sirsa hail event (25 Oct 2026).
- **Judge impression:** the rubric names "geospatial models"; few teams will attempt it; a robust "drop any pin" demo.
- Deep dive: [03](03-idea-1-fasalsaakshi.md)

### L — AgniDrishti (81)
- **Unsolved:** official counts miss post-overpass fires. iFOREST found counts down 90%+ while burnt area fell only 25–37%. The Supreme Court is examining evasion, and CAQM's burnt-area protocol isn't operational.
- **Impact:** Delhi-NCR air (30M+ people), plus emissions accounting.
- **Weaker on:** agentic depth (analysis-heavy, so the prevention layer must be real) and **theme fit** (environmental, but not an exact match to a listed problem).
- Deep dive: [04](04-idea-2-agnidrishti.md)

### B — TraceBack (80)
- **Unsolved:** the long tail of regional-language misinformation and scheme scams. **But** many tools exist (human fact-checkers, the DAU tipline, Vastav AI, SynthID/C2PA checks), and "fake news detector" will be one of the **most common submissions**, which hurts first impressions.
- **Strongest agentic story** of all candidates, and enormous reach.
- Deep dive: [05](05-idea-3-traceback.md)

### E — Mandi Sell-or-Hold (72): dropped from contention
New finding: **the eNAM app already shows prices for nearby eNAM and non-eNAM mandis within 100 km, with route maps** (Lok Sabha reply). eNAM has 1.80 crore farmers registered (Mar 2026). The open gap (net realisation after transport and commission, and sell-vs-store timing) is real. Farmers get only **33% / 36% / 37%** of the consumer rupee for tomato / onion / potato (RBI WP 08/2024). But the core is "partly solved", forecasts carry about 20% error (SARIMA onion MAPE 21% in one study), and the price sources were unreachable from our container.

### D — ScholarFlow (71)
NSP's 2026-27 deadline for most scholarships is **today**, and OTR requires **Aadhaar face authentication**, so the live end-to-end demo breaks at step 1. Details in [06](06-recommendation-and-open-questions.md#on-scholarflow-the-existing-plan).

### C — Nigrani (70): out of the top 3
Without the virality criterion, its weakness on "unsolved" (many reporting apps; a crowded hackathon concept) decides it. Its deep dive is kept as a runner-up reference: [08](08-runner-up-nigrani.md).

### F, G, K, J
F is robust but low on agentic depth. G is strong but off-season for heat, and AQI is a stretch for the theme. K has the same captcha/OTP problem as D. J is saturated.

### H, I: gated out
Both need non-public data (supplier inventories, fleet or grid telemetry). Building them would require simulated data, which the rules disqualify with zero tolerance.
