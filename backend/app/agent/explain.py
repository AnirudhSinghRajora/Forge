"""Deterministic headlines and explanations, optional LLM rewrites through the validator, and TTS.

The Telugu here NEEDS NATIVE REVIEW: it was written without a native speaker's check. It is used
only for headlines, and Gemini's translation (also validated) replaces it when available.
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


def headlines(level: str, event_type: str) -> tuple[str, str, str]:
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


def _sat_line(ev: Evidence) -> tuple[str, str]:
    o = ev.optical
    if o.pre and o.post and o.plot_delta_ndvi is not None:
        return (
            (f"{date_hi(o.pre.date)} से {date_hi(o.post.date)} के बीच आपके खेत की हरियाली (NDVI) "
            f"{o.pre.ndvi_median:.2f} से {o.post.ndvi_median:.2f} हुई, यानी बदलाव {signed(o.plot_delta_ndvi)}।"),
            (f"Between {date_en(o.pre.date)} and {date_en(o.post.date)} your field's greenness (NDVI) "
            f"went from {o.pre.ndvi_median:.2f} to {o.post.ndvi_median:.2f}, a change of "
            f"{signed(o.plot_delta_ndvi)}."),
        )
    s = ev.sar
    if s and s.usable and s.vh_change_db is not None and s.pre_date and s.post_date:
        return (
            (f"साफ़ तस्वीर नहीं मिली, इसलिए रडार देखा गया: {date_hi(s.pre_date)} से {date_hi(s.post_date)} के बीच "
            f"रडार संकेत (VH) में {s.vh_change_db:+.1f} dB का बदलाव है।"),
            (f"No clear optical image was available, so radar was used: between {date_en(s.pre_date)} "
            f"and {date_en(s.post_date)} the radar signal (VH) changed by {s.vh_change_db:+.1f} dB."),
        )
    if rubric.comparison_incomplete(ev):
        return (
            "सैटेलाइट संग्रह धीमा था या जवाब नहीं दे रहा था, इसलिए तुलना पूरी नहीं हुई। यह जाँच जल्द दोबारा चलेगी।",
            ("The satellite archive was slow or not responding, so the comparison did not finish. "
            "This check will run again soon."),
        )
    return (
        "घटना के बाद की कोई भरोसेमंद सैटेलाइट तस्वीर अभी नहीं मिली।",
        "No trustworthy satellite image from after the event is available yet.",
    )


def tests_line(ev: Evidence) -> tuple[str, str, str] | None:
    """Both answers in plain words. "Far yes, ring no" is the whole area, and never a weakness.
    Telugu NEEDS NATIVE REVIEW."""
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
            ("आपका खेत तूफ़ान के इलाक़े से बाहर के खेतों से ज़्यादा बदला, पर आसपास के खेतों जितना ही: आपका पूरा इलाक़ा प्रभावित हुआ, "
            "सिर्फ़ आपका खेत नहीं।"),
            ("Your field changed more than fields outside the storm area, and about as much as the "
            "fields around it: your whole area was hit, not only your field."),
            "మీ పొలం తుఫాను ప్రాంతం వెలుపలి పొలాల కంటే ఎక్కువగా, చుట్టుపక్కల పొలాలంత మారింది: మీ పొలం మాత్రమే కాదు, మీ ప్రాంతమంతా దెబ్బతింది.",
        )
    if ring:
        return (
            "आपका खेत आसपास के खेतों से ज़्यादा बदला: यह आपके खेत का स्थानीय बदलाव दिखता है।",
            "Your field changed more than the fields around it: this looks local to your field.",
            "మీ పొలం చుట్టుపక్కల పొలాల కంటే ఎక్కువగా మారింది: ఇది మీ పొలానికే పరిమితమైన మార్పులా ఉంది.",
        )
    return (
        "आपका खेत न पास के खेतों से ज़्यादा बदला, न दूर के खेतों से।",
        "Your field did not change more than nearby fields, or more than distant ones.",
        "మీ పొలం సమీప పొలాల కంటే గానీ, దూరంలోని పొలాల కంటే గానీ ఎక్కువగా మారలేదు.",
    )


def _weather_line(ev: Evidence) -> tuple[str, str]:
    w = ev.weather
    if w is None:
        return ("मौसम का डेटा इस बार नहीं मिल सका।", "Weather data could not be retrieved this time.")
    if w.corroborated:
        rain = f"{w.max_daily_mm:.1f}" if w.max_daily_mm is not None else None
        hi = "मौसम मॉडल के अनुसार उस समय मौसम बिगड़ा था"
        en = "The weather model indicates bad weather around that time"
        if rain:
            hi += f" (एक दिन में अधिकतम {rain} मिमी बारिश)"
            en += f" (up to {rain} mm of rain in a day)"
        return hi + "।", en + "."
    return (
        ("मौसम मॉडल में इस दौरान कुछ ख़ास नहीं दिखता, पर उसका ग्रिड बड़ा है और छोटी ओलावृष्टि छूट सकती है, इसलिए "
        "इससे आपकी बात ग़लत साबित नहीं होती।"),
        ("The weather model shows little in this period, but its grid is coarse and can miss a small "
        "hail cell, so this does not count against what you reported."),
    )


_LEVEL_CLOSE = {
    "strong": (
        "यह सबूत है, दावे का फ़ैसला नहीं।",
        "This is evidence, not a claim decision.",
    ),
    "moderate": (
        "यह सबूत है, दावे का फ़ैसला नहीं।",
        "This is evidence, not a claim decision.",
    ),
    "weak": (
        "अगर आपका नुकसान हुआ है तो इस नतीजे से रुकें नहीं, क्योंकि सैटेलाइट हर नुकसान नहीं देख पाता।",
        ("If you have a loss, do not let this result stop you, because a satellite cannot see every "
        "kind of damage."),
    ),
    "insufficient": (
        "सबूत का इंतज़ार न करें। नई सैटेलाइट तस्वीर आने पर यह जाँच दोबारा चलेगी।",
        "Do not wait for the evidence. This check will run again when a new satellite image arrives.",
    ),
    "not_damage_likely_harvest": (
        "अगर आपने फ़सल नहीं काटी थी, तो हमें बताएँ और खेत की तस्वीरें रखें।",
        "If you did not harvest, tell us and keep photographs of the field.",
    ),
}


def template_explanation(ev: Evidence, level: str) -> tuple[str, str]:
    head = headlines(level, ev.event.type)
    parts = [(head[0] + "।", head[1] + "."), _sat_line(ev)]
    conceded = [o for o in ev.cross_examination if o.outcome == "conceded"]
    tests = tests_line(ev)
    if tests and not any(o.id == "regional_trend" for o in conceded):
        parts.append(tests[:2])  # a conceded regional_trend finding already says the same thing
    parts.append(_weather_line(ev))
    if conceded:
        parts.append((conceded[0].finding_hi, conceded[0].finding_en))
    parts.append(_LEVEL_CLOSE[level])
    return " ".join(p[0] for p in parts), " ".join(p[1] for p in parts)


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
    template_hi, template_en = template_explanation(ev, ev.verdict.level)
    ev.explanation_hi, ev.explanation_en = template_hi, template_en
    ev.verdict.headline_te = headlines(ev.verdict.level, ev.event.type)[2]


def explain(ev: Evidence) -> dict:
    """Fills explanations and Telugu headline fields. Returns which LLM attempts were used."""
    level = ev.verdict.level
    _, head_en, head_te = headlines(level, ev.event.type)
    template_hi, template_en = template_explanation(ev, level)
    allowed = allowed_numbers(ev)
    report = {"hi": "template", "en": "template", "te": "none", "headline_te": "template",
              "rejected": []}

    summary = digest(ev)
    ev.explanation_hi, ev.explanation_en = template_hi, template_en
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
