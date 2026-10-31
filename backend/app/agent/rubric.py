"""Verdict rubric v2 from the build contract: pure functions over Evidence. No I/O, no LLM.

Interpretation notes where the contract leaves a choice:
- A placebo p-value only counts when it rests on at least MIN_PLACEBOS placebos and has no
  `insufficient_reason`, since (k+1)/(n+1) on a handful of pseudo-plots proves nothing.
- A conceded wrong_plot objection caps the verdict at weak: if no crop was visible before the
  event, no signal can be read as crop loss. This is stricter than the contract table.
- A suspect post scene only counts toward moderate if the corrupt_scene objection was rebutted.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.evidence.schema import Evidence, Objection, PlaceboTest, VerdictLevel

RUBRIC_VERSION = "v2"
MIN_PLACEBOS = 30
STRONG_DELTA = -0.15
MODERATE_DELTA = -0.10
P_STRICT = 0.05
P_LOOSE = 0.10
NEW_WATER_MIN = 0.2
ARCHIVE_UNREACHABLE = "the satellite archive could not be reached in this run; it will be retried soon"


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
    return usable_p(ev.neighbours.placebo) if ev.neighbours else None


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
    if ev.verdict is not None and ARCHIVE_UNREACHABLE in ev.verdict.reasons:
        return True
    return any(q.status == "accepted" and q.date > ev.event.date for q in ev.optical.scenes_considered)


def accepted_optical_pair(ev: Evidence) -> bool:
    return pre_status(ev) == "accepted" and post_status(ev) == "accepted"


def corroboration(ev: Evidence) -> list[str]:
    """Which independent sources corroborate. Weather absence never refutes; it is just absent."""
    sources = []
    if ev.weather is not None and ev.weather.corroborated:
        sources.append("weather")
    if ev.alerts:
        sources.append("official_alert")
    if ev.news:
        sources.append("news")
    return sources


def conceded(ev: Evidence) -> list[str]:
    return [o.id for o in ev.cross_examination if o.outcome == "conceded"]


def event_date_unresolved(ev: Evidence) -> bool:
    """No source confirms or contradicts the farmer's date: the Sirsa-style case."""
    if corroboration(ev):
        return False
    wrong_date = _objection(ev, "wrong_date")
    return wrong_date is None or wrong_date.outcome == "unresolved"


def strong_field_conditions(ev: Evidence) -> bool:
    delta = ev.optical.plot_delta_ndvi
    p = optical_p(ev)
    return (
        accepted_optical_pair(ev)
        and delta is not None
        and delta <= STRONG_DELTA
        and p is not None
        and p <= P_STRICT
        and not conceded(ev)
    )


def _moderate_signals(ev: Evidence) -> list[str]:
    signals = []
    delta = ev.optical.plot_delta_ndvi
    p = optical_p(ev)
    status = post_status(ev)
    corrupt = _objection(ev, "corrupt_scene")
    optical_trusted = status == "accepted" or (
        status == "suspect" and corrupt is not None and corrupt.outcome == "rebutted"
    )
    if optical_trusted and p is not None and p <= P_LOOSE and delta is not None and (
        delta <= MODERATE_DELTA
    ):
        signals.append(f"optical placebo p = {p:.3f} with NDVI change {delta:+.2f}")
    sp = sar_p(ev)
    if sp is not None and sp <= P_STRICT:
        signals.append(f"radar placebo p = {sp:.3f}")
    water = ev.sar.new_water_frac if ev.sar and ev.sar.usable else None
    if water is not None and water >= NEW_WATER_MIN:
        signals.append(f"new standing water on {water:.0%} of the plot")
    return signals


def has_any_signal(ev: Evidence) -> bool:
    delta = ev.optical.plot_delta_ndvi
    p = optical_p(ev)
    sp = sar_p(ev)
    water = ev.sar.new_water_frac if ev.sar and ev.sar.usable else None
    return bool(
        corroboration(ev)
        or (delta is not None and delta <= MODERATE_DELTA)
        or (p is not None and p <= P_LOOSE)
        or (sp is not None and sp <= P_LOOSE)
        or (water is not None and water >= NEW_WATER_MIN)
    )


def has_usable_data(ev: Evidence) -> bool:
    accepted_post = post_status(ev) == "accepted"
    usable_sar = ev.sar is not None and ev.sar.usable
    return accepted_post or usable_sar


def _too_few_placebos(ev: Evidence) -> bool:
    return optical_p(ev) is None and sar_p(ev) is None


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
            f"optical placebo p = {optical_p(ev):.3f} (threshold {P_STRICT})",
            f"corroborated by {', '.join(sources)}",
            "accepted optical scenes before and after",
            "no objection conceded",
        ]

    if sources and (signals := _moderate_signals(ev)):
        return "moderate", [*signals, f"corroborated by {', '.join(sources)}"]
    if strong_field_conditions(ev) and not sources and event_date_unresolved(ev):
        return "moderate", [
            f"plot NDVI change {ev.optical.plot_delta_ndvi:+.2f}",
            f"optical placebo p = {optical_p(ev):.3f}",
            "no source confirms or contradicts the reported date",
        ]

    return "weak", _weak_reasons(ev, sources)


def _weak_reasons(ev: Evidence, sources: list[str]) -> list[str]:
    reasons = []
    delta = ev.optical.plot_delta_ndvi
    p = optical_p(ev)
    if delta is not None:
        reasons.append(f"plot NDVI change {delta:+.2f}")
    if p is not None:
        reasons.append(f"optical placebo p = {p:.3f}")
    if sources:
        reasons.append(f"corroborated by {', '.join(sources)}, but no plot-specific signal")
    else:
        reasons.append("no corroboration from weather, alerts or news")
    if taken := conceded(ev):
        reasons.append(f"conceded objections: {', '.join(taken)}")
    return reasons


def _caveats(ev: Evidence, level: str) -> list[str]:
    caveats = []
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
        schedule_recheck=level == "insufficient" or ev.optical.post is None,
    )
