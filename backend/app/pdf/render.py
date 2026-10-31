"""WeasyPrint evidence pack. Rendering happens on demand, from stored evidence, with no invention.

System needs: pango, harfbuzz and fontconfig for WeasyPrint, plus fonts with Devanagari and Telugu
(Noto Sans Devanagari, Noto Sans Telugu). Debian: libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b
libharfbuzz-subset0 fonts-noto-core.
"""
from __future__ import annotations

import base64
import io
import logging
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app import disclosures, errors
from app.agent import explain as explain_mod
from app.agent import rubric
from app.config import get_settings
from app.evidence.schema import Evidence
from app.pdf import charts
from app.tools import actions as actions_tool

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
_ENV = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "j2"]),
)

L = {
    "hi": {
        "title": "सैटेलाइट सबूत पत्र", "verdict": "नतीजा", "explanation": "सरल भाषा में", "testimony": "खेत की गवाही",
        "route": "आपके लिए रास्ता", "next": "आगे क्या करें", "use": "यह सबूत किस काम का है", "unknowns": "अभी जो पता नहीं",
        "deadline": "सूचना की समय-सीमा", "field": "खेत", "before_after": "पहले और बाद", "before": "पहले", "after": "बाद",
        "map": "खेत का नक्शा", "delta": "बदलाव का नक्शा", "placebo": "आसपास के मिलते-जुलते खेतों से तुलना", "far": "तूफ़ान के इलाक़े से बाहर के खेतों से तुलना (5-12 किमी)", "not_computed": "जो हिस्से नहीं बन पाए",
        "twin": "खेत का जुड़वाँ: जो मिलते-जुलते खेतों ने किया", "draw": "दस खेतों का ड्रॉ: एक ड्रॉ का औसत कितना हिल सकता है",
        "vanish": "बड़े खानों में खो जाता नुकसान", "weather": "मौसम (मॉडल का अनुमान)", "alerts": "सरकारी चेतावनियाँ", "news": "ख़बरें",
        "cross": "जिरह: सर्वेयर की आपत्तियाँ", "challenge": "आपत्ति", "finding": "जाँच का नतीजा", "outcome": "परिणाम",
        "clauses": "दिशानिर्देशों के अनुच्छेद", "scenes": "देखी गई तस्वीरें", "provenance": "हर आँकड़े का स्रोत",
        "hash": "सबूत की मुहर", "verify_note": "यह QR खोलकर कोई भी सार्वजनिक सैटेलाइट डेटा से सैटेलाइट के आँकड़े दोबारा निकाल सकता है।",
        "near": "सीमा के पास", "none": "कोई नहीं मिला", "no_data": "उपलब्ध नहीं", "generated": "बनाया गया",
        "disclaimer": "यह सबूत है, दावे का फ़ैसला नहीं। किसान के सैटेलाइट सबूत के लिए दिशानिर्देशों में अलग कोई नियम नहीं है और इसे माना ही जाएगा, ऐसा नहीं है।",
        "note_lang": "",
        "rebutted": "खंडन हुआ", "conceded": "मानी गई", "unresolved": "अनसुलझी",
        "open": "चालू", "met": "समय पर दी, किसान के अपने बताने के अनुसार", "lapsed": "समय निकल गया",
        "event": "घटना", "crop": "फ़सल", "district": "ज़िला", "clause": "अनुच्छेद", "time_assumed": "घटना के दिन की शुरुआत मानी गई",
        "scope": "सैटेलाइट के आँकड़े दोबारा निकाले जाते हैं; नतीजे और मौसम की जाँच केवल छेड़छाड़ के लिए होती है।",
        "tech_en": "तकनीकी कारण और सावधानियाँ (अंग्रेज़ी में)", "related": "संबंधित रिपोर्ट (नतीजे पर इनका असर नहीं)",
        "t_date": "तारीख़", "t_scene": "तस्वीर", "t_qa": "जाँच", "t_cloud": "बादल %", "t_reasons": "कारण",
        "t_field": "आँकड़ा", "t_source": "स्रोत", "t_asset": "फ़ाइल", "t_retrieved": "कब लिया", "t_value": "मान",
        "replay": "मुहरबंद आँकड़े", "engine": "इंजन", "seed": "बीज", "threshold": "सीमा", "non_overlap": "बिना ओवरलैप",
        "p5_95": "5वें से 95वें प्रतिशतक तक", "to": "से", "under_half": "इस खेत के बदलाव के आधे से कम", "candidates": "संभावित खेत",
        "affected": "मिलती-जुलती फ़सल भूमि का प्रभावित हिस्सा", "nearby": "हमारे रिकॉर्ड में पास के असली मामले",
        "window": "घटना के दौरान", "hail_h": "ओलों के कोड वाले घंटे", "thunder_h": "गरज के घंटे", "gust": "सबसे तेज़ झोंका",
    },
    "en": {
        "title": "Satellite evidence pack", "verdict": "Result", "explanation": "In plain language", "testimony": "The field's testimony",
        "route": "Your route", "next": "What to do next", "use": "What this evidence is useful for", "unknowns": "Still unknown",
        "deadline": "Intimation timing", "field": "Field", "before_after": "Before and after", "before": "Before", "after": "After",
        "map": "Field map", "delta": "Change map", "placebo": "Compared with look-alike fields nearby", "far": "Compared with fields outside the storm area (5-12 km)", "not_computed": "Exhibits that could not be computed",
        "twin": "Field twin: what comparable fields did", "draw": "The Ten-Field Draw: how far one draw's average can move",
        "vanish": "The same change at coarser cells", "weather": "Weather (model-indicated)", "alerts": "Official alerts", "news": "News",
        "cross": "Cross-examination: the surveyor's objections", "challenge": "Objection", "finding": "What the test found", "outcome": "Outcome",
        "clauses": "Guideline clauses", "scenes": "Images considered", "provenance": "Where each number comes from",
        "hash": "Evidence seal", "verify_note": "Open this QR code to recompute the satellite numbers from public satellite data.",
        "near": "near the threshold", "none": "None found", "no_data": "Not available", "generated": "Generated",
        "disclaimer": "This is evidence, not a claim decision. No clause provides for farmer-submitted satellite evidence, and acceptance is not guaranteed.",
        "note_lang": "",
        "rebutted": "Rebutted", "conceded": "Conceded", "unresolved": "Unresolved",
        "open": "Open", "met": "Met, as self-reported by the farmer", "lapsed": "Time passed",
        "event": "Event", "crop": "Crop", "district": "District", "clause": "clause", "time_assumed": "start of the event day assumed",
        "scope": "Satellite numbers are recomputed; the verdict and weather are checked for tampering only.",
        "tech_en": "Technical reasons and caveats", "related": "Related reports (these do not affect the result)",
        "t_date": "Date", "t_scene": "Scene", "t_qa": "QA", "t_cloud": "Cloud %", "t_reasons": "Reasons",
        "t_field": "Field", "t_source": "Source", "t_asset": "Asset", "t_retrieved": "Retrieved", "t_value": "Value",
        "replay": "Replay numbers", "engine": "engine", "seed": "seed", "threshold": "threshold", "non_overlap": "non-overlapping",
        "p5_95": "5th-95th percentile", "to": "to", "under_half": "under half of this field's change", "candidates": "candidate parcels",
        "affected": "Affected share of comparable cropland", "nearby": "real cases nearby in our records",
        "window": "event window", "hail_h": "hail-code hours", "thunder_h": "thunder hours", "gust": "max gust",
    },
    # NEEDS NATIVE REVIEW: Telugu not checked by a native speaker.
    "te": {
        "title": "ఉపగ్రహ ఆధారాల పత్రం", "verdict": "ఫలితం", "explanation": "సరళ భాషలో", "testimony": "పొలం సాక్ష్యం",
        "route": "మీ మార్గం", "next": "తర్వాత ఏమి చేయాలి", "use": "ఈ ఆధారం దేనికి పనికొస్తుంది", "unknowns": "ఇంకా తెలియనివి",
        "deadline": "సమాచార గడువు", "field": "పొలం", "before_after": "ముందు మరియు తర్వాత", "before": "ముందు", "after": "తర్వాత",
        "map": "పొలం మ్యాప్", "delta": "మార్పు మ్యాప్", "placebo": "సమీపంలోని ఒకేలాంటి పొలాలతో పోలిక", "far": "తుఫాను ప్రాంతం వెలుపలి పొలాలతో పోలిక (5-12 కి.మీ)", "not_computed": "తయారు కాని భాగాలు",
        "twin": "పొలం జంట: పోలికైన పొలాలు ఏమి చేశాయి", "draw": "పది పొలాల డ్రా: ఒక డ్రా సగటు ఎంత మారవచ్చు",
        "vanish": "పెద్ద గడుల్లో అదే మార్పు", "weather": "వాతావరణం (నమూనా అంచనా)", "alerts": "అధికారిక హెచ్చరికలు", "news": "వార్తలు",
        "cross": "క్రాస్ ఎగ్జామినేషన్: సర్వేయర్ అభ్యంతరాలు", "challenge": "అభ్యంతరం", "finding": "పరీక్ష ఫలితం", "outcome": "తీర్పు",
        "clauses": "మార్గదర్శకాల నిబంధనలు", "scenes": "పరిశీలించిన చిత్రాలు", "provenance": "ప్రతి సంఖ్య మూలం",
        "hash": "ఆధారాల ముద్ర", "verify_note": "ఈ QR తెరిచి ఉపగ్రహ సంఖ్యలను పబ్లిక్ ఉపగ్రహ డేటా నుంచి మళ్లీ లెక్కించవచ్చు.",
        "near": "హద్దు దగ్గర", "none": "ఏదీ దొరకలేదు", "no_data": "అందుబాటులో లేదు", "generated": "తయారైన సమయం",
        "disclaimer": "ఇది ఆధారం, క్లెయిమ్ నిర్ణయం కాదు. రైతు సమర్పించే ఉపగ్రహ ఆధారాలకు ప్రత్యేక నిబంధన లేదు, అంగీకారానికి హామీ లేదు.",
        "note_lang": "ఈ పత్రంలోని తెలుగు వచనాన్ని స్థానిక భాషా నిపుణులు ఇంకా సమీక్షించలేదు. తెలుగు లేని భాగాలు ఆంగ్లంలో ఉన్నాయి.",
        "rebutted": "ఖండించబడింది", "conceded": "అంగీకరించబడింది", "unresolved": "తేలలేదు",
        "open": "తెరిచి ఉంది", "met": "సమయానికి ఇచ్చారు, రైతు స్వయంగా చెప్పిన ప్రకారం", "lapsed": "సమయం దాటింది",
        "event": "సంఘటన", "crop": "పంట", "district": "జిల్లా", "clause": "నిబంధన", "time_assumed": "సంఘటన రోజు మొదలు అని భావించాం",
        "scope": "ఉపగ్రహ సంఖ్యలను మళ్ళీ లెక్కిస్తారు; ఫలితం, వాతావరణం మార్చబడలేదని మాత్రమే తనిఖీ చేస్తారు.",
        "tech_en": "సాంకేతిక కారణాలు, జాగ్రత్తలు (ఆంగ్లంలో)", "related": "సంబంధిత నివేదికలు (ఇవి ఫలితాన్ని మార్చవు)",
        "t_date": "తేదీ", "t_scene": "చిత్రం", "t_qa": "తనిఖీ", "t_cloud": "మేఘాలు %", "t_reasons": "కారణాలు",
        "t_field": "అంశం", "t_source": "మూలం", "t_asset": "ఫైల్", "t_retrieved": "తీసిన సమయం", "t_value": "విలువ",
        "replay": "ముద్ర వేసిన సంఖ్యలు", "engine": "ఇంజిన్", "seed": "సీడ్", "threshold": "పరిమితి", "non_overlap": "అతివ్యాప్తి లేనివి",
        "p5_95": "5వ నుంచి 95వ శాతాంశం", "to": "నుంచి", "under_half": "ఈ పొలం మార్పులో సగం కంటే తక్కువ", "candidates": "ఎంపిక చేయగల పొలాలు",
        "affected": "పోలికైన సాగు భూమిలో ప్రభావిత భాగం", "nearby": "మా రికార్డుల్లో సమీపంలోని నిజమైన కేసులు",
        "window": "సంఘటన సమయంలో", "hail_h": "వడగళ్ల కోడ్ గంటలు", "thunder_h": "ఉరుముల గంటలు", "gust": "గరిష్ఠ గాలి",
    },
}

