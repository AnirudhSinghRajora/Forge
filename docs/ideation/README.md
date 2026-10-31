# Forge '26 — Idea Research & Selection

Research date: **31 Oct 2026**. Per the event screenshot, about 31 hours of the build window were left when this was written.

This folder holds the research behind choosing what to build for the Forge Gen AI Buildathon (NxtWave). It covers the competition constraints, a longlist of 11 ideas scored against the judging rubric, deep dives on the top 3, and a final recommendation.

## TL;DR — Top 3

| Rank | Idea (working name) | Theme / problem | One-line pitch | Score /100 |
|---|---|---|---|---:|
| **1** | **FasalSaakshi** — satellite evidence & claim agent for crop-loss | Theme 2 · Problem 2 (Predictive Climate & Micro-Location Yield Engine) | Insurers and states already use satellites to judge farmers' claims. FasalSaakshi gives the *farmer* the same satellite evidence for their own plot, plus an agent that files the claim before the 72-hour deadline. | **84** |
| **2** | **TraceBack** — provenance-first misinformation & scheme-scam verifier on WhatsApp | Theme 1 · Problems 4 + 1 | Forward any video, voice note, screenshot, link or APK. An investigator agent traces where it came from, checks it against official sources, and sends back a forwardable debunk card in your language. | **84** |
| **3** | **Nigrani** — civic accountability agent | Theme 1 · Problem 2 (Civic Grievance & Infrastructure Triage) | Unlike a pothole-reporting app, the agent works out *which* authority is responsible, files the complaint through the official channel, watches the SLA, and escalates up to an RTI request. | **75** |

The existing ScholarFlow direction (`HACKATHON_PLAYBOOK.md`) scored **73** and finished 4th. The main reason: **the NSP 2026-27 deadline for most scholarships is today (31 Oct 2026), and One-Time Registration requires Aadhaar face authentication**, so a live end-to-end agent demo on NSP is very hard to pull off now. Details are in [02-longlist-and-scoring.md](02-longlist-and-scoring.md#why-scholarflow-dropped-to-4).

**Recommendation:** Build **#1, FasalSaakshi**, unless the team's answers to the [open questions](06-recommendation-and-open-questions.md#open-questions-for-the-team) point to #2. The reasoning is in [06](06-recommendation-and-open-questions.md).

## Documents

| # | File | What it covers |
|---|---|---|
| 01 | [01-competition-analysis.md](01-competition-analysis.md) | Rules, rubric maths, what the judges reward, the audience-award mechanics, disqualification traps, timing facts |
| 02 | [02-longlist-and-scoring.md](02-longlist-and-scoring.md) | Scoring method, 11 candidate ideas, weighted matrix, why each idea was cut |
| 03 | [03-idea-1-fasalsaakshi.md](03-idea-1-fasalsaakshi.md) | Deep dive on #1: problem evidence, the gap, USP, agent design, architecture, verified data, demo script, risks |
| 04 | [04-idea-2-traceback.md](04-idea-2-traceback.md) | Deep dive on #2 |
| 05 | [05-idea-3-nigrani.md](05-idea-3-nigrani.md) | Deep dive on #3 |
| 06 | [06-recommendation-and-open-questions.md](06-recommendation-and-open-questions.md) | Final pick, decision rules, questions only the team can answer |
| 07 | [07-sources.md](07-sources.md) | Every source used, plus the live API checks run on 31 Oct 2026 |

## How to read the evidence

- **Verified live** means we called the API or feed from our build container on 31 Oct 2026 and got real data back.
- Statistics come from parliamentary answers, PIB, or named news outlets. Where only a secondary or vendor source was available, the doc says so. Don't put a caveated number on a pitch slide without checking it first.
- Product names are provisional.
