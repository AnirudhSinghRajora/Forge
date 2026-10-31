# 05 — Idea #3: Nigrani (निगरानी, "oversight"): the civic accountability agent

> **A reporting app sends your complaint off and that's the end of it. Nigrani works out who is responsible, files the complaint through the official channel, watches the deadline, and escalates when it's missed, all the way to an RTI request.**

**Theme 1 · Problem 2** (Transparent Civic Grievance & Infrastructure Triage System).

---

## 1. The problem

Filing a complaint is easy. **Getting it resolved isn't.** Citizens don't know *which* authority owns a road: municipal ward, state PWD, or NHAI. Complaints get closed without action, and nobody follows up.

| Evidence | Source |
|---|---|
| CPGRAMS feedback: **46% of citizens dissatisfied** with the outcome after "resolution" (Aug 2025), **37%** (Nov 2025) | DARPG monthly reports via PIB |
| States/UTs pendency on CPGRAMS: **1,92,877** (Feb 2026) | DARPG / PIB |
| DARPG circular (2025) allows closure when the officer "cannot obtain information despite best efforts" | DARPG circular |
| **Karnataka HC (Aug 2026)** sought a detailed affidavit from the Greater Bengaluru Authority on pothole identification and repair, plus FIR details for pothole deaths. GBA said 10,202 potholes were closed since Apr 2026. | LiveLaw, Siasat |
| Residents report complaints on the city app still unaddressed | The South First, Deccan Herald |
| Bengaluru tops NCRB civic-negligence deaths among cities (17 in 2024) | ThePrint (NCRB) |
| National pothole deaths reportedly **up 53% in 5 years, around 9,400 fatalities** | Deccan Herald headline, Feb 2026 (*only the headline was seen, so verify before using*) |

## 2. Existing solutions and the gap

| Existing | Gap |
|---|---|
| CPGRAMS, city apps (e.g. GBA/BBMP), Swachhata, NHAI Rajmargyatra | Siloed. The citizen must pick the right channel, and there's no cross-channel follow-up or escalation. |
| FixMyStreet-style / I Change My City / Reap Benefit | Reporting and community, with little or no automated escalation through legal instruments |
| Many hackathon pothole-detector apps | Detection plus a map. They stop at "reported". |

**USP:** *the agent that never forgets a complaint.* Jurisdiction resolution, official filing, SLA watch, an escalation ladder (officer → senior officer → CPGRAMS appeal → RTI under Section 6, Section 7 timelines), and an evidence file that could support legal action (e.g. the Karnataka HC context).

## 3. User journey

1. Citizen sends a photo, video or voice note (any language) plus location on WhatsApp or the web.
2. **Triage:** a vision model scores severity (size, depth cues, traffic exposure, proximity to a school or hospital from OSM). The agent geo-deduplicates against existing open cases (H3 cells), and duplicate reports are merged and *add weight*.
3. **Jurisdiction resolution:** an OSM road ref (NH/SH) plus ward boundaries from open data and agency directories give the responsible body and officer.
4. **Filing:** through the official channel (city portal or CPGRAMS, with browser automation where permitted, plus a human confirmation step) and/or a public post tagging the official handle. The acknowledgment number is stored.
5. **Watch:** an SLA timer per channel. The agent rechecks status on the portal and asks the reporter for a "still there?" photo.
6. **Escalate:** on an SLA breach, it escalates to the next level. On closure without a fix, it files an appeal. As a last resort, it **drafts an RTI** asking for action taken, budget, and contractor details for that stretch.
7. **Public dashboard:** open and closed cases by ward and authority, median time-to-fix, "closed but not fixed" rate. This is the accountability layer the problem statement asks for.

## 4. Agentic core

Planner over the tools: `classify_issue` → `score_severity` → `dedupe_cluster` → `resolve_jurisdiction` → `file_complaint` → `schedule_check` → `check_status` → `escalate`/`draft_rti` → `notify_reporter`. Self-correction: if a jurisdiction is ambiguous, ask a clarifying question or use the road-ref fallback. If filing fails because of a captcha or portal outage, queue a retry and hand over to the human with prefilled data.

## 5. Architecture (indicative)

WhatsApp Cloud API / PWA · multimodal LLM + fine-tuned or few-shot vision severity · PostGIS + H3 · OSM (Overpass) for road refs and POIs · open ward boundaries (city open-data portals, e.g. OpenCity) · Playwright/browser-use for portal filing with human-in-the-loop · scheduler · RTI template engine with RAG over the RTI Act · public dashboard.

## 6. Data and compliance

All case data comes from **real reports**. The team must collect real reports during the event (e.g. 30–50 from their campus or city). Seeding fake cases would be a disqualification risk. Road and ward data come from OSM and official open-data portals.

## 7. Rubric mapping and risks

| Pillar | Assessment |
|---|---|
| Live demo (30) | Good for intake, triage and dashboard. **Filing on real government portals during judging carries captcha and OTP risk**, so keep a human-confirm step. SLA escalation can't be shown in real time, so show cases filed on day 1 of the event. |
| Agentic (25) | Good: multi-step, stateful over days |
| Impact & USP (25) | High impact. USP vs crowd is moderate: **judges will likely see several pothole apps**, so lead the pitch with escalation and RTI, not detection. |
| Tech (20) | Medium-high |
| Audience award | Very high: everybody hates potholes, and before/after "fixed because of Nigrani" posts spread |

Key risks: the concept looks crowded at first glance; real-portal automation is fragile; demonstrating "escalation over time" within 48 hours; misrouting. Mitigations: lead with the accountability ladder; human-in-loop filing; transparent jurisdiction reasoning shown to the user.

## 8. MVP cut

Must-have: multimodal intake → severity + dedupe → jurisdiction resolution → prefilled official complaint (human-confirmed filing) → SLA tracker → escalation/RTI draft → public dashboard with real reports.
