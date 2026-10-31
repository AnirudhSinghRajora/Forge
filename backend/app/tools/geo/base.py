"""Shared types, errors and constants for the geo engine."""
from __future__ import annotations

import math
import os
from datetime import date as Date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

# Bump whenever a change could alter any computed number. It is part of the evidence hash.
ENGINE_VERSION = "geo-1.1.0"

S2_COLLECTION = "sentinel-2-l2a"
S1_COLLECTION = "sentinel-1-rtc"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
EARTH_SEARCH_URL = "https://earth-search.aws.element84.com/v1"
ARCHIVE_PC = "planetary_computer"
ARCHIVE_ES = "earth_search"

CONTEXT_M = 1500  # context = plot bbox + this
RING_M = (300, 1500)  # placebo and neighbour ring, metres from the plot edge
MAX_PLOT_HA = 50.0
MIN_RELIABLE_HA = 0.2
RED_EDGE_MIN_HA = 0.5  # NDRE and NDMI need 20 m B05/B8A, only meaningful from this size


class GeoUnavailable(RuntimeError):
    """Upstream (STAC or blob storage) still failing after retries. Nothing was computed."""


class PlotError(ValueError):
    """The polygon itself is unusable: invalid, too large, or outside satellite coverage."""


class SceneUnusable(ValueError):
    """The requested scene cannot support a computation (rejected by QA, missing, or no pixels)."""


class SceneRef(BaseModel):
    """One satellite pass over the plot. `id` is the STAC item id and is all replay needs."""

    id: str
    collection: Literal["sentinel-2-l2a", "sentinel-1-rtc"]
    date: Date
    datetime: datetime
    cloud_pct: float | None = None
    tile: str | None = None
    processing_baseline: str | None = None
    orbit_state: str | None = None
    relative_orbit: int | None = None
    platform: str | None = None
    epsg: int | None = None
    coverage_frac: float | None = None  # share of the context window inside the item footprint
    archive: Literal["planetary_computer", "earth_search"] = "planetary_computer"
    # True: this archive already removed the +1000 DN offset. None: the item does not say.
    boa_offset_applied: bool | None = False


def r4(x: float | int | None) -> float | None:
    """Round to 4 dp. NaN and None become None; -0.0 becomes 0.0 so that output is byte-stable."""
    if x is None:
        return None
    v = float(x)
    if math.isnan(v) or math.isinf(v):
        return None
    return round(v, 4) + 0.0


def var_dir() -> Path:
    env = os.environ.get("FASALSAAKSHI_VAR_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "var"
