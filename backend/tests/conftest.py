"""Test helpers. Fake geo and evidence builders live here only, never in the running app."""
from __future__ import annotations

import sys
import types
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from app.evidence.schema import (
    Alert,
    Counterfactual,
    CounterfactualPoint,
    EventInfo,
    Evidence,
    HistoryEvidence,
    HistoryYear,
    NeighbourEvidence,
    OpticalEvidence,
    PlaceboTest,
    PlotInfo,
    PlotStats,
    SarEvidence,
    SceneQA,
    WeatherDay,
    WeatherEvidence,
)

EVENT = date(2026, 10, 25)
PRE_ID, POST_ID = "S2_PRE", "S2_POST"


@pytest.fixture(autouse=True)
def isolated_app(tmp_path, monkeypatch, request):
    """Every test gets its own database and artifacts dir. No test touches backend/var/, and unless
    it is marked live no test reaches a real server: the app's startup would otherwise hit SACHET,
    whose rate limit is shared with the running demo."""
    if not request.node.get_closest_marker("live"):
        def blocked(self, req):
            raise httpx.ConnectError(f"real network is blocked in tests: {req.url}")

        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setenv("VAR_DIR", str(tmp_path / "var"))
    monkeypatch.setenv("ENABLE_SCHEDULER", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app import config, db

    config.get_settings.cache_clear()
    db.init_db(f"sqlite:///{tmp_path / 'test.db'}")
    yield
    config.get_settings.cache_clear()


def stats(scene_id, when, ndvi, valid=0.98):
    return PlotStats(scene_id=scene_id, date=when, valid_frac=valid, n_pixels=200, ndvi_median=ndvi,
                     ndvi_p25=ndvi - 0.05, ndvi_p75=ndvi + 0.05)


def placebo(p=0.02, n=200, k=3, plot_value=-0.25, reason=None):
    return PlaceboTest(
        n_placebos=n, n_at_least_as_extreme=k, p_value=p, statistic="median_delta_ndvi",
        plot_value=plot_value, placebo_median=-0.03, placebo_p05=-0.15, placebo_p95=0.05,
        histogram_edges=[-0.3, -0.2, -0.1, 0.0, 0.1], histogram_counts=[3, 20, 120, 57], seed=7,
        insufficient_reason=reason,
    )


def qa(scene_id, when, status="accepted", reasons=()):
    return SceneQA(id=scene_id, collection="sentinel-2-l2a", date=when, status=status,
                   reasons=list(reasons), metadata_cloud_pct=2.0, plot_valid_frac=0.98,
                   context_ndvi_median=0.5)


def weather(corroborated=True, max_mm=25.0, proposed=None, hail=0, gust=30.0):
    return WeatherEvidence(
        source="Open-Meteo historical-forecast API (model-indicated)",
        fetched_at=datetime(2026, 10, 31, tzinfo=UTC), grid_note="note",
        days=[WeatherDay(date=EVENT + timedelta(days=i), precip_mm=float(i + 3)) for i in range(-2, 3)],
        precip_mm_event_window=max_mm + 5, max_daily_mm=max_mm, hail_code_hours=hail,
        thunder_hours=hail, max_gust_kmh=gust, corroborated=corroborated, proposed_event_date=proposed,
    )


def evidence(
    *, delta=-0.25, pre_ndvi=0.7, post_ndvi=0.45, p=None, pre_status="accepted",
    post_status="accepted", bare=0.1, pattern="patchy", neighbour_bare=0.1, history=None,
    sar=None, wx=None, alerts=(), area=1.5, post_valid=0.98, optical=True, cross=None,
    far=None, pretrend=None,
) -> Evidence:
    p = p if p is not None else placebo()
    pre_date, post_date = EVENT - timedelta(days=7), EVENT + timedelta(days=5)
    opt = OpticalEvidence()
    neighbours = None
    if optical:
        opt = OpticalEvidence(
            scenes_considered=[qa(PRE_ID, pre_date, pre_status), qa(POST_ID, post_date, post_status)],
            pre=stats(PRE_ID, pre_date, pre_ndvi),
            post=stats(POST_ID, post_date, post_ndvi, valid=post_valid),
            plot_delta_ndvi=delta, drop_frac=0.6, iqr_delta=0.15, within_plot_pattern=pattern,
            post_bare_fraction=bare,
        )
        neighbours = NeighbourEvidence(
            n_comparable_pixels=5000, neighbour_median_delta=-0.03, plot_minus_neighbour=delta + 0.03,
            neighbour_bare_fraction_post=neighbour_bare, placebo=p, far_placebo=far,
            pretrend_delta=pretrend,
            counterfactual=Counterfactual(
                n_control_pixels=800, pre_fit_rmse=0.02, gap_at_post=-0.2, method="test",
                series=[CounterfactualPoint(date=pre_date, observed=pre_ndvi, expected=pre_ndvi),
                        CounterfactualPoint(date=post_date, observed=post_ndvi, expected=pre_ndvi - 0.03)],
            ),
        )
    ev = Evidence(
        case_id="c", run_id="r", created_at=datetime(2026, 10, 31, tzinfo=UTC),
        plot=PlotInfo(geometry={"type": "Polygon", "coordinates": [[[75.03, 29.53], [75.04, 29.53],
                                                                    [75.04, 29.54], [75.03, 29.53]]]},
                      area_ha=area, centroid=(75.035, 29.535), crs="EPSG:32643"),
        event=EventInfo(type="hail", date=EVENT, crop="cotton"),
        optical=opt, neighbours=neighbours, history=history, sar=sar,
        weather=wx if wx is not None else weather(),
        alerts=list(alerts),
    )
    if cross is not None:
        ev.cross_examination = cross
    else:
        from app.agent import cross_exam

        ev.cross_examination, _ = cross_exam.run(ev)
    return ev


def sar_evidence(p=0.02, usable=True, water=0.0, n=200):
    return SarEvidence(
        pre_scene_id="S1_PRE", post_scene_id="S1_POST", pre_date=EVENT - timedelta(days=9),
        post_date=EVENT + timedelta(days=3), orbit_direction="ascending", relative_orbit=100,
        vh_change_db=-2.0, vh_excess_db=-1.8, new_water_frac=water, usable=usable,
        placebo=placebo(p=p, n=n),
    )


def history_ok(excess=-0.2, typical=-0.05, down=False):
    return HistoryEvidence(
        years=[HistoryYear(year=2025, pre_scene_id="h1", post_scene_id="h2", pre_ndvi=0.68, delta_ndvi=typical),
               HistoryYear(year=2024, pre_scene_id="h3", post_scene_id="h4", pre_ndvi=0.66, delta_ndvi=typical)],
        typical_delta=typical, excess_vs_history=excess, downweighted=down,
    )


def an_alert():
    return Alert(source="NDMA SACHET", identifier="1", area="Sirsa district", headline="Hail warning")


class FakeScene(types.SimpleNamespace):
    pass


def scene(scene_id, when, collection="sentinel-2-l2a", orbit=None, rel=None):
    return FakeScene(id=scene_id, date=when, collection=collection, cloud_pct=2.0, orbit_state=orbit,
                     relative_orbit=rel, datetime=datetime.combine(when, datetime.min.time(), UTC))


def install_fake_geo(monkeypatch, **overrides):
    """A stand-in for app.tools.geo, driven by test values. Never importable by the running app."""
    pre_date, post_date = EVENT - timedelta(days=7), EVENT + timedelta(days=5)
    base = evidence(cross=[])

    def plot_info(polygon):
        if polygon is None:
            raise ValueError("no plot")
        return base.plot.model_copy(update={"geometry": polygon})

    defaults = {
        "ENGINE_VERSION": "test-1",
        "plot_info": plot_info,
        "search_optical": lambda *a, **k: [scene(PRE_ID, pre_date), scene(POST_ID, post_date)],
        "qa_scene": lambda sc, *a, **k: qa(sc.id, sc.date),
        "optical_compare": lambda *a, **k: (base.optical, base.neighbours),
        "search_sar": lambda *a, **k: [scene("S1_PRE", EVENT - timedelta(days=9), orbit="ascending", rel=100),
                                    scene("S1_POST", EVENT + timedelta(days=3), orbit="ascending", rel=100)],
        "sar_compare": lambda *a, **k: sar_evidence(),
        "history": lambda *a, **k: history_ok(),
        "history_scene_ids": lambda h: ["h1", "h2", "h3", "h4"],
        "scene_archive": lambda sid: "earth-search" if sid.endswith("_L2A") else "planetary-computer",
        "timeline": lambda *a, **k: [],
        "render_chips": lambda *a, **k: [],
        "flatten_numbers": lambda *a, **k: {"optical.plot_delta_ndvi": -0.25},
        "replay": lambda core: dict(core.numbers),
    }
    defaults.update(overrides)
    module = types.ModuleType("app.tools.geo")
    module.__dict__.update(defaults)
    monkeypatch.setitem(sys.modules, "app.tools.geo", module)
    import app.tools

    monkeypatch.setattr(app.tools, "geo", module, raising=False)
    return module


@pytest.fixture
def fake_weather(monkeypatch):
    from app.tools import alerts
    from app.tools import weather as weather_tool

    monkeypatch.setattr(weather_tool, "fetch_weather", lambda *a, **k: weather())
    monkeypatch.setattr(alerts, "locate", lambda *a, **k: {"district": "Sirsa", "state": "Haryana"})
    return weather_tool
