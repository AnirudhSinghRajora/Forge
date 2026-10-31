import { useEffect, useRef, useState } from "react";
import { canRunMap, maplibregl, satelliteStyle } from "./base";
import { useI18n } from "../i18n";
import { artifactUrl } from "../api";
import { dayLabel } from "../format";
import type { Chip, Evidence } from "../types";

/** The storm's footprint: the change across about 24 km, with this field marked. */
export default function RegionMap({ chip, ev }: { chip: Chip; ev: Evidence }) {
  const { t, lang } = useI18n();
  const host = useRef<HTMLDivElement | null>(null);
  const [broken] = useState(() => !canRunMap());
  const bounds = chip.bounds as [number, number, number, number];
  const [w, s, e, n] = bounds;

  useEffect(() => {
    if (broken || !host.current) return;
    const map = new maplibregl.Map({
      container: host.current,
      style: satelliteStyle(),
      bounds: [[w, s], [e, n]],
      fitBoundsOptions: { padding: 4 },
      interactive: false,
      attributionControl: { compact: false },
    });
    map.on("load", () => {
      map.addSource("region", { type: "image", url: artifactUrl(chip.path), coordinates: [[w, n], [e, n], [e, s], [w, s]] });
      map.addLayer({ id: "region", type: "raster", source: "region", paint: { "raster-opacity": 0.92, "raster-resampling": "nearest", "raster-fade-duration": 0 } });
    });
    return () => map.remove();
    // A sealed record's chip does not change while the page is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [broken, chip.path]);

  const [lon, lat] = ev.plot.centroid;
  const left = ((lon - w) / (e - w)) * 100;
  const top = ((n - lat) / (n - s)) * 100;
  const inside = left >= 0 && left <= 100 && top >= 0 && top <= 100;

  return (
    <figure className="region">
      <div className="region-map">
        {broken ? <img src={artifactUrl(chip.path)} alt={t("foot.alt")} /> : <div ref={host} className="map-host" />}
        {inside && (
          <span className="vanish-pin" style={{ left: `${left}%`, top: `${top}%` }} aria-hidden="true">
            <i /><b>{t("placebo.yours")}</b>
          </span>
        )}
        <span className="vanish-stamp">{t("foot.stamp")}</span>
      </div>
      <figcaption>
        <div className="ramp">
          <span className="ramp-bar ramp-delta" />
          <div className="ramp-ticks mono"><span>{"−"}0.5</span><span>0</span><span>+0.5</span></div>
          <div className="ramp-words"><span>{t("ramp.delta_low")}</span><span>{t("ramp.delta_high")}</span></div>
        </div>
        <p className="small">{t("foot.read")}</p>
        <p className="small faint">
          <span className="mono">{dayLabel(ev.optical.pre?.date, lang)}</span> → <span className="mono">{dayLabel(chip.date ?? ev.optical.post?.date, lang)}</span>
          {chip.scene_id && <> · <span className="mono break">{chip.scene_id}</span></>}
        </p>
      </figcaption>
    </figure>
  );
}
