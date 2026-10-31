"""Scheduled re-checks, deadline upkeep, the planner's use of the LLM, and the radar's cells."""
from datetime import UTC, datetime, timedelta

import pytest

from app.agent import llm
from app.db import Action, Case, Plot, Run, session_scope
from app.tools import weather
from tests import conftest
from tests.conftest import EVENT, POST_ID, PRE_ID, install_fake_geo, qa, scene
from tests.test_api import SQUARE, client, new_case, wait_done  # noqa: F401


def _first_run(client, monkeypatch, **overrides):  # noqa: F811
    install_fake_geo(monkeypatch, **overrides)
    case_id = new_case(client)
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    with session_scope() as s:
        for action in s.query(Action).filter_by(case_id=case_id, type="recheck").all():
            action.due_at = datetime.now(UTC) - timedelta(minutes=1)
    return case_id


def _runs(case_id, trigger="scheduler"):
    with session_scope() as s:
        return [r.id for r in s.query(Run).filter_by(case_id=case_id, trigger=trigger).all()]


def _make_due(case_id):
    with session_scope() as s:
        action = s.scalar(select(Action).where(Action.case_id == case_id, Action.type == "recheck"))
        action.due_at = datetime.now(UTC) - timedelta(minutes=1)


def test_recheck_waits_for_a_new_accepted_scene(client, monkeypatch):  # noqa: F811
    from app import jobs

    def reject_post(sc, *a, **k):
        return qa(sc.id, sc.date, "rejected", ["Q3: bad"]) if sc.id == POST_ID else qa(sc.id, sc.date)

    case_id = _first_run(client, monkeypatch, qa_scene=reject_post,
                         search_sar=lambda *a, **k: [])
    assert jobs.recheck_open_cases()["started"] == []  # no new scene yet
    assert jobs.recheck_open_cases()["checked"] == 0  # and it waits its turn before asking again
    _make_due(case_id)

    later = scene("S2_NEW", EVENT + timedelta(days=12))

    def compare(polygon, pre, post, seed):
        base = conftest.evidence(cross=[])
        base.optical.post = conftest.stats(post, later.date, 0.45)
        return base.optical, base.neighbours

    install_fake_geo(monkeypatch, search_sar=lambda *a, **k: [], optical_compare=compare,
                     search_optical=lambda *a, **k: [scene(PRE_ID, EVENT - timedelta(days=7)),
                                                     scene(POST_ID, EVENT + timedelta(days=5)), later],
                     qa_scene=reject_post)
    report = jobs.recheck_open_cases()
    assert [s["scene"] for s in report["started"]] == ["S2_NEW"]
    wait_done(client, report["started"][0]["run_id"])
    assert len(_runs(case_id)) == 1
    level = client.get(f"/api/cases/{case_id}").json()["evidence"]["verdict"]["level"]
    assert level != "insufficient"


def test_slow_archive_retries_without_waiting_for_a_new_scene(client, monkeypatch):  # noqa: F811
    from app import jobs

    def down(*a, **k):
        raise RuntimeError("archive timed out")

    case_id = _first_run(client, monkeypatch, optical_compare=down, search_sar=lambda *a, **k: [])
    assert "did not finish" in client.get(f"/api/cases/{case_id}").json()["evidence"]["verdict"]["reasons"][0]
    install_fake_geo(monkeypatch)
    report = jobs.recheck_open_cases()
    assert [s["scene"] for s in report["started"]] == [None]
    wait_done(client, report["started"][0]["run_id"])
    assert client.get(f"/api/cases/{case_id}").json()["evidence"]["verdict"]["level"] == "strong"


def test_recheck_outage_is_reported_and_harmless(client, monkeypatch):  # noqa: F811
    from app import jobs

    def reject_post(sc, *a, **k):
        return qa(sc.id, sc.date, "rejected", ["Q3: bad"]) if sc.id == POST_ID else qa(sc.id, sc.date)

    case_id = _first_run(client, monkeypatch, qa_scene=reject_post, search_sar=lambda *a, **k: [])

    def down(*a, **k):
        raise RuntimeError("archive down")

    install_fake_geo(monkeypatch, search_optical=down)
    report = jobs.recheck_open_cases()
    assert report["started"] == [] and report["errors"][0]["case_id"] == case_id


def test_archive_outage_on_the_first_run_retries_soon(client, monkeypatch):  # noqa: F811
    from app import jobs

    def down(*a, **k):
        raise RuntimeError("archive down")

    _first_run(client, monkeypatch, search_optical=down, search_sar=down)
    install_fake_geo(monkeypatch)
    report = jobs.recheck_open_cases()
    assert [s["scene"] for s in report["started"]] == [None]
    wait_done(client, report["started"][0]["run_id"])


def test_tick_reports_each_job_and_survives_a_feed_outage(client, monkeypatch):  # noqa: F811
    from app import jobs

    report = jobs.tick()
    assert "error" in report["alerts"] and "rechecks" in report and "deadlines" in report


def test_tick_route_checks_the_token(client, monkeypatch):  # noqa: F811
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "scheduler_token", "secret")
    assert client.post("/api/jobs/tick").status_code == 403
    assert client.post("/api/jobs/tick", headers={"X-Scheduler-Token": "secret"}).status_code == 200


