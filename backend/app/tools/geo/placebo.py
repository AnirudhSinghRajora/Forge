"""Randomization inference: same-shape pseudo-plots placed around the real plot.

Pure numpy, seeded, and independent of any I/O, so it can be tested on synthetic arrays.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import fftconvolve

from .base import r4

TARGET_PLACEBOS = 200
MIN_PLACEBOS = 30
MIN_VALID_SHARE = 0.8
MAX_EVALUATIONS = 30000
HIST_BINS = 20


@dataclass(frozen=True)
class PlacementResult:
    values: np.ndarray  # statistic for each accepted placement
    offsets: np.ndarray  # (row, col) of the top-left of the mask's bbox
    n_non_overlapping: int  # placements from the first pass, whose bboxes do not overlap
    n_candidates: int  # geometrically feasible offsets that were available
    n_evaluated: int


def p_value(plot_value: float, placebo_values: np.ndarray) -> tuple[int, float]:
    """(k + 1) / (n + 1), with k = placebos whose drop is at least as extreme (value <= plot)."""
    k = int(np.sum(placebo_values <= plot_value))
    return k, (k + 1) / (placebo_values.size + 1)


def _count_map(field: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """For each top-left offset, how many mask pixels fall on True pixels of `field`."""
    return np.rint(fftconvolve(field.astype(np.float64), kernel[::-1, ::-1].astype(np.float64), mode="valid"))


def sample_placements(
    mask: np.ndarray,
    ring: np.ndarray,
    valid: np.ndarray,
    pre: np.ndarray,
    delta: np.ndarray,
    plot_pre_median: float,
    seed: int,
    pre_tolerance: float,
    target: int = TARGET_PLACEBOS,
    allow_overlap: bool = True,
    plot_pre_iqr: float | None = None,
    spread_tolerance: float | None = None,
) -> PlacementResult:
    """Translate `mask` to random feasible positions and compute the median delta at each.

    A placement counts only if all its pixels lie in `ring`, at least 80% of them are valid in
    both scenes, and its pre-event median is within `pre_tolerance` of the plot's. If
    `spread_tolerance` is given, its pre-event IQR must also be that close to the plot's: on real
    data a uniform field and a half-bare mix with the same median behave differently, and matching
    on the median alone made p-values too small for uniform plots. The first pass
    takes placements whose bounding boxes do not overlap. If that falls short of `target`, a second
    pass fills up with overlapping ones, which are correlated with each other.
    """
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        raise ValueError("empty plot mask")
    r0, c0 = rows.min(), cols.min()
    rel_r, rel_c = rows - r0, cols - c0
    h, w = int(rel_r.max()) + 1, int(rel_c.max()) + 1
    n_mask = rows.size
    if h > ring.shape[0] or w > ring.shape[1]:
        return PlacementResult(np.empty(0), np.empty((0, 2), int), 0, 0, 0)

    kernel = np.zeros((h, w), dtype=bool)
    kernel[rel_r, rel_c] = True
    in_ring = _count_map(ring, kernel) == n_mask
    enough_valid = _count_map(ring & valid, kernel) >= np.ceil(MIN_VALID_SHARE * n_mask)
    cand_r, cand_c = np.nonzero(in_ring & enough_valid)

    rng = np.random.default_rng(seed)
    order = rng.permutation(cand_r.size)

    values: list[float] = []
    offsets: list[tuple[int, int]] = []
    n_evaluated = 0

    def evaluate(y: int, x: int) -> bool:
        nonlocal n_evaluated
        n_evaluated += 1
        pr, pc = rel_r + y, rel_c + x
        ok = valid[pr, pc]
        if not ok.any():
            return False
        pre_values = pre[pr[ok], pc[ok]]
        if abs(float(np.median(pre_values)) - plot_pre_median) > pre_tolerance:
            return False
        if spread_tolerance is not None:
            q25, q75 = np.percentile(pre_values, [25, 75])
            if abs(float(q75 - q25) - plot_pre_iqr) > spread_tolerance:
                return False
        values.append(float(np.median(delta[pr[ok], pc[ok]])))
        offsets.append((y, x))
        return True

    # First pass: bounding boxes that do not overlap any accepted one. `blocked` marks every
    # top-left offset whose bbox would overlap an accepted placement, which makes the test O(1).
    blocked = np.zeros(ring.shape, dtype=bool)
    skipped: list[tuple[int, int]] = []
    for idx in order:
        if len(values) >= target or n_evaluated >= MAX_EVALUATIONS:
            break
        y, x = int(cand_r[idx]), int(cand_c[idx])
        if blocked[y, x]:
            skipped.append((y, x))
        elif evaluate(y, x):
            blocked[max(0, y - h + 1): y + h, max(0, x - w + 1): x + w] = True
    n_non_overlapping = len(values)

    # Second pass: fill up from the overlapping offsets, which are correlated with their neighbours.
    for y, x in skipped if allow_overlap else []:
        if len(values) >= target or n_evaluated >= MAX_EVALUATIONS:
            break
        evaluate(y, x)

    return PlacementResult(
        np.asarray(values, dtype=np.float64),
        np.asarray(offsets, dtype=int).reshape(-1, 2),
        n_non_overlapping,
        int(cand_r.size),
        n_evaluated,
    )


def build_placebo_fields(result: PlacementResult, plot_value: float, statistic: str, seed: int) -> dict:
    """The kwargs for schema.PlaceboTest. Below 30 placements there is no p-value to report."""
    vals = result.values
    n = int(vals.size)
    reason = None
    if n < MIN_PLACEBOS:
        reason = (
            f"only {n} comparable same-shape placements with valid pixels in both scenes "
            f"({result.n_candidates} feasible offsets, {result.n_evaluated} evaluated); need {MIN_PLACEBOS}"
        )
    if n:
        edges = np.linspace(min(vals.min(), plot_value), max(vals.max(), plot_value), HIST_BINS + 1)
        if edges[0] == edges[-1]:
            edges = np.linspace(edges[0] - 0.05, edges[0] + 0.05, HIST_BINS + 1)
        counts, edges = np.histogram(vals, bins=edges)
        p05, med, p95 = np.percentile(vals, [5, 50, 95])
    else:
        counts, edges = np.empty(0, int), np.empty(0)
        p05 = med = p95 = None
    k, p = p_value(plot_value, vals)
    return {
        "n_placebos": n,
        "n_non_overlapping": result.n_non_overlapping,
        "n_at_least_as_extreme": k,
        "p_value": 1.0 if reason else r4(p),
        "statistic": statistic,
        "plot_value": r4(plot_value),
        "placebo_median": r4(med),
        "placebo_p05": r4(p05),
        "placebo_p95": r4(p95),
        "histogram_edges": [r4(e) for e in edges],
        "histogram_counts": [int(c) for c in counts],
        "seed": seed,
        "insufficient_reason": reason,
    }