_IDX = {"hi": 0, "te": 1, "en": 2}
ROUTE_NAMES = {
    "not_insured": ("बीमा नहीं: दावे का रास्ता लागू नहीं", "బీమా లేదు: క్లెయిమ్ దారి వర్తించదు", "Not insured: no claim route applies"),
    "localized_addon": ("स्थानीय आपदा का रास्ता: आपकी सूचना ज़रूरी", "స్థానిక విపత్తు దారి: మీ సమాచారం అవసరం", "Localized calamity: your intimation is essential"),
    "post_harvest_addon": ("कटाई के बाद के नुकसान का रास्ता: आपकी सूचना ज़रूरी", "కోత తర్వాత నష్టం దారి: మీ సమాచారం అవసరం", "Post-harvest loss: your intimation is essential"),
    "area_yield_basic": ("क्षेत्र की उपज का रास्ता: व्यक्तिगत सूचना ज़रूरी नहीं", "ప్రాంత దిగుబడి దారి: వ్యక్తిగత సమాచారం అవసరం లేదు", "Area-yield cover: individual intimation is not essential"),
    "outside_cover": ("खेत से हटाई गई फ़सल: कवर से बाहर", "పొలం నుంచి తీసిన పంట: కవర్ పరిధిలో లేదు", "Crop off the field: outside the cover"),
    "undetermined": ("रास्ता अभी तय नहीं", "దారి ఇంకా తేలలేదు", "The route is not determined yet"),
}
UNKNOWN_NAMES = {
    "state_notification": ("क्या आपके राज्य ने यह कवर अधिसूचित किया है", "మీ రాష్ట్రం ఈ కవర్ నోటిఫై చేసిందా", "whether your State notified this cover"),
    "crop_notified": ("क्या आपकी फ़सल इसके लिए अधिसूचित है", "మీ పంట దీనికి నోటిఫై అయిందా", "whether your crop is notified for it"),
    "days_since_harvest": ("कटाई को कितने दिन हुए", "కోత తర్వాత ఎన్ని రోజులు", "how many days since harvest"),
    "insured": ("क्या फ़सल का बीमा है", "పంటకు బీమా ఉందా", "whether the crop is insured"),
    "crop_stage": ("घटना के समय फ़सल की अवस्था", "సంఘటన సమయంలో పంట దశ", "the crop's stage at the time"),
    "event_type": ("क्या हुआ था", "ఏం జరిగింది", "what happened"),
    "cover_for_this_peril_after_cutting": ("कटाई के बाद इस आपदा का कवर", "కోత తర్వాత ఈ విపత్తుకు కవర్", "cover for this peril after cutting"),
    "paddy_localized_inundation_cover": ("धान में जलभराव का कवर", "వరి ముంపుకు కవర్", "cover for paddy inundation"),
    "unseasonal_rain_on_standing_crop": ("खड़ी फ़सल पर बेमौसम बारिश का कवर", "నిలబడిన పంటపై అకాల వర్షానికి కవర్", "cover for unseasonal rain on a standing crop"),
    "policy_corpus": ("नीति के दस्तावेज़", "విధాన పత్రాలు", "the policy documents"),
}
DATE_SOURCES = {
    "farmer": ("आपकी बताई तारीख़", "మీరు చెప్పిన తేదీ", "your date"),
    "weather_proposed": ("मौसम से सुझाई तारीख़", "వాతావరణం సూచించిన తేదీ", "date proposed from weather data"),
    "news": ("ख़बरों से ली तारीख़", "వార్తల నుండి తేదీ", "date from news"),
}
_MONTHS = {
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "te": explain_mod._TE_MONTHS,
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}
_IST_WORD = {"hi": "भारतीय समय", "te": "భారత కాలమానం", "en": "IST"}
LEVEL_NAMES = {
    "strong": ("मज़बूत", "బలమైన", "strong"), "moderate": ("मध्यम", "మధ్యస్థ", "moderate"), "weak": ("कमज़ोर", "బలహీన", "weak"),
    "insufficient": ("पर्याप्त नहीं", "సరిపోదు", "insufficient"),
    "not_damage_likely_harvest": ("कटाई जैसा, नुकसान नहीं", "కోత లాగా, నష్టం కాదు", "looks like harvest, not damage"),
}


