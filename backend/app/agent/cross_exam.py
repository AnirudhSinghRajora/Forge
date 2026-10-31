"""The cross-examination: a hostile surveyor's objections, each answered by a test on real values.

Pure functions over Evidence. `measured` holds only values copied from the evidence. An objection
can be conceded, and a concession that more data could resolve yields a FollowUp the graph can loop
on. The graph emits one `objection` trace event per entry, in this order, so the UI can animate it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.agent import rubric
from app.evidence.schema import Evidence, Objection

ORDER = (
    "harvest", "wrong_plot", "wrong_date", "cloud_shadow", "corrupt_scene", "regional_trend",
    "pre_trend", "too_small", "stale_crop",
)

BARE_MIN = 0.6
NEIGHBOUR_BARE_MIN = 0.30
HISTORY_SIMILAR = -0.10
PRE_NDVI_MIN = 0.3
VALID_FRAC_MIN = 0.8
TOO_SMALL_HA = 0.2
HISTORY_PRE_DIFF = 0.2
WATER_PRE_MIN_PCT = 70
HARVEST_MIN_DELTA = -0.10
PRE_TREND_FALLING = -0.10
WHOLE_FIELD_DROP = 0.8

_HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर",
              "नवंबर", "दिसंबर"]
_PATTERN_HI = {"uniform": "पूरे खेत में एक जैसा", "patchy": "जगह-जगह", "none": "कोई ख़ास नहीं"}


@dataclass(frozen=True)
class FollowUp:
    """More data that could resolve a conceded objection."""
    kind: str  # exclude_scene | redate | widen_post | widen_pre
    objection: str
    scene_id: str | None = None
    event_date: date | None = None
    note: str = ""


def date_hi(d: date) -> str:
    return f"{d.day} {_HI_MONTHS[d.month - 1]}"


def date_en(d: date) -> str:
    return d.strftime("%-d %b")


def pct(x: float) -> str:
    return f"{x * 100:.0f}"


def signed(x: float) -> str:
    """Two decimals with a sign, without the misleading "-0.00" of a change that rounds to nothing."""
    return "0.00" if abs(x) < 0.005 else f"{x:+.2f}"


def _obj(oid, challenge_hi, challenge_en, test, measured, outcome, finding_hi, finding_en):
    return Objection(
        id=oid, challenge_hi=challenge_hi, challenge_en=challenge_en, test=test,
        measured=measured, outcome=outcome, finding_hi=finding_hi, finding_en=finding_en,
    )


def _no_post(ev: Evidence, hi: str, en: str) -> tuple[str, str]:
    if rubric.comparison_incomplete(ev):
        return (
            ("घटना के बाद की तस्वीर मिली है, पर सैटेलाइट संग्रह धीमा होने से तुलना पूरी नहीं हुई, इसलिए यह जाँच अभी नहीं "
            "हो सकी। यह दोबारा चलेगी।"),
            ("An image from after the event exists, but the satellite archive was too slow to finish "
            "the comparison, so this could not be tested yet. It will be retried."),
        )
    return hi, en


def check_harvest(ev: Evidence) -> Objection:
    challenge_hi = "यह नुकसान नहीं, कटाई है। फ़सल कट गई तो हरियाली तो घटेगी ही।"
    challenge_en = "This isn't damage, it's harvest. Of course greenness falls once a crop is cut."
    test = (
        f"Bare fraction after the event > {BARE_MIN} and the whole field fell, and comparable neighbours "
        f"also bare (>= {NEIGHBOUR_BARE_MIN}), and this plot's history shows a similar drop."
    )
    bare = ev.optical.post_bare_fraction
    pattern = ev.optical.within_plot_pattern
    neighbour_bare = ev.neighbours.neighbour_bare_fraction_post if ev.neighbours else None
    history = ev.history
    excess = history.excess_vs_history if history else None
    typical = history.typical_delta if history else None
    measured = {
        "post_bare_fraction": bare, "within_plot_pattern": pattern,
        "neighbour_bare_fraction_post": neighbour_bare, "history_typical_delta": typical,
        "excess_vs_history": excess,
        "history_downweighted": history.downweighted if history else None,
    }

    def out(outcome, hi, en):
        return _obj("harvest", challenge_hi, challenge_en, test, measured, outcome, hi, en)

    if ev.optical.post is None or bare is None:
        return out("unresolved", *_no_post(
            ev,
            "घटना के बाद की कोई साफ़ तस्वीर नहीं मिली, इसलिए कटाई की जाँच अभी नहीं हो सकी। क्या आपने "
            "घटना के बाद फ़सल काटी थी?",
            "There is no clear image after the event, so harvest could not be tested yet. Did you "
            "harvest after the event?",
        ))
    delta = ev.optical.plot_delta_ndvi
    drop_frac = ev.optical.drop_frac
    measured["drop_frac"] = drop_frac
    if bare <= BARE_MIN:
        return out(
            "rebutted",
            f"कटाई जैसा नहीं दिखता: घटना के बाद खेत का {pct(bare)}% हिस्सा ही खाली मिट्टी है (कटाई में 60% से "
            f"ज़्यादा होता है), और गिरावट का पैटर्न '{_PATTERN_HI.get(pattern or 'none')}' है।",
            f"This does not look like harvest: only {pct(bare)}% of the plot is bare after the "
            f"event (harvest leaves over 60%), and the pattern of decline is '{pattern or 'none'}'.",
        )
    if delta is not None and delta > HARVEST_MIN_DELTA:
        change = signed(delta)
        return out(
            "rebutted",
            f"खेत का {pct(bare)}% हिस्सा खाली मिट्टी है, पर इन तस्वीरों के बीच बदलाव {change} ही है। इनके बीच कटाई नहीं "
            "दिखती; हो सकता है ज़मीन पहले से खाली हो।",
            f"{pct(bare)}% of the plot is bare, but it changed by only {change} between these images. "
            "No harvest shows between them; the land may already have been bare.",
        )
    # The whole field fell. A real harvest can miss the strict "uniform" pattern when its spread is
    # wide (live case: 93% of pixels dropped, IQR over 0.12), so the share that dropped counts too.
    whole_field = pattern == "uniform" or (drop_frac is not None and drop_frac >= WHOLE_FIELD_DROP)
    if not whole_field:
        return out(
            "unresolved",
            f"खेत का {pct(bare)}% हिस्सा खाली मिट्टी है, पर गिरावट पूरे खेत में नहीं है। तस्वीर से यह तय नहीं हो सकता। क्या "
            "आपने घटना के बाद फ़सल काटी थी?",
            f"{pct(bare)}% of the plot is bare, but the decline does not cover the whole field. The "
            "image alone cannot settle this. Did you harvest after the event?",
        )

    neighbours_support = None if neighbour_bare is None else neighbour_bare >= NEIGHBOUR_BARE_MIN
    history_support = None
    if history is not None and excess is not None and not history.downweighted:
        history_support = excess > HISTORY_SIMILAR
    concede = (history_support is True) or (neighbours_support is True and history_support is None)
    if concede:
        hi_bits = [f"खेत का {pct(bare)}% हिस्सा खाली मिट्टी है और गिरावट पूरे खेत में है"]
        en_bits = [f"{pct(bare)}% of the plot is bare and the decline covers the whole field"]
        if neighbours_support:
            hi_bits.append(f"आसपास के मिलते-जुलते खेतों में भी {pct(neighbour_bare)}% ज़मीन खाली है")
            en_bits.append(f"comparable fields nearby are also {pct(neighbour_bare)}% bare")
        if history_support:
            hi_bits.append(f"पिछले वर्षों में इसी समय इस खेत में भी ऐसी ही गिरावट ({typical:+.2f}) रही है")
            en_bits.append(f"this plot usually drops about as much at this time of year ({typical:+.2f})")
        return out(
            "conceded",
            "यह कटाई से मेल खाता है: " + "; ".join(hi_bits) + "। क्या आपने घटना के बाद फ़सल काटी थी?",
            "This matches harvest: " + "; ".join(en_bits) + ". Did you harvest after the event?",
        )
    return out(
        "unresolved",
        f"खेत का {pct(bare)}% हिस्सा खाली मिट्टी है और गिरावट पूरे खेत में है, जो कटाई जैसी लगती है, पर आसपास "
        "के खेत या इस खेत का पुराना रिकॉर्ड इसकी पुष्टि नहीं करते। तस्वीर से यह तय नहीं हो सकता। क्या आपने "
        "घटना के बाद फ़सल काटी थी?",
        f"{pct(bare)}% of the plot is bare and the whole field fell, which looks like harvest, but "
        "neither nearby fields nor this plot's history confirm it. The image alone cannot settle "
        "this. Did you harvest after the event?",
    )


def _pre_event_water(ev: Evidence) -> list[int]:
    """Water share of the plot on pre-event images where QA found it mostly water."""
    shares = []
    for q in ev.optical.scenes_considered:
        if q.date > ev.event.date:
            continue
        for reason in q.reasons:
            m = re.search(r"(\d+)% of plot pixels classified as water", reason)
            if m and int(m[1]) >= WATER_PRE_MIN_PCT:
                shares.append(int(m[1]))
    return shares


def check_wrong_plot(ev: Evidence) -> Objection:
    challenge_hi = "क्या यह आपका ही खेत है? घटना से पहले यहाँ फ़सल थी भी?"
    challenge_en = "Is this even your field? Was there a crop here before the event?"
    test = f"Plot median NDVI on the last accepted scene before the event >= {PRE_NDVI_MIN}."
    pre = ev.optical.pre
    if pre is None:
        water = _pre_event_water(ev)
        if len(water) >= 2:
            shares = ", ".join(f"{w}%" for w in water)
            return _obj(
                "wrong_plot", challenge_hi, challenge_en, test,
                {"pre_ndvi_median": None, "pre_event_water_pct": water}, "conceded",
                f"घटना से पहले की तस्वीरों में यह जगह पानी दिखती है ({shares}), यहाँ खड़ी फ़सल नहीं दिखती। कृपया खेत की "
                "सीमा दोबारा जाँच लें।",
                f"Before the event the images show this place as water ({shares}), with no standing "
                "crop visible. Please re-check the field boundary.",
            )
        return _obj(
            "wrong_plot", challenge_hi, challenge_en, test,
            {"pre_ndvi_median": None}, "unresolved",
            "घटना से पहले की कोई भरोसेमंद तस्वीर नहीं मिली, इसलिए यह जाँच नहीं हो सकी।",
            "No trustworthy image from before the event was found, so this could not be tested.",
        )
    measured = {"pre_ndvi_median": pre.ndvi_median, "pre_date": pre.date.isoformat(),
                "pre_scene_id": pre.scene_id}
    if pre.ndvi_median < PRE_NDVI_MIN:
        return _obj(
            "wrong_plot", challenge_hi, challenge_en, test, measured, "conceded",
            f"{date_hi(pre.date)} की तस्वीर में इस खेत की हरियाली (NDVI {pre.ndvi_median:.2f}) बहुत कम है: "
            "घटना से पहले यहाँ खड़ी फ़सल नहीं दिखती। कृपया खेत की सीमा दोबारा जाँच लें।",
            f"The {date_en(pre.date)} image shows very low greenness here (NDVI "
            f"{pre.ndvi_median:.2f}): no standing crop is visible before the event. Please re-check "
            "the field boundary.",
        )
    return _obj(
        "wrong_plot", challenge_hi, challenge_en, test, measured, "rebutted",
        f"घटना से पहले {date_hi(pre.date)} को इस खेत में फ़सल दिख रही थी (NDVI {pre.ndvi_median:.2f})।",
        f"A crop was visible here before the event, on {date_en(pre.date)} (NDVI "
        f"{pre.ndvi_median:.2f}).",
    )


def check_wrong_date(ev: Evidence, farmer_date: date | None = None) -> tuple[Objection, date | None]:
    challenge_hi = "आपने तारीख़ ग़लत बताई है। उस दिन तो कुछ हुआ ही नहीं।"
    challenge_en = "You have the date wrong. Nothing happened that day."
    test = (
        "Model-indicated rain, hail codes or strong gusts within two days of the reported date, or "
        "an official alert or cited news for it. No weather signal never counts against the farmer."
    )
    w = ev.weather
    used = ev.event.date
    measured = {
        "event_date": used.isoformat(), "date_source": ev.event.date_source,
        "farmer_date": farmer_date.isoformat() if farmer_date else None,
        "precip_mm_event_window": w.precip_mm_event_window if w else None,
        "max_daily_mm": w.max_daily_mm if w else None,
        "hail_code_hours": w.hail_code_hours if w else None,
        "max_gust_kmh": w.max_gust_kmh if w else None,
        "proposed_event_date": w.proposed_event_date.isoformat()
        if w and w.proposed_event_date else None,
        "official_alerts": len(ev.alerts), "cited_news": len(ev.news),
    }

    def out(outcome, hi, en):
        return _obj("wrong_date", challenge_hi, challenge_en, test, measured, outcome, hi, en)

    moved = farmer_date is not None and farmer_date != used
    if ev.alerts or ev.news:
        return out(
            "rebutted",
            f"{date_hi(used)} के आसपास के लिए {len(ev.alerts)} सरकारी चेतावनी और {len(ev.news)} ख़बरों "
            "का स्रोत मिला।",
            f"{len(ev.alerts)} official alerts and {len(ev.news)} cited news sources cover the days "
            f"around {date_en(used)}.",
        ), None
    if w is not None and w.corroborated:
        rain = w.max_daily_mm if w.max_daily_mm is not None else 0.0
        if moved:
            return out(
                "rebutted",
                f"आपकी बताई तारीख़ {date_hi(farmer_date)} के आसपास मौसम मॉडल में कुछ नहीं था, पर "
                f"{date_hi(used)} के आसपास था (एक दिन में अधिकतम {rain:.1f} मिमी)। जाँच {date_hi(used)} "
                "पर दोबारा की गई। कृपया तारीख़ की पुष्टि करें।",
                f"The weather model showed nothing around your date ({date_en(farmer_date)}) but did "
                f"around {date_en(used)} (up to {rain:.1f} mm in a day). The evidence was re-run for "
                f"{date_en(used)}. Please confirm the date.",
            ), None
        return out(
            "rebutted",
            f"मौसम मॉडल के अनुसार {date_hi(used)} के आसपास मौसम बिगड़ा था (एक दिन में अधिकतम "
            f"{rain:.1f} मिमी)। यह मॉडल का अनुमान है, खेत पर मापा हुआ नहीं।",
            f"The weather model indicates bad weather around {date_en(used)} (up to {rain:.1f} mm in "
            "a day). This is model-indicated, not measured at the field.",
        ), None
    if w is None:
        return out(
            "unresolved",
            "मौसम का डेटा इस बार नहीं मिल सका, इसलिए तारीख़ की जाँच नहीं हो सकी। इससे आपकी बात ग़लत साबित "
            "नहीं होती।",
            "Weather data could not be retrieved, so the date could not be tested. That does not "
            "count against what you reported.",
        ), None
    if w.proposed_event_date is not None:
        proposed = w.proposed_event_date
        day = next((d for d in w.days if d.date == proposed), None)
        rain = day.precip_mm if day and day.precip_mm is not None else None
        measured["proposed_day_precip_mm"] = rain
        rain_hi = f" ({rain:.1f} मिमी)" if rain is not None else ""
        rain_en = f" ({rain:.1f} mm)" if rain is not None else ""
        return out(
            "conceded",
            f"{date_hi(used)} के आसपास मौसम मॉडल में कुछ नहीं है, पर {date_hi(proposed)} को संकेत "
            f"है{rain_hi}। क्या घटना असल में {date_hi(proposed)} को हुई थी?",
            f"The weather model shows nothing around {date_en(used)}, but it does on "
            f"{date_en(proposed)}{rain_en}. Could the event have been on {date_en(proposed)}?",
        ), proposed
    return out(
        "unresolved",
        f"मौसम मॉडल में {date_hi(used)} के आसपास कोई संकेत नहीं है, और किसी और नज़दीकी तारीख़ पर भी नहीं। "
        "मॉडल का ग्रिड बड़ा होता है और छोटी ओलावृष्टि छूट सकती है, इसलिए इससे आपकी बात ग़लत साबित नहीं होती।",
        f"The weather model shows no signal around {date_en(used)} or on any nearby date. Its grid "
        "is coarse and can miss a small hail cell, so this does not count against what you reported.",
    ), None


def check_cloud_shadow(ev: Evidence) -> tuple[Objection, list[str]]:
    challenge_hi = "तस्वीर में बादल या उसकी छाया है। हरियाली कम दिखना उसी वजह से है।"
    challenge_en = "That's a cloud or its shadow. The greenness only looks lower because of it."
    test = f"Share of clear plot pixels on each image used >= {VALID_FRAC_MIN}."
    pre, post = ev.optical.pre, ev.optical.post
    measured = {
        "pre_valid_frac": pre.valid_frac if pre else None,
        "post_valid_frac": post.valid_frac if post else None,
        "pre_scene_id": pre.scene_id if pre else None,
        "post_scene_id": post.scene_id if post else None,
    }

    def out(outcome, hi, en):
        return _obj("cloud_shadow", challenge_hi, challenge_en, test, measured, outcome, hi, en)

    if post is None:
        if ev.sar is not None and ev.sar.usable:
            return out(
                "rebutted",
                "यहाँ रडार का इस्तेमाल हुआ है, जो बादलों के पार देख सकता है, इसलिए बादल का असर नहीं है।",
                "This rests on radar, which sees through cloud, so cloud cannot explain it.",
            ), []
        return out("unresolved", *_no_post(
            ev,
            "घटना के बाद की कोई साफ़ तस्वीर नहीं मिली, इसलिए यह जाँच नहीं हो सकी।",
            "There is no clear image after the event, so this could not be tested.",
        )), []
    bad = [s for s in (pre, post) if s is not None and s.valid_frac < VALID_FRAC_MIN]
    if bad:
        worst = min(bad, key=lambda s: s.valid_frac)
        return out(
            "conceded",
            f"{date_hi(worst.date)} की तस्वीर में खेत का केवल {pct(worst.valid_frac)}% हिस्सा साफ़ दिखता "
            "है। बाकी बादल या छाया हो सकता है, इसलिए यह तस्वीर पूरी तरह भरोसेमंद नहीं है।",
            f"Only {pct(worst.valid_frac)}% of the plot is clear on the {date_en(worst.date)} image. "
            "The rest may be cloud or shadow, so this image is not fully reliable.",
        ), [s.scene_id for s in bad]
    return out(
        "rebutted",
        f"बादल या छाया की बात सही नहीं: घटना के बाद की तस्वीर में खेत का {pct(post.valid_frac)}% हिस्सा साफ़ है।",
        f"Cloud or shadow does not explain this: {pct(post.valid_frac)}% of the plot is clear on the "
        "image after the event.",
    ), []


def check_corrupt_scene(ev: Evidence) -> tuple[Objection, list[str]]:
    challenge_hi = "सैटेलाइट की तस्वीर ही ख़राब हो सकती है। ऐसा होता है।"
    challenge_en = "The satellite image itself may be bad. That happens."
    test = "Radiometric and temporal QA status of every image considered; only clean ones are used."
    scenes = ev.optical.scenes_considered
    rejected = [s for s in scenes if s.status == "rejected"]
    pre_st, post_st = rubric.pre_status(ev), rubric.post_status(ev)
    post = ev.optical.post
    sar_ok = ev.sar is not None and ev.sar.usable
    sp = rubric.sar_p(ev)
    measured = {
        "scenes_considered": len(scenes),
        "scenes_rejected": len(rejected),
        "rejected": [{"id": s.id, "date": s.date.isoformat(), "reasons": s.reasons}
                     for s in rejected],
        "pre_status": pre_st, "post_status": post_st,
        "post_context_ndvi_median": next(
            (s.context_ndvi_median for s in scenes if post and s.id == post.scene_id), None
        ),
        "sar_usable": sar_ok, "sar_placebo_p": sp,
    }

    def out(outcome, hi, en):
        return _obj("corrupt_scene", challenge_hi, challenge_en, test, measured, outcome, hi, en)

    n_rej = len(rejected)
    rej_hi = f"{n_rej} ख़राब तस्वीरें पहले ही हटा दी गईं" if n_rej else "कोई तस्वीर ख़राब नहीं मिली"
    rej_en = f"{n_rej} bad images were already thrown out" if n_rej else "no image failed QA"

    if post is None:
        if sar_ok:
            return out(
                "rebutted",
                f"{rej_hi}। यह नतीजा उन पर नहीं, रडार की जोड़ी पर टिका है।",
                f"{rej_en.capitalize()}. This result rests on a radar pair, not on those.",
            ), []
        return out("unresolved", *_no_post(
            ev,
            f"{rej_hi}, और घटना के बाद की कोई भरोसेमंद तस्वीर नहीं बची। इसलिए अगली तस्वीर का इंतज़ार है।",
            f"{rej_en.capitalize()}, and no trustworthy image remains after the event. The next "
            "pass is needed.",
        )), []
    if post_st == "suspect" or pre_st == "suspect":
        suspects = [
            s.scene_id for s, st in ((ev.optical.pre, pre_st), (post, post_st)) if s and st == "suspect"
        ]
        if sar_ok and sp is not None and sp <= rubric.P_SAR:
            return out(
                "rebutted",
                f"इस तस्वीर में पूरे इलाक़े की हरियाली अचानक बदली दिखती है, पर रडार (p = {sp:.3f}) भी बदलाव "
                "दिखाता है। दूसरा सेंसर इसकी पुष्टि करता है।",
                f"This image shows a sudden shift across the whole area, but radar (p = {sp:.3f}) "
                "shows a change too. A second sensor confirms it.",
            ), []
        return out(
            "conceded",
            "इस तस्वीर में पूरे इलाक़े की हरियाली अचानक बदली दिखती है और कोई दूसरा सेंसर इसकी पुष्टि नहीं करता। "
            "यह तस्वीर संदिग्ध है।",
            "This image shows a sudden shift across the whole area, and no second sensor confirms "
            "it. The image is suspect.",
        ), suspects
    return out(
        "rebutted",
        f"जिन तस्वीरों पर नतीजा टिका है वे जाँच में पास हुईं, और {rej_hi}।",
        f"The images behind this result passed QA, and {rej_en}.",
    ), []


def check_regional_trend(ev: Evidence) -> Objection:
    challenge_hi = "पूरे इलाक़े में ऐसा ही हुआ है। इसमें आपके खेत की क्या ख़ास बात है?"
    challenge_en = "The whole area looks like this. What's special about your field?"
    test = (
        "Two same-shape placebo tests: against immediate neighbours (ring) and against comparable "
        f"fields 5-12 km away (far). Either at p <= {rubric.P_FIELD} counts."
    )
    optical = ev.neighbours is not None and ev.optical.post is not None
    ring = ev.neighbours.placebo if optical else None
    far = ev.neighbours.far_placebo if optical else None
    sar = ev.sar.placebo if not optical and ev.sar is not None else None

    def facts(prefix: str, placebo) -> dict:
        return {
            f"{prefix}_n_placebos": placebo.n_placebos if placebo else None,
            f"{prefix}_n_at_least_as_extreme": placebo.n_at_least_as_extreme if placebo else None,
            f"{prefix}_p_value": placebo.p_value if placebo else None,
            f"{prefix}_insufficient_reason": placebo.insufficient_reason if placebo else None,
        }

    measured = {**facts("ring", ring), **facts("far", far), **facts("radar", sar)}

    def out(outcome, hi, en):
        return _obj("regional_trend", challenge_hi, challenge_en, test, measured, outcome, hi, en)

    if not optical:
        p = rubric.usable_p(sar)
        if p is None:
            n = sar.n_placebos if sar else 0
            return out(
                "unresolved",
                f"तुलना के लिए आसपास पर्याप्त मिलते-जुलते खेत नहीं मिले ({n}; कम से कम {rubric.MIN_PLACEBOS} "
                "चाहिए), इसलिए यह जाँच नहीं हो सकी।",
                f"Too few comparable fields nearby ({n}; at least {rubric.MIN_PLACEBOS} are needed), so "
                "this could not be tested.",
            )
        n, k = sar.n_placebos, sar.n_at_least_as_extreme
        if p <= rubric.P_SAR:
            return out(
                "rebutted",
                f"रडार में आसपास के {n} मिलते-जुलते खेतों में से केवल {k} में इतना बदलाव हुआ (p = {p:.3f})।",
                f"On radar, only {k} of {n} look-alike fields nearby changed this much (p = {p:.3f}).",
            )
        return out(
            "conceded",
            f"रडार में आसपास के {n} मिलते-जुलते खेतों में से {k} में इतना बदलाव हुआ (p = {p:.3f})। आपका खेत इलाक़े "
            "से अलग नहीं दिखता।",
            f"On radar, {k} of {n} look-alike fields nearby changed this much (p = {p:.3f}). Your field "
            "does not stand out from the area.",
        )

    ring_p, far_p = rubric.usable_p(ring), rubric.usable_p(far)
    if ring_p is None and far_p is None:
        n = ring.n_placebos if ring else 0
        return out(
            "unresolved",
            f"तुलना के लिए पर्याप्त मिलते-जुलते खेत नहीं मिले ({n}; कम से कम {rubric.MIN_PLACEBOS} चाहिए), इसलिए यह "
            "जाँच नहीं हो सकी।",
            f"Too few comparable fields ({n}; at least {rubric.MIN_PLACEBOS} are needed), so this "
            "could not be tested.",
        )
    ring_yes, far_yes = rubric.ring_significant(ev), rubric.far_significant(ev)
    far_hi = (f"5-12 किमी दूर के {far.n_placebos} मिलते-जुलते खेतों में से {far.n_at_least_as_extreme} में इतना बदलाव हुआ "
              f"(p = {far_p:.3f})") if far_p is not None else "दूर के खेतों से तुलना नहीं हो सकी"
    far_en = (f"{far.n_at_least_as_extreme} of {far.n_placebos} comparable fields 5-12 km away changed this "
              f"much (p = {far_p:.3f})") if far_p is not None else "the comparison with distant fields was not available"
    ring_hi = (f"आसपास के {ring.n_placebos} खेतों में से {ring.n_at_least_as_extreme} में इतना बदलाव हुआ "
               f"(p = {ring_p:.3f})") if ring_p is not None else "पास के खेतों से तुलना नहीं हो सकी"
    ring_en = (f"{ring.n_at_least_as_extreme} of {ring.n_placebos} fields right around it changed this much "
               f"(p = {ring_p:.3f})") if ring_p is not None else "the comparison with nearby fields was not available"
    if far_yes and ring_yes:
        return out(
            "rebutted",
            f"आपका खेत दूर के खेतों से भी अलग है और पास के खेतों से भी: {far_hi}; {ring_hi}।",
            f"Your field stands apart from both distant and nearby fields: {far_en}; {ring_en}.",
        )
    if far_yes:
        return out(
            "rebutted",
            f"आपका पूरा इलाक़ा प्रभावित हुआ, सिर्फ़ आपका खेत नहीं: {far_hi}; {ring_hi}।",
            f"Your whole area was hit, not only your field: {far_en}; {ring_en}.",
        )
    if ring_yes:
        return out(
            "rebutted",
            f"यह आपके खेत का स्थानीय नुकसान दिखता है: आसपास के खेतों से यह अलग है। {ring_hi}; {far_hi}।",
            f"This looks like a local loss on your field: it stands apart from the fields around it. "
            f"{ring_en}; {far_en}.",
        )
    return out(
        "conceded",
        f"आपका खेत न पास के खेतों से अलग दिखता है, न दूर के खेतों से: {ring_hi}; {far_hi}। यह आपकी बात को ग़लत नहीं "
        "ठहराता, पर यह आपके खेत का अलग सबूत भी नहीं है।",
        f"Your field stands apart from neither nearby nor distant fields: {ring_en}; {far_en}. That "
        "does not refute you, but it is not field-specific evidence either.",
    )


def check_pre_trend(ev: Evidence) -> Objection:
    challenge_hi = "आपका खेत तो घटना से पहले ही गिर रहा था। इसका घटना से क्या लेना-देना?"
    challenge_en = "Your field was already falling before the event. What has that to do with it?"
    test = f"The same statistic on the last accepted pre-event pair: conceded at or below {PRE_TREND_FALLING}."
    neighbours = ev.neighbours
    delta = neighbours.pretrend_delta if neighbours else None
    placebo = neighbours.pretrend_placebo if neighbours else None
    measured = {"pretrend_delta": delta, "pretrend_p_value": placebo.p_value if placebo else None}
    if delta is None:
        return _obj(
            "pre_trend", challenge_hi, challenge_en, test, measured, "unresolved",
            "घटना से पहले की तस्वीरों की जोड़ी नहीं मिली, इसलिए यह जाँच नहीं हो सकी।",
            "No pair of images from before the event was available, so this could not be tested.",
        )
    if delta <= PRE_TREND_FALLING:
        return _obj(
            "pre_trend", challenge_hi, challenge_en, test, measured, "conceded",
            f"यह सही है: घटना से पहले ही इस खेत की हरियाली {signed(delta)} बदल रही थी। इसलिए सारी गिरावट को घटना से जोड़ना "
            "ठीक नहीं होगा।",
            f"That's fair: this field's greenness was already changing by {signed(delta)} before the "
            "event, so not all of the fall can be put down to it.",
        )
    return _obj(
        "pre_trend", challenge_hi, challenge_en, test, measured, "rebutted",
        f"घटना से पहले यह खेत नहीं गिर रहा था: उससे पहले की तस्वीरों के बीच बदलाव {signed(delta)} था।",
        f"This field was not falling before the event: the change between the earlier images was "
        f"{signed(delta)}.",
    )


def check_too_small(ev: Evidence) -> Objection:
    area = ev.plot.area_ha
    challenge_hi = "इतने छोटे खेत को सैटेलाइट ठीक से देख ही नहीं सकता।"
    challenge_en = "A satellite can't see a plot this small properly."
    test = f"Plot area >= {TOO_SMALL_HA} ha."
    n_pixels = ev.optical.post.n_pixels if ev.optical.post else None
    measured = {"area_ha": area, "n_pixels": n_pixels}
    if area < TOO_SMALL_HA:
        return _obj(
            "too_small", challenge_hi, challenge_en, test, measured, "conceded",
            f"यह सही है: {area:.2f} हेक्टेयर का खेत सैटेलाइट के लिए छोटा है। कृपया खेत की तस्वीरें भी साथ रखें।",
            f"That's fair: at {area:.2f} ha this plot is small for a satellite. Please keep "
            "photographs of the field too.",
        )
    return _obj(
        "too_small", challenge_hi, challenge_en, test, measured, "rebutted",
        f"{area:.2f} हेक्टेयर का खेत 10 मीटर के पिक्सेल से मापने लायक है।",
        f"At {area:.2f} ha this plot is large enough to measure with 10 m pixels.",
    )


def check_stale_crop(ev: Evidence) -> Objection:
    challenge_hi = "पिछले साल यहाँ कोई और फ़सल थी। पुराने रिकॉर्ड से तुलना बेकार है।"
    challenge_en = "That field grew something else last year. Comparing to history means nothing."
    test = f"Pre-event NDVI this year vs. the same window in past years, difference <= {HISTORY_PRE_DIFF}."
    h = ev.history
    pre = ev.optical.pre
    years = h.years if h else []
    usable = [y for y in years if y.pre_ndvi is not None]
    measured = {
        "pre_ndvi_median": pre.ndvi_median if pre else None,
        "history_pre_ndvi": {str(y.year): y.pre_ndvi for y in usable},
        "downweighted": h.downweighted if h else None,
    }
    if h is None or not usable:
        return _obj(
            "stale_crop", challenge_hi, challenge_en, test, measured, "unresolved",
            "पिछले वर्षों की भरोसेमंद तस्वीरें नहीं मिलीं, इसलिए यह तुलना नहीं हो सकी।",
            "No reliable images from past years were found, so this comparison could not be made.",
        )
    if h.downweighted or pre is None:
        if pre is None:
            return _obj(
                "stale_crop", challenge_hi, challenge_en, test, measured, "unresolved",
                "इस साल की घटना से पहले की तस्वीर नहीं है, इसलिए तुलना नहीं हो सकी।",
                "There is no image from before this year's event, so the comparison could not be made.",
            )
        return _obj(
            "stale_crop", challenge_hi, challenge_en, test, measured, "conceded",
            "यह सही हो सकता है: पिछले वर्षों में इसी समय इस खेत की हरियाली इस साल से काफ़ी अलग थी, शायद फ़सल "
            "अलग थी। इसलिए पिछले वर्षों की तुलना को कम महत्व दिया गया है।",
            "That may be right: this plot's greenness in the same window of past years was quite "
            "different, possibly a different crop. The comparison with history is down-weighted.",
        )
    return _obj(
        "stale_crop", challenge_hi, challenge_en, test, measured, "rebutted",
        f"इस साल (NDVI {pre.ndvi_median:.2f}) और पिछले वर्षों की हरियाली मिलती-जुलती है, इसलिए तुलना ठीक है।",
        f"Greenness this year (NDVI {pre.ndvi_median:.2f}) is similar to past years, so the "
        "comparison holds.",
    )


def run(
    ev: Evidence, farmer_date: date | None = None
) -> tuple[list[Objection], list[FollowUp]]:
    """Runs all objections in order. Returns them and the follow-ups more data could settle."""
    followups: list[FollowUp] = []
    wrong_date, proposed = check_wrong_date(ev, farmer_date)
    if proposed is not None:
        followups.append(FollowUp("redate", "wrong_date", event_date=proposed,
                                  note=f"weather peak on {proposed.isoformat()}"))
    cloud, cloudy_ids = check_cloud_shadow(ev)
    followups.extend(FollowUp("exclude_scene", "cloud_shadow", scene_id=i) for i in cloudy_ids)
    corrupt, suspect_ids = check_corrupt_scene(ev)
    followups.extend(FollowUp("exclude_scene", "corrupt_scene", scene_id=i) for i in suspect_ids)
    if ev.optical.post is None and not rubric.comparison_incomplete(ev):
        followups.append(FollowUp("widen_post", "corrupt_scene", note="no accepted post scene"))
    if ev.optical.pre is None:
        followups.append(FollowUp("widen_pre", "wrong_plot", note="no accepted pre scene"))
    objections = [
        check_harvest(ev), check_wrong_plot(ev), wrong_date, cloud, corrupt,
        check_regional_trend(ev), check_pre_trend(ev), check_too_small(ev), check_stale_crop(ev),
    ]
    return objections, followups
