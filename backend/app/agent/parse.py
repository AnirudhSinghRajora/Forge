"""Deterministic report parsing for Hindi, Telugu, English and Hinglish.

This is the no-key path for POST /api/cases and the safety net under Gemini parsing. It only
returns what the text actually says; anything it cannot tell is reported through `needs`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

_DIGITS = str.maketrans("०१२३४५६७८९౦౧౨౩౪౫౬౭౮౯", "01234567890123456789")

# (canonical name, latin words matched on word boundaries, Indic stems matched as substrings)
_CROPS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("paddy", ("paddy", "rice", "dhan", "dhaan", "chawal"), ("धान", "चावल", "వరి", "ధాన్యం")),
    ("cotton", ("cotton", "kapas", "narma", "narama"), ("कपास", "नरमा", "పత్తి")),
    ("wheat", ("wheat", "gehu", "gehun", "gehoon"), ("गेहूं", "गेहूँ", "గోధుమ")),
    ("mustard", ("mustard", "sarson"), ("सरसों", "ఆవాలు")),
    ("sugarcane", ("sugarcane", "ganna"), ("गन्ना", "गन्ने", "చెరకు", "చెరుకు")),
    ("maize", ("maize", "corn", "makka", "makki"), ("मक्का", "मक्की", "మొక్కజొన్న")),
    ("bajra", ("bajra", "pearl millet"), ("बाजरा", "सज्ज", "సజ్జ")),
    ("jowar", ("jowar", "sorghum"), ("ज्वार", "జొన్న")),
    ("soybean", ("soybean", "soyabean", "soya"), ("सोयाबीन", "సోయా")),
    ("groundnut", ("groundnut", "peanut", "moongfali"), ("मूंगफली", "వేరుశనగ", "వేరుశెనగ")),
    ("chilli", ("chilli", "chili", "mirch", "mirchi"), ("मिर्च", "మిర్చి", "మిరప")),
    ("banana", ("banana", "kela"), ("केला", "केले", "అరటి")),
    ("gram", ("gram", "chana"), ("चना", "चने", "శనగ")),
    ("guar", ("guar", "cluster bean"), ("ग्वार",)),
    ("tur", ("tur", "arhar", "pigeon pea"), ("अरहर", "तुअर", "కంది")),
]

# Order matters: the more specific calamity wins when a report mentions several.
_EVENTS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("hail", ("hail", "hailstorm", "hailstones", "ole", "olay", "olavrishti"),
     ("ओले", "ओला", "ओलों", "ओलावृष्टि", "వడగళ్ల", "వడగండ్ల", "వడగళ్ళ")),
    ("cyclone", ("cyclone", "cyclonic", "chakravat"), ("चक्रवात", "తుఫాను", "తుపాను", "తుఫాన్")),
    ("flood", ("flood", "flooded", "flooding", "waterlogged", "waterlogging", "inundated", "badh",
               "baadh", "jalbharav"),
     ("बाढ़", "बाढ", "जलभराव", "पानी भर", "వరద", "నీట మునిగ", "ముంపు")),
    ("pest", ("pest", "pests", "insect", "insects", "bollworm", "sundi", "keet"),
     ("कीट", "कीड़", "सुंडी", "పురుగు", "తెగులు")),
    ("drought", ("drought", "sukha", "sookha"), ("सूखा", "కరువు", "ఎండిపో")),
    ("wind", ("wind", "gale", "storm", "windstorm", "toofan", "tufan", "aandhi", "andhi"),
     ("आंधी", "आँधी", "तूफान", "तूफ़ान", "तेज़ हवा", "तेज हवा", "గాలి", "ఈదురు")),
    ("unseasonal_rain", ("rain", "rains", "rainfall", "raining", "baarish", "barish", "barsaat",
                         "barsat", "varsha"),
     ("बारिश", "बरसात", "वर्षा", "వర్షం", "వర్షాలు", "వాన")),
]

_MONTHS: dict[str, int] = {}
for _num, _names in enumerate(
    [
        ("jan", "january", "जनवरी", "జనవరి"),
        ("feb", "february", "फरवरी", "फ़रवरी", "ఫిబ్రవరి"),
        ("mar", "march", "मार्च", "మార్చి"),
        ("apr", "april", "अप्रैल", "ఏప్రిల్"),
        ("may", "मई", "మే"),
        ("jun", "june", "जून", "జూన్"),
        ("jul", "july", "जुलाई", "జులై", "జూలై"),
        ("aug", "august", "अगस्त", "ఆగస్టు", "ఆగష్టు"),
        ("sep", "sept", "september", "सितंबर", "सितम्बर", "సెప్టెంబర్", "సెప్టెంబరు"),
        ("oct", "october", "अक्टूबर", "अक्तूबर", "అక్టోబర్", "అక్టోబరు"),
        ("nov", "november", "नवंबर", "नवम्बर", "నవంబర్", "నవంబరు"),
        ("dec", "december", "दिसंबर", "दिसम्बर", "డిసెంబర్", "డిసెంబరు"),
    ],
    start=1,
):
    for _name in _names:
        _MONTHS[_name] = _num
_MONTH_ALT = "|".join(sorted(map(re.escape, _MONTHS), key=len, reverse=True))

_NUMBER_WORDS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "ek": 1, "do": 2, "teen": 3, "char": 4,
    "paanch": 5, "panch": 5, "ఒక": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5,
}
_NUM_ALT = "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True))


@dataclass
class ParsedReport:
    crop: str | None = None
    event_type: str = "unknown"
    event_date: date | None = None
    event_time: str | None = None
    transcript: str | None = None
    confidence: float = 0.0
    date_note: str | None = None
    llm_used: bool = False
    extra: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "crop": self.crop,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "event_time": self.event_time,
            "transcript": self.transcript,
            "confidence": self.confidence,
            "date_note": self.date_note,
            "llm_used": self.llm_used,
        }


def today_ist() -> date:
    return datetime.now(IST).date()


def normalize_digits(text: str) -> str:
    return text.translate(_DIGITS)


def _keyword_hit(text_lower: str, latin: tuple[str, ...], indic: tuple[str, ...]) -> bool:
    if any(stem in text_lower for stem in indic):
        return True
    return any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", text_lower) for w in latin)


def extract_crop(text: str) -> str | None:
    lowered = text.lower()
    for name, latin, indic in _CROPS:
        if _keyword_hit(lowered, latin, indic):
            return name
    return None


def extract_event(text: str) -> str:
    lowered = text.lower()
    for name, latin, indic in _EVENTS:
        if _keyword_hit(lowered, latin, indic):
            return name
    return "unknown"


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve_no_year(month: int, day: int, today: date) -> date | None:
    """A date without a year is this year's. It only rolls back a year when "this year" would be
    far ahead (25 Dec said in January); a near-future date stays future and gets refused later."""
    candidate = _safe_date(today.year, month, day)
    if candidate and (candidate - today).days > 180:
        candidate = _safe_date(today.year - 1, month, day)
    return candidate


def extract_date(text: str, today: date | None = None) -> tuple[date | None, str | None]:
    """Returns (date, note). A date in the future is refused, not guessed around."""
    today = today or today_ist()
    norm = normalize_digits(text)
    lowered = norm.lower()
    found: date | None = None

    if m := re.search(r"(?<!\d)(20\d\d)-(\d{1,2})-(\d{1,2})(?!\d)", lowered):
        found = _safe_date(int(m[1]), int(m[2]), int(m[3]))
    elif m := re.search(r"(?<!\d)(\d{1,2})[/.\-](\d{1,2})[/.\-](20\d\d|\d\d)(?!\d)", lowered):
        year = int(m[3]) if len(m[3]) == 4 else 2000 + int(m[3])
        found = _safe_date(year, int(m[2]), int(m[1]))
    elif m := re.search(rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?({_MONTH_ALT})(?![a-z])"
                        r"(?:[,\s]+(20\d\d))?", lowered):
        found = (
            _safe_date(int(m[3]), _MONTHS[m[2]], int(m[1]))
            if m[3]
            else _resolve_no_year(_MONTHS[m[2]], int(m[1]), today)
        )
    elif m := re.search(rf"(?<![a-z])({_MONTH_ALT})(?![a-z])\s+(\d{{1,2}})(?:st|nd|rd|th)?(?!\d)"
                        r"(?:[,\s]+(20\d\d))?", lowered):
        found = (
            _safe_date(int(m[3]), _MONTHS[m[1]], int(m[2]))
            if m[3]
            else _resolve_no_year(_MONTHS[m[1]], int(m[2]), today)
        )
    elif m := re.search(r"(?<!\d)(\d{1,2})[/.](\d{1,2})(?!\d)", lowered):
        found = _resolve_no_year(int(m[2]), int(m[1]), today)
    else:
        days_ago = _relative_days(lowered)
        if days_ago is not None:
            found = today - timedelta(days=days_ago)

    if found is None:
        return None, None
    if found > today:
        return None, f"future_date_refused:{found.isoformat()}"
    if (today - found).days > 365 * 5:
        return None, f"too_old_refused:{found.isoformat()}"
    return found, None


def _relative_days(lowered: str) -> int | None:
    if m := re.search(rf"(\d{{1,2}}|{_NUM_ALT})\s*(?:दिन|din|days?|రోజుల|రోజులు|రోజు)\s*"
                      r"(?:पहले|pehle|pahle|ago|back|క్రితం|కిందట|ముందు)", lowered):
        word = m[1]
        return int(word) if word.isdigit() else _NUMBER_WORDS.get(word)
    if re.search(r"day before yesterday|परसों|parson|parso|మొన్న", lowered):
        return 2
    if re.search(r"(?<![a-z])(yesterday|last night|kal)(?![a-z])|कल|నిన్న", lowered):
        return 1
    if re.search(r"(?<![a-z])(today|tonight|this morning|aaj)(?![a-z])|आज|ఈరోజు|ఈ రోజు|నేడు", lowered):
        return 0
    return None


def extract_time(text: str) -> str | None:
    """Only an explicit clock time counts; "at night" alone gives no time."""
    norm = normalize_digits(text).lower()
    if m := re.search(r"(?<!\d)(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)", norm):
        hour = int(m[1]) % 12 + (12 if m[3].startswith("p") else 0)
        minute = int(m[2] or 0)
    elif m := re.search(r"(सुबह|दोपहर|शाम|रात|subah|dopahar|shaam|sham|raat)?\s*"
                        r"(?<!\d)(\d{1,2})(?::(\d{2}))?\s*(?:बजे|baje)", norm):
        hour = int(m[2])
        minute = int(m[3] or 0)
        period = m[1] or ""
        if period in ("दोपहर", "dopahar", "शाम", "shaam", "sham") and hour < 12 or period in ("रात", "raat") and 7 <= hour < 12:
            hour += 12
    else:
        return None
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_text(text: str | None, today: date | None = None) -> ParsedReport:
    report = ParsedReport(transcript=(text or "").strip() or None)
    if not report.transcript:
        return report
    source = report.transcript
    report.crop = extract_crop(source)
    report.event_type = extract_event(source)
    report.event_date, report.date_note = extract_date(source, today)
    report.event_time = extract_time(source)
    found = sum([report.crop is not None, report.event_type != "unknown",
                 report.event_date is not None])
    report.confidence = round(found / 3, 2)
    return report


def needs_for(crop: str | None, event_type: str | None, event_date: date | None) -> list[str]:
    needs = []
    if not crop:
        needs.append("crop")
    if not event_type or event_type == "unknown":
        needs.append("event_type")
    if not event_date:
        needs.append("event_date")
    return needs
