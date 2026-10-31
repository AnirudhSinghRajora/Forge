"""News corroboration through Gemini Search grounding, cached per district and date.

Only URLs the API attached as grounding citations are returned, never text the model wrote. With no
key, or on any failure, this returns [] and the verdict simply goes without news. News is supporting
only, and never proof about an individual plot.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import httpx

from app.agent import llm
from app.db import cache_get, cache_put
from app.evidence.schema import NewsItem

log = logging.getLogger(__name__)
CACHE_TTL = timedelta(hours=6)
_EVENT_WORDS = {
    "hail": "hailstorm", "unseasonal_rain": "unseasonal rain", "flood": "flood",
    "cyclone": "cyclone", "wind": "storm", "pest": "pest attack", "drought": "drought",
}


def _resolve(url: str) -> str:
    """Grounding URLs can be redirects. Report the final address when it can be resolved."""
    if "grounding-api-redirect" not in url:
        return url
    try:
        response = httpx.head(url, follow_redirects=True, timeout=5.0)
        return str(response.url)
    except httpx.HTTPError:
        return url


def search(district: str | None, state: str | None, event_type: str | None, event_date: date
           ) -> list[NewsItem]:
    if not llm.available() or not district:
        return []
    key = f"news:{district}:{event_date.isoformat()}".lower()
    hit = cache_get(key)
    if hit:
        fetched = hit.fetched_at if hit.fetched_at.tzinfo else hit.fetched_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - fetched < CACHE_TTL:
            return [NewsItem.model_validate(i) for i in hit.payload]
    words = _EVENT_WORDS.get(event_type or "", "crop damage calamity")
    window = f"{event_date - timedelta(days=2):%d %b} to {event_date + timedelta(days=3):%d %b %Y}"
    query = (
        f"News reports of {words} and crop damage in {district} district, {state or 'India'}, "
        f"between {window}. Cite local news or government sources."
    )
    sources = llm.grounded_sources(query)
    if sources is None:
        return []
    items = [
        NewsItem(title=src["title"], url=_resolve(src["url"]), date=None, snippet=src.get("snippet"))
        for src in sources[:6]
    ]
    cache_put(key, "gemini-search-grounding", None, [i.model_dump(mode="json") for i in items])
    return items
