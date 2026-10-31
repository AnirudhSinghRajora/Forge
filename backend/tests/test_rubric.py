"""Every level of rubric v2, including its boundaries."""
from app.agent import rubric
from app.evidence.schema import Objection
from tests.conftest import an_alert, evidence, history_ok, placebo, sar_evidence, weather


def _objection(oid, outcome):
    return Objection(id=oid, challenge_hi="", challenge_en="", test="", measured={}, outcome=outcome,
                     finding_hi="", finding_en="")


def level(ev):
    return rubric.decide(ev).level


def test_strong_when_all_conditions_hold():
    assert level(evidence(history=history_ok())) == "strong"


def test_strong_boundary_values_are_inclusive():
    assert level(evidence(delta=-0.15, p=placebo(p=0.05), history=history_ok())) == "strong"


def test_delta_just_above_threshold_is_not_strong():
    assert level(evidence(delta=-0.149, p=placebo(p=0.05), history=history_ok())) == "moderate"


def test_p_just_above_threshold_is_not_strong():
    # p of 0.06 also concedes nothing (it is unresolved), so moderate through the loose branch.
    assert level(evidence(p=placebo(p=0.06), history=history_ok())) == "moderate"


def test_any_conceded_objection_blocks_strong():
    ev = evidence(history=history_ok())
    ev.cross_examination.append(_objection("too_small", "conceded"))
    assert level(ev) == "moderate"


def test_harvest_conceded_is_evaluated_first():
    ev = evidence(bare=0.8, pattern="uniform", neighbour_bare=0.5,
                  history=history_ok(excess=-0.02), alerts=[an_alert()])
    assert level(ev) == "not_damage_likely_harvest"


def test_insufficient_without_post_or_sar():
    assert level(evidence(optical=False, wx=weather(corroborated=False, max_mm=0.0))) == "insufficient"


def test_insufficient_with_unusable_sar_even_when_corroborated():
    assert level(evidence(optical=False, sar=sar_evidence(usable=False))) == "insufficient"


def test_insufficient_few_placebos_and_no_other_signal():
    ev = evidence(delta=-0.01, p=placebo(p=0.5, n=20), wx=weather(corroborated=False, max_mm=0.0))
    assert level(ev) == "insufficient"


def test_few_placebos_with_another_signal_is_not_insufficient():
    assert level(evidence(p=placebo(p=0.01, n=20))) != "insufficient"


def test_moderate_optical_loose_branch():
    assert level(evidence(delta=-0.10, p=placebo(p=0.10), history=history_ok())) == "moderate"


def test_moderate_sar_alone_never_exceeds_moderate():
    ev = evidence(optical=False, sar=sar_evidence(p=0.001))
    assert level(ev) == "moderate"


def test_moderate_sar_needs_corroboration():
    ev = evidence(optical=False, sar=sar_evidence(p=0.001), wx=weather(corroborated=False, max_mm=0.0))
    assert level(ev) == "weak"


def test_moderate_new_water():
    ev = evidence(optical=False, sar=sar_evidence(p=0.5, water=0.2))
    assert level(ev) == "moderate"


def test_moderate_strong_field_conditions_with_unresolved_date():
    """The Sirsa rule: a clear field signal, and no source that speaks to the date at all."""
    ev = evidence(wx=weather(corroborated=False, max_mm=0.5), history=history_ok())
    assert rubric.event_date_unresolved(ev)
    assert level(ev) == "moderate"


def test_weather_pointing_elsewhere_is_not_unresolved():
    from datetime import date

    ev = evidence(wx=weather(corroborated=False, max_mm=0.5, proposed=date(2026, 10, 20)),
                  history=history_ok())
    assert not rubric.event_date_unresolved(ev)
    assert level(ev) == "weak"


def test_weak_corroborated_without_plot_signal():
    assert level(evidence(delta=-0.02, p=placebo(p=0.6), history=history_ok())) == "weak"


def test_weak_no_signal_at_all_with_good_data():
    ev = evidence(delta=0.02, p=placebo(p=0.7), wx=weather(corroborated=False, max_mm=0.0),
                  history=history_ok())
    assert level(ev) == "weak"


def test_wrong_plot_caps_at_weak():
    ev = evidence(pre_ndvi=0.2, post_ndvi=0.1, history=history_ok())
    assert level(ev) == "weak"


def test_suspect_post_cannot_be_strong():
    ev = evidence(post_status="suspect", sar=sar_evidence(p=0.02), history=history_ok())
    assert level(ev) == "moderate"


def test_suspect_post_without_confirmation_gets_no_optical_credit():
    ev = evidence(post_status="suspect", history=history_ok())
    assert level(ev) == "insufficient" or level(ev) == "weak"


def test_alert_or_news_corroborates_without_weather():
    ev = evidence(wx=weather(corroborated=False, max_mm=0.0), alerts=[an_alert()], history=history_ok())
    assert rubric.corroboration(ev) == ["official_alert"]
    assert level(ev) == "strong"


def test_absent_weather_never_refutes():
    ev = evidence(wx=weather(corroborated=False, max_mm=0.0), history=history_ok())
    wrong_date = next(o for o in ev.cross_examination if o.id == "wrong_date")
    assert wrong_date.outcome == "unresolved"


def test_recheck_scheduled_when_insufficient():
    assert rubric.decide(evidence(optical=False)).schedule_recheck
