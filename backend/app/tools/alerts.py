"""NDMA SACHET CAP alerts: archive the live RSS feed and match by what the data actually supports.

The feed only carries current alerts, so history starts when archiving starts; older events have
no archived alert, and that is reported as nothing found. Matching is by district name in the CAP
area text. A state-level mention does not match, because it says nothing about a field.
"""
from __future__ import annotations

import logging
import re
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import AlertArchive, cache_get, cache_put, session_scope, utcnow
from app.evidence.schema import Alert

log = logging.getLogger(__name__)

CAP_NS = "{urn:oasis:names:tc:emergency:cap:1.2}"
MATCH_WINDOW_DAYS = 3
MAX_NEW_PER_RUN = 40  # the feed has about 100 items and rate-limits, so a backlog spreads over ticks
MAX_WORKERS = 2
HTTP_TIMEOUT_S = 15.0
MAX_PLACE_CHARS = 120
# Weather and flood hazards bear on crops. Other categories (health, for instance) do not.
_NOT_CROP_RELEVANT = re.compile(r"(?i)covid|health|fire safety|road|earthquake|tsunami")


def _headers() -> dict:
    return {"User-Agent": get_settings().http_user_agent}


def parse_rss(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.iter("item"):
        guid = (item.findtext("guid") or "").strip()
        if not guid:
            continue
        published = None
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError):
            pass
        items.append({
            "guid": guid,
            "title": (item.findtext("title") or "").strip(),
            "link": (item.findtext("link") or "").strip(),
            "author": (item.findtext("author") or "").strip(),
            "category": (item.findtext("category") or "").strip(),
            "published": published,
        })
    return items


def _time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_cap(xml_text: str) -> dict:
    """One CAP alert. The English info block is preferred; alerts also carry a regional one."""
    root = ET.fromstring(xml_text)
    infos = root.findall(f"{CAP_NS}info")
    english = next(
        (i for i in infos if (i.findtext(f"{CAP_NS}language") or "").lower().startswith("en")),
        infos[0] if infos else None,
    )

    def field(name: str) -> str | None:
        if english is None:
            return None
        value = english.findtext(f"{CAP_NS}{name}")
        return value.strip() if value and value.strip() else None

    areas, geocode = [], {}
    if english is not None:
        for area in english.findall(f"{CAP_NS}area"):
            if desc := area.findtext(f"{CAP_NS}areaDesc"):
                areas.append(desc.strip())
            for code in area.findall(f"{CAP_NS}geocode"):
                name = code.findtext(f"{CAP_NS}valueName")
                if name:
                    geocode.setdefault(name, []).append(code.findtext(f"{CAP_NS}value"))
    return {
        "identifier": (root.findtext(f"{CAP_NS}identifier") or "").strip(),
        "sender": (root.findtext(f"{CAP_NS}sender") or "").strip() or None,
        "sent": _time(root.findtext(f"{CAP_NS}sent")),
        "status": (root.findtext(f"{CAP_NS}status") or "").strip(),
        "event": field("event"),
        "severity": field("severity"),
        "headline": field("headline"),
        "effective": _time(field("effective")),
        "expires": _time(field("expires")),
        "area_desc": "; ".join(areas) or None,
        "geocode": geocode or None,
    }


def _store(guid: str, cap: dict, url: str, raw: str) -> None:
    with session_scope() as s:
        s.merge(AlertArchive(
            identifier=guid, sent=cap["sent"], effective=cap["effective"], expires=cap["expires"],
            sender=cap["sender"], event=cap["event"], severity=cap["severity"],
            area_desc=cap["area_desc"], headline=cap["headline"], geocode=cap["geocode"],
            url=url, raw_xml=raw, fetched_at=utcnow(),
        ))


