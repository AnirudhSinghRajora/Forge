"""Read windows through a cache of whole COG blocks.

GDAL fetches whole blocks to serve any window. Keeping them means overlapping windows from different
tools cost nothing extra, and each byte is downloaded once per run, whichever tool asks first.

`fresh=True` neither reads nor writes the cache. That is what replay uses, so a recomputation really
does re-download the public data.

Only for rasters already in the grid's CRS, on the 10 m lattice, at the same or a coarser multiple of
its resolution. Anything else returns None and the caller reads through WarpedVRT. On the supported
case the result is identical to WarpedVRT with nearest resampling, which tests/geo_blocks_check.py
checks against real data.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from rasterio.windows import Window

from .base import var_dir
from .grid import Grid

log = logging.getLogger(__name__)

MEMORY_BYTES = 768 * 1024 * 1024
DISK_BYTES = 3 * 1024 * 1024 * 1024
PRUNE_EVERY_WRITES = 200


@dataclass(frozen=True)
class Layout:
    left: float
    top: float
    res_x: float
    res_y: float
    width: int
    height: int
    block_w: int
    block_h: int
    dtype: str
    nodata: float | None
    epsg: int | None


_mem: OrderedDict[tuple, np.ndarray] = OrderedDict()
_mem_bytes = 0
_mem_lock = threading.Lock()
_layouts: dict[tuple[str, str], Layout] = {}
_key_locks: dict[tuple[str, str], threading.Lock] = {}
_key_locks_guard = threading.Lock()
_writes = 0


def _root() -> Path:
    return var_dir() / "block_cache"


def _digest(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:40]


def _block_path(item_id: str, asset: str, row: int, col: int) -> Path:
    digest = _digest(item_id, asset, row, col)
    return _root() / digest[:2] / f"{digest}.npy"


def _atomic_write(path: Path, write) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            write(fh)
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("could not write the block cache: %s", exc)


def prune(limit_bytes: int = DISK_BYTES) -> None:
    """Drop the least recently written blocks once the disk cache exceeds its limit."""
    root = _root()
    if not root.exists():
        return
    files = sorted((p.stat().st_mtime, p.stat().st_size, p) for p in root.rglob("*.npy"))
    total = sum(f[1] for f in files)
    for _, size, path in files:
        if total <= limit_bytes:
            break
        path.unlink(missing_ok=True)
        total -= size


def _mem_get(key: tuple) -> np.ndarray | None:
    with _mem_lock:
        arr = _mem.get(key)
        if arr is not None:
            _mem.move_to_end(key)
        return arr


def _mem_put(key: tuple, arr: np.ndarray) -> None:
    global _mem_bytes
    with _mem_lock:
        if key in _mem:
            return
        arr.setflags(write=False)
        _mem[key] = arr
        _mem_bytes += arr.nbytes
        while _mem_bytes > MEMORY_BYTES and _mem:
            _, old = _mem.popitem(last=False)
            _mem_bytes -= old.nbytes


def _get_block(item_id: str, asset: str, row: int, col: int) -> np.ndarray | None:
    key = (item_id, asset, row, col)
    arr = _mem_get(key)
    if arr is not None:
        return arr
    try:
        arr = np.load(_block_path(item_id, asset, row, col), allow_pickle=False)
    except (OSError, ValueError):
        return None
    _mem_put(key, arr)
    return arr


def _put_block(item_id: str, asset: str, row: int, col: int, arr: np.ndarray) -> None:
    global _writes
    _mem_put((item_id, asset, row, col), arr)
    _atomic_write(_block_path(item_id, asset, row, col), lambda fh: np.save(fh, arr, allow_pickle=False))
    _writes += 1
    if _writes % PRUNE_EVERY_WRITES == 0:
        prune()


def _layout_from(ds) -> Layout:
    t = ds.transform
    block_h, block_w = ds.block_shapes[0]
    return Layout(
        float(t.c), float(t.f), float(t.a), float(-t.e), int(ds.width), int(ds.height), int(block_w), int(block_h),
        ds.dtypes[0], ds.nodata, ds.crs.to_epsg() if ds.crs else None,
    )


def _layout_path(item_id: str, asset: str) -> Path:
    return _root() / "layouts" / f"{_digest(item_id, asset)}.json"


def layout_of(item_id: str, asset: str, opener, *, fresh: bool = False) -> Layout:
    """Open the COG only if its layout is not already known. Each open costs real round trips."""
    if not fresh:
        known = _layouts.get((item_id, asset))
        if known is not None:
            return known
        try:
            known = Layout(**json.loads(_layout_path(item_id, asset).read_text()))
            _layouts[(item_id, asset)] = known
            return known
        except (OSError, ValueError, TypeError):
            pass
    with opener() as ds:
        layout = _layout_from(ds)
    if not fresh:
        _layouts[(item_id, asset)] = layout
        _atomic_write(_layout_path(item_id, asset), lambda fh: fh.write(json.dumps(asdict(layout)).encode()))
    return layout


def supported(layout: Layout, grid: Grid) -> bool:
    if layout.epsg != grid.epsg or layout.res_x != layout.res_y:
        return False
    ratio = layout.res_x / grid.res
    if ratio != int(ratio) or ratio < 1:
        return False
    # Grid pixels must not straddle source pixels: its lattice has to sit on the source's.
    return (grid.left - layout.left) % grid.res == 0 and (layout.top - grid.top) % grid.res == 0


def source_indices(layout: Layout, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    """For each grid row and column, the source pixel containing that grid pixel's centre."""
    cols = np.floor((grid.left + (np.arange(grid.width) + 0.5) * grid.res - layout.left) / layout.res_x).astype(int)
    rows = np.floor((layout.top - (grid.top - (np.arange(grid.height) + 0.5) * grid.res)) / layout.res_y).astype(int)
    return rows, cols


