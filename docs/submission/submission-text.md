# Submission form text

**For:** whoever fills in the organisers' form. Paste as is. Sources for every external number are in `docs/submission/facts.md`.

**Theme:** Theme 2 · Problem 2 (Climate, Resource Infrastructure & Global Supply Resilience; Predictive Climate & Micro-Location Yield Engine)

**Project:** FasalSaakshi (फसल साक्षी, "crop witness")

## Problem statement

### Target issue

Under PMFBY, India's crop insurance scheme, a farmer hit by a loss usually has no evidence of their own about what happened to their field.

Different losses take different routes. Yield under basic cover is worked out at area level, and YES-TECH estimates yield at Gram Panchayat level (Operational Guidelines 2023, para 2.17). For individual-farm covers (localized and post-harvest), where the State has notified them, the rule asks for intimation within 72 hours, and many farmers don't know it. A joint survey follows, or a sample of 10 parcels if the unit is above 25% under intimation (para 21.5.8).

Farmers can contest, but they have no evidence of their own to contest with.

### Context

- "More than 92.46 crore farmer applications have been insured" since Kharif 2016 (PIB, 29 Aug 2026).
- ₹4,107.47 crore of claims from 2020-21 to 2024-25 were pending as on 31.12.2025 (Lok Sabha Q662, 3 Feb 2026). The official reasons are mainly State share, bank data and yield disputes. 74% of that is in Andhra Pradesh (our arithmetic).
- In 2025, Bhiwani and Charkhi Dadri farmers sat on dharna from 16 July. They say satellite-based yield cut about ₹350 crore from CCE-based claims (The Tribune, Aug 2025).
- Cyclone Arnab hit coastal Andhra Pradesh on 28 Oct 2026 (IMD). About 3.51 lakh hectares of crops damaged, per the Andhra Pradesh Agriculture Minister's preliminary assessment (29 Oct 2026).

### Target audience

PMFBY-insured farmers, including marginal, tenant and loanee farmers, and those who help them: bank staff, agriculture officers, FPOs and KVKs. Of farmer applications in 2024-25, 17.6% were marginal, 6.5% tenant and 48% loanee (PIB, 25 Jul 2025).

## Solution description

### Overview

FasalSaakshi gives a farmer's field its own satellite evidence, which anyone can recompute. We did not find a farmer-side tool that gives a field its own placebo-tested satellite evidence and lets anyone recompute it.

A farmer reports a loss in Hindi, Telugu or English and outlines the field. An agent then investigates:

1. **Checks its data.** It rejects bad scenes, including one with about 0% metadata cloud and impossible reflectance, and switches to radar when optical fails.
2. **Asks two questions.** Did this field change more than comparable fields outside the storm area? Did it change more than its neighbours? Both are placebo tests on same-shape pseudo-plots.
3. **Faces cross-examination.** A hostile surveyor raises nine objections, such as harvest, wrong date and cloud. Each is answered by a test on real values, and the agent can concede.
4. **Gives a verdict from a fixed rubric.** It says "consistent with", and it can say "your field doesn't show this". Corroboration is the weather model or a matching official alert. News never changes a level, and a report with neither stays weak. A deciding p-value from 0.01 to 0.075 is marked as near the threshold.
5. **Finds the route.** It works out which PMFBY route applies, with cited clauses. A 72-hour countdown shows only where that rule applies. It drafts an intimation for the farmer to send. Nothing is filed for them.
6. **Seals the evidence.** The PDF carries a QR code to a public page that re-downloads the same scenes and recomputes the satellite numbers. The verdict and weather are checked for tampering only.

