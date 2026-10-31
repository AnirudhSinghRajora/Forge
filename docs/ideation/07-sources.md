# 07 — Sources & Live Checks

Researched 31 Oct 2026. Sources marked *(secondary)* are exam-prep, blogs or aggregators. Verify them against primary documents before quoting them on a slide.

## Live API checks (31 Oct 2026)

Run from our cloud build container (not an Indian network):

| Endpoint | HTTP | Result |
|---|---|---|
| `planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a` | 200 | Collection available |
| STAC search `sentinel-2-l2a` @ Sirsa (75.03, 29.53), 10–31 Oct 2026 | 200 | Scenes 13, 15, 18, 23, 28 Oct; 18 & 28 Oct ≈ 0% cloud |
| STAC search `sentinel-1-rtc` @ Sirsa, 10–31 Oct 2026 | 200 | Passes 12, 16, 24, 28 Oct |
| STAC search `sentinel-2-l2a` @ (76.08, 29.06), Oct 2026 | 200 | Scenes through 30 Oct 2026 |
| `sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml` | 200 | 100 live CAP alerts (Telugu, Kannada, …) |
| `power.larc.nasa.gov/api/temporal/daily/point` | 200 | Daily T2M returned |
| `api.open-meteo.com/v1/forecast` | 200 | OK |
| `archive-api.open-meteo.com/v1/archive` | 429 | Daily limit exceeded (shared IP): cache or use a key |
| `api.data.gov.in/resource/9ef84268-…` (mandi prices) | timeout | Unreachable from container; test from India |
| `factchecktools.googleapis.com/v1alpha1/claims:search` | 403 | Requires API key (free) |
| `api.gdeltproject.org/api/v2/doc/doc` | 429 | Rate limit: 1 req / 5 s |
| STAC search `sentinel-2-l2a` @ Sangrur, Punjab (75.84, 30.24), 15–31 Oct 2026 | 200 | Clear (0%) scenes 18, 20, 22, 25, 28 Oct |
| `firms.modaps.eosdis.nasa.gov/api/area/csv/…` | 400 | Reachable; "Invalid MAP_KEY" with DEMO_KEY, so register a free key |
| `agmarknet.gov.in`, `api.agmarknet.gov.in` | 403 | Blocked from non-Indian network |
| `enam.gov.in/web/` | 200 | Reachable |

