"""Plot and pin validation. A rejection carries a Hindi and an English message for the farmer."""
from __future__ import annotations

from dataclasses import dataclass, field

from pyproj import Geod
from shapely import Point
from shapely.geometry import Polygon, shape
from shapely.prepared import prep
from shapely.validation import explain_validity

MIN_RELIABLE_HA = 0.2
SLOW_ABOVE_HA = 10.0
MAX_PLOT_HA = 50.0  # the geo engine's own limit

# A deliberately coarse, generous outline of India (lon, lat), used only to refuse pins clearly
# outside India or at sea. It is not a boundary claim and it does not decide anything about a case.
_INDIA_OUTLINE = Polygon(
    [
        (67.9, 23.7), (68.6, 24.5), (70.1, 24.4), (69.3, 26.7), (70.0, 28.1), (72.2, 29.9),
        (73.6, 30.6), (74.2, 31.4), (74.3, 32.6), (73.3, 33.2), (73.3, 34.8), (74.0, 37.2),
        (77.8, 35.8), (80.6, 35.6), (79.6, 32.8), (81.3, 30.4), (80.0, 28.6), (83.0, 27.1),
        (85.0, 26.3), (88.0, 26.1), (87.9, 28.2), (89.1, 28.0), (89.0, 26.5), (92.1, 26.6),
        (91.9, 28.1), (96.5, 29.6), (97.7, 28.3), (95.3, 25.9), (94.3, 23.4), (93.4, 21.7),
        (92.3, 21.7), (90.9, 22.7), (91.0, 24.1), (92.3, 24.7), (89.7, 25.0), (88.0, 24.5),
        (88.9, 23.9), (89.3, 21.3), (86.9, 20.8), (86.5, 19.6), (84.9, 18.9), (83.1, 17.0),
        (81.6, 15.7), (80.5, 15.3), (80.6, 12.8), (80.5, 10.2), (79.6, 8.8), (78.4, 8.3),
        (77.5, 7.7), (76.0, 8.8), (74.7, 11.2), (74.0, 13.6), (73.2, 15.3), (72.4, 18.8),
        (72.3, 20.5), (70.7, 20.4), (68.6, 22.1),
    ]
)
_ISLANDS = [
    Polygon([(92.0, 6.5), (94.5, 6.5), (94.5, 14.0), (92.0, 14.0)]),  # Andaman and Nicobar
    Polygon([(71.5, 8.0), (74.3, 8.0), (74.3, 12.6), (71.5, 12.6)]),  # Lakshadweep
]
_PREPARED = [prep(p) for p in [_INDIA_OUTLINE, *_ISLANDS]]
_GEOD = Geod(ellps="WGS84")


def in_service_area(lon: float, lat: float) -> bool:
    point = Point(lon, lat)
    return any(p.contains(point) for p in _PREPARED)


class PlotRejected(ValueError):
    def __init__(self, code: str, message_hi: str, message_en: str, message_te: str | None = None):
        super().__init__(message_en)
        self.code = code
        self.message_hi = message_hi
        self.message_en = message_en
        self.message_te = message_te

    def as_detail(self) -> dict:
        detail = {"code": self.code, "message_hi": self.message_hi, "message_en": self.message_en}
        if self.message_te:
            detail["message_te"] = self.message_te
        return detail


def check_pin(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise PlotRejected(
            "pin_invalid",
            "यह स्थान सही निर्देशांक नहीं है। कृपया नक्शे पर अपना खेत फिर से चुनें।",
            "These are not valid coordinates. Please pick your field on the map again.",
        )
    if not in_service_area(lon, lat):
        raise PlotRejected(
            "outside_india",
            "यह स्थान भारत के ज़मीनी हिस्से में नहीं दिखता। फ़सल बीमा योजना भारत के खेतों के लिए है, "
            "इसलिए कृपया अपने खेत पर पिन लगाएँ।",
            "This point does not appear to be on land in India. PMFBY covers Indian farmland, so "
            "please place the pin on your field.",
        )


@dataclass
class PlotResult:
    geometry: dict
    area_ha: float
    centroid: tuple[float, float]
    crs: str
    warnings: list[str] = field(default_factory=list)


def utm_crs(lon: float, lat: float) -> str:
    zone = int((lon + 180) // 6) + 1
    return f"EPSG:{(32600 if lat >= 0 else 32700) + zone}"


def validate_polygon(raw: dict | None) -> PlotResult:
    """Accepts a GeoJSON Polygon or a Feature holding one. Raises PlotRejected with a clear reason."""
    bad = PlotRejected(
        "polygon_invalid",
        "खेत की सीमा ठीक से नहीं बनी। कृपया कम से कम तीन कोने लगाकर दोबारा बनाएँ।",
        "The field boundary is not a valid polygon. Please draw it again with at least three corners.",
    )
    if not isinstance(raw, dict):
        raise bad
    if raw.get("type") == "Feature":
        raw = raw.get("geometry")
        if not isinstance(raw, dict):
            raise bad
    if raw.get("type") != "Polygon":
        raise bad
    try:
        geom = shape(raw)
    except Exception as exc:  # shapely raises several types on malformed coordinates
        raise bad from exc
    if geom.is_empty or len(geom.exterior.coords) < 4:
        raise bad
    if len(geom.interiors) > 0:
        # Only the outer ring would be kept, so the hole would silently count as field.
        raise PlotRejected(
            "polygon_has_hole",
            "खेत की सीमा में छेद नहीं हो सकता। कृपया केवल बाहरी सीमा बनाएँ।",
            "The field boundary cannot have a hole in it. Please draw only the outer edge.",
            "పొలం సరిహద్దులో రంధ్రం ఉండకూడదు. దయచేసి బయటి అంచు మాత్రమే గీయండి.",
        )
    if not geom.is_valid:
        raise PlotRejected(
            "polygon_self_intersecting",
            "खेत की सीमा की रेखाएँ एक-दूसरे को काट रही हैं। कृपया बिना क्रॉस किए दोबारा बनाएँ।",
            f"The field boundary crosses itself ({explain_validity(geom)}). Please redraw it.",
        )
    centroid = geom.centroid
    lon, lat = float(centroid.x), float(centroid.y)
    check_pin(lat, lon)
    area_m2 = abs(_GEOD.geometry_area_perimeter(geom)[0])
    area_ha = area_m2 / 10_000
    if area_ha <= 0:
        raise bad
    if area_ha > MAX_PLOT_HA:
        raise PlotRejected(
            "polygon_too_large",
            "यह सीमा एक खेत से बहुत बड़ी है। कृपया केवल अपना खेत चुनें।",
            f"This boundary covers {area_ha:.0f} ha, far larger than a single field. Please outline "
            "only your field.",
        )
    warnings: list[str] = []
    if area_ha < MIN_RELIABLE_HA:
        warnings.append("too_small_photo_evidence_advised")
    if area_ha > SLOW_ABOVE_HA:
        warnings.append("large_plot_slower_analysis")
    geometry = {"type": "Polygon", "coordinates": [list(map(list, geom.exterior.coords))]}
    return PlotResult(
        geometry=geometry,
        area_ha=round(area_ha, 4),
        centroid=(round(lon, 6), round(lat, 6)),
        crs=utm_crs(lon, lat),
        warnings=warnings,
    )
