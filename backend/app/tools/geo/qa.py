"""Scene QA, Q1-Q5 from 03 section 2, evaluated over the context window (plot + 1.5 km)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

import numpy as np

from app.evidence.schema import SceneQA

from . import indices as ix
from .base import ENGINE_VERSION, S1_COLLECTION, GeoUnavailable, SceneRef, r4, var_dir
from .grid import Plot
from .raster import read_assets

log = logging.getLogger(__name__)

QA_BANDS = ["B02", "B03", "B04", "B08", "B11", "SCL"]
# For scenes that only feed the NDVI series of the field twin: those three bands are all it uses.
LITE_BANDS = ["B04", "B08", "SCL"]
BAND_NAMES = {"B02": "blue", "B03": "green", "B04": "red", "B08": "infrared", "B11": "shortwave-infrared", "SCL": "scene classification"}
PLOT_VALID_MIN = 0.80
B08_RANGE = (0.05, 0.60)
B04_RANGE = (0.01, 0.40)
BAD_SHARE_MAX = 0.05
VEG_NDVI_MIN = 0.30
MIN_LAND_PIXELS = 200
MIN_VEG_PIXELS = 100
Q5_MAX_SHIFT = 0.35
Q5_MAX_DAYS = 10
PLOT_WATER_SUSPECT = 0.20


@dataclass(frozen=True)
class RawQA:
    """The Q1-Q4 result. Depends only on scene and polygon, so it is safe to cache to disk."""

    status: str
    reasons: list[str]
    plot_valid_frac: float | None
    context_ndvi_median: float | None


def _median_or_none(values: np.ndarray) -> float | None:
    values = values[np.isfinite(values)]
    return float(np.median(values)) if values.size else None


def plot_clear_share(scl: np.ndarray, plot_mask: np.ndarray) -> float:
    """Q2's number. Water counts as observed, because a flooded plot is a real observation."""
    return float(np.mean(np.isin(scl[plot_mask], [ix.SCL_VEGETATION, ix.SCL_BARE, ix.SCL_WATER])))


