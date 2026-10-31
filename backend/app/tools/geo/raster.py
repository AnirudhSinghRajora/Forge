"""Windowed COG reads onto a local grid, in threads, with retries.

Read order: prefetched region, memory LRU, disk cache of real windows, then the network. The blob
store is far from India (about 0.35 MB/s measured), so bytes are what cost time. `fresh=True` goes
straight to the network and is what replay uses, so a replay really does re-download the data.
"""
from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import planetary_computer
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import RasterioError, RasterioIOError
from rasterio.vrt import WarpedVRT
from rasterio.windows import from_bounds

from .base import GeoUnavailable, var_dir
from .grid import Grid
from .stac import asset_href, get_item

log = logging.getLogger(__name__)

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff",
    GDAL_HTTP_TIMEOUT="150",
    GDAL_HTTP_CONNECTTIMEOUT="20",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="1",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    VSI_CACHE="TRUE",
    VSI_CACHE_SIZE="5000000",
    GDAL_CACHEMAX=256,
)
RETRY_DELAYS = (2.0, 5.0, 15.0)
MAX_WORKERS = 8  # the link is the limit (about 0.35 MB/s measured); more workers only cause timeouts
LRU_BYTES = 512 * 1024 * 1024
DISK_CACHE_BYTES = 3 * 1024 * 1024 * 1024
PRUNE_EVERY_WRITES = 200

_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="geo-read")
_lru: OrderedDict[tuple, np.ndarray] = OrderedDict()
_lru_size = 0
_lru_lock = threading.Lock()
_sign_lock = threading.Lock()  # the token is cached after one fetch; do not fetch it once per thread


_regions: dict[tuple[str, str], tuple[Grid, np.ndarray]] = {}
_writes_since_prune = 0
_layouts: dict[tuple[str, str], tuple[float, float, int]] = {}


class AssetMissing(Exception):
    """The asset is genuinely absent (404), which QA reports rather than treating as an outage."""


def _lru_get(key: tuple) -> np.ndarray | None:
    with _lru_lock:
        arr = _lru.get(key)
        if arr is not None:
            _lru.move_to_end(key)
        return arr


def _lru_put(key: tuple, arr: np.ndarray) -> None:
    global _lru_size
    with _lru_lock:
        if key in _lru:
            return
        arr.setflags(write=False)
        _lru[key] = arr
        _lru_size += arr.nbytes
        while _lru_size > LRU_BYTES and _lru:
            _, old = _lru.popitem(last=False)
            _lru_size -= old.nbytes


def _disk_path(key: tuple):
    digest = hashlib.sha256("|".join(key).encode()).hexdigest()[:40]
    return var_dir() / "band_cache" / digest[:2] / f"{digest}.npy"


def _disk_get(key: tuple) -> np.ndarray | None:
    try:
        return np.load(_disk_path(key), allow_pickle=False)
    except (OSError, ValueError):
        return None


def _disk_put(key: tuple, arr: np.ndarray) -> None:
    global _writes_since_prune
    _writes_since_prune += 1
    if _writes_since_prune >= PRUNE_EVERY_WRITES:
        _writes_since_prune = 0
        prune_disk_cache()
    path = _disk_path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            np.save(fh, arr, allow_pickle=False)
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("could not write the band cache: %s", exc)


def prune_disk_cache(limit_bytes: int = DISK_CACHE_BYTES) -> None:
    """Drop the least recently written windows once the cache exceeds its limit."""
    root = var_dir() / "band_cache"
    if not root.exists():
        return
    files = sorted((p.stat().st_mtime, p.stat().st_size, p) for p in root.rglob("*.npy"))
    total = sum(f[1] for f in files)
    for _, size, path in files:
        if total <= limit_bytes:
            break
        path.unlink(missing_ok=True)
        total -= size


def _crop_from_region(item_id: str, asset: str, grid: Grid) -> np.ndarray | None:
    """A prefetched region serves any aligned sub-window. Pixels are identical to a direct read."""
    region = _regions.get((item_id, asset))
    if region is None:
        return None
    big, arr = region
    if big.epsg != grid.epsg or big.res != grid.res:
        return None
    col = (grid.left - big.left) / big.res
    row = (big.top - grid.top) / big.res
    if col != int(col) or row != int(row):
        return None
    col, row = int(col), int(row)
    if col < 0 or row < 0 or col + grid.width > big.width or row + grid.height > big.height:
        return None
    return arr[row: row + grid.height, col: col + grid.width]


def prefetch_region(item_ids: list[str], assets: list[str], grid: Grid, *, is_float: bool = False) -> None:
    """Hold large windows in memory so many plots inside them need no further reads (for batch runs)."""
    got = read_many([(i, a) for i in item_ids for a in assets], grid, is_float=is_float)
    for item_id, by_asset in got.items():
        for asset, arr in by_asset.items():
            if arr is not None:
                _regions[(item_id, asset)] = (grid, arr)


def clear_regions() -> None:
    _regions.clear()


def block_layout(item_id: str, asset: str, *, fresh: bool = False) -> tuple[float, float, int]:
    """(left, top, block size in pixels) of a COG, so reads can line up with whole blocks."""
    cached = None if fresh else _layouts.get((item_id, asset))
    if cached is not None:
        return cached
    href = asset_href(get_item(item_id), asset)
    if href is None:
        raise GeoUnavailable(f"{item_id} has no asset {asset}")

    def fetch() -> tuple[float, float, int]:
        with _sign_lock:
            signed = planetary_computer.sign(href)
        with rasterio.Env(**GDAL_ENV), rasterio.open(signed) as ds:
            return (float(ds.transform.c), float(ds.transform.f), int(ds.block_shapes[0][0]))

    last: Exception | None = None
    for delay in (*RETRY_DELAYS, None):
        try:
            layout = fetch()
            _layouts[(item_id, asset)] = layout
            return layout
        except (RasterioError, RasterioIOError, OSError) as exc:
            last = exc
            if delay is not None:
                time.sleep(delay)
    raise GeoUnavailable(f"reading the layout of {item_id}/{asset} failed: {last}") from last