def _in_lang(table: dict, key: str | None, lang: str) -> str:
    row = table.get(key or "")
    return row[_IDX[lang]] if row else (key or "")


def _day(when, lang: str) -> str:
    return f"{when.day} {_MONTHS[lang][when.month - 1]} {when.year}" if when else ""


def _moment(when, lang: str) -> str:
    if not when:
        return ""
    local = when.astimezone(IST)
    return f"{_day(local, lang)}, {local:%H:%M} {_IST_WORD[lang]}"


def _crop(name: str | None, lang: str) -> str | None:
    if not name or lang == "en":
        return name
    row = actions_tool._CROP_LABELS.get(name.strip().lower())
    return row[0 if lang == "hi" else 1] if row else name

# Printed beside the result every time (build contract addendum).
DRAW_CAVEATS = {
    "hi": "यह सूचना की असली सूची से नहीं, फ़सल भूमि से चुने गए खेतों पर चलाया गया है। यह सैटेलाइट का बदलाव सूचकांक है, आँका गया फ़सल नुकसान नहीं। हमें बीमित क्षेत्र का पता नहीं, इसलिए प्रभावित हिस्सा केवल एक संकेत है, कानूनी 25% की जाँच नहीं। यादृच्छिक चुनाव औसतन निष्पक्ष होता है; यह सिर्फ़ दिखाता है कि इस घटना में एक ड्रॉ का औसत कितना हिल सकता है।",
    "en": "This draws from cropland, not the real intimation list. It uses a satellite change index, not assessed crop loss. We do not know the insured area, so the affected share is an indicator and not the legal 25% test. Random sampling is unbiased on average; this only shows how far one draw's average can move for this event.",
    "te": "ఇది అసలు సమాచార జాబితా నుంచి కాదు, సాగు భూమి నుంచి తీసుకున్నది. ఇది ఉపగ్రహ మార్పు సూచిక, అంచనా వేసిన పంట నష్టం కాదు. బీమా విస్తీర్ణం మాకు తెలియదు, కాబట్టి ప్రభావిత వాటా ఒక సూచిక మాత్రమే, చట్టపరమైన 25% పరీక్ష కాదు. యాదృచ్ఛిక ఎంపిక సగటున నిష్పక్షపాతమే; ఈ సంఘటనకు ఒక డ్రా సగటు ఎంత మారవచ్చో మాత్రమే ఇది చూపిస్తుంది.",
}
# Whether para 21.5.8 governs this route is stated before the numbers.
DRAW_APPLICABILITY = {
    "may_apply": {
        "hi": "अनुच्छेद 21.5.8 इस रास्ते पर लागू हो सकता है, अगर राज्य ने यह कवर अधिसूचित किया है और इकाई के 25% से ज़्यादा बीमित क्षेत्र की सूचना आई है।",
        "en": "Para 21.5.8 may apply on this route, if the State notified this cover and over 25% of the unit's insured area is under intimation.",
        "te": "మీ రాష్ట్రం ఈ కవర్‌ను నోటిఫై చేసి, యూనిట్ బీమా విస్తీర్ణంలో 25% కంటే ఎక్కువ సమాచారం అందితే, పేరా 21.5.8 ఈ మార్గంలో వర్తించవచ్చు.",
    },
    "illustration_only": {
        "hi": "अनुच्छेद 21.5.8 इस रास्ते पर लागू नहीं होता। यह सिर्फ़ यह दिखाता है कि अगर यह नियम यहाँ लागू होता तो क्या होता।",
        "en": "Para 21.5.8 does not govern this route. This shows only what this rule would do if it applied here.",
        "te": "పేరా 21.5.8 ఈ మార్గానికి వర్తించదు. ఈ నియమం ఇక్కడ వర్తిస్తే ఏమి జరుగుతుందో మాత్రమే ఇది చూపిస్తుంది.",
    },
}
VANISH_CAVEATS = {
    "hi": "सार्वजनिक सैटेलाइट डेटा से हमारा चित्रण, YES-TECH का नतीजा नहीं। YES-TECH का स्तर ग्राम पंचायत है।",
    "en": "Our illustration from public satellite data, not output of YES-TECH. YES-TECH works at Gram Panchayat level.",
    "te": "పబ్లిక్ ఉపగ్రహ డేటా నుంచి మా చిత్రణ, YES-TECH ఫలితం కాదు. YES-TECH గ్రామ పంచాయతీ స్థాయిలో పనిచేస్తుంది.",
}