Three exhibits make this readable: The Field Testifies (the evidence told by the field, with its caveats), The Vanishing (our illustration of how a change averages out at coarser scales, not YES-TECH output), and The Ten-Field Draw (para 21.5.8's 10-parcel sample simulated on real pixels). We did not find a published simulation of the guidelines' 10-parcel localized survey.

**What we measured, and what we didn't.** There is no plot-level ground truth for any event here, so this shows consistency, not accuracy.

- **Design event.** On the hail of 2-3 March 2024 in Bhiwani, a coherent band consistent with a hail swath appears and doesn't repeat in other years. Radar does not confirm it. The most dramatic plot is the strongest of 200 scanned. A typical plot, the median of the original 40, is weak and near the threshold. Sensitivity via the field-signal test is shown only on this event.
- **False alarms.** With rules frozen in advance, field conditions fired on 2.0% (strong) and 2.5% (moderate) of plots on two no-event windows. Each is one scene pair with correlated plots, so the confidence intervals are too narrow.
- **Independent hail event.** Sirsa, 14 Mar 2025: 0 of 200. Damage was reported as "minor", so this is consistent but isn't a pass, as we can't tell little damage from a miss.
- **Punjab floods, pre-registered: partial.** New water passes, at 28.3% of plots against 0.0% in the control year. The radar placebo fails, at 1.7% against 8.3%. The two years' pass timing differs, and one site of three shows almost nothing.
- **Seed sensitivity.** Clear cases are stable. Near the 0.025 threshold, the level flips on up to a third of seeds, which is why those results carry a caveat.
- **Cyclone Arnab.** No signal established. The strongest of 51 usable plots fell -0.34 in 5 days and is weak, but the crop was days from harvest, and a later pass will help.

An insurer may decline this evidence, as no clause provides for it. Details are in the repo's `docs/validation/engine-results.md`.

### How Gen AI is used

Gemini understands, explains and questions. Code measures and decides. A model can't talk the verdict up.

- **Understands the report:** Hindi, Telugu and Hinglish voice or text into structured facts, with a clarifying question when it's ambiguous.
- **Ask the witness:** answers a farmer's question about their own result, grounded only in that case's record and cited clauses. Answers must cite what they used and pass digit and phrase checks, and it refuses what the record doesn't cover.
- **Contradiction question:** asks when the statement and evidence don't fit. It changes nothing by itself.
- **Second opinion on images:** advisory only, and never fed to the rubric. A disagreement shows as "needs a person to look".
- **Speech and related reports:** testimony read aloud, and grounded search for related reports, which never change a level.

The verdict stays off the LLM because the same evidence has to give the same level, and a sealed result has to be reproducible. None of this has been run against the real API yet: `TODO(gemini)`.

### Technical architecture

**One container:** FastAPI serves the built Vite + React (MapLibre) app and the API from one URL. SQLite by default, Postgres through `DATABASE_URL`.

**Agent:** branching is an explicit LangGraph state graph, with real conditional edges and a tool budget: parse, plot, context, optical search and QA, optical comparison or radar switch, history, cross-examination (which can loop back to search), verdict, policy, action, explanation, exhibits, seal. Every step is streamed as a trace over SSE. The verdict does not wait for slower exhibits, which fill in after it.

**Geo engine (shapely, rasterio, numpy):** windowed reads of Sentinel-2 L2A and Sentinel-1 RTC from Microsoft Planetary Computer, with Earth Search as a Sentinel-2 fallback. Placebo tests in a near ring and a 5-12 km annulus, rubric v3 (0.025 on either test, Bonferroni).

**Other data:** Open-Meteo with NASA POWER as fallback, NDMA SACHET alerts, and a cited clause corpus from PMFBY Operational Guidelines 2023.

**LLM optional:** the verdict, cross-examination and testimony text are deterministic, so the same evidence gives the same level with or without an LLM. Each Gemini feature falls back to fixed text or a clear "not available" state. Its output is stored outside the sealed core.

**Verification:** a SHA-256 hash over the polygon, scene ids, archives, seed, engine version, numbers, and a digest of the verdict and weather. Public recomputation reads satellite numbers fresh from the archive, with caches bypassed. Independent runs from a clean database produced identical hashes.

## Links

| Item | Value |
|---|---|
| Prototype | https://exercise-instance-promptly-proxy.trycloudflare.com |
| Demo video | https://drive.google.com/file/d/1Tt_5LF6CzvONoBqgDpttNTY_Go2xSDd1/view?usp=sharing |
| Repository | https://github.com/AnirudhSinghRajora/Forge |
| Deck | Team to add a link with view access |
