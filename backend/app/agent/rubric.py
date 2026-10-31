"""Verdict rubric v3 (build contract, Addendum 4): pure functions over Evidence. No I/O, no LLM.

Field signal = plot change at threshold AND (far p <= 0.025 OR ring p <= 0.025), Bonferroni across
the two tests. The far test asks whether the field changed more than comparable fields outside the
storm area; the ring test asks whether it changed more than its immediate neighbours. A missing far
test counts as not significant, never as a pass. The p <= 0.10 tier is gone, and so is v2's moderate
branch for strong field conditions with no corroboration, since v3's fixed rules do not list it.

Interpretation notes where the contract leaves a choice:
- A placebo p-value only counts when it rests on at least MIN_PLACEBOS placebos and has no
  `insufficient_reason`, since (k+1)/(n+1) on a handful of pseudo-plots proves nothing.
- A conceded wrong_plot objection caps the verdict at weak: if no crop was visible before the
  event, no signal can be read as crop loss. This is stricter than the contract table.
- A suspect post scene only counts toward moderate if the corrupt_scene objection was rebutted.

Corroboration (addendum 8) is the weather model or an official alert whose hazard matches the reported
event. Cited news is shown as related reports and never moves a level, because search hits carry no
reliable date, place or peril check.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.agent.parse import today_ist
from app.evidence.schema import Alert, Evidence, Objection, PlaceboTest, VerdictLevel

RUBRIC_VERSION = "v3"
MIN_PLACEBOS = 30
STRONG_DELTA = -0.15
MODERATE_DELTA = -0.10
P_FIELD = 0.025  # Bonferroni across the far and ring tests
# Not a threshold: a deciding p in this band is reported as near it. Seeds moved far p by a factor of 4-8.
P_NEAR_LOW = 0.01
P_NEAR_HIGH = 0.075
P_SAR = 0.05
MIN_DAYS_AFTER_EVENT = 5  # hail damage develops, so an earlier image may show too little
NEW_WATER_MIN = 0.2
STILL_COMPUTING = "the satellite comparison is still computing; this result will update when it lands"
ARCHIVE_UNREACHABLE = "the satellite archive could not be reached in this run; it will be retried soon"
RUN_INTERRUPTED = "the run was interrupted by a server restart before the comparison finished; please run it again"
NO_SUPPORT = (
    "the weather model shows no signal and no official alert for this hazard covers it, so this stays "
    "weak; related reports do not change the level"
)
RECHECK_WINDOW_DAYS = 30  # the search never looks further than this after the event
# Which official alerts speak to which reported event. A "Light" alert speaks to none of them, and
# the feed is full of those. An event with no named hazard has nothing an alert could match.
_HAZARD = {
    "hail": re.compile(r"(?i)\bhail"),
    "unseasonal_rain": re.compile(r"(?i)\brain"),
    "flood": re.compile(r"(?i)flood|inundat|waterlog|cloud\s?burst|heavy rain"),
    "cyclone": re.compile(r"(?i)cyclon|depression|storm surge"),
    "wind": re.compile(r"(?i)\bwinds?\b|squall|\bgale|dust\s?storm|cyclon"),
}
_LIGHT = re.compile(r"(?i)^\s*light\b")


@dataclass(frozen=True)
class RubricResult:
    level: VerdictLevel
    reasons: list[str]
    caveats: list[str]
    falsifiers_checked: list[str]
    version: str = RUBRIC_VERSION
    schedule_recheck: bool = False


def usable_p(placebo: PlaceboTest | None) -> float | None:
    if placebo is None or placebo.insufficient_reason or placebo.n_placebos < MIN_PLACEBOS:
        return None
    return placebo.p_value


def optical_p(ev: Evidence) -> float | None:
    """The ring test: against immediate neighbours."""
    return usable_p(ev.neighbours.placebo) if ev.neighbours else None


def far_p(ev: Evidence) -> float | None:
    """The far test: against comparable fields 5-12 km away, outside the storm area."""
    return usable_p(ev.neighbours.far_placebo) if ev.neighbours else None


def ring_significant(ev: Evidence) -> bool:
    p = optical_p(ev)
    return p is not None and p <= P_FIELD


def far_significant(ev: Evidence) -> bool:
    p = far_p(ev)
    return p is not None and p <= P_FIELD


def field_signal(ev: Evidence) -> bool:
    return ring_significant(ev) or far_significant(ev)


def post_too_early(ev: Evidence) -> bool:
    post = ev.optical.post
    return post is not None and (post.date - ev.event.date).days < MIN_DAYS_AFTER_EVENT


def sar_p(ev: Evidence) -> float | None:
    if ev.sar is None or not ev.sar.usable:
        return None
    return usable_p(ev.sar.placebo)


def _objection(ev: Evidence, oid: str) -> Objection | None:
    return next((o for o in ev.cross_examination if o.id == oid), None)


def _status(ev: Evidence, scene_id: str | None) -> str | None:
    if scene_id is None:
        return None
    return next((s.status for s in ev.optical.scenes_considered if s.id == scene_id), None)


def post_status(ev: Evidence) -> str | None:
    return _status(ev, ev.optical.post.scene_id if ev.optical.post else None)


def pre_status(ev: Evidence) -> str | None:
    return _status(ev, ev.optical.pre.scene_id if ev.optical.pre else None)


def comparison_incomplete(ev: Evidence) -> bool:
    """An accepted image exists after the event but the comparison did not finish, or the archive
    could not be searched at all. Different from "no image", and never reported as that."""
    if ev.optical.post is not None:
        return False
    if ev.verdict is not None and (
        ARCHIVE_UNREACHABLE in ev.verdict.reasons or STILL_COMPUTING in ev.verdict.reasons
        or RUN_INTERRUPTED in ev.verdict.reasons
    ):
        return True
    return any(q.status == "accepted" and q.date > ev.event.date for q in ev.optical.scenes_considered)


def accepted_optical_pair(ev: Evidence) -> bool:
    return pre_status(ev) == "accepted" and post_status(ev) == "accepted"


def alert_matches(alert: Alert, event_type: str) -> bool:
    """Whether this alert's own hazard is the one reported. The CAP event name decides when there
    is one; a record from before that field was kept falls back on the headline."""
    pattern = _HAZARD.get(event_type)
    text = (alert.event or alert.headline or "").strip()
    return bool(pattern and text and not _LIGHT.match(text) and pattern.search(text))


def matching_alerts(ev: Evidence) -> list[Alert]:
    return [a for a in ev.alerts if alert_matches(a, ev.event.type)]


def corroboration(ev: Evidence) -> list[str]:
    """Which independent sources corroborate. Weather absence never refutes; it is just absent."""
    sources = []
    if ev.weather is not None and ev.weather.corroborated:
        sources.append("weather")
    if matching_alerts(ev):
        sources.append("official_alert")
    return sources


def verdict_digest(ev: Evidence) -> str | None:
    """Sealed with the numbers. The level and weather are not recomputed by the public check, so this
    is how a later change to them is detected."""
    if ev.verdict is None:
        return None
    w = ev.weather
    payload = {
        "level": ev.verdict.level,
        "rubric_version": ev.verdict.rubric_version,
        "event_type": ev.event.type,
        "corroborated_by": corroboration(ev),
        "weather": None if w is None else {
            "source": w.source, "corroborated": w.corroborated, "max_daily_mm": w.max_daily_mm,
            "precip_mm_event_window": w.precip_mm_event_window, "hail_code_hours": w.hail_code_hours,
            "thunder_hours": w.thunder_hours, "max_gust_kmh": w.max_gust_kmh,
            "fallback_used": w.fallback_used,
        },
        "alerts": sorted(a.identifier for a in matching_alerts(ev)),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def recheck_window_open(ev: Evidence, today: date | None = None) -> bool:
    """A later pass can still land inside the window the search looks at."""
    return (today or today_ist()) <= ev.event.date + timedelta(days=RECHECK_WINDOW_DAYS)


def recheck_possible(ev: Evidence, today: date | None = None) -> bool:
    """A slow archive can be retried at any age. A new image can only help inside the window."""
    return comparison_incomplete(ev) or recheck_window_open(ev, today)


def retry_blocker(ev: Evidence, name: str) -> str | None:
    """Why this exhibit cannot be run again on this record, if it cannot."""
    pair = ev.optical.pre is not None and ev.optical.post is not None
    usable_sar = ev.sar is not None and ev.sar.usable and ev.sar.pre_scene_id and ev.sar.post_scene_id
    if name == "history" and (ev.optical.pre is None or ev.optical.plot_delta_ndvi is None):
        return "there is no optical comparison on this record to compare past years with"
    if name == "chips" and not pair:
        return "there is no image pair on this record to render"
    if name in ("village", "scale_fade") and not (pair or usable_sar):
        return "there is no trustworthy image pair on this record"
    return None


def conceded(ev: Evidence) -> list[str]:
    return [o.id for o in ev.cross_examination if o.outcome == "conceded"]


def strong_field_conditions(ev: Evidence) -> bool:
    delta = ev.optical.plot_delta_ndvi
    return (
        accepted_optical_pair(ev)
        and delta is not None
        and delta <= STRONG_DELTA
        and field_signal(ev)
        and not conceded(ev)
    )


def _tests_text(ev: Evidence) -> str:
    ring, far = optical_p(ev), far_p(ev)
    ring_text = f"ring p = {ring:.3f}" if ring is not None else "ring test not usable"
    far_text = f"far p = {far:.3f}" if far is not None else "far test not measured"
    return f"{far_text}, {ring_text} (threshold {P_FIELD} on either)"


def _moderate_signals(ev: Evidence) -> list[str]:
    signals = []
    delta = ev.optical.plot_delta_ndvi
    status = post_status(ev)
    corrupt = _objection(ev, "corrupt_scene")
    optical_trusted = status == "accepted" or (
        status == "suspect" and corrupt is not None and corrupt.outcome == "rebutted"
    )
    if optical_trusted and field_signal(ev) and delta is not None and delta <= MODERATE_DELTA:
        signals.append(f"NDVI change {delta:+.2f}; {_tests_text(ev)}")
    sp = sar_p(ev)
    if sp is not None and sp <= P_SAR:
        signals.append(f"radar placebo p = {sp:.3f}")
    water = ev.sar.new_water_frac if ev.sar and ev.sar.usable else None
    if water is not None and water >= NEW_WATER_MIN:
        signals.append(f"new standing water on {water:.0%} of the plot")
    return signals


def has_any_signal(ev: Evidence) -> bool:
    delta = ev.optical.plot_delta_ndvi
    sp = sar_p(ev)
    water = ev.sar.new_water_frac if ev.sar and ev.sar.usable else None
    return bool(
        corroboration(ev)
        or (delta is not None and delta <= MODERATE_DELTA)
        or field_signal(ev)
        or (sp is not None and sp <= P_SAR)
        or (water is not None and water >= NEW_WATER_MIN)
    )


def has_usable_data(ev: Evidence) -> bool:
    accepted_post = post_status(ev) == "accepted"
    usable_sar = ev.sar is not None and ev.sar.usable
    return accepted_post or usable_sar


def _too_few_placebos(ev: Evidence) -> bool:
    return optical_p(ev) is None and far_p(ev) is None and sar_p(ev) is None


def decide_level(ev: Evidence) -> tuple[VerdictLevel, list[str]]:
    """The rubric table, top to bottom. Returns the level and the conditions that decided it."""
    harvest = _objection(ev, "harvest")
    if harvest is not None and harvest.outcome == "conceded":
        return "not_damage_likely_harvest", ["harvest objection conceded"]

    if not has_usable_data(ev):
        if comparison_incomplete(ev):
            return "insufficient", [
                ("an accepted image exists after the event, but the comparison did not finish "
                "because the satellite archive was slow or unavailable; it will be retried")
            ]
        return "insufficient", ["no accepted optical post scene and no usable radar pair"]
    if _too_few_placebos(ev) and not has_any_signal(ev):
        return "insufficient", [f"fewer than {MIN_PLACEBOS} placebos and no other signal"]

    wrong_plot = _objection(ev, "wrong_plot")
    if wrong_plot is not None and wrong_plot.outcome == "conceded":
        return "weak", ["no crop was visible before the event (pre NDVI below 0.3)"]

    sources = corroboration(ev)
    if strong_field_conditions(ev) and sources:
        return "strong", [
            f"plot NDVI change {ev.optical.plot_delta_ndvi:+.2f} (threshold {STRONG_DELTA})",
            _tests_text(ev),
            f"corroborated by {', '.join(sources)}",
            "accepted optical scenes before and after",
            "no objection conceded",
        ]

    if sources and (signals := _moderate_signals(ev)):
        return "moderate", [*signals, f"corroborated by {', '.join(sources)}"]

    return "weak", _weak_reasons(ev, sources)


def _weak_reasons(ev: Evidence, sources: list[str]) -> list[str]:
    reasons = []
    delta = ev.optical.plot_delta_ndvi
    if delta is not None:
        reasons.append(f"plot NDVI change {delta:+.2f}")
        reasons.append(_tests_text(ev))
    if sources:
        reasons.append(f"corroborated by {', '.join(sources)}, but no plot-specific signal")
    else:
        reasons.append(NO_SUPPORT)
    if taken := conceded(ev):
        reasons.append(f"conceded objections: {', '.join(taken)}")
    return reasons


def ripening_unresolved(ev: Evidence) -> bool:
    """A drop that cannot be told from ripening, because no bare soil or history settles it."""
    harvest = _objection(ev, "harvest")
    delta = ev.optical.plot_delta_ndvi
    return (
        harvest is not None and harvest.outcome == "unresolved"
        and ev.optical.post is not None and delta is not None and delta <= MODERATE_DELTA
    )


def sensors_disagree(ev: Evidence) -> bool:
    """Optical shows a field signal, and a usable radar pair does not support it."""
    if not (field_signal(ev) and ev.optical.plot_delta_ndvi is not None
            and ev.optical.plot_delta_ndvi <= MODERATE_DELTA):
        return False
    sp = sar_p(ev)
    return sp is not None and sp > P_SAR


def area_wide(ev: Evidence) -> bool:
    return far_significant(ev) and not ring_significant(ev)


def near_threshold(p: float | None) -> bool:
    """Reported as near the threshold (build contract, addendum 7). Thresholds themselves do not move."""
    return p is not None and P_NEAR_LOW <= p <= P_NEAR_HIGH


def near_line_decides(far: float | None, ring: float | None, delta: float | None) -> bool:
    """Whether a near-threshold p could change the level, given the field's change. A delta short of the
    moderate threshold cannot reach either level, and a test clearly passing already carries the field
    signal, so a near value beside it decides nothing."""
    if delta is None or delta > MODERATE_DELTA:
        return False
    if any(p is not None and p < P_NEAR_LOW for p in (far, ring)):
        return False
    return near_threshold(far) or near_threshold(ring)


def level_could_change(ev: Evidence, level: str) -> bool:
    """near_line_decides on this evidence, where the field signal is what the level turns on."""
    if level not in ("strong", "moderate", "weak") or not corroboration(ev):
        return False
    wrong_plot = _objection(ev, "wrong_plot")
    if wrong_plot is not None and wrong_plot.outcome == "conceded":
        return False
    delta = ev.optical.plot_delta_ndvi if ev.optical.post is not None else None
    return near_line_decides(far_p(ev), optical_p(ev), delta)


NEAR_LINE_CAVEAT = (
    "A deciding comparison is near the threshold, so a slightly different drawing of this field could "
    "change this result."
)


def _caveats(ev: Evidence, level: str) -> list[str]:
    caveats = []
    if level_could_change(ev, level):
        caveats.append(NEAR_LINE_CAVEAT)
    can_recheck = recheck_possible(ev)
    if ripening_unresolved(ev):
        caveats.append(
            "If the crop was near harvest, this fall in greenness cannot be told apart from ripening "
            "without a control."
            + (" A later satellite pass will help." if can_recheck else "")
        )
    if sensors_disagree(ev):
        caveats.append(
            "Optical and radar disagree: the optical images show a change here, and the radar pair "
            "does not support it."
        )
    if area_wide(ev):
        caveats.append(
            "The effect does not look limited to your field. That is consistent with the event, but "
            "it is not proof of its cause."
        )
    if ev.weather is None:
        caveats.append("Weather data could not be retrieved for this run.")
    elif not ev.weather.corroborated:
        caveats.append(
            "The gridded weather model shows no signal here. A model this coarse can miss a small "
            "storm, so this does not rule the event out."
        )
    elif ev.weather.fallback_used:
        caveats.append("Weather came from the fallback source (NASA POWER), which has no hail codes.")
    if ev.optical.post is None and ev.sar is not None and ev.sar.usable:
        caveats.append("No usable optical image after the event, so this rests on radar alone.")
    if post_too_early(ev):
        days = (ev.optical.post.date - ev.event.date).days
        caveats.append(
            f"The image after the event is from only {days} day{'s' if days != 1 else ''} later, which may be too early: "
            "damage can take days to show."
            + (" A re-check is scheduled." if can_recheck else " The window for a later image has passed.")
        )
    if ev.neighbours is not None and ev.optical.post is not None:
        caveats.append(
            "For an event wider than 12 km, such as a whole delta under a cyclone, the far "
            "comparison loses power as well, so history and the pre-event trend carry that case."
        )
    if post_status(ev) == "suspect":
        caveats.append("The post-event image failed the temporal consistency check and is suspect.")
    if ev.plot.area_ha < 0.2:
        caveats.append("Plot under 0.2 ha: satellite pixels are coarse here; add photo evidence.")
    if ev.event.date_source != "farmer":
        caveats.append(
            f"The event date used ({ev.event.date.isoformat()}) came from {ev.event.date_source}, "
            "not from the farmer. Please confirm it."
        )
    if ev.history is not None and ev.history.downweighted:
        caveats.append("Previous years may be a different crop, so history is down-weighted.")
    if level in ("strong", "moderate"):
        caveats.append(
            "This is evidence consistent with damage, not a claim decision. Crop-cutting and "
            "insurer assessment remain separate."
        )
    return caveats


def decide(ev: Evidence) -> RubricResult:
    level, reasons = decide_level(ev)
    return RubricResult(
        level=level,
        reasons=reasons,
        caveats=_caveats(ev, level),
        falsifiers_checked=[o.id for o in ev.cross_examination],
        schedule_recheck=(
            level == "insufficient" or ev.optical.post is None or post_too_early(ev)
            or ripening_unresolved(ev)
        ),
    )
