"""The geo engine: reproducible satellite evidence for one farm plot. See docs/plan/07-build-contract.md.

Importing this package does no network I/O.
"""
from .base import ENGINE_VERSION, GeoUnavailable, PlotError, SceneRef, SceneUnusable
from .chips import render_chips
from .grid import plot_info, utm_epsg
from .optical import (
    history,
    history_scene_ids,
    optical_compare,
    qa_scene,
    search_and_qa,
    search_optical,
    timeline,
)
from .replay import flatten_numbers, replay
from .sar import sar_compare, search_sar
from .scale import scale_fade
from .stac import scene_archive
from .village import village_witness

__all__ = [
    "ENGINE_VERSION",
    "GeoUnavailable",
    "PlotError",
    "SceneRef",
    "SceneUnusable",
    "flatten_numbers",
    "history",
    "history_scene_ids",
    "optical_compare",
    "plot_info",
    "qa_scene",
    "render_chips",
    "replay",
    "sar_compare",
    "scale_fade",
    "scene_archive",
    "search_and_qa",
    "search_optical",
    "search_sar",
    "timeline",
    "utm_epsg",
    "village_witness",
]
