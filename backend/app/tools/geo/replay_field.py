"""Cheapest first public replay: only the plot's own pixels, re-read from the public archive.

The full comparison reads windows kilometres wide, which takes minutes on a thin link. Plot statistics
need only the plot. This reads a window just large enough for them, with fresh=True, and computes
exactly the numbers the full engine reports for those fields, from the same index helpers.

Why the numbers cannot differ from a wider window:
- Every window snaps to the same 10 m lattice, so a pixel is the same pixel in any window.
- Cloud masking dilates by CLOUD_BUFFER_PX, so a cloud just outside the plot still removes pixels in
  it. The window keeps that margin, which is the only way a pixel's validity depends on its surroundings.
- Nothing else here looks at neighbouring pixels. The radar median filter is only used for water and
  comparability, which are not field values, so those numbers stay out of this module.

QA is not repeated here. The sealed record already passed it, and the full optical group re-runs it.
"""
from __future__ import annotations

import numpy as np

from . import indices as ix
from .base import RED_EDGE_MIN_HA, S1_COLLECTION, S2_COLLECTION, SceneUnusable, r4
from .grid import RES, parse_plot
from .raster import read_many
from .sar import to_db
from .stac import get_scene

CORE_BANDS = ["B04", "B08", "SCL"]
EXTRA_BANDS = ["B02", "B11"]
RED_EDGE_BANDS = ["B05", "B8A"]
WINDOW_MARGIN_M = (ix.CLOUD_BUFFER_PX + 1) * RES  # cloud dilation reach, plus one pixel to be safe


def _median(values: np.ndarray) -> float | None:
    values = values[np.isfinite(values)]
    return float(np.median(values)) if values.size else None


class FieldReplay:
    """Three steps, so that numbers tick early: before, after and the change, then the extra bands."""

    def __init__(self, polygon: dict, pre_id: str, post_id: str):
        self.plot = parse_plot(polygon)
        self.pre = get_scene(pre_id, self.plot)
        self.post = get_scene(post_id, self.plot)
        if self.pre.collection != S2_COLLECTION or self.post.collection != S2_COLLECTION:
            raise SceneUnusable("the field replay needs two Sentinel-2 scenes")
        self.grid = self.plot.grid(WINDOW_MARGIN_M)
        self.mask = self.plot.stats_mask(self.grid)
        self.bands: dict[str, dict] = {}
        self.vi: dict[str, np.ndarray] = {}
        self.valid: dict[str, np.ndarray] = {}

    def _offset(self, scene) -> int:
        try:
            return ix.scene_offset(scene.processing_baseline, scene.boa_offset_applied)
        except ValueError as exc:
            raise SceneUnusable(f"{scene.id}: {exc}") from exc

    def _read(self, names: list[str]) -> None:
        got = read_many([(s.id, n) for s in (self.pre, self.post) for n in names], self.grid, fresh=True)
        for scene in (self.pre, self.post):
            self.bands.setdefault(scene.id, {}).update(got[scene.id])

    def _refl(self, scene, name: str) -> np.ndarray:
        arr = self.bands[scene.id].get(name)
        if arr is None:
            raise SceneUnusable(f"{scene.id}: band {name} is missing or unreadable")
        return ix.to_reflectance(arr, self._offset(scene))

    def _scene_stats(self, prefix: str, scene, is_post: bool) -> dict[str, float | None]:
        got = read_many([(scene.id, n) for n in CORE_BANDS], self.grid, fresh=True)[scene.id]
        self.bands.setdefault(scene.id, {}).update(got)
        if got.get("SCL") is None:
            raise SceneUnusable(f"{scene.id}: band SCL is missing or unreadable")
        valid = ix.clear_mask(got["SCL"], allow_water=is_post)
        vi = ix.ndvi(self._refl(scene, "B08"), self._refl(scene, "B04"))
        vi[~valid] = np.nan
        valid = valid & np.isfinite(vi)
        self.vi[scene.id], self.valid[scene.id] = vi, valid
        pick = self.mask & valid
        n = int(pick.sum())
        if n == 0:
            raise SceneUnusable(f"{scene.id}: no valid pixels inside the plot")
        p25, p50, p75 = np.percentile(vi[pick], [25, 50, 75])
        return {
            f"{prefix}.valid_frac": r4(n / self.mask.sum()),
            f"{prefix}.n_pixels": r4(n),
            f"{prefix}.ndvi_median": r4(p50),
            f"{prefix}.ndvi_p25": r4(p25),
            f"{prefix}.ndvi_p75": r4(p75),
        }

    def pre_stats(self) -> dict[str, float | None]:
        """NDVI statistics of the image before the event: three bands, so the first numbers come quickly."""
        return self._scene_stats("optical.pre", self.pre, False)

    def post_stats(self) -> dict[str, float | None]:
        """The image after the event, and the change between the two."""
        if self.pre.id not in self.vi:
            self.pre_stats()
        out = self._scene_stats("optical.post", self.post, True)
        pair = self.mask & self.valid[self.pre.id] & self.valid[self.post.id]
        if not pair.any():
            raise SceneUnusable("the plot has no pixel that is valid in both scenes")
        delta, drop_frac, iqr = ix.delta_summary((self.vi[self.post.id] - self.vi[self.pre.id])[pair])
        out["optical.plot_delta_ndvi"] = r4(delta)
        out["optical.drop_frac"] = r4(drop_frac)
        out["optical.iqr_delta"] = r4(iqr)
        return out

    def core(self) -> dict[str, float | None]:
        return {**self.pre_stats(), **self.post_stats()}

    def extra(self) -> dict[str, float | None]:
        """Bare soil and, on larger plots, red edge. Needs core() to have run."""
        if self.post.id not in self.vi:
            self.post_stats()
        red_edge = self.plot.area_ha >= RED_EDGE_MIN_HA
        self._read(EXTRA_BANDS + (RED_EDGE_BANDS if red_edge else []))
        out: dict[str, float | None] = {}
        mask = self.mask
        for prefix, scene in (("optical.pre", self.pre), ("optical.post", self.post)):
            refl = {n: self._refl(scene, n) for n in ("B02", "B04", "B08", "B11")}
            pick = mask & self.valid[scene.id]
            bsi = ix.bsi(refl["B11"], refl["B04"], refl["B08"], refl["B02"])
            out[f"{prefix}.bsi_median"] = r4(_median(bsi[pick]))
            ndmi = ndre = None
            have = self.bands[scene.id]
            if red_edge and have.get("B05") is not None and have.get("B8A") is not None:
                b8a = self._refl(scene, "B8A")
                ndre = r4(_median(ix.normalised_difference(b8a, self._refl(scene, "B05"))[pick]))
                ndmi = r4(_median(ix.normalised_difference(b8a, refl["B11"])[pick]))
            out[f"{prefix}.ndmi_median"] = ndmi
            out[f"{prefix}.ndre_median"] = ndre
            if scene.id == self.post.id:
                out["optical.post_bare_fraction"] = r4(ix.bare_fraction(self.vi[scene.id][pick], bsi[pick]))
        return out


