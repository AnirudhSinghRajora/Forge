"""The Gemini features of Addendum 9, on a fake client. Nothing here proves Gemini's answers are any
good; `python -m app.agent.llm --selftest` is the real test and needs a key. These prove the fences:
what a model says cannot reach the level or the hash, and what fails validation is never shown."""
import base64
import copy
import io
import json
import time
import types
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app import config, limits
from app.agent import advisory, llm, witness
from app.db import EvidenceRow, session_scope
from app.evidence.schema import Chip, Verdict
from tests.conftest import EVENT, POST_ID, PRE_ID, evidence, install_fake_geo, placebo
from tests.test_api import new_case, wait_done

TALL_TALE = "आपका नतीजा मज़बूत है और आपको पैसा मिलेगा: ₹50000, 99% नुकसान।"


class FakeGemini:
    """Answers each capability from a table, keyed by a phrase in its prompt. A capability with no
    answer raises, the way a failed call does."""

    def __init__(self):
        self.replies = {}
        self.calls = []
        self.interactions = types.SimpleNamespace(create=self.create)
        self.models = types.SimpleNamespace(generate_content=self.refuse, embed_content=self.refuse)

    def create(self, *, model, input, **kwargs):
        text = " ".join(p["text"] for p in input if p.get("type") == "text") if isinstance(input, list) else input
        self.calls.append({"model": model, "input": input, **kwargs})
        for phrase, reply in self.replies.items():
            if phrase in text:
                if callable(reply):
                    reply = reply()
                return types.SimpleNamespace(output_text=json.dumps(reply, ensure_ascii=False))
        raise RuntimeError("no scripted reply")

    def refuse(self, **kwargs):
        raise RuntimeError("no such surface in this fake")


ASK = "about their own crop-loss evidence record"
CHECK = "Compare a farmer's statement"
LOOK = "These are satellite images"
PARSE = "You parse an Indian farmer"


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    config.get_settings.cache_clear()
    fake = FakeGemini()
    monkeypatch.setattr(llm, "client", lambda: fake)
    yield fake
    config.get_settings.cache_clear()


@pytest.fixture
def client(fake_weather):
    from app import main

    with TestClient(main.app) as c:
        yield c


