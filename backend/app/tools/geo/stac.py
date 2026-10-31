"""STAC access: search, dedupe to one item per pass, resolve an id to a scene. All with retries."""
from __future__ import annotations

import logging
import threading
import time
from datetime import date as Date, datetime, timedelta
from typing import Callable, TypeVar

import pystac_client
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

from .base import S1_COLLECTION, S2_COLLECTION, STAC_URL, GeoUnavailable, PlotError, SceneRef, SceneUnusable
from .grid import Plot

log = logging.getLogger(__name__)
T = TypeVar("T")
RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0)

_lock = threading.Lock()
_catalog: pystac_client.Client | None = None
_items: dict[str, object] = {}  # item id -> pystac.Item, unsigned; hrefs are signed at read time


def with_retries(fn: Callable[[], T], what: str) -> T:
    last: Exception | None = None
    for delay in (*RETRY_DELAYS, None):
        try:
            return fn()
        except Exception as exc:  # the STAC client raises many unrelated exception types
            last = exc
            if delay is not None:
                log.warning("%s failed (%s); retrying in %.0f s", what, exc, delay)
                time.sleep(delay)
    raise GeoUnavailable(f"{what} failed after {len(RETRY_DELAYS) + 1} attempts: {last}") from last


def _client() -> pystac_client.Client:
    global _catalog
    with _lock:
        if _catalog is None:
            _catalog = with_retries(lambda: pystac_client.Client.open(STAC_URL), "opening the STAC catalog")
        return _catalog


def _search(collection: str, geometry: dict | None, start: Date | None, end: Date | None, ids=None) -> list:
    kwargs: dict = {"collections": [collection], "max_items": 500}
    if geometry is not None:
        kwargs["intersects"] = geometry
    if start is not None and end is not None:
        # STAC datetimes are UTC; an inclusive whole-day range matches item.date semantics below.
        kwargs["datetime"] = f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z"
    if ids is not None:
        kwargs["ids"] = list(ids)
    items = with_retries(lambda: list(_client().search(**kwargs).items()), f"searching {collection}")
    with _lock:
        for it in items:
            _items[it.id] = it
    return items


def _item_epsg(item) -> int | None:
    code = item.properties.get("proj:code") or item.properties.get("proj:epsg")
    if code is None:
        return None
    return int(str(code).split(":")[-1])


def scene_from_item(item, coverage: float | None = None) -> SceneRef:
    props = item.properties
    collection = item.collection_id
    when: datetime = item.datetime
    return SceneRef(
        id=item.id,
        collection=collection,
        date=when.date(),
        datetime=when,
        cloud_pct=props.get("eo:cloud_cover"),
        tile=props.get("s2:mgrs_tile"),
        processing_baseline=props.get("s2:processing_baseline"),
        orbit_state=props.get("sat:orbit_state"),
        relative_orbit=props.get("sat:relative_orbit"),
        platform=props.get("platform"),
        epsg=_item_epsg(item),
        coverage_frac=coverage,
    )


def _coverage(item, plot: Plot) -> tuple[float, float]:
    """Share of the plot and share of its context window inside this item's data footprint."""
    footprint = shape(item.geometry)
    grid = plot.grid()
    to_ll = Transformer.from_crs(plot.epsg, 4326, always_xy=True).transform
    right, bottom = grid.left + grid.width * grid.res, grid.top - grid.height * grid.res
    from shapely.geometry import box

    ctx = shp_transform(to_ll, box(grid.left, bottom, right, grid.top))
    plot_cov = plot.lonlat.intersection(footprint).area / plot.lonlat.area
    ctx_cov = ctx.intersection(footprint).area / ctx.area
    return plot_cov, ctx_cov


def search_scenes(collection: str, plot: Plot, start: Date, end: Date) -> list[SceneRef]:
    """One item per pass (date + relative orbit), the one covering most of the context window.

    MGRS tiles and S1 slices overlap, so a pass often yields several items for the same pixels.
    Picking on footprint coverage, then same UTM zone, then id, never on the data, keeps this
    deterministic and free of selection on the outcome.
    """
    items = _search(collection, plot.geojson, start, end)
    if not items:
        # Tell "wrong place" apart from "no pass in this short window".
        probe_end = end
        probe_start = end - timedelta(days=90)
        if not _search(collection, plot.geojson, probe_start, probe_end):
            raise PlotError(
                f"no {collection} data covers this polygon at all between {probe_start} and {probe_end}: "
                "it appears to be outside satellite coverage"
            )
        return []

    best: dict[tuple[Date, int | None], tuple[tuple, SceneRef]] = {}
    for item in items:
        plot_cov, ctx_cov = _coverage(item, plot)
        if plot_cov < 0.999:
            continue  # the plot would be partly outside this item
        scene = scene_from_item(item, round(ctx_cov, 4))
        same_zone = scene.epsg == plot.epsg
        rank = (-round(ctx_cov, 3), 0 if same_zone else 1, tuple(-ord(c) for c in item.id))
        key = (scene.date, scene.relative_orbit)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, scene)
    return sorted((v[1] for v in best.values()), key=lambda s: (s.datetime, s.id))


def get_item(scene_id: str):
    """Resolve a scene id to its STAC item, with the collection inferred from the id format."""
    with _lock:
        cached = _items.get(scene_id)
    if cached is not None:
        return cached
    if "_MSIL2A_" in scene_id:
        collection = S2_COLLECTION
    elif scene_id.endswith("_rtc"):
        collection = S1_COLLECTION
    else:
        raise SceneUnusable(f"unrecognised scene id format: {scene_id}")
    items = _search(collection, None, None, None, ids=[scene_id])
    if not items:
        raise SceneUnusable(f"scene {scene_id} was not found in {collection}")
    return items[0]


def get_scene(scene_id: str, plot: Plot | None = None) -> SceneRef:
    item = get_item(scene_id)
    cov = None
    if plot is not None:
        plot_cov, ctx_cov = _coverage(item, plot)
        if plot_cov < 0.999:
            raise SceneUnusable(
                f"scene {scene_id} covers only {plot_cov:.0%} of the plot; pick a scene whose footprint contains it"
            )
        cov = round(ctx_cov, 4)
    return scene_from_item(item, cov)
