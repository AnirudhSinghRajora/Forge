"""The claim-path router against key_rules.json, which has to exist for these."""
from datetime import UTC, date, datetime, timedelta

from app.agent.claim_path import route_claim, with_deadline
from app.tools import actions


def test_not_insured():
    path = route_claim("no", "standing", "hail", "cotton")
    assert path.route == "not_insured" and not path.countdown_applies


def test_undetermined_when_insured_is_unknown():
    path = route_claim(None, "standing", "hail", "cotton")
    assert path.route == "undetermined" and "insured" in path.unknowns and not path.countdown_applies


def test_undetermined_when_stage_is_unknown():
    path = route_claim("yes", None, "cyclone", "paddy")
    assert path.route == "undetermined" and path.unknowns == ["crop_stage"]


def test_undetermined_when_peril_is_unknown():
    path = route_claim("yes", "standing", "unknown", "paddy")
    assert path.route == "undetermined" and "event_type" in path.unknowns


def test_arnab_standing_paddy_is_area_yield():
    path = route_claim("yes", "standing", "cyclone", "paddy")
    assert path.route == "area_yield_basic"
    assert path.intimation == "not_essential" and not path.countdown_applies
    assert "5.5" in path.clause_ids


def test_hail_on_standing_crop_is_localized_with_notification_unknown():
    path = route_claim("yes", "standing", "hail", "cotton")
    assert path.route == "localized_addon" and path.intimation == "essential"
    assert "state_notification" in path.unknowns
    assert any("notified" in step.lower() or "notif" in step.lower() for step in path.next_steps)


def test_cut_and_spread_cyclone_is_post_harvest():
    path = route_claim("yes", "cut_and_spread", "cyclone", "paddy")
    assert path.route == "post_harvest_addon" and path.intimation == "essential"
    assert "state_notification" in path.unknowns


def test_stored_crop_is_undetermined():
    assert route_claim("yes", "harvested_stored", "hail", "paddy").route == "undetermined"


def test_flood_cut_crop_is_not_on_post_harvest_list():
    assert route_claim("yes", "cut_and_spread", "flood", "cotton").route == "undetermined"


def test_paddy_inundation_is_not_called_individually_covered():
    path = route_claim("yes", "standing", "flood", "paddy")
    assert path.route == "area_yield_basic" and path.intimation == "unknown"
    assert "paddy_localized_inundation_cover" in path.unknowns
    assert any("conflict" in r for r in path.reasons)


def test_inundation_other_crop_is_localized():
    assert route_claim("yes", "standing", "flood", "cotton").route == "localized_addon"


def test_wind_is_basic_only():
    assert route_claim("yes", "standing", "wind", "cotton").route == "area_yield_basic"


def test_countdown_only_on_addon_and_only_while_open():
    now = datetime(2026, 10, 26, 12, tzinfo=UTC)
    path, deadlines = with_deadline(route_claim("yes", "standing", "hail", "cotton"), "", date(2026, 10, 25),
                                    "17:00", "en", now)
    assert path.countdown_applies and deadlines[0].status == "open"
    assert deadlines[0].due_at == datetime(2026, 10, 25, 11, 30, tzinfo=UTC) + timedelta(hours=72)

    area, deadlines = with_deadline(route_claim("yes", "standing", "cyclone", "paddy"), "", date(2026, 10, 25),
                                    None, "en", now)
    assert not area.countdown_applies and deadlines == []


def test_lapsed_uses_the_wording_in_key_rules():
    now = datetime(2026, 11, 5, tzinfo=UTC)
    path, deadlines = with_deadline(route_claim("yes", "standing", "hail", "cotton"), "", date(2026, 10, 25),
                                    None, "en", now)
    assert deadlines[0].status == "lapsed" and not path.countdown_applies
    joined = " ".join(path.next_steps).lower()
    assert "still report it now" in joined and "21.5.9.2" in path.clause_ids
    assert "rejected" not in joined and "lost" not in joined


def test_unknown_time_takes_the_start_of_the_day():
    start, assumed = actions.event_datetime(date(2026, 10, 25), None)
    assert assumed and (start.hour, start.minute) == (0, 0)