def _png(colour=(40, 120, 40)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def render_chips(polygon, pre, post, out_dir, *rest):
    out_dir.mkdir(parents=True, exist_ok=True)
    chips = []
    for kind, scene_id, when in (("true_colour_pre", pre, EVENT - timedelta(days=7)),
                                 ("true_colour_post", post, EVENT + timedelta(days=5)),
                                 ("ndvi_pre", pre, EVENT - timedelta(days=7)),
                                 ("ndvi_post", post, EVENT + timedelta(days=5))):
        path = out_dir / f"{kind}.png"
        path.write_bytes(_png())
        chips.append(Chip(kind=kind, path=str(path), scene_id=scene_id, date=when, bounds=(75, 29, 76, 30)))
    return chips


def _row(case_id):
    with session_scope() as s:
        row = s.scalars(select(EvidenceRow).where(EvidenceRow.case_id == case_id)).first()
        return types.SimpleNamespace(json=copy.deepcopy(row.json), exhibits=copy.deepcopy(row.exhibits),
                                     level=row.verdict_level, hash=row.evidence_hash,
                                     core=copy.deepcopy(row.replay_core), run_id=row.run_id)


def _sealed(client, monkeypatch, text="25 Oct hail cotton"):
    install_fake_geo(monkeypatch, render_chips=render_chips)
    case_id = new_case(client, text=text)
    run_id = client.post(f"/api/cases/{case_id}/investigate").json()["run_id"]
    wait_done(client, run_id)
    assert _row(case_id).hash
    return case_id


def _settled(case_id, name, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        entry = (_row(case_id).exhibits or {}).get(name)
        if entry and entry["status"] != "pending":
            return entry
        time.sleep(0.05)
    raise AssertionError(f"{name} did not settle")


def with_verdict(ev, level="weak"):
    ev.verdict = Verdict(level=level, headline_hi="ह", headline_en="e", reasons=["r"], caveats=["c"],
                         falsifiers_checked=[], rubric_version="v")
    ev.explanation_hi, ev.explanation_en, ev.explanation_te = "हिंदी व्याख्या", "English explanation", "తెలుగు వివరణ"
    return ev


# 1. Ask the witness


def test_a_grounded_answer_comes_back_with_what_it_cites(gemini):
    gemini.replies[ASK] = {"covered": True, "answer": "आपका बदलाव -0.25 है, इसलिए नतीजा ऐसा है।",
                           "cited_fields": ["optical.plot_delta_ndvi", "verdict.level", "invented.field"],
                           "cited_clause_ids": []}
    out = witness.ask("मेरा नतीजा कमज़ोर क्यों है?", "en", with_verdict(evidence()))
    assert out["llm_used"] and out["covered"] and out["lang"] == "hi"
    assert out["evidence_fields"] == ["optical.plot_delta_ndvi", "verdict.level"]  # never an invented one


@pytest.mark.parametrize("answer, why", [
    ("आपका बदलाव -0.99 है।", "a number not in the evidence"),
    ("आपको पैसा मिलेगा।", "a promise"),
    ("आपको ₹5000 मिलेंगे।", "rupees"),
    ("Your change is -0.25.", "not in the asked language"),
])
def test_a_bad_answer_is_never_shown(gemini, answer, why):
    gemini.replies[ASK] = {"covered": True, "answer": answer, "cited_fields": ["verdict.level"], "cited_clause_ids": []}
    out = witness.ask("मेरा नतीजा कमज़ोर क्यों है?", "hi", with_verdict(evidence()))
    assert answer not in out["answer"], why
    assert out["llm_used"] is False and out["answer"] == "हिंदी व्याख्या"


def test_an_answer_that_cites_nothing_is_not_shown(gemini):
    gemini.replies[ASK] = {"covered": True, "answer": "आपका नतीजा कमज़ोर है।", "cited_fields": ["made.up"], "cited_clause_ids": ["9.9.9"]}
    assert witness.ask("मेरा नतीजा कमज़ोर क्यों है?", "hi", with_verdict(evidence()))["llm_used"] is False


def test_what_the_record_does_not_cover_is_refused(gemini):
    gemini.replies[ASK] = {"covered": False, "answer": ""}
    out = witness.ask("Who won the cricket world cup?", "en", with_verdict(evidence()))
    assert out["covered"] is False and out["answer"] == witness.REFUSAL["en"] and out["citations"] == []


def test_a_hung_or_failing_model_falls_back(gemini):
    out = witness.ask("why is my result weak?", "en", with_verdict(evidence()))  # nothing scripted: it raises
    assert out["answer"] == "English explanation" and out["llm_used"] is False and out["mode"] == "record"


def test_without_a_key_the_record_still_answers_in_fixed_words():
    ev = with_verdict(evidence())
    steps = {"hi": {"next_steps": ["अपने बैंक से पूछें।"]}, "en": {"next_steps": ["Ask your bank."]}, "te": {"next_steps": ["బ్యాంకును అడగండి."]}}
    assert witness.ask("why is my result weak?", "en", ev)["answer"] == "English explanation"
    assert witness.ask("मुझे अब क्या करना चाहिए?", "en", ev, steps)["answer"] == "अपने बैंक से पूछें।"
    assert witness.ask("ఇప్పుడు ఏం చేయాలి?", "en", ev, steps)["answer"] == "బ్యాంకును అడగండి."
    refused = witness.ask("Who won the cricket world cup?", "en", ev)
    assert refused["covered"] is False and refused["llm_used"] is False


def test_a_question_about_a_rule_still_goes_to_the_rule():
    out = witness.ask("How long do I have to report hail damage?", "en", with_verdict(evidence()))
    assert out["mode"] == "policy" and out["citations"]


def test_paddy_inundation_stays_with_the_fixed_text(gemini):
    gemini.replies[ASK] = {"covered": True, "answer": "Paddy inundation is covered.", "cited_fields": ["verdict.level"]}
    out = witness.ask("Is paddy flood damage covered?", "en", with_verdict(evidence()))
    assert "cannot say it is covered" in out["answer"] and not gemini.calls


def test_the_model_sees_no_ids_locations_or_hash():
    facts = witness.evidence_facts(with_verdict(evidence()))
    text = json.dumps(facts, default=str)
    assert PRE_ID not in text and POST_ID not in text and "75.03" not in text and "coordinates" not in text
    assert facts["verdict.level"] == "weak" and facts["optical.plot_delta_ndvi"] == -0.25


def test_ask_cannot_change_the_level_or_the_hash(client, monkeypatch, gemini):
    gemini.replies[ASK] = {"covered": True, "answer": "Your result is strong now.", "cited_fields": ["verdict.level"]}
    case_id = _sealed(client, monkeypatch)
    before = _row(case_id)
    answered = client.post(f"/api/cases/{case_id}/ask", json={"question": "why is my result weak?", "lang": "en"})
    assert answered.status_code == 200 and answered.json()["llm_used"]
    after = _row(case_id)
    assert (after.level, after.hash, after.core, after.json) == (before.level, before.hash, before.core, before.json)


# 2. Spots contradictions


def test_a_contradiction_is_one_question_stored_outside_the_record(client, monkeypatch, gemini):
    gemini.replies[CHECK] = {"found": True, "about": "date", "question_hi": "क्या घटना किसी और दिन हुई थी?",
                             "question_en": "Could this have happened on another day?",
                             "question_te": "ఇది వేరే రోజున జరిగిందా?", "cited_fields": ["event.date", "made.up"]}
    case_id = _sealed(client, monkeypatch)
    before = _row(case_id)
    entry = _settled(case_id, advisory.STATEMENT_CHECK)
    assert entry["question"]["about"] == "date" and entry["question"]["cited_fields"] == ["event.date"]
    after = _row(case_id)
    assert (after.level, after.hash, after.core, after.json) == (before.level, before.hash, before.core, before.json)
    assert advisory.STATEMENT_CHECK not in json.dumps(after.core)


@pytest.mark.parametrize("reply", [
    {"found": True, "about": "date", "question_hi": "क्या पैसा मिलेगा?", "question_en": "Is it another day?", "question_te": "వేరే రోజా?"},
    {"found": True, "about": "date", "question_hi": "क्या 13 तारीख़ थी?", "question_en": "Was it the 13th?", "question_te": "13వ తేదీనా?"},
    {"found": True, "about": "date", "question_hi": "तारीख़ ग़लत है।", "question_en": "The date is wrong.", "question_te": "తేదీ తప్పు."},
    {"found": True, "about": "none", "question_hi": "क्या?", "question_en": "What?", "question_te": "ఏమిటి?"},
])
def test_a_bad_question_is_dropped(gemini, reply, monkeypatch):
    gemini.replies[CHECK] = reply
    stored = {}
    monkeypatch.setattr(advisory, "_store", lambda run_id, name, entry: stored.update({name: entry}))
    advisory.run_statement_check("r", with_verdict(evidence()), "कल ओले गिरे", "standing")
    assert stored[advisory.STATEMENT_CHECK]["status"] == "failed"
    assert "question" not in stored[advisory.STATEMENT_CHECK]


def test_no_statement_means_nothing_to_compare(gemini):
    assert advisory.statement_input(None, "unknown", evidence()) is None
    assert advisory.statement_input("कल ओले गिरे", None, evidence()) is not None


def test_the_farmers_answer_goes_through_patch_and_leaves_the_seal(client, monkeypatch, gemini):
    case_id = _sealed(client, monkeypatch)
    before = _row(case_id)
    patched = client.patch(f"/api/cases/{case_id}", json={"crop_stage": "cut_and_spread"})
    assert patched.status_code == 200 and patched.json()["crop_stage"] == "cut_and_spread"
    after = _row(case_id)
    assert (after.level, after.hash, after.core, after.json) == (before.level, before.hash, before.core, before.json)


# 3. Second opinion on images


def test_the_second_opinion_sends_the_chips_and_stays_out_of_the_seal(client, monkeypatch, gemini):
    gemini.replies[LOOK] = {"description_hi": "खेत का रंग भूरा हुआ।", "description_en": "The field turned browner.",
                            "description_te": "పొలం రంగు గోధుమగా మారింది.", "visible_change": "clear", "consistent": "yes"}
    case_id = _sealed(client, monkeypatch)
    entry = _settled(case_id, advisory.IMAGE_OPINION)
    assert entry["status"] == "done" and entry["opinion"]["needs_person"] is False
    assert entry["opinion"]["description_en"] == "The field turned browner."
    call = next(c for c in gemini.calls if isinstance(c["input"], list) and LOOK in c["input"][0]["text"])
    images = [p for p in call["input"] if p["type"] == "image"]
    assert len(images) == 4 and all(p["mime_type"] == "image/png" for p in images)
    assert base64.b64decode(images[0]["data"])[:4] == b"\x89PNG"
    row = _row(case_id)
    assert row.level == row.json["verdict"]["level"]
    assert "opinion" not in json.dumps(row.core) and "opinion" not in json.dumps(row.json)
    shown = client.get(f"/api/cases/{case_id}").json()
    assert shown["exhibits"][advisory.IMAGE_OPINION]["opinion"]["visible_change"] == "clear"


def test_a_disagreement_asks_for_a_person_and_moves_nothing(client, monkeypatch, gemini):
    gemini.replies[LOOK] = {"description_hi": "कोई बदलाव नहीं दिखता।", "description_en": "No change is visible.",
                            "description_te": "మార్పు కనిపించడం లేదు.", "visible_change": "none", "consistent": "no"}
    case_id = _sealed(client, monkeypatch)
    entry = _settled(case_id, advisory.IMAGE_OPINION)
    assert entry["opinion"]["needs_person"] is True
    plain = _sealed_without_gemini(client, monkeypatch)
    row, other = _row(case_id), _row(plain)
    assert row.level == other.level and row.hash == other.hash


def _sealed_without_gemini(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    config.get_settings.cache_clear()
    case_id = _sealed(client, monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    config.get_settings.cache_clear()
    return case_id


def test_hostile_answers_everywhere_give_the_same_level_and_hash_as_no_key(client, monkeypatch, gemini):
    gemini.replies.update({
        ASK: {"covered": True, "answer": TALL_TALE, "cited_fields": ["verdict.level"]},
        CHECK: {"found": True, "about": "event", "question_hi": TALL_TALE, "question_en": "You lied?", "question_te": "?"},
        LOOK: {"description_hi": TALL_TALE, "description_en": "Proves the hail.", "description_te": "x", "visible_change": "clear", "consistent": "no"},
    })
    with_key = _sealed(client, monkeypatch)
    assert _settled(with_key, advisory.STATEMENT_CHECK)["status"] == "failed"
    assert _settled(with_key, advisory.IMAGE_OPINION)["status"] == "failed"
    no_key = _sealed_without_gemini(client, monkeypatch)
    a, b = _row(with_key), _row(no_key)
    assert a.level == b.level and a.hash == b.hash
    assert (a.exhibits or {}).get("chips", {}).get("status") == "done"
    assert advisory.IMAGE_OPINION not in (b.exhibits or {})  # no key: no entry claims anything


def test_no_key_means_no_call_and_no_entry(client, monkeypatch):
    case_id = _sealed(client, monkeypatch)
    assert not set(advisory.NAMES) & set(_row(case_id).exhibits)
    assert client.post(f"/api/cases/{case_id}/advisories").json() == {"gemini": False, "started": []}


def test_the_seal_does_not_wait_for_a_slow_model(client, monkeypatch, gemini):
    release = []

    def stuck():
        deadline = time.time() + 20
        while not release and time.time() < deadline:
            time.sleep(0.02)
        return {"found": False}

    gemini.replies[CHECK] = stuck
    gemini.replies[LOOK] = stuck
    case_id = _sealed(client, monkeypatch)  # asserts the hash is there
    try:
        shown = client.get(f"/api/cases/{case_id}").json()
        assert shown["sealed"] is True
        assert shown["exhibits"][advisory.STATEMENT_CHECK]["status"] == "pending"
    finally:
        release.append(True)


def test_a_late_entry_survives_the_run_that_outlives_it(client, monkeypatch, gemini):
    gemini.replies[LOOK] = {"description_hi": "भूरा।", "description_en": "Browner.", "description_te": "గోధుమ.",
                            "visible_change": "clear", "consistent": "yes"}
    case_id = _sealed(client, monkeypatch)
    entry = _settled(case_id, advisory.IMAGE_OPINION)
    # A run's own view of the exhibits never carries these, and must not wipe them.
    merged = advisory.merged(_row(case_id).exhibits, {"chips": {"status": "done"}})
    assert merged[advisory.IMAGE_OPINION] == entry and merged["chips"] == {"status": "done"}
    merged = advisory.merged({advisory.IMAGE_OPINION: entry}, {advisory.IMAGE_OPINION: {"status": "pending"}})
    assert merged[advisory.IMAGE_OPINION] == entry


def test_a_lost_thread_does_not_leave_the_page_waiting():
    old = {"status": "pending", "reason": None, "updated_at": (datetime.now(UTC) - timedelta(minutes=10)).isoformat()}
    assert advisory.public(advisory.IMAGE_OPINION, old)["status"] == "failed"
    fresh = {**old, "updated_at": datetime.now(UTC).isoformat()}
    assert advisory.public(advisory.IMAGE_OPINION, fresh)["status"] == "pending"
    assert advisory.public("chips", old)["status"] == "pending"  # the run's own exhibits are not touched


def test_older_records_can_ask_for_a_look_and_it_is_limited(client, monkeypatch, gemini):
    monkeypatch.setenv("RATE_ADVISORIES_PER_HOUR", "1")
    config.get_settings.cache_clear()
    gemini.replies[CHECK] = {"found": False}
    gemini.replies[LOOK] = {"description_hi": "भूरा।", "description_en": "Browner.", "description_te": "గోధుమ.",
                            "visible_change": "clear", "consistent": "yes"}
    case_id = _sealed(client, monkeypatch)
    _settled(case_id, advisory.STATEMENT_CHECK)
    _settled(case_id, advisory.IMAGE_OPINION)
    # Nothing left to do costs nothing.
    limits.reset()
    assert client.post(f"/api/cases/{case_id}/advisories").json()["started"] == []
    with session_scope() as s:
        row = s.scalars(select(EvidenceRow).where(EvidenceRow.case_id == case_id)).first()
        row.exhibits = {k: v for k, v in row.exhibits.items() if k not in advisory.NAMES}
    assert sorted(client.post(f"/api/cases/{case_id}/advisories").json()["started"]) == sorted(advisory.NAMES)
    with session_scope() as s:
        row = s.scalars(select(EvidenceRow).where(EvidenceRow.case_id == case_id)).first()
        row.exhibits = {k: v for k, v in row.exhibits.items() if k not in advisory.NAMES}
    assert client.post(f"/api/cases/{case_id}/advisories").status_code == 429


def test_advisories_need_a_result(client, gemini):
    case_id = new_case(client)
    assert client.post(f"/api/cases/{case_id}/advisories").status_code == 409


def test_the_pdf_leaves_the_advisories_out(client, monkeypatch, gemini, tmp_path):
    from app.pdf import render

    gemini.replies[LOOK] = {"description_hi": "भूरा।", "description_en": "Browner than a model should say.", "description_te": "గోధుమ.",
                            "visible_change": "clear", "consistent": "yes"}
    case_id = _sealed(client, monkeypatch)
    _settled(case_id, advisory.IMAGE_OPINION)
    captured = {}
    monkeypatch.setattr(render, "build_html", lambda *a, **k: captured.update(failed=a[5]) or "<html></html>")
    monkeypatch.setattr("weasyprint.HTML", lambda **k: types.SimpleNamespace(write_pdf=lambda: b"%PDF"))
    row = _row(case_id)
    exhibits = {**row.exhibits, advisory.IMAGE_OPINION: {"status": "failed", "reason": "no_answer"}}
    from app.evidence.schema import Evidence

    render.build_pdf(Evidence.model_validate(row.json), {}, [], "en", exhibits)
    assert captured["failed"] == {}


# 4. Understands the farmer


@pytest.mark.parametrize("text, crop, event, days_ago", [
    ("कल शाम ओले गिरे, कपास की फ़सल खराब हो गई", "cotton", "hail", 1),
    ("kal raat ole gire, kapas ki fasal kharab ho gayi", "cotton", "hail", 1),
    ("parso tufaan aaya, dhan gir gaya", "paddy", "wind", 2),
    ("నిన్న వడగళ్ల వాన పడింది, పత్తి పంట పోయింది", "cotton", "hail", 1),
    ("మొన్న తుఫానుకు వరి పంట నేలకొరిగింది", "paddy", "cyclone", 2),
])
def test_the_fixed_rules_read_hindi_hinglish_and_telugu(text, crop, event, days_ago):
    from datetime import date

    from app.agent import parse

    today = date(2026, 11, 1)
    report = parse.parse_text(text, today)
    assert report.crop == crop and report.event_type == event
    assert report.event_date == today - timedelta(days=days_ago)


@pytest.mark.parametrize("text", ["पानी निकल गया", "आजकल फ़सल ठीक नहीं है"])
def test_a_date_word_inside_another_word_is_no_date(text):
    from app.agent import parse

    assert parse.extract_date(text)[0] is None


def _report(**over):
    return {"transcript": "फ़सल खराब", "crop": None, "event_type": "unknown", "event_date": None,
            "event_time": None, "confidence": 0.3, **over}


def test_gemini_asks_a_clarifying_question_and_the_api_says_who_understood(client, gemini):
    gemini.replies[PARSE] = _report(clarifying_question="कौन सी फ़सल थी और क्या हुआ था?")
    r = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "lang": "hi", "text": "फ़सल खराब"}).json()
    assert r["parsed"]["llm_used"] is True
    assert r["parsed"]["clarifying_question"] == "कौन सी फ़सल थी और क्या हुआ था?"
    assert r["questions"]["crop"]["hi"]  # the fixed questions stay beside it
    stored = client.get(f"/api/cases/{r['case_id']}").json()["case"]["parsed"]
    assert stored["clarifying_question"] == "कौन सी फ़सल थी और क्या हुआ था?" and stored["llm_used"] is True


@pytest.mark.parametrize("question", ["क्या आपको ₹5000 चाहिए?", "क्या 13 तारीख़ थी?", "आपको पैसा मिलेगा?"])
def test_a_clarifying_question_goes_through_the_validator(client, gemini, question):
    gemini.replies[PARSE] = _report(clarifying_question=question)
    r = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "lang": "hi", "text": "फ़सल खराब"}).json()
    assert r["parsed"]["clarifying_question"] is None and r["parsed"]["llm_used"] is True


