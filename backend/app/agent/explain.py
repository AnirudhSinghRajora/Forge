"""Deterministic headlines and explanations, optional LLM rewrites through the validator, and TTS.

The templates carry the verdict in all three languages. LLM rewrites run only under LLM_POLISH=true.

The Telugu here NEEDS NATIVE REVIEW: it was written without a native speaker's check.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.agent import llm, rubric, validate
from app.agent.cross_exam import date_en, date_hi, signed
from app.config import get_settings
from app.evidence.schema import Evidence

log = logging.getLogger(__name__)

_TE_MONTHS = ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జులై", "ఆగస్టు", "సెప్టెంబర్",
              "అక్టోబర్", "నవంబర్", "డిసెంబర్"]

EVENT_HI = {
    "hail": "ओलावृष्टि", "unseasonal_rain": "बेमौसम बारिश", "flood": "बाढ़ या जलभराव", "cyclone": "चक्रवात",
    "wind": "तेज़ आँधी", "pest": "कीट या रोग", "drought": "सूखा", "other": "आपदा", "unknown": "आपदा",
}
EVENT_EN = {
    "hail": "hail", "unseasonal_rain": "unseasonal rain", "flood": "flooding", "cyclone": "the cyclone",
    "wind": "strong wind", "pest": "pests or disease", "drought": "drought", "other": "the event",
    "unknown": "the event",
}
# NEEDS NATIVE REVIEW: deterministic Telugu, not checked by a native speaker.
EVENT_TE = {
    "hail": "వడగళ్ల వాన", "unseasonal_rain": "అకాల వర్షం", "flood": "వరద", "cyclone": "తుఫాను",
    "wind": "ఈదురు గాలులు", "pest": "పురుగులు లేదా తెగుళ్లు", "drought": "కరువు", "other": "విపత్తు",
    "unknown": "విపత్తు",
}


# NEEDS NATIVE REVIEW (Telugu)
INTERRUPTED_HEADLINES = (
    "सर्वर दोबारा शुरू होने से यह जाँच पूरी नहीं हुई। कृपया इसे फिर से चलाएँ।",
    "The server restarted before this check finished. Please run it again.",
    "సర్వర్ మళ్ళీ మొదలవడంతో ఈ పరిశీలన పూర్తి కాలేదు. దయచేసి మళ్ళీ నడపండి.",
)
# Said when the search window after the event has passed, so no later image can change this.
NO_WINDOW_HEADLINES = (
    "पक्की बात कहने लायक सबूत नहीं हैं, और इस घटना के बाद की तस्वीरों की समय-सीमा निकल चुकी है",
    "There is not enough evidence to say, and the window for images after this event has passed",
    "నిర్ధారించడానికి తగిన ఆధారాలు లేవు, ఈ సంఘటన తర్వాతి చిత్రాల గడువు కూడా దాటిపోయింది",
)
# Said beside a weak result with no support: the level is capped because of this, and it is not a
# finding against the farmer.
NO_SUPPORT_LINE = (
    "मौसम मॉडल में संकेत नहीं है और इस आपदा की कोई सरकारी चेतावनी नहीं मिली, इसलिए नतीजा 'कमज़ोर' ही रहता है। "
    "ख़बरें संबंधित रिपोर्ट के रूप में दिखती हैं और स्तर नहीं बदलतीं।",
    "The weather model shows no signal and no official alert for this hazard covers it, so this stays "
    "weak. News appears as related reports and does not change the level.",
    "వాతావరణ నమూనాలో సంకేతం లేదు, ఈ విపత్తుకు అధికారిక హెచ్చరికా లేదు, కాబట్టి ఫలితం బలహీనంగానే ఉంటుంది. "
    "వార్తలు సంబంధిత నివేదికలుగా కనిపిస్తాయి, స్థాయిని మార్చవు.",
)


def headlines(level: str, event_type: str, *, recheck: bool = True) -> tuple[str, str, str]:
    if level == "insufficient" and not recheck:
        return NO_WINDOW_HEADLINES
    hi, en, te = EVENT_HI.get(event_type, "आपदा"), EVENT_EN.get(event_type, "the event"), EVENT_TE.get(
        event_type, "విపత్తు")
    return {
        "strong": (
            f"सैटेलाइट के सबूत आपके खेत में {hi} से हुए नुकसान से मेल खाते हैं",
            f"Satellite evidence is consistent with damage to your field from {en}",
            # NEEDS NATIVE REVIEW
            f"ఉపగ్రహ ఆధారాలు మీ పొలంలో {te} వల్ల జరిగిన నష్టానికి సరిపోలుతున్నాయి",
        ),
        "moderate": (
            f"सैटेलाइट के सबूत {hi} से नुकसान की ओर इशारा करते हैं, पर पूरी तरह पक्के नहीं हैं",
            f"Satellite evidence points to damage from {en}, but is not conclusive",
            # NEEDS NATIVE REVIEW
            f"ఉపగ్రహ ఆధారాలు {te} వల్ల నష్టాన్ని సూచిస్తున్నాయి, కానీ పూర్తిగా నిర్ధారణ కాలేదు",
        ),
        "weak": (
            "अभी के सैटेलाइट सबूतों में आपके खेत का नुकसान साफ़ नहीं दिखता",
            "The satellite evidence so far does not clearly show damage to your field",
            # NEEDS NATIVE REVIEW
            "ప్రస్తుత ఉపగ్రహ ఆధారాల్లో మీ పొలంలో నష్టం స్పష్టంగా కనిపించడం లేదు",
        ),
        "insufficient": (
            "अभी पक्की बात कहने लायक सबूत नहीं हैं; अगली सैटेलाइट तस्वीर पर फिर जाँच होगी",
            ("There is not enough evidence to say yet; this will be checked again on the next "
            "satellite pass"),
            # NEEDS NATIVE REVIEW
            "ఇప్పుడే నిర్ధారించడానికి తగిన ఆధారాలు లేవు; తదుపరి ఉపగ్రహ చిత్రంతో మళ్లీ పరిశీలిస్తాం",
        ),
        "not_damage_likely_harvest": (
            "यह बदलाव नुकसान से ज़्यादा फ़सल की कटाई जैसा दिखता है",
            "This change looks more like harvest than damage",
            # NEEDS NATIVE REVIEW
            "ఈ మార్పు నష్టం కంటే పంట కోత లాగా కనిపిస్తోంది",
        ),
    }[level]


def headlines_for(ev: Evidence) -> tuple[str, str, str]:
    if ev.verdict is not None and rubric.RUN_INTERRUPTED in ev.verdict.reasons:
        return INTERRUPTED_HEADLINES
    level = ev.verdict.level if ev.verdict else "insufficient"
    return headlines(level, ev.event.type, recheck=rubric.recheck_possible(ev))


def _date_te(d) -> str:
    return f"{_TE_MONTHS[d.month - 1]} {d.day}"


def _sat_line(ev: Evidence) -> tuple[str, str, str]:
    o = ev.optical
    if o.pre and o.post and o.plot_delta_ndvi is not None:
        return (
            (f"{date_hi(o.pre.date)} से {date_hi(o.post.date)} के बीच आपके खेत की हरियाली (NDVI) "
            f"{o.pre.ndvi_median:.2f} से {o.post.ndvi_median:.2f} हुई, यानी बदलाव {signed(o.plot_delta_ndvi)}।"),
            (f"Between {date_en(o.pre.date)} and {date_en(o.post.date)} your field's greenness (NDVI) "
            f"went from {o.pre.ndvi_median:.2f} to {o.post.ndvi_median:.2f}, a change of "
            f"{signed(o.plot_delta_ndvi)}."),
            (f"{_date_te(o.pre.date)} నుంచి {_date_te(o.post.date)} మధ్య మీ పొలం పచ్చదనం (NDVI) "
            f"{o.pre.ndvi_median:.2f} నుంచి {o.post.ndvi_median:.2f} అయింది, అంటే మార్పు {signed(o.plot_delta_ndvi)}."),
        )
    s = ev.sar
    if s and s.usable and s.vh_change_db is not None and s.pre_date and s.post_date:
        return (
            (f"साफ़ तस्वीर नहीं मिली, इसलिए रडार देखा गया: {date_hi(s.pre_date)} से {date_hi(s.post_date)} के बीच "
            f"रडार संकेत (VH) में {s.vh_change_db:+.1f} dB का बदलाव है।"),
            (f"No clear optical image was available, so radar was used: between {date_en(s.pre_date)} "
            f"and {date_en(s.post_date)} the radar signal (VH) changed by {s.vh_change_db:+.1f} dB."),
            (f"స్పష్టమైన చిత్రం దొరకలేదు, కాబట్టి రాడార్ చూశాం: {_date_te(s.pre_date)} నుంచి {_date_te(s.post_date)} మధ్య "
            f"రాడార్ సంకేతం (VH) {s.vh_change_db:+.1f} dB మారింది."),
        )
    if ev.verdict is not None and rubric.RUN_INTERRUPTED in ev.verdict.reasons:
        return INTERRUPTED_HEADLINES
    if rubric.comparison_incomplete(ev):
        return (
            "सैटेलाइट संग्रह धीमा था या जवाब नहीं दे रहा था, इसलिए तुलना पूरी नहीं हुई। यह जाँच जल्द दोबारा चलेगी।",
            ("The satellite archive was slow or not responding, so the comparison did not finish. "
            "This check will run again soon."),
            "ఉపగ్రహ ఆర్కైవ్ నెమ్మదిగా ఉంది లేదా స్పందించలేదు, కాబట్టి పోలిక పూర్తి కాలేదు. ఈ పరిశీలన త్వరలో మళ్ళీ నడుస్తుంది.",
        )
    if not rubric.recheck_possible(ev):
        return (
            "घटना के बाद की समय-सीमा में कोई भरोसेमंद सैटेलाइट तस्वीर नहीं मिली।",
            "No trustworthy satellite image was found in the window after the event.",
            "సంఘటన తర్వాతి గడువులో నమ్మదగిన ఉపగ్రహ చిత్రం దొరకలేదు.",
        )
    return (
        "घटना के बाद की कोई भरोसेमंद सैटेलाइट तस्वीर अभी नहीं मिली।",
        "No trustworthy satellite image from after the event is available yet.",
        "సంఘటన తర్వాతి నమ్మదగిన ఉపగ్రహ చిత్రం ఇంకా దొరకలేదు.",
    )


def tests_line(ev: Evidence) -> tuple[str, str, str] | None:
    """Both answers in plain words. "Far yes, ring no" reads "the effect does not look limited to
    your field", and never as a weakness. A ring test that misses its threshold does not show that
    the neighbours changed as much. Telugu NEEDS NATIVE REVIEW."""
    if ev.neighbours is None or ev.optical.post is None:
        placebo = ev.sar.placebo if ev.sar else None
        if rubric.usable_p(placebo) is None:
            return None
        n, k = placebo.n_placebos, placebo.n_at_least_as_extreme
        return (
            f"रडार में आसपास के {n} मिलते-जुलते खेतों में से {k} में इतना या इससे ज़्यादा बदलाव दिखा।",
            f"On radar, of {n} look-alike fields nearby, {k} changed this much or more.",
            f"రాడార్‌లో సమీపంలోని {n} పొలాల్లో {k} పొలాల్లో ఇంత లేదా ఎక్కువ మార్పు కనిపించింది.",
        )
    ring, far = rubric.ring_significant(ev), rubric.far_significant(ev)
    if rubric.optical_p(ev) is None and rubric.far_p(ev) is None:
        return None
    if far and ring:
        return (
            "आपका खेत दूर के खेतों से भी ज़्यादा बदला और पास के खेतों से भी।",
            "Your field changed more than distant fields and more than the fields around it.",
            "మీ పొలం దూరంలోని పొలాల కంటే, చుట్టుపక్కల పొలాల కంటే కూడా ఎక్కువగా మారింది.",
        )
    if far:
        return (
            ("आपका खेत तूफ़ान के इलाक़े से बाहर के खेतों से ज़्यादा बदला। आसपास के खेतों से फ़र्क़ इतना साफ़ नहीं कि पक्का कहा जाए, "
            "और हो सकता है वे भी प्रभावित हुए हों, इसलिए असर सिर्फ़ आपके खेत तक सीमित नहीं दिखता।"),
            ("Your field changed more than fields outside the storm area. The difference from the "
            "fields around it is not clear enough to call, and they may have been affected too, so "
            "the effect does not look limited to your field."),
            "మీ పొలం తుఫాను ప్రాంతం వెలుపలి పొలాల కంటే ఎక్కువగా మారింది. చుట్టుపక్కల పొలాలతో తేడా ఖచ్చితంగా చెప్పేంత స్పష్టంగా లేదు, అవి కూడా ప్రభావితమై ఉండవచ్చు, కాబట్టి ప్రభావం మీ పొలానికే పరిమితమైనట్లు కనిపించడం లేదు.",
        )
    if ring:
        return (
            "आपका खेत आसपास के खेतों से ज़्यादा बदला: यह आपके खेत का स्थानीय बदलाव दिखता है।",
            "Your field changed more than the fields around it: this looks local to your field.",
            "మీ పొలం చుట్టుపక్కల పొలాల కంటే ఎక్కువగా మారింది: ఇది మీ పొలానికే పరిమితమైన మార్పులా ఉంది.",
        )
    return (
        "यह साफ़ नहीं दिखता कि आपका खेत पास के या दूर के खेतों से ज़्यादा बदला।",
        "Your field did not clearly change more than nearby fields, or more than distant ones.",
        "మీ పొలం సమీప పొలాల కంటే గానీ, దూరంలోని పొలాల కంటే గానీ స్పష్టంగా ఎక్కువగా మారలేదు.",
    )


NEAR_LINE = (
    "एक निर्णायक तुलना सीमा के पास है, इसलिए इस खेत की सीमा थोड़ी अलग बनाने पर यह नतीजा बदल सकता है।",
    rubric.NEAR_LINE_CAVEAT,
    # NEEDS NATIVE REVIEW
    "ఒక నిర్ణయాత్మక పోలిక హద్దు దగ్గర ఉంది, కాబట్టి ఈ పొలం సరిహద్దును కొద్దిగా వేరుగా గీస్తే ఈ ఫలితం మారవచ్చు.",
)


def _weather_line(ev: Evidence) -> tuple[str, str, str]:
    w = ev.weather
    if w is None:
        return ("मौसम का डेटा इस बार नहीं मिल सका।", "Weather data could not be retrieved this time.",
                "ఈసారి వాతావరణ సమాచారం దొరకలేదు.")
    if w.corroborated:
        rain = f"{w.max_daily_mm:.1f}" if w.max_daily_mm is not None else None
        hi = "मौसम मॉडल के अनुसार उस समय मौसम बिगड़ा था"
        en = "The weather model indicates bad weather around that time"
        te = "వాతావరణ నమూనా ప్రకారం ఆ సమయంలో వాతావరణం దెబ్బతింది"
        if rain:
            hi += f" (एक दिन में अधिकतम {rain} मिमी बारिश)"
            en += f" (up to {rain} mm of rain in a day)"
            te += f" (ఒక రోజులో గరిష్ఠంగా {rain} మి.మీ వర్షం)"
        return hi + "।", en + ".", te + "."
    return (
        ("मौसम मॉडल में इस दौरान कुछ ख़ास नहीं दिखता, पर उसका ग्रिड बड़ा है और छोटी ओलावृष्टि छूट सकती है, इसलिए "
        "इससे आपकी बात ग़लत साबित नहीं होती।"),
        ("The weather model shows little in this period, but its grid is coarse and can miss a small "
        "hail cell, so this does not count against what you reported."),
        ("వాతావరణ నమూనాలో ఈ సమయంలో పెద్దగా ఏమీ కనిపించడం లేదు, కానీ దాని గ్రిడ్ పెద్దది, చిన్న వడగళ్ల వాన తప్పిపోవచ్చు, "
        "కాబట్టి ఇది మీరు చెప్పినదానికి వ్యతిరేకం కాదు."),
    )


_LEVEL_CLOSE = {
    "strong": (
        "यह सबूत है, दावे का फ़ैसला नहीं।",
        "This is evidence, not a claim decision.",
        "ఇది ఆధారం, క్లెయిమ్ నిర్ణయం కాదు.",
    ),
    "moderate": (
        "यह सबूत है, दावे का फ़ैसला नहीं।",
        "This is evidence, not a claim decision.",
        "ఇది ఆధారం, క్లెయిమ్ నిర్ణయం కాదు.",
    ),
    "weak": (
        "अगर आपका नुकसान हुआ है तो इस नतीजे से रुकें नहीं, क्योंकि सैटेलाइट हर नुकसान नहीं देख पाता।",
        ("If you have a loss, do not let this result stop you, because a satellite cannot see every "
        "kind of damage."),
        "మీకు నష్టం జరిగి ఉంటే ఈ ఫలితంతో ఆగకండి, ఎందుకంటే ఉపగ్రహం ప్రతి నష్టాన్నీ చూడలేదు.",
    ),
    "insufficient": (
        "सबूत का इंतज़ार न करें। नई सैटेलाइट तस्वीर आने पर यह जाँच दोबारा चलेगी।",
        "Do not wait for the evidence. This check will run again when a new satellite image arrives.",
        "ఆధారాల కోసం ఆగకండి. కొత్త ఉపగ్రహ చిత్రం వచ్చినప్పుడు ఈ పరిశీలన మళ్ళీ నడుస్తుంది.",
    ),
    "not_damage_likely_harvest": (
        "अगर आपने फ़सल नहीं काटी थी, तो हमें बताएँ और खेत की तस्वीरें रखें।",
        "If you did not harvest, tell us and keep photographs of the field.",
        "మీరు పంట కోయకపోతే మాకు చెప్పండి, పొలం ఫోటోలు ఉంచండి.",
    ),
}
_NO_RECHECK_CLOSE = (
    "सबूत का इंतज़ार न करें। अपना नुकसान बताने के लिए खेत की तस्वीरें और दूसरे काग़ज़ रखें।",
    "Do not wait for the evidence. Keep photographs and other records of your loss.",
    "ఆధారాల కోసం ఆగకండి. మీ నష్టానికి ఫోటోలు, ఇతర పత్రాలు ఉంచండి.",
)
_INTERRUPTED_CLOSE = (
    "यह आपके खेत के बारे में कुछ नहीं कहता।",
    "This says nothing about your field.",
    "ఇది మీ పొలం గురించి ఏమీ చెప్పదు.",
)
# A conceded objection's finding is written in Hindi and English. These carry the gist in Telugu.
_CONCEDED_TE = {
    "harvest": "ఈ మార్పు పంట కోతలా కనిపిస్తోంది అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "wrong_plot": "సంఘటనకు ముందు ఈ పొలంలో పంట కనిపించలేదు అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "wrong_date": "చెప్పిన తేదీ చుట్టూ వాతావరణ నమూనాలో సంకేతం లేదు అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "cloud_shadow": "మేఘాలు లేదా నీడ చిత్రాన్ని ప్రభావితం చేసి ఉండవచ్చు అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "corrupt_scene": "సంఘటన తర్వాతి చిత్రం అనుమానాస్పదంగా ఉంది అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "regional_trend": "ఈ మార్పు ఈ ప్రాంతం మొత్తం ధోరణిలానే ఉంది అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "pre_trend": "సంఘటనకు ముందే పచ్చదనం తగ్గుతోంది అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "too_small": "ఈ పొలం ఉపగ్రహానికి చాలా చిన్నది అనే అభ్యంతరాన్ని అంగీకరించాం.",
    "stale_crop": "గత సంవత్సరాలతో పోలిక బలహీనం అనే అభ్యంతరాన్ని అంగీకరించాం.",
}


def template_explanation(ev: Evidence, level: str) -> tuple[str, str, str]:
    interrupted = ev.verdict is not None and rubric.RUN_INTERRUPTED in ev.verdict.reasons
    if interrupted:
        return tuple(  # type: ignore[return-value]
            f"{head} {close}" for head, close in zip(INTERRUPTED_HEADLINES, _INTERRUPTED_CLOSE, strict=True)
        )
    head = headlines(level, ev.event.type, recheck=rubric.recheck_possible(ev))
    parts = [(head[0] + "।", head[1] + ".", head[2] + "."), _sat_line(ev)]
    conceded = [o for o in ev.cross_examination if o.outcome == "conceded"]
    tests = tests_line(ev)
    if tests and not any(o.id == "regional_trend" for o in conceded):
        parts.append(tests)  # a conceded regional_trend finding already says the same thing
    if rubric.level_could_change(ev, level):
        parts.append(NEAR_LINE)
    parts.append(_weather_line(ev))
    if level == "weak" and not rubric.corroboration(ev):
        parts.append(NO_SUPPORT_LINE)
    if conceded:
        first = conceded[0]
        parts.append((first.finding_hi, first.finding_en, _CONCEDED_TE.get(first.id, first.finding_en)))
    close = _LEVEL_CLOSE[level]
    if level == "insufficient" and not rubric.recheck_possible(ev):
        close = _NO_RECHECK_CLOSE
    parts.append(close)
    return " ".join(p[0] for p in parts), " ".join(p[1] for p in parts), " ".join(p[2] for p in parts)


def digest(ev: Evidence) -> dict:
    """What the LLM may talk about. Everything in here came from deterministic code."""
    return {
        "verdict_level": ev.verdict.level if ev.verdict else None,
        "reasons": ev.verdict.reasons if ev.verdict else [],
        "caveats": ev.verdict.caveats if ev.verdict else [],
        "event": ev.event.model_dump(mode="json"),
        "plot_area_ha": ev.plot.area_ha,
        "optical": {
            "pre": ev.optical.pre.model_dump(mode="json") if ev.optical.pre else None,
            "post": ev.optical.post.model_dump(mode="json") if ev.optical.post else None,
            "plot_delta_ndvi": ev.optical.plot_delta_ndvi,
            "post_bare_fraction": ev.optical.post_bare_fraction,
            "within_plot_pattern": ev.optical.within_plot_pattern,
        },
        "placebo": ev.neighbours.placebo.model_dump(
            mode="json", exclude={"histogram_edges", "histogram_counts", "seed"}
        ) if ev.neighbours and ev.neighbours.placebo else None,
        "radar": ev.sar.model_dump(mode="json", exclude={"placebo"}) if ev.sar else None,
        "weather": ev.weather.model_dump(mode="json", exclude={"days", "grid_note"})
        if ev.weather else None,
        "cross_examination": [
            {"id": o.id, "outcome": o.outcome, "finding": o.finding_en}
            for o in ev.cross_examination
        ],
    }


def allowed_numbers(ev: Evidence) -> set[float]:
    data = ev.model_dump(mode="json")
    allowed = validate.collect_numbers(data)
    return allowed


def checked(text: str | None, allowed: set[float], what: str) -> str | None:
    """Returns the text only if it passes the validator. A rejection is logged, never shown."""
    if not text:
        return None
    result = validate.validate_text(text, allowed)
    if not result.ok:
        log.warning("LLM %s rejected by the validator: %s", what, result.reason())
        return None
    return text


def fill_templates(ev: Evidence) -> None:
    """The deterministic text, in place. It is complete on its own, with or without any LLM."""
    ev.explanation_hi, ev.explanation_en, ev.explanation_te = template_explanation(ev, ev.verdict.level)
    ev.verdict.headline_te = headlines_for(ev)[2]


def explain(ev: Evidence) -> dict:
    """Fills explanations and Telugu headline fields. Returns which LLM attempts were used."""
    level = ev.verdict.level
    _, head_en, head_te = headlines_for(ev)
    template_hi, template_en, template_te = template_explanation(ev, level)
    allowed = allowed_numbers(ev)
    report = {"hi": "template", "en": "template", "te": "template", "headline_te": "template",
              "rejected": []}

    summary = digest(ev)
    ev.explanation_hi, ev.explanation_en, ev.explanation_te = template_hi, template_en, template_te
    if llm.available():
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="narrate") as pool:
            narrated = dict(zip(("hi", "en"), pool.map(lambda code: llm.narrate(summary, code),
                                                       ("hi", "en")), strict=True))
        for lang, raw in narrated.items():
            if checked(raw, allowed, f"narrative {lang}"):
                setattr(ev, f"explanation_{lang}", raw)
                report[lang] = "llm"
                ev.llm_used = True
            elif raw:
                report["rejected"].append(f"narrative_{lang}")

    ev.verdict.headline_te = head_te
    if llm.available():
        translated = checked(llm.translate(head_en, "te"), allowed, "headline te")
        if translated:
            ev.verdict.headline_te = translated
            report["headline_te"] = "llm"
            ev.llm_used = True
        explained_te = checked(llm.translate(ev.explanation_en, "te"), allowed, "explanation te")
        if explained_te:
            ev.explanation_te = explained_te
            report["te"] = "llm"
            ev.llm_used = True
    return report


def _audio_path(ev: Evidence, lang: str, kind: str) -> Path:
    tag = ev.evidence_hash or ev.run_id
    return get_settings().artifacts_dir / ev.case_id / f"{kind}_{tag[:16]}_{lang}.wav"


def summary_audio_path(ev: Evidence, lang: str, kind: str = "testimony") -> Path | None:
    """The WAV for this evidence, language and kind, generated on first request. None if no TTS."""
    path = _audio_path(ev, lang, kind)
    if path.is_file():
        return path
    if not llm.available():
        return None
    if kind == "testimony":
        text = {"hi": ev.testimony_hi, "en": ev.testimony_en, "te": ev.testimony_te}.get(lang)
    else:
        text = {"hi": ev.explanation_hi, "en": ev.explanation_en, "te": ev.explanation_te}.get(lang)
    if not text:
        return None
    audio = llm.tts(text, lang)
    if not audio:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    return path
