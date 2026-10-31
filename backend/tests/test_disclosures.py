"""The selection disclosure: where it applies, and that it is said without touching any number."""
from app import disclosures
from app.pdf import render
from tests.conftest import evidence

STRONGEST = [76.215719, 28.700911]
TYPICAL = [76.231138, 28.715212]
METRE_LAT = 1 / 111_320


def test_each_scanned_plot_has_its_own_note_in_every_language():
    for centroid, kind, phrase in ((STRONGEST, "strongest", "strongest of 200 random plots scanned in this area"),
                                   (TYPICAL, "typical", "median of 40 random plots from the band")):
        note = disclosures.selection_note(centroid)
        assert note["kind"] == kind and phrase in note["en"]
        assert note["hi"] and note["te"]
        assert set(note) == {"hi", "te", "en", "kind"}


def test_distance_limit_is_about_300_m():
    lon, lat = STRONGEST
    assert disclosures.selection_note([lon, lat + 250 * METRE_LAT])["kind"] == "strongest"
    assert disclosures.selection_note([lon, lat + 350 * METRE_LAT]) is None


def test_anywhere_else_or_nothing_has_no_note():
    assert disclosures.selection_note([81.9, 16.45]) is None
    assert disclosures.selection_note(None) is None
    assert disclosures.selection_note([None, None]) is None


def _html(tmp_path, ev, lang):
    return render.build_html(ev, {"district": None, "state": None, "event_time": None}, [], lang, tmp_path)


def _at(centroid):
    ev = evidence(cross=[])
    ev.plot = ev.plot.model_copy(update={"centroid": tuple(centroid)})
    return ev


def test_the_pdf_says_it_above_the_result_in_each_language(tmp_path):
    note = disclosures.selection_note(STRONGEST)
    for lang in ("hi", "en", "te"):
        html = _html(tmp_path, _at(STRONGEST), lang)
        assert note[lang] in html
        assert html.index('<div class="selection">') < html.index('<div class="verdict ')


def test_the_pdf_says_nothing_for_any_other_plot(tmp_path):
    assert '<div class="selection">' not in _html(tmp_path, _at([81.9, 16.45]), "en")


def test_the_pdf_prints_near_the_threshold_only_where_it_applies(tmp_path):
    from app.agent import explain
    from app.evidence.schema import Verdict
    from tests.conftest import placebo

    ev = evidence(delta=-0.126, cross=[])
    ev.neighbours.far_placebo, ev.neighbours.placebo = placebo(p=0.054), placebo(p=0.202)
    ev.verdict = Verdict(level="weak", headline_hi="h", headline_en="e", reasons=[], caveats=[],
                         falsifiers_checked=[], rubric_version="v")
    for lang, index in (("hi", 0), ("en", 1), ("te", 2)):
        assert explain.NEAR_LINE[index] in _html(tmp_path, ev, lang)
    assert "near the threshold</b>" in _html(tmp_path, ev, "en")
    ev.neighbours.far_placebo, ev.neighbours.placebo = placebo(p=0.005), placebo(p=0.035)
    html = _html(tmp_path, ev, "en")
    assert explain.NEAR_LINE[1] not in html and "near the threshold</b>" in html  # the ring line alone
