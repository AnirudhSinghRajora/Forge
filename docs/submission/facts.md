# FasalSaakshi: fact sheet for slides and the pitch

Researched 31 Oct 2026. **Every number on a slide must come from this file, with its wording kept.**

- **VERIFIED**: we read the primary document ourselves, and the quote is exact.
- **SECONDARY**: a news report, vendor page or summary. Attribute it on the slide ("per The Tribune", "farmers say").
- **UNVERIFIED**: do not use.

Downloaded copies are in `backend/data/policy/raw/`. Rule text and clause IDs are in `backend/data/policy/key_rules.json` and `clauses.jsonl`.

## 1. What must change in the pitch

| # | Current wording (where) | Problem | Use instead |
|---|---|---|---|
| 1 | "No farmer-side, plot-level evidence tool exists" (ideation 06) | Stronger than we can prove. Section 7 lists close neighbours, including a farmer-side 72-hour agent and an India-focused photo, satellite and weather service. | "We did not find a farmer-side tool that gives a field its own placebo-tested satellite evidence and lets anyone recompute it." |
| 2 | "72-hour rule silently kills valid claims", "Late intimation is a standard rejection ground" (ideation 03, 06) | No clause says this. Para 21.5.9.2 calls intimation a pre-condition, then says intimations received during the survey "would also be considered". | "The rule asks for intimation within 72 hours, and many farmers don't know it." We have no source for how often claims are lost this way. |
| 3 | The 72-hour rule as the headline for all crop loss (05 demo) | It applies only to the localized and post-harvest add-ons, where the State notified them. For widespread loss, intimation "is not essential" (para 5.5). | "For individual-farm covers (localized and post-harvest)..." |
| 4 | "Satellites decide claims at village level... a hail strip gets averaged away" (03, 05) | This mixes two systems. YES-TECH sets area yield for basic cover. A localized hail claim goes to a joint survey, or to the 10-parcel sample above 25%. Satellite indices enter there only in a dispute (para 21.5.9.4). | Tell them apart. See section 6 for the sample rule. |
| 5 | "Farmers can't see or contest the evidence" (05, 03) | A contest route exists: written notice within 7 days with proofs, then DLMC, State, STAC. Also 14447, Taluka officer, DGRC, SGRC. | "Farmers can contest, but they have no evidence of their own to contest with." |
| 6 | "YES-TECH: insurance-unit level" (05, 03) | The guidelines say Gram Panchayat level (para 2.17). "Insurance-unit level" is a vendor's wording. | "Gram Panchayat level." |
| 7 | "moderate resolution (5-30 m) can't see a small farm" as a weakness of YES-TECH | Sentinel-2 at 10 m is in the same range. A judge can turn this on us. | Our difference is the unit of analysis and the placebo test, not a better sensor. |
| 8 | "On 25 Oct, hail hit Sirsa" (03, 05, 07-contract) | 25 Oct is the UNI dateline. The Tribune puts it on **Saturday evening, 24 Oct 2026**. | 24 Oct 2026 (see `docs/validation/events.md`). |
| 9 | "waterlogging" as an insured localized peril (05) | Note 1: "mere water logging without corresponding crop loss will not be eligible". | "Inundation that damages the crop." |
| 10 | CSC listed as an intimation channel (ideation 03) | Not named in paras 21.5.5.4 or 21.6.6.4, or in Tables 10 and 11. | Remove it. |
| 11 | CROPIC "nationwide in 2026" (ideation 03) | PIB on 29 Aug 2026 says "nation-wide pilots are in the process of initiation". | Quote PIB. |
| 12 | Rajasthan "₹947.72 cr pending (Jul 2025)" (ideation 03) | Secondary only. The official table for 30.06.2025 shows Rajasthan at ₹1,525.2 cr. | Use the official figure with its date, or drop it. |
| 13 | "4,992.79 lakh applications", "₹86,306 cr to 1,423 lakh" (ideation 03, AS125) | We could not reopen the primary: eparlib refused connections on 31 Oct. | Use the PIB figures in section 2. |
| 14 | Haryana: "satellite assessments cut... by about ₹350 crore" as plain fact (05) | It is what farmers allege. | "Farmers say..." (section 4). |

