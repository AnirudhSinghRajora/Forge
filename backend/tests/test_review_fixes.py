"""One focused test per finding from the independent review, in the order they were listed."""
import json
import time
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import errors, limits
from app.agent import cross_exam, explain, parse, rubric, runner, testimony, validate
from app.config import get_settings
from app.db import Action, Case, EvidenceRow, Plot, Run, VerifyEvent, VerifyRun, session_scope
from app.evidence.schema import Alert, NewsItem, ReplayCore
from app.tools import policy
from tests.conftest import (
    EVENT, an_alert, evidence, install_fake_geo, placebo, qa, weather,
)
from tests.test_api import SQUARE, client, new_case, stream, wait_done  # noqa: F401


def _setenv(monkeypatch, **values):
    for key, value in values.items():
        monkeypatch.setenv(key, str(value))
    get_settings.cache_clear()


def _sealed_case(client, monkeypatch, **geo):  # noqa: F811
    install_fake_geo(monkeypatch, **geo)
    case_id = new_case(client)
    wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    return case_id


def _no_weather():
    return weather(corroborated=False, max_mm=0.0)


def _strong_field(**kw):
    return evidence(p=placebo(p=0.01), wx=kw.pop("wx", weather()), **kw)


# A. Corroboration


def test_news_never_corroborates_and_the_report_stays_weak():
    ev = _strong_field(wx=_no_weather())
    ev.news = [NewsItem(title="Hail in Sirsa", url="https://x.example/a")]
    assert rubric.corroboration(ev) == []
    level, reasons = rubric.decide_level(ev)
    assert level == "weak" and rubric.NO_SUPPORT in reasons


def test_the_same_evidence_gets_the_same_level_with_or_without_news():
    ev = _strong_field()
    plain = rubric.decide_level(ev)[0]
    ev.news = [NewsItem(title="t", url="https://x.example/a")]
    assert rubric.decide_level(ev)[0] == plain == "strong"


@pytest.mark.parametrize(("event", "alert_event", "matches"), [
    ("hail", "Thunderstorm with Hail", True),
    ("hail", "Light Thunderstorms", False),
    ("hail", "Lightning", False),
    ("hail", "Flood", False),
    ("flood", "Flood", True),
    ("unseasonal_rain", "Moderate Rain", True),
    ("unseasonal_rain", "Light Rain", False),
    ("wind", "Squally", True),
    ("wind", "Moderate Thunderstorms with surface wind", True),
    ("cyclone", "Cyclonic storm warning", True),
    ("unknown", "Flood", False),
    ("other", "Flood", False),
])
def test_an_alert_corroborates_only_when_its_hazard_matches(event, alert_event, matches):
    alert = Alert(source="NDMA SACHET", identifier="a1", event=alert_event, headline="Take care")
    assert rubric.alert_matches(alert, event) is matches


def test_an_alert_for_another_hazard_is_shown_but_does_not_corroborate():
    other = Alert(source="NDMA SACHET", identifier="a1", event="Flood", headline="Flood warning")
    ev = _strong_field(wx=_no_weather(), alerts=[other])
    assert ev.event.type == "hail" and rubric.corroboration(ev) == [] and rubric.decide_level(ev)[0] == "weak"
    assert rubric.decide_level(_strong_field(wx=_no_weather(), alerts=[an_alert()]))[0] == "strong"


def test_news_cannot_rebut_the_wrong_date_objection():
    ev = evidence(wx=_no_weather(), cross=[])
    ev.news = [NewsItem(title="t", url="https://x.example/a")]
    objection, _ = cross_exam.check_wrong_date(ev)
    assert objection.outcome != "rebutted" and "cited_news" not in objection.measured
    ev.alerts = [an_alert()]
    assert cross_exam.check_wrong_date(ev)[0].outcome == "rebutted"


def test_the_text_says_why_a_report_without_support_stays_weak():
    ev = _strong_field(wx=_no_weather())
    result = rubric.decide(ev)
    from app.evidence.schema import Verdict

    ev.verdict = Verdict(level=result.level, headline_hi="h", headline_en="e", reasons=result.reasons,
                         caveats=result.caveats, falsifiers_checked=[], rubric_version="v3")
    for text, line in zip(explain.template_explanation(ev, "weak"), explain.NO_SUPPORT_LINE, strict=True):
        assert line in text
    for text, line in zip(testimony.templates(ev), (explain.NO_SUPPORT_LINE), strict=True):
        assert line in text


def test_news_cache_key_includes_the_event_type(monkeypatch):
    from app.agent import llm
    from app.tools import news

    calls = []
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "grounded_sources", lambda q: calls.append(q) or [{"url": f"https://x/{len(calls)}", "title": "t"}])
    first = news.search("Sirsa", "Haryana", "hail", EVENT)
    second = news.search("Sirsa", "Haryana", "flood", EVENT)
    again = news.search("Sirsa", "Haryana", "hail", EVENT)
    assert len(calls) == 2 and first != second and again == first


# B. Regex freezes


def _fastest_ms(fn, *args, runs=3) -> float:
    best = 1e9
    for _ in range(runs):  # the best of a few, so a busy machine does not fail a linear regex
        began = time.perf_counter()
        fn(*args)
        best = min(best, (time.perf_counter() - began) * 1000)
    return best


