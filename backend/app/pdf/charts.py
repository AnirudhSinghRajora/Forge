"""Charts for the evidence pack, rendered with matplotlib from real values only.

Labels stay in English on purpose: matplotlib does not shape Devanagari or Telugu correctly, so
localized captions are set in the HTML around each chart. A chart with no data returns None.
Palette: reference data-viz slots, checked with the palette validator (blue, orange on light).
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import itertools

import matplotlib.dates
import matplotlib.pyplot as plt

from app.agent.cross_exam import signed
from app.evidence.schema import Evidence, PlaceboTest, ScaleFade, SurveyLottery

SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#c9c8c2"
GRID = "#e6e5e0"
SURFACE = "#ffffff"


STATISTIC_LABELS = {
    "median_delta_ndvi": "Change in greenness (NDVI)",
    "delta_ndvi": "Change in greenness (NDVI)",
    "median_vh_change_db": "Change in radar signal (VH, dB)",
    "vh_change_db": "Change in radar signal (VH, dB)",
}


def statistic_label(statistic: str) -> str:
    """A chart's words for a statistic. A machine name not listed here still reads as words."""
    return STATISTIC_LABELS.get(statistic, statistic.replace("_", " "))


def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def _save(fig, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _histogram(edges, counts, ax, color) -> None:
    widths = [b - a for a, b in itertools.pairwise(edges)]
    # A small gap between neighbouring bars keeps them countable.
    ax.bar(edges[:-1], counts, width=[w * 0.92 for w in widths], align="edge", color=color,
           linewidth=0)


def _marker(ax, x: float, label: str, ymax: float, color: str, side: str = "right") -> None:
    ax.axvline(x, color=color, linewidth=2)
    ha = "left" if side == "right" else "right"
    offset = 4 if side == "right" else -4
    ax.annotate(label, xy=(x, ymax), xytext=(offset, 0), textcoords="offset points", ha=ha,
                va="top", fontsize=8, color=INK, fontweight="bold")


def placebo_histogram(placebo: PlaceboTest | None, path: Path, label: str = "same-shape look-alike fields"
                      ) -> str | None:
    if placebo is None or not placebo.histogram_counts or placebo.n_placebos <= 0:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    _style(ax)
    _histogram(placebo.histogram_edges, placebo.histogram_counts, ax, MUTED)
    ymax = max(placebo.histogram_counts)
    side = "right" if placebo.plot_value < sum(placebo.histogram_edges) / len(placebo.histogram_edges) else "left"
    _marker(ax, placebo.plot_value, f"Your field {signed(placebo.plot_value)}", ymax * 1.08, SERIES_2, side)
    ax.set_ylim(0, ymax * 1.15)
    ax.set_xlabel(f"{statistic_label(placebo.statistic)} on {placebo.n_placebos} {label}",
                  fontsize=8, color=INK_2)
    ax.set_ylabel("fields", fontsize=8, color=INK_2)
    return _save(fig, path)


def twin_chart(ev: Evidence, path: Path) -> str | None:
    twin = ev.neighbours.counterfactual if ev.neighbours else None
    if twin is None or not twin.series:
        return None
    points = sorted(twin.series, key=lambda p: p.date)
    obs = [(p.date, p.observed) for p in points if p.observed is not None]
    exp = [(p.date, p.expected) for p in points if p.expected is not None]
    if not obs or not exp:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    _style(ax)
    band = [p for p in points if p.expected_low is not None and p.expected_high is not None]
    if band:
        ax.fill_between([p.date for p in band], [p.expected_low for p in band],
                        [p.expected_high for p in band], color=SERIES_2, alpha=0.14, linewidth=0)
    ax.plot(*zip(*exp, strict=True), color=SERIES_2, linewidth=2, marker="o", markersize=4,
            label="Field twin (expected)")
    ax.plot(*zip(*obs, strict=True), color=SERIES_1, linewidth=2, marker="o", markersize=4,
            label="Your field (observed)")
    ax.legend(frameon=False, fontsize=8, loc="best")
    ax.set_ylabel("NDVI", fontsize=8, color=INK_2)
    ax.axvline(ev.event.date, color=INK_2, linewidth=1, linestyle="--")
    ax.annotate(f"event {ev.event.date:%-d %b}", xy=(ev.event.date, ax.get_ylim()[1]), xytext=(3, -2),
                textcoords="offset points", fontsize=8, color=INK_2, va="top")
    fig.autofmt_xdate(rotation=0, ha="center")
    ax.xaxis.set_major_locator(matplotlib.dates.AutoDateLocator(maxticks=6))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%-d %b"))
    return _save(fig, path)


def weather_strip(ev: Evidence, path: Path) -> str | None:
    w = ev.weather
    if w is None:
        return None
    days = [d for d in w.days if d.precip_mm is not None]
    if not days:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 1.9))
    _style(ax)
    ax.bar([d.date for d in days], [d.precip_mm for d in days], width=0.8, color=SERIES_1, linewidth=0)
    top = max(max(d.precip_mm for d in days), 1.0)
    ax.set_ylim(0, top * 1.25)
    ax.axvline(ev.event.date, color=INK_2, linewidth=1, linestyle="--")
    ax.annotate(f"event {ev.event.date:%-d %b}", xy=(ev.event.date, top * 1.22), xytext=(3, 0),
                textcoords="offset points", fontsize=8, color=INK_2, va="top")
    ax.set_ylabel("mm/day, model-indicated", fontsize=8, color=INK_2)
    ax.xaxis.set_major_locator(matplotlib.dates.AutoDateLocator(maxticks=7))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%-d %b"))
    return _save(fig, path)


