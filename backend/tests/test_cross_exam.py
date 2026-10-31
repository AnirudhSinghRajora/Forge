"""Each objection, in each outcome, on evidence values."""
from datetime import date

from app.agent import cross_exam
from tests.conftest import an_alert, evidence, history_ok, placebo, sar_evidence, weather


def get(ev, oid):
    return next(o for o in ev.cross_examination if o.id == oid)


def test_order_is_fixed_and_complete():
    assert tuple(o.id for o in evidence().cross_examination) == cross_exam.ORDER


def test_every_text_has_hindi_and_english():
    for ev in (evidence(), evidence(optical=False), evidence(optical=False, sar=sar_evidence())):
        for o in ev.cross_examination:
            assert o.challenge_hi and o.challenge_en and o.finding_hi and o.finding_en and o.test


def test_harvest_rebutted_with_values():
    o = get(evidence(bare=0.1, pattern="patchy", history=history_ok()), "harvest")
    assert o.outcome == "rebutted" and o.measured["post_bare_fraction"] == 0.1


def test_harvest_conceded_neighbours_and_history():
    ev = evidence(bare=0.8, pattern="uniform", neighbour_bare=0.5, history=history_ok(excess=-0.02))
    assert get(ev, "harvest").outcome == "conceded"


def test_harvest_conceded_when_history_is_missing_but_neighbours_agree():
    assert get(evidence(bare=0.8, pattern="uniform", neighbour_bare=0.5), "harvest").outcome == "conceded"


def test_harvest_unresolved_when_neither_confirms():
    ev = evidence(bare=0.8, pattern="uniform", neighbour_bare=0.05, history=history_ok(excess=-0.3))
    assert get(ev, "harvest").outcome == "unresolved"


def test_harvest_unresolved_without_post():
    assert get(evidence(optical=False), "harvest").outcome == "unresolved"


def test_wrong_plot_outcomes():
    assert get(evidence(pre_ndvi=0.2), "wrong_plot").outcome == "conceded"
    assert get(evidence(pre_ndvi=0.3), "wrong_plot").outcome == "rebutted"
    assert get(evidence(optical=False), "wrong_plot").outcome == "unresolved"


def test_wrong_date_rebutted_by_weather():
    assert get(evidence(), "wrong_date").outcome == "rebutted"


def test_wrong_date_rebutted_by_alert_without_weather():
    ev = evidence(wx=weather(corroborated=False, max_mm=0.0), alerts=[an_alert()])
    assert get(ev, "wrong_date").outcome == "rebutted"


def test_wrong_date_conceded_with_proposal():
    proposed = date(2026, 10, 20)
    ev = evidence(wx=weather(corroborated=False, max_mm=0.5, proposed=proposed))
    o = get(ev, "wrong_date")
    assert o.outcome == "conceded" and o.measured["proposed_event_date"] == "2026-10-20"
    _, followups = cross_exam.run(ev)
    assert any(f.kind == "redate" and f.event_date == proposed for f in followups)


def test_absence_of_weather_never_refutes():
    o = get(evidence(wx=weather(corroborated=False, max_mm=0.0)), "wrong_date")
    assert o.outcome == "unresolved"
    assert "does not count against" in o.finding_en


def test_cloud_shadow_conceded_yields_exclusion():
    ev = evidence(post_valid=0.7)
    assert get(ev, "cloud_shadow").outcome == "conceded"
    _, followups = cross_exam.run(ev)
    assert any(f.kind == "exclude_scene" and f.scene_id == "S2_POST" for f in followups)


def test_cloud_shadow_radar_and_nothing():
    assert get(evidence(optical=False, sar=sar_evidence()), "cloud_shadow").outcome == "rebutted"
    assert get(evidence(optical=False), "cloud_shadow").outcome == "unresolved"


def test_corrupt_scene_suspect_needs_second_sensor():
    assert get(evidence(post_status="suspect"), "corrupt_scene").outcome == "conceded"
    ev = evidence(post_status="suspect", sar=sar_evidence(p=0.02))
    assert get(ev, "corrupt_scene").outcome == "rebutted"


def test_corrupt_scene_accepted_is_rebutted():
    assert get(evidence(), "corrupt_scene").outcome == "rebutted"


def test_regional_trend_outcomes():
    assert get(evidence(p=placebo(p=0.02)), "regional_trend").outcome == "rebutted"
    assert get(evidence(p=placebo(p=0.08)), "regional_trend").outcome == "unresolved"
    assert get(evidence(p=placebo(p=0.4)), "regional_trend").outcome == "conceded"
    assert get(evidence(p=placebo(p=0.01, n=10)), "regional_trend").outcome == "unresolved"


def test_too_small_outcomes():
    assert get(evidence(area=0.1), "too_small").outcome == "conceded"
    assert get(evidence(area=0.2), "too_small").outcome == "rebutted"


def test_stale_crop_outcomes():
    assert get(evidence(), "stale_crop").outcome == "unresolved"
    assert get(evidence(history=history_ok(down=True)), "stale_crop").outcome == "conceded"
    assert get(evidence(history=history_ok()), "stale_crop").outcome == "rebutted"


def test_measured_values_are_copied_from_evidence():
    o = get(evidence(p=placebo(p=0.02, n=200, k=3)), "regional_trend")
    assert (o.measured["n_placebos"], o.measured["n_at_least_as_extreme"]) == (200, 3)
    assert "3" in o.finding_en and "200" in o.finding_en
