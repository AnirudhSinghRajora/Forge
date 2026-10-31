# Verified events for demos and engine validation

Researched 31 Oct 2026 by RESEARCH. Copies of sources are in `backend/data/policy/raw/`. Rule citations are in `backend/data/policy/key_rules.json`.

## How the coordinates were checked

- **Village point:** OpenStreetMap, through Nominatim or Overpass. A match to a different spelling is marked "variant"; those are our inference.
- **Cropland point:** the nearest location at least 300 m from the village point that sits inside a 90 m block of ESA WorldCover 2021 v200 class 40 (cropland). "Crop share" is the share of cropland in a box about 4 km across.
- **What this does not prove:** that the point is the reported crop, that it was damaged, or whose field it is. WorldCover is from 2021 and sees no crop type. **GEO must look at the imagery before using any point.**

## Which events are patchy (where the 10-parcel spread matters)

| Event | Patchy? | Evidence | Use for the 21.5.8 simulation? |
|---|---|---|---|
| Sirsa hail, 14 Mar 2025 | **Yes, strongly** | "While some villages received minimal rainfall, others experienced heavy hailstorms lasting about five minutes" | Best documented patchiness. But the same report calls damage "minor" |
| Bhiwani and Hisar hail, 2-3 Mar 2024 | **Yes, with official numbers** | Agriculture Department damage bins range from below 25% to above 76% within a district (section C1) | **Best overall**, as an illustration. See the insurance caveat there |
| Hisar hail, 31 Mar 2026 | Yes | "there is no major impact in areas where the size of hails is tiny" | Weak: wheat "fully ripe" |
| Fatehabad hail, 27 Dec 2024 | Yes | Named village list; 15 villages in Hisar | Hard case: young crop, and experts call the rain beneficial |
| Sirsa and Fatehabad hail, 24 Oct 2026 | Probably | "several villages"; no measure of variation found | Honest hard case only |
| Punjab floods, Aug-Sep 2025 | **Sharp edges** | Breach-driven; "enormous devastation in Ghonewal and adjoining Machhiwal" (Tribune, search excerpt) | Good for edges, but this is widespread flooding, and paddy is excluded from localized inundation |
| **Cyclone Arnab** | **Not shown at village level** | District shares only (A6). We found no report comparing neighbouring villages or mandals | **Not on the rule's text for standing paddy** (A7). Label as hypothetical |

## A. Cyclone Arnab, October 2026

### A1. Landfall: VERIFIED from IMD

