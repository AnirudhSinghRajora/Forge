"""The field twin: control pixels matched to the plot's pre-event NDVI trajectory."""
from __future__ import annotations

from datetime import date as Date

import numpy as np

from app.evidence.schema import Counterfactual, CounterfactualPoint

from .base import r4

N_CONTROLS = 300
MIN_CONTROLS = 30
MIN_PLOT_SHARE = 0.5  # a date needs this share of plot pixels observed to have a plot value


def _pct(values: np.ndarray, q: float) -> float:
    return float(np.percentile(values, q))


def field_twin(
    stack: np.ndarray,
    dates: list[Date],
    n_pre: int,
    post_index: int,
    plot_mask: np.ndarray,
    control_candidates: np.ndarray,
    n_controls: int = N_CONTROLS,
) -> Counterfactual:
    """`stack` is (time, row, col) NDVI with NaN where invalid; the first `n_pre` dates are pre-event.

    Controls must be observed on every pre date on which the plot was observed, and at the post
    date, so that the band at post uses the same pixels the fit was judged on. Ties in RMSE break
    on pixel index, which keeps selection deterministic.
    """
    n_mask = int(plot_mask.sum())
    observed: list[float | None] = []
    for t in range(stack.shape[0]):
        vals = stack[t][plot_mask]
        vals = vals[np.isfinite(vals)]
        observed.append(float(np.median(vals)) if vals.size >= MIN_PLOT_SHARE * n_mask else None)

    pre_ts = [t for t in range(n_pre) if observed[t] is not None]
    series_empty = [
        CounterfactualPoint(date=d, observed=r4(o), expected=None) for d, o in zip(dates, observed)
    ]
    if not pre_ts:
        return Counterfactual(
            n_control_pixels=0, pre_fit_rmse=None, gap_at_post=None, series=series_empty,
            method="not computed: the plot has no valid pre-event observation",
        )

    target = np.asarray([observed[t] for t in pre_ts], dtype=np.float32)
    rows, cols = np.nonzero(control_candidates)
    traj = stack[pre_ts][:, rows, cols]
    keep = np.all(np.isfinite(traj), axis=0) & np.isfinite(stack[post_index][rows, cols])
    rows, cols, traj = rows[keep], cols[keep], traj[:, keep]
    if rows.size < MIN_CONTROLS:
        return Counterfactual(
            n_control_pixels=int(rows.size), pre_fit_rmse=None, gap_at_post=None, series=series_empty,
            method=f"not computed: only {rows.size} context pixels are valid on all pre-event dates and at post",
        )

    rmse = np.sqrt(np.mean((traj - target[:, None]) ** 2, axis=0))
    chosen = np.lexsort((np.arange(rmse.size), rmse))[: n_controls]
    c_rows, c_cols = rows[chosen], cols[chosen]

    series: list[CounterfactualPoint] = []
    expected_at: dict[int, float] = {}
    for t, d in enumerate(dates):
        vals = stack[t][c_rows, c_cols]
        vals = vals[np.isfinite(vals)]
        if vals.size >= MIN_CONTROLS:
            exp = _pct(vals, 50)
            expected_at[t] = exp
            series.append(CounterfactualPoint(
                date=d, observed=r4(observed[t]), expected=r4(exp),
                expected_low=r4(_pct(vals, 10)), expected_high=r4(_pct(vals, 90)),
            ))
        else:
            series.append(CounterfactualPoint(date=d, observed=r4(observed[t]), expected=None))

    fit_pairs = [(observed[t], expected_at[t]) for t in pre_ts if t in expected_at]
    pre_fit = float(np.sqrt(np.mean([(o - e) ** 2 for o, e in fit_pairs]))) if fit_pairs else None
    gap = None
    if observed[post_index] is not None and post_index in expected_at:
        gap = observed[post_index] - expected_at[post_index]

    note = (
        f"{chosen.size} context pixels (300 m+ from the plot) with the lowest RMSE against the plot's median "
        f"NDVI on {len(pre_ts)} accepted pre-event scene(s); expected = their median, band = their p10-p90"
    )
    if len(pre_ts) == 1:
        note += "; only one pre-event scene, so this matches NDVI level only, not trajectory"
    return Counterfactual(
        n_control_pixels=int(chosen.size), pre_fit_rmse=r4(pre_fit), gap_at_post=r4(gap),
        series=series, method=note,
    )