def read_overview(item_id: str, asset: str, grid: Grid, *, fresh: bool = False) -> np.ndarray | None:
    """A coarse read that uses the COG's overviews, which WarpedVRT does not (measured: it fetched
    native blocks for a whole tile). Only for pictures and context, never for a reported statistic.
    The item must be in the grid's CRS; otherwise this returns None and the caller reads normally.
    """
    key = (item_id, asset, grid.key, "overview")
    if not fresh:
        cached = _lru_get(key)
        if cached is None:
            cached = _disk_get(key)
        if cached is not None:
            return cached
    item = get_item(item_id)
    href = asset_href(item, asset)
    if href is None:
        return None

    def fetch() -> np.ndarray | None:
        with _sign_lock:
            signed = planetary_computer.sign(href)
        with rasterio.Env(**GDAL_ENV), rasterio.open(signed) as ds:
            if ds.crs.to_epsg() != grid.epsg:
                return None
            right, bottom = grid.left + grid.width * grid.res, grid.top - grid.height * grid.res
            window = from_bounds(grid.left, bottom, right, grid.top, ds.transform)
            return ds.read(
                1, window=window, out_shape=grid.shape, resampling=Resampling.nearest, boundless=True,
                fill_value=ds.nodata if ds.nodata is not None else 0,
            )

    last: Exception | None = None
    for delay in (*RETRY_DELAYS, None):
        try:
            data = fetch()
            if data is not None and not fresh:
                _disk_put(key, data)
                _lru_put(key, data)
            return data
        except (RasterioError, RasterioIOError, OSError) as exc:
            last = exc
            if delay is not None:
                time.sleep(delay)
    raise GeoUnavailable(f"overview read of {item_id}/{asset} failed: {last}") from last


def _read_once(href: str, grid: Grid, is_float: bool) -> np.ndarray:
    with _sign_lock:
        signed = planetary_computer.sign(href)
    with rasterio.Env(**GDAL_ENV):
        with rasterio.open(signed) as ds:
            nodata = ds.nodata if ds.nodata is not None else (0 if not is_float else -32768.0)
            with WarpedVRT(
                ds,
                crs=grid.crs,
                transform=grid.transform,
                width=grid.width,
                height=grid.height,
                resampling=Resampling.nearest,
                src_nodata=nodata,
                nodata=nodata,
            ) as vrt:
                data = vrt.read(1)
    if is_float:
        out = data.astype(np.float32)
        out[data == nodata] = np.nan
        return out
    return data


def _read_with_retries(item_id: str, href: str, asset: str, grid: Grid, is_float: bool) -> np.ndarray:
    last: Exception | None = None
    for delay in (*RETRY_DELAYS, None):
        try:
            return _read_once(href, grid, is_float)
        except (RasterioError, RasterioIOError, OSError) as exc:
            last = exc
            text = f"{exc} {exc.__cause__ or ''}"
            if "404" in text or "BlobNotFound" in text:
                raise AssetMissing(f"{item_id}/{asset}: {text[:160]}") from exc
            if "403" in text or "AuthenticationFailed" in text:
                planetary_computer.sas.TOKEN_CACHE.clear()
        if delay is not None:
            log.warning("read %s/%s failed (%s %s); retrying in %.0f s", item_id, asset, last, last.__cause__ or "", delay)
            time.sleep(delay)
    cause = f"{last} {last.__cause__ or ''}".strip()
    raise GeoUnavailable(f"reading {item_id}/{asset} failed after {len(RETRY_DELAYS) + 1} attempts: {cause}") from last


def read_assets(
    item_id: str, assets: list[str], grid: Grid, *, is_float: bool = False, fresh: bool = False
) -> dict[str, np.ndarray | None]:
    """Read several assets of one item onto `grid`. A missing asset comes back as None.

    Outages raise GeoUnavailable. `fresh` skips the in-memory cache, which is what replay needs.
    """
    return read_many([(item_id, a) for a in assets], grid, is_float=is_float, fresh=fresh)[item_id]


def read_many(
    requests: list[tuple[str, str]], grid: Grid, *, is_float: bool = False, fresh: bool = False
) -> dict[str, dict[str, np.ndarray | None]]:
    """Concurrent reads of (item_id, asset) pairs. Result is {item_id: {asset: array or None}}."""
    out: dict[str, dict[str, np.ndarray | None]] = {}
    pending = []
    for item_id, asset in requests:
        out.setdefault(item_id, {})
        key = (item_id, asset, grid.key)
        if not fresh:
            cached = _crop_from_region(item_id, asset, grid)
            if cached is None:
                cached = _lru_get(key)
            if cached is None:
                cached = _disk_get(key)
                if cached is not None:
                    _lru_put(key, cached)
            if cached is not None:
                out[item_id][asset] = cached
                continue
        href = asset_href(get_item(item_id), asset)
        if href is None:
            out[item_id][asset] = None
            continue
        pending.append((item_id, asset, key, _pool.submit(_read_with_retries, item_id, href, asset, grid, is_float)))
    for item_id, asset, key, fut in pending:
        try:
            arr = fut.result()
        except AssetMissing:
            out[item_id][asset] = None
            continue
        if not fresh:
            _disk_put(key, arr)
            _lru_put(key, arr)
        out[item_id][asset] = arr
    return out