# SACHET answers a rate limit with a 302 to /rate-limit.xml.
def _archive_one(item: dict, stop: threading.Event) -> bool:
    if stop.is_set():
        return False
    try:
        response = httpx.get(item["link"], timeout=HTTP_TIMEOUT_S, headers=_headers())
        if response.is_redirect:
            stop.set()  # stop at once rather than keep knocking; the next tick picks up the rest
            return False
        response.raise_for_status()
        cap = parse_cap(response.text)
        if cap["status"] and cap["status"] != "Actual":
            return False
        _store(item["guid"], cap, item["link"], response.text)
        return True
    except (httpx.HTTPError, ET.ParseError) as exc:
        log.warning("CAP alert %s could not be archived: %s", item["guid"], exc)
        return False


def archive() -> dict:
    """Fetches the feed and stores any alert not seen before. Raises httpx errors if unreachable."""
    settings = get_settings()
    response = httpx.get(settings.sachet_rss_url, timeout=HTTP_TIMEOUT_S, headers=_headers())
    if response.is_redirect:
        return {"feed_items": 0, "pending": None, "archived": 0, "rate_limited": True}
    response.raise_for_status()
    items = parse_rss(response.text)
    with session_scope() as s:
        known = set(s.scalars(select(AlertArchive.identifier)).all())
    pending = [i for i in items if i["guid"] not in known and i["link"]]
    new = pending[:MAX_NEW_PER_RUN]
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="sachet") as pool:
        stored = sum(pool.map(lambda item: _archive_one(item, stop), new))
    if stop.is_set():
        log.warning("SACHET rate limit reached after archiving %d alerts; resuming next tick", stored)
    return {"feed_items": len(items), "pending": len(pending), "archived": stored,
            "rate_limited": stop.is_set()}


def _as_aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _name_in(name: str, text: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(name.lower())}(?![a-z])", text.lower()) is not None


def clean_district(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r"(?i)\s+(district|tehsil|taluk|mandal)$", "", name.strip()) or None


def match(district: str | None, event_date: date, event_type: str | None = None) -> list[Alert]:
    """Archived alerts naming this district within three days of the event. All of them are shown;
    only those whose hazard matches the reported event corroborate (rubric.matching_alerts)."""
    district = clean_district(district)
    if not district or event_type in ("pest", "drought"):
        return []
    start = datetime.combine(event_date - timedelta(days=MATCH_WINDOW_DAYS), datetime.min.time(), UTC)
    end = datetime.combine(event_date + timedelta(days=MATCH_WINDOW_DAYS + 1),
                           datetime.min.time(), UTC)
    with session_scope() as s:
        rows = s.scalars(select(AlertArchive).where(AlertArchive.area_desc.is_not(None))).all()
    out = []
    for row in rows:
        when = row.effective or row.sent
        if when is None or not (start <= _as_aware(when) <= end):
            continue
        if not _name_in(district, row.area_desc or ""):
            continue
        if _NOT_CROP_RELEVANT.search(row.event or ""):
            continue
        out.append(Alert(
            source=f"NDMA SACHET ({row.sender})" if row.sender else "NDMA SACHET",
            identifier=row.identifier, issued=row.sent, area=row.area_desc, event=row.event,
            headline=row.headline, severity=row.severity, url=row.url,
        ))
    return sorted(out, key=lambda a: a.issued or datetime.min.replace(tzinfo=UTC))[:10]


def locate(lat: float, lon: float) -> dict:
    """Reverse geocode to district and state, cached. {} on failure; matching then finds nothing."""
    settings = get_settings()
    key = f"geo:{lat:.2f}:{lon:.2f}"
    hit = cache_get(key)
    if hit:
        return dict(hit.payload)
    try:
        response = httpx.get(
            settings.nominatim_url,
            params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 10,
                    "accept-language": "en"},
            headers=_headers(), timeout=6.0,
        )
        response.raise_for_status()
        address = response.json().get("address") or {}
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("reverse geocoding failed: %s", exc)
        return {}
    place = {
        "district": (clean_district(address.get("state_district") or address.get("county")
                                    or address.get("city")) or "")[:MAX_PLACE_CHARS] or None,
        "state": (address.get("state") or "")[:MAX_PLACE_CHARS] or None,
        "country_code": address.get("country_code"),
        "source": "OpenStreetMap Nominatim",
    }
    cache_put(key, "nominatim", settings.nominatim_url, place)
    return place