## 2. Scale of PMFBY

"Applications" are not farmers. One farmer can file several applications. Keep the word.

| Number | Exact wording | Source | Status |
|---|---|---|---|
| 92.46 crore; 26.33 crore; ₹2.06 lakh crore | "since the inception of the scheme in Kharif 2016 till Rabi 2025-26, more than 92.46 crore farmer applications have been insured, and over 26.33 crore farmer applications have been paid claims exceeding ₹2.06 lakh crore" | [PIB backgrounder, 29 Aug 2026](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/aug/doc_9735_20260829_18493301.pdf) | VERIFIED |
| 78.70 crore applications; ₹1,92,477.31 cr claims; 23.23 crore benefitted | Annexure, "State-wise All India cumulative Coverage & Claims from 2016-17 to 2024-25 (as on 31.12.2025)", Total row: 787,021,056 / premium 36,055.07 / claims 192,477.31 / 232,268,660 | [PIB 2237736, Lok Sabha reply, 10 Mar 2026](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2237736&reg=48&lang=2) | VERIFIED |
| 241.38 lakh farmers; 278.12 lakh ha (Kharif 2026) | "As of 27th August 2026, 241.38 lakh farmers have been insured, covering 278.12 lakh hectares" | PIB backgrounder, 29 Aug 2026 | VERIFIED |
| 229.77 lakh farmers; 269.38 lakh ha (Kharif 2025) | "In Kharif 2025, crop insurance covered 229.77 lakh farmers covering 269.38 lakh hectares" | same | VERIFIED |
| ₹9,837.61 cr; 60.89 lakh | "For Kharif 2025, claims worth ₹9,837.61 Crore have already been paid to 60.89 lakh eligible farmers" | same | VERIFIED |
| 15.23 crore applications (2024-25) | "National enrolment reached an all-time high in 2024-25, with more than 15.23 crore farmer applications covering more than 4 crore farmers have been insured, and over 623 lakh hectares covered." | same | VERIFIED |
| 25 States/UTs | "PMFBY is currently being implemented by 25 States and Union Territories in Kharif 2026." | same | VERIFIED |
| ₹12,200 crore | "The Government has allocated ₹12,200 crore for PMFBY in the Union Budget 2026–27" | same | VERIFIED |
| 26.12 lakh grievances; 99.66% | "It was launched in January 2024 across the nation, and since then, 26.12 lakh grievances of insured farmers have been addressed & resolved with 99.66% resolution rate." (KRPH) | same | VERIFIED. This is the government's own figure and cuts against a "nobody listens" story. |

**Slide suggestion:** "92.46 crore farmer applications insured since 2016 (PIB, Aug 2026)". This replaces "crore-scale".

## 3. Pending claims