def test_a_clarifying_question_may_quote_the_farmers_own_number(gemini):
    gemini.replies[PARSE] = _report(transcript="13 को ओले गिरे", clarifying_question="क्या 13 तारीख़ इसी महीने की है?")
    assert llm.parse_text("13 को ओले गिरे", "hi").clarifying_question == "क्या 13 तारीख़ इसी महीने की है?"


def test_the_rules_fill_what_gemini_left_empty_even_from_a_voice_note(client, gemini):
    gemini.replies[PARSE] = _report(transcript="कल ओले गिरे, कपास खराब")
    r = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "lang": "hi"},
                    files={"audio": ("a.webm", b"\x1aE\xdf\xa3 voice", "audio/webm")}).json()
    assert r["parsed"]["crop"] == "cotton" and r["parsed"]["event_type"] == "hail" and r["parsed"]["event_date"]
    assert r["parsed"]["llm_used"] is True


def test_the_fallback_is_named_when_gemini_fails(client, gemini):
    r = client.post("/api/cases", data={"lat": 29.53, "lon": 75.03, "lang": "hi", "text": "कल ओले गिरे"}).json()
    assert r["parsed"]["llm_used"] is False and r["parsed"]["event_type"] == "hail"
    assert r["parsed"]["clarifying_question"] is None


