"""The API and the run lifecycle with a fake geo module and no external calls: failures included."""
import json
import threading
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import EVENT, POST_ID, PRE_ID, install_fake_geo, qa, sar_evidence, scene

SQUARE = {"type": "Polygon", "coordinates": [[[75.03, 29.53], [75.0314, 29.53], [75.0314, 29.5314],
                                              [75.03, 29.5314], [75.03, 29.53]]]}


@pytest.fixture
def client(fake_weather):
    from app import main

    with TestClient(main.app) as c:
        yield c


def new_case(client, text="25 Oct hail cotton", **extra):
    r = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "lang": "en", "text": text, **extra})
    assert r.status_code == 200, r.text
    case_id = r.json()["case_id"]
    assert client.put(f"/api/cases/{case_id}/plot", json={"polygon": SQUARE}).status_code == 200
    return case_id


def wait_done(client, run_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        events = stream(client, run_id)
        if events and events[-1]["type"] == "done":
            return events
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def stream(client, run_id, after=0):
    with client.stream("GET", f"/api/runs/{run_id}/stream?after={after}") as response:
        assert response.status_code == 200
        return [json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")]


def test_health_without_a_key(client):
    assert client.get("/api/health").json() == {"status": "ok", "gemini": False, "version": "0.1.0"}


def test_text_only_case_and_needs(client):
    r = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "text": "ओले गिरे"}).json()
    assert r["parsed"]["event_type"] == "hail"
    assert set(r["needs"]) == {"crop", "event_date", "insured", "crop_stage", "plot"}
    assert r["questions"]["insured"]["hi"]


def test_audio_without_a_key_returns_needs_not_failure(client):
    r = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03},
                    files={"audio": ("a.webm", b"\x00\x01", "audio/webm")})
    assert r.status_code == 200 and "transcript" in r.json()["needs"]


def test_bad_pin_and_bad_polygon(client):
    assert client.post("/api/cases", data={"lat": 15, "lon": 65}).status_code == 422
    case_id = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03}).json()["case_id"]
    bad = {"type": "Polygon", "coordinates": [[[75, 29], [75.01, 29.01], [75.01, 29], [75, 29.01], [75, 29]]]}
    r = client.put(f"/api/cases/{case_id}/plot", json={"polygon": bad})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "polygon_self_intersecting"


def test_investigate_needs_a_plot(client):
    case_id = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03}).json()["case_id"]
    r = client.post(f"/api/cases/{case_id}/investigate")
    assert r.status_code == 422 and r.json()["detail"]["needs"] == ["plot"]


def test_patch_validates_and_clears_needs(client):
    case_id = new_case(client)
    assert client.patch(f"/api/cases/{case_id}", json={"event_type": "meteor"}).status_code == 422
    assert client.patch(f"/api/cases/{case_id}", json={"event_time": "25:00"}).status_code == 422
    future = (date.today() + timedelta(days=5)).isoformat()
    assert client.patch(f"/api/cases/{case_id}", json={"event_date": future}).status_code == 422
    assert client.patch(f"/api/cases/{case_id}", json={"insured": "maybe"}).status_code == 422
    r = client.patch(f"/api/cases/{case_id}", json={"insured": "yes", "crop_stage": "standing"})
    assert r.status_code == 200 and r.json()["needs"] == []


def test_submission_requires_a_reference(client):
    case_id = new_case(client)
    for body in ({"channel": "14447"}, {"channel": "14447", "reference_no": "   "}):
        assert client.post(f"/api/cases/{case_id}/submission", json=body).status_code == 422
    assert client.get(f"/api/cases/{case_id}").json()["case"]["status"] != "submitted"
    r = client.post(f"/api/cases/{case_id}/submission", json={"channel": "14447", "reference_no": "R1"})
    assert r.status_code == 200 and r.json()["status"] == "submitted"