def _qr_data_uri(url: str) -> str:
    image = qrcode.make(url, box_size=6, border=2)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _chip_uri(ev: Evidence, kind: str) -> tuple[Path | None, tuple | None, object | None]:
    root = get_settings().artifacts_dir
    chip = next((c for c in ev.chips if c.kind == kind), None)
    if chip is None:
        return None, None, None
    path = (root / chip.path).resolve()
    return (path if path.is_file() else None), chip.bounds, chip


def _pick(ev: Evidence, name: str, lang: str) -> str | None:
    """A localized field, falling back to English, then Hindi."""
    for code in (lang, "en", "hi"):
        value = getattr(ev, f"{name}_{code}", None)
        if value:
            return value
    return None


def _headline(ev: Evidence, lang: str) -> str:
    if ev.verdict is None:
        return ""
    return getattr(ev.verdict, f"headline_{lang}", None) or ev.verdict.headline_en


def _reason_lines(ev: Evidence, lang: str) -> list[str]:
    """Reasons and caveats are machine-written English, so they go under a label saying so."""
    if ev.verdict is None:
        return []
    return [*ev.verdict.reasons, *ev.verdict.caveats]


def _tests_text(ev: Evidence, lang: str) -> str | None:
    line = explain_mod.tests_line(ev)
    return line[{"hi": 0, "en": 1, "te": 2}[lang]] if line else None


