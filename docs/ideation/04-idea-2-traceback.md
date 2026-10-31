# 04 — Idea #2: TraceBack: provenance-first misinformation & scheme-scam verifier

> **Forward anything suspicious: a video, voice note, screenshot, link or APK. An investigator agent traces where it came from, checks it against official sources, and sends back a verdict with evidence and a forwardable debunk card in your language.**

**Theme 1 · Problem 4** (Real-Time Fact-Verification & Deepfake Audit Engine). Also covers **Problem 1** by explaining the *real* scheme when a fake one is caught.

---

## 1. The problem

### Evidence of demand, this week and this year
| Evidence | Source |
|---|---|
| **31 Oct 2026 (today):** PIB Fact Check debunked a widely shared **AI-manipulated video of Defence Minister Rajnath Singh** on India–China border tensions | IANS / Newsmobile |
| **26–27 Oct 2026:** fake videos claiming China took control of areas in Arunachal Pradesh. The Army clarified one clip showed authorised trade vehicles at Nathu La. Hive flagged another as likely AI-generated. | Newschecker / IANS |
| Early Oct 2026: a sexual deepfake of actors Janhvi Kapoor and Jr NTR spread on X | Outlook India |
| **McAfee, Feb 2026:** 1 in 5 Indians say they've encountered a voice-clone scam; more than 1 in 3 aren't confident they can identify a deepfake scam | McAfee press release |
| **Fake PM-Kisan APK scams:** WhatsApp APKs ("PM KISAN YOJNA v12.apk") hijack the victim's WhatsApp and spread to every contact. A Hyderabad man lost ₹1.95 lakh. Nagaland and Tamil Nadu police issued alerts. PIB also flagged fake "RBI" APKs. | Telangana Today, NewsOnAir, Digit, Deccan Chronicle |
| Fake scheme "bonuses" (e.g. an extra ₹4,000 PM-Kisan instalment, reportedly spread with an AI video) | CareerIndia |
| **IT Rules amendment (G.S.R. 120(E), in force 20 Feb 2026):** mandatory labelling of synthetic content, 3-hour takedown on government/court orders, 2 hours for non-consensual intimate imagery | MediaNama, Hogan Lovells, Freshfields |

### The insight that shapes the product
The Deepfakes Analysis Unit (Misinformation Combat Alliance) found that of media sent to its tipline, **only 2% were deepfakes**. 3% were AI-generated but not deepfakes, **9% were manipulated media** (cheapfakes), and **55% was spam** (2024 report).

So **most harmful content isn't a deepfake**. It's old footage with a new caption, edited clips, fake schemes, and malicious links. A team that builds only "deepfake classifier → % fake" is solving the 2% case, and with unreliable detectors at that. Independent 2026 tests found wide performance gaps, and English-centric datasets miss Indian-language audio. **TraceBack leads with provenance and official sources, and treats detector scores as one weak signal among many.** That's our differentiation from the many "fake news detector" submissions we expect.

### Who is affected
WhatsApp-first Indian users: hundreds of millions, especially older and first-time internet users and regional-language speakers. Secondary users are district administrations, police cyber cells, newsrooms and fact-checkers, who need **trend radar**: which claims are spreading, where, and in what language.

---

## 2. Existing solutions and the gap

| Existing | Gap |
|---|---|
| **DAU WhatsApp tipline** (MCA + Meta, since Mar 2024; EN/HI/TA/TE) | Human-assessed, deepfake-focused, slow turnaround, few languages |
| **PIB Fact Check**, BOOM, Alt News, Newschecker, Factly | Human, so it doesn't scale to the long tail. The user must go and *look for* the fact-check. |
| **Vastav AI** (Zero Defend / TraceX Labs, Mar 2025) | Enterprise/law-enforcement deepfake detection. Not citizen-facing, no provenance or scheme checks. |
| SynthID Detector, OpenAI's verifier, C2PA viewers | Only catch content from tools that embed watermarks or credentials. Open-source models carry none. |
| Truecaller AI voice scanner, VoxShield, and similar | Call-only, vendor claims, narrow scope |

