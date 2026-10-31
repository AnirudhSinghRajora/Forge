"""Polygon validation and the local UTM pixel grid every band is read onto."""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import numpy as np
from affine import Affine
from pyproj import Transformer
from rasterio.features import geometry_mask
from scipy import ndimage
from shapely.geometry import box, mapping, shape
from shapely.ops import transform as shp_transform

from .base import CONTEXT_M, MAX_PLOT_HA, MIN_RELIABLE_HA, PlotError, r4

RES = 10


def utm_epsg(lon: float, lat: float) -> int:
    """UTM zone from the coordinates: Sirsa (75.03E) is 32643, coastal Andhra (82E) is 32644."""
    zone = int((lon + 180.0) // 6) + 1
    zone = min(zone, 60)
    return (32600 if lat >= 0 else 32700) + zone


@dataclass(frozen=True)
class Grid:
    epsg: int
    left: float
    top: float
    width: int
    height: int
    res: int = RES

    @property
    def crs(self) -> str:
        return f"EPSG:{self.epsg}"

    @property
    def transform(self) -> Affine:
        return Affine(self.res, 0.0, self.left, 0.0, -self.res, self.top)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    @property
    def key(self) -> str:
        return f"{self.epsg}:{self.left:.0f}:{self.top:.0f}:{self.width}:{self.height}:{self.res}"

    def lonlat_bounds(self) -> tuple[float, float, float, float]:
        to_ll = Transformer.from_crs(self.epsg, 4326, always_xy=True)
        right, bottom = self.left + self.width * self.res, self.top - self.height * self.res
        xs = np.linspace(self.left, right, 21)
        ys = np.linspace(bottom, self.top, 21)
        edge_x = np.concatenate([xs, xs, np.full(21, self.left), np.full(21, right)])
        edge_y = np.concatenate([np.full(21, bottom), np.full(21, self.top), ys, ys])
        lon, lat = to_ll.transform(edge_x, edge_y)
        return (float(np.min(lon)), float(np.min(lat)), float(np.max(lon)), float(np.max(lat)))

    def lonlat_polygon(self) -> dict:
        w, s, e, n = self.lonlat_bounds()
        return mapping(box(w, s, e, n))


@dataclass(frozen=True)
class Plot:
    geojson: dict
    lonlat: object
    utm: object
    epsg: int
    area_ha: float
    centroid: tuple[float, float]
    warnings: tuple[str, ...]

    def grid(self, buffer_m: float = CONTEXT_M) -> Grid:
        """Plot bbox plus a buffer, snapped outward to the 10 m pixel lattice Sentinel uses."""
        minx, miny, maxx, maxy = self.utm.bounds
        left = np.floor((minx - buffer_m) / RES) * RES
        right = np.ceil((maxx + buffer_m) / RES) * RES
        bottom = np.floor((miny - buffer_m) / RES) * RES
        top = np.ceil((maxy + buffer_m) / RES) * RES
        return Grid(self.epsg, float(left), float(top), int((right - left) / RES), int((top - bottom) / RES))

    def full_mask(self, grid: Grid) -> np.ndarray:
        """Pixels whose centre lies inside the polygon as drawn."""
        return geometry_mask([mapping(self.utm)], out_shape=grid.shape, transform=grid.transform, invert=True)

    def stats_mask(self, grid: Grid) -> np.ndarray:
        """Eroded by one pixel to drop mixed edge pixels, unless that leaves under 20 pixels (03 s1)."""
        eroded = self.utm.buffer(-RES, join_style=2)
        if not eroded.is_empty:
            mask = geometry_mask([mapping(eroded)], out_shape=grid.shape, transform=grid.transform, invert=True)
            if mask.sum() >= 20:
                return mask
        mask = self.full_mask(grid)
        if mask.sum() == 0:
            raise PlotError("polygon covers no 10 m pixel centre; it is too small to measure")
        return mask

    def distance_m(self, grid: Grid) -> np.ndarray:
        """Distance of every pixel from the plot edge, in metres. Zero inside the plot."""
        return ndimage.distance_transform_edt(~self.full_mask(grid)) * grid.res

    @cached_property
    def key(self) -> str:
        return ",".join(f"{x:.7f},{y:.7f}" for x, y in self.lonlat.exterior.coords)


def parse_plot(polygon: dict) -> Plot:
    """Validate a GeoJSON Polygon (or Feature holding one) in EPSG:4326. Raises PlotError clearly."""
    if isinstance(polygon, dict) and polygon.get("type") == "Feature":
        polygon = polygon.get("geometry") or {}
    if not isinstance(polygon, dict) or polygon.get("type") != "Polygon":
        raise PlotError("plot must be a GeoJSON Polygon in EPSG:4326")
    try:
        geom = shape(polygon)
    except Exception as exc:
        raise PlotError(f"could not read the polygon: {exc}") from exc
    if geom.is_empty:
        raise PlotError("plot polygon is empty")
    if not geom.is_valid:
        raise PlotError("plot polygon is invalid (it may cross itself)")
    w, s, e, n = geom.bounds
    if not (-180 <= w and e <= 180 and -90 <= s and n <= 90):
        raise PlotError("plot coordinates are out of range; expected [longitude, latitude]")
    if not (geom.bounds[2] - geom.bounds[0] < 1 and geom.bounds[3] - geom.bounds[1] < 1):
        raise PlotError("plot spans more than a degree; check the coordinates and their [lon, lat] order")

    c = geom.centroid
    epsg = utm_epsg(c.x, c.y)
    project = Transformer.from_crs(4326, epsg, always_xy=True).transform
    utm = shp_transform(project, geom)
    area_ha = utm.area / 10000.0
    if area_ha > MAX_PLOT_HA:
        raise PlotError(
            f"plot is {area_ha:.1f} ha; the limit is {MAX_PLOT_HA:.0f} ha. Draw one field, not a whole farm or block."
        )
    warnings = []
    if area_ha < MIN_RELIABLE_HA:
        warnings.append(
            f"plot is {area_ha:.2f} ha, under {MIN_RELIABLE_HA} ha: too small for reliable satellite evidence; "
            "photo evidence advised"
        )
    return Plot(polygon, geom, utm, epsg, area_ha, (c.x, c.y), tuple(warnings))


def plot_info(polygon: dict):
    """Fill schema.PlotInfo. Raises PlotError if the polygon cannot be used."""
    from app.evidence.schema import PlotInfo

    plot = parse_plot(polygon)
    return PlotInfo(
        geometry=mapping(plot.lonlat),
        area_ha=r4(plot.area_ha),
        centroid=(round(plot.centroid[0], 6), round(plot.centroid[1], 6)),
        crs=f"EPSG:{plot.epsg}",
        warnings=list(plot.warnings),
    )