def build_context(ev: Evidence, case: dict, actions: list[dict], lang: str, chart_dir: Path,
                  failed: dict | None = None, base_url: str | None = None) -> dict:
    labels = L[lang]
    pre, _, pre_chip = _chip_uri(ev, "true_colour_pre")
    post, post_bounds, post_chip = _chip_uri(ev, "true_colour_post")
    delta, _, _ = _chip_uri(ev, "delta_map")
    sar_change, _, _ = _chip_uri(ev, "sar_change")
    placebo = ev.neighbours.placebo if ev.neighbours else None
    placebo_sensor = "optical"
    if placebo is None and ev.sar is not None:
        placebo, placebo_sensor = ev.sar.placebo, "radar"
    draw = ev.village.lottery if ev.village else None
    base = base_url or get_settings().public_web_url or "http://localhost:8000"
    verify_url = f"{base.rstrip('/')}/verify/{ev.evidence_hash}"
    challenge_key, finding_key = ("challenge_hi", "finding_hi") if lang == "hi" else (
        "challenge_en", "finding_en")
    return {
        "L": labels,
        "lang": lang,
        "ev": ev,
        "case": case,
        "headline": _headline(ev, lang),
        "selection_note": (disclosures.selection_note(ev.plot.centroid) or {}).get(lang),
        "selection_source": (disclosures.selection_note(ev.plot.centroid) or {}).get("source"),
        "level_name": _in_lang(LEVEL_NAMES, ev.verdict.level if ev.verdict else "insufficient", lang),
        "route_name": _in_lang(ROUTE_NAMES, ev.claim_path.route if ev.claim_path else None, lang),
        "unknown_names": [_in_lang(UNKNOWN_NAMES, u, lang).replace("_", " ") for u in (ev.claim_path.unknowns if ev.claim_path else [])],
        "event_name": {"hi": explain_mod.EVENT_HI, "te": explain_mod.EVENT_TE, "en": explain_mod.EVENT_EN}[lang].get(ev.event.type, ev.event.type),
        "event_day": _day(ev.event.date, lang),
        "date_source_name": _in_lang(DATE_SOURCES, ev.event.date_source, lang),
        "crop_name": _crop(ev.event.crop, lang),
        "day": lambda when: _day(when, lang),
        "explanation": _pick(ev, "explanation", lang),
        "testimony": _pick(ev, "testimony", lang),
        "reason_lines": _reason_lines(ev, lang),
        "level": ev.verdict.level if ev.verdict else "insufficient",
        "pre_chip": pre.as_uri() if pre else None,
        "post_chip": post.as_uri() if post else None,
        "pre_date": pre_chip.date if pre_chip else None,
        "post_date": post_chip.date if post_chip else None,
        "delta_chip": delta.as_uri() if delta else None,
        "sar_chip": sar_change.as_uri() if sar_change else None,
        "map_img": _as_uri(charts.plot_map(ev, post, post_bounds, chart_dir / "map.png")),
        "placebo_img": _as_uri(charts.placebo_histogram(placebo, chart_dir / "placebo.png")),
        "placebo": placebo,
        "placebo_sensor": placebo_sensor,
        "placebo_p": rubric.usable_p(placebo),
        "far_img": _as_uri(charts.placebo_histogram(
            ev.neighbours.far_placebo if ev.neighbours else None, chart_dir / "far.png",
            label="comparable fields 5-12 km away")),
        "far": ev.neighbours.far_placebo if ev.neighbours else None,
        "far_p": rubric.far_p(ev),
        "tests_plain": _tests_text(ev, lang),
        "near_note": explain_mod.NEAR_LINE[{"hi": 0, "en": 1, "te": 2}[lang]]
        if ev.verdict and rubric.level_could_change(ev, ev.verdict.level) else None,
        "far_near": rubric.near_threshold(rubric.far_p(ev)),
        "placebo_near": placebo_sensor == "optical" and rubric.near_threshold(rubric.usable_p(placebo)),
        "failed_exhibits": failed or {},
        "twin_img": _as_uri(charts.twin_chart(ev, chart_dir / "twin.png")),
        "weather_img": _as_uri(charts.weather_strip(ev, chart_dir / "weather.png")),
        "draw_img": _as_uri(charts.draw_histogram(draw, chart_dir / "draw.png")),
        "draw": draw,
        "draw_caveat": DRAW_CAVEATS[lang],
        "draw_applicability": DRAW_APPLICABILITY[draw.rule_applicability][lang] if draw else None,
        "vanish_img": _as_uri(charts.scale_chart(ev.scale_fade, chart_dir / "scale.png")),
        "vanish_caveat": VANISH_CAVEATS[lang],
        "objections": [
            {"id": o.id, "challenge": getattr(o, challenge_key), "finding": getattr(o, finding_key),
             "outcome": o.outcome, "outcome_label": labels[o.outcome]}
            for o in ev.cross_examination
        ],
        "deadline": next((d for d in ev.deadlines if d.type == "intimation_72h"), None),
        "ist": lambda when: _moment(when, lang),
        "generated": _moment(datetime.now(UTC), lang),
        "qr": _qr_data_uri(verify_url),
        "verify_url": verify_url,
        "numbers": sorted(
            (name.replace("village.lottery.", "village.ten_field_draw."), value)
            for name, value in (ev.replay.numbers or {}).items()
        ) if ev.replay else [],
    }


def _as_uri(path: str | None) -> str | None:
    return Path(path).resolve().as_uri() if path else None


def build_html(ev: Evidence, case: dict, actions: list[dict], lang: str, chart_dir: Path,
               failed: dict | None = None, base_url: str | None = None) -> str:
    template = _ENV.get_template("evidence.html.j2")
    return template.render(**build_context(ev, case, actions, lang, chart_dir, failed, base_url))


def build_pdf(ev: Evidence, case: dict, actions: list[dict], lang: str = "hi",
              exhibits: dict | None = None, base_url: str | None = None) -> bytes:
    from weasyprint import HTML

    tag = (ev.evidence_hash or ev.run_id)[:16]
    chart_dir = get_settings().artifacts_dir / ev.case_id / f"pdf_{tag}"
    failed = {k: errors.public_text(v.get("reason"), "it could not be computed") for k, v in (exhibits or {}).items()
              if v.get("status") == "failed"}
    html = build_html(ev, case, actions, lang, chart_dir, failed, base_url)
    return HTML(string=html, base_url=str(chart_dir)).write_pdf()
