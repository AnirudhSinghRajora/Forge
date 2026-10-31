"""How a demo plot was chosen, said wherever its result is shown (build contract, addenda 5 and 6).

A plot picked from a scan has to carry that label. This is a statement about selection only: it is
read at display time, it never enters the evidence or the sealed hash, and it changes no number.

Telugu NEEDS NATIVE REVIEW: not checked by a native speaker.
"""
from __future__ import annotations

import math

NEAR_M = 300.0
# Where the scan these labels describe is written up, for anyone who wants to check the selection.
VALIDATION_DOC = "https://github.com/AnirudhSinghRajora/Forge/blob/main/docs/validation/engine-results.md"

SELECTED_PLOTS = (
    {
        "kind": "strongest", "lat": 28.700911, "lon": 76.215719,
        "en": "This plot was picked from a scan: the strongest of 200 random plots scanned in this "
              "area. It is not a typical field.",
        "hi": "यह खेत एक स्कैन से चुना गया है: इस इलाके में स्कैन किए गए 200 यादृच्छिक खेतों में सबसे ज़्यादा "
              "गिरावट वाला। यह आम खेत नहीं है।",
        "te": "ఈ పొలాన్ని స్కాన్ నుంచి ఎంచుకున్నాం: ఈ ప్రాంతంలో స్కాన్ చేసిన 200 యాదృచ్ఛిక పొలాలలో అత్యధిక "
              "తగ్గుదల ఉన్నది. ఇది సాధారణ పొలం కాదు.",
    },
    {
        "kind": "typical", "lat": 28.715212, "lon": 76.231138,
        "en": "This plot was chosen by rule, not for its result: the median of the original 40 random "
              "plots from the band.",
        "hi": "यह खेत नियम से चुना गया है, नतीजा देखकर नहीं: उस पट्टी के मूल 40 यादृच्छिक खेतों में बीच वाला (मध्यिका)।",
        "te": "ఈ పొలాన్ని ఫలితం చూసి కాదు, నియమం ప్రకారం ఎంచుకున్నాం: ఆ పట్టీలోని అసలు 40 యాదృచ్ఛిక పొలాలలో "
              "మధ్యస్థమైనది.",
    },
    {
        "kind": "strongest", "lat": 16.906738, "lon": 81.975164,
        "en": "This plot was picked from a scan: the strongest of 51 usable plots scanned near Anaparthi. It is not a typical field. The crop was days from harvest, and the same plot also fell in other years, so normal ripening could look similar.",
        "hi": "यह खेत एक स्कैन से चुना गया है: अनपर्ति के पास स्कैन किए गए 51 उपयोगी खेतों में सबसे ज़्यादा गिरावट वाला। यह आम खेत नहीं है। फ़सल कटाई से कुछ ही दिन दूर थी, और यही खेत दूसरे सालों में भी गिरा था, इसलिए सामान्य पकाव भी ऐसा दिख सकता है।",
        "te": "ఈ పొలాన్ని స్కాన్ నుంచి ఎంచుకున్నాం: అనపర్తి సమీపంలో స్కాన్ చేసిన 51 ఉపయోగపడే పొలాలలో అత్యధిక తగ్గుదల ఉన్నది. ఇది సాధారణ పొలం కాదు. పంట కోతకు కొద్ది రోజుల దూరంలో ఉంది, ఇదే పొలం ఇతర సంవత్సరాల్లోనూ తగ్గింది, కాబట్టి సాధారణంగా పండటం కూడా ఇలాగే కనిపించవచ్చు.",
    },
)


def _metres(lon_a: float, lat_a: float, lon_b: float, lat_b: float) -> float:
    dy = (lat_a - lat_b) * 111_320
    dx = (lon_a - lon_b) * 111_320 * math.cos(math.radians((lat_a + lat_b) / 2))
    return math.hypot(dx, dy)


def selection_note(centroid) -> dict | None:
    """{hi, te, en, kind, source} for a [lon, lat] within about 300 m of a scanned plot, otherwise None."""
    if not centroid or len(centroid) < 2 or centroid[0] is None or centroid[1] is None:
        return None
    lon, lat = float(centroid[0]), float(centroid[1])
    for plot in SELECTED_PLOTS:
        if _metres(lon, lat, plot["lon"], plot["lat"]) <= NEAR_M:
            return {**{key: plot[key] for key in ("hi", "te", "en", "kind")}, "source": VALIDATION_DOC}
    return None
