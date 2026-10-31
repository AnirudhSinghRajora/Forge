"""What the app may say: the trace on a cold run, and the far-yes-ring-no finding."""
from concurrent.futures import Future
from types import SimpleNamespace

from app.agent import explain, graph, rubric, testimony
from tests.conftest import evidence, placebo, qa


def _switch_line(ev, **ctx_values):
    lines = []
    ctx = SimpleNamespace(
        **{"archive_failed": False, "optical_future": None, **ctx_values},
        emit=lambda kind, node, hi, en, **detail: lines.append((kind, hi, en, detail)),
    )
    graph.n_sensor_switch({"evidence": ev}, ctx)
    assert len(lines) == 1 and lines[0][0] == "sensor_switch"
    return lines[0]


def test_optical_still_downloading_is_not_called_no_trustworthy_pair():
    _, hi, en, detail = _switch_line(evidence(cross=[]), optical_future=Future())
    assert "still downloading" in en and "Radar is starting alongside" in en
    assert "trustworthy" not in en.lower() and "भरोसेमंद" not in hi and "डाउनलोड" in hi
    assert detail["optical_continues"] is True


def test_still_downloading_wins_over_rejected_images_and_a_failed_read():
    ev = evidence(cross=[])
    ev.optical.scenes_considered = [qa("x", ev.event.date, "rejected", ["Q2: cloud"])]
    _, _, en, _ = _switch_line(ev, optical_future=Future())
    assert "still downloading" in en and "trustworthy" not in en
    ctx = SimpleNamespace(archive_failed=True, optical_future=Future(), emit=lambda *a, **k: seen.append(a))
    seen = []
    graph.n_sensor_switch({"evidence": ev}, ctx)
    assert "still downloading" in seen[0][3]


def test_a_finished_search_keeps_the_no_pair_wording():
    _, _, en, detail = _switch_line(evidence(cross=[]))
    assert en.startswith("No trustworthy optical pair was found") and detail["optical_continues"] is False
    ev = evidence(cross=[])
    ev.optical.scenes_considered = [qa("x", ev.event.date, "rejected", ["Q2: cloud"])]
    assert "no trustworthy pair remains" in _switch_line(ev)[2]


def test_a_background_search_that_concludes_no_pair_says_so_then():
    lines = []
    ev = evidence(cross=[])
    ctx = SimpleNamespace(emit=lambda kind, node, hi, en, **detail: lines.append((en, detail)))
    graph._apply_late_optical(ctx, ev, {"considered": [], "optical": None}, {})
    assert "no trustworthy optical pair was found" in lines[0][0]
    assert lines[0][1]["action"] == "optical_concluded_no_pair"


def _far_yes_ring_no():
    ev = evidence(cross=[])
    ev.neighbours.placebo = placebo(p=0.0348)
    ev.neighbours.far_placebo = placebo(p=0.005)
    assert rubric.far_significant(ev) and not rubric.ring_significant(ev)
    return ev


def test_far_yes_ring_no_never_says_the_whole_area_was_hit():
    ev = _far_yes_ring_no()
    hi, en, te = testimony.templates(ev)
    tests = explain.tests_line(ev)
    caveats = rubric._caveats(ev, "strong")
    english = " ".join([en, tests[1], *caveats]).lower()
    for claim in ("whole area", "about as much as", "across the area", "across this area", "area was hit"):
        assert claim not in english
    assert "does not look limited to your field" in tests[1]
    assert any("does not look limited to your field" in c for c in caveats)
    assert "does not look limited to me" in en
    assert "पूरा इलाक़ा" not in hi and "पूरे इलाक़े" not in hi and "ప్రాంతమంత" not in te
