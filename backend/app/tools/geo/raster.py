"""Windowed COG reads onto a local grid, in threads, with retries and a small in-memory LRU."""
from __future__ import annotations

import logging
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

from .base import GeoUnavailable
from .grid import Grid
from .stac import get_item

log = logging.getLogger(__name__)

GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff",
    GDAL_HTTP_TIMEOUT="60",
    GDAL_HTTP_CONNECTTIMEOUT="20",
    GDAL_HTTP_MAX_RETRY="3",
    GDAL_HTTP_RETRY_DELAY="1",
    GDAL_HTTP_MULTIRANGE="YES",
    GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
    VSI_CACHE="TRUE",
    VSI_CACHE_SIZE="5000000",
    GDAL_CACHEMAX=256,
)
RETRY_DELAYS = (1.0, 3.0, 8.0)
MAX_WORKERS = 16
LRU_BYTES = 512 * 1024 * 1024

_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="geo-read")
_lru: OrderedDict[tuple, np.ndarray] = OrderedDict()
_lru_size = 0
_lru_lock = threading.Lock()


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


def _read_once(href: str, grid: Grid, is_float: bool) -> np.ndarray:
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
            text = str(exc)
            if "404" in text or "BlobNotFound" in text:
                raise AssetMissing(f"{item_id}/{asset}: {text[:160]}") from exc
            if "403" in text or "AuthenticationFailed" in text:
                planetary_computer.sas.TOKEN_CACHE.clear()
        if delay is not None:
            log.warning("read %s/%s failed (%s); retrying in %.0f s", item_id, asset, last, delay)
            time.sleep(delay)
    raise GeoUnavailable(f"reading {item_id}/{asset} failed after {len(RETRY_DELAYS) + 1} attempts: {last}") from last


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
        cached = None if fresh else _lru_get(key)
        if cached is not None:
            out[item_id][asset] = cached
            continue
        item = get_item(item_id)
        if asset not in item.assets:
            out[item_id][asset] = None
            continue
        href = item.assets[asset].href
        pending.append((item_id, asset, key, _pool.submit(_read_with_retries, item_id, href, asset, grid, is_float)))
    for item_id, asset, key, fut in pending:
        try:
            arr = fut.result()
        except AssetMissing:
            out[item_id][asset] = None
            continue
        _lru_put(key, arr)
        out[item_id][asset] = arr
    return out