| Number | Exact wording or derivation | Source | Status |
|---|---|---|---|
| **₹4,107.47 cr pending** | Annexure-I, "All India State Wise Claims Report from 2020-21 to 2024-25 as on 31.12.2025". Total row pending: Kharif 2,793.17 + Rabi 1,314.30 | Lok Sabha Unstarred Q662, 3 Feb 2026. `sansad.in` returned a server error, so we read the same file at [this mirror](https://api.policyindex.ai/demo/_loksabhaquestions_annex_187_AU662_dnteed.pdf) | VERIFIED (document read via mirror; check `sansad.in` before printing the link) |
| ₹1,00,085.31 cr reported; ₹95,977.84 cr paid | Total row: reported 71,148.24 + 28,937.07; paid 68,355.07 + 27,622.77 | same | VERIFIED |
| **74% in Andhra Pradesh** (₹3,041.66 cr) | AP pending 2,184.03 + 857.63 = 3,041.66, which is 74.05% of 4,107.47 (our arithmetic) | same | VERIFIED |
| AP: ₹2,817.86 cr pending, later date | "PMFBY & RWBCIS: Year wise Coverage and Claims Report of Andhra Pradesh from 2022-23 to 2025-26 as on 24.07.2026", Total, Pending Claims 2,817.86 (2023-24 alone: 2,038.52) | [Lok Sabha Unstarred Q3825, 11 Aug 2026](https://sansad.in/getFile/lsapps/loksabhaquestions/annex/188/AU3825_joiHcd.pdf) | VERIFIED. Different years and date, so do not add it to or compare it directly with the 74%. |
| Why claims stay pending | "some claims remained pending, primarily on account of: a. delay in providing State Government share of claims b. incorrect/delayed submission of insurance proposals by banks and unverified bank account details of enrolled farmers c. discrepancy in yield data & consequent disputes between State Government and insurance companies, etc." | Q3825 | VERIFIED |
| ₹6,456.6 cr (older) | "State Wise Claims Pending Data for Five Years as on 30.06.2025", Total 6,456.6. Rajasthan 1,525.2; AP 2,565.8; Haryana 65.4 | [PIB 2148513, Rajya Sabha reply, 25 Jul 2025](https://www.pib.gov.in/PressReleseDetailm.aspx?PRID=2148513&reg=48&lang=2) | VERIFIED as printed. The Total row's year columns add to 6,482.9, not 6,456.6, so the table does not reconcile. Prefer ₹4,107 cr. |

**Do not imply** that AP's pending claims come from satellite assessment or individual field evidence. The official reasons above are mainly money and data flow. FasalSaakshi does not fix a State's unpaid share. The fair use of this number is "the state with most pending claims is where Arnab just hit".

## 4. Haryana 2025 protests over satellite assessment

All SECONDARY: a single news report of what farmers and a former Chief Minister said. We have no official confirmation of the amounts.

Source: [The Tribune, 25 Aug 2025](https://www.tribuneindia.com/news/haryana/crop-insurance-row-hooda-seeks-probe-compensation)

- "According to them, Crop Cutting Experiments (CCEs) had estimated claims worth Rs 450 crore, but the yield assessment through HARSAC satellite imagery cut it down by nearly Rs 350 crore."
- "Notably, farmers from both districts have been on dharna since July 16, 2025, demanding fair settlement of claims. They alleged that the State Technical Advisory Committee, in its meeting on August 20, 2024, wrongly rejected the CCE and approved claims on the basis of “technical yield.”"
- "The farmers also referred to a state government order dated August 29, 2023, mandating that claims under PMFBY be settled on the basis of CCEs, not satellite imagery alone."
- Hooda: "Around Rs 350 crore of farmers’ rightful claims have been denied through manipulation of data."
- Districts: Bhiwani and Charkhi Dadri.

**Safe slide wording:** "In 2025, Bhiwani and Charkhi Dadri farmers sat on dharna from 16 July. They say satellite-based yield cut about ₹350 crore from CCE-based claims (The Tribune, Aug 2025)."

Related: [Down To Earth, 20 Aug 2026, "Beyond the Lens"](https://www.downtoearth.org.in/agriculture/beyond-the-lens) reports Madhya Pradesh farmers struggling with satellite-based insurance (SECONDARY; we read only the free portion). The Rajasthan protest in ideation 06 is secondary only, so leave it off slides.

## 5. YES-TECH, CROPIC, small farmers, Andhra Pradesh, Arnab

### YES-TECH

| Fact | Exact wording | Source | Status |
|---|---|---|---|
| Scope | "Yield Estimation System based on Technology (YES-TECH) for direct estimation of yield at Gram Panchayat (GP) level has been rolled out from Kharif 2023 season onwards" | OG 2023 para 2.17 | VERIFIED |
| Minimum 30% | "minimum 30% weightage to technology driven yield estimates in the first year along with 70% to traditional Crop Cutting Experiments approach" | OG 2023 para 20.2.1.5 | VERIFIED |
| Current weightage | "mandatory 30% weightage to yield estimation has been assigned to YES-TECH derived yield. However, State Government of Madhya Pradesh and Maharashtra has given 100% and 50% weightage respectively to YES-TECH based yield in 2025-26." | [Lok Sabha Starred Q25, 21 Jul 2026](https://sansad.in/getFile/lsapps/loksabhaquestions/annex/188/AS25_tpFUNy.pdf) | VERIFIED |
| Conflict | "has now increased up to 50% across certain states" (PIB, 29 Aug 2026) conflicts with the 100% for MP in the reply above. | both | Flagged. Cite the Lok Sabha reply. |
| Crops | "launched for paddy & wheat crops from Kharif 2023 and Soybean crop from Kharif 2024" | same | VERIFIED |
| "can't detect" a small farm | "well suited to Insurance Unit-level aggregation but can’t detect variation within an individual small farm" | [Vassar Labs](https://vassarlabs.com/yes-tech-explained-how-satellites-estimate-crop-yield-for-insurance/) | SECONDARY (vendor). See table row 7 before using. |

Not read: the official YES-TECH Manual 2023 (v.2). It is a 120-page scan with no text layer. We make no claim from it.

### CROPIC

- "It is also envisaged to support crop damage assessment and yield estimation through pictorial analytics, for which nation-wide pilots are in the process of initiation" (PIB, 29 Aug 2026). VERIFIED.
- "The use of CROPIC Mobile App for collection of crop photographs shall be mandatory for Insurance Companies and State Governments/UTs." (OG 2023 para 20.2.2.4). VERIFIED.
- 50-district pilot for Kharif 2025 and Rabi 2025-26: exam-prep sites only. SECONDARY. Do not put on a slide.

### Small and marginal farmers

| Number | Wording | Source | Status |
|---|---|---|---|
| 86.08% of holdings; 46.94% of operated area | Agriculture Census 2015-16 | Search excerpts only ([GKToday](https://www.gktoday.in/what-are-the-major-current-trends-in-fragmentation/)). The primary Lok Sabha copies were unreachable. | SECONDARY. Widely repeated, but check before printing. |
| 17.6% marginal; 6.5% tenant; 48% loanee | "Out of the total farmer applications enrolled under the scheme in 2024-25, 6.5%, 17.6% and 48% are pertaining to tenant, marginal and loanee farmers respectively." | PIB 2148513, 25 Jul 2025 | VERIFIED |
| Small and marginal share of PMFBY enrolment | No current official figure found. Others conflict (84%, 64%). | | UNVERIFIED |

### Andhra Pradesh enrolment

- "In Kharif 2025, the farmers’ enrollment in Andhra Pradesh dropped 77% (from 31.92 lakh in Kharif 2024 to 7.43 lakh in Kharif 2025). In Kharif 2026, the trend has reversed, and till 28th Aug 2026, 16.22 lakh farmers have been enrolled" (PIB, 29 Aug 2026). VERIFIED.
- "In 2025, both states discontinued this 100% farmer premium subsidy approach" (same). VERIFIED.
- "AP provided insurance coverage for approximately 17.12 lakh hectares" in Kharif 2026 under PMFBY and RWBCIS; paddy sum insured about ₹40,000 per acre; 30,286 CCEs ([Deccan Chronicle, 31 Oct 2026](https://www.deccanchronicle.com/southern-states/andhra-pradesh/cm-naidus-crop-insurance-policy-to-provide-financial-security-to-farmers-2000460)). SECONDARY.

### Arnab crop loss

**Safe slide wording:** "About 3.51 lakh hectares of crops damaged, per the Andhra Pradesh Agriculture Minister's preliminary assessment (29 Oct 2026)." SECONDARY: news reports of his statement; we did not find the State's own press note. Sources and the full conflict table are in `docs/validation/events.md`.

Do not use ₹4,600 crore as crop loss. That is the Chief Minister's preliminary figure for all cyclone damage.

## 6. Paras 21.5.8, 21.5.9.3, 21.5.9.4, 21.5.9.5 (the 10-parcel survey)

Source: [Operational Guidelines 2023](https://pmfby.amnex.co.in/pmfby/pdf/operational_guidelines_pmfby.pdf), pp. 105-106. VERIFIED. The same text is in the copy issued with the 6 Nov 2024 ministry circular.

### Verbatim

**Para 21.5.8, below 25%:**

> If the insured area in an IU with loss intimations as compared to the total insured area for that particular crop in the IU is less than 25%, then an individual survey of all the farmers shall have to necessarily be done.

**Para 21.5.8, above 25%:**

> Wide-spread Localized Calamity: If the Insured area under loss intimation under localized calamity claims in an IU is more than 25% of the total Insured area in the IU during a specific weather event having a single/similar peril, then the event shall be considered as Wide-spread Localized calamity and the sample loss survey will be conducted at 10 different randomly selected crop-land parcels using the loss intimation list across the affected Insurance Unit and average loss %age basis the sample survey shall be applicable to all intimations for the given IU during the specific weather event.

> In this case, the losses will not be considered as individual and will be presumed widespread.

> Therefore, the claims shall be disbursed to all eligible insured farmers (who have given intimation/for whom intimation has been received/accepted) in accordance with the crop loss assessment arrived at following the below tabular grid.

> (Average Area Affected %age X Average Crop Loss %) X Sum Insured X 25%

**Para 21.5.9.3:**

> If the affected area under a notified crop is more than 25% of the total insured area in a notified insurance unit, all the eligible farmers who have taken insurance for the notified crop, which has been damaged, and informed about the occurrence of a calamity in the individual insured farm/land parcel within the stipulated time in the notified Insurance Unit (IU), would be deemed to have suffered localized loss and would be eligible for financial support under localized calamity loss. The percentage of loss would be arrived at by Insurance Company through a requisite number of sample survey as defined in the detailed protocol for the add-on cover.

**Para 21.5.9.4:**

> The eligibility of claim settlement shall be decided based on the outcome of joint loss assessment surveys carried out by representatives of Insurance Company, District Administration/State Government’s/UT Administration’s Nodal Department and Farmers. Further if the affected area is more than 25% of the total insured area and there is dispute / disagreement between the stakeholders regarding the quantum/extent of loss reported by the Joint Loss Assessment committee, the claim calculation will be done using technology derived solutions involving weather and/or remote-sensing indices along with loss assessment surveys with a weightage of 70% and 30% respectively for assessment and evaluation of the final extent of loss. Acceptance of the technology-driven extent of loss will be binding on all stakeholders.

**Para 21.5.9.5:**

> STAC in coordination with State Remote Sensing Application Centre or TIP appointed under YES-TECH (for the crops notified under Crop Model Matrix (CMM)) will conduct yield estimation and assessment of loss as mentioned in Para 21.5.9.4 based on the protocol developed by MNCFC. STAC may take the help of MNCFC if they desire.

The post-harvest cover repeats the sample rule at para 21.6.9, with its own 21.6.10.x conditions.

### Limits on how we may describe this

1. **It applies only above 25%, only to localized or post-harvest claims, and only where the State notified the cover and crop.** Below 25%, every intimation gets an individual survey, so there is no sampling to simulate.
2. **It is not usable for standing Godavari paddy on current text.** Cyclone is not a localized peril and paddy is excluded from localized inundation (Note 2). PIB announced a change for Kharif 2026, but a Lok Sabha reply of 4 Aug 2026 still says "except in case of localized claims". An Arnab run must be labelled "what the rule would do if it applied", or use cut-and-spread paddy under para 21.6.9 if AP notified that cover (not verified).
3. **The sample frame is the loss intimation list, not all parcels.** A simulation drawing from all cropland in a unit models a different thing. If we have no intimation list, we must say that the frame is assumed.
4. **Pixels are not the survey.** A joint survey estimates crop loss %. Our index drop is a proxy. Say "the spread of a 10-parcel sample of this satellite signal", never "the survey result would have been X%".
5. **Random sampling is not unfair by design.** A 10-parcel random sample is unbiased on average. What we can show is how much one draw varies in a patchy event. "Lottery" is our word and appears nowhere in the guidelines. Use it as our framing, not as a finding of misconduct.
6. **We have no data on any real sample.** We found no public record of an actual 10-parcel draw, so we cannot say farmers lost money from it.
7. **Do not show a rupee payout.** The text is inconsistent. The 21.5.8 formula ends in "X 25%", while the illustration on p.111 computes A x B x C = Rs. 24,000 with no 25% factor. Note 3 points to the on-account modality, where para 21.4.2.7 says "25% of the likely claims".
8. **Two different triggers are worded.** Para 21.5.8 says "Insured area under loss intimation". Para 21.5.9.3 says "affected area". Neither explains how they relate. Para 21.5.9.2 also says "limited up to 25%", while other text says "less than 25%".
9. **"10" and "requisite number".** Para 21.5.9.3 still says "requisite number", while 21.5.8 says 10. Cite 21.5.8 for the 10.
10. **Only those who intimated are covered.** Do not say "everyone in the unit gets paid". Table 10 Note 3 omits the bracket on intimation, but 21.5.8, 21.5.9.3 and the post-harvest Note 3 include that limit.
11. **The 70/30 route is not a farmer's satellite right.** It applies only above 25% and only when there is a dispute, and STAC with SRSAC or a TIP runs it under an MNCFC protocol we have not seen. A farmer's PDF does not trigger it. It also binds the farmer: "binding on all stakeholders". The honest statement is that the guidelines accept remote sensing in this dispute, and that any stakeholder may give written notice with "proofs/data/reports" within 7 days (area-protocol row 4).
12. **The history is modest.** A 10-location random survey is not new in 2023. The 2018 and 2020 guidelines' mid-season table already says "at least 5% of crop sown area at 10 different locations randomly". The 2020 localized text says "requisite number of sample survey". OG 2023 is where we first found 10 parcels for localized claims.

### Has anyone published on this? (searched 31 Oct 2026)

**Method:** seven web searches on the wording, on criticism, and on simulation and sampling-error studies. We did not search Google Scholar, Scopus or Indian-language press directly. So this is "we did not find", not "none exists".

| Question | Finding |
|---|---|
| Analysis or criticism of the 10-parcel localized rule itself | **None found.** No article, paper or critique quoting this rule surfaced. |
| Criticism of sampling in PMFBY generally | **Yes, and old.** [Down To Earth, Feb 2018](https://www.downtoearth.org.in/merely-increasing-pmfby-coverage-might-not-help-59620): "In an entire village panchayat, random sample from only four farms are taken, which determine, if any farmers of that village panchayat will get any claim." That is about crop cutting experiments, not this rule. A similar point on sampling error in payouts appears in [a Substack essay](https://sustainabilitymattersindia.substack.com/p/sm-107-forty-years-of-crop-insurance) (seen as a search excerpt). |
| Localized patchiness argument | **Yes.** A [ThePrint opinion piece](https://theprint.in/opinion/pmfby-is-failing/2637517/) argues that a flash flood in a corner of a village can destroy one farmer's crop and spare a neighbour's (search excerpt). |
| Simulations of sampling or error effects on indemnity | **Related work exists.** The PMFBY compendium's [2021 technical report](https://pmfby.gov.in/compendium/Technology/2021%20-%20Replacing%20CCE-yield%20with%20modelled%20yield-Technical%20Report.pdf) has a section "Model error and its impact on indemnity". The NRSC [smart sampling report](https://pmfby.gov.in/compendium/Technology/2019%20-%20Smart_sampling_odisha_NRSC_Tech%20Report.pdf) studies CCE plot selection. Neither models the localized 10-parcel rule. |
| Field-scale hail or flood measurement with satellites | **Well established; not novel.** [Ha et al. 2022](https://doi.org/10.3390/rs14040951): Sentinel-2 hail damage against adjuster estimates on 54 Canadian fields. Poddar 2022 (*Natural Hazards*; ISRO and AIC authors, potato hail, India). A [2025 Romanian study](https://doi.org/10.3390/rs17233850) warns that image timing changes the damaged area measured. |
| Farmer-side or academic simulation of this rule | **None found.** The farmer-side projects we found do not model it. |

**What the pitch may say:** "We did not find a published simulation of the guidelines' 10-parcel localized survey." Do not say "first", "novel", "nobody has", or "no one has noticed sampling".

Before the final deck, one person should spend 15 minutes on Google Scholar with: "localized calamity" PMFBY sample survey; "wide-spread localized"; PMFBY "10" parcels loss assessment.

## 7. Closest existing products

| Product | What it does | Who it serves | Plot-level? | Satellite? | Gap against us |
|---|---|---|---|---|---|
| [Proof of Loss](https://github.com/Sarcastic-Soul/proof-of-loss) (open source, AWS hackathon) | "A Strands Agents SDK agent that helps small farmers in India report crop damage in time". Takes Hindi, Hinglish or English, photos; returns a claim packet with deadline, photo time and GPS, weather check. It also reasons that weather grids can miss a local hailstorm. | **Farmers** | Photo-level | Not in the README we read | **Closest pitch.** Same 72-hour framing, and same point about weather grids. No satellite placebo test or recomputation seen. Judges could find this. |
| [CropSnap (Agtuall, ESA-supported)](https://business.esa.int/projects/cropsnap) | "a smartphone-based crop monitoring system that empowers farmers and insurers alike"; combines farmer photos, Sentinel-1 and Sentinel-2, and weather for damage assessment. Targets India. Status: ongoing. | "Insurance Companies (Primary Segment)", loss adjusters | Yes | Yes | **Closest technology: the same satellites as ours.** Insurer-first, and we saw no public recomputation. |
| Farmonaut | Vendor pages describe satellite monitoring through consumer apps ("field-by-field advice on crop health") and crop loan and insurance verification for institutions. | Farmers and institutions | Field-level monitoring (vendor claim) | Yes | **A farmer can already buy field-level satellite monitoring**, so "no farmer can see this" is false. We did not find it producing claim evidence. Vendor claims only; product not tested. |
| [Picture-based insurance (HDFC Ergo study)](https://www.3ieimpact.org/sites/default/files/2020-06/FE-TW13.1038-PBI-India.pdf) | Farmers' repeat smartphone photos reduce basis risk at plot level. | Research with an insurer | Yes | No | A precedent for farmer-side, plot-level evidence. |
| [AgRISE (IWMI)](https://www.iwmi.org/news/press-release-mobile-phone-app-launched-to-strengthen-new-insurance-scheme-for-indias-farmers/) | Satellite and climate crop health card "enables insurers and government agencies to estimate crop damage". | Insurers, government | No | Yes | Not for farmers. |
| CROPIC, CLAP, YES-TECH | Government photo, survey and yield tools. | Insurers, States, surveyors | CLAP at field level; YES-TECH at GP level | YES-TECH yes | Farmers are data sources, not users of the output. |

**Honest answer to "does a farmer-side, plot-level evidence tool exist?"** Parts of it do. Farmer-side claim help exists, plot-level satellite monitoring is sold to farmers, and insurer-side plot assessment exists. We did not find a tool that combines them into a farmer-owned, placebo-tested record of a specific loss that anyone can recompute. That combination is the claim to make. Our EOfactory and Bajaj link could not be opened on 31 Oct, so it is not assessed here.

## 8. Official wording worth quoting

- "Enrolled farmer has no need to file the claims. Claims of enrolled and eligible farmers are automatically worked out based on the shortfall in yield as reported by the State Government concerned." (Lok Sabha Q25, 21 Jul 2026)
- "In this case, farmers have to intimate the loss within 72 hours of the loss by calling on the toll-free number i.e. 14447." (same, on localized and post-harvest losses)
- "The financial assistance provided under SDRF and NDRF is by way of relief and not for compensation of losses suffered/ claimed." (Lok Sabha Q3825, 11 Aug 2026). Input subsidy and insurance are separate tracks.