def assemble(layout: Layout, rows: np.ndarray, cols: np.ndarray, blocks: dict[tuple[int, int], np.ndarray], fill) -> np.ndarray:
    """Copy source pixels out of whole blocks. Pixels outside the raster get `fill`."""
    out = np.full((rows.size, cols.size), fill, dtype=layout.dtype)
    row_ok = (rows >= 0) & (rows < layout.height)
    col_ok = (cols >= 0) & (cols < layout.width)
    if not row_ok.any() or not col_ok.any():
        return out
    for (block_row, block_col), block in blocks.items():
        r_in = row_ok & (rows // layout.block_h == block_row)
        c_in = col_ok & (cols // layout.block_w == block_col)
        if r_in.any() and c_in.any():
            local_r = rows[r_in] - block_row * layout.block_h
            local_c = cols[c_in] - block_col * layout.block_w
            out[np.ix_(r_in, c_in)] = block[np.ix_(local_r, local_c)]
    return out


def needed_blocks(layout: Layout, rows: np.ndarray, cols: np.ndarray) -> list[tuple[int, int]]:
    r = rows[(rows >= 0) & (rows < layout.height)]
    c = cols[(cols >= 0) & (cols < layout.width)]
    if not r.size or not c.size:
        return []
    return [(int(i), int(j)) for i in np.unique(r // layout.block_h) for j in np.unique(c // layout.block_w)]


def _fetch(ds, layout: Layout, wanted: list[tuple[int, int]]) -> dict[tuple[int, int], np.ndarray]:
    """One read over the bounding box of the missing blocks, so GDAL can merge the ranges."""
    r0, r1 = min(b[0] for b in wanted), max(b[0] for b in wanted)
    c0, c1 = min(b[1] for b in wanted), max(b[1] for b in wanted)
    x0, y0 = c0 * layout.block_w, r0 * layout.block_h
    x1 = min((c1 + 1) * layout.block_w, layout.width)
    y1 = min((r1 + 1) * layout.block_h, layout.height)
    data = ds.read(1, window=Window(x0, y0, x1 - x0, y1 - y0))
    out = {}
    for block_row, block_col in wanted:
        ys = block_row * layout.block_h - y0
        xs = block_col * layout.block_w - x0
        out[(block_row, block_col)] = data[ys: ys + layout.block_h, xs: xs + layout.block_w].copy()
    return out


def read_through(item_id: str, asset: str, grid: Grid, opener, *, fresh: bool = False) -> tuple[np.ndarray, Layout] | None:
    """The window as source dtype, plus the layout, or None if this raster is not a supported case."""
    layout = layout_of(item_id, asset, opener, fresh=fresh)
    if not supported(layout, grid):
        return None
    rows, cols = source_indices(layout, grid)
    wanted = needed_blocks(layout, rows, cols)
    fill = layout.nodata if layout.nodata is not None else 0
    if fresh:
        if not wanted:
            return np.full(grid.shape, fill, dtype=layout.dtype), layout
        with opener() as ds:
            blocks = _fetch(ds, layout, wanted)
        return assemble(layout, rows, cols, blocks, fill), layout

    with _key_locks_guard:
        lock = _key_locks.setdefault((item_id, asset), threading.Lock())
    with lock:  # two tools asking for the same blocks must not download them twice
        blocks = {}
        missing = []
        for row, col in wanted:
            block = _get_block(item_id, asset, row, col)
            if block is None:
                missing.append((row, col))
            else:
                blocks[(row, col)] = block
        if missing:
            with opener() as ds:
                fetched = _fetch(ds, layout, missing)
            for (row, col), block in fetched.items():
                _put_block(item_id, asset, row, col, block)
                blocks[(row, col)] = block
    return assemble(layout, rows, cols, blocks, fill), layout


__all__ = ["Layout", "assemble", "needed_blocks", "prune", "read_through", "source_indices", "supported"]