def test_scheduler_starts_and_stops():
    from app import jobs

    stop = jobs.start_scheduler()
    stop()


def test_deadline_upkeep_moves_status_with_the_route(client, monkeypatch):  # noqa: F811
    from app import jobs

    case_id = new_case(client, text="25 Oct hail cotton")
    client.patch(f"/api/cases/{case_id}", json={
        "insured": "yes", "crop_stage": "standing",
        "event_date": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
    })
    jobs.update_deadlines()
    assert client.get(f"/api/cases/{case_id}").json()["case"]["status"] == "intimation_due"
    client.patch(f"/api/cases/{case_id}", json={"insured": "no"})
    jobs.update_deadlines()
    assert client.get(f"/api/cases/{case_id}").json()["case"]["status"] == "open"


def _planned(monkeypatch, name, args=None):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "plan", lambda ctx, opts: llm.PlanChoice(name, args or {}, "reason"))
    for attr in ("narrate", "translate", "rephrase_challenges"):
        monkeypatch.setattr(llm, attr, lambda *a, **k: None)
    monkeypatch.setattr(llm, "_plain_text", lambda *a, **k: None)
    monkeypatch.setattr(llm, "grounded_sources", lambda *a, **k: None)


def test_planner_vetoed_on_a_hail_report_with_no_weather(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LLM_PLANNER", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(weather, "fetch_weather", lambda *a, **k: conftest.weather(corroborated=False, max_mm=0.1))
    _planned(monkeypatch, "sar_first")
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    veto = next(e for e in events if e["node"] == "planner")
    assert veto["detail"]["veto"] and veto["detail"]["suggested"] == "sar_first"
    assert not any(e["type"] == "sensor_switch" for e in events)


def test_planner_allowed_on_a_cyclone_goes_to_radar_first(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LLM_PLANNER", "true")
    get_settings.cache_clear()
    _planned(monkeypatch, "sar_first")
    install_fake_geo(monkeypatch)
    case_id = new_case(client, text="25 Oct cyclone paddy")
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert any(e["type"] == "sensor_switch" for e in events)
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["llm_used"] is True and ev["sar"] is not None


def test_planner_window_is_clamped(client, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LLM_PLANNER", "true")
    get_settings.cache_clear()
    _planned(monkeypatch, "search_optical", {"post_window_days": 400})
    seen = []

    def search(polygon, start, end):
        seen.append((start, end))
        return []

    install_fake_geo(monkeypatch, search_optical=search)
    case_id = new_case(client)
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert seen[0][1] <= EVENT + timedelta(days=30)


def _radar_payload(days, rain, codes=None, gust=None):
    times = [d.isoformat() for d in days]
    return {
        "daily": {"time": times, "precipitation_sum": rain, "weather_code": [0] * len(days),
                  "wind_gusts_10m_max": [gust] * len(days)},
        "hourly": {"time": [f"{t}T12:00" for t in times], "weather_code": codes or [0] * len(days)},
    }


def test_radar_cell_counts_hours_from_the_start_of_the_heavy_day():
    now = datetime(2026, 10, 31, 12, tzinfo=weather.IST)
    days = [now.date() - timedelta(days=i) for i in (3, 2, 1, 0)]
    cell = weather._radar_cell(("X", "Y", 1.0, 2.0), _radar_payload(days, [0, 40.0, 0, 0]), now)
    assert cell["heavy_date"] == days[1].isoformat() and cell["hours_left"] == pytest.approx(12.0)


def test_radar_ignores_quiet_cells_and_closed_windows():
    now = datetime(2026, 10, 31, 12, tzinfo=weather.IST)
    days = [now.date() - timedelta(days=i) for i in (3, 2, 1, 0)]
    assert weather._radar_cell(("X", "Y", 1, 2), _radar_payload(days, [0, 1.0, 0, 0]), now) is None
    assert weather._radar_cell(("X", "Y", 1, 2), _radar_payload(days, [40.0, 0, 0, 0]), now) is None


def test_radar_hail_code_counts():
    now = datetime(2026, 10, 31, 12, tzinfo=weather.IST)
    days = [now.date() - timedelta(days=i) for i in (3, 2, 1, 0)]
    cell = weather._radar_cell(("X", "Y", 1, 2), _radar_payload(days, [0, 0, 0, 0], codes=[0, 0, 96, 0]), now)
    assert cell["hail_code_hours"] == 1 and cell["precip_mm"] == 0


def test_radar_without_data_raises_and_with_old_data_says_stale(monkeypatch):
    def down():
        raise weather.httpx.ConnectError("down")

    monkeypatch.setattr(weather, "_fetch_radar", down)
    with pytest.raises(weather.WeatherUnavailable):
        weather.radar()
    from app.db import cache_put

    cache_put("radar:india:v1", "open-meteo", None, [])
    with session_scope() as s:
        from app.db import ApiCache

        s.get(ApiCache, "radar:india:v1").fetched_at = datetime.now(UTC) - timedelta(hours=2)
    assert weather.radar()["stale"] is True


def test_models_cover_the_plan(client):  # noqa: F811
    with session_scope() as s:
        assert s.query(Case).count() == 0 and s.query(Plot).count() == 0
    assert SQUARE["type"] == "Polygon"
