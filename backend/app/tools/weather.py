"""Weather at the plot: Open-Meteo first, NASA POWER as the fallback. All of it is model-indicated.

Weather corroborates when present, and its absence never refutes (build contract, point 4).
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from app import errors
from app.config import get_settings
from app.db import cache_get, cache_put
from app.evidence.schema import WeatherDay, WeatherEvidence

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

HEAVY_DAY_MM = 10.0  # 03 §9
HEAVY_WINDOW_MM = 20.0  # 03 §9
STRONG_GUST_KMH = 60.0  # about the start of gale-force wind
CYCLONE_RAIN_MM = 64.5  # IMD's lower bound for "heavy rain" in a day
HAIL_CODES = {96, 99}
THUNDER_CODES = {95, 96, 99}
EVENT_WINDOW_DAYS = 2  # E-2 .. E+2 (03 §9)
SCAN_WINDOW_DAYS = 10  # how far from E a corrected date may be proposed
NOT_WEATHER_EVENTS = {"pest", "drought"}  # rain does not corroborate these
HTTP_TIMEOUT_S = 12.0

GRID_NOTE = (
    "Model-indicated values from a gridded weather model (about 9-25 km), not a gauge at your "
    "field. A gridded model can miss a small hail cell, so no signal here does not mean no storm. | "
    "ये मौसम मॉडल के अनुमान हैं (लगभग 9-25 किमी का ग्रिड), खेत पर मापे हुए नहीं। ऐसा मॉडल छोटी ओलावृष्टि को चूक "
    "सकता है, इसलिए यहाँ संकेत न होने का मतलब यह नहीं कि तूफ़ान नहीं आया।"
)


class WeatherUnavailable(RuntimeError):
    """Every weather source failed, and no earlier response is cached."""


def _ttl(end: date, today: date) -> timedelta:
    return timedelta(hours=1) if (today - end).days < 3 else timedelta(days=7)


def _as_aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _get_json(url: str, params: dict, timeout: float = HTTP_TIMEOUT_S) -> dict | list:
    headers = {"User-Agent": get_settings().http_user_agent}
    response = httpx.get(url, params=params, timeout=timeout, headers=headers)
    response.raise_for_status()
    return response.json()


def _fetch_open_meteo(lat: float, lon: float, start: date, end: date) -> dict:
    settings = get_settings()
    params = {
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "precipitation_sum,wind_gusts_10m_max,weather_code",
        "hourly": "weather_code",
        "timezone": "Asia/Kolkata",
    }
    url = settings.open_meteo_historical_url
    if settings.open_meteo_api_key:
        url = settings.open_meteo_customer_url
        params["apikey"] = settings.open_meteo_api_key
    return _get_json(url, params)


def _fetch_power(lat: float, lon: float, start: date, end: date) -> dict:
    settings = get_settings()
    return _get_json(
        settings.nasa_power_url,
        {
            "parameters": "PRECTOTCORR", "community": "AG",
            "latitude": round(lat, 4), "longitude": round(lon, 4),
            "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON",
        },
        timeout=20.0,
    )


def _days_from_open_meteo(payload: dict) -> tuple[list[WeatherDay], dict[date, list[int]]]:
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    rain = daily.get("precipitation_sum") or [None] * len(times)
    gusts = daily.get("wind_gusts_10m_max") or [None] * len(times)
    codes = daily.get("weather_code") or [None] * len(times)
    days = [
        WeatherDay(date=date.fromisoformat(t), precip_mm=p, gust_kmh=g, weather_code=c)
        for t, p, g, c in zip(times, rain, gusts, codes, strict=False)
    ]
    hourly: dict[date, list[int]] = {}
    hourly_block = payload.get("hourly") or {}
    for stamp, code in zip(hourly_block.get("time") or [], hourly_block.get("weather_code") or [],
                           strict=False):
        if code is not None:
            hourly.setdefault(date.fromisoformat(stamp[:10]), []).append(int(code))
    return days, hourly


def _days_from_power(payload: dict) -> list[WeatherDay]:
    """POWER marks a missing day with -999; it must become None, never a number."""
    values = payload["properties"]["parameter"]["PRECTOTCORR"]
    fill = payload.get("header", {}).get("fill_value", -999.0)
    days = []
    for key in sorted(values):
        value = values[key]
        missing = value is None or value == fill or value <= -999
        days.append(WeatherDay(date=datetime.strptime(key, "%Y%m%d").date(),
                               precip_mm=None if missing else value))
    return days


def _load(lat: float, lon: float, start: date, end: date, today: date) -> tuple[str, dict, datetime]:
    """Returns (provider, payload, fetched_at), preferring a fresh cache of a real response."""
    settings = get_settings()
    ttl = _ttl(end, today)
    base = f"{lat:.2f}:{lon:.2f}:{start}:{end}"
    om_key, power_key = f"weather:om:{base}", f"weather:power:{base}"
    now = datetime.now(UTC)
    hit = cache_get(om_key)
    if hit and now - _as_aware(hit.fetched_at) < ttl:
        return "open-meteo", hit.payload, _as_aware(hit.fetched_at)
    failures = []  # names only: an httpx message holds the URL, and so the API key
    try:
        payload = _fetch_open_meteo(lat, lon, start, end)
        cache_put(om_key, "open-meteo", settings.open_meteo_historical_url, payload)
        return "open-meteo", payload, now
    except (httpx.HTTPError, ValueError) as exc:
        failures.append(f"open-meteo: {type(exc).__name__}")
        log.warning("open-meteo failed, trying NASA POWER: %s", errors.scrub(exc))
    try:
        payload = _fetch_power(lat, lon, start, end)
        cache_put(power_key, "nasa-power", settings.nasa_power_url, payload)
        return "nasa-power", payload, now
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        failures.append(f"nasa-power: {type(exc).__name__}")
        log.warning("NASA POWER failed: %s", errors.scrub(exc))
    for provider, key in (("open-meteo", om_key), ("nasa-power", power_key)):
        hit = cache_get(key)
        if hit:  # an older real response, carrying its true fetch time
            return provider, hit.payload, _as_aware(hit.fetched_at)
    raise WeatherUnavailable("; ".join(failures))


def _sum(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present), 2) if present else None


def _max(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def _day_signal(day: WeatherDay, hourly: dict[date, list[int]]) -> bool:
    if day.precip_mm is not None and day.precip_mm >= HEAVY_DAY_MM:
        return True
    if day.gust_kmh is not None and day.gust_kmh >= STRONG_GUST_KMH:
        return True
    return any(code in HAIL_CODES for code in hourly.get(day.date, []))


def build_evidence(
    provider: str, payload: dict, fetched_at: datetime, event_date: date,
    event_type: str | None, today: date,
) -> WeatherEvidence:
    if provider == "open-meteo":
        days, hourly = _days_from_open_meteo(payload)
        source = "Open-Meteo historical-forecast API (model-indicated)"
    else:
        days, hourly = _days_from_power(payload), {}
        source = "NASA POWER daily PRECTOTCORR (model-indicated)"
    days = [d for d in days if d.date <= today]
    window = [d for d in days if abs((d.date - event_date).days) <= EVENT_WINDOW_DAYS]
    window_mm = _sum([d.precip_mm for d in window])
    max_daily = _max([d.precip_mm for d in window])
    max_gust = _max([d.gust_kmh for d in window])
    hail_hours = thunder_hours = None
    if provider == "open-meteo":
        codes = [c for d in window for c in hourly.get(d.date, [])]
        hail_hours = sum(1 for c in codes if c in HAIL_CODES)
        thunder_hours = sum(1 for c in codes if c in THUNDER_CODES)

    corroborated = bool(
        (max_daily is not None and max_daily >= HEAVY_DAY_MM)
        or (window_mm is not None and window_mm >= HEAVY_WINDOW_MM)
        or (hail_hours or 0) > 0
        or (max_gust is not None and max_gust >= STRONG_GUST_KMH)
    )
    if event_type in NOT_WEATHER_EVENTS:
        corroborated = False

    proposed = None
    if not corroborated and event_type not in NOT_WEATHER_EVENTS:
        outside = [
            d for d in days
            if abs((d.date - event_date).days) > EVENT_WINDOW_DAYS and _day_signal(d, hourly)
        ]
        if outside:
            peak = max(outside, key=lambda d: (d.precip_mm or 0.0, d.gust_kmh or 0.0))
            proposed = peak.date

    return WeatherEvidence(
        source=source, fetched_at=fetched_at, grid_note=GRID_NOTE, days=days,
        precip_mm_event_window=window_mm, max_daily_mm=max_daily, hail_code_hours=hail_hours,
        thunder_hours=thunder_hours, max_gust_kmh=max_gust, corroborated=corroborated,
        proposed_event_date=proposed, fallback_used=provider != "open-meteo",
    )


def fetch_weather(
    lat: float, lon: float, event_date: date, event_type: str | None = None,
    today: date | None = None,
) -> WeatherEvidence:
    today = today or datetime.now(IST).date()
    start = event_date - timedelta(days=SCAN_WINDOW_DAYS)
    end = min(event_date + timedelta(days=SCAN_WINDOW_DAYS), today)
    provider, payload, fetched_at = _load(lat, lon, start, end, today)
    return build_evidence(provider, payload, fetched_at, event_date, event_type, today)


def peak_recent_date(lat: float, lon: float, today: date | None = None, days_back: int = 14
                     ) -> tuple[date | None, WeatherEvidence | None]:
    """For a report with no date: the strongest recent weather signal, if there is one at all."""
    today = today or datetime.now(IST).date()
    start = today - timedelta(days=days_back)
    provider, payload, fetched_at = _load(lat, lon, start, today, today)
    evidence = build_evidence(provider, payload, fetched_at, today, None, today)
    hourly = _days_from_open_meteo(payload)[1] if provider == "open-meteo" else {}
    strong = [d for d in evidence.days if _day_signal(d, hourly)]
    if not strong:
        return None, evidence
    return max(strong, key=lambda d: (d.precip_mm or 0.0, d.gust_kmh or 0.0)).date, evidence


def corroboration_signals(w: WeatherEvidence) -> list[str]:
    """Plain statements of which rule fired, for reasons and the trace. Always model-indicated."""
    signals = []
    if w.max_daily_mm is not None and w.max_daily_mm >= CYCLONE_RAIN_MM:
        signals.append(f"cyclone-class rain, model-indicated: {w.max_daily_mm:.1f} mm in a day")
    elif w.max_daily_mm is not None and w.max_daily_mm >= HEAVY_DAY_MM:
        signals.append(f"heavy rain, model-indicated: {w.max_daily_mm:.1f} mm in a day")
    if w.precip_mm_event_window is not None and w.precip_mm_event_window >= HEAVY_WINDOW_MM:
        signals.append(f"{w.precip_mm_event_window:.1f} mm over the event window, model-indicated")
    if w.hail_code_hours:
        signals.append(f"hail-conducive storm modelled in {w.hail_code_hours} hours")
    if w.max_gust_kmh is not None and w.max_gust_kmh >= STRONG_GUST_KMH:
        signals.append(f"strong gusts, model-indicated: {w.max_gust_kmh:.0f} km/h")
    return signals


# The calamity radar: one multi-point query across Indian cropland, cached for 30 minutes.

RADAR_TTL = timedelta(minutes=30)
RADAR_HEAVY_MM = 25.0
RADAR_WINDOW_H = 72

# Representative points in major cropping districts (name, state, lat, lon).
RADAR_POINTS: list[tuple[str, str, float, float]] = [
    ("Sirsa", "Haryana", 29.53, 75.03), ("Fatehabad", "Haryana", 29.52, 75.45),
    ("Karnal", "Haryana", 29.69, 76.98), ("Bathinda", "Punjab", 30.21, 74.95),
    ("Ludhiana", "Punjab", 30.90, 75.85), ("Amritsar", "Punjab", 31.63, 74.87),
    ("Sri Ganganagar", "Rajasthan", 29.91, 73.88), ("Kota", "Rajasthan", 25.18, 75.84),
    ("Jaipur", "Rajasthan", 26.91, 75.79), ("Meerut", "Uttar Pradesh", 28.98, 77.71),
    ("Bareilly", "Uttar Pradesh", 28.37, 79.43), ("Lucknow", "Uttar Pradesh", 26.85, 80.95),
    ("Gorakhpur", "Uttar Pradesh", 26.76, 83.37), ("Varanasi", "Uttar Pradesh", 25.32, 82.97),
    ("Patna", "Bihar", 25.59, 85.14), ("Gaya", "Bihar", 24.80, 85.00),
    ("Purnia", "Bihar", 25.78, 87.47), ("Malda", "West Bengal", 25.01, 88.14),
    ("Bardhaman", "West Bengal", 23.24, 87.86), ("Cooch Behar", "West Bengal", 26.32, 89.45),
    ("Nagaon", "Assam", 26.35, 92.68), ("Jorhat", "Assam", 26.75, 94.20),
    ("Cuttack", "Odisha", 20.46, 85.88), ("Sambalpur", "Odisha", 21.47, 83.97),
    ("Ganjam", "Odisha", 19.39, 84.68), ("Raipur", "Chhattisgarh", 21.25, 81.63),
    ("Bilaspur", "Chhattisgarh", 22.08, 82.15), ("Ranchi", "Jharkhand", 23.34, 85.31),
    ("Indore", "Madhya Pradesh", 22.72, 75.86), ("Ujjain", "Madhya Pradesh", 23.18, 75.78),
    ("Bhopal", "Madhya Pradesh", 23.26, 77.41), ("Jabalpur", "Madhya Pradesh", 23.18, 79.99),
    ("Sagar", "Madhya Pradesh", 23.84, 78.74), ("Gwalior", "Madhya Pradesh", 26.22, 78.18),
    ("Nagpur", "Maharashtra", 21.15, 79.09), ("Akola", "Maharashtra", 20.70, 77.00),
    ("Amravati", "Maharashtra", 20.93, 77.78), ("Yavatmal", "Maharashtra", 20.39, 78.12),
    ("Nanded", "Maharashtra", 19.16, 77.32), ("Aurangabad", "Maharashtra", 19.88, 75.34),
    ("Nashik", "Maharashtra", 19.99, 73.79), ("Solapur", "Maharashtra", 17.66, 75.91),
    ("Kolhapur", "Maharashtra", 16.70, 74.24), ("Ahmedabad", "Gujarat", 23.03, 72.58),
    ("Rajkot", "Gujarat", 22.30, 70.80), ("Junagadh", "Gujarat", 21.52, 70.46),
    ("Surat", "Gujarat", 21.17, 72.83), ("Belagavi", "Karnataka", 15.85, 74.50),
    ("Raichur", "Karnataka", 16.20, 77.36), ("Ballari", "Karnataka", 15.14, 76.92),
    ("Mandya", "Karnataka", 12.52, 76.90), ("Warangal", "Telangana", 17.98, 79.59),
    ("Karimnagar", "Telangana", 18.44, 79.13), ("Nalgonda", "Telangana", 17.05, 79.27),
    ("Srikakulam", "Andhra Pradesh", 18.30, 83.90), ("East Godavari", "Andhra Pradesh", 16.98, 82.25),
    ("Konaseema", "Andhra Pradesh", 16.58, 82.00), ("West Godavari", "Andhra Pradesh", 16.71, 81.10),
    ("Krishna", "Andhra Pradesh", 16.19, 81.14), ("Guntur", "Andhra Pradesh", 16.31, 80.44),
    ("Nellore", "Andhra Pradesh", 14.44, 79.99), ("Kurnool", "Andhra Pradesh", 15.83, 78.04),
    ("Anantapur", "Andhra Pradesh", 14.68, 77.60), ("Thanjavur", "Tamil Nadu", 10.79, 79.14),
    ("Tiruchirappalli", "Tamil Nadu", 10.79, 78.70), ("Madurai", "Tamil Nadu", 9.93, 78.12),
    ("Coimbatore", "Tamil Nadu", 11.02, 76.97), ("Palakkad", "Kerala", 10.78, 76.65),
]


def _fetch_radar() -> list[dict]:
    settings = get_settings()
    params = {
        "latitude": ",".join(str(p[2]) for p in RADAR_POINTS),
        "longitude": ",".join(str(p[3]) for p in RADAR_POINTS),
        "daily": "precipitation_sum,wind_gusts_10m_max,weather_code",
        "hourly": "weather_code",
        "past_days": 3, "forecast_days": 1, "timezone": "Asia/Kolkata",
    }
    url = settings.open_meteo_forecast_url
    if settings.open_meteo_api_key:
        url = settings.open_meteo_customer_forecast_url
        params["apikey"] = settings.open_meteo_api_key
    payload = _get_json(url, params, timeout=25.0)
    return payload if isinstance(payload, list) else [payload]


def _radar_cell(point: tuple, data: dict, now: datetime) -> dict | None:
    name, state, lat, lon = point
    today = now.date()
    days, hourly = _days_from_open_meteo(data)
    past = [d for d in days if d.date <= today and (today - d.date).days <= 3]
    heavy = []
    for d in past:
        codes = hourly.get(d.date, [])
        hail = sum(1 for c in codes if c in HAIL_CODES)
        thunder = sum(1 for c in codes if c in THUNDER_CODES)
        rain = d.precip_mm or 0.0
        if rain >= RADAR_HEAVY_MM or hail or thunder:  # a storm code in the model, or heavy rain
            heavy.append((d, rain, hail, thunder))
    if not heavy:
        return None
    day, rain, hail, thunder = max(heavy, key=lambda item: item[0].date)
    # Measured from the start of that day (IST): the conservative reading, since the hour of the
    # event at any field is not known. The real window can only close later than this.
    start = datetime.combine(day.date, datetime.min.time(), IST)
    hours_left = RADAR_WINDOW_H - (now - start).total_seconds() / 3600
    if hours_left <= 0:
        return None
    return {
        "name": name, "state": state, "lat": lat, "lon": lon,
        "heavy_date": day.date.isoformat(),
        "precip_mm": round(rain, 1),
        "max_gust_kmh": day.gust_kmh,
        "hail_code_hours": hail,
        "thunder_hours": thunder,
        "hours_left": round(hours_left, 1),
        # What put this cell on the list: a thunder code alone is a weak signal, and is labelled so.
        "signal": "heavy_rain" if rain >= RADAR_HEAVY_MM else "hail_code" if hail else "thunder_code",
    }


def radar() -> dict:
    now = datetime.now(IST)
    utc_now = datetime.now(UTC)
    key = "radar:india:v1"
    hit = cache_get(key)
    stale = False
    if hit and utc_now - _as_aware(hit.fetched_at) < RADAR_TTL:
        payload, fetched_at = hit.payload, _as_aware(hit.fetched_at)
    else:
        try:
            payload = _fetch_radar()
            cache_put(key, "open-meteo", get_settings().open_meteo_forecast_url, payload)
            fetched_at = utc_now
        except (httpx.HTTPError, ValueError) as exc:
            if not hit:
                raise WeatherUnavailable(type(exc).__name__) from exc
            log.warning("radar refresh failed, serving the cached response: %s", errors.scrub(exc))
            payload, fetched_at, stale = hit.payload, _as_aware(hit.fetched_at), True
    cells = [
        cell
        for point, data in zip(RADAR_POINTS, payload, strict=False)
        if (cell := _radar_cell(point, data, now)) is not None
    ]
    cells.sort(key=lambda c: c["hours_left"])
    return {
        "source": "Open-Meteo forecast API with past days (model-indicated)",
        "fetched_at": fetched_at.isoformat(),
        "stale": stale,
        "points_checked": len(payload),
        "heavy_rain_mm_threshold": RADAR_HEAVY_MM,
        "window_hours": RADAR_WINDOW_H,
        "basis": "Signals from the last 72 hours, not live conditions. hours_left counts from the start "
                 "of the most recent heavy day in IST, the conservative reading. It is a prompt to "
                 "check, not a statement about any field. "
                 "The 72 hour rule applies only on localized and post-harvest covers the State has "
                 "notified, so each farmer's route has to be checked first.",
        "basis_hi": "ये पिछले 72 घंटों के संकेत हैं, इस समय का हाल नहीं। बचे हुए घंटे सबसे हाल के भारी दिन की शुरुआत (IST) से गिने गए हैं। यह जाँचने का इशारा है, किसी खेत "
                    "के बारे में दावा नहीं। 72 घंटे का नियम केवल राज्य द्वारा अधिसूचित स्थानीय आपदा और कटाई-बाद के कवर "
                    "पर लागू होता है, इसलिए हर किसान का रास्ता पहले देखना होगा।",
        "grid_note": GRID_NOTE,
        "cells": cells,
    }