def test_unknown_ids(client):
    assert client.get("/api/cases/nope").status_code == 404
    assert client.get("/api/runs/nope/stream").status_code == 404
    assert client.get("/api/artifacts/..%2F..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert client.get("/api/nope").status_code == 404


def test_ask_refuses_out_of_scope(client):
    case_id = new_case(client)
    r = client.post(f"/api/cases/{case_id}/ask", json={"question": "capital of France?", "lang": "en"})
    assert r.json()["covered"] is False


def test_full_run_on_the_no_key_path(client, monkeypatch):
    install_fake_geo(monkeypatch)
    case_id = new_case(client, insured="yes", crop_stage="standing")
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    kinds = {e["type"] for e in events}
    assert {"tool_called", "tool_result", "objection", "verdict", "done"} <= kinds
    assert [e["detail"]["id"] for e in events if e["type"] == "objection"][:8] == [
        "harvest", "wrong_plot", "wrong_date", "cloud_shadow", "corrupt_scene", "regional_trend",
        "too_small", "stale_crop"]
    assert all(e["title_hi"] and e["title_en"] for e in events)
    assert events[-1]["detail"]["status"] == "done"

    body = client.get(f"/api/cases/{case_id}").json()
    ev = body["evidence"]
    assert ev["verdict"]["level"] == "strong" and ev["llm_used"] is False
    assert ev["evidence_hash"] and ev["replay"]["numbers"]
    assert ev["explanation_hi"] and ev["explanation_en"] and ev["testimony_hi"]
    assert ev["verdict"]["headline_te"]
    assert ev["claim_path"]["route"] == "localized_addon"
    types = {a["type"] for a in body["actions"]}
    assert "intimation_draft" in types and "submission" not in types
    draft = next(a for a in body["actions"] if a["type"] == "intimation_draft")["payload"]
    assert draft["filed"] is False and draft["whatsapp_url_en"].startswith("https://wa.me/?text=")
    assert "CSC" not in json.dumps(draft) and "Aadhaar" not in json.dumps(draft)
    assert ev["evidence_hash"] in draft["text_en"]
    assert draft["deadline_status"] in ("open", "lapsed")
    client.post(f"/api/cases/{case_id}/submission", json={"channel": "14447", "reference_no": "R1"})
    after = client.get(f"/api/cases/{case_id}").json()
    draft = next(a for a in after["actions"] if a["type"] == "intimation_draft")["payload"]
    assert draft["filed"] is True and after["case"]["status"] == "submitted"


def test_replay_from_any_seq(client, monkeypatch):
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    middle = len(events) // 2
    assert [e["seq"] for e in stream(client, run_id, after=middle)] == [e["seq"] for e in events[middle:]]


def test_double_investigate_returns_the_same_run(client, monkeypatch):
    release = threading.Event()

    def slow(*a, **k):
        release.wait(10)
        return []

    install_fake_geo(monkeypatch, search_optical=slow)
    case_id = new_case(client)
    first = client.post(f"/api/cases/{case_id}/investigate").json()
    second = client.post(f"/api/cases/{case_id}/investigate").json()
    assert first["run_id"] == second["run_id"] and second["created"] is False
    # The plot cannot change under a running investigation.
    assert client.put(f"/api/cases/{case_id}/plot", json={"polygon": SQUARE}).status_code == 409
    release.set()
    wait_done(client, first["run_id"])
    third = client.post(f"/api/cases/{case_id}/investigate").json()
    assert third["run_id"] != first["run_id"]
    wait_done(client, third["run_id"])


def test_rejected_post_switches_to_radar(client, monkeypatch):
    def qa_fn(sc, *a, **k):
        if sc.id == POST_ID:
            return qa(sc.id, sc.date, "rejected", ["Q3: infrared band (B08) is empty"])
        return qa(sc.id, sc.date)

    install_fake_geo(monkeypatch, qa_scene=qa_fn, optical_compare=lambda *a, **k: pytest.fail("must not run"))
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    assert any(e["type"] == "scene_rejected" for e in events)
    assert any(e["type"] == "sensor_switch" for e in events)
    level = client.get(f"/api/cases/{case_id}").json()["evidence"]["verdict"]["level"]
    assert level == "moderate"  # radar placebo plus weather, and radar alone never exceeds this


def test_satellite_outage_gives_partial_evidence_and_a_recheck(client, monkeypatch):
    def down(*a, **k):
        raise RuntimeError("Planetary Computer timed out")

    install_fake_geo(monkeypatch, search_optical=down, search_sar=down, timeline=down)
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    assert events[-1]["detail"]["status"] == "done"
    assert any(e["type"] == "warning" for e in events)
    body = client.get(f"/api/cases/{case_id}").json()
    assert body["evidence"]["verdict"]["level"] == "insufficient"
    assert body["evidence"]["weather"] is not None
    assert any(a["type"] == "recheck" for a in body["actions"])
    assert any(d["type"] == "recheck" and d["basis"] == "archive-retry"
               for d in body["evidence"]["deadlines"])
    assert "could not be reached" in body["evidence"]["verdict"]["reasons"][0]
    assert "not responding" in body["evidence"]["explanation_en"]


def test_weather_outage_does_not_refute(client, monkeypatch):
    from app.tools import weather

    def down(*a, **k):
        raise weather.WeatherUnavailable("both down")

    monkeypatch.setattr(weather, "fetch_weather", down)
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    wait_done(client, run_id)
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["weather"] is None
    wrong_date = next(o for o in ev["cross_examination"] if o["id"] == "wrong_date")
    assert wrong_date["outcome"] == "unresolved" and ev["verdict"]["level"] == "moderate"


def test_cloudy_post_loops_to_another_scene(client, monkeypatch):
    from tests import conftest

    later = EVENT + timedelta(days=10)
    clean = conftest.evidence(cross=[])
    cloudy = conftest.evidence(post_valid=0.6, cross=[])
    calls = []

    def compare(polygon, pre, post, seed):
        calls.append(post)
        return (cloudy if post == POST_ID else clean).optical, clean.neighbours

    install_fake_geo(
        monkeypatch, optical_compare=compare,
        search_optical=lambda *a, **k: [scene(PRE_ID, EVENT - timedelta(days=7)),
                                        scene(POST_ID, EVENT + timedelta(days=5)),
                                        scene("S2_LATER", later)],
    )
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    assert calls == [POST_ID, "S2_LATER"]
    assert any(e["detail"].get("action") == "exclude_scene" for e in events if e["type"] == "decision")


def test_wrong_date_reruns_on_the_proposed_date_and_keeps_the_farmers_date(client, monkeypatch):
    from app.tools import weather as weather_tool
    from tests import conftest

    proposed = EVENT - timedelta(days=4)

    def fetch(lat, lon, when, *a, **k):
        if when == EVENT:
            return conftest.weather(corroborated=False, max_mm=0.2, proposed=proposed)
        return conftest.weather(corroborated=True, max_mm=33.0)

    monkeypatch.setattr(weather_tool, "fetch_weather", fetch)
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    assert any(e["detail"].get("action") == "redate" for e in events)
    body = client.get(f"/api/cases/{case_id}").json()
    assert body["evidence"]["event"]["date"] == proposed.isoformat()
    assert body["evidence"]["event"]["date_source"] == "weather_proposed"
    assert body["case"]["event_date"] == EVENT.isoformat()
    assert body["case"]["proposed_event_date"] == proposed.isoformat()


def test_budget_is_never_exceeded(client, monkeypatch):
    from tests import conftest

    cloudy = conftest.evidence(post_valid=0.6, cross=[])
    install_fake_geo(
        monkeypatch, optical_compare=lambda *a, **k: (cloudy.optical, cloudy.neighbours),
        search_optical=lambda *a, **k: [scene(PRE_ID, EVENT - timedelta(days=7))]
        + [scene(f"S{i}", EVENT + timedelta(days=i)) for i in range(1, 9)],
    )
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    assert events[-1]["detail"]["calls_used"] <= 12
    assert events[-1]["detail"]["status"] == "done"


def test_crash_inside_a_node_still_ends_with_done(client, monkeypatch):
    from app.agent import cross_exam

    def explode(*a, **k):
        raise ValueError("boom")

    monkeypatch.setattr(cross_exam, "run", explode)
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    events = wait_done(client, run_id)
    assert any(e["type"] == "error" for e in events) and events[-1]["type"] == "done"
    assert client.get(f"/api/cases/{case_id}").json()["evidence"]["verdict"]


def test_restart_closes_interrupted_runs(client, monkeypatch):
    from app.agent import runner
    from app.db import Run, session_scope

    case_id = new_case(client)
    with session_scope() as s:
        s.add(Run(id="stuck", case_id=case_id, status="running"))
    assert runner.recover_interrupted() == 1
    assert stream(client, "stuck")[-1]["detail"]["status"] == "interrupted"


def test_chip_paths_become_relative_and_artifacts_are_served(client, monkeypatch, tmp_path):
    from app.config import get_settings
    from app.evidence.schema import Chip

    def chips(polygon, pre, post, out_dir, *a):
        from pathlib import Path

        path = Path(out_dir) / "true_colour_post.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG")
        return [Chip(kind="true_colour_post", path=str(path), scene_id=post)]

    install_fake_geo(monkeypatch, render_chips=chips)
    case_id = new_case(client)
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    chip = client.get(f"/api/cases/{case_id}").json()["evidence"]["chips"][0]
    assert not chip["path"].startswith("/") and str(get_settings().artifacts_dir) not in chip["path"]
    assert client.get(f"/api/artifacts/{chip['path']}").content == b"\x89PNG"