[IMD National Bulletin No. 25](https://mausam.imd.gov.in/Forecast/marquee_data/25.%20National%20Bulletin%20No%2025-28Oct2026_0830IST.pdf), issued 1200 IST, 28 Oct 2026:

> crossed Andhra Pradesh & Yanam coasts between Bapatla and Visakhapatnam to the Southwest of Yanam near latitude 16.450N and 81.90E, about 20 km east-northeast of Narsapur, 40 km southwest of Yanam and 60 km southwest of Kakinada during 0200 - 0800 hours IST of today, the 28th October, 2026 as a very severe cyclonic storm with the maximum sustained wind speed of 125-135 kmph gusting to 150 kmph. Latest observations indicate that the landfall process completed with the central region moving completely into land by 0800 hrs IST.

- **Time and place:** 0200-0800 IST, Wednesday 28 Oct 2026, near 16.45 N, 81.90 E. The stated distance to Narsapur matches our map check (about 21 km).
- **Start of process:** [Akashvani](https://newsonair.gov.in/cyclone-arnab-makes-landfall-along-andhra-pradesh-and-yanam-coasts-near-kakinada-several-states-witnessing-heavy-rainfall/) quotes IMD as saying it began at 1:20 AM. This differs from the bulletin's 0200. Use 0200-0800 and cite the bulletin.
- **Plan correction:** "landfall near Yanam" (decision D10) is loose. It was about 40 km southwest of Yanam and 20 km from Narsapur, in West Godavari.

### A2. Track

| Time (IST) | Position | Status | Source |
|---|---|---|---|
| 24-26 Oct | Depression 24 Oct, deep depression 25 Oct, named cyclonic storm 26 Oct | Formation | [Wikipedia](https://en.wikipedia.org/wiki/Cyclone_Arnab), citing IMD. SECONDARY |
| 28 Oct 0830 | 16.5 N, 81.9 E | Severe cyclonic storm, 110-120 gusting 130 | IMD NB25, VERIFIED |
| 28 Oct 2330 | 17.8 N, 81.8 E | Deep depression, 50-60 gusting 70 | [IMD NB30](https://mausam.imd.gov.in/Forecast/marquee_data/30.%20National%20Bulletin%20No%2030-28Oct2026_2330IST.pdf), VERIFIED |
| 29 Oct 0530 (forecast) | 18.6 N, 81.9 E | Depression | IMD NB30 |
| 29 Oct 1730 (forecast) | 20.5 N, 82.1 E | Well marked low | IMD NB30 |

The system moved nearly north after landfall, into south Chhattisgarh and south Odisha. Wikipedia reports damage in Odisha too (Ganjam, Gajapati, Kandhamal); we did not verify that.

### A3. Crop figures, in time order

These are all preliminary, and all are press reports of officials unless marked. We did not find a State press note. **The "conflict" is mostly assessments growing over time plus a change of units, not a real disagreement on scale.**

| When | Figure | Who said it | Source |
|---|---|---|---|
| 28 Oct | Over 70,000 ha paddy, over 10,000 ha horticulture | CM Naidu, to Amit Shah and at a review | [Akashvani](https://newsonair.gov.in/cyclone-arnab-damages-over-80000-hectares-of-crops-in-andhra-pradesh/); [ETV Bharat](https://www.etvbharat.com/en/bharat/cyclone-arnab-update-deavstation-in-andhra-pradesh-casualties-odisha-rain-enn26102900680) |
| 28 Oct | **2,24,489 ha**, 14 districts, about 3.45 lakh farmers. 154 mandals; 2,11,726 ha agriculture, of which **2,09,460 ha paddy**; 12,763 ha horticulture | Agriculture Minister K Atchannaidu, letter to Union Minister Chouhan | [Daily Pioneer](https://dailypioneer.com/india/andhra-pradesh-seeks-advance-central-funds-as-cyclone-arnab-flattens-224-lakh-hectares); [Deccan Chronicle](https://www.deccanchronicle.com/southern-states/andhra-pradesh/cyclone-arnab-claims-9-lives-devastates-crops-in-14-ap-dists-1999772) |
| 29 Oct | **3,51,662 ha** in the lead; 3,51,962.60 ha later in the same report. Horticulture 22,457.75 ha, 77,431 farmers. Aquaculture Rs 176.82 crore | Atchannaidu, review meeting | [UNI](https://www.uniindia.com/south-india/admin-ap-cyclone-crop-loss/229976) (paywalled after the opening) |
| 29 Oct | Paddy "around 3.45 lakh hectares" | Attributed to Atchannaidu | [Gulte](https://www.gulte.com/political-news/438842/cyclone-arnab-aftermath-governments-relief-recovery-plan). **Treat with care:** the earlier 3.45 lakh figure was farmers, and the UNI text we can read does not state this |
| 29 Oct | 3.25 lakh ha in 2,727 villages of 249 mandals; also 3.04 lakh ha in 16 districts | Unattributed; two numbers in one report | [ETV Bharat](https://www.etvbharat.com/en/bharat/cyclone-arnab-damages-standing-crops-across-several-areas-in-andhra-pradesh-enn26102903906) |
| 30 Oct | **5.36 lakh acres** of paddy "fell flat" in Kakinada, Konaseema, Eluru, East and West Godavari; over 2.80 lakh farmers | Reporter, with agriculture officers | [Deccan Chronicle](https://www.deccanchronicle.com/southern-states/andhra-pradesh/harvest-season-pushes-farmers-into-distress-536-lakh-acres-of-paddy-damaged-2000099) |
| 31 Oct | "nearly 4.10 lakh hectares of crops across 16 districts" | Unattributed | [Deccan Chronicle](https://www.deccanchronicle.com/southern-states/andhra-pradesh/cm-naidus-crop-insurance-policy-to-provide-financial-security-to-farmers-2000460) |

**Units reconcile.** 5.36 lakh acres is about 2.17 lakh ha, close to the 2.09 lakh ha of paddy in the 28 Oct letter. Konaseema's "1.16 lakh acres" ([Hans India](https://www.thehansindia.com/news/cities/amaravati/cyclone-leaves-farmers-staring-at-ruined-harvests-1137256)) is about 46,900 ha, close to the official 44,232-48,449 ha.

**District figures moved:**

| District | 28 Oct letter (ha) | 29 Oct ETV (ha) |
|---|---|---|
| West Godavari | 76,176 | 74,175 |
| Konaseema | 44,232 | 48,449 |
| Kakinada | 42,222 | 50,993 |
| East Godavari | 29,866 | 42,635 |
| Krishna | 22,339 | 40,141 |

**Not a crop figure:** ₹4,600 crore is the CM's preliminary estimate of all losses ([Daily Pioneer](https://dailypioneer.com/india/cyclone-arnab-leaves-7-dead-causes-rs-4600-crore-loss-in-andhra-pradesh-345-lakh-farmers-affected)).

**A strong claim to avoid:** "only 15 to 20 per cent of the harvest is salvageable" is one reporter's paraphrase of officers. No named official or assessment supports it.

### A4. Political claims (not figures for us)

- **YSRCP West Godavari president Mudunuri Prasada Raju, 29 Oct** ([party site](https://www.ysrcongress.com/top-stories/cyclone-arnab-devastates-west-106061)): "nearly 70,000 hectares of paddy damaged", and the government's "failure to pay its premium share had left crop-loss victims without insurance compensation". The area is in line with official numbers. The insurance claim is partisan and overbroad: AP is running PMFBY this season (A5). Official data does show large AP pending claims (₹2,817.86 cr as on 24.07.2026), with delay in the State's share named as a primary cause across the scheme.
- **Jagan's "15 lakh acres", "11 lakh acres" and "Rs 600 crore dues" are about Cyclone Montha (2025), not Arnab.** Search results mix them. Do not attach them to Arnab.
- **Tenant farmers:** farmers quoted by Deccan Chronicle fear that subsidy or insurance "would go to the farmers, not the tenant farmers". The guidelines do allow tenants to enrol (para 3.1).

### A5. Is AP running PMFBY in Kharif 2026? Yes: VERIFIED

Source: [PIB backgrounder, 29 Aug 2026](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc_9735_20260829_18493301.pdf).

- "Andhra Pradesh rejoined from Kharif 2022".
- "Both states previously implemented a "universalization approach" during 2023 & 2024, where the State Government bore 100% of the premium on behalf of all farmers, leading to very high enrolment in Kharif 2024."
- "In 2025, both states discontinued this 100% farmer premium subsidy approach".
- "from 31.92 lakh in Kharif 2024 to 7.43 lakh in Kharif 2025 ... till 28th Aug 2026, 16.22 lakh farmers have been enrolled".

**What this means:** enrolment is now not automatic for all farmers. A Godavari farmer may well be uninsured, and many will not know. The app must ask first.

| Item | Finding | Status |
|---|---|---|
| Free crop insurance history | YSR Free Crop Insurance from 2019, ₹1 fee, later closed ([Sarkari Yojana](https://sarkariyojana.com/ysr-free-crop-insurance-scheme-apply-enroll/), updated Sep 2026). Under PMFBY, the State bore 100% of the premium "during 2023 & 2024" per PIB | Secondary, except PIB |
| Kharif 2026 coverage | About 17.12 lakh ha under PMFBY and RWBCIS; 22 notified crops; paddy sum insured about ₹40,000 per acre; 30,286 CCEs planned | [Deccan Chronicle, 31 Oct](https://www.deccanchronicle.com/southern-states/andhra-pradesh/cm-naidus-crop-insurance-policy-to-provide-financial-security-to-farmers-2000460). SECONDARY |
| Enrolment routes and paddy cut-off | Loanee auto-covered with opt-out; non-loanee opt in; paddy 15 Aug | Sarkari Yojana. SECONDARY |
| **Insurer in Godavari districts** | **Not found.** The AP notification was not found, and `apagrisnet.gov.in` did not connect | **UNVERIFIED. Do not name one.** It is on the farmer's PMFBY receipt |
| **Does AP notify localized or post-harvest cover for paddy in Kharif 2026?** | **Not found** | **UNVERIFIED. This decides whether a 72-hour route exists at all** |
| Helpline | 14447 (national; guidelines and Lok Sabha reply). WhatsApp 7065514447 and https://pmfby.gov.in/krph/ from pmfby.gov.in | VERIFIED as published; not test-called |

### A6. Government statements on surveys and intimation

**Intimation: we found no State or Central statement about 72-hour intimation for Arnab.** The only reminder we found is a private blog, [BigHaat](https://www.bighaat.com/kisan-vedika/blogs/cyclone-arnab-2026-landfall-path-wind-speed), which also carries the paddy exclusion.

**Surveys, all reported in the press:**

- Atchannaidu: the extent will be known after rain stops and water recedes, "when agriculture, horticulture and revenue officials conduct joint field inspections". He asked for input subsidy under NDRF and SDRF norms (Daily Pioneer).
- West Godavari Joint Director G Sunitha: "enumeration would start after the waters receded from the fields" (Deccan Chronicle, 30 Oct).
- CM Naidu: crops "would be enumerated to assess losses and extend support", and crop compensation "will follow the damage assessment process" ([ap7am](https://www.ap7am.com/en/138440/cyclone-arnab-claims-four-lives-leaves-trail-of-destruction-in-coastal-andhra)).
- Government, as reported after the Cabinet meeting: losses "are being assessed through field-level enumeration, with compensation expected to be transferred directly to eligible farmers’ bank accounts" (Gulte).
- Central teams were expected on 30 Oct (Daily Pioneer, Gulte). We did not confirm the visit.
- Insurance: "After verification of farmer enrolment, e-Panta crop details and claim eligibility, the admissible compensation would be credited directly to beneficiaries’ bank accounts" (Deccan Chronicle, 31 Oct).

**Two tracks must stay separate in the UI:** State enumeration and input subsidy is relief. PMFBY is insurance. The enumeration does not count as a PMFBY intimation in any text we found.

**Variation between neighbouring villages or mandals (requested):**

- **None found at village or adjacent-mandal level.** No report compares neighbours.
- District shares of paddy inundated: "82 per cent of paddy in West Godavari, 75 per cent in Konaseema and 48 per cent in Kakinada" (Deccan Chronicle).
- Crop stage varies: harvest in 3-5 days in East Godavari, 10 days in West Godavari and others (Deccan Chronicle); about 15 days at Vetlapalem (Gulte); "milky grain stage" around Ramachandrapuram ([BigHaat](https://www.bighaat.com/kisan-vedika/blogs/cyclone-arnab-2026-landfall-path-wind-speed), private blog). These do not fit together neatly, so stage must be checked per plot.
- Rain in Bapatla mandals: Vemuru 106.4 mm, Kolluru 83, Repalle 78, Chunduru 71.1 (ETV Bharat).
- Eluru about 40,000 acres; Bapatla 66,690 acres of paddy flattened (ETV Bharat).
- Reported wind-versus-water difference: West Godavari 1.19 lakh acres "lodged" (Sunitha), against 2.25 lakh acres with over 70% flattened (ETV Bharat). These are different counts, possibly different dates.

### A7. What the app may honestly tell a Godavari paddy farmer

Based on Operational Guidelines 2023. **The 72 hours from landfall ended between 0200 and 0800 IST on 31 Oct 2026, so a live countdown would be false for Arnab.**

| Farmer's situation | Cover on the text | May say | Must not say |
|---|---|---|---|
| Not insured this season | None | "You don't appear to be covered. State enumeration and input subsidy are a separate route." | Anything suggesting a claim |
| Insured, paddy **standing**, flattened or under water | **Basic area-yield cover** (para 5.1, 21.2.1). Intimation "is not essential" (5.5). Cyclone is not a localized peril; paddy inundation is excluded from localized cover (Note 2). The Kharif 2026 change is unconfirmed | "Your claim, if any, comes from the yield measured for your insurance unit. You don't need to file for that. Your evidence helps if you dispute the assessment. Check with 14447 whether AP notified anything further." | "File within 72 hours or lose your claim." "Your individual loss will be paid." |
| Insured, paddy **cut and spread** to dry, in the State's notified harvest window | **Post-harvest**, if AP notified it for paddy (unverified). Cyclone and cyclonic rain are covered perils (21.6.1). 72 hours from the peril | "If paddy is notified for this cover, the rule asks for intimation within 72 hours. That time has now passed from landfall. Report it now anyway on the Crop Insurance App or 14447, and keep the reference number. The guidelines say intimations received during the survey would also be considered." | "You are covered." "Late is fine." "Your claim is rejected." |
| Harvested and stored, or removed from the field | Not covered | "Loss after removal from the field is outside the cover." (PIB, 29 Aug 2026) | |

### A8. Named places with reported paddy or crop damage

The CM survey stops are mixed: "inundated paddy fields, damaged banana and coconut plantations, and aquaculture ponds". So those stops do not each confirm paddy damage. Crop share below 30% usually means coconut, town or ponds.

| Place | Report | Source | Village point | Cropland point | Crop share |
|---|---|---|---|---|---|
| Vetlapalem, Samalkota mandal, Kakinada | Paddy about 15 days from harvest, per farmers to the CM | Gulte | 17.02588, 82.13694 | 17.02151, 82.13781 | 0.58 |
| Mudinepalle mandal, Eluru | "Paddy crops flattened" (photo caption) | ETV Bharat | 16.43882, 81.17512 (mandal) | 16.44153, 81.17491 | 0.51 |
| Anaparthi mandal, East Godavari | Officials visited damaged areas | Deccan Chronicle | 16.90049, 81.97517 (mandal) | 16.90319, 81.97497 | 0.81 |
| Biccavolu mandal, East Godavari | Same visit | Deccan Chronicle | 16.95143, 82.02390 (mandal) | 16.95180, 82.02110 | 0.88 |
| Ramachandrapuram, Konaseema | Paddy flattened at milky stage | BigHaat (private) | 16.83390, 82.03113 | 16.82927, 82.02951 | 0.70 |
| Peddapuram, Kakinada | Fields under water in parts | BigHaat (private) | 17.07567, 82.14332 | 17.07188, 82.14727 | 0.39 |
| Nimmakuru, Pamarru mandal, Krishna | CM survey stop | Daily Pioneer | 16.27134, 81.00446 | 16.27163, 81.00167 | 0.82 |
| Pamarru, Krishna | CM survey stop | Daily Pioneer | 16.32264, 80.96059 | 16.32019, 80.96272 | 0.73 |
| Bantumilli, Krishna | CM survey stop | Daily Pioneer | 16.37058, 81.27247 | 16.36912, 81.27485 | 0.75 |
| Palakollu, West Godavari | CM survey stop | Daily Pioneer | 16.51799, 81.72533 | 16.51195, 81.72778 | 0.39 |
| Narasapuram, West Godavari | CM survey stop | Daily Pioneer | 16.43864, 81.70146 | 16.44060, 81.69784 | 0.29 |
| Katrenikona, Konaseema | CM survey stop | Daily Pioneer | 16.58090, 82.15554 | 16.58169, 82.15174 | 0.41 |
| Amalapuram, Konaseema | CM survey stop | Daily Pioneer | 16.57772, 82.00326 | 16.57834, 82.01397 | 0.20 |
| Ainavilli mandal, Konaseema | Damaged crops, coconut, river-island villages | Hans India | 16.66378, 82.03102 (mandal) | 16.66516, 82.02014 | 0.15 |

**Best for GEO to try first:** Anaparthi, Biccavolu, Nimmakuru, Pamarru and Bantumilli (high cropland share). Vetlapalem and Ramachandrapuram are next.

**Harvest risk:** with harvest due in days, a before-and-after drop may be ordinary harvest. Lodged paddy may also keep some greenness. The cross-examination must test this for every plot.

**Not read:** The Hindu and Times of India reports. WebFetch refuses those domains, and we did not work around that.

## B. Sirsa and Fatehabad, October 2026

### B1. Event date: Saturday evening, 24 October 2026

| Source | Wording | Note |
|---|---|---|
| [The Tribune, updated 11:17 PM, 24 Oct 2026](https://www.tribuneindia.com/news/haryana/hailstorm-rain-raise-fears-of-paddy-crop-damage-in-sirsa-fatehabad-districts/) | "rain and hailstorm in several villages across Rania, Dabwali and Ding areas of Sirsa, as well as Ratia and Tohana in Fatehabad district, on Saturday evening" | **Filed the same night. Strongest date evidence** |
| [The Tribune, 26 Oct 2026](https://www.tribuneindia.com/news/haryana/hailstorm-hits-sirsa-crops-farmers-seek-compensation/) | "unseasonal rain and hailstorms late on Saturday have damaged paddy and cotton crops" | Confirms it. Names Bharokhan, Darbi, Baruwali |
| [UNI, 25 Oct 2026, 10:08](https://www.uniindia.com/north-india/agriculture-haryana-selja-crops-damage/224950) | "Sirsa, Oct 25 (UNI) Unseasonal rain and hail storms have damaged standing paddy and cotton crops" | **No event date. 25 Oct is the dateline.** Selja's statement. Paywalled after the opening |

- **The plan's "25 Oct hail" is wrong. Use 24 Oct.** The 72 hours ran out on the evening of 27 Oct.
- **The weather finding still stands.** 24 Oct is inside the 23-25 Oct window where gridded weather shows under 1 mm, so a date error does not explain it. No source gives any other date. "The grid can't see a storm this small" remains the honest reading, though we have no measured rainfall for these villages.
- **GEO check:** Sentinel-1 has a 24 Oct pass. Check its time against the evening event; it may be before the hail. If so, the first true post-event radar is 28 Oct.
- **Do not confuse with:** rain "early Wednesday" (14 Oct) in Fatehabad, Jakhal 36 mm and Bhuna 9 mm, which soaked paddy in mandis ([The Tribune, 15 Oct 2026](https://www.tribuneindia.com/news/haryana/paddy-soaked-mandis-flooded-as-rain-wreaks-havoc-in-fatehabad)). This falls before the 18 Oct baseline scene.
- **Harvest is underway:** "harvesting is already underway in several villages", and some paddy lay cut in fields.
- **Haryana has a separate route:** the BKE mentions errors on Meri Fasal Mera Byora "preventing the farmers from selling their produce and filing online claims". State compensation portals are not PMFBY.
- **Official assessment:** none found. Claims are from an MP, farmer groups and INLD.

### B2. Village locations

Selja's villages appear to sit in **Ratia tehsil, Fatehabad**, not Sirsa district. [A census-based listing](https://villageinfo.in/haryana/fatehabad/ratia/) shows Dadupur, Jallopur, Haroli (a likely variant of Hadoli) and Ratta Khera in Ratia. This matters for any plot chosen near (75.03, 29.53), which is in Sirsa district about 50 km west.

| Name in report | Resolved as | Point | Cropland point | Crop share | Confidence |
|---|---|---|---|---|---|
| Jalopur | Jallopur, Ratia, Fatehabad | 29.68881, 75.49755 | 29.69151, 75.49735 | 0.93 | Good (variant) |
| Dadupur | Dadupur, Ratia tehsil, pincode 125051 | **Not found on the map** | - | - | Tehsil only |
| Hadoli | Haroli, Ratia tehsil | **Not found on the map** | - | - | Tehsil only; spelling is our inference |
| Rattakhera | Ratta Khera, Ratia tehsil (listing). OSM also has Rattakhera, Tohana | Candidate: 29.65989, 75.87590 | 29.65718, 75.87569 | 0.89 | **Ambiguous** |
| Nimari | - | **Not found** | - | - | None |
| Bhatusotra | Not found. Ratia has several "Sotter" villages, which may be related | **Not found** | - | - | None |
| Darbi (Tribune, 26 Oct) | Darbi, Sirsa | 29.57531, 75.15869 (a health centre there) | 29.57327, 75.15664 | 0.93 | Good |
| Bharokhan, Baruwali (Tribune, 26 Oct) | - | **Not found** | - | - | None |
| Ratia (area) | Town | 29.68623, 75.57505 | 29.68469, 75.56926 | 0.66 | Good |
| Tohana (area) | Town | 29.71079, 75.90423 | 29.70975, 75.91219 | 0.51 | Good |
| Rania (area) | OSM place | 29.52409, 74.83693 | 29.52597, 74.84047 | 0.81 | Good |
| Dabwali (area) | OSM place | 29.94866, 74.73728 | 29.94495, 74.73832 | 0.80 | Good |

**Recommended Sirsa-case plot area:** around Jallopur or Darbi, the two named villages we could pin down. Tell the demo audience we cannot place every named village.

## C. Earlier events for positive validation

### C1. Hail, 2-3 March 2024, Bhiwani and Hisar (best positive case)

Standing rabi crop, late-season hail, official damage numbers.

- **Date:** "damage to crops by hailstorm on March 2 and 3" (AIKS memorandum). [The Tribune, 6 Mar 2024](https://www.tribuneindia.com/news/haryana/hisar-bhiwani-farmers-suffer-massive-losses-says-report-597645).
- **Official numbers (Agriculture Department report, as reported):**
  - Hisar: wheat about 1 lakh acres and mustard 38,000 acres at 51-75% loss; mustard 4,571 acres and wheat 230 acres over 76%; mustard 43,220 and wheat 39,065 acres at 26-50%.
  - Bhiwani: mustard about 4,500 acres at 76-100%, 8,117 acres at 51-75%, 33,772 acres at 26-50%, out of 83,000 acres.
- **Named villages:** "Manheru, Dharedu, Goripur, Kitlana, Nangal, Umravat and surrounding villages had been completely destroyed" (farmers' delegation, a claim).
- **Other reports:** [The Tribune, 3 Mar 2024](https://www.tribuneindia.com/news/haryana/rabi-crops-face-fury-of-rain-hailstorm-in-state-farmers-seek-special-girdawari-596666/) names Badkhalsa (Rai) and Nirthan (Kharkhoda) in Sonipat, which we could not locate.
- **Crop state:** mustard "at ripening stages", wheat standing. Mustard harvest is near, so wheat is the cleaner signal.
- **Insurance caveat:** a Congress leader said no insurer covered seven districts including Hisar that season. Good for signal validation; **do not present it as a PMFBY claim case.**

| Village | Point | Cropland point | Crop share | Match |
|---|---|---|---|---|
| Umrawat (Umravat), Bhiwani | 28.76924, 76.18476 | 28.76654, 76.18455 | 0.80 | Variant |
| Maneharu (Manheru), Bhiwani | 28.70809, 76.21909 | 28.70463, 76.22013 | 0.85 | Variant |
| Dhareru (Dharedu), Bhiwani | 28.73657, 76.22797 | 28.73686, 76.23176 | 0.90 | Variant |

### C2. Hail, Friday night 14 March 2025, Sirsa (patchy; weaker signal)

[The Tribune, 16 Mar 2025](https://www.tribuneindia.com/news/haryana/hailstorm-causes-crop-damage-in-sirsa): "A hailstorm accompanied by rainfall struck Sirsa district on Friday night, affecting around 25 villages in the Dabwali, Rania and Odhan regions. The storm caused minor damage to wheat and mustard crops". Light rain began "around 9 pm". Mustard harvest had started.

**Use as a test of honesty:** expect weak or mixed signals. If the engine shouts "strong" here, it is over-claiming.

| Village | Point | Cropland point | Crop share | Match |
|---|---|---|---|---|
| Paniwala Motta (Panniwala Mota) | 29.70361, 74.90780 | 29.70249, 74.90434 | 0.87 | Variant |
| Kharian | 29.61899, 74.85707 | 29.62286, 74.85670 | 0.88 | Exact |
| Bacher | 29.65187, 74.59787 | 29.65442, 74.59674 | 0.89 | Exact |

### C3. Hail, 31 March 2026, Hisar (recent, but harvest-confounded)

- [The Tribune, 2 Apr 2026](https://www.tribuneindia.com/news/haryana/haryana-farmers-congress-mla-demand-compensation-from-govt-after-rain-hail-damage-crops/): "hail and rain on March 31"; "wheat crops were fully ripe and ready for harvesting".
- [The Tribune, 1 Apr 2026](https://www.tribuneindia.com/news/haryana/haryana-farmers-fear-yield-loss-as-hailstorm-hits-standing-crops/): "no official assessment has been conducted so far". AIKS speaks of "the past two days", so the date may span 30-31 March.
- **Ripe crop already has low greenness, so optical signal may be weak.** A good test for the harvest objection.

| Village | Point | Cropland point | Crop share | Match |
|---|---|---|---|---|
| Kabrel, Hisar | 29.18265, 75.51466 | 29.18419, 75.51720 | 0.91 | Exact |
| Kirtan, Hisar | 29.13895, 75.55686 | 29.13941, 75.55990 | 0.94 | Exact |
| Matarsham (Matrashyam), Hisar | 29.17665, 75.59365 | 29.17403, 75.59285 | 0.92 | Variant |
| Bagla, Hisar | 29.18915, 75.47654 | 29.18645, 75.47633 | 0.91 | Exact |
| Sundawas, Hisar | 29.10438, 75.52262 | 29.10392, 75.52566 | 0.95 | Exact |
| Dobhi, Hisar | 29.13203, 75.50814 (health centre) | 29.13157, 75.51118 | 0.82 | Exact |

### C4. Hail, 27 December 2024, Fatehabad (hard negative-leaning case)

[The Tribune, 28 Dec 2024](https://www.tribuneindia.com/news/haryana/widespread-hailstorm-damages-rabi-crops-in-region) names Dhangar, Bigar, Saalamkheda, Badopal, Mohammadpur Rohi, Bhirdana, Bisla and others. It also quotes a scientist saying the rain helps the crop overall. Young crop can recover, and hail in December may leave little lasting signal.

| Village | Point | Cropland point | Crop share |
|---|---|---|---|
| Dhangar | 29.46765, 75.51848 | 29.46761, 75.51535 | 0.89 |
| Badopal | 29.41576, 75.54885 | 29.41663, 75.55264 | 0.88 |
| Bhirdana | 29.54806, 75.54941 | 29.55127, 75.55161 | 0.91 |

### C5. Punjab floods, 26 August to September 2025 (radar test)

**Dates:**

- Madhopur headworks: "intervening night of August 26-27" ([The Tribune, 20 Sep 2025](https://www.tribuneindia.com/news/jalandhar/ravi-floods-punjab-government-suspends-3-officers-at-madhopur-headworks-for-floodgate-failure-on-august-26-27-night/)). [SANDRP](https://sandrp.in/2025/08/29/aug-2025-ravi-flood-damages-madhopur-barrage-gates-in-punjab/) says "the evening of Aug 27". The sources differ by up to a day.
- Ajnala and Ramdass: Dhussi embankment breached at three places (SANDRP); floods "since August 27" (Tribune, search excerpt).
- Fazilka on the Sutlej: **no exact flood date in our sources.** Down To Earth visited by late September.

**Scale:** Punjab agriculture director: "around 3 lakh acres" and "over 42,000 hectares of paddy crop" in Gurdaspur, before any girdawari ([The Wire, 31 Aug 2025](https://m.thewire.in/article/environment/punjab-floods-rivers-overflow-3-lakh-hectares-of-crops-affected/amp)). Crop: mainly paddy, standing.

**Use SAR.** Monsoon cloud limits optical. Silt and sand can remain for months, so a later "bare" reading is expected. Sharp breach edges should make placebo tests clear.

**Insurance caveat:** this is widespread flooding of paddy, which is basic cover on the text, not a localized claim.

| Village | Reported | Source | Point | Cropland point | Crop share |
|---|---|---|---|---|---|
| Pakhoke Mehmaran (Pakho Ke), Dera Baba Nanak | Displaced villagers on the highway; breach near Kartarpur corridor | The Wire | 32.01766, 75.01231 | 32.01496, 75.01210 | 0.84 |
| Dera Baba Nanak | Destroyed paddy | [Down To Earth, 30 Sep 2025](https://www.downtoearth.org.in/climate-change/despair-after-deluge-2025-floods-have-turned-punjabs-fields-into-sand-dunes) | 32.03179, 75.02846 | 32.03325, 75.02517 | 0.78 |
| Kot Gurbaksh, Ajnala | 38 acres of basmati destroyed, one farmer | Down To Earth | 31.98334, 74.91568 | 31.98063, 74.91547 | 0.84 |
| Mahatam Nagar (Mahatmanagar), Fazilka | "2-3 feet of silt", mainly paddy lost | Down To Earth | 30.47609, 73.99717 | 30.47879, 73.99697 | 0.94 |
| Ram Singh Bhaini, Fazilka | Same | Down To Earth | 30.48809, 73.99757 | 30.49080, 73.99736 | 0.95 |

Not located: Haruwal, Ghonewal, Machhiwal (the worst-hit Ajnala villages in Tribune excerpts), Dineke. "Ghuram" in Ferozepur resolved only to places in other districts, so we rejected it.

## D. Suggested order for GEO

1. **C1** Umrawat, Maneharu, Dhareru: wheat fields, 2-3 Mar 2024. Clean positive; compare fields against the official loss bins by district only (no field truth).
2. **C5** Mahatam Nagar and Kot Gurbaksh, with SAR. Flood positive.
3. **C3** Kabrel and Kirtan. Harvest-confounded test.
4. **C2 and C4.** Expect weak signals; these test against over-claiming.
5. **A8** Anaparthi, Biccavolu, Nimmakuru. Live demo, only if imagery allows. Label harvest and insurance status honestly.
6. **B** Jallopur and Darbi. The honest hard case.

**No event here gives plot-level ground truth.** Reports give villages and district-level bins. Validation can show consistency, not accuracy.
