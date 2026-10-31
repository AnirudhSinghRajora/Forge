"""Flatten evidence to the numbers dict, and recompute it from the public archives."""
from __future__ import annotations

from app.evidence.schema import (
    HistoryEvidence,
    NeighbourEvidence,
    OpticalEvidence,
    PlaceboTest,
    PlotStats,
    ReplayCore,
    SarEvidence,
)

from .base import r4
from .optical import _optical_compare, history_from_ids
from .sar import _sar_compare


def _stats(prefix: str, s: PlotStats | None, out: dict) -> None:
    if s is None:
        return
    for name in ("valid_frac", "n_pixels", "ndvi_median", "ndvi_p25", "ndvi_p75", "bsi_median", "ndmi_median", "ndre_median"):
        out[f"{prefix}.{name}"] = r4(getattr(s, name))


def _placebo(prefix: str, p: PlaceboTest | None, out: dict) -> None:
    if p is None:
        return
    for name in ("n_placebos", "n_non_overlapping", "n_at_least_as_extreme", "p_value", "plot_value",
                 "placebo_median", "placebo_p05", "placebo_p95"):
        out[f"{prefix}.{name}"] = r4(getattr(p, name))


def flatten_numbers(
    optical: OpticalEvidence | None = None,
    neighbours: NeighbourEvidence | None = None,
    sar: SarEvidence | None = None,
    history: HistoryEvidence | None = None,
) -> dict[str, float | None]:
    """The flat "field.path" -> value dict for ReplayCore.numbers, rounded to 4 dp, sorted by key."""
    out: dict[str, float | None] = {}
    if optical is not None:
        _stats("optical.pre", optical.pre, out)
        _stats("optical.post", optical.post, out)
        for name in ("plot_delta_ndvi", "drop_frac", "iqr_delta", "post_bare_fraction"):
            out[f"optical.{name}"] = r4(getattr(optical, name))
    if neighbours is not None:
        out["neighbours.ring_outer_m"] = r4(neighbours.ring_m[1])
        for name in ("n_comparable_pixels", "neighbour_median_delta", "plot_minus_neighbour", "neighbour_bare_fraction_post"):
            out[f"neighbours.{name}"] = r4(getattr(neighbours, name))
        _placebo("neighbours.placebo", neighbours.placebo, out)
        twin = neighbours.counterfactual
        if twin is not None:
            out["neighbours.counterfactual.n_control_pixels"] = r4(twin.n_control_pixels)
            out["neighbours.counterfactual.pre_fit_rmse"] = r4(twin.pre_fit_rmse)
            out["neighbours.counterfactual.gap_at_post"] = r4(twin.gap_at_post)
    if sar is not None:
        out["sar.usable"] = 1.0 if sar.usable else 0.0
        for name in ("vv_pre_db", "vv_post_db", "vh_pre_db", "vh_post_db", "vh_change_db", "neighbour_vh_change_db",
                     "vh_excess_db", "water_frac_pre", "water_frac_post", "new_water_frac"):
            out[f"sar.{name}"] = r4(getattr(sar, name))
        _placebo("sar.placebo", sar.placebo, out)
    if history is not None:
        out["history.typical_delta"] = r4(history.typical_delta)
        out["history.excess_vs_history"] = r4(history.excess_vs_history)
        for row in history.years:
            out[f"history.{row.year}.pre_ndvi"] = r4(row.pre_ndvi)
            out[f"history.{row.year}.delta_ndvi"] = r4(row.delta_ndvi)
    return dict(sorted(out.items()))


def replay(core: ReplayCore) -> dict[str, float | None]:
    """Recompute from public data, bypassing every cache. Compare the result with core.numbers."""
    optical = neighbours = sar = hist = None
    if core.optical_pre_id and core.optical_post_id:
        optical, neighbours = _optical_compare(
            core.polygon, core.optical_pre_id, core.optical_post_id, core.seed, fresh=True
        )
    if core.sar_pre_id and core.sar_post_id:
        sar = _sar_compare(core.polygon, core.sar_pre_id, core.sar_post_id, core.seed, fresh=True)
    if core.history_scene_ids:
        # Excess is only part of the record if the original run supplied this year's delta.
        with_current = core.numbers.get("history.excess_vs_history") is not None and optical is not None
        hist = history_from_ids(
            core.polygon,
            core.history_scene_ids,
            current_delta=optical.plot_delta_ndvi if with_current else None,
            current_pre_ndvi=optical.pre.ndvi_median if with_current and optical.pre else None,
            fresh=True,
        )
    return flatten_numbers(optical, neighbours, sar, hist)
