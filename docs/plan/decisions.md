# Decision Log

| # | Date | Decision | Why | Who |
|---|---|---|---|---|
| D1 | 31 Oct 2026 | Build **FasalSaakshi** (Theme 2 · Problem 2); drop ScholarFlow | Highest score on judge impression / impact / unsolved gap (see docs/ideation). Nothing built for ScholarFlow; NSP deadline + face-auth block its live demo. | Team |
| D2 | 31 Oct 2026 | Gemini (paid) is the LLM/voice provider; no Gemini 2.5 (shut down Oct 2026) | Team has paid access; covers audio, function calling, Search grounding, Hindi TTS | Team |
| D3 | 31 Oct 2026 | Scene radiometric QA is mandatory before any index is used | Spike: 28 Oct 2026 S2 pass is corrupted despite 0% cloud metadata | Plan |
| D4 | 31 Oct 2026 | Verdicts require neighbour comparison (not just before/after) | Spike: normal 2025 harvest dropped Sirsa median NDVI 0.60 → 0.51 in 5 days | Plan |
| D5 | 31 Oct 2026 | Demo language: Hindi | Gemini TTS hi-IN is GA; Punjabi is preview | Plan |
| D6 | 31 Oct 2026 | Plan for submission by 5 PM IST on 1 Nov | Unstop shows both 6 PM and 11:59 PM as the end; assume the earlier | Plan |
| D7 | 31 Oct 2026 | One container (FastAPI + built Vite app); SQLite by default, Postgres via `DATABASE_URL` | Fewer accounts and failure points for a live demo under 24 h out | Plan |
| D8 | 31 Oct 2026 | Placebo p-value over same-shape pseudo-plots replaces pixel percentile | Pixel variance overstates significance; harvest widens the placebo distribution by itself | Plan |
| D9 | 31 Oct 2026 | Weather corroborates when present; its absence never refutes | 25 Oct Sirsa hail reports vs. under 1 mm and no hail codes in gridded models | Plan |
| D10 | 31 Oct 2026 | Primary demo event: Cyclone Arnab (coastal Andhra, landfall near Yanam, late Oct 2026). Telugu added alongside Hindi for farmer-facing output. | Live event with reported crop loss in the state holding most pending PMFBY claims; Godavari farmers speak Telugu, not Hindi. Supersedes D5 for that case. | Plan |
| D11 | 31 Oct 2026 | `PlaceboTest`: added optional `n_non_overlapping`; `placebo_median/p05/p95` may be `None` when `n_placebos` is 0 | Additive. Correlated placements must be reportable, and with zero placements there is no median to state (schema rule: `None` means not measured). | GEO |
| D11 | 31 Oct 2026 | Route each case to a claim path before showing any countdown; 72 h is not universal and "late means rejected" is not in the text | OG 2023 paras 5.5, 21.5.8, 21.5.9.2 | Plan |
| D12 | 31 Oct 2026 | Signature features: Ten-Field Lottery (21.5.8 simulated on real pixels), The Vanishing (scale fade), The Field Testifies. Headline is the lottery. | Derived from the guideline text and real data; no other entry is likely to read the rule this closely. Deliberately limited to three plus cross-examination and replay. | Plan |
| D13 | 31 Oct 2026 | Rename to "The Ten-Field Draw"; lead with Bhiwani/Hisar hail (Mar 2024); label 21.5.8 as illustration-only outside localized and post-harvest routes; soften novelty claims | Research: the rule does not cover standing Godavari paddy, random sampling is unbiased, and nearby products exist | Plan |
