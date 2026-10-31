import { useEffect, useRef, useState } from "react";
import { canRunMap, maplibregl, satelliteStyle } from "./base";
import { useI18n } from "../i18n";
import { artifactUrl } from "../api";
import { bboxOfRing } from "../geo";
import { dayLabel } from "../format";
import type { Chip, GeoPolygon } from "../types";

function coordsOf(b: [number, number, number, number]): [[number, number], [number, number], [number, number], [number, number]] {
  const [w, s, e, n] = b;
  return [[w, n], [e, n], [e, s], [w, s]];
}

export default function AnomalyMap({ chips, polygon }: { chips: Chip[]; polygon: GeoPolygon }) {
  const { t, lang } = useI18n();
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const usable = chips.filter((c) => c.bounds);
  const [kind, setKind] = useState(usable[0]?.kind);
  const [opacity, setOpacity] = useState(85);
  const [broken] = useState(() => !canRunMap());
  const chip = usable.find((c) => c.kind === kind) ?? usable[0];

  useEffect(() => {
    if (broken || !host.current || !chip?.bounds) return;
    const [w, s, e, n] = chip.bounds;
    const map = new maplibregl.Map({
      container: host.current,
      style: satelliteStyle(),
      bounds: [[w, s], [e, n]],
      fitBoundsOptions: { padding: 12 },
      dragRotate: false,
      pitchWithRotate: false,
      scrollZoom: false,
      cooperativeGestures: true,
      attributionControl: { compact: false },
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      map.addSource("anomaly", { type: "image", url: artifactUrl(chip.path), coordinates: coordsOf(chip.bounds!) });
      map.addLayer({ id: "anomaly", type: "raster", source: "anomaly", paint: { "raster-opacity": opacity / 100, "raster-resampling": "nearest" } });
      map.addSource("plot", { type: "geojson", data: { type: "Feature", properties: {}, geometry: polygon } });
      map.addLayer({ id: "plot-halo", type: "line", source: "plot", paint: { "line-color": "#FFFFFF", "line-width": 4 } });
      map.addLayer({ id: "plot-line", type: "line", source: "plot", paint: { "line-color": "#1E1913", "line-width": 2 } });
      // Stays far enough out that the outline burned into the chip reads as one line with this one.
      const [pw, ps, pe, pn] = bboxOfRing(polygon.coordinates[0]);
      map.fitBounds([[pw, ps], [pe, pn]], { padding: 110, maxZoom: 14.5, duration: 0 });
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // Rebuilt when the chip changes; opacity is applied in the effect below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [broken, chip?.path]);

  useEffect(() => {
    const m = mapRef.current;
    if (m?.getLayer("anomaly")) m.setPaintProperty("anomaly", "raster-opacity", opacity / 100);
  }, [opacity]);

  if (!chip) return null;
  const isSar = chip.kind === "sar_change";

  return (
    <div className="anomaly">
      {usable.length > 1 && (
        <div className="seg" role="group" aria-label={t("anom.layer")}>
          {usable.map((c) => (
            <button key={c.kind} aria-pressed={c.kind === chip.kind} onClick={() => setKind(c.kind)}>
              {t(c.kind === "sar_change" ? "anom.sar" : "anom.optical")}
            </button>
          ))}
        </div>
      )}
      {broken ? (
        <img className="anomaly-flat" src={artifactUrl(chip.path)} alt={t("anom.alt")} loading="lazy" />
      ) : (
        <div className="anomaly-canvas"><div ref={host} className="map-host" /></div>
      )}
      {!broken && (
        <label className="opacity">
          <span>{t("anom.opacity")}</span>
          <input type="range" min={0} max={100} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} />
        </label>
      )}
      <div className="ramp">
        <span className={`ramp-bar ${isSar ? "ramp-sar" : "ramp-delta"}`} />
        <div className="ramp-ticks mono">
          {isSar ? <><span>{"−"}6 dB</span><span>0</span><span>+6 dB</span></> : <><span>{"−"}0.5</span><span>0</span><span>+0.5</span></>}
        </div>
        <div className="ramp-words">
          <span>{t(isSar ? "ramp.sar_low" : "ramp.delta_low")}</span>
          <span>{t(isSar ? "ramp.sar_high" : "ramp.delta_high")}</span>
        </div>
      </div>
      <p className="small faint">
        {t("anom.grey")} <span className="mono">{dayLabel(chip.date, lang)}</span>{" "}
        <span className="mono break">{chip.scene_id ?? ""}</span>
      </p>
    </div>
  );
}
