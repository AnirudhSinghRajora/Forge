# FasalSaakshi — Build Plan

**Status:** idea locked on 31 Oct 2026 (see [../ideation](../ideation/README.md)). About 2 days remain to submission. The team is 3 devs with paid Gemini API access.

> **FasalSaakshi (फसल साक्षी, "crop witness"):** a farmer reports crop damage by voice. An agent pulls satellite and weather evidence for *that farmer's plot*, judges whether it really looks like calamity damage (as opposed to normal harvest), explains the verdict in Hindi with every number cited, and makes sure the PMFBY loss intimation goes in before the 72-hour deadline. It then keeps watching the plot and follows up.

## Documents

| # | File | Use it for |
|---|---|---|
| 01 | [01-product-scope.md](01-product-scope.md) | Who it's for, user stories, P0/P1/P2 scope, non-goals, honesty rules |
| 02 | [02-architecture.md](02-architecture.md) | System diagram, tech stack decisions, repo layout, API contracts, data model, agent graph, Gemini usage, deployment |
| 03 | [03-evidence-engine.md](03-evidence-engine.md) | **The core algorithm:** scene QA, indices, pre/post selection, neighbour and history baselines, harvest discrimination, SAR, confidence rubric, plus the spike findings |
| 04 | [04-build-timeline.md](04-build-timeline.md) | Hour-by-hour plan for 3 owners, gates, integration points, sleep rotation |
| 05 | [05-demo-and-submission.md](05-demo-and-submission.md) | Demo script, test matrix, judge Q&A prep, submission checklist, deck outline, draft submission text |
| 06 | [06-risks-and-fallbacks.md](06-risks-and-fallbacks.md) | Risk register with pre-decided fallbacks |
| — | [`/spikes`](../../spikes) | The 31 Oct feasibility scripts (Sentinel-2/1 over Sirsa & Fatehabad) |

## Five things everyone must know before writing code

1. **Metadata lies.** The 28 Oct 2026 Sentinel-2 pass over Sirsa/Fatehabad claims 0% cloud, but its pixel data is corrupted. **Every scene goes through radiometric QA before use** ([03 §2](03-evidence-engine.md#2-scene-quality-assurance-mandatory)).
2. **Harvest ≠ damage.** Late October is paddy harvest season. In 2025, Sirsa's median NDVI fell 0.60 → 0.51 in 5 days from normal harvesting. **A verdict is never based on before/after alone. It always compares against neighbours and the plot's own history** ([03 §5–6](03-evidence-engine.md#5-neighbour-comparison-the-key-discriminator)).
3. **No dummy data, ever.** Every number shown must come from a live API or a real user input, with provenance attached. No seeded cases, no fixture JSON in the running app.
4. **Never claim what didn't happen.** The agent *prepares and tracks* the intimation. It only says "filed" when the farmer confirms submission with a reference number.
5. **Everyone can explain everything.** Each owner demos their layer to the other two at every gate.

## Owners (assign names at kickoff)

| Owner | Layer |
|---|---|
| **A: Geo** | Evidence engine: STAC search, scene QA, indices, baselines, SAR, image chips |
| **B: Agent** | Backend + agent: FastAPI, LangGraph investigation graph, Gemini tools, weather/alerts/news, policy RAG, actions, scheduler, DB |
| **C: Experience** | Web app + channel: map & polygon drawing, live agent trace, voice in/out, evidence pack PDF, WhatsApp (P1), deploys, demo video |

The process sections of `HACKATHON_PLAYBOOK.md` (checkpoints, handoffs, decision records) still apply. Its ScholarFlow-specific content is superseded by this plan.
