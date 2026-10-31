import { useEffect, useRef, useState } from "react";
import { canRunMap, maplibregl, satelliteStyle } from "./base";
import { useI18n } from "../i18n";
import { PLACES, type Place } from "../places";
import { Icon } from "../components/Icon";
import { PlaceNote } from "../components/Bits";

export default function PinMap({ start, onPick }: {
  start: { lat: number; lon: number; zoom?: number } | null;
  onPick: (lat: number, lon: number) => void;
}) {
  const { t, lang } = useI18n();
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [center, setCenter] = useState<{ lat: number; lon: number } | null>(null);
  const [broken] = useState(() => !canRunMap());
  const [place, setPlace] = useState<Place | null>(null);

  useEffect(() => {
    if (broken || !host.current) return;
    const map = new maplibregl.Map({
      container: host.current,
      style: satelliteStyle(),
      center: start ? [start.lon, start.lat] : [79.5, 22.5],
      zoom: start?.zoom ?? (start ? 14 : 4),
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: { compact: false },
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const sync = () => {
      const c = map.getCenter();
      setCenter({ lat: c.lat, lon: c.lng });
    };
    map.on("move", sync);
    sync();
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // The start point only seeds the map; later changes come from the user moving it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [broken]);

  if (broken) return <p className="notice">{t("map.no_webgl")}</p>;

  return (
    <div className="pinmap">
      <div className="places" role="group" aria-label={t("map.places")}>
        {PLACES.map((p) => (
          <button key={p.id} className="chip" onClick={() => { mapRef.current?.jumpTo({ center: [p.lon, p.lat], zoom: p.zoom }); setPlace(p); }}>
            <Icon name="pin" size={16} /> {p.label[lang]}
          </button>
        ))}
      </div>
      {place && <PlaceNote place={place} />}
      <div className="pinmap-canvas">
        <div ref={host} className="map-host" />
        <span className="crosshair" aria-hidden="true"><Icon name="pin" size={44} stroke={1.6} /></span>
      </div>
      <div className="pinmap-foot">
        <span className="mono small">
          {center ? `${center.lat.toFixed(5)}, ${center.lon.toFixed(5)}` : ""}
        </span>
        <button className="btn btn-primary" disabled={!center} onClick={() => center && onPick(center.lat, center.lon)}>
          <Icon name="check" /> {t("loc.pin_here")}
        </button>
      </div>
    </div>
  );
}