def test_no_tts_is_a_404(client, monkeypatch):
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert client.get(f"/api/cases/{case_id}/summary.mp3?lang=hi").status_code == 404
    assert client.get(f"/api/cases/{case_id}/summary.mp3?kind=bad").status_code == 422


def test_pdf_in_all_languages(client, monkeypatch):
    install_fake_geo(monkeypatch)
    case_id = new_case(client, insured="yes", crop_stage="standing")
    assert client.get(f"/api/cases/{case_id}/evidence.pdf").status_code == 404
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    for lang in ("hi", "en", "te"):
        r = client.get(f"/api/cases/{case_id}/evidence.pdf?lang={lang}")
        assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert client.get(f"/api/cases/{case_id}/evidence.pdf?lang=xx").status_code == 422


def test_live_route_follows_later_answers_without_a_new_run(client, monkeypatch):
    install_fake_geo(monkeypatch)
    case_id = new_case(client, text="25 Oct cyclone paddy")
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert client.get(f"/api/cases/{case_id}").json()["evidence"]["claim_path"]["route"] == "undetermined"
    client.patch(f"/api/cases/{case_id}", json={"insured": "yes", "crop_stage": "standing"})
    route = client.get(f"/api/cases/{case_id}").json()["evidence"]["claim_path"]
    assert route["route"] == "area_yield_basic" and not route["countdown_applies"]