@pytest.mark.parametrize("hostile", [
    " " * parse.MAX_TEXT_CHARS,
    "1 " * (parse.MAX_TEXT_CHARS // 2),
    "1" + " " * (parse.MAX_TEXT_CHARS - 1),
    "सुबह " * (parse.MAX_TEXT_CHARS // 5),
    "ek " * (parse.MAX_TEXT_CHARS // 3),
    "may " * (parse.MAX_TEXT_CHARS // 4),
    "3 of " * (parse.MAX_TEXT_CHARS // 5),
    "a" * parse.MAX_TEXT_CHARS,
])
def test_hostile_report_text_of_the_cap_size_is_quick(hostile):
    parse.parse_text(hostile)  # compile the patterns first: the cost being tested is the search
    assert _fastest_ms(parse.parse_text, hostile) < 50


def test_report_text_is_cut_to_the_cap_before_any_regex():
    report = parse.parse_text("x" * (parse.MAX_TEXT_CHARS * 20) + " hail")
    assert len(report.transcript) == parse.MAX_TEXT_CHARS and report.event_type == "unknown"


def test_clock_time_still_reads_after_the_rewrite():
    assert parse.extract_time("शाम 5 बजे ओले गिरे") == "17:00"
    assert parse.extract_time("raat 8:30 baje") == "20:30"
    assert parse.extract_time("10 baje") == "10:00"
    assert parse.extract_time("12 बजे") == "12:00"


@pytest.mark.parametrize("hostile", [
    "late " * 100, "what detail " * 41, "how " * 125, "hail " * 100, "when " * 100,
    "क्या " * 100, "report " * 71, "late" + " " * 496, " " * 500, "what " + "x" * 495,
])
def test_hostile_questions_of_the_cap_size_are_quick(hostile):
    question = hostile[:policy.MAX_QUESTION_CHARS]
    rules = {name: {"status": "verified"} for name, _ in policy._INTENTS}
    policy._intent_rule(question, rules)
    assert _fastest_ms(policy._intent_rule, question, {}) < 50
    # Every intent is evaluated, with none of them matching first: the worst case.
    assert _fastest_ms(lambda q: [m(q) for _, m in policy._INTENTS], question) < 50


def test_a_long_question_is_cut_before_any_regex():
    assert policy.ask("x" * 100_000 + " hail cover", "en")["covered"] is False


@pytest.mark.parametrize(("question", "intent"), [
    ("I am late, can I still report it?", "late_intimation"),
    ("I reported it after a delay", "late_intimation"),
    ("how long do I have", "intimation_deadline"),
    ("when should I report", "intimation_deadline"),
    ("which details go in the report", "intimation_contents"),
    ("where do I report", "channels"),
    ("the helpline", "channels"),
    ("can I contest the survey", "grievance"),
    ("is hail covered", "perils"),
    ("does the insurance cover flood", "perils"),
])
def test_intents_still_route_after_the_rewrite(question, intent):
    rules = {name: {"status": "verified"} for name, _ in policy._INTENTS}
    assert policy._intent_rule(question, rules)[0] == intent


# C. No case id on the public side


def test_verify_never_sends_the_case_id(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    env = client.get(f"/api/cases/{case_id}").json()
    h = env["evidence"]["evidence_hash"]
    with client.stream("GET", f"/api/verify/{h}") as response:
        body = "".join(response.iter_text())
    assert case_id not in body and '"case_id"' not in body and '"type": "result"' in body


def test_a_stored_start_event_with_a_case_id_is_not_replayed_with_it(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    h = client.get(f"/api/cases/{case_id}").json()["evidence"]["evidence_hash"]
    with client.stream("GET", f"/api/verify/{h}") as response:
        "".join(response.iter_text())
    with session_scope() as s:
        row = s.query(VerifyEvent).filter(VerifyEvent.seq == 1).first()
        row.payload = {**row.payload, "case_id": case_id}
    with client.stream("GET", f"/api/verify/{h}") as response:
        body = "".join(response.iter_text())
    assert '"cached": true' in body and case_id not in body


def test_the_pdf_shows_no_case_id(client, monkeypatch):  # noqa: F811
    pytest.importorskip("weasyprint")
    import io

    from pypdf import PdfReader

    case_id = _sealed_case(client, monkeypatch)
    response = client.get(f"/api/cases/{case_id}/evidence.pdf?lang=en")
    if response.status_code == 503:
        pytest.skip("no PDF renderer here")
    reader = PdfReader(io.BytesIO(response.content))
    text = " ".join(page.extract_text() or "" for page in reader.pages)
    assert case_id not in text and case_id[:12] not in text
    assert case_id[:8] not in response.headers["content-disposition"]
    assert case_id not in str(reader.metadata)


# D. Abuse limits


def test_investigations_are_limited_per_ip_with_a_message_in_each_language(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, RATE_INVESTIGATIONS_PER_HOUR=1, MAX_QUEUED_RUNS=8)
    install_fake_geo(monkeypatch)
    first, second = new_case(client), new_case(client)
    wait_done(client, client.post(f"/api/cases/{first}/investigate").json()["run_id"])
    limited = client.post(f"/api/cases/{second}/investigate")
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    detail = limited.json()["detail"]
    assert detail["code"] == "rate_limited" and all(detail[f"message_{x}"] for x in ("hi", "en", "te"))


def test_asking_again_about_a_running_investigation_costs_nothing(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, RATE_INVESTIGATIONS_PER_HOUR=1)
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    with session_scope() as s:
        s.add(Run(id="busy", case_id=case_id, status="running"))
    assert client.post(f"/api/cases/{case_id}/investigate").json() == {"run_id": "busy", "created": False}
    assert client.post(f"/api/cases/{case_id}/investigate").json()["run_id"] == "busy"


def test_asks_are_limited(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, RATE_ASKS_PER_HOUR=2)
    case_id = new_case(client)
    codes = [client.post(f"/api/cases/{case_id}/ask", json={"question": "is hail covered", "lang": "en"}).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429]


def test_a_new_download_is_limited_and_a_stored_check_is_not(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, RATE_VERIFY_PER_HOUR=1)
    case_id = _sealed_case(client, monkeypatch)
    h = client.get(f"/api/cases/{case_id}").json()["evidence"]["evidence_hash"]
    for _ in range(3):  # the first download, then two reads of the stored check
        with client.stream("GET", f"/api/verify/{h}") as response:
            assert response.status_code == 200
            "".join(response.iter_text())
    assert client.get(f"/api/verify/{h}?rerun=1").status_code == 429


def test_the_client_address_ignores_forwarded_for_unless_the_proxy_is_trusted(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, RATE_ASKS_PER_HOUR=1)
    case_id = new_case(client)

    def ask(ip):
        return client.post(f"/api/cases/{case_id}/ask", json={"question": "is hail covered", "lang": "en"},
                           headers={"X-Forwarded-For": ip}).status_code

    assert ask("1.1.1.1") == 200 and ask("2.2.2.2") == 429  # the header changes nothing
    limits.reset()
    _setenv(monkeypatch, TRUST_PROXY="true")
    assert ask("1.1.1.1") == 200 and ask("2.2.2.2") == 200 and ask("2.2.2.2") == 429
    assert ask("9.9.9.9, 2.2.2.2") == 429  # the last entry is the one our proxy wrote


def test_the_queue_is_capped(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, MAX_QUEUED_RUNS=2)
    install_fake_geo(monkeypatch)
    ids = [new_case(client) for _ in range(3)]
    with session_scope() as s:
        s.add_all([Run(id="q1", case_id=ids[0], status="queued"), Run(id="q2", case_id=ids[1], status="queued")])
    limited = client.post(f"/api/cases/{ids[2]}/investigate")
    assert limited.status_code == 429 and limited.json()["detail"]["code"] == "queue_full"
    with session_scope() as s:
        s.query(Run).filter(Run.id.in_(("q1", "q2"))).update({"status": "failed"})


def test_the_jobs_route_is_closed_without_a_token(client):  # noqa: F811
    assert client.post("/api/jobs/tick").status_code == 403
    assert client.post("/api/jobs/tick", headers={"X-Scheduler-Token": ""}).status_code == 403


def test_rendered_pdfs_are_cached_per_route_state(client, monkeypatch):  # noqa: F811
    from app.pdf import render

    calls = []
    monkeypatch.setattr(render, "build_pdf", lambda *a, **k: calls.append(a[3]) or b"%PDF-fake")
    case_id = _sealed_case(client, monkeypatch)
    for _ in range(3):
        assert client.get(f"/api/cases/{case_id}/evidence.pdf?lang=en").content == b"%PDF-fake"
    assert calls == ["en"]
    client.get(f"/api/cases/{case_id}/evidence.pdf?lang=hi")
    assert calls == ["en", "hi"]
    client.patch(f"/api/cases/{case_id}", json={"crop_stage": "cut_and_spread"})
    client.get(f"/api/cases/{case_id}/evidence.pdf?lang=en")
    assert calls == ["en", "hi", "en"]


def test_no_cors_headers(client):  # noqa: F811
    response = client.options("/api/health", headers={"Origin": "https://evil.example",
                                                      "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-origin" not in client.get("/api/health", headers={"Origin": "https://x"}).headers


# E. Uploads and fields


def test_an_oversized_json_body_is_refused_by_its_declared_length(client):  # noqa: F811
    case_id = new_case(client)
    response = client.post(f"/api/cases/{case_id}/ask", content=b"x" * 70_000,
                           headers={"content-type": "application/json"})
    assert response.status_code == 413 and response.json()["detail"]["code"] == "body_too_large"


def test_an_oversized_body_without_a_length_is_refused_as_it_streams(client):  # noqa: F811
    case_id = new_case(client)

    def chunks():
        for _ in range(10):
            yield b"x" * 10_000

    response = client.post(f"/api/cases/{case_id}/ask", content=chunks(),
                           headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_a_voice_note_may_be_larger_than_other_bodies_but_not_without_limit(client):  # noqa: F811
    form = {"lat": 29.53, "lon": 75.03}
    fine = client.post("/api/cases", data=form, files={"audio": ("a.webm", b"\x1aE\xdf\xa3" + b"0" * 200_000, "audio/webm")})
    assert fine.status_code == 200
    huge = client.post("/api/cases", data=form, files={"audio": ("a.webm", b"0" * (26 * 1024 * 1024), "audio/webm")})
    assert huge.status_code == 413


def test_something_that_is_not_audio_is_refused(client):  # noqa: F811
    form = {"lat": 29.53, "lon": 75.03}
    bad = client.post("/api/cases", data=form, files={"audio": ("a.exe", b"MZ" + b"0" * 100, "application/x-msdownload")})
    assert bad.status_code == 415 and bad.json()["detail"]["message_te"]
    # A client that labels it generically is judged by the container it actually sent.
    ok = client.post("/api/cases", data=form, files={"audio": ("a.bin", b"OggS" + b"0" * 100, "application/octet-stream")})
    assert ok.status_code == 200


def test_form_text_over_the_cap_is_refused(client):  # noqa: F811
    response = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "text": "x" * (parse.MAX_TEXT_CHARS + 1)})
    assert response.status_code == 422 and response.json()["detail"]["code"] == "text_too_long"


@pytest.mark.parametrize(("field", "size"), [("crop", 65)])
def test_patch_fields_have_a_maximum_length(client, field, size):  # noqa: F811
    case_id = new_case(client)
    assert client.patch(f"/api/cases/{case_id}", json={field: "x" * size}).status_code == 422
    assert client.patch(f"/api/cases/{case_id}", json={field: "x" * (size - 1)}).status_code == 200


def test_submission_and_question_fields_have_a_maximum_length(client):  # noqa: F811
    case_id = new_case(client)
    assert client.post(f"/api/cases/{case_id}/submission", json={"reference_no": "x" * 101}).status_code == 422
    assert client.post(f"/api/cases/{case_id}/submission", json={"reference_no": "A1", "channel": "x" * 65}).status_code == 422
    assert client.post(f"/api/cases/{case_id}/ask", json={"question": "x" * 501}).status_code == 422


@pytest.mark.parametrize(("method", "path", "body"), [
    ("PATCH", "", b'{"crop": "\\ud800"}'),
    ("POST", "/submission", b'{"reference_no": "\\ud800"}'),
    ("POST", "/ask", b'{"question": "\\ud800"}'),
])
def test_a_lone_surrogate_is_a_clean_422_that_echoes_nothing(client, method, path, body):  # noqa: F811
    case_id = new_case(client)
    response = client.request(method, f"/api/cases/{case_id}{path}", content=body,
                              headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert "input" not in response.json()["detail"][0]


def test_a_validation_error_does_not_echo_the_input(client):  # noqa: F811
    case_id = new_case(client)
    response = client.patch(f"/api/cases/{case_id}", json={"crop": "secret" * 100})
    assert response.status_code == 422 and "secret" not in response.text


# F. Validation and verdict text


def test_polish_is_off_by_default_and_nothing_narrates(client, monkeypatch):  # noqa: F811
    from app.agent import llm

    called = []
    monkeypatch.setattr(llm, "available", lambda: True)
    for name in ("narrate", "translate", "rephrase_challenges", "_plain_text", "plan"):
        monkeypatch.setattr(llm, name, lambda *a, name=name, **k: called.append(name))
    monkeypatch.setattr(llm, "parse_text", lambda *a, **k: None)
    monkeypatch.setattr(llm, "grounded_sources", lambda *a, **k: [])
    case_id = _sealed_case(client, monkeypatch)
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert called == [] and ev["llm_used"] is False
    assert ev["explanation_te"] and ev["testimony_te"]


def test_polish_runs_when_asked_for(client, monkeypatch):  # noqa: F811
    from app.agent import llm

    called = []
    _setenv(monkeypatch, LLM_POLISH="true")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "narrate", lambda *a, **k: called.append("narrate"))
    monkeypatch.setattr(llm, "translate", lambda *a, **k: None)
    monkeypatch.setattr(llm, "rephrase_challenges", lambda *a, **k: called.append("rephrase"))
    monkeypatch.setattr(llm, "_plain_text", lambda *a, **k: called.append("polish"))
    monkeypatch.setattr(llm, "parse_text", lambda *a, **k: None)
    monkeypatch.setattr(llm, "grounded_sources", lambda *a, **k: [])
    _sealed_case(client, monkeypatch)
    assert {"narrate", "rephrase", "polish"} <= set(called)


def test_the_level_is_the_same_whichever_the_llm_says(client, monkeypatch):  # noqa: F811
    """The planner could send a run to radar first, skipping the optical pair. It stays off."""
    from app.agent import llm

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "plan", lambda *a, **k: llm.PlanChoice("sar_first", {}, "x"))
    monkeypatch.setattr(llm, "parse_text", lambda *a, **k: None)
    monkeypatch.setattr(llm, "grounded_sources", lambda *a, **k: [])
    case_id = _sealed_case(client, monkeypatch)
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["optical"]["post"] is not None


def test_snippet_and_rationale_never_reach_a_reader(client, monkeypatch):  # noqa: F811
    assert "snippet" not in NewsItem.model_fields
    case_id = _sealed_case(client, monkeypatch)
    with session_scope() as s:
        row = s.query(EvidenceRow).filter_by(case_id=case_id).first()
        row.json = {**row.json, "news": [{"title": "t", "url": "https://x", "snippet": "model wrote this"}]}
        run_id = row.run_id
        from app.db import RunEvent

        event = s.query(RunEvent).filter_by(run_id=run_id).order_by(RunEvent.seq).first()
        event.payload = {**event.payload, "detail": {"rationale": "model wrote that", "error": "boom https://x?key=abc"}}
    assert "model wrote" not in client.get(f"/api/cases/{case_id}").text
    assert not any("rationale" in e["detail"] or "error" in e["detail"] for e in stream(client, run_id))


def test_a_planner_event_carries_no_rationale(client, monkeypatch):  # noqa: F811
    from app.agent import llm

    _setenv(monkeypatch, LLM_PLANNER="true")
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "plan", lambda *a, **k: llm.PlanChoice("search_optical", {}, "because the model said"))
    monkeypatch.setattr(llm, "parse_text", lambda *a, **k: None)
    monkeypatch.setattr(llm, "grounded_sources", lambda *a, **k: [])
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert "because the model said" not in json.dumps(events)


@pytest.mark.parametrize(("raw", "kept"), [
    ("14:30", "14:30"), ("25:00", None), ("9am", None), ("14:30:00", None), ("../..", None),
])
def test_an_llm_event_time_is_validated_as_patch_does(raw, kept):
    from app.agent import llm

    report = llm._to_report(llm._ReportSchema(transcript="t", event_time=raw))
    assert report.event_time == kept


@pytest.mark.parametrize("raw", ["2001-01-01", "2015-06-22", "2999-01-01", "0001-01-01"])
def test_an_llm_event_date_outside_the_range_is_dropped(raw):
    from app.agent import llm

    assert llm._to_report(llm._ReportSchema(transcript="t", event_date=raw)).event_date is None


def test_one_bad_case_cannot_stop_the_deadline_job(client, monkeypatch):  # noqa: F811
    from app import jobs
    from app.agent import claim_path

    bad, good = new_case(client), new_case(client)
    real = claim_path.for_case

    def flaky(case, *a, **k):
        if case.id == bad:
            raise ValueError("a bad row")
        return real(case, *a, **k)

    monkeypatch.setattr(claim_path, "for_case", flaky)
    with session_scope() as s:
        s.get(Case, good).status = "intimation_due"
    report = jobs.update_deadlines()
    assert report["cases_failed"] == [bad] and report["cases_changed"] >= 1
    with session_scope() as s:
        assert s.get(Case, good).status == "open"


def test_a_stored_time_that_is_not_a_clock_time_cannot_break_a_page(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    with session_scope() as s:
        s.get(Case, case_id).event_time = "not a time"
    assert client.get(f"/api/cases/{case_id}").status_code == 200


@pytest.mark.parametrize("text", [
    "You will get paid for this.", "The claim will be approved.", "Payment is guaranteed.",
    "You can report any time.", "You can report at any time.", "This proves the hail did it.",
    "The insurer must accept this.", "The insurer is required to accept this evidence.",
    "YES-TECH works at insurance-unit level.", "Inundation of paddy is covered.", "Seventy percent of the crop was lost.",
    "fifty per cent loss", "twenty-five percent of the field",
    "दावा मंज़ूर हो जाएगा", "भुगतान मिलेगा", "इसकी गारंटी है", "आप कभी भी सूचना दे सकते हैं", "यह साबित करता है",
    "बीमा कंपनी को यह स्वीकार करना होगा", "YES-TECH बीमा इकाई स्तर पर चलता है", "धान में जलभराव कवर है", "सत्तर प्रतिशत नुकसान",
    "ఆమోదిస్తారు", "డబ్బులు వస్తాయి", "హామీ ఇస్తున్నాం", "ఎప్పుడైనా నివేదించవచ్చు", "ఇది రుజువు చేస్తుంది",
    "బీమా సంస్థ దీన్ని అంగీకరించాలి", "YES-TECH బీమా యూనిట్ స్థాయిలో", "వరి ముంపు కవర్ అవుతుంది", "డెబ్బై శాతం నష్టం",
])
def test_the_validator_refuses_promises_in_every_language(text):
    result = validate.validate_text(text, {})
    assert not result.ok and result.banned, text


@pytest.mark.parametrize("text", [
    "This is not guaranteed.", "Its acceptance is not guaranteed.", "This does not prove the cause.",
    "That is consistent with the event, but it is not proof of the cause.", "इसकी कोई गारंटी नहीं",
    "इससे आपकी बात ग़लत साबित नहीं होती", "దీని అంగీకారానికి హామీ లేదు", "అది కారణానికి రుజువు కాదు",
    "The insurer may not accept this.", "Please report it now.",
])
def test_the_validator_leaves_honest_wording_alone(text):
    assert validate.validate_text(text, {}).banned == []


def test_the_templates_themselves_pass_the_new_denylist():
    ev = evidence()
    result = rubric.decide(ev)
    from app.evidence.schema import Verdict

    for level in ("strong", "moderate", "weak", "insufficient", "not_damage_likely_harvest"):
        ev.verdict = Verdict(level=level, headline_hi="h", headline_en="e", reasons=result.reasons,
                             caveats=result.caveats, falsifiers_checked=[], rubric_version="v3")
        for text in (*explain.template_explanation(ev, level), *testimony.templates(ev)):
            assert validate.validate_text(text, explain.allowed_numbers(ev)).banned == [], text


# G. Re-check honesty


def _reject_post(sc, *a, **k):
    return qa(sc.id, sc.date, "rejected", ["Q3: bad"]) if sc.id == "S2_POST" else qa(sc.id, sc.date)


def _recheck_rows(case_id):
    with session_scope() as s:
        return [(a.status, a.payload.get("basis")) for a in s.query(Action).filter_by(case_id=case_id, type="recheck")]


def test_a_deadline_shown_always_has_an_action_behind_it(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch, qa_scene=_reject_post, search_sar=lambda *a, **k: [])
    env = client.get(f"/api/cases/{case_id}").json()
    assert any(d["type"] == "recheck" for d in env["evidence"]["deadlines"])
    assert _recheck_rows(case_id) == [("open", "sentinel-2-revisit")]
    assert any(a["type"] == "recheck" and a["status"] == "open" for a in env["actions"])


def test_a_verdict_revised_away_from_a_recheck_removes_the_action():
    from types import SimpleNamespace

    from app.agent import graph

    with session_scope() as s:
        s.add(Case(id="c9", lat=29.5, lon=75.0, status="rechecking"))
        s.add(Action(case_id="c9", type="recheck", status="open", payload={"basis": "sentinel-2-revisit"}))
    ctx = SimpleNamespace(case_id="c9", archive_failed=False)
    ev = evidence()
    settled = replace(rubric.decide(ev), schedule_recheck=False)
    graph._sync_recheck(ctx, ev, settled, False)
    assert _recheck_rows("c9") == []
    with session_scope() as s:
        assert s.get(Case, "c9").status == "open"


def test_an_old_event_promises_no_recheck():
    from types import SimpleNamespace

    from app.agent import graph

    ev = evidence(optical=False, wx=_no_weather())
    ev.event.date = parse.today_ist() - timedelta(days=rubric.RECHECK_WINDOW_DAYS + 1)
    result = rubric.decide(ev)
    assert result.schedule_recheck and not rubric.recheck_possible(ev)
    ctx = SimpleNamespace(case_id="c9", archive_failed=False)
    assert graph._recheck_deadline(ctx, ev, result, False) is None
    assert explain.headlines("insufficient", "hail", recheck=False) == explain.NO_WINDOW_HEADLINES
    assert "next image" not in testimony.templates(ev)[1] and "window" in testimony.templates(ev)[1]


def test_a_slow_archive_can_still_be_retried_on_an_old_event():
    from types import SimpleNamespace

    from app.agent import graph

    ev = evidence(optical=False)
    ev.event.date = date(2024, 3, 3)
    ev.optical.scenes_considered = [qa("late", date(2024, 3, 10))]
    deadline = graph._recheck_deadline(SimpleNamespace(archive_failed=False), ev, rubric.decide(ev), False)
    assert deadline is not None and deadline.basis == "archive-retry"


def test_the_job_clips_its_search_to_the_window_and_closes_past_it(client, monkeypatch):  # noqa: F811
    from app import jobs

    searched = []
    case_id = _sealed_case(client, monkeypatch, qa_scene=_reject_post, search_sar=lambda *a, **k: [])
    install_fake_geo(monkeypatch, search_optical=lambda p, start, end: searched.append((start, end)) or [])
    with session_scope() as s:
        for a in s.query(Action).filter_by(case_id=case_id, type="recheck"):
            a.due_at = datetime.now(UTC) - timedelta(minutes=1)
    jobs.recheck_open_cases()
    assert searched == [(EVENT + timedelta(days=1), min(EVENT + timedelta(days=rubric.RECHECK_WINDOW_DAYS), parse.today_ist()))]

    with session_scope() as s:
        row = s.query(EvidenceRow).filter_by(case_id=case_id).first()
        old = (parse.today_ist() - timedelta(days=rubric.RECHECK_WINDOW_DAYS + 2)).isoformat()
        row.json = {**row.json, "event": {**row.json["event"], "date": old}, "optical": {"scenes_considered": []},
                    "neighbours": None}
        for a in s.query(Action).filter_by(case_id=case_id, type="recheck"):
            a.due_at = datetime.now(UTC) - timedelta(minutes=1)
    assert jobs.recheck_open_cases()["checked"] == 0
    assert _recheck_rows(case_id) == [("closed", "sentinel-2-revisit")]
    env = client.get(f"/api/cases/{case_id}").json()
    assert env["recheck_closed"] is True and not [a for a in env["actions"] if a["type"] == "recheck" and a["status"] == "open"]


def test_stuck_cases_cannot_starve_the_others(client, monkeypatch):  # noqa: F811
    from app import jobs

    _setenv(monkeypatch, RATE_INVESTIGATIONS_PER_HOUR=100)
    install_fake_geo(monkeypatch, search_optical=lambda *a, **k: [])
    with session_scope() as s:
        ids = []
        for i in range(jobs.MAX_RECHECKS_PER_TICK + 2):
            cid = f"case{i:02d}"
            ids.append(cid)
            s.add(Case(id=cid, lat=29.5, lon=75.0, event_date=parse.today_ist() - timedelta(days=2)))
            s.add(Plot(case_id=cid, geometry=SQUARE, area_ha=1.0, centroid_lon=75.0, centroid_lat=29.5, crs="EPSG:32643"))
            s.add(Run(id=f"run{i:02d}", case_id=cid, status="done"))
            s.add(EvidenceRow(run_id=f"run{i:02d}", case_id=cid, json={"optical": {"scenes_considered": []}}))
            s.add(Action(case_id=cid, type="recheck", status="open", payload={"basis": "sentinel-2-revisit"},
                         due_at=datetime.now(UTC) - timedelta(minutes=100 - i)))
        # The oldest due cases have a run active, so they cannot use up the tick's slots.
        s.add(Run(id="active0", case_id=ids[0], status="running"))
        s.add(Run(id="active1", case_id=ids[1], status="running"))
    first = jobs.recheck_open_cases()
    assert first["checked"] == jobs.MAX_RECHECKS_PER_TICK
    with session_scope() as s:
        s.query(Run).filter(Run.id.in_(("active0", "active1"))).update({"status": "done"})
    # The ones that found nothing wait their turn, so the rest come up.
    second = jobs.recheck_open_cases()
    assert second["checked"] == 2


# H. Restart and stuck states


def _provisional_row(client, monkeypatch, status="running", trigger="user"):  # noqa: F811
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    ev = evidence(optical=False)
    from app.evidence.schema import Verdict

    ev.case_id, ev.run_id = case_id, "dead"
    ev.verdict = Verdict(level="insufficient", headline_hi="h", headline_en="e", reasons=[rubric.STILL_COMPUTING],
                         caveats=[], falsifiers_checked=[], rubric_version="v3")
    ev.explanation_en = "will update"
    with session_scope() as s:
        s.add(Run(id="dead", case_id=case_id, status=status, trigger=trigger))
        s.add(EvidenceRow(run_id="dead", case_id=case_id, json=ev.model_dump(mode="json"), verdict_level="insufficient",
                          exhibits={"chips": {"status": "pending", "reason": None}, "sar": {"status": "done"}}))
    return case_id


def test_recovery_rewrites_a_stale_still_computing_verdict(client, monkeypatch):  # noqa: F811
    case_id = _provisional_row(client, monkeypatch)
    assert runner.recover_interrupted() == 1
    env = client.get(f"/api/cases/{case_id}").json()
    verdict = env["evidence"]["verdict"]
    assert verdict["reasons"] == [rubric.RUN_INTERRUPTED] and "restarted" in verdict["headline_en"]
    assert rubric.STILL_COMPUTING not in json.dumps(env) and "restarted" in env["evidence"]["explanation_en"]
    assert env["exhibits"]["chips"]["status"] == "failed" and env["exhibits"]["sar"]["status"] == "done"
    assert env["evidence"]["explanation_te"] and env["sealed"] is False and env["case"]["active_run_id"] is None


def test_recovery_resolves_a_retry_pending_on_the_original_row(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    with session_scope() as s:
        row = s.query(EvidenceRow).filter_by(case_id=case_id).first()
        row.exhibits = {**row.exhibits, "history": {"status": "pending", "reason": None}}
        s.add(Run(id="retry1", case_id=case_id, trigger="retry", status="running"))
    runner.recover_interrupted()
    env = client.get(f"/api/cases/{case_id}").json()
    assert env["exhibits"]["history"]["status"] == "failed" and "restarted" in env["exhibits"]["history"]["reason"]


def test_a_failed_run_leaves_nothing_pending(client, monkeypatch):  # noqa: F811
    from app.agent import graph

    case_id = _provisional_row(client, monkeypatch, status="done")
    monkeypatch.setattr(graph, "run_investigation", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    run_id, _ = runner.start_run(case_id)
    wait_done(client, run_id)
    assert client.get(f"/api/cases/{case_id}").json()["exhibits"]["chips"]["status"] == "failed"


def test_retry_with_missing_inputs_is_a_clean_409(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    with session_scope() as s:
        row = s.query(EvidenceRow).filter_by(case_id=case_id).first()
        row.json = {**row.json, "optical": {"scenes_considered": []}}
        row.exhibits = {**row.exhibits, "history": {"status": "failed", "reason": "x"}, "chips": {"status": "failed", "reason": "x"}}
    for name in ("history", "chips"):
        response = client.post(f"/api/cases/{case_id}/exhibits/{name}/retry")
        assert response.status_code == 409 and response.json()["detail"]["code"] == "exhibit_inputs_missing"


def test_a_sealed_row_is_preferred_over_a_newer_unsealed_one(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    sealed_hash = client.get(f"/api/cases/{case_id}").json()["evidence"]["evidence_hash"]
    from app.evidence.schema import Verdict

    ev = evidence()
    ev.case_id, ev.run_id = case_id, "newer"
    ev.verdict = Verdict(level="weak", headline_hi="h", headline_en="e", reasons=[], caveats=[], falsifiers_checked=[], rubric_version="v3")
    with session_scope() as s:
        s.add(Run(id="newer", case_id=case_id, status="interrupted"))
        s.add(EvidenceRow(run_id="newer", case_id=case_id, json=ev.model_dump(mode="json"), verdict_level="weak",
                          created_at=datetime.now(UTC) + timedelta(hours=1)))
    env = client.get(f"/api/cases/{case_id}").json()
    assert env["evidence"]["evidence_hash"] == sealed_hash and env["sealed"] is True


def test_a_retry_uses_the_sealed_polygon_and_not_a_redrawn_one(client, monkeypatch):  # noqa: F811
    seen = []

    def slow_then_seen(polygon, *a, **k):
        seen.append(polygon)
        raise RuntimeError("down")

    case_id = _sealed_case(client, monkeypatch, timeline=slow_then_seen)
    sealed = client.get(f"/api/cases/{case_id}").json()["evidence"]["replay"]["polygon"]
    redrawn = {"type": "Polygon", "coordinates": [[[75.05, 29.55], [75.0514, 29.55], [75.0514, 29.5514],
                                                   [75.05, 29.5514], [75.05, 29.55]]]}
    assert client.put(f"/api/cases/{case_id}/plot", json={"polygon": redrawn}).status_code == 200
    seen.clear()
    retried = client.post(f"/api/cases/{case_id}/exhibits/timeline/retry")
    assert retried.status_code == 200
    wait_done(client, retried.json()["run_id"])
    assert seen == [sealed] and sealed != redrawn


# I. Dates


@pytest.mark.parametrize(("value", "code"), [
    ("2015-06-22", "event_date_too_early"), ("0001-01-01", "event_date_too_early"), ("2000-02-29", "event_date_too_early"),
    ("9999-12-31", "event_date_future"),
])
def test_a_date_with_no_satellite_window_is_refused_in_every_language(client, value, code):  # noqa: F811
    case_id = new_case(client)
    response = client.patch(f"/api/cases/{case_id}", json={"event_date": value})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == code and all(detail[f"message_{x}"] for x in ("hi", "en", "te"))


def test_the_earliest_date_is_allowed(client):  # noqa: F811
    case_id = new_case(client)
    assert client.patch(f"/api/cases/{case_id}", json={"event_date": "2015-06-23"}).status_code == 200


def test_text_cannot_produce_a_date_outside_the_range():
    assert parse.extract_date("2014-01-01", date(2016, 1, 1))[0] is None
    assert parse.extract_date("2014-01-01", date(2016, 1, 1))[1] == "too_old_refused:2014-01-01"
    assert parse.extract_date("2030-01-01", date(2026, 1, 1))[1] == "future_date_refused:2030-01-01"


def test_a_bad_date_already_in_the_database_cannot_start_a_run_or_overflow(client, monkeypatch):  # noqa: F811
    install_fake_geo(monkeypatch)
    case_id = new_case(client)
    with session_scope() as s:
        s.get(Case, case_id).event_date = date(1, 1, 1)
    response = client.post(f"/api/cases/{case_id}/investigate")
    assert response.status_code == 422 and response.json()["detail"]["code"] == "event_date_too_early"
    run_id, _ = runner.start_run(case_id)
    assert wait_done(client, run_id)[-1]["detail"]["status"] == "needs_input"


# J. Error leaks


def test_an_unhandled_error_gives_a_reference_and_no_detail(fake_weather, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "_case_dict", lambda *a: (_ for _ in ()).throw(RuntimeError("secret https://x?key=abc")))
    with TestClient(main.app, raise_server_exceptions=False) as c:
        r = c.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "text": "hail"})
        response = c.get(f"/api/cases/{r.json()['case_id']}")
    assert response.status_code == 500 and "secret" not in response.text and response.json()["error_ref"]


@pytest.mark.parametrize("path", [
    "/api/artifacts/" + "a" * 5000, "/api/artifacts/%00", "/api/artifacts/x%00y", "/%00", "/" + "a" * 5000,
    "/api/artifacts/../../etc/passwd", "/api/verify/%00",
])
def test_odd_paths_are_refused_cleanly(fake_weather, path, tmp_path):
    from app import main

    (tmp_path / "index.html").write_text("x")
    with TestClient(main.app, raise_server_exceptions=False) as c:
        response = c.get(path)
    assert response.status_code != 500 and (path.startswith("/api/verify") or 400 <= response.status_code < 500 or response.text)


def test_a_long_or_nul_case_id_is_a_404(client):  # noqa: F811
    assert client.get("/api/cases/" + "a" * 5000).status_code == 404
    assert client.get("/api/cases/a%00b").status_code == 404


@pytest.mark.parametrize("header", ["²", "٣", "-1", "99999999999999999999999", "abc"])
def test_an_odd_last_event_id_is_ignored(client, monkeypatch, header):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    run_id = client.get(f"/api/cases/{case_id}").json()["case"]["latest_run"]["id"]
    with client.stream("GET", f"/api/runs/{run_id}/stream", headers={"Last-Event-ID": header.encode()}) as r:
        assert r.status_code == 200
        assert any(line.startswith("data: ") for line in r.iter_lines())


def test_an_after_beyond_any_integer_is_a_422(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    run_id = client.get(f"/api/cases/{case_id}").json()["case"]["latest_run"]["id"]
    assert client.get(f"/api/runs/{run_id}/stream?after={10 ** 30}").status_code == 422


def test_scrub_removes_keys_and_signed_url_parts():
    text = errors.scrub("GET https://x/y?apikey=SECRET1&lat=1 and https://b?se=2030&sig=SECRET2&sv=2020 key=SECRET3")
    assert "SECRET" not in text and "lat=1" in text


def test_a_weather_failure_never_carries_the_api_key(monkeypatch):
    import httpx

    from app.tools import weather as weather_tool

    _setenv(monkeypatch, OPEN_METEO_API_KEY="SECRETKEY")
    with pytest.raises(weather_tool.WeatherUnavailable) as caught:
        weather_tool._load(29.5, 75.0, date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3))
    assert "SECRETKEY" not in str(caught.value) and "apikey" not in str(caught.value)
    assert httpx is not None


def test_the_radar_route_says_nothing_about_the_url(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, OPEN_METEO_API_KEY="SECRETKEY")
    response = client.get("/api/radar")
    assert response.status_code == 503 and "SECRETKEY" not in response.text and "http" not in response.text
    assert response.json()["detail"]["message_te"]


def test_a_tool_failure_shows_no_raw_exception_in_the_trace(client, monkeypatch):  # noqa: F811
    def down(*a, **k):
        raise RuntimeError("https://archive.example/x?sig=SECRETSIG")

    install_fake_geo(monkeypatch, search_optical=down)
    case_id = new_case(client)
    events = wait_done(client, client.post(f"/api/cases/{case_id}/investigate").json()["run_id"])
    assert "SECRETSIG" not in json.dumps(events) and "archive.example" not in json.dumps(events)


def test_a_stored_raw_run_error_is_not_shown(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    with session_scope() as s:
        run = s.query(Run).filter_by(case_id=case_id).first()
        run.error = "RuntimeError: https://x?key=abc"
    latest = client.get(f"/api/cases/{case_id}").json()["case"]["latest_run"]
    assert "https" not in latest["error"] and "RuntimeError" not in latest["error"]


def test_the_httpx_logger_is_at_warning():
    import logging

    from app import main  # noqa: F401

    assert logging.getLogger("httpx").level == logging.WARNING


def test_a_verify_outage_shows_no_raw_exception(client, monkeypatch):  # noqa: F811
    from app import verify

    case_id = _sealed_case(client, monkeypatch)
    h = client.get(f"/api/cases/{case_id}").json()["evidence"]["evidence_hash"]

    def down(core):
        raise RuntimeError("https://archive.example/x?sig=SECRETSIG")

    install_fake_geo(monkeypatch, replay=down)
    with client.stream("GET", f"/api/verify/{h}") as response:
        body = "".join(response.iter_text())
    assert "SECRETSIG" not in body and "archive.example" not in body and verify is not None


# K. What "verified" covers


def _with_verdict(ev, level="strong"):
    from app.evidence.schema import Verdict

    ev.verdict = Verdict(level=level, headline_hi="h", headline_en="e", reasons=[], caveats=[], falsifiers_checked=[], rubric_version="v3")
    return ev


def test_the_digest_moves_with_the_level_and_its_inputs_and_nothing_else():
    ev = _with_verdict(evidence())
    base = rubric.verdict_digest(ev)
    assert rubric.verdict_digest(_with_verdict(evidence(), "weak")) != base
    assert rubric.verdict_digest(_with_verdict(evidence(wx=weather(max_mm=99.0)))) != base
    assert rubric.verdict_digest(_with_verdict(evidence(alerts=[an_alert()]))) != base
    ev.news = [NewsItem(title="t", url="https://x")]
    ev.explanation_en = "reworded"
    assert rubric.verdict_digest(ev) == base


def test_a_record_sealed_before_the_digest_keeps_its_hash():
    from app.agent.graph import canonical_json, evidence_hash

    core = ReplayCore(engine_version="v", polygon={}, event_date=EVENT, seed=1, numbers={})
    legacy = {k: v for k, v in core.model_dump(mode="json").items() if k != "verdict_digest"}
    import hashlib

    assert evidence_hash(core) == hashlib.sha256(canonical_json(legacy).encode()).hexdigest()
    assert evidence_hash(core.model_copy(update={"verdict_digest": "a"})) != evidence_hash(core)


def test_sealing_includes_the_digest_and_a_changed_verdict_is_called_tampering(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["replay"]["verdict_digest"]
    h = ev["evidence_hash"]
    with client.stream("GET", f"/api/verify/{h}") as response:
        body = "".join(response.iter_text())
    assert '"verdict_check": "intact"' in body
    with session_scope() as s:
        row = s.query(EvidenceRow).filter_by(case_id=case_id).first()
        row.json = {**row.json, "verdict": {**row.json["verdict"], "level": "strong" if ev["verdict"]["level"] != "strong" else "weak"}}
    with client.stream("GET", f"/api/verify/{h}") as response:
        body = "".join(response.iter_text())
    assert '"status": "tampered"' in body and '"verdict_changed": true' in body
    with session_scope() as s:
        row = s.query(EvidenceRow).filter_by(case_id=case_id).first()
        row.json = {**row.json, "verdict": ev["verdict"], "weather": {**ev["weather"], "max_daily_mm": 999.0}}
    with client.stream("GET", f"/api/verify/{h}") as response:
        assert '"status": "tampered"' in "".join(response.iter_text())


def test_when_cases_share_a_hash_the_most_recent_is_used(monkeypatch):
    from app import verify

    with session_scope() as s:
        for name, when in (("old", datetime(2026, 1, 1, tzinfo=UTC)), ("new", datetime(2026, 6, 1, tzinfo=UTC))):
            s.add(Case(id=name, lat=1, lon=1))
            s.add(Run(id=f"r{name}", case_id=name))
            s.add(EvidenceRow(run_id=f"r{name}", case_id=name, json={"from": name}, evidence_hash="samehash",
                              replay_core={"x": 1}, created_at=when))
    assert verify.load_core("samehash")[1] == {"from": "new"}


# O. Smaller items


def test_the_add_on_routes_cite_a_grievance_clause(client, monkeypatch):  # noqa: F811
    from app.agent import graph

    for route in ("localized_addon", "post_harvest_addon", "area_yield_basic"):
        path = type("P", (), {"route": route})
        assert "grievance" in [name for name, _ in graph._rule_names_for(path)], route
    case_id = _sealed_case(client, monkeypatch)
    client.patch(f"/api/cases/{case_id}", json={"insured": "yes", "crop_stage": "standing"})
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    wait_done(client, run_id)
    ev = client.get(f"/api/cases/{case_id}").json()["evidence"]
    assert ev["claim_path"]["route"] == "localized_addon" and any(c["clause_id"] == "30.2" for c in ev["policy"])


def test_a_future_submission_time_is_refused(client):  # noqa: F811
    case_id = new_case(client)
    future = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    response = client.post(f"/api/cases/{case_id}/submission", json={"reference_no": "A1", "submitted_at": future})
    assert response.status_code == 422 and response.json()["detail"]["code"] == "submitted_at_future"
    assert client.post(f"/api/cases/{case_id}/submission", json={"reference_no": "A1", "submitted_at": "0001-01-01T00:00:00"}).status_code == 422
    assert client.post(f"/api/cases/{case_id}/submission", json={"reference_no": "A1"}).status_code == 200


def test_met_says_self_reported_in_every_language():
    from app.pdf.render import L

    assert "self-reported" in L["en"]["met"] and "बताने" in L["hi"]["met"] and "స్వయంగా" in L["te"]["met"]


def test_radar_cells_say_what_put_them_there():
    from app.tools import weather as weather_tool
    from app.tools.weather import IST

    now = datetime(2026, 10, 25, 12, tzinfo=IST)
    point = ("Sirsa", "Haryana", 29.5, 75.0)

    def cell(rain, code):
        data = {"daily": {"time": ["2026-10-25"], "precipitation_sum": [rain], "wind_gusts_10m_max": [10.0], "weather_code": [code]},
                "hourly": {"time": ["2026-10-25T10:00"], "weather_code": [code]}}
        return weather_tool._radar_cell(point, data, now)

    assert cell(30.0, 3)["signal"] == "heavy_rain"
    assert cell(1.0, 96)["signal"] == "hail_code"
    assert cell(1.0, 95)["signal"] == "thunder_code"


def test_a_polygon_with_a_hole_is_refused(client):  # noqa: F811
    from app.agent.plot import PlotRejected, validate_polygon

    holed = {"type": "Polygon", "coordinates": [
        [[75.03, 29.53], [75.04, 29.53], [75.04, 29.54], [75.03, 29.54], [75.03, 29.53]],
        [[75.033, 29.533], [75.036, 29.533], [75.036, 29.536], [75.033, 29.536], [75.033, 29.533]],
    ]}
    with pytest.raises(PlotRejected) as caught:
        validate_polygon(holed)
    assert caught.value.code == "polygon_has_hole"
    case_id = new_case(client)
    response = client.put(f"/api/cases/{case_id}/plot", json={"polygon": holed})
    assert response.status_code == 422 and response.json()["detail"]["message_te"]


def _pdf_html(lang, **updates):
    from app.evidence.schema import ClaimPath
    from app.pdf.render import build_html

    ev = _with_verdict(evidence())
    ev.verdict.reasons = ["plot NDVI change -0.25"]
    ev.evidence_hash = "ab" * 32
    ev.claim_path = ClaimPath(route="localized_addon", unknowns=["state_notification", "crop_notified"], reasons=["r"])
    for key, value in updates.items():
        setattr(ev, key, value)
    return build_html(ev, {"district": "Sirsa", "state": "Haryana"}, [], lang, get_settings().artifacts_dir / "c" / "t")


def test_the_hindi_pdf_has_no_english_labels_left():
    html = _pdf_html("hi")
    for word in ("<b>Event</b>", "<b>Crop</b>", "<b>District</b>", "localized_addon", "state_notification",
                 "Replay numbers", "<th>Date</th>", "<th>Field</th>", " Nov ", " Oct "):
        assert word not in html, word
    assert "स्थानीय आपदा" in html and "<b>घटना</b>" in html and "ओलावृष्टि" in html and "अक्टूबर" in html
    assert "अंग्रेज़ी में" in html  # the machine-written reasons say what language they are in
    assert "छेड़छाड़" in html


def test_the_telugu_pdf_is_labelled_too():
    html = _pdf_html("te")
    assert "స్థానిక విపత్తు" in html and "<b>సంఘటన</b>" in html and "ఆంగ్లంలో" in html and "localized_addon" not in html


def test_the_pdf_states_what_was_recomputed_near_the_top():
    html = _pdf_html("en")
    scope = "Satellite numbers are recomputed; the verdict and weather are checked for tampering only."
    assert html.index(scope) < html.index('class="meta"')


# N. Deployment


def test_links_use_the_request_origin_when_no_public_url_is_set(client, monkeypatch):  # noqa: F811
    case_id = _sealed_case(client, monkeypatch)
    env = client.get(f"/api/cases/{case_id}").json()
    h = env["evidence"]["evidence_hash"]
    draft = next(a for a in env["actions"] if a["type"] == "intimation_draft")
    if draft["payload"].get("available"):
        assert f"http://testserver/verify/{h}" in draft["payload"]["text_en"]


def test_forwarded_host_counts_only_under_trust_proxy(monkeypatch):
    from starlette.requests import Request

    def request(headers=()):
        return Request({"type": "http", "method": "GET", "scheme": "http", "path": "/", "query_string": b"",
                        "server": ("internal", 8080), "headers": list(headers)})

    forwarded = [(b"x-forwarded-host", b"public.example"), (b"x-forwarded-proto", b"https")]
    assert limits.web_base(request(forwarded)) == "http://internal:8080"
    _setenv(monkeypatch, TRUST_PROXY="true")
    assert limits.web_base(request(forwarded)) == "https://public.example"
    _setenv(monkeypatch, PUBLIC_WEB_URL="https://set.example/")
    assert limits.web_base(request(forwarded)) == "https://set.example"


def test_a_missing_public_url_is_warned_about_at_startup(fake_weather, caplog):
    from app import main

    with caplog.at_level("WARNING"), TestClient(main.app):
        pass
    assert any("PUBLIC_WEB_URL" in r.message for r in caplog.records)


# warm_demo


def test_warm_demo_pauses_when_the_server_says_to(monkeypatch):
    import httpx

    from scripts import warm_demo

    responses = [httpx.Response(429, headers={"retry-after": "7"}, json={}), httpx.Response(200, json={"ok": True})]
    slept = []
    monkeypatch.setattr(warm_demo.time, "sleep", slept.append)
    assert warm_demo._sent(lambda: responses.pop(0), "x", 100).json() == {"ok": True} and slept == [8.0]
    with pytest.raises(RuntimeError, match="limit-wait"):
        warm_demo._sent(lambda: httpx.Response(429, headers={"retry-after": "7"}), "x", 1)


def test_verify_run_rows_are_untouched_by_a_rate_limited_scan(client, monkeypatch):  # noqa: F811
    _setenv(monkeypatch, RATE_VERIFY_PER_HOUR=0)
    case_id = _sealed_case(client, monkeypatch)
    h = client.get(f"/api/cases/{case_id}").json()["evidence"]["evidence_hash"]
    assert client.get(f"/api/verify/{h}").status_code == 429
    with session_scope() as s:
        assert s.query(VerifyRun).count() == 0
