"""Weather, alert and policy tools on recorded-shape responses. No network."""
from datetime import date

import httpx
import pytest

from app.tools import alerts, policy, weather

EVENT = date(2026, 10, 25)
TODAY = date(2026, 10, 31)


def om_payload(rain=None, codes=None, gusts=None):
    days = [f"2026-10-{d:02d}" for d in range(20, 31)]
    rain = rain or {}
    gusts = gusts or {}
    codes = codes or {}
    hourly_time, hourly_code = [], []
    for d in days:
        for h in range(24):
            hourly_time.append(f"{d}T{h:02d}:00")
            hourly_code.append(codes.get(d, 0) if h == 15 else 0)
    return {
        "daily": {
            "time": days,
            "precipitation_sum": [rain.get(d, 0.0) for d in days],
            "wind_gusts_10m_max": [gusts.get(d, 20.0) for d in days],
            "weather_code": [codes.get(d, 0) for d in days],
        },
        "hourly": {"time": hourly_time, "weather_code": hourly_code},
    }


def build(payload, event_type="hail"):
    from datetime import UTC, datetime

    return weather.build_evidence("open-meteo", payload, datetime.now(UTC), EVENT, event_type, TODAY)


def test_no_signal_does_not_corroborate_or_propose():
    w = build(om_payload())
    assert not w.corroborated and w.proposed_event_date is None and "model" in w.grid_note.lower()


def test_heavy_day_corroborates():
    assert build(om_payload(rain={"2026-10-25": 10.0})).corroborated


def test_window_total_corroborates():
    assert build(om_payload(rain={"2026-10-24": 9.0, "2026-10-25": 6.0, "2026-10-26": 6.0})).corroborated


def test_hail_code_corroborates_and_is_counted():
    w = build(om_payload(codes={"2026-10-25": 96}))
    assert w.corroborated and w.hail_code_hours == 1 and w.thunder_hours == 1


def test_thunder_alone_does_not_corroborate():
    w = build(om_payload(codes={"2026-10-25": 95}))
    assert not w.corroborated and w.thunder_hours == 1 and w.hail_code_hours == 0


def test_strong_gusts_corroborate():
    assert build(om_payload(gusts={"2026-10-26": 75.0})).corroborated


def test_signal_three_days_away_proposes_a_date():
    w = build(om_payload(rain={"2026-10-28": 40.0}))
    assert not w.corroborated and w.proposed_event_date == date(2026, 10, 28)


def test_rain_does_not_corroborate_pest():
    assert not build(om_payload(rain={"2026-10-25": 50.0}), "pest").corroborated


def test_power_treats_fill_value_as_missing():
    from datetime import UTC, datetime

    payload = {"header": {"fill_value": -999.0}, "properties": {"parameter": {"PRECTOTCORR": {
        "20261024": 12.0, "20261025": -999.0, "20261026": 1.0}}}}
    w = weather.build_evidence("nasa-power", payload, datetime.now(UTC), EVENT, "hail", TODAY)
    day = next(d for d in w.days if d.date == EVENT)
    assert day.precip_mm is None and w.corroborated and w.fallback_used
    assert w.hail_code_hours is None and w.max_gust_kmh is None


def test_open_meteo_failure_falls_back_to_power(monkeypatch):
    def fail(*a, **k):
        request = httpx.Request("GET", "https://x")
        raise httpx.HTTPStatusError("429", request=request, response=httpx.Response(429, request=request))

    monkeypatch.setattr(weather, "_fetch_open_meteo", fail)
    monkeypatch.setattr(weather, "_fetch_power", lambda *a, **k: {
        "header": {}, "properties": {"parameter": {"PRECTOTCORR": {"20261025": 15.0}}}})
    w = weather.fetch_weather(29.5, 75.0, EVENT, "hail", TODAY)
    assert w.fallback_used and "NASA POWER" in w.source and w.corroborated