def evaluate_optical(
    bands: dict[str, np.ndarray | None],
    offset: int | None,
    plot_mask: np.ndarray,
    required: list[str] = QA_BANDS,
) -> RawQA:
    """Q1-Q4 on arrays. Pure, so the regression logic is testable without any network."""
    rejected: list[str] = []
    notes: list[str] = []

    # Q1: every asset present, readable, and not empty.
    for band in required:
        if bands.get(band) is None:
            rejected.append(f"Q1: {BAND_NAMES[band]} band ({band}) is missing or unreadable")
    if offset is None:
        rejected.append("Q1: processing baseline is missing, so the reflectance offset cannot be determined")
    scl = bands.get("SCL")
    if scl is None or offset is None:
        return RawQA("rejected", rejected, None, None)

    imaged = scl != 0
    if not imaged[plot_mask].any():
        rejected.append("Q2: the plot lies outside the imaged area of this scene")
        return RawQA("rejected", rejected, 0.0, None)

    # Empty or zero-filled where SCL says there is an image means the band is corrupt. Zero outside
    # the swath (SCL 0) is normal at a tile edge and is not a defect.
    for band in [b for b in required if b != "SCL"]:
        arr = bands.get(band)
        if arr is None:
            continue
        bad = float(np.mean(arr[imaged] == 0)) if imaged.any() else 1.0
        if bad >= BAD_SHARE_MAX:
            label = "empty" if bad > 0.99 else f"{bad:.0%} zero-filled"
            rejected.append(f"Q3: {BAND_NAMES[band]} band ({band}) is {label} where the scene claims data")

    # Q2: plot validity.
    plot_scl = scl[plot_mask]
    plot_valid = plot_clear_share(scl, plot_mask)
    if plot_valid < PLOT_VALID_MIN:
        counts = {
            "cloud": int(np.isin(plot_scl, [8, 9]).sum()),
            "cirrus": int((plot_scl == 10).sum()),
            "shadow": int((plot_scl == 3).sum()),
            "nodata": int(np.isin(plot_scl, [0, 1]).sum()),
        }
        main = max(counts, key=lambda k: counts[k])
        rejected.append(f"Q2: only {plot_valid:.0%} of plot pixels are clear (need {PLOT_VALID_MIN:.0%}; mostly {main})")
    water_share = float(np.mean(plot_scl == ix.SCL_WATER))
    if water_share > PLOT_WATER_SUSPECT:
        notes.append(
            f"Q2: {water_share:.0%} of plot pixels classified as water; could be flooding or a dark shadow, confirm with radar"
        )

    # Q3: radiometric range over clear land in the context window, after the offset.
    land = np.isin(scl, [ix.SCL_VEGETATION, ix.SCL_BARE])
    land_px = int(land.sum())
    context_ndvi = None
    b04 = bands.get("B04")
    b08 = bands.get("B08")
    if b04 is None or b08 is None:
        return RawQA("rejected", rejected, r4(plot_valid), None)
    red = ix.to_reflectance(b04, offset)
    nir = ix.to_reflectance(b08, offset)
    if land_px < MIN_LAND_PIXELS:
        # Without clear land the radiometric checks mean nothing; a confident value is impossible.
        rejected.append(f"Q3: only {land_px} clear land pixels in the context window, too few to check radiometry")
    else:
        for name, arr, (lo, hi), label in (("B08", nir, B08_RANGE, "infrared"), ("B04", red, B04_RANGE, "red")):
            med = _median_or_none(arr[land])
            if med is None:
                rejected.append(f"Q3: {label} band ({name}) has no valid values over clear land")
            elif not lo <= med <= hi:
                rejected.append(
                    f"Q3: {label} band ({name}) median reflectance {med:.3f} is outside [{lo:.2f}, {hi:.2f}]"
                )
        vi = ix.ndvi(nir, red)
        context_ndvi = _median_or_none(vi[land])

        # Q4: pixels the classifier calls vegetation must look like vegetation.
        veg = scl == ix.SCL_VEGETATION
        if int(veg.sum()) >= MIN_VEG_PIXELS:
            veg_ndvi = _median_or_none(vi[veg])
            if veg_ndvi is None or veg_ndvi < VEG_NDVI_MIN:
                shown = "undefined" if veg_ndvi is None else f"{veg_ndvi:.2f}"
                rejected.append(
                    f"Q4: pixels classified as vegetation have median NDVI {shown} (need {VEG_NDVI_MIN:.2f}); "
                    "the image is physically implausible"
                )

    status = "rejected" if rejected else ("suspect" if notes else "accepted")
    return RawQA(status, rejected + notes, r4(plot_valid), r4(context_ndvi))


def apply_q5(raw: RawQA, scene_date: Date, previous: SceneQA | None) -> RawQA:
    """Q5: context median NDVI must not jump against the previous accepted scene within 10 days."""
    if raw.status == "rejected" or previous is None or previous.status != "accepted":
        return raw
    if raw.context_ndvi_median is None or previous.context_ndvi_median is None:
        return raw
    days = abs((scene_date - previous.date).days)
    shift = raw.context_ndvi_median - previous.context_ndvi_median
    if 0 < days <= Q5_MAX_DAYS and abs(shift) > Q5_MAX_SHIFT:
        reason = (
            f"Q5: context median NDVI moved {shift:+.2f} in {days} days against {previous.date} "
            f"(limit {Q5_MAX_SHIFT:.2f}); needs radar or another image to confirm"
        )
        return RawQA("suspect", raw.reasons + [reason], raw.plot_valid_frac, raw.context_ndvi_median)
    return raw


def evaluate_sar(vv: np.ndarray | None, vh: np.ndarray | None, plot_mask: np.ndarray) -> RawQA:
    """SAR has no cloud. The checks are: both polarisations present, plot imaged, values plausible."""
    reasons: list[str] = []
    if vv is None or vh is None:
        missing = [n for n, a in (("VV", vv), ("VH", vh)) if a is None]
        return RawQA("rejected", [f"Q1: {', '.join(missing)} missing or unreadable"], None, None)
    ok = np.isfinite(vv[plot_mask]) & np.isfinite(vh[plot_mask]) & (vv[plot_mask] > 0) & (vh[plot_mask] > 0)
    valid = float(np.mean(ok))
    if valid < PLOT_VALID_MIN:
        reasons.append(f"Q2: only {valid:.0%} of plot pixels have radar data (need {PLOT_VALID_MIN:.0%})")
    with np.errstate(invalid="ignore", divide="ignore"):
        med = np.nanmedian(10 * np.log10(vv[vv > 0])) if np.any(vv > 0) else np.nan
    if not np.isfinite(med) or not -30 <= med <= 5:
        reasons.append("Q3: context median VV is outside the plausible range of -30 to +5 dB")
    return RawQA("rejected" if reasons else "accepted", reasons, r4(valid), None)