def test_sar_only_mentions_radar(client, monkeypatch):
    install_fake_geo(monkeypatch, search_optical=lambda *a, **k: [],
                     sar_compare=lambda *a, **k: sar_evidence(p=0.01))
    case_id = new_case(client)
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert "रडार" in client.get(f"/api/cases/{case_id}").json()["evidence"]["testimony_hi"]


def test_no_user_facing_lottery_wording():
    from pathlib import Path

    import app

    root = Path(app.__file__).parent
    texts = [root / "pdf" / "render.py", root / "pdf" / "templates" / "evidence.html.j2"]
    for path in texts:
        assert "lottery" not in path.read_text(encoding="utf-8").replace("village.lottery", "").lower(), path


def _village(**lottery_extra):
    from app.evidence.schema import SurveyDraw, SurveyLottery, VillageWitness

    return VillageWitness(
        radius_m=1500, sensor="s2", n_cropland_pixels=9000, affected_share=0.31,
        affected_definition="change consistent with damage, excluding harvest-like bare soil",
        lottery=SurveyLottery(
            n_simulations=1000, statistic="median_delta_ndvi", plot_value=-0.25, n_candidate_parcels=400,
            average_median=-0.06, average_p05=-0.12, average_p95=-0.01, share_below_half_of_plot=0.82,
            histogram_edges=[-0.15, -0.1, -0.05, 0.0], histogram_counts=[100, 500, 400],
            sample_draws=[SurveyDraw(parcels=[(75.03, 29.53)] * 10, average=-0.05)], seed=7, **lottery_extra,
        ),
    )


def _fade(tmp_path=None):
    from app.evidence.schema import ScaleFade, ScaleLevel

    return ScaleFade(sensor="s2", statistic="delta_ndvi", bounds=(75.0, 29.5, 75.1, 29.6), levels=[
        ScaleLevel(block_m=10, plot_cell_value=-0.3), ScaleLevel(block_m=100, plot_cell_value=-0.22),
        ScaleLevel(block_m=500, plot_cell_value=-0.11), ScaleLevel(block_m=1000, plot_cell_value=-0.06),
        ScaleLevel(block_m=3000, plot_cell_value=-0.03),
    ])


