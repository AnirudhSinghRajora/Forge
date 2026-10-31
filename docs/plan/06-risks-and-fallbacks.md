# 06 — Risks & Pre-decided Fallbacks

These fallbacks are decided now so nobody debates them at 3 am.

| # | Risk | Likelihood | Impact | Early signal | Pre-decided fallback |
|---|---|---|---|---|---|
| R1 | **No clean post-event optical over Sirsa before judging** (28 Oct corrupt; ~2 Nov pass may be cloudy or late) | Medium | Medium | QA result on the 2 Nov scene | Demo T1 with **SAR fallback as the feature** ("satellite data breaks; our agent notices"). Use a documented past event (calibration step 2) with clean optical as the second demo case. |
| R2 | Signal too weak to separate damage from harvest in Sirsa | Medium | High | Calibration results at H14 | Lead with honest confidence levels. Show a documented past event where the anomaly is clear. The value proposition still holds (evidence + deadline + documentation). |
| R3 | Planetary Computer slow or rate-limited during the live demo | Low-Med | High | Latency > 30 s in smoke tests | Scene-QA + context-stat cache, pre-warm demo plots before judging, **Copernicus Data Space** as the backup STAC source (register an account at H0). |
| R4 | Gemini model ID or feature differences (3.x naming, TTS availability, Search-grounding billing) | Medium | Medium | G0 key/model test | Wrap all calls in `llm.py`. Fallback TTS: Google Cloud TTS hi-IN voice. Fallback ASR: text input. |
| R5 | Open-Meteo quota (429 seen on the shared free tier) | Medium | Low | 429 in logs | Paid key + NASA POWER fallback + response cache |
| R6 | WhatsApp Cloud API setup takes too long (Meta app review / test numbers) | High | Low | Not working by H28 | Drop it. The PWA is the channel; mention WhatsApp in the roadmap. |
| R7 | PMFBY intimation fields/channels unclear in the official PDF | Low-Med | Medium | B's H1 reading | Use exactly what the guideline states, cite it. Where unclear, say "confirm with insurer". No invented fields. |
| R8 | Any number in the app without provenance → "dummy data" accusation | Low | **Critical** | Review at G3 | Number-validator + provenance table; remove anything that can't be traced |
| R9 | Over-claiming ("you will get paid", "filed") | Low | High | Copy review at G3 | Copy rules in 01 §4; "consistent with", "prepared", "you submitted" |
| R10 | Scope creep in Phase 3 | High | High | P1 items started before G2 | Gate discipline: no P1 before G2, no P2 before G3 |
| R11 | Deployment breaks at the end | Medium | Critical | — | Deploy continuously from H6; tag a known-good release at every gate; roll back instead of hot-fixing after H38 |
| R12 | A teammate can't explain another layer in Q&A | Medium | High | Gate demos | Each owner demos their layer at every gate; Q&A drill at H36 |
| R13 | Corrupted or odd scenes beyond the 28 Oct type | Medium | Medium | QA rejections in logs | QA Q1–Q5 are generic; log the reasons; never silently accept |