def replay_sar_field(polygon: dict, pre_id: str, post_id: str) -> dict[str, float | None]:
    """Radar plot medians only, re-read from the archive. Water and placebo need the wider window."""
    plot = parse_plot(polygon)
    pre, post = get_scene(pre_id, plot), get_scene(post_id, plot)
    if pre.collection != S1_COLLECTION or post.collection != S1_COLLECTION:
        raise SceneUnusable("the radar field replay needs two Sentinel-1 RTC scenes")
    grid = plot.grid(RES)
    mask = plot.stats_mask(grid)
    got = read_many([(s.id, n) for s in (pre, post) for n in ("vv", "vh")], grid, is_float=True, fresh=True)
    for scene in (pre, post):
        if got[scene.id].get("vv") is None or got[scene.id].get("vh") is None:
            raise SceneUnusable(f"{scene.id}: VV or VH asset is missing")
    vv_a, vh_a = to_db(got[pre.id]["vv"]), to_db(got[pre.id]["vh"])
    vv_b, vh_b = to_db(got[post.id]["vv"]), to_db(got[post.id]["vh"])
    pick = mask & np.isfinite(vv_a) & np.isfinite(vv_b) & np.isfinite(vh_a) & np.isfinite(vh_b)
    if not pick.any():
        raise SceneUnusable("the plot has no radar pixel valid in both scenes")
    return {
        "sar.vv_pre_db": r4(np.median(vv_a[pick])),
        "sar.vv_post_db": r4(np.median(vv_b[pick])),
        "sar.vh_pre_db": r4(np.median(vh_a[pick])),
        "sar.vh_post_db": r4(np.median(vh_b[pick])),
        "sar.vh_change_db": r4(np.median((vh_b - vh_a)[pick])),
    }
