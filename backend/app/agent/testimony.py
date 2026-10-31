"""The Field Testifies: the evidence read in the first person, from a template over real values.

It carries the verdict's caveats, works for every verdict level including "no damage visible", and
never claims that the field knows the cause: "consistent with". Gemini may polish a template only
through the number validator; the template is what ships otherwise.

Telugu NEEDS NATIVE REVIEW: not checked by a native speaker.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from app.agent import explain as explain_mod
from app.agent import llm, rubric
from app.agent.cross_exam import date_en, date_hi, signed
from app.evidence.schema import Evidence

log = logging.getLogger(__name__)

_TE_MONTHS = ["జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్", "జులై", "ఆగస్టు", "సెప్టెంబర్",
              "అక్టోబర్", "నవంబర్", "డిసెంబర్"]


def _date_te(d) -> str:
    return f"{_TE_MONTHS[d.month - 1]} {d.day}"


def _caveat_lines(ev: Evidence) -> tuple[list[str], list[str], list[str]]:
    hi, en, te = [], [], []
    if ev.weather is None:
        hi.append("उस समय का मौसम डेटा मुझे नहीं मिल सका।")
        en.append("I could not get weather data for that time.")
        te.append("ఆ సమయపు వాతావరణ సమాచారం నాకు దొరకలేదు.")
    elif not ev.weather.corroborated:
        hi.append("मौसम मॉडल में मेरे ऊपर कोई ख़ास संकेत नहीं है, पर उसका ग्रिड बड़ा है और छोटी ओलावृष्टि चूक सकता है।")
        en.append("The weather model shows little over me, but its grid is coarse and can miss a small hail cell.")
        te.append("వాతావరణ నమూనాలో నాపై పెద్దగా సంకేతం లేదు, కానీ దాని గ్రిడ్ పెద్దది, చిన్న వడగళ్ల వానను అది కోల్పోవచ్చు.")
    if ev.event.date_source != "farmer":
        hi.append("जो तारीख़ यहाँ है वह मौसम से सुझाई गई है, आपसे नहीं। कृपया उसकी पुष्टि करें।")
        en.append("The date used here was suggested by the weather, not by you. Please confirm it.")
        te.append("ఇక్కడి తేదీ వాతావరణం నుంచి సూచించినది, మీరు చెప్పినది కాదు. దయచేసి నిర్ధారించండి.")
    if ev.plot.area_ha < 0.2:
        hi.append("मैं छोटा खेत हूँ, इसलिए उपग्रह मुझे ठीक से नहीं देख पाता। मेरी तस्वीरें भी रखिए।")
        en.append("I am a small field, so the satellite sees me only roughly. Please keep photographs of me too.")
        te.append("నేను చిన్న పొలం, కాబట్టి ఉపగ్రహం నన్ను సరిగా చూడలేదు. నా ఫోటోలు కూడా ఉంచండి.")
    if ev.history is not None and ev.history.downweighted:
        hi.append("पिछले वर्षों में मुझ पर शायद कोई और फ़सल थी, इसलिए उनसे तुलना कमज़ोर है।")
        en.append("I may have grown a different crop in past years, so comparing with them is weak.")
        te.append("గత ఏళ్లలో నాపై వేరే పంట ఉండి ఉండవచ్చు, కాబట్టి వాటితో పోలిక బలహీనం.")
    return hi, en, te


def templates(ev: Evidence) -> tuple[str, str, str]:
    """Deterministic testimony in Hindi, English and Telugu."""
    level = ev.verdict.level if ev.verdict else "insufficient"
    hi = ["मैं आपका खेत हूँ।"]
    en = ["I am your field."]
    te = ["నేను మీ పొలాన్ని."]
    o = ev.optical
    if o.pre is not None:
        hi.append(f"{date_hi(o.pre.date)} को उपग्रह ने मुझे देखा। तब मेरी हरियाली (NDVI) {o.pre.ndvi_median:.2f} थी।")
        en.append(f"On {date_en(o.pre.date)} the satellite saw me. My greenness (NDVI) was {o.pre.ndvi_median:.2f}.")
        te.append(f"{_date_te(o.pre.date)}న ఉపగ్రహం నన్ను చూసింది. అప్పుడు నా పచ్చదనం (NDVI) {o.pre.ndvi_median:.2f}.")
    rejected = [q for q in o.scenes_considered if q.status == "rejected"]
    if rejected:
        # The one nearest the event, preferring an image from after it: that is the one that matters.
        q = min(rejected, key=lambda x: (x.date <= ev.event.date, abs((x.date - ev.event.date).days)))
        cloud = any(r.startswith("Q2") for r in q.reasons)
        if cloud:
            hi.append(f"{date_hi(q.date)} की तस्वीर में मैं बादलों से ढका था, इसलिए उसे गवाही में नहीं लिया गया।")
            en.append(f"On the {date_en(q.date)} image I was hidden by cloud, so it was kept out of this testimony.")
            te.append(f"{_date_te(q.date)} చిత్రంలో నేను మేఘాల కింద ఉన్నాను, కాబట్టి దాన్ని ఈ సాక్ష్యంలో తీసుకోలేదు.")
        else:
            hi.append(f"{date_hi(q.date)} की तस्वीर जाँच में ख़राब निकली, इसलिए उसे गवाही में नहीं लिया गया।")
            en.append(f"The {date_en(q.date)} image failed its checks, so it was kept out of this testimony.")
            te.append(f"{_date_te(q.date)} చిత్రం పరీక్షల్లో విఫలమైంది, కాబట్టి దాన్ని ఈ సాక్ష్యంలో తీసుకోలేదు.")
    if o.post is not None and o.plot_delta_ndvi is not None:
        hi.append(f"{date_hi(o.post.date)} को मेरी हरियाली {o.post.ndvi_median:.2f} थी, यानी बदलाव {signed(o.plot_delta_ndvi)}।")
        en.append(f"On {date_en(o.post.date)} it was {o.post.ndvi_median:.2f}, a change of {signed(o.plot_delta_ndvi)}.")
        te.append(f"{_date_te(o.post.date)}న అది {o.post.ndvi_median:.2f}, అంటే మార్పు {signed(o.plot_delta_ndvi)}.")
    elif ev.sar is not None and ev.sar.usable and ev.sar.vh_change_db is not None and ev.sar.post_date:
        s = ev.sar
        hi.append(f"बाद में साफ़ तस्वीर नहीं मिली। {date_hi(s.post_date)} को रडार ने मुझे देखा: संकेत में {s.vh_change_db:+.1f} dB का बदलाव।")
        en.append(f"No clear image came after that. On {date_en(s.post_date)} radar saw me: a {s.vh_change_db:+.1f} dB change in the signal.")
        te.append(f"తర్వాత స్పష్టమైన చిత్రం రాలేదు. {_date_te(s.post_date)}న రాడార్ నన్ను చూసింది: సంకేతంలో {s.vh_change_db:+.1f} dB మార్పు.")
    elif rubric.comparison_incomplete(ev):
        hi.append("सैटेलाइट संग्रह धीमा था या जवाब नहीं दे रहा था, इसलिए मेरी तुलना पूरी नहीं हुई।")
        en.append("The satellite archive was slow or not responding, so my comparison did not finish.")
        te.append("ఉపగ్రహ ఆర్కైవ్ నెమ్మదిగా ఉంది లేదా స్పందించలేదు, కాబట్టి నా పోలిక పూర్తి కాలేదు.")
    else:
        hi.append("घटना के बाद मुझे दिखाने वाली कोई भरोसेमंद तस्वीर अभी नहीं है।")
        en.append("No trustworthy image shows me after the event yet.")
        te.append("సంఘటన తర్వాత నన్ను చూపే నమ్మదగిన చిత్రం ఇంకా లేదు.")

    tests = explain_mod.tests_line(ev)
    if tests:
        hi.append(tests[0])
        en.append(tests[1])
        te.append(tests[2])
    if rubric.post_too_early(ev):
        hi.append("यह तस्वीर घटना के कुछ ही दिन बाद की है। नुकसान दिखने में समय लग सकता है, इसलिए अगली तस्वीर पर फिर देखा जाएगा।")
        en.append("This image is from only days after the event. Damage can take time to show, so the next image will be checked too.")
        te.append("ఈ చిత్రం సంఘటన జరిగిన కొన్ని రోజులకే తీసినది. నష్టం కనిపించడానికి సమయం పట్టవచ్చు, కాబట్టి తదుపరి చిత్రాన్ని కూడా చూస్తాం.")

    if level in ("strong", "moderate"):
        word_hi, word_en, word_te = (
            explain_mod.EVENT_HI.get(ev.event.type, "आपदा"),
            explain_mod.EVENT_EN.get(ev.event.type, "the event"),
            explain_mod.EVENT_TE.get(ev.event.type, "విపత్తు"),
        )
        hi.append(f"मैं कारण नहीं जानता। मैं बस इतना कह सकता हूँ कि यह {word_hi} से हुए नुकसान से मेल खाता है।")
        en.append(f"I do not know the cause. I can only say this is consistent with damage from {word_en}.")
        te.append(f"కారణం నాకు తెలియదు. ఇది {word_te} వల్ల జరిగిన నష్టానికి సరిపోలుతోందని మాత్రమే చెప్పగలను.")
    elif level == "weak":
        hi.append("मुझमें नुकसान का साफ़ निशान नहीं दिखता। इसका मतलब यह नहीं कि नुकसान नहीं हुआ; उपग्रह हर नुकसान नहीं देख पाता।")
        en.append("No clear mark of damage shows on me. That does not mean there was none; a satellite cannot see everything.")
        te.append("నాపై నష్టం స్పష్టంగా కనిపించడం లేదు. నష్టం లేదని దీని అర్థం కాదు; ఉపగ్రహం అన్నీ చూడలేదు.")
    elif level == "insufficient":
        hi.append("अभी मैं पक्की गवाही नहीं दे सकता। अगली तस्वीर आने पर फिर बोलूँगा।")
        en.append("I cannot give firm testimony yet. I will speak again when the next image arrives.")
        te.append("ఇప్పుడు నేను ఖచ్చితమైన సాక్ష్యం ఇవ్వలేను. తదుపరి చిత్రం వచ్చాక మళ్లీ చెబుతాను.")
    else:
        hi.append("सच कहूँ तो मेरा बदलाव कटाई जैसा दिखता है, नुकसान जैसा नहीं। अगर मुझे काटा नहीं गया था तो यह बताइए।")
        en.append("In truth, my change looks like harvest, not damage. If I was not harvested, please say so.")
        te.append("నిజం చెప్పాలంటే, నా మార్పు నష్టం లాగా కాకుండా కోత లాగా కనిపిస్తోంది. నన్ను కోయకపోతే దయచేసి చెప్పండి.")

    caveat_hi, caveat_en, caveat_te = _caveat_lines(ev)
    hi += caveat_hi
    en += caveat_en
    te += caveat_te
    hi.append("यह मेरी गवाही है, दावे का फ़ैसला नहीं, और इसे माना ही जाएगा, ऐसा नहीं है।")
    en.append("This is my testimony, not a claim decision, and its acceptance is not guaranteed.")
    te.append("ఇది నా సాక్ష్యం, క్లెయిమ్ నిర్ణయం కాదు, దీని అంగీకారానికి హామీ లేదు.")
    return " ".join(hi), " ".join(en), " ".join(te)


def _polish(text: str, lang: str) -> str | None:
    prompt = (
        f"Polish this first-person testimony of a farm field so that it reads naturally when spoken "
        f"in {llm.LANG_NAMES[lang]}. Keep every number and date exactly, keep every caveat, keep "
        "'consistent with' wording, add no facts, and never claim the field knows the cause. Return "
        f"only the text.\n\n{text}"
    )
    return llm._plain_text(f"testimony_{lang}", llm.get_settings().gemini_model_flash,
                           [llm._text_part(prompt)])


def fill_templates(ev: Evidence) -> None:
    ev.testimony_hi, ev.testimony_en, ev.testimony_te = templates(ev)


def polish(ev: Evidence) -> None:
    """Gemini may polish a template, through the validator only. A rejection keeps the template."""
    if not llm.available():
        return
    allowed = explain_mod.allowed_numbers(ev)
    originals = (("hi", ev.testimony_hi), ("en", ev.testimony_en), ("te", ev.testimony_te))
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="testimony") as pool:
        results = list(pool.map(lambda item: _polish(item[1], item[0]), originals))
    for (lang, _), raw in zip(originals, results, strict=True):
        polished = explain_mod.checked(raw, allowed, f"testimony {lang}")
        if polished:
            setattr(ev, f"testimony_{lang}", polished)
            ev.llm_used = True


def fill(ev: Evidence) -> None:
    fill_templates(ev)
    polish(ev)
