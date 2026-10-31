"""Every level of rubric v3, including its boundaries."""
from datetime import timedelta

from app.agent import rubric
from app.evidence.schema import Objection
from tests.conftest import (
    EVENT,
    an_alert,
    evidence,
    history_ok,
    placebo,
    sar_evidence,
    stats,
    weather,
)


def _objection(oid, outcome):
    return Objection(id=oid, challenge_hi="", challenge_en="", test="", measured={}, outcome=outcome,
                     finding_hi="", finding_en="")


def level(ev):
    return rubric.decide(ev).level


def good(**kwargs):
    """A clean case: rebutted pre-trend and history, so that only what a test changes matters."""
    kwargs.setdefault("history", history_ok())
    kwargs.setdefault("pretrend", -0.01)
    return evidence(**kwargs)


def test_version():
    assert rubric.RUBRIC_VERSION == "v3" and rubric.decide(good()).version == "v3"


def test_strong_on_the_ring_test():
    assert level(good(p=placebo(p=0.02))) == "strong"


def test_strong_on_the_far_test_when_the_ring_is_not_significant():
    assert level(good(p=placebo(p=0.4), far=placebo(p=0.01))) == "strong"


def test_strong_boundaries_are_inclusive():
    assert level(good(delta=-0.15, p=placebo(p=0.025))) == "strong"
    assert level(good(delta=-0.15, p=placebo(p=0.4), far=placebo(p=0.025))) == "strong"


def test_delta_just_above_threshold_is_moderate():
    assert level(good(delta=-0.149, p=placebo(p=0.02))) == "moderate"


def test_p_just_above_bonferroni_has_no_field_signal():
    ev = good(p=placebo(p=0.026), far=placebo(p=0.026))
    assert not rubric.field_signal(ev) and level(ev) == "weak"


def test_the_old_ten_percent_tier_is_gone():
    assert level(good(delta=-0.2, p=placebo(p=0.09))) == "weak"


def test_missing_far_is_not_a_pass():
    ev = good(p=placebo(p=0.4), far=None)
    assert not rubric.far_significant(ev) and level(ev) == "weak"


def test_far_with_too_few_placebos_does_not_count():
    ev = good(p=placebo(p=0.4), far=placebo(p=0.01, n=10))
    assert not rubric.far_significant(ev) and level(ev) == "weak"


def test_far_with_an_insufficient_reason_does_not_count():
    ev = good(p=placebo(p=0.4), far=placebo(p=0.01, reason="too few"))
    assert not rubric.far_significant(ev)


def test_any_conceded_objection_blocks_strong():
    ev = good()
    ev.cross_examination.append(_objection("too_small", "conceded"))
    assert level(ev) == "moderate"


def test_conceded_pre_trend_blocks_strong():
    assert level(good(pretrend=-0.2)) == "moderate"


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


def test_moderate_field_signal_boundary():
    assert level(good(delta=-0.10, p=placebo(p=0.025))) == "moderate"
    assert level(good(delta=-0.099, p=placebo(p=0.025))) == "weak"


def test_moderate_sar_alone_never_exceeds_moderate():
    assert level(evidence(optical=False, sar=sar_evidence(p=0.001))) == "moderate"


def test_moderate_sar_threshold_and_corroboration():
    assert level(evidence(optical=False, sar=sar_evidence(p=0.05))) == "moderate"
    assert level(evidence(optical=False, sar=sar_evidence(p=0.06))) == "weak"
    ev = evidence(optical=False, sar=sar_evidence(p=0.001), wx=weather(corroborated=False, max_mm=0.0))
    assert level(ev) == "weak"


def test_moderate_new_water():
    assert level(evidence(optical=False, sar=sar_evidence(p=0.5, water=0.2))) == "moderate"


def test_field_signal_without_corroboration_is_weak_in_v3():
    """v2 allowed moderate here when no source spoke to the date. v3's fixed rules do not list it."""
    assert level(good(wx=weather(corroborated=False, max_mm=0.5))) == "weak"


def test_weak_corroborated_without_plot_signal():
    assert level(good(delta=-0.02, p=placebo(p=0.6))) == "weak"


def test_weak_no_signal_at_all_with_good_data():
    assert level(good(delta=0.02, p=placebo(p=0.7), wx=weather(corroborated=False, max_mm=0.0))) == "weak"


def test_wrong_plot_caps_at_weak():
    assert level(good(pre_ndvi=0.2, post_ndvi=0.1)) == "weak"


def test_suspect_post_cannot_be_strong():
    assert level(good(post_status="suspect", sar=sar_evidence(p=0.02))) == "moderate"


def test_suspect_post_without_confirmation_gets_no_optical_credit():
    assert level(good(post_status="suspect")) in ("insufficient", "weak")


def test_alert_or_news_corroborates_without_weather():
    ev = good(wx=weather(corroborated=False, max_mm=0.0), alerts=[an_alert()])
    assert rubric.corroboration(ev) == ["official_alert"] and level(ev) == "strong"


def test_absent_weather_never_refutes():
    ev = good(wx=weather(corroborated=False, max_mm=0.0))
    assert next(o for o in ev.cross_examination if o.id == "wrong_date").outcome == "unresolved"


def test_recheck_scheduled_when_insufficient():
    assert rubric.decide(evidence(optical=False)).schedule_recheck


def test_early_post_scene_gets_a_caveat_and_a_recheck():
    ev = good()
    ev.optical.post = stats("S2_POST", EVENT + timedelta(days=2), 0.45)
    result = rubric.decide(ev)
    assert rubric.post_too_early(ev) and result.schedule_recheck
    assert any("may be too early" in c for c in result.caveats)


def test_settled_post_scene_has_no_such_caveat():
    ev = good()
    ev.optical.post = stats("S2_POST", EVENT + timedelta(days=5), 0.45)
    result = rubric.decide(ev)
    assert not rubric.post_too_early(ev) and not result.schedule_recheck
    assert not any("too early" in c for c in result.caveats)


def test_wide_events_are_named_as_the_limit_of_the_far_test():
    assert any("wider than 12 km" in c for c in rubric.decide(good()).caveats)