## Competition
- Event page and rules: user-supplied screenshots and text (Forge '26, NxtWave Launchpad)
- [OpenAI Academy × NxtWave Buildathon finale, Feb 2026](https://businessnewsthisweek.com/news/openai-academy-x-nxtwave-buildathon-maharashtra-team-wins-indias-largest-genai-student-challenge-at-india-ai-impact-summit-2026/)
- [Students showcase GenAI solutions (letsdatascience)](https://letsdatascience.com/news/students-showcase-deployment-ready-genai-solutions-at-india-ab05fef4)

## Idea #1: crop insurance, satellites, agriculture
- [Tribune: Haryana crop insurance row (CCE ₹450 cr vs satellite)](https://www.tribuneindia.com/news/haryana/crop-insurance-row-hooda-seeks-probe-compensation)
- [IASGyan: PMFBY systemic failures (Rajasthan ₹947.72 cr pending)](https://www.iasgyan.in/daily-current-affairs/pradhan-mantri-fasal-bima-yojana-systemic-failures) *(secondary)*
- [Global Agriculture: Why PMFBY is being questioned](https://www.global-agriculture.com/india-region/why-is-indias-pradhan-mantri-fasal-bima-yojana-being-questioned/) *(secondary)*
- [Rural Voice: why farmers face low payouts and rejections](https://eng.ruralvoice.in/fasal-bima-why-farmers-face-low-payouts-and-claim-rejections)
- [101Reporters: Fasal Bima and the art of minimising payouts](https://101reporters.com/article/agriculture/Fasal_Bima_Yojana_and_the_art_of_minimising_payouts)
- [Lok Sabha answer AS36 (YES-TECH 30% weightage; delays)](https://eparlib.sansad.in/bitstream/123456789/3015769/1/AS36_U80S8R.pdf)
- [Lok Sabha answer AS125 (claims 2020-21 to 2024-25)](https://eparlib.sansad.in/bitstream/123456789/2993761/1/AS125_opgcdx.pdf)
- [Drishti IAS: PMFBY 28 Jul 2025](https://www.drishtiias.com/daily-updates/daily-news-analysis/pradhan-mantri-fasal-bima-yojana-10/print_manually) *(secondary)*
- [Bajaj Allianz PMFBY claim process (72 h rule)](https://www.bajajallianz.com/pradhan-mantri-fasal-bima-yojana.html)
- [Kshema: when to file a crop insurance claim](https://kshema.co/when-to-file-a-crop-insurance-claim/)
- [Vassar Labs: YES-TECH explained (IU-level, 5–30 m)](https://vassarlabs.com/yes-tech-explained-how-satellites-estimate-crop-yield-for-insurance/)
- [APSAC YES-TECH presentation](https://apsac.ap.gov.in/wp-content/uploads/2023/01/Document3.pdf)
- [Takshashila: CROPIC](https://takshashila.org.in/content/blogs/20250801-CROPIC.html)
- [ESA CropSnap](https://business.esa.int/projects/cropsnap)
- [IWMI AgRISE press release](https://www.iwmi.org/news/press-release-mobile-phone-app-launched-to-strengthen-new-insurance-scheme-for-indias-farmers/)
- [EOfactory × Bajaj Allianz case study](https://EOfactory.ai/documents/Bajaj_Allianz_x_EOfactory_digital_case_study.pdf)
- [UNI: Sirsa/Fatehabad rain & hail damage, 25 Oct 2026](https://www.uniindia.com/north-india/agriculture-haryana-selja-crops-damage/224950)
- [UNI: UP digital crop damage survey, Oct 2026](https://www.uniindia.com/north-india/agri-up-crop-damage-digital-survey/204850)
- [Copernicus Data Space: Sentinel-2 L2A](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html)
- [Copernicus: Statistical API time series](https://documentation.dataspace.copernicus.eu/notebook-samples/sentinelhub/Statistical_API_basic_timeseries_visualisations.html)
- [spyndex Planetary Computer tutorial](https://spyndex.readthedocs.io/en/stable/tutorials/pc.html)
- [World Bank blog: AI advice for small-scale producers](https://blogs.worldbank.org/en/agfood/can-ai-give-small-scale-producers-the-right-advice-)
- [IndiaAI: Farmer.Chat use case](https://aikosh.indiaai.gov.in/home/use-cases/details/farmerchat_ai_powered_agricultural_advisory_at_scale.html)

## Idea #2: AgniDrishti (stubble burning)
- [The Week/PTI: satellites missing most farm fires (iFOREST 2025)](https://www.theweek.in/wire-updates/national/2025/12/08/del43-env-stubble-burning-report.html)
- [The Wire: govt data on farm fires doesn't paint the entire picture](https://thewire.in/environment/govt-data-on-farm-fires-does-not-paint-entire-picture-says-new-report)
- [Tribune: satellites miss majority of stubble fires](https://www.tribuneindia.com/news/delhi/satellites-miss-majority-of-stubble-fires-delhi-air-pollution-underestimated-report)
- [Daily Pioneer: over 90% of large farm fires go undetected](https://dailypioneer.com/news/over-90-of-large-farm-fires-in-punjab-haryana-now-go-undetected)
- [ThePrint: CAQM assessing intensity instead of counts](https://theprint.in/india/caqm-assessing-intensity-of-stubble-fires-instead-of-relying-on-fire-counts-in-haryana-punjab/3034123/)
- [Scroll: SC to examine satellite evasion (Nov 2025)](https://scroll.in/latest/1088511/sc-to-examine-if-punjab-haryana-farmers-are-evading-satellite-surveillance-to-burn-crop-stubble)
- [Scroll: satellite tracking underreports stubble burning](https://scroll.in/latest/1089140/scroll_in)
- [LiveLaw: SC seeks 24/7 monitoring](https://www.livelaw.in/amp/top-stories/supreme-court-seeks-247-monitoring-of-stubble-burning-says-state-officials-cannot-help-farmers-avoid-satellite-detection-276663)
- [Drishti: discrepancies in satellite data on farm fires](https://www.drishtiias.com/daily-updates/daily-news-analysis/discrepancies-in-satellite-data-on-farm-fires) *(secondary)*
- [CivilsDaily: CAQM–Punjab–ISRO talks on tracking](https://www.civilsdaily.com/news/air-quality-panel-holding-talks-with-punjab-govt-and-isro-over-tracking-of-stubble-fires/) *(secondary)*
- [Tribune: Haryana ₹1,200/acre residue incentive explainer](https://www.tribuneindia.com/news/haryana/explainer-haryana-targets-further-drop-in-stubble-burning-after-39-per-cent-decline)
- [UNI: Jhajjar administration on stubble (Oct 2026)](https://www.uniindia.com/north-india/admin-jhajjar-farmers-stubble/220083)
- [Tribune: delays in CRM incentives](https://www.tribuneindia.com/news/haryana/delays-in-crop-residue-management-incentives-may-discourage-farmers/amp)
- [Lok Sabha AU1592 (CRM / custom hiring centres)](https://eparlib.sansad.in/bitstream/123456789/2998167/1/AU1592_zf34Ss.pdf)

## Idea #3: TraceBack (misinformation, deepfakes, scams)
- [IANS: deepfake videos on China/Arunachal, 27 Oct 2026](https://ianslive.in/nalin-kohli-slams-congress-over-sharing-deepfake-videos-on-china-arunachal-pradesh--20261027180703)
- [Newsmobile: Rajnath Singh did not make this statement](https://www.newsmobile.in/nm-fact-checker/verified-rajnath-singh-did-not-make-this-statement-on-india-china-border-dispute/)
- [Newschecker: Western Command chief claim](https://newschecker.in/fact-check/fact-check/did-former-western-command-chief-allege-chinese-incursion-in-arunachal-pradesh)
- [Outlook: Janhvi Kapoor deepfake](https://www.outlookindia.com/art-entertainment/south-cinema/janhvi-kapoor-ai-deepfake-video-what-happened-and-what-indian-law-says)
- [Meta: MCA WhatsApp helpline](https://about.fb.com/news/2024/02/mcas-whatsapp-helpline-curbing-the-spread-of-ai-generated-misinformation/)
- [MediaNama: DAU report, only 2% deepfakes](https://www.medianama.com/2024/09/223-deepfake-analysis-unit-report-most-media-alterations-done-with-basic-tools-only-2-deepfakes/)
- [MediaNama: MeitY IT Rules amendments on synthetic media (Feb 2026)](https://www.medianama.com/2026/02/223-meity-amendments-it-rules-synthetic-media-deepfakes/)
- [Hogan Lovells: mandatory AI labelling & 3-hour takedown](https://www.hoganlovells.com/en/publications/india-introduces-mandatory-labelling-for-ai-and-3hour-takedown-for-illegal-content)
- [Freshfields: MeitY 2026 changes](https://technologyquotient.freshfields.com/post/102mjwn/india-targets-deepfakes-and-ai-generated-content-key-changes-under-meitys-2026)
- [iPleaders: IT Rules 2026](https://blog.ipleaders.in/it-rules-2026/)
- [McAfee India press release, Feb 2026](https://www.mcafee.com/en-in/consumer-corporate/newsroom/press-releases/2026/20260204-1.html)
- [MediaNama: Truecaller AI voice scanner (regional-language gap)](https://www.medianama.com/2024/05/223-truecaller-ai-voice-scanner-spam-call/)
- [arXiv: regional-language deepfake dataset gap](https://arxiv.org/html/2411.15457v1)
- [Telangana Today: ₹1.95 lakh lost to fake PM-Kisan APK](https://telanganatoday.com/hyderabad-man-duped-of-rs-1-95-lakh-via-fake-pm-kisan-apk)
- [NewsOnAir: Nagaland Police alert on PM-Kisan APK](https://www.newsonair.gov.in/nagaland-police-issues-alert-on-malicious-pm-kisan-yojana-apk-file-circulating-across-state)
- [Digit: fake PM-Kisan WhatsApp link](https://www.digit.in/news/general/hyderabad-man-loses-rs-1-9-lakh-to-fake-pm-kisan-scheme-offer-via-whatsapp-link-heres-what-happened.html/amp/)
- [Deccan Chronicle: PIB warns on fake RBI APKs](https://deccanchronicle.com/nation/rbi-did-not-send-whatsapp-apk-notices-warns-pib-fact-check-1963061)
- [CareerIndia: fake PM-Kisan ₹4,000 grant](https://www.careerindia.com/features/pm-kisan-4000-raksha-bandhan-grant-fact-check-viral-ai-videos-fake-claims-011-64505.html)
- [Vastav AI (TraceX Labs)](https://completeaitraining.com/news/tracex-labs-develops-vastav-ai-deepfake-detection-platform/) *(secondary)*
- [OpenAI: advancing content provenance (May 2026)](https://openai.com/index/advancing-content-provenance)
- [C2PA viewer: verifying AI images with C2PA/SynthID](https://c2paviewer.com/articles/verify-ai-generated-image-c2pa-synthid) *(secondary)*

## Runner-up: Nigrani (civic grievances)
- [PIB/DARPG CPGRAMS report, Sep 2025](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/sep/doc2025915637301.pdf)
- [PIB/DARPG CPGRAMS report, Nov 2025](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251110688501.pdf)
- [PIB/DARPG report, Feb 2026](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/feb/doc2026216792801.pdf)
- [NPS circular on CPGRAMS resolution, Feb 2025](https://www.npscra.proteantech.in/download/Circular%20dated%2024.02.2025%20resolution%20of%20grievances%20on%20CPGRAMS_Eng_Version.pdf)
- [LiveLaw: Karnataka HC pothole case](https://www.livelaw.in/high-court/karnataka-high-court/karnataka-high-court-pothole-crisis-bbmp-claims-potholes-545776)
- [Siasat: HC seeks report from GBA](https://www.siasat.com/bengaluru-pothole-case-hc-seeks-detailed-report-from-gba-3524712/)
- [ThePrint: pothole death & public anger](https://theprint.in/india/a-pothole-death-ignites-public-anger-against-shivakumar-govt-minister-santosh-lads-remarks-fuel-bonfire/3014128/)
- [South First: pothole-free deadline](https://thesouthfirst.com/karnataka/karnataka-governments-pothole-free-bengaluru-deadline-nears-but-roads-remain-in-ruins)
- [Deccan Herald: Bengaluru tops NCRB civic negligence deaths](https://www.deccanherald.com/india/karnataka/bengaluru/bengaluru-tops-ncrbs-chart-for-civic-negligence-deaths-for-4th-successive-year-3748656)
- [TNM: pothole deaths cover-up investigation](https://www.thenewsminute.com/karnataka/tnm-investigation-bbmp-and-cops-cover-13-pothole-deaths-bengaluru-170088)

## ScholarFlow / scholarships
- [The Wire: 12 lakh fewer SC students get PMS](https://thewire.in/education/12-lakh-fewer-sc-students-get-scholarships-under-pms)
- [PIB blog on scheme awareness](https://www.pib.gov.in/blogs/blogsdescr.aspx?feaaid=562)
- [DT Next: CAG on SC/ST scholarships (TN)](https://www.dtnext.in/news/tamilnadu/cag-audit-flags-gaps-in-scst-scholarship-schemes-rs-1253-crore-in-irregulardelayed-payments)
- [Careers360: NSP 2026-27 registration](https://school.careers360.com/articles/nsp-scholarship-registration-2026-27) *(secondary)*
- [IndiaScholarships: NSP 2026-27 OTR & biometric guide](https://www.indiascholarships.in/news/nsp-scholarship-2026-27-portal-opening-otr-guidelines) *(secondary)*
- [CareerIndia: NSP deadlines before 31 Oct](https://www.careerindia.com/news/nsp-2026-27-scholarship-portal-deadlines-verification-guide-011-66633.html) *(secondary)*

## Other longlist ideas
- [PIB: eNAM factsheet (Apr 2026)](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/apr/doc2026413845801.pdf)
- [Lok Sabha AU2721 (eNAM app: mandis within 100 km)](https://eparlib.nic.in/bitstream/123456789/1056260/1/AU2721.pdf)
- [RBI WP 08/2024: TOP vegetables value chain (farmer share 33/36/37%)](https://website.rbi.org.in/documents/87730/30842423/WPS+No.+8%2C+2024+-+Vegetables+Inflation+in+India.pdf)
- [Business Standard: RBI study on farmer share](https://www.business-standard.com/amp/markets/capital-market-news/rbi-study-shows-tomato-onion-and-potato-farmers-get-only-a-third-of-retail-price-that-consumer-pays-124100400307_1.html)
- [ICAR: onion price forecasting (Varanasi)](https://epubs.icar.org.in/index.php/IJAgS/article/view/111603)
- [Outlook Business: why farmers dump crops (May 2026)](https://www.outlookbusiness.com/amp/story/industry/why-farmers-dump-crops-despite-rising-food-prices)
- [UNI: Karnataka tomato price crash protests (Aug 2026)](https://test.uniindia.com/news/business-economy/tomoto-price-crash-karnataka/3939873.html)
- [data.gov.in: current daily mandi prices](https://data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi)
- [The Wire: heatwaves and workers](https://thewire.in/labour/the-scorching-reality-indias-heatwaves-and-the-plight-of-workers)
- [The Leaflet: auditing Delhi's Heat Action Plan](https://theleaflet.in/governance-and-policy/auditing-delhis-heat-action-plan-a-ground-study-part-i)
- [Insights: India's Heat Action Plans (2026)](https://www.insightsonindia.com/2026/05/15/upsc-editorial-analysis-indias-heat-action-plans-2026/) *(secondary)*
- [Vikaspedia: National Disaster Alert Portal (SACHET)](https://en.vikaspedia.in/social-welfare/disaster-management-1/national-disaster-alert-portal)
- [Sphere India SitRep, Aug 2026](https://www.sphereindia.org.in/sites/default/files/2026-08/02.08.2026%20SitRep-%205%20Extreme%20Weather%20Events%20in%20India.pdf)

## Gemini API (build tooling)
- [Gemini 3 developer guide](https://ai.google.dev/gemini-api/docs/gemini-3)
- [Gemini API changelog (built-in tools + function calling combination, Mar 2026)](https://ai.google.dev/gemini-api/docs/changelog)
- [Firebase AI Logic: grounding with Google Search (supported models)](https://firebase.google.com/docs/ai-logic/grounding-google-search)
- [Firebase AI Logic locations (Gemini 2.5 shutdown notice, Oct 2026)](https://firebase.google.com/docs/ai-logic/locations?api=vertexai)
- [Cloud Text-to-Speech: Gemini-TTS languages (hi-IN GA, pa-IN preview)](https://cloud.google.com/text-to-speech/docs/gemini-tts)
