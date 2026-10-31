"""The warm script against a local test app and fake geo. No real archive is reached."""
import json

import pytest
from fastapi.testclient import TestClient

from app import disclosures
from app.agent.graph import evidence_hash, make_seed
from app.evidence.schema import ReplayCore
from scripts import warm_demo
from tests.conftest import evidence, install_fake_geo
from tests.geo_fpr_sirsa import square as validated_square

BY_NAME = {p.name: p for p in warm_demo.PLOTS}


@pytest.fixture
def client(fake_weather):
    from app import main

    with TestClient(main.app) as c:
        yield c


def fake_geo_on_real_plot(monkeypatch, **overrides):
    """Fake numbers, but the plot info follows the polygon that actually arrived."""
    def plot_info(polygon):
        ring = polygon["coordinates"][0][:-1]
        centroid = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
        return evidence(cross=[]).plot.model_copy(update={"geometry": polygon, "centroid": centroid})

    install_fake_geo(monkeypatch, plot_info=plot_info, **overrides)


def warm(client, name, verify=False):
    return warm_demo.warm_one(client, BY_NAME[name], "http://host", verify=verify, lang="en", timeout=30,
                              verify_timeout=30, poll=0.05)


def test_base_url_is_required_and_checked(capsys):
    for argv in ([], ["--base-url", "host.example"], ["--base-url", "http://h", "--poll", "0"]):
        with pytest.raises(SystemExit) as stop:
            warm_demo.parse_args(argv)
        assert stop.value.code == 2
    capsys.readouterr()


def test_arguments_and_plot_choice():
    args = warm_demo.parse_args(["--base-url", "http://h:8000/"])
    assert args.base_url == "http://h:8000" and not args.verify
    assert [p.name for p in warm_demo.choose(False, None)] == ["bhiwani-strongest", "bhiwani-typical", "godavari-arnab"]
    assert warm_demo.choose(True, None)[-1].name == "ratia-hail"
    assert [p.name for p in warm_demo.choose(False, ["ratia-hail"])] == ["ratia-hail"]
    with pytest.raises(SystemExit):
        warm_demo.parse_args(["--base-url", "http://h", "--only", "nowhere"])


def test_plots_are_the_ones_geo_validated():
    strongest, typical = BY_NAME["bhiwani-strongest"], BY_NAME["bhiwani-typical"]
    assert (strongest.lat, strongest.lon, strongest.side_m) == (28.700911, 76.215719, 113.1)
    assert (typical.lat, typical.lon, typical.side_m) == (28.715212, 76.231138, 104.7)
    assert strongest.event_date == typical.event_date == "2024-03-03"
    for plot in (strongest, typical):
        assert plot.polygon == validated_square(plot.lon, plot.lat, plot.side_m)
        assert (plot.crop, plot.event_type) == ("wheat", "hail")
    godavari = BY_NAME["godavari-arnab"]
    assert (godavari.event_date, godavari.crop, godavari.event_type) == ("2026-10-28", "paddy", "cyclone")
    assert godavari.crop_stage is None and BY_NAME["ratia-hail"].crop_stage is None


def test_insured_is_never_sent():
    for plot in warm_demo.PLOTS:
        assert "insured" not in json.dumps(warm_demo.case_payloads(plot, "hi"))


def test_dry_run_sends_nothing(capsys, monkeypatch):
    monkeypatch.setattr(warm_demo.httpx, "Client", lambda *a, **k: pytest.fail("must not connect"))
    assert warm_demo.main(["--base-url", "http://h", "--dry-run"]) == 0
    assert "bhiwani-typical" in capsys.readouterr().out


def test_a_full_warm_through_the_public_api(client, monkeypatch):
    fake_geo_on_real_plot(monkeypatch)
    row = warm(client, "bhiwani-strongest", verify=True)
    assert row["error"] is None and row["level"] and row["hash"]
    assert row["url"] == f"http://host/case/{row["case_id"]}"
    assert row["verify_status"] == "verified" and row["verify_s"] is not None
    assert row["sealed_s"] is not None and row["verdict_s"] is not None
    assert warm_demo.succeeded(row, True)

    body = client.get(f"/api/cases/{row['case_id']}").json()
    plot = BY_NAME["bhiwani-strongest"]
    case = body["case"]
    assert case["insured"] is None and case["crop_stage"] == "standing"
    assert (case["crop"], case["event_type"], case["event_date"]) == ("wheat", "hail", "2024-03-03")
    assert case["date_source"] == "farmer"
    # Nothing rounded the polygon on its way in, so the seed is the validated runs' seed.
    assert case["plot"]["geometry"] == plot.polygon
    assert body["evidence"]["replay"]["polygon"] == plot.polygon
    assert body["evidence"]["replay"]["seed"] == make_seed(plot.polygon, "2024-03-03")
    assert body["selection_note"]["kind"] == "strongest"


