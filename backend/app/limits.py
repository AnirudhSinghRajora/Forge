"""In-process, per-IP limits. One process only: the app runs without --workers for this reason.

The defaults are generous, since judges and farmers can share one NAT. A client's address comes from
X-Forwarded-For only under TRUST_PROXY=true, and then from its last entry: the one our own proxy
appended. Everything to the left of that is whatever the client chose to send.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from app.config import get_settings

WINDOW_S = 3600.0
MAX_TRACKED = 20_000  # a flood of new addresses cannot grow this without bound

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = {}


def reset() -> None:
    with _lock:
        _hits.clear()


def client_ip(request: Request) -> str:
    if get_settings().trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        entries = [part.strip() for part in forwarded.split(",") if part.strip()]
        if entries:
            return entries[-1]
    return request.client.host if request.client else "unknown"


def web_base(request: Request) -> str:
    """The address readers reach us on: PUBLIC_WEB_URL, else this request's own origin. Forwarded
    headers count only under TRUST_PROXY, since a client can send anything in them."""
    settings = get_settings()
    if settings.public_web_url:
        return settings.public_web_url.rstrip("/")
    if settings.trust_proxy:
        proto = request.headers.get("x-forwarded-proto", "").split(",")[-1].strip()
        host = request.headers.get("x-forwarded-host", "").split(",")[-1].strip()
        if host:
            return f"{proto or request.url.scheme}://{host}"
    return str(request.base_url).rstrip("/")


def retry_after(bucket: str, ip: str, per_hour: int, now: float | None = None) -> int | None:
    """Records one use and returns None, or returns the seconds until a use frees up."""
    now = time.monotonic() if now is None else now
    with _lock:
        if len(_hits) > MAX_TRACKED:
            _hits.clear()
        hits = _hits.setdefault((bucket, ip), deque())
        while hits and now - hits[0] >= WINDOW_S:
            hits.popleft()
        if len(hits) >= per_hour:
            return max(1, math.ceil(WINDOW_S - (now - hits[0])))
        hits.append(now)
        return None


def too_many(seconds: int, code: str = "rate_limited") -> HTTPException:
    minutes = max(1, math.ceil(seconds / 60))
    return HTTPException(
        429,
        detail={
            "code": code,
            "retry_after_s": seconds,
            "message_hi": f"इस नेटवर्क से अभी बहुत अनुरोध आए हैं। कृपया लगभग {minutes} मिनट बाद फिर कोशिश करें। आपका केस सुरक्षित है।",
            "message_en": f"Too many requests from this network just now. Please try again in about {minutes} minutes. Your case is safe.",
            # NEEDS NATIVE REVIEW
            "message_te": f"ఈ నెట్‌వర్క్ నుంచి ఇప్పుడు చాలా అభ్యర్థనలు వచ్చాయి. దయచేసి సుమారు {minutes} నిమిషాల తర్వాత మళ్ళీ ప్రయత్నించండి. మీ కేసు సురక్షితంగా ఉంది.",
        },
        headers={"Retry-After": str(seconds)},
    )


def busy(seconds: int = 300) -> HTTPException:
    minutes = max(1, math.ceil(seconds / 60))
    return HTTPException(
        429,
        detail={
            "code": "queue_full",
            "retry_after_s": seconds,
            "message_hi": f"अभी बहुत सी जाँचें कतार में हैं। कृपया लगभग {minutes} मिनट बाद फिर कोशिश करें। आपका केस सुरक्षित है।",
            "message_en": f"Many investigations are already waiting. Please try again in about {minutes} minutes. Your case is safe.",
            # NEEDS NATIVE REVIEW
            "message_te": f"ఇప్పటికే చాలా పరిశీలనలు వరుసలో ఉన్నాయి. దయచేసి సుమారు {minutes} నిమిషాల తర్వాత మళ్ళీ ప్రయత్నించండి. మీ కేసు సురక్షితంగా ఉంది.",
        },
        headers={"Retry-After": str(seconds)},
    )


def enforce(request: Request, bucket: str, per_hour: int) -> None:
    if (wait := retry_after(bucket, client_ip(request), per_hour)) is not None:
        raise too_many(wait)
