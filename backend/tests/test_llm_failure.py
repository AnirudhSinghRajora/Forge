"""LLM behaviour with no key, with bad output, and with a raising client. No network."""
from app.agent import explain, llm, rubric, testimony
from app.evidence.schema import Verdict
from tests.conftest import evidence


def with_verdict(ev):
    r = rubric.decide(ev)
    hi, en, te = explain.headlines(r.level, ev.event.type)
    ev.verdict = Verdict(level=r.level, headline_hi=hi, headline_en=en, headline_te=te, reasons=r.reasons,
                         caveats=r.caveats, falsifiers_checked=r.falsifiers_checked, rubric_version=r.version)
    return ev


def test_every_wrapper_returns_none_without_a_key():
    assert not llm.available()
    assert llm.parse_text("x") is None
    assert llm.parse_audio(b"x", "audio/webm") is None
    assert llm.plan("x", [{"name": "a"}]) is None
    assert llm.narrate({}, "hi") is None
    assert llm.translate("x", "te") is None
    assert llm.tts("x", "hi") is None
    assert llm.grounded_sources("x") is None
    assert llm.embed(["x"], is_query=True) is None


def test_templates_exist_for_every_level():
    for level in ("strong", "moderate", "weak", "insufficient", "not_damage_likely_harvest"):
        hi, en, te = explain.headlines(level, "hail")
        assert hi and en and te


def test_explanation_falls_back_to_template_without_llm():
    ev = with_verdict(evidence())
    report = explain.explain(ev)
    assert report["hi"] == "template" and report["te"] == "template" and not ev.llm_used
    assert "0.70" in ev.explanation_hi and "0.45" in ev.explanation_en
    assert ev.explanation_te and ev.verdict.headline_te


def test_template_numbers_pass_the_validator():
    from app.agent import validate

    ev = with_verdict(evidence())
    explain.explain(ev)
    testimony.fill(ev)
    allowed = explain.allowed_numbers(ev)
    for text in (ev.explanation_hi, ev.explanation_en, ev.testimony_hi, ev.testimony_en, ev.testimony_te):
        assert validate.validate_text(text, allowed).ok, text


def test_llm_narrative_with_an_invented_number_is_blocked(monkeypatch):
    """T15: the validator blocks it and the deterministic text ships."""
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "narrate", lambda digest, lang: "Your loss is 87% and 4.2 hectares.")
    monkeypatch.setattr(llm, "translate", lambda text, lang: "నష్టం 87%")
    ev = with_verdict(evidence())
    report = explain.explain(ev)
    assert "87" not in ev.explanation_en and "87" not in (ev.explanation_te or "")
    assert not ev.llm_used and set(report["rejected"]) == {"narrative_hi", "narrative_en"}


def test_llm_narrative_with_a_promise_is_blocked(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "narrate", lambda digest, lang: "You will be paid for this.")
    monkeypatch.setattr(llm, "translate", lambda text, lang: None)
    ev = with_verdict(evidence())
    explain.explain(ev)
    assert "paid" not in ev.explanation_en


def test_llm_narrative_with_real_numbers_is_used(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "narrate", lambda digest, lang: "NDVI went from 0.70 to 0.45.")
    monkeypatch.setattr(llm, "translate", lambda text, lang: None)
    ev = with_verdict(evidence())
    explain.explain(ev)
    assert ev.explanation_en == "NDVI went from 0.70 to 0.45." and ev.llm_used


def test_raising_client_means_none_on_both_surfaces(monkeypatch):
    class Boom:
        class interactions:
            @staticmethod
            def create(**k):
                raise TimeoutError("slow")

        class models:
            @staticmethod
            def generate_content(**k):
                raise RuntimeError("500")

            @staticmethod
            def embed_content(**k):
                raise RuntimeError("500")

    monkeypatch.setattr(llm, "client", lambda: Boom)
    assert llm.parse_text("x") is None
    assert llm.narrate({}, "hi") is None
    assert llm.tts("x", "hi") is None
    assert llm.grounded_sources("x") is None
    assert llm.embed(["x"], is_query=True) is None
    assert llm.plan("x", [{"name": "a", "description": "d", "parameters": {"type": "object"}}]) is None


def test_testimony_covers_all_levels_and_carries_caveats():
    cases = [
        evidence(),
        evidence(optical=False),
        evidence(delta=-0.01, wx=None),
        evidence(bare=0.8, pattern="uniform", neighbour_bare=0.5),
    ]
    for ev in cases:
        with_verdict(ev)
        hi, en, te = testimony.templates(ev)
        assert hi.startswith("मैं आपका खेत हूँ") and en.startswith("I am your field") and te
        assert "not guaranteed" in en
        assert "will be paid" not in en and "knows" not in en


def test_testimony_never_claims_the_cause():
    ev = with_verdict(evidence())
    _, en, _ = testimony.templates(ev)
    assert "do not know the cause" in en and "consistent with" in en


def test_testimony_states_both_answers_in_plain_words():
    from tests.conftest import placebo

    area = with_verdict(evidence(p=placebo(p=0.4), far=placebo(p=0.01)))
    assert "does not look limited to me" in testimony.templates(area)[1]
    local = with_verdict(evidence(p=placebo(p=0.02), far=placebo(p=0.4)))
    assert "looks local to me" in testimony.templates(local)[1]
    neither = with_verdict(evidence(p=placebo(p=0.4), far=placebo(p=0.4)))
    assert "I did not clearly change more" in testimony.templates(neither)[1]


def test_testimony_says_no_damage_visible_honestly():
    from tests.conftest import placebo

    ev = with_verdict(evidence(delta=0.01, p=placebo(p=0.7)))
    _, en, _ = testimony.templates(ev)
    assert ev.verdict.level == "weak" and "No clear mark of damage" in en and "does not mean" in en


def test_planner_veto(monkeypatch):
    from app.agent.graph import plan_veto

    ev = evidence()
    ev.weather.corroborated = False
    assert plan_veto("sar_first", ev)
    ev.event.type = "cyclone"
    assert plan_veto("sar_first", ev) is None
    assert plan_veto("search_optical", ev) is None


def test_hung_llm_cannot_hold_up_a_run(monkeypatch):
    import time

    start = time.monotonic()
    assert llm.bounded(0.05, time.sleep, 2) is None
    assert time.monotonic() - start < 1


def test_raising_llm_is_a_none_from_bounded():
    def boom():
        raise RuntimeError("x")

    assert llm.bounded(1, boom) is None
