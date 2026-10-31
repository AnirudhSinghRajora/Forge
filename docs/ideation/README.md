# Forge '26 — Idea Research & Selection

Research date: **31 Oct 2026**. About 31 hours of the build window were left when this was written.

This folder holds the research behind choosing what to build for the Forge Gen AI Buildathon (NxtWave): competition constraints, a longlist of 12 ideas scored against the judging rubric, deep dives on the top 3, and a recommendation.

**Team inputs so far:** nothing has been built for ScholarFlow; ~2 days left to submit; Gemini paid APIs available (mapping in [03 §5a](03-idea-1-fasalsaakshi.md#5a-gemini-mapping-paid-access-confirmed)).

**Revision 2:** the team's priorities are **judge impression, impact, and a problem that isn't fully solved yet**. The audience award is not a goal. Scores and rankings were redone on that basis.

## TL;DR — Top 3

| Rank | Idea (working name) | Theme | One-line pitch | How unsolved? | Score |
|---|---|---|---|---|---:|
| **1** | **FasalSaakshi**: farmer-side satellite crop-loss evidence & claim agent | T2 · P2 | Satellites are already used to judge farmers' claims. This gives the *farmer* plot-level satellite evidence, and an agent that files the claim before the 72-hour deadline. | Unsolved for farmers: government satellite systems work at insurance-unit level for insurers/states | **87** |
| **2** | **AgniDrishti**: stubble-burning truth & prevention agent | T2 | Official counts say farm fires fell 90%; actual burnt area fell only 25–37%. This measures what really burned every day, field by field, weights it by today's wind toward Delhi, and targets the fields not yet burned. | Unsolved operationally: counts still used; burnt-area analysis only annual; CAQM protocol pending | **81** |
| **3** | **TraceBack**: provenance-first misinformation & scheme-scam verifier | T1 · P4 (+P1) | Forward any suspicious item on WhatsApp. An investigator agent traces its origin, checks official sources and scam signals, and replies in your language. | Partly solved: many fact-checkers and detectors exist; long tail unserved; crowded among competitors | **80** |

**Recommendation: build #1, FasalSaakshi.** #1 and #2 share the same satellite engine, so the first 3–4 build hours are identical. Reasoning and tie-breakers are in [06](06-recommendation-and-open-questions.md).

The existing ScholarFlow plan (`HACKATHON_PLAYBOOK.md`) ranks #5. **NSP's 2026-27 deadline for most scholarships is today (31 Oct), and One-Time Registration requires Aadhaar face authentication**, which blocks a live end-to-end demo.

## Documents

| # | File | What it covers |
|---|---|---|
| 01 | [01-competition-analysis.md](01-competition-analysis.md) | Rules, rubric, what judges reward, disqualification traps, timing facts, selection criteria |
| 02 | [02-longlist-and-scoring.md](02-longlist-and-scoring.md) | 12 ideas, "how solved is it today", weighted matrix, why each was cut |
| 03 | [03-idea-1-fasalsaakshi.md](03-idea-1-fasalsaakshi.md) | Deep dive on #1 |
| 04 | [04-idea-2-agnidrishti.md](04-idea-2-agnidrishti.md) | Deep dive on #2 |
| 05 | [05-idea-3-traceback.md](05-idea-3-traceback.md) | Deep dive on #3 |
| 06 | [06-recommendation-and-open-questions.md](06-recommendation-and-open-questions.md) | Final pick, tie-breakers, questions for the team |
| 07 | [07-sources.md](07-sources.md) | All sources + the live API checks |
| 08 | [08-runner-up-nigrani.md](08-runner-up-nigrani.md) | Former #3 (civic accountability agent), kept for reference |

Each deep dive covers: problem evidence, existing solutions and the gap, USP, user journey, agent design, architecture, verified data sources, demo script, rubric mapping, risks, and MVP cut.

## How to read the evidence
- **Verified live** means we called the API or feed on 31 Oct 2026 and got real data back.
- Statistics come from parliamentary answers, PIB, research bodies, or named news outlets. Secondary sources are marked. Verify any caveated number before putting it on a slide.
- Product names are provisional.