def test_both_sources_failing_raises_without_a_number(monkeypatch):
    def fail(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(weather, "_fetch_open_meteo", fail)
    monkeypatch.setattr(weather, "_fetch_power", fail)
    with pytest.raises(weather.WeatherUnavailable):
        weather.fetch_weather(29.5, 75.0, EVENT, "hail", TODAY)


CAP = """<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
<cap:identifier>IN-1_17</cap:identifier><cap:sender>Haryana-SDMA</cap:sender>
<cap:sent>2026-10-25T19:47:37+05:30</cap:sent><cap:status>Actual</cap:status>
<cap:info><cap:language>en-IN</cap:language><cap:event>Hailstorm</cap:event>
<cap:severity>Severe</cap:severity><cap:effective>2026-10-25T19:35:00+05:30</cap:effective>
<cap:headline>Hail likely over parts of Sirsa district</cap:headline>
<cap:area><cap:areaDesc>Sirsa district of Haryana</cap:areaDesc>
<cap:geocode><cap:valueName>LGD District Code</cap:valueName><cap:value>703</cap:value></cap:geocode></cap:area></cap:info>
<cap:info><cap:language>HI</cap:language><cap:headline>ओले</cap:headline></cap:info>
</cap:alert>"""


def test_parse_cap_prefers_english_and_stores_utc():
    cap = alerts.parse_cap(CAP)
    assert cap["headline"].startswith("Hail likely") and cap["area_desc"].startswith("Sirsa")
    assert cap["sent"].utcoffset().total_seconds() == 0 and cap["sent"].hour == 14


def test_match_by_district_and_date_only():
    alerts._store("1", alerts.parse_cap(CAP), "https://sachet/x", CAP)
    assert [a.identifier for a in alerts.match("Sirsa", EVENT, "hail")] == ["1"]
    assert alerts.match("Hisar", EVENT, "hail") == []
    assert alerts.match("Sirsa", date(2026, 9, 1), "hail") == []
    assert alerts.match(None, EVENT, "hail") == []
    assert alerts.match("Sirsa", EVENT, "pest") == []


def test_ask_refuses_outside_the_corpus():
    for question in ("What is the capital of France?", "Who is the prime minister of India?",
                     "what crops grow in mars soil"):
        result = policy.ask(question, "en")
        assert not result["covered"] and result["citations"] == []


def test_ask_answers_with_citations_in_hindi_and_english():
    for question, lang in (("how many hours to report hail loss", "en"),
                           ("ओले गिरने पर कितने घंटे में सूचना देनी है", "hi")):
        result = policy.ask(question, lang)
        assert result["covered"] and result["citations"]
        assert "21.5.5.1" in [c["clause_id"] for c in result["citations"]]


def test_ask_without_a_corpus_says_so(monkeypatch):
    monkeypatch.setattr(policy, "load_corpus", lambda: None)
    result = policy.ask("hail claim deadline", "en")
    assert not result["covered"] and result["reason"] == policy.UNAVAILABLE


def test_interleaved_tables_and_old_faq_are_not_citable():
    corpus = policy.load_corpus()
    ids = {str(c["clause_id"]) for c in corpus.clauses}
    assert "21.5.10" not in ids and "21.6.11" not in ids
    assert "21.5.10/Table-10/row-1/schedule" in ids
    assert not any(c["doc"].startswith("PIB Research Unit FAQ") for c in corpus.clauses)


def test_paddy_inundation_is_never_called_covered():
    for question, lang in (("is paddy flood loss covered", "en"), ("धान में जलभराव कवर है क्या", "hi")):
        result = policy.ask(question, lang)
        assert "14447" in result["answer"]
        assert "conflict" in result["answer"] or "मेल नहीं" in result["answer"]


def test_seventy_thirty_only_comes_with_its_limits():
    result = policy.ask("does satellite technology evidence weight 70 30 yes-tech apply", "en")
    if "70%" in result["answer"]:
        assert "does not trigger" in result["answer"] and "binds the farmer" in result["answer"]