**USP:** an **autonomous investigator** over WhatsApp that (1) traces **provenance**, (2) checks **official registries** for government and scheme claims, (3) analyses **links and APKs**, (4) uses detectors and C2PA/watermark checks as supporting signals, and (5) answers with a **forwardable debunk** in the user's language. That last part closes the loop in the same group where the fake spread.

---

## 3. Solution: the user journey

1. User forwards a suspicious item to the TraceBack WhatsApp number: a video, image, voice note, text, link or APK.
2. TraceBack replies in seconds: "Investigating…", then streams progress.
3. Within about 30–90 s it delivers:
   - **Verdict** on a 4-level scale: *False (with authoritative source)* · *Misleading / out of context* · *Verified true* · *Unverified, insufficient evidence*. Never a bare "% fake".
   - **Evidence trail:** earliest known appearance, original context, official source links, fact-check matches, and detector signals with their caveats.
   - **For scheme claims:** what the *real* scheme says (eligibility, amount, official portal), from the official source. This is Problem 1.
   - **For APKs and links:** "Do not install. Requests SMS + Accessibility permissions, domain registered 3 days ago, flagged by N engines."
   - A **debunk card** (image) and a **voice note** in the user's language, made to be forwarded back into the family group.
4. **Public trend radar** (web): anonymised clusters of incoming claims, showing which are spreading, by language and region, with links to evidence. This is the "public accountability" layer for fact-checkers and district cyber cells.

---

## 4. The agent: investigation as a plan

```
1  ingest(media)          → type detection; ffmpeg keyframes; OCR (incl. Indic scripts); ASR (Indic); language ID
2  extract_claims()       → LLM extracts atomic, checkable claims + entities (person, scheme, place, date)
3  route by claim type:
   ├─ government/scheme   → official registries: myScheme, scheme portals (e.g. pmkisan.gov.in), PIB releases,
   │                         eGazette; "does this scheme / amount / date exist?"
   ├─ news event          → news search (GDELT, publisher sites), PIB Fact Check, Google Fact Check Tools (ClaimReview)
   ├─ media origin        → reverse image/keyframe search → earliest appearance; compare dates/locations (miscontext)
   ├─ link / APK          → URL expansion, domain age (WHOIS), VirusTotal reputation, static APK permission analysis
   └─ synthetic media     → C2PA/content-credentials check; watermark checks where APIs allow;
                             open detectors (image/video/audio) as a *weak* signal
4  reconcile()            → evidence graph: each claim ← supporting/refuting evidence with source + timestamp
5  self_check()           → a verdict needs ≥1 authoritative source or ≥2 independent signals;
                             otherwise the agent searches again with reformulated queries, or downgrades to "Unverified"
6  compose()              → verdict + citations + regional-language voice/text + debunk card
7  cluster()              → embed the claim; join an existing cluster (instant answer for repeats) or open a new one
```

Agentic highlights for judges: **claim-type routing**, **iterative query reformulation** when the first search fails, **evidence thresholds** before any verdict, **caching and clustering** so the 1,000th forward of a viral fake gets an instant cited answer, and **source attribution** on every line.

---

## 5. Technical architecture (indicative)