def draw_histogram(draw: SurveyLottery | None, path: Path) -> str | None:
    if draw is None or not draw.histogram_counts or draw.insufficient_reason:
        return None
    fig, ax = plt.subplots(figsize=(6.4, 2.5))
    _style(ax)
    _histogram(draw.histogram_edges, draw.histogram_counts, ax, SERIES_1)
    ymax = max(draw.histogram_counts)
    ax.set_ylim(0, ymax * 1.15)
    if draw.plot_value is not None:
        _marker(ax, draw.plot_value, f"Your field {signed(draw.plot_value)}", ymax * 1.12, SERIES_2,
                "right")
    ax.set_xlabel(f"{statistic_label(draw.statistic)}: average of {draw.parcels_per_survey} random "
                  f"parcels, {draw.n_simulations} simulated draws", fontsize=8, color=INK_2)
    ax.set_ylabel("draws", fontsize=8, color=INK_2)
    return _save(fig, path)


def scale_chart(fade: ScaleFade | None, path: Path) -> str | None:
    if fade is None:
        return None
    levels = [x for x in fade.levels if x.plot_cell_value is not None]
    if len(levels) < 2:
        return None
    labels = [f"{x.block_m} m" if x.block_m < 1000 else f"{x.block_m / 1000:g} km" for x in levels]
    values = [x.plot_cell_value for x in levels]
    fig, ax = plt.subplots(figsize=(6.4, 2.2))
    _style(ax)
    bars = ax.bar(labels, values, width=0.5, color=SERIES_1, linewidth=0)
    ax.axhline(0, color=MUTED, linewidth=1)
    for bar, value in zip(bars, values, strict=True):
        ax.annotate(f"{value:+.2f}", xy=(bar.get_x() + bar.get_width() / 2, value),
                    xytext=(0, 3 if value >= 0 else -3), textcoords="offset points", ha="center",
                    va="bottom" if value >= 0 else "top", fontsize=8, color=INK)
    span = max(abs(v) for v in values) or 1.0
    ax.set_ylim(min(0, min(values)) - span * 0.2, max(0, max(values)) + span * 0.2)
    ax.set_ylabel(statistic_label(fade.statistic), fontsize=8, color=INK_2)
    return _save(fig, path)


def plot_map(ev: Evidence, chip_path: Path | None, bounds, path: Path) -> str | None:
    """The plot outline, drawn over the post-event true-colour chip when there is one."""
    geometry = ev.plot.geometry
    ring = (geometry.get("coordinates") or [[]])[0]
    if not ring:
        return None
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    ax.set_aspect(1 / max(0.2, abs(math.cos(math.radians(ev.plot.centroid[1])))))
    if chip_path is not None and chip_path.is_file() and bounds is not None:
        image = plt.imread(chip_path)
        west, south, east, north = bounds
        ax.imshow(image, extent=(west, east, south, north), interpolation="nearest",
                  aspect=ax.get_aspect())
    else:
        pad = max(max(xs) - min(xs), max(ys) - min(ys), 0.002) * 0.6
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)
        ax.set_facecolor("#f5f4f0")
    ax.plot(xs, ys, color=SERIES_2, linewidth=2)
    ax.tick_params(colors=INK_2, labelsize=7, length=0)
    ax.ticklabel_format(useOffset=False)
    ax.locator_params(nbins=3)
    return _save(fig, path)
