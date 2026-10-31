from datetime import date

import pytest

from app.agent.parse import extract_time, needs_for, parse_text
from app.agent.plot import PlotRejected, check_pin, in_service_area, validate_polygon

TODAY = date(2026, 10, 31)


@pytest.mark.parametrize(
    "text,crop,event,day",
    [
        ("ओले गिरे, कपास खराब हो गई", "cotton", "hail", None),
        ("कल शाम 5 बजे ओले गिरे, धान की फसल बर्बाद", "paddy", "hail", date(2026, 10, 30)),
        ("Hail on 25 Oct damaged my cotton", "cotton", "hail", date(2026, 10, 25)),
        ("kal raat barish se dhan gir gaya", "paddy", "unseasonal_rain", date(2026, 10, 30)),
        ("తుఫాను వల్ల నిన్న వరి పంట నీట మునిగింది", "paddy", "cyclone", date(2026, 10, 30)),
        ("तीन दिन पहले तेज़ आंधी से गन्ना गिर गया", "sugarcane", "wind", date(2026, 10, 28)),
        ("wheat 2026-10-20 flood", "wheat", "flood", date(2026, 10, 20)),
        ("२५ अक्टूबर को ओलावृष्टि", None, "hail", date(2026, 10, 25)),
        ("my whole price dropped", None, "unknown", None),
    ],
)
def test_keyword_and_date_extraction(text, crop, event, day):
    report = parse_text(text, TODAY)
    assert (report.crop, report.event_type, report.event_date) == (crop, event, day)


def test_future_date_is_refused_not_guessed():
    report = parse_text("rain on 5/11", TODAY)
    assert report.event_date is None and report.date_note.startswith("future_date_refused")


def test_no_text_gives_no_values():
    report = parse_text(None, TODAY)
    assert report.crop is None and report.confidence == 0


def test_time_needs_an_explicit_clock():
    assert extract_time("कल शाम 5 बजे") == "17:00"
    assert extract_time("at 4:30 pm") == "16:30"
    assert extract_time("कल रात") is None


def test_needs_lists_what_is_missing():
    assert needs_for(None, "unknown", None) == ["crop", "event_type", "event_date"]
    assert needs_for("cotton", "hail", TODAY) == []


def square(lon=75.03, lat=29.53, half=0.0007):
    ring = [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half],
            [lon - half, lat + half], [lon - half, lat - half]]
    return {"type": "Polygon", "coordinates": [ring]}


def test_valid_polygon_area_is_about_right():
    result = validate_polygon(square())
    assert 1.8 < result.area_ha < 2.4 and result.crs == "EPSG:32643" and result.warnings == []


def test_feature_is_accepted():
    assert validate_polygon({"type": "Feature", "geometry": square()}).area_ha > 0


def test_tiny_plot_warns():
    assert "too_small_photo_evidence_advised" in validate_polygon(square(half=0.0001)).warnings


@pytest.mark.parametrize(
    "raw,code",
    [
        (None, "polygon_invalid"),
        ({"type": "Point", "coordinates": [75, 29]}, "polygon_invalid"),
        ({"type": "Polygon", "coordinates": []}, "polygon_invalid"),
        ({"type": "Polygon", "coordinates": [[[75, 29], [75.001, 29]]]}, "polygon_invalid"),
        ({"type": "Polygon", "coordinates": "nonsense"}, "polygon_invalid"),
        ({"type": "Polygon", "coordinates": [[[75, 29], [75.01, 29.01], [75.01, 29], [75, 29.01], [75, 29]]]},
         "polygon_self_intersecting"),
        (square(lon=65, lat=15), "outside_india"),
        (square(half=0.05), "polygon_too_large"),
    ],
)
def test_bad_polygons_are_rejected_with_a_code(raw, code):
    with pytest.raises(PlotRejected) as info:
        validate_polygon(raw)
    assert info.value.code == code and info.value.message_hi and info.value.message_en


@pytest.mark.parametrize(
    "lon,lat,inside",
    [(75.03, 29.53, True), (82.21, 16.73, True), (77.55, 8.09, True), (88.36, 22.57, True),
     (91.28, 23.83, True), (93.94, 24.82, True), (74.8, 34.08, True), (92.74, 11.62, True),
     (65, 15, False), (88, 15, False), (79.86, 6.93, False), (85.32, 27.7, False), (67, 24.86, False)],
)
def test_service_area(lon, lat, inside):
    assert in_service_area(lon, lat) is inside


def test_pin_outside_india_is_rejected():
    with pytest.raises(PlotRejected):
        check_pin(51.5, -0.12)