def test_rerunning_creates_new_cases(client, monkeypatch):
    fake_geo_on_real_plot(monkeypatch)
    assert warm(client, "godavari-arnab")["case_id"] != warm(client, "godavari-arnab")["case_id"]


def test_godavari_has_no_invented_stage_or_selection_note(client, monkeypatch):
    fake_geo_on_real_plot(monkeypatch)
    row = warm(client, "godavari-arnab")
    body = client.get(f"/api/cases/{row['case_id']}").json()
    assert body["case"]["crop_stage"] is None and body["case"]["insured"] is None
    assert body["selection_note"] is None and body["evidence"]["claim_path"]["route"] == "undetermined"


def test_a_rejected_case_is_reported_and_does_not_stop_the_rest(client, monkeypatch, capsys):
    fake_geo_on_real_plot(monkeypatch)
    real = warm_demo.create_case

    def fail_first(c, plot, lang):
        if plot.name == "bhiwani-strongest":
            raise RuntimeError("create case: HTTP 422")
        return real(c, plot, lang)

    monkeypatch.setattr(warm_demo, "create_case", fail_first)
    args = warm_demo.parse_args(["--base-url", "http://host", "--only", "bhiwani-strongest", "bhiwani-typical", "--poll", "0.05"])
    assert warm_demo.run(args, client) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out and "1 of 2 cases" in out and "bhiwani-typical" in out


def test_a_check_that_does_not_verify_is_not_success():
    row = {"error": None, "hash": "h", "verify_status": "engine_changed"}
    assert not warm_demo.succeeded(row, True) and warm_demo.succeeded(row, False)


def test_sse_parsing_skips_pings_and_noise():
    lines = [": ping", "id: 1", 'data: {"type": "number", "seq": 1}', "data: not json", ""]
    assert warm_demo.sse_data(lines) == [{"type": "number", "seq": 1}]


def test_selection_note_stays_out_of_the_hash(client, monkeypatch):
    fake_geo_on_real_plot(monkeypatch)
    row = warm(client, "bhiwani-typical")
    body = client.get(f"/api/cases/{row['case_id']}").json()
    assert body["selection_note"]["kind"] == "typical"
    assert "selection" not in json.dumps(body["evidence"])
    assert evidence_hash(ReplayCore.model_validate(body["evidence"]["replay"])) == row["hash"]
    assert disclosures.selection_note(body["evidence"]["plot"]["centroid"])["kind"] == "typical"


def test_the_api_gives_the_near_band_and_whether_it_decides(client, monkeypatch):
    from datetime import date

    from tests.conftest import POST_ID, PRE_ID, placebo, scene

    base = evidence(delta=-0.126, cross=[])
    base.neighbours.far_placebo, base.neighbours.placebo = placebo(p=0.054), placebo(p=0.202)
    base.optical.plot_delta_ndvi = -0.126
    fake_geo_on_real_plot(
        monkeypatch, optical_compare=lambda *a, **k: (base.optical, base.neighbours),
        search_optical=lambda *a, **k: [scene(PRE_ID, date(2024, 2, 28)), scene(POST_ID, date(2024, 3, 9))],
    )
    row = warm(client, "bhiwani-typical")
    body = client.get(f"/api/cases/{row['case_id']}").json()
    assert body["rubric"]["near_low"] == 0.01 and body["rubric"]["near_high"] == 0.075
    assert body["rubric"]["near_line_decides"] is True
    assert any("could change this result" in c for c in body["evidence"]["verdict"]["caveats"])


def test_the_api_says_near_does_not_decide_for_a_case_with_no_evidence(client):
    case_id = warm_demo.create_case(client, BY_NAME["godavari-arnab"], "en")
    assert client.get(f"/api/cases/{case_id}").json()["rubric"]["near_line_decides"] is False