| Layer | Choice (suggested) |
|---|---|
| Channel | WhatsApp Cloud API (Meta test number) + web upload page |
| Media | ffmpeg (keyframes, audio), Indic OCR (e.g. PaddleOCR / Tesseract Indic packs / multimodal LLM), Indic ASR (IndicWhisper / Sarvam / Bhashini) |
| Reasoning | Multimodal LLM for claim extraction and synthesis; state-graph orchestration with tools |
| Retrieval | Google Fact Check Tools API (free key required; it returned 403 without a key in our test), PIB releases and fact-checks, GDELT DOC API (rate-limited to 1 request per 5 s, so queue it), myScheme/official portals, eGazette |
| Provenance | Reverse image search (e.g. a SerpAPI Google Lens/Bing-style API; check free-tier limits), perceptual hashing for internal dedupe |
| Security | VirusTotal API (free tier), WHOIS/RDAP, androguard (static APK analysis only, never executed) |
| Synthetic signals | `c2pa` libraries for content credentials; open-source image/audio deepfake detectors as weak signals |
| Store | Postgres + pgvector (claim clusters), object storage |
| Output | Server-side rendered debunk card (PNG), TTS voice note, public trend-radar dashboard |

---

## 6. Data sources: status on 31 Oct 2026

| Source | Status |
|---|---|
| Google Fact Check Tools API | Reachable; **needs a free API key** (403 without one) |
| GDELT DOC API | Reachable; **rate limit: 1 request per 5 s** (we got a 429), so queue and cache |
| PIB Fact Check | Website reachable (redirects); scrape releases or monitor PIB channels |
| Reverse image search | No free official API, so choose a provider and budget for it |
| VirusTotal | Free public API with tight rate limits (not tested here) |

Inputs are always real user forwards, and every verdict cites live sources, so there's **no dummy-data risk**.

---

## 7. Demo script

1. **Hook:** Show today's PIB debunk of the Rajnath Singh video. "PIB took time to debunk this. By then it had been forwarded millions of times."
2. **Live:** Forward three things to TraceBack from a phone mirrored on screen:
   - an old flood video re-captioned as "today" → *Misleading* (earliest appearance found, with date)
   - a fake "PM-Kisan ₹4,000 bonus" message with an APK → *False + dangerous* (official portal check + APK permissions + domain age)
   - a real recent PIB announcement → *Verified true* (shows it doesn't just say "fake")
3. **Self-correction:** a claim where the first search fails, the agent reformulates and finds it, or honestly returns "Unverified".
4. **Judges try their own forwards.**
5. **Trend radar:** clusters forming from the demo traffic, live.

## 8. Rubric mapping

| Pillar | How TraceBack earns it |
|---|---|
| Live Demo (30) | Inputs are real; graceful "Unverified" path; caching. Risk: unknown live inputs can produce wrong verdicts (see risks). |
| Agentic (25) | Strongest of the three: routing, iterative search, thresholds, multi-tool investigation |
| Impact & USP (25) | Huge reach. USP = provenance + official-source + scam focus vs. a deepfake-only classifier. |
| Tech (20) | Multimodal pipeline, evidence graph, clustering, security analysis |
| Audience award | **Best of the three.** Debunk cards are built to be shared, the topic is in the news this week, and the team can post "we caught X" content daily. |

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Wrong verdict live** (credibility-destroying) | 4-level scale with "Unverified" as an honest default; evidence thresholds; always show sources; never let a detector score alone decide a verdict |
| Crowded concept; judges have seen many | Lead the pitch with the **DAU 2% insight** and the provenance + scam focus. Don't open with "deepfake detection". |
| Paid or limited APIs (reverse search, VirusTotal, GDELT) | Budget a small paid tier; cache aggressively; pre-cluster repeated forwards |
| Indic audio deepfake detection is immature | Present audio detection as a weak signal only; lean on provenance |
| Political sensitivity | Neutral sourcing (official sources + IFCN-signatory fact-checkers); show evidence rather than editorialising |
| APK handling safety | Static analysis only, in an isolated worker; never execute; hash-check against VirusTotal first |

## 10. MVP cut for the remaining window

Must-have: WhatsApp intake → OCR/ASR → claim extraction → routing to (official/scheme check, fact-check search, reverse-image provenance, link/APK check) → evidence-threshold verdict → regional-language reply + debunk card. Nice-to-have: trend radar, C2PA checks, audio detectors.