def test_ten_field_draw_on_an_add_on_route(client, monkeypatch):
    install_fake_geo(monkeypatch, village_witness=lambda *a, **k: _village(),
                     scale_fade=lambda *a, **k: _fade())
    other = new_case(client)  # a real nearby case with a date within three days
    case_id = new_case(client, insured="yes", crop_stage="standing")
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    village = client.get(f"/api/cases/{case_id}").json()["evidence"]["village"]
    assert village["lottery"]["rule_applicability"] == "may_apply"
    assert village["nearby_real_cases"] == 1 and other != case_id
    line = next(e for e in events if e["detail"].get("signature") == "ten_field_draw")
    assert "Ten-Field Draw" in line["title_en"] and "दस खेतों का ड्रॉ" in line["title_hi"]
    assert "not the real intimation list" in line["title_en"]
    for event in events:
        text = (event["title_en"] + event["title_hi"] + json.dumps(event["detail"])).lower()
        assert "lottery" not in text and "unfair" not in text
    assert any(e["detail"].get("signature") == "vanishing" and "not output of YES-TECH" in e["title_en"]
               for e in events)
    for lang in ("hi", "en", "te"):
        assert client.get(f"/api/cases/{case_id}/evidence.pdf?lang={lang}").status_code == 200


def test_ten_field_draw_is_an_illustration_on_area_yield(client, monkeypatch):
    install_fake_geo(monkeypatch, village_witness=lambda *a, **k: _village(),
                     scale_fade=lambda *a, **k: _fade())
    case_id = new_case(client, text="25 Oct cyclone paddy", insured="yes", crop_stage="standing")
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["village"]["lottery"]["rule_applicability"] == "illustration_only"
    line = next(e for e in events if e["detail"].get("signature") == "ten_field_draw")
    assert "if it applied here" in line["title_en"]
    # Answering later moves the route, and the applicability moves with it on read.
    client.patch(f"/api/cases/{case_id}", json={"crop_stage": "cut_and_spread"})
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["claim_path"]["route"] == "post_harvest_addon"
    assert ev["village"]["lottery"]["rule_applicability"] == "may_apply"


def test_village_without_geo_exports_is_an_honest_null(client, monkeypatch):
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["village"] is None and ev["scale_fade"] is None
    assert any(e["node"] == "village" and e["type"] == "warning" for e in events)
    assert events[-1]["detail"]["status"] == "done"


def test_village_failure_does_not_lose_the_run(client, monkeypatch):
    def down(*a, **k):
        raise RuntimeError("slow archive")

    install_fake_geo(monkeypatch, village_witness=down, scale_fade=down)
    case_id = new_case(client)
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert events[-1]["detail"]["status"] == "done"
    assert client.get(f"/api/cases/{case_id}").json()["evidence"]["village"] is None


def test_redate_without_a_pair_keeps_the_farmers_evidence(client, monkeypatch):
    from app.tools import weather as weather_tool
    from tests import conftest

    proposed = EVENT + timedelta(days=4)

    def fetch(lat, lon, when, *a, **k):
        if when == EVENT:
            return conftest.weather(corroborated=False, max_mm=0.2, proposed=proposed)
        return conftest.weather(corroborated=True, max_mm=33.0)

    calls = []

    def compare(*a, **k):
        calls.append(a)
        base = conftest.evidence(cross=[])
        return base.optical, base.neighbours

    def search_by_window(polygon, start, end):
        # Before the redate the window opens 25 days before the farmer's date; after, before the new one.
        if start == EVENT - timedelta(days=25):
            return [scene(PRE_ID, EVENT - timedelta(days=7)), scene(POST_ID, EVENT + timedelta(days=2))]
        return [scene(PRE_ID, EVENT - timedelta(days=7))]

    monkeypatch.setattr(weather_tool, "fetch_weather", fetch)
    install_fake_geo(monkeypatch, search_optical=search_by_window, optical_compare=compare,
                     search_sar=lambda *a, **k: [])
    case_id = new_case(client)
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert any(e["detail"].get("action") == "redate_reverted" for e in events)
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["event"]["date"] == EVENT.isoformat() and ev["event"]["date_source"] == "farmer"
    assert ev["optical"]["plot_delta_ndvi"] == -0.25
    wrong_date = next(o for o in ev["cross_examination"] if o["id"] == "wrong_date")
    assert wrong_date["outcome"] == "conceded"
    assert len(calls) == 1
