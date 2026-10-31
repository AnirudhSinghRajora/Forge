"""Pure index and pattern math. No I/O, so all of it is unit-tested on tiny arrays."""
from __future__ import annotations

import numpy as np
from scipy import ndimage

OFFSET_BASELINE = 4.0
OFFSET_DN = 1000
SCL_VEGETATION = 4
SCL_BARE = 5
SCL_WATER = 6
SCL_CLOUD_LIKE = (3, 8, 9, 10)  # shadow, cloud medium, cloud high, cirrus
CLOUD_BUFFER_PX = 2

DROP_THRESHOLD = -0.15
PATTERN_IQR = 0.12
BARE_NDVI = 0.25


def boa_offset(baseline: str | None) -> int:
    """DN offset for a processing baseline such as '05.13'. Raises if it cannot be read.

    Baselines >= 04.00 add +1000 DN. A wrong guess silently distorts NDVI, so a missing or
    malformed baseline is an error and is never defaulted.
    """
    if baseline is None:
        raise ValueError("Sentinel-2 item has no s2:processing_baseline")
    try:
        value = float(str(baseline).strip())
    except ValueError as exc:
        raise ValueError(f"unparseable processing baseline {baseline!r}") from exc
    return OFFSET_DN if value >= OFFSET_BASELINE else 0


def to_reflectance(dn: np.ndarray, offset: int) -> np.ndarray:
    """(DN - offset) / 10000 as float32. DN 0 is the L2A nodata value and becomes NaN."""
    out = (dn.astype(np.float32) - float(offset)) / 10000.0
    out[dn == 0] = np.nan
    return out


def normalised_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b). NaN where either input is non-positive: such a ratio has no meaning."""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = (a - b) / (a + b)
    bad = ~(np.isfinite(a) & np.isfinite(b)) | (a <= 0) | (b <= 0)
    out[bad] = np.nan
    return out


def ndvi(b08: np.ndarray, b04: np.ndarray) -> np.ndarray:
    return normalised_difference(b08, b04)


def bsi(b11: np.ndarray, b04: np.ndarray, b08: np.ndarray, b02: np.ndarray) -> np.ndarray:
    """((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))."""
    return normalised_difference(b11 + b04, b08 + b02)


def clear_mask(scl: np.ndarray, allow_water: bool = False) -> np.ndarray:
    """Pixels usable for statistics: SCL vegetation or bare soil, away from cloud and shadow.

    `allow_water` is for post-event scenes only: a pixel that was crop before and is water now is
    the flood signal itself, and must not be masked away.
    """
    classes = [SCL_VEGETATION, SCL_BARE] + ([SCL_WATER] if allow_water else [])
    ok = np.isin(scl, classes)
    cloudy = np.isin(scl, SCL_CLOUD_LIKE)
    if cloudy.any():
        cloudy = ndimage.binary_dilation(cloudy, iterations=CLOUD_BUFFER_PX)
    return ok & ~cloudy


def within_plot_pattern(drop_frac: float, iqr_delta: float) -> str:
    """03 section 4. patchy: uneven damage. uniform: harvest or whole-field event."""
    if 0.2 <= drop_frac <= 0.8 and iqr_delta >= PATTERN_IQR:
        return "patchy"
    if drop_frac > 0.8 and iqr_delta < PATTERN_IQR:
        return "uniform"
    return "none"


def delta_summary(d: np.ndarray) -> tuple[float, float, float]:
    """Median, share with d <= -0.15, and IQR of a 1-D array of finite per-pixel changes."""
    p25, p50, p75 = np.percentile(d, [25, 50, 75])
    return float(p50), float(np.mean(d <= DROP_THRESHOLD)), float(p75 - p25)


def bare_fraction(ndvi_values: np.ndarray, bsi_values: np.ndarray) -> float | None:
    """Share of finite-NDVI pixels with NDVI < 0.25 and BSI > 0. 1-D inputs, same length."""
    keep = np.isfinite(ndvi_values)
    if not keep.any():
        return None
    return float(np.mean((ndvi_values[keep] < BARE_NDVI) & (bsi_values[keep] > 0)))


def otsu_threshold(values: np.ndarray, lo: float = -35.0, hi: float = 5.0, bins: int = 256) -> float:
    """Classic Otsu on a fixed histogram range, so it is deterministic and comparable."""
    v = values[np.isfinite(values)]
    v = v[(v >= lo) & (v <= hi)]
    if v.size == 0:
        return float("nan")
    counts, edges = np.histogram(v, bins=bins, range=(lo, hi))
    centres = (edges[:-1] + edges[1:]) / 2
    w = counts.astype(np.float64)
    w0 = np.cumsum(w)
    w1 = w0[-1] - w0
    m0 = np.cumsum(w * centres)
    m1 = m0[-1] - m0
    with np.errstate(invalid="ignore", divide="ignore"):
        between = w0 * w1 * (m0 / w0 - m1 / w1) ** 2
    between[~np.isfinite(between)] = -1
    return float(centres[int(np.argmax(between))])
