# 01 — Competition Analysis: What Actually Wins Forge '26

## 1. Facts from the event page (user-supplied, 31 Oct 2026)

- **Event:** Forge '26, Gen AI Buildathon by NxtWave Launchpad. Open only to students from IITs, NITs, IIITs and BITS.
- **Window:** started 30 Oct, 7:30 PM. Builds take 48 hours. The screenshot shows **"Hackathon ends in 31:16:43."**
- **Teams:** 2–3 members.
- **Prizes:** ₹2 lakh+ in total. The **top 10 present at the finale**. Judges pick **2 winners**; the **audience award** goes to 1 team.
- **Themes:** (1) Civic Pulse, Digital Governance & Public Information; (2) Climate, Resource Infrastructure & Global Supply Resilience. The team picks a theme at submission and can change it until submissions close.

## 2. The rubric, and what it really rewards

| Pillar | Points | What judges are told to look for | Implication for idea choice |
|---|---:|---|---|
| Live Demonstration & Robustness | **30** | Runs live without crashing; handles unexpected inputs, missing data, flaky networks | **Biggest pillar.** Avoid ideas whose core path depends on things you don't control live: OTP, captchas, Aadhaar face-auth, closed portals, rate-limited single APIs. |
| AI Reasoning & Agentic Execution | 25 | Multi-step planning, tool calls, error handling, self-correction; accuracy, few hallucinations, **source attribution** | The agent needs real tools and real branching (e.g. "cloudy, so switch to radar"), not a chatbot. Every claim should carry a citation. |
| Problem Relevance, Impact & USP | 25 | Real value for affected people; **clear differentiation from existing solutions and off-the-shelf chatbots**; novelty; scalability | Expect many IIT/NIT teams to build the obvious things: scheme chatbots, fake-news detectors, pothole apps, farmer chatbots. **Differentiation is worth more than polish.** |
| Technical Architecture & Engineering Depth | 20 | Clean modular code, low latency; **"beyond superficial wrappers… e.g., custom RAG pipelines, geospatial models, browser automation loops, complex state graphs"** | The rubric names **geospatial models** and **browser automation** as examples of depth. Ideas built on these get credit almost automatically. |

**Total: 100.** Live demo plus agentic execution make up 55% of the score. Whatever we build has to be agentic and has to hold up live.

## 3. Disqualification traps, and how each idea handles them

| Rule | Risk pattern | How to stay safe |
|---|---|---|
| **No dummy data (zero tolerance)**: no hardcoded JSON, static mocks or placeholder numbers; must use live backends, real-time APIs, or official open datasets | Ideas that need data nobody publishes, such as supplier inventories, grid telemetry or private fleet data | Prefer ideas where **every** number comes from an open feed: satellites, IMD/NDMA, Open-Meteo, NASA POWER, data.gov.in, official registries, or real user input |
| Core logic built during the window | Reusing a past project | Start from a fresh repo. The existing repo only has docs, which is fine. |
| Every member must explain the codebase | One-person "black box" ML | Keep the architecture explainable. Each member owns a layer but walks through the whole flow. |
| No pre-recorded demos disguised as live | — | The demo video must be a screen recording of the live app. Judges will also run it themselves. |

## 4. The Audience Favourite Award: a separate, winnable prize

Scoring: **reshare/repost = 5, comment = 3, like = 1**, summed across **X + Instagram + LinkedIn**.

Implications:
- Reshares are worth 5× likes. Content needs to be **forwardable**: a strong before/after visual, a "check this yourself" hook, or a debunk people want to share.
- Ideas with a visual "wow" moment do better here, e.g. a satellite before/after of a hail-hit field, or a deepfake being caught.
- This prize is **independent** of the judges' top 2. An idea that's strong on both gives two shots at winning.

## 5. Timing facts that change the analysis

| Fact | Source | Impact |
|---|---|---|
| ~31 hours of build time left at research time | Event screenshot | A pivot decision is needed now. Every hour spent debating is an hour not building. |
| **NSP 2026-27 last date for most scholarships = 31 Oct 2026**; institute verification closes 15 Nov; **OTR needs face authentication** | Careers360, IndiaScholarships, CareerIndia (secondary; confirm on scholarships.gov.in) | Breaks a live NSP application demo for ScholarFlow (see 02) |
| **PIB Fact Check debunked an AI-manipulated Rajnath Singh video today (31 Oct 2026)**; fake Indian Army / Arunachal videos 26–27 Oct | IANS / Newschecker / Newsmobile | Misinformation is front-page news this week, which helps idea #2 |
| **Unseasonal rain + hail damaged standing paddy & cotton in Sirsa and Fatehabad (Haryana), reported 25 Oct 2026** | UNI | A fresh, real crop-loss event to demo idea #1 on. **Verified:** cloud-free Sentinel-2 scenes over Sirsa on **18 Oct (before)** and **28 Oct (after)**, plus Sentinel-1 radar passes on 16/24/28 Oct |
| Kharif harvest season, when post-harvest losses are covered for 14 days in-field under PMFBY | PMFBY norms (insurer pages) | Idea #1 is seasonally relevant right now |
| IT Rules amendment on synthetic media (G.S.R. 120(E), effective 20 Feb 2026): labelling, 3-hour takedown on orders, 2-hour for NCII | MediaNama, Hogan Lovells, Freshfields | Regulatory tailwind for idea #2 |

## 6. Who we're competing against

The pool is IIT/NIT/IIIT/BITS students, most of whom will follow the problem-spectrum text closely. Expect a lot of:
- Scheme/policy explainer chatbots (Theme 1 P1)
- "Fake news / deepfake detector" web apps (Theme 1 P4)
- Pothole/civic reporting apps (Theme 1 P2)
- Farmer advisory chatbots (Theme 2 P1)

Few teams will attempt real **geospatial / satellite** work (Theme 2 P2), because it feels intimidating. That's an opening. With three strong devs, we can pick the problem other teams shy away from.

## 7. Selection criteria derived from the above

Used for scoring in [02](02-longlist-and-scoring.md):

| Criterion | Weight | Why |
|---|---:|---|
| Uniqueness / USP vs existing products **and** likely competitor builds | 20 | Rubric pillar 3, plus differentiation from the crowd |
| Evidence of real demand (people actively asking or protesting) | 15 | "Real problem people are asking solutions for" |
| Impact & reach (number of people, severity) | 15 | Rubric pillar 3 |
| Agentic depth (genuine multi-step tool use, self-correction) | 15 | Rubric pillar 2 |
| Technical depth | 10 | Rubric pillar 1 |
| Live-demo robustness & data compliance | 15 | Rubric pillar 4 plus the disqualification rules |
| Audience-award virality | 10 | Separate prize |