def test_a_crop_that_fails_the_denylist_is_dropped(gemini):
    gemini.replies[PARSE] = _report(crop="₹50000 paddy")
    assert llm.parse_text("x", "hi").crop is None


# Wording corrected after a record was sealed


def test_a_stored_record_shows_the_corrected_words_and_keeps_its_seal(client, monkeypatch):
    from app import main  # noqa: F401
    from app.agent import rubric

    case_id = _sealed(client, monkeypatch)
    with session_scope() as s:
        row = s.scalars(select(EvidenceRow).where(EvidenceRow.case_id == case_id)).first()
        data = copy.deepcopy(row.json)
        data["testimony_en"] = "old words"
        for objection in data["cross_examination"]:
            if objection["id"] == "regional_trend":
                objection["finding_en"] = "old finding"
        row.json = data
    stored = _row(case_id)
    shown = client.get(f"/api/cases/{case_id}").json()
    assert shown["evidence"]["testimony_en"] != "old words"
    trend = next(o for o in shown["evidence"]["cross_examination"] if o["id"] == "regional_trend")
    assert trend["finding_en"] != "old finding"
    assert shown["evidence"]["evidence_hash"] == stored.hash
    assert shown["evidence"]["verdict"]["level"] == stored.level
    after = _row(case_id)
    assert after.json == stored.json  # a read writes nothing
    assert rubric.P_FIELD  # thresholds untouched by any of this


def test_an_outcome_is_never_rewritten_on_read():
    from app.agent import current_text

    ev = with_verdict(evidence(p=placebo(p=0.4), far=placebo(p=0.01)))
    data = ev.model_dump(mode="json")
    for objection in data["cross_examination"]:
        if objection["id"] == "regional_trend":
            objection["outcome"] = "conceded"  # as sealed, whatever today's rule would say
            objection["finding_en"] = "as sealed"
    out = current_text.refresh(data)
    trend = next(o for o in out["cross_examination"] if o["id"] == "regional_trend")
    assert trend["outcome"] == "conceded" and trend["finding_en"] == "as sealed"
    assert out["verdict"]["level"] == "weak"


def test_polished_text_is_left_alone():
    from app.agent import current_text

    data = with_verdict(evidence()).model_dump(mode="json")
    data["llm_used"], data["testimony_en"] = True, "polished"
    assert current_text.refresh(data)["testimony_en"] == "polished"


def test_pdf_charts_name_their_statistic_in_words():
    from app.pdf import charts

    assert charts.statistic_label("median_delta_ndvi") == "Change in greenness (NDVI)"
    assert "_" not in charts.statistic_label("some_new_statistic")
