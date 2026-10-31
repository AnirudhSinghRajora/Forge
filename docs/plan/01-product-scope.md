# 01 — Product Scope

> **Superseded in part.** This file is an early working draft and some claims here were later corrected against the official guidelines and real data. For current facts see [`docs/submission/facts.md`](../submission/facts.md), and for the current design see [`docs/plan/07-build-contract.md`](07-build-contract.md).

## 1. Users

| Persona | Situation | What they need from us |
|---|---|---|
| **Small/marginal farmer** (primary): e.g. a paddy or cotton grower in Sirsa, 1–5 acres, PMFBY-insured through a KCC loan, Hindi/Haryanvi speaker, uses WhatsApp | Hail or unseasonal rain hit their field. They don't know about the 72-hour rule, or what to say. Village-level assessment may average their loss away. | A plain-language answer to "is my loss visible, and what do I do now?", evidence they can show anyone, and a reminder before the deadline |
| **FPO / KVK volunteer or agri-officer** (secondary) | Handles many farmers after a local event | Batch view of cases, evidence packs, deadlines |

The demo runs in **Hindi** (Gemini TTS: hi-IN is GA; Punjabi is still in preview).

## 2. Core user stories

| ID | Story | Priority |
|---|---|---|
| US1 | As a farmer, I record a voice note ("ओले गिरे, कपास खराब हो गई") and share my field location, so I don't have to type. | **P0** |
| US2 | As a farmer, I mark my field on a map (draw it, or tap and confirm a suggested boundary). | **P0** (draw) / P1 (suggested boundary) |
| US3 | As a farmer, I watch the agent investigate step by step, so I trust the result. | **P0** |
| US4 | As a farmer, I get a verdict with a confidence level, before/after images of *my* field, and a comparison with neighbouring fields, all explained in Hindi voice and text. | **P0** |
| US5 | As a farmer, I get a pre-filled PMFBY loss intimation and a live 72-hour countdown, with one-tap ways to submit (call 14447, share, download). | **P0** |
| US6 | As a farmer, I record my submission reference number, and the agent tracks the case. | **P0** |
| US7 | As a farmer, I download an evidence-pack PDF (images, charts, weather, citations, policy clauses). | **P0** |
| US8 | As a farmer, I'm told when a new satellite pass updates my evidence. | **P1** (scheduled re-check) |
| US9 | As a farmer whose claim stalled or was rejected, I get a drafted grievance citing the guideline clause and my evidence. | **P1** |
| US10 | As a farmer, I can do all of this on WhatsApp. | **P1** |
| US11 | As an FPO/officer, I see all cases on a map with deadlines and confidence. | **P2** |
| US12 | As a farmer, I can ask policy questions ("क्या post-harvest नुकसान कवर है?") and get cited answers. | **P1** |

## 3. Scope

### P0: must ship (the demo depends on it)
- Web app (mobile-first PWA): voice note recording, location pin, polygon drawing
- Investigation agent with a visible step trace: parse report → plot → weather → optical scenes (with QA) → SAR fallback → neighbour + history comparison → self-check → verdict
- Before/after image chips and NDVI chips, plus neighbour comparison chart
- Confidence rubric verdict with full provenance
- Hindi voice summary (TTS) + text
- PMFBY intimation draft + 72-hour deadline countdown + "record my reference number"
- Evidence-pack PDF
- Policy RAG over the PMFBY operational guidelines (cited clauses)
- Deployed backend + frontend, reachable by judges

### P1: ship if the gates are green
- Scheduled re-check of open cases when new passes land (**watch for the ~2 Nov Sentinel-2 pass over Sirsa**)
- News corroboration via Gemini Google Search grounding
- Grievance draft
- WhatsApp channel (Meta Cloud API test number)
- Suggested field boundary from imagery
- SACHET alert archiver (starts collecting real alert history from day 1)

### P2: only if everything else is done
- FPO/officer case map dashboard
- Multi-language beyond Hindi
- Gemini visual "second opinion" on image chips

### Non-goals (say so if asked)
- We do **not** decide or predict claim payouts. We provide evidence.
- We do **not** auto-submit on government or insurer systems without the farmer's action. There's no public API, and we won't fake one.
- We do **not** collect Aadhaar or bank credentials.
- We do **not** replace CCEs or YES-TECH. We give the individual farmer a plot-level voice in that process.

## 4. Honesty rules (product-level)
1. Every number on screen is traceable to its source: scene ID + date, API + timestamp, or clause ID.
2. "Insufficient evidence" is a first-class outcome, not a failure.
3. Corrupted, cloudy, or missing data is shown as such, never smoothed over.
4. "Filed" appears only after farmer confirmation with a reference number.
5. Demo users are real people (team members or consenting farmers) entering their own details. No invented farmer profiles.
