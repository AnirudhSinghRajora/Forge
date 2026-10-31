"""Cover routing, deadlines and the intimation draft. Every rule comes from key_rules.json.

Without that file this module says the policy corpus is unavailable; it never fills in a rule from
memory. "Filed" exists only as a submission action with a reference number, written by the API.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import get_settings
from app.db import Action, session_scope
from app.evidence.schema import ClaimPath, Deadline

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
UNAVAILABLE = "policy corpus unavailable"

_FIELD_LABELS = {
    "farmer_name": ("किसान का नाम", "Farmer name"),
    "survey_number": ("खसरा / सर्वे नंबर", "Survey number"),
    "insured_crop": ("बीमित फ़सल", "Insured crop"),
    "acreage_affected": ("प्रभावित रकबा", "Acreage affected"),
    "ncip_application_no": ("NCIP आवेदन संख्या", "NCIP application number"),
    "mobile_number": ("मोबाइल नंबर", "Mobile number"),
    "kcc_account_no_if_loanee_or_savings_account_if_non_loanee": (
        "KCC खाता (ऋणी) या बचत खाता (गैर-ऋणी)",
        "KCC account (loanee) or savings account (non-loanee)",
    ),
}
_EVENT_LABELS = {
    "hail": ("ओलावृष्टि", "Hailstorm"), "flood": ("जलभराव / बाढ़", "Inundation / flood"),
    "cyclone": ("चक्रवात", "Cyclone"), "unseasonal_rain": ("बेमौसम बारिश", "Unseasonal rain"),
    "wind": ("तेज़ आँधी", "Storm"), "pest": ("कीट या रोग", "Pest or disease"),
    "drought": ("सूखा", "Drought"), "other": ("अन्य", "Other"), "unknown": ("अज्ञात", "Not stated"),
}


def load_key_rules() -> dict | None:
    path = get_settings().policy_dir / "key_rules.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        log.exception("key_rules.json could not be read")
        return None


def _rule(name: str) -> dict | None:
    rules = (load_key_rules() or {}).get("rules") or {}
    rule = rules.get(name)
    return rule if isinstance(rule, dict) else None


def event_datetime(event_date: date, event_time: str | None) -> tuple[datetime, bool]:
    """Event moment in IST. With no time given it takes the day's start, the conservative reading:
    the true deadline cannot fall earlier than this."""
    if event_time:
        hour, minute = (int(x) for x in event_time.split(":"))
        return datetime.combine(event_date, time(hour, minute), IST), False
    return datetime.combine(event_date, time(0, 0), IST), True


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def submission_for(case_id: str) -> dict | None:
    with session_scope() as s:
        row = s.scalars(
            select(Action).where(Action.case_id == case_id, Action.type == "submission")
            .order_by(Action.created_at.desc())
        ).first()
        return dict(row.payload) if row else None


def deadline_status(due_at: datetime, submitted_at: datetime | None, now: datetime | None = None
                    ) -> str:
    now = now or datetime.now(UTC)
    due = _aware(due_at)
    if submitted_at is not None and _aware(submitted_at) <= due:
        return "met"
    return "lapsed" if now > due else "open"


LAPSED_HI = (
    "नियम 72 घंटे में सूचना देने को कहता है। अगर यह समय निकल चुका है, तब भी अभी सूचना दें और संदर्भ संख्या "
    "संभालकर रखें; दिशानिर्देश कहते हैं कि सर्वे के दौरान मिली सूचनाओं पर भी विचार किया जाएगा।"
)
LAPSED_EN = (
    "The rule asks for intimation within 72 hours. If that time has passed, still report it now and "
    "keep the reference number; the guidelines say intimations received during the survey would "
    "also be considered."
)


def channels() -> list[dict]:
    rule = _rule("channels")
    if rule is None:
        return []
    out = []
    if helpline := rule.get("helpline"):
        out.append({"kind": "helpline", "value": helpline, "url": f"tel:{helpline}",
                    "label_hi": f"कृषि रक्षक पोर्टल और हेल्पलाइन: {helpline}",
                    "label_en": f"Krishi Rakshak Portal & Helpline: {helpline}"})
    if portal := rule.get("krph_portal"):
        out.append({"kind": "portal", "value": portal, "url": portal,
                    "label_hi": "कृषि रक्षक पोर्टल", "label_en": "Krishi Rakshak Portal"})
    if app_id := rule.get("crop_insurance_app_android_id"):
        out.append({"kind": "app", "value": app_id,
                    "url": f"https://play.google.com/store/apps/details?id={app_id}",
                    "label_hi": "क्रॉप इंश्योरेंस ऐप", "label_en": "Crop Insurance App"})
    if chatbot := rule.get("whatsapp_chatbot"):
        out.append({"kind": "whatsapp_chatbot", "value": chatbot, "url": f"https://wa.me/91{chatbot}",
                    "label_hi": f"व्हाट्सऐप चैटबॉट: {chatbot}", "label_en": f"WhatsApp chatbot: {chatbot}"})
    out.append({"kind": "other", "value": None, "url": None,
                "label_hi": "बीमा कंपनी का टोल-फ़्री नंबर (आपके आवेदन या पॉलिसी की रसीद पर), आपका बैंक, या कृषि विभाग "
                            "के स्थानीय अधिकारी",
                "label_en": "The insurer's toll-free number (on your application or policy "
                            "receipt), your bank, or local agriculture department officials"})
    return out


def draft_intimation(case: dict, evidence: dict, path: ClaimPath, deadlines: list[Deadline]) -> dict:
    """The farmer's own intimation text. Its required fields come only from intimation_contents."""
    contents = _rule("intimation_contents")
    if contents is None:
        return {"available": False, "reason": UNAVAILABLE}
    event = evidence.get("event", {})
    plot = evidence.get("plot", {})
    area = plot.get("area_ha")
    lon, lat = (plot.get("centroid") or [None, None])[:2]
    when = event.get("date") or "-"
    kind_hi, kind_en = _EVENT_LABELS.get(event.get("type") or "unknown", _EVENT_LABELS["unknown"])
    prefilled = {
        "insured_crop": case.get("crop"),
        "acreage_affected": f"{area} ha" if area is not None else None,
    }
    hi_lines = ["विषय: प्रधानमंत्री फ़सल बीमा योजना के तहत फ़सल नुकसान की सूचना",
                f"घटना: {kind_hi}", f"घटना की तारीख़: {when}"]
    en_lines = ["Subject: Intimation of crop loss under PMFBY",
                f"Event: {kind_en}", f"Date of event: {when}"]
    if case.get("event_time"):
        hi_lines.append(f"समय: {case['event_time']}")
        en_lines.append(f"Time: {case['event_time']}")
    missing = []
    for name in contents.get("fields") or []:
        label_hi, label_en = _FIELD_LABELS.get(name, (name, name))
        value = prefilled.get(name)
        if value is None:
            missing.append(name)
        hi_lines.append(f"{label_hi}: {value if value is not None else '[कृपया भरें]'}")
        en_lines.append(f"{label_en}: {value if value is not None else '[please fill in]'}")
    if "latitude_longitude" in (contents.get("optional_per_text") or []):
        hi_lines.append(f"अक्षांश, देशांतर: {lat}, {lon}")
        en_lines.append(f"Latitude, longitude: {lat}, {lon}")
    if evidence_hash := evidence.get("evidence_hash"):
        link = f"{get_settings().public_web_url.rstrip('/')}/verify/{evidence_hash}"
        hi_lines.append(f"सैटेलाइट सबूत (सहायक रिकॉर्ड): {link}")
        en_lines.append(f"Satellite evidence (supporting record): {link}")
    hindi, english = "\n".join(hi_lines), "\n".join(en_lines)
    deadline = next((d for d in deadlines if d.type == "intimation_72h"), None)
    lapsed = deadline is not None and deadline.status == "lapsed"
    return {
        "available": True,
        "needed": path.route in ("localized_addon", "post_harvest_addon"),
        "text_hi": hindi,
        "text_en": english,
        "whatsapp_url_hi": "https://wa.me/?text=" + urllib.parse.quote(hindi),
        "whatsapp_url_en": "https://wa.me/?text=" + urllib.parse.quote(english),
        "fields_to_fill": missing,
        "partial_allowed_note_hi": "अगर सारी जानकारी तैयार नहीं है तो अभी जितनी है उतनी भेजें; पूरी जानकारी नुकसान के 7 "
                                   "दिन के भीतर दें।",
        "partial_allowed_note_en": "If not everything is ready, send what you have now and give "
                                   "complete details within 7 days of the loss.",
        "channels": channels(),
        "basis": deadline.basis if deadline else None,
        "deadline_status": deadline.status if deadline else None,
        "due_at": deadline.due_at.isoformat() if deadline else None,
        "time_assumed": case.get("event_time") is None,
        "lapsed_note_hi": LAPSED_HI if lapsed else None,
        "lapsed_note_en": LAPSED_EN if lapsed else None,
        "filed": False,
    }