def _cache_path(scene_id: str, plot: Plot, mode: str) -> Path:
    digest = hashlib.sha256(f"{ENGINE_VERSION}|{mode}|{scene_id}|{plot.key}".encode()).hexdigest()[:32]
    return var_dir() / "qa_cache" / f"{digest}.json"


def _cache_load(path: Path) -> RawQA | None:
    try:
        return RawQA(**json.loads(path.read_text()))
    except (OSError, ValueError, TypeError):
        return None


def _cache_store(path: Path, raw: RawQA) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as fh:
            json.dump(raw.__dict__, fh)
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("could not write the QA cache: %s", exc)


def raw_qa(scene: SceneRef, plot: Plot, *, fresh: bool = False, lite: bool = False) -> RawQA:
    """Q1-Q4 for a scene on this polygon. Cached on disk unless `fresh`; outages are never cached.

    SCL is read first because it is the smallest band: a cloudy plot is rejected on Q2 without
    paying for the rest. `lite` checks only the bands the field twin's NDVI series uses.
    """
    path = _cache_path(scene.id, plot, "lite" if lite else "full")
    if not fresh:
        cached = _cache_load(path)
        if cached is not None:
            return cached

    grid = plot.grid()
    mask = plot.stats_mask(grid)
    if scene.collection == S1_COLLECTION:
        bands = read_assets(scene.id, ["vv", "vh"], grid, is_float=True, fresh=fresh)
        raw = evaluate_sar(bands["vv"], bands["vh"], mask)
    else:
        required = LITE_BANDS if lite else QA_BANDS
        scl = read_assets(scene.id, ["SCL"], grid, fresh=fresh)["SCL"]
        try:
            offset: int | None = ix.boa_offset(scene.processing_baseline)
        except ValueError:
            offset = None
        if scl is not None and plot_clear_share(scl, mask) < PLOT_VALID_MIN:
            # Every other check would only add reasons to a scene already rejected over this plot.
            raw = evaluate_optical({"SCL": scl}, offset, mask, ["SCL"])
        else:
            others = [b for b in required if b != "SCL"]
            bands = read_assets(scene.id, others, grid, fresh=fresh) if scl is not None else {}
            bands["SCL"] = scl
            raw = evaluate_optical(bands, offset, mask, required)
    _cache_store(path, raw)
    return raw


def to_scene_qa(scene: SceneRef, raw: RawQA) -> SceneQA:
    return SceneQA(
        id=scene.id,
        collection=scene.collection,
        date=scene.date,
        status=raw.status,
        reasons=list(raw.reasons),
        metadata_cloud_pct=r4(scene.cloud_pct),
        plot_valid_frac=raw.plot_valid_frac,
        context_ndvi_median=raw.context_ndvi_median,
    )


def qa_one(scene: SceneRef, plot: Plot, previous: SceneQA | None = None, *, fresh: bool = False) -> SceneQA:
    return to_scene_qa(scene, apply_q5(raw_qa(scene, plot, fresh=fresh), scene.date, previous))


def qa_chain(scenes: list[SceneRef], plot: Plot, *, fresh: bool = False, lite: bool = False) -> list[SceneQA]:
    """QA scenes in date order with Q5 against the last accepted one. Reads run concurrently."""
    ordered = sorted(scenes, key=lambda s: (s.datetime, s.id))
    if not ordered:
        return []
    with ThreadPoolExecutor(max_workers=6, thread_name_prefix="geo-qa") as pool:
        raws = list(pool.map(lambda s: raw_qa(s, plot, fresh=fresh, lite=lite), ordered))
    out: list[SceneQA] = []
    prev: SceneQA | None = None
    for scene, raw in zip(ordered, raws):
        qa = to_scene_qa(scene, apply_q5(raw, scene.date, prev))
        out.append(qa)
        if qa.status == "accepted":
            prev = qa
    return out


__all__ = ["GeoUnavailable", "RawQA", "apply_q5", "evaluate_optical", "evaluate_sar", "qa_chain", "qa_one", "raw_qa"]