def test_all_languages_produce_text_without_csc_or_insurer_or_rejection():
    routes = [("yes", "standing", "hail", "cotton"), ("yes", "standing", "cyclone", "paddy"),
              ("yes", "cut_and_spread", "cyclone", "paddy"), ("no", "standing", "hail", "x"),
              (None, None, "hail", "x"), ("yes", "standing", "flood", "paddy")]
    for lang in ("hi", "en", "te"):
        for route in routes:
            path = route_claim(*route, lang=lang)
            text = " ".join([*path.reasons, *path.next_steps, path.evidence_use or ""])
            assert text.strip()
            assert "CSC" not in text and "reject" not in text.lower()
            assert "must accept" not in text


def test_missing_rules_say_unavailable(monkeypatch):
    monkeypatch.setattr(actions, "load_key_rules", lambda: None)
    path = route_claim("yes", "standing", "hail", "cotton")
    assert path.route == "undetermined" and path.reasons == [actions.UNAVAILABLE]


def test_draw_applicability_follows_the_route():
    from app.agent.claim_path import draw_applicability

    assert draw_applicability("localized_addon") == "may_apply"
    assert draw_applicability("post_harvest_addon") == "may_apply"
    for route in ("area_yield_basic", "not_insured", "undetermined"):
        assert draw_applicability(route) == "illustration_only"


def test_contest_routes_are_stated_on_add_on_routes():
    path = route_claim("yes", "standing", "hail", "cotton")
    assert any("written notice" in step and "7 days" in step for step in path.next_steps)


ALL_ROUTES = [
    ("yes", "standing", "hail", "cotton"), ("yes", "standing", "cyclone", "paddy"),
    ("yes", "cut_and_spread", "cyclone", "paddy"), ("no", "standing", "hail", "x"),
    (None, None, "hail", "x"), ("yes", "standing", "flood", "paddy"),
    ("yes", "harvested_stored", "hail", "paddy"), ("yes", "cut_and_spread", "flood", "cotton"),
    ("yes", "standing", "unseasonal_rain", "paddy"),
]


def test_every_cited_clause_has_its_text():
    from app.tools import policy

    for route in ALL_ROUTES:
        path, deadlines = with_deadline(route_claim(*route, lang="en"), "", date(2026, 1, 1), None, "en")
        clauses = []
        policy.ensure_cited(path, clauses, deadlines)
        have = {c.clause_id for c in clauses}
        assert set(path.clause_ids) <= have, route
        assert all(c.text for c in clauses)
        assert all(d.basis in have for d in deadlines), route


def test_previously_missing_clause_ids_resolve():
    from app.tools import policy

    for clause_id in ("21.5.6.2", "21.5.4.4", "21.5.9.8"):
        assert policy._clause_by_id(clause_id) is not None, clause_id


def test_a_clause_with_no_text_is_dropped_not_shown():
    from app.evidence.schema import ClaimPath
    from app.tools import policy

    path = ClaimPath(route="undetermined", clause_ids=["no-such-clause", "21.5.8"])
    clauses = []
    policy.ensure_cited(path, clauses)
    assert path.clause_ids == ["21.5.8"] and [c.clause_id for c in clauses] == ["21.5.8"]


def test_draft_has_telugu_including_the_lapsed_note():
    case = {"id": "", "crop": "paddy", "event_time": None}
    ev = {"event": {"date": "2026-01-01", "type": "hail"}, "plot": {"area_ha": 1.0, "centroid": [80, 16]}}
    now = datetime(2026, 2, 1, tzinfo=UTC)
    path, deadlines = with_deadline(route_claim("yes", "standing", "hail", "paddy", "te"), "", date(2026, 1, 1),
                                    None, "te", now)
    draft = actions.draft_intimation(case, ev, path, deadlines)
    assert "వడగళ్ల" in draft["text_te"] and "[దయచేసి నింపండి]" in draft["text_te"]
    assert draft["lapsed_note_te"] and "14447" not in draft["lapsed_note_te"]
    assert draft["whatsapp_url_te"].startswith("https://wa.me/?text=")
    assert all(c["label_te"] for c in draft["channels"])
    assert draft["partial_allowed_note_te"]
