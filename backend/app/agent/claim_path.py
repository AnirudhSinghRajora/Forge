"""The claim-path router: which PMFBY route a report is on, before any deadline is mentioned.

Deterministic, from the peril lists and rules in key_rules.json. State notification is never assumed:
it is always listed as unknown until verified, because no notification has been verified here. Every
output honours the `do_not_say` and `app_rule` entries in that file: no "late means rejected", no
promise that evidence will be accepted, and no insurer named.

Telugu strings NEED NATIVE REVIEW: they have not been checked by a native speaker.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.evidence.schema import ClaimPath, Deadline
from app.tools import actions

LOCALIZED_BASIS = "21.5.10/Table-10/row-1/schedule"
POST_HARVEST_BASIS = "21.6.11/Table-11/row-1/schedule"

# Our event types mapped onto the guideline's peril names (key_rules.json, `perils`).
_PERIL = {
    "hail": "hailstorm",
    "flood": "inundation",
    "cyclone": "cyclone",
    "unseasonal_rain": "unseasonal_rain",
    "wind": "storm",
    "pest": "widespread_pest_disease",
    "drought": "drought",
}

TEXT = {
    # Reasons
    "not_insured": (
        "आपने बताया कि इस मौसम में आपकी फ़सल का बीमा नहीं है, इसलिए फ़सल बीमा का दावा इस रास्ते पर नहीं बनता।",
        "You said this crop is not insured this season, so there is no PMFBY claim on this route.",
        "ఈ సీజన్‌లో మీ పంటకు బీమా లేదని చెప్పారు, కాబట్టి ఈ మార్గంలో PMFBY క్లెయిమ్ ఉండదు.",
    ),
    "insured_unknown": (
        "पहले यह जानना ज़रूरी है: क्या इस मौसम में आपकी फ़सल का बीमा है? ऋण वाले किसान अपने बैंक से पूछ सकते हैं।",
        "First we need to know: is this crop insured this season? If you have a crop loan, your bank can tell you.",
        "ముందు ఇది తెలియాలి: ఈ సీజన్‌లో మీ పంటకు బీమా ఉందా? పంట రుణం ఉంటే మీ బ్యాంకును అడగవచ్చు.",
    ),
    "stage_unknown": (
        "यह भी ज़रूरी है: घटना के समय फ़सल खड़ी थी, कटकर खेत में सूख रही थी, या कटकर रखी जा चुकी थी?",
        "We also need to know: was the crop standing, cut and drying in the field, or already stored at the time?",
        "ఇది కూడా తెలియాలి: ఆ సమయంలో పంట నిలబడి ఉందా, కోసి పొలంలో ఆరబెట్టారా, లేక నిల్వ చేశారా?",
    ),
    "event_unknown": (
        "नुकसान का प्रकार साफ़ नहीं है, इसलिए रास्ता अभी तय नहीं हो सकता।",
        "The type of loss is not clear, so the route cannot be settled yet.",
        "నష్టం రకం స్పష్టంగా లేదు, కాబట్టి మార్గం ఇప్పుడే తేల్చలేము.",
    ),
    "localized": (
        "खड़ी फ़सल पर यह नुकसान स्थानीय आपदा के अतिरिक्त कवर में आता है, अगर आपके राज्य ने यह कवर और आपकी फ़सल अधिसूचित की है।",
        "On a standing crop this falls under the localized calamity add-on, if your State has notified this cover and this crop.",
        "నిలబడిన పంటపై ఈ నష్టం స్థానిక విపత్తు అదనపు కవర్ కిందకు వస్తుంది, మీ రాష్ట్రం ఈ కవర్‌ను, ఈ పంటను నోటిఫై చేసి ఉంటే.",
    ),
    "post_harvest": (
        "कटकर खेत में सूख रही फ़सल (कटाई से 14 दिन तक) का नुकसान कटाई-बाद के अतिरिक्त कवर में आता है, अगर राज्य ने यह कवर और फ़सल अधिसूचित की है।",
        "Loss to a crop cut and drying in the field (up to 14 days from harvesting) falls under the post-harvest add-on, if the State has notified this cover and this crop.",
        "కోసి పొలంలో ఆరబెడుతున్న పంట నష్టం (కోత నుంచి 14 రోజుల వరకు) కోత అనంతర అదనపు కవర్ కిందకు వస్తుంది, రాష్ట్రం ఈ కవర్‌ను, పంటను నోటిఫై చేసి ఉంటే.",
    ),
    "area_yield": (
        "खड़ी फ़सल पर यह नुकसान मूल क्षेत्र-उपज कवर में आता है। इसमें हर किसान की अलग सूचना ज़रूरी नहीं है; उपज का हिसाब बीमा इकाई के स्तर पर फ़सल कटाई प्रयोगों और तकनीकी अनुमानों से होता है।",
        "On a standing crop this falls under basic area-yield cover. An individual intimation is not essential here; yield is worked out at insurance-unit level from crop cutting experiments and technology estimates.",
        "నిలబడిన పంటపై ఈ నష్టం ప్రాథమిక విస్తీర్ణ-దిగుబడి కవర్ కిందకు వస్తుంది. ఇక్కడ వ్యక్తిగత సమాచారం తప్పనిసరి కాదు; దిగుబడిని బీమా యూనిట్ స్థాయిలో పంట కోత ప్రయోగాలు, సాంకేతిక అంచనాల ద్వారా లెక్కిస్తారు.",
    ),
    "paddy_inundation": (
        "धान में जलभराव को अलग खेत के स्तर पर कवर माना जाए या नहीं, इस पर सरकारी बयान आपस में मेल नहीं खाते। राज्य की अधिसूचना या 14447 से पुष्टि करनी होगी।",
        "Official statements conflict on whether paddy inundation is covered per field. The State notification or 14447 must confirm it.",
        "వరిలో ముంపు నష్టం వ్యక్తిగత పొలం స్థాయిలో కవర్ అవుతుందా అనే విషయంలో అధికారిక ప్రకటనలు ఒకదానికొకటి సరిపోలడం లేదు. రాష్ట్ర నోటిఫికేషన్ లేదా 14447 ద్వారా నిర్ధారించుకోవాలి.",
    ),
    "rain_standing": (
        "बेमौसम बारिश का नाम मूल कवर की सूची में अलग से नहीं है, इसलिए 14447 से पुष्टि कर लें।",
        "Unseasonal rain is not named separately in the basic cover list, so please confirm with 14447.",
        "అకాల వర్షం ప్రాథమిక కవర్ జాబితాలో విడిగా లేదు, కాబట్టి 14447 ద్వారా నిర్ధారించుకోండి.",
    ),
    "stored": (
        "कटाई-बाद का कवर खेत में सूख रही फ़सल के लिए है। रखी जा चुकी फ़सल का रास्ता दिशानिर्देशों में साफ़ नहीं मिला, इसलिए 14447 से पूछें।",
        "Post-harvest cover is for a crop drying in the field. We found no clear route for a crop already stored, so please ask 14447.",
        "కోత అనంతర కవర్ పొలంలో ఆరబెడుతున్న పంటకు. నిల్వ చేసిన పంటకు స్పష్టమైన మార్గం మార్గదర్శకాల్లో కనిపించలేదు, కాబట్టి 14447 ని అడగండి.",
    ),
    "not_listed_post_harvest": (
        "यह नुकसान कटाई-बाद के कवर की सूची में नहीं है, इसलिए रास्ता साफ़ नहीं है। 14447 से पूछें।",
        "This peril is not on the post-harvest cover list, so the route is not clear. Please ask 14447.",
        "ఈ నష్టం కోత అనంతర కవర్ జాబితాలో లేదు, కాబట్టి మార్గం స్పష్టంగా లేదు. 14447 ని అడగండి.",
    ),
    # Next steps
    "confirm_notification": (
        "अपने बैंक या 14447 से पुष्टि करें कि आपके राज्य ने यह कवर और आपकी फ़सल अधिसूचित की है।",
        "Confirm with your bank or 14447 that your State has notified this cover and your crop.",
        "మీ రాష్ట్రం ఈ కవర్‌ను, మీ పంటను నోటిఫై చేసిందో లేదో మీ బ్యాంకు లేదా 14447 ద్వారా నిర్ధారించుకోండి.",
    ),
    "report_now": (
        "नियम 72 घंटे में सूचना देने को कहता है। क्रॉप इंश्योरेंस ऐप या कृषि रक्षक पोर्टल और हेल्पलाइन 14447 से सूचना दें और संदर्भ संख्या संभालकर रखें।",
        "The rule asks for intimation within 72 hours. Report through the Crop Insurance App or the Krishi Rakshak Portal and Helpline 14447, and keep the reference number.",
        "నియమం 72 గంటల్లో సమాచారం ఇవ్వమని చెబుతోంది. క్రాప్ ఇన్సూరెన్స్ యాప్ లేదా కృషి రక్షక్ పోర్టల్, హెల్ప్‌లైన్ 14447 ద్వారా తెలియజేసి రిఫరెన్స్ నంబర్ దాచుకోండి.",
    ),
    "late": (
        actions.LAPSED_HI,
        actions.LAPSED_EN,
        "నియమం 72 గంటల్లో సమాచారం ఇవ్వమని చెబుతోంది. ఆ సమయం దాటినా ఇప్పుడే తెలియజేసి రిఫరెన్స్ నంబర్ దాచుకోండి; సర్వే సమయంలో అందిన సమాచారాన్ని కూడా పరిగణిస్తామని మార్గదర్శకాలు చెబుతున్నాయి.",
    ),
    "filed": (
        "आपने सूचना दर्ज कर दी है। संदर्भ संख्या संभालकर रखें और सर्वे के समय खेत पर रहें।",
        "You have recorded your intimation. Keep the reference number and be present at the field for the survey.",
        "మీ సమాచారం నమోదైంది. రిఫరెన్స్ నంబర్ దాచుకోండి, సర్వే సమయంలో పొలంలో ఉండండి.",
    ),
    "photos": (
        "खेत की तारीख़ वाली तस्वीरें लेकर रखें। फ़सल काटने से पहले तस्वीरें ज़रूर लें।",
        "Keep dated photographs of the field, and take them before any harvesting.",
        "పొలం ఫోటోలు తేదీతో సహా తీసి ఉంచండి, కోతకు ముందే తీయండి.",
    ),
    "area_track": (
        "अपने बैंक या 14447 से जानें कि आपके बीमा इकाई क्षेत्र में फ़सल कटाई प्रयोग कब होंगे। अगर नतीजा ग़लत लगे तो 14447 या तहसील के शिकायत अधिकारी के पास शिकायत कर सकते हैं।",
        "Ask your bank or 14447 when crop cutting experiments will run in your insurance unit. If the result looks wrong, you can raise a grievance through 14447 or the tehsil grievance officer.",
        "మీ బీమా యూనిట్‌లో పంట కోత ప్రయోగాలు ఎప్పుడో మీ బ్యాంకు లేదా 14447 ని అడగండి. ఫలితం తప్పుగా అనిపిస్తే 14447 లేదా తహసీల్ ఫిర్యాదుల అధికారి ద్వారా ఫిర్యాదు చేయవచ్చు.",
    ),
    "contest": (
        "सर्वे के नतीजे से असहमत हों तो 7 दिन के भीतर सबूतों के साथ लिखित सूचना दे सकते हैं, और 14447 या तहसील के शिकायत अधिकारी के पास शिकायत कर सकते हैं।",
        "If you disagree with a survey, you can give written notice with proofs within 7 days, and raise a grievance through 14447 or the tehsil grievance officer.",
        "సర్వే ఫలితంతో ఏకీభవించకపోతే 7 రోజుల్లోగా ఆధారాలతో లిఖిత నోటీసు ఇవ్వవచ్చు, 14447 లేదా తహసీల్ ఫిర్యాదుల అధికారి ద్వారా ఫిర్యాదు చేయవచ్చు.",
    ),
    "tell_neighbours": (
        "अगर आसपास के किसानों को भी नुकसान हुआ है, तो उन्हें भी सूचना देने को कहें। 25% वाले नियम में भुगतान उन्हीं का बनता है जिन्होंने सूचना दी।",
        "If neighbouring farmers also had losses, tell them to report too. Under the 25% rule, only those who gave intimation are covered by it.",
        "చుట్టుపక్కల రైతులకూ నష్టం జరిగితే, వారినీ సమాచారం ఇవ్వమని చెప్పండి. 25% నియమం సమాచారం ఇచ్చిన వారికే వర్తిస్తుంది.",
    ),
    "answer_questions": (
        "ऊपर के सवालों के जवाब दें, ताकि सही रास्ता बताया जा सके।",
        "Please answer the questions above so that the right route can be shown.",
        "సరైన మార్గం చెప్పడానికి పై ప్రశ్నలకు సమాధానం ఇవ్వండి.",
    ),
    "if_addon_72": (
        "अगर आप बीमित हैं और यह स्थानीय आपदा या कटाई-बाद के कवर में आता है, तो नियम घटना से 72 घंटे में सूचना देने को कहता है। इसलिए देर न करें: 14447 से पूछ लें।",
        "If you are insured and this falls under the localized or post-harvest cover, the rule asks for intimation within 72 hours of the event. So do not wait: ask 14447 now.",
        "మీకు బీమా ఉండి, ఇది స్థానిక విపత్తు లేదా కోత అనంతర కవర్ కిందకు వస్తే, నియమం సంఘటన నుంచి 72 గంటల్లో సమాచారం ఇవ్వమంటుంది. ఆలస్యం చేయకుండా 14447 ని అడగండి.",
    ),
    "where_insurer": (
        "आपकी बीमा कंपनी का नाम आपके PMFBY आवेदन या पॉलिसी की रसीद पर लिखा है।",
        "Your insurer's name is on your PMFBY application or policy receipt.",
        "మీ బీమా కంపెనీ పేరు మీ PMFBY దరఖాస్తు లేదా పాలసీ రసీదుపై ఉంటుంది.",
    ),
    # What the evidence is for
    "use_addon": (
        "यह सबूत आपकी सूचना के साथ रखने का एक सहायक रिकॉर्ड है। बीमा कंपनी घटना और उसकी गंभीरता पर \"कोई अन्य उपलब्ध सबूत\" जुटाती है, पर किसान के सैटेलाइट सबूत के लिए अलग से कोई नियम नहीं है और इसे माना ही जाएगा, ऐसा नहीं है।",
        "This is a supporting record to keep with your intimation. The insurer collects \"any other available evidence\" on occurrence and severity, but no clause provides for farmer-submitted satellite evidence, and acceptance is not guaranteed.",
        "ఇది మీ సమాచారంతో పాటు ఉంచుకోదగిన సహాయక రికార్డు. సంఘటన, తీవ్రతపై బీమా కంపెనీ \"అందుబాటులో ఉన్న ఇతర ఆధారాలు\" సేకరిస్తుంది, కానీ రైతు సమర్పించే ఉపగ్రహ ఆధారాలకు ప్రత్యేక నిబంధన లేదు, అంగీకారానికి హామీ లేదు.",
    ),
    "use_area": (
        "इस रास्ते पर दावा इकाई की उपज से तय होता है, आपके अकेले खेत से नहीं, इसलिए यह सबूत उसे तय नहीं करता। यह आपके खेत की तारीख़वार स्थिति का रिकॉर्ड है, जिसे आप शिकायत या कृषि अधिकारी से बात करते समय दिखा सकते हैं; इसे माना ही जाएगा, ऐसा नहीं है।",
        "On this route the outcome depends on the unit's yield, not on your plot alone, so this evidence does not decide it. It is a dated record of your field that you can show when raising a grievance or speaking to an agriculture officer; acceptance is not guaranteed.",
        "ఈ మార్గంలో ఫలితం యూనిట్ దిగుబడిపై ఆధారపడుతుంది, మీ ఒక్క పొలంపై కాదు, కాబట్టి ఈ ఆధారం దాన్ని నిర్ణయించదు. ఇది మీ పొలం స్థితి తేదీలతో కూడిన రికార్డు; ఫిర్యాదు చేసేటప్పుడు లేదా వ్యవసాయ అధికారితో మాట్లాడేటప్పుడు చూపించవచ్చు; అంగీకారానికి హామీ లేదు.",
    ),
    "use_uninsured": (
        "यह आपके खेत की तारीख़वार स्थिति का रिकॉर्ड है। इससे फ़सल बीमा का दावा नहीं बनता।",
        "This is a dated record of your field. It does not create a PMFBY claim.",
        "ఇది మీ పొలం స్థితి తేదీలతో కూడిన రికార్డు. దీని వల్ల PMFBY క్లెయిమ్ ఏర్పడదు.",
    ),
    "use_undetermined": (
        "रास्ता तय होने तक यह आपके खेत की तारीख़वार स्थिति का रिकॉर्ड है; इसे माना ही जाएगा, ऐसा नहीं है।",
        "Until the route is settled this is a dated record of your field; acceptance is not guaranteed.",
        "మార్గం తేలే వరకు ఇది మీ పొలం స్థితి తేదీలతో కూడిన రికార్డు; అంగీకారానికి హామీ లేదు.",
    ),
}
_LANG_INDEX = {"hi": 0, "en": 1, "te": 2}


def _t(key: str, lang: str) -> str:
    return TEXT[key][_LANG_INDEX.get(lang, 1)]


def _rules() -> dict:
    return (actions.load_key_rules() or {}).get("rules") or {}


def _cited(rule_name: str, *also: str) -> list[str]:
    ids = [str(c.get("clause_id")) for c in (_rules().get(rule_name) or {}).get("citations", [])]
    return list(dict.fromkeys([*also, *ids]))


def draw_applicability(route: str) -> str:
    """Para 21.5.8 only governs localized and post-harvest claims."""
    return "may_apply" if route in ("localized_addon", "post_harvest_addon") else "illustration_only"


def route_claim(
    insured: str | None,
    crop_stage: str | None,
    event_type: str | None,
    crop: str | None,
    lang: str = "en",
) -> ClaimPath:
    """Route only. Countdown status, which depends on time, is added by `with_deadline`."""
    insured = insured if insured in ("yes", "no") else "unknown"
    stage = crop_stage if crop_stage in ("standing", "cut_and_spread", "harvested_stored") else "unknown"
    rules = _rules()
    perils = rules.get("perils")
    if not perils or not rules.get("intimation_deadline"):
        return ClaimPath(
            route="undetermined", insured=insured, crop_stage=stage,
            reasons=[actions.UNAVAILABLE], unknowns=["policy_corpus"],
        )

    base = {"insured": insured, "crop_stage": stage}
    peril = _PERIL.get(event_type or "")
    localized = set(perils.get("localized_add_on") or [])
    post_harvest = set(perils.get("post_harvest_add_on") or [])
    has_addon_rule = peril in localized or peril in post_harvest

    if insured == "no":
        return ClaimPath(
            route="not_insured", intimation="not_essential", **base,
            reasons=[_t("not_insured", lang)], next_steps=[_t("photos", lang)],
            evidence_use=_t("use_uninsured", lang),
            clause_ids=_cited("when_individual_cover_is_available"),
        )

    unknowns: list[str] = []
    reasons: list[str] = []
    if insured == "unknown":
        unknowns.append("insured")
        reasons.append(_t("insured_unknown", lang))
    if stage == "unknown":
        unknowns.append("crop_stage")
        reasons.append(_t("stage_unknown", lang))
    if peril is None:
        unknowns.append("event_type")
        reasons.append(_t("event_unknown", lang))
    if unknowns:
        steps = [_t("answer_questions", lang)]
        if has_addon_rule or peril is None:
            steps.append(_t("if_addon_72", lang))
        steps.append(_t("photos", lang))
        return ClaimPath(
            route="undetermined", unknowns=unknowns, **base, reasons=reasons, next_steps=steps,
            evidence_use=_t("use_undetermined", lang),
            clause_ids=_cited("intimation_deadline", "5.5"),
        )

    notification_steps = [_t("confirm_notification", lang), _t("where_insurer", lang)]
    is_paddy = (crop or "").strip().lower() in ("paddy", "rice")

    if stage == "harvested_stored":
        return ClaimPath(
            route="undetermined", unknowns=["cover_for_stored_crop"], **base,
            reasons=[_t("stored", lang)], next_steps=[*notification_steps, _t("photos", lang)],
            evidence_use=_t("use_undetermined", lang), clause_ids=_cited("post_harvest_14_day"),
        )

    if stage == "cut_and_spread":
        if peril in post_harvest:
            return ClaimPath(
                route="post_harvest_addon", intimation="essential", **base,
                reasons=[_t("post_harvest", lang)],
                next_steps=[_t("report_now", lang), *notification_steps, _t("photos", lang),
                            _t("contest", lang)],
                evidence_use=_t("use_addon", lang),
                unknowns=["state_notification", "crop_notified", "days_since_harvest"],
                clause_ids=_cited("post_harvest_14_day", POST_HARVEST_BASIS, "21.6.6.1", "21.5.6.2"),
            )
        return ClaimPath(
            route="undetermined", unknowns=["cover_for_this_peril_after_cutting"], **base,
            reasons=[_t("not_listed_post_harvest", lang)],
            next_steps=[*notification_steps, _t("photos", lang)],
            evidence_use=_t("use_undetermined", lang), clause_ids=_cited("post_harvest_14_day"),
        )

    # A standing crop.
    if peril == "inundation" and is_paddy:
        return ClaimPath(
            route="area_yield_basic", intimation="unknown", **base,
            reasons=[_t("area_yield", lang), _t("paddy_inundation", lang)],
            next_steps=[*notification_steps, _t("area_track", lang), _t("photos", lang)],
            evidence_use=_t("use_area", lang), unknowns=["paddy_localized_inundation_cover"],
            clause_ids=_cited("perils", "21.5.10/Note-2", "5.5"),
        )
    if peril in localized:
        return ClaimPath(
            route="localized_addon", intimation="essential", **base,
            reasons=[_t("localized", lang)],
            next_steps=[_t("report_now", lang), *notification_steps, _t("tell_neighbours", lang),
                        _t("photos", lang), _t("contest", lang)],
            evidence_use=_t("use_addon", lang),
            unknowns=["state_notification", "crop_notified"],
            clause_ids=_cited("when_individual_cover_is_available", LOCALIZED_BASIS, "21.5.5.1",
                              "21.5.6.2", "21.5.8"),
        )
    reasons = [_t("area_yield", lang)]
    area_unknowns: list[str] = []
    if event_type == "unseasonal_rain":
        reasons.append(_t("rain_standing", lang))
        area_unknowns.append("unseasonal_rain_on_standing_crop")
    return ClaimPath(
        route="area_yield_basic", intimation="not_essential", **base, reasons=reasons,
        next_steps=[_t("area_track", lang), _t("photos", lang)],
        evidence_use=_t("use_area", lang), unknowns=area_unknowns,
        clause_ids=_cited("no_individual_intimation_for_widespread", "5.5", "2.17"),
    )


def with_deadline(
    path: ClaimPath, case_id: str, event_date: date | None, event_time: str | None,
    lang: str = "en", now: datetime | None = None,
) -> tuple[ClaimPath, list[Deadline]]:
    """Adds the time-dependent part. A live countdown applies only on an add-on route and only
    while the time is open. Lapsed uses the wording in key_rules.json: report anyway."""
    now = now or datetime.now(UTC)
    if path.route not in ("localized_addon", "post_harvest_addon") or event_date is None:
        return path, []
    rule = _rules().get("intimation_deadline") or {}
    hours = rule.get("hours")
    if not isinstance(hours, int | float):
        return path, []
    start, _assumed = actions.event_datetime(event_date, event_time)
    due = start + timedelta(hours=hours)
    submission = actions.submission_for(case_id) if case_id else None
    submitted = datetime.fromisoformat(submission["submitted_at"]) if submission else None
    status = actions.deadline_status(due, submitted, now)
    basis = LOCALIZED_BASIS if path.route == "localized_addon" else POST_HARVEST_BASIS
    deadline = Deadline(type="intimation_72h", due_at=due, basis=basis, status=status)
    updated = path.model_copy(deep=True)
    updated.countdown_applies = status == "open" and submission is None
    if submission is not None:
        updated.next_steps = [_t("filed", lang), *updated.next_steps[1:]]
    elif status == "lapsed":
        updated.next_steps = [_t("late", lang), *updated.next_steps[1:]]
        updated.clause_ids = list(dict.fromkeys([*updated.clause_ids, *_cited("late_intimation")]))
    return updated, [deadline]


def for_case(case, lang: str | None = None, now: datetime | None = None
             ) -> tuple[ClaimPath, list[Deadline]]:
    """The route for a Case row or anything with the same attributes."""
    lang = lang or case.lang
    path = route_claim(case.insured, case.crop_stage, case.event_type, case.crop, lang)
    return with_deadline(path, case.id, case.event_date, case.event_time, lang, now)
