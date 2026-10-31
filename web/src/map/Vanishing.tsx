import { useEffect, useMemo, useRef, useState } from "react";
import { canRunMap, maplibregl, satelliteStyle } from "./base";
import { useI18n } from "../i18n";
import { artifactUrl } from "../api";
import { useInView, usePrefersReducedMotion } from "../components/Bits";
import { bboxOfRing } from "../geo";
import { num } from "../format";
import type { Evidence, ScaleFade } from "../types";

function scaleName(m: number): string {
  return m >= 1000 ? `${m / 1000} km` : `${m} m`;
}

export default function Vanishing({ ev, fade }: { ev: Evidence; fade: ScaleFade }) {
  const { t } = useI18n();
  const reduced = usePrefersReducedMotion();
  const levels = useMemo(() => [...fade.levels].sort((a, b) => a.block_m - b.block_m), [fade]);
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [slot, inView] = useInView<HTMLDivElement>("-15%");
  const [pos, setPos] = useState(0);
  const [ready, setReady] = useState(false);
  const [broken] = useState(() => !canRunMap());
  const touched = useRef(false);
  const ring = ev.plot.geometry.coordinates[0];
  const [w, s, e, n] = fade.bounds;

  useEffect(() => {
    if (broken || !host.current) return;
    const map = new maplibregl.Map({
      container: host.current,
      style: satelliteStyle(),
      bounds: [[w, s], [e, n]],
      fitBoundsOptions: { padding: 8 },
      interactive: false,
      attributionControl: { compact: false },
    });
    map.on("load", () => {
      levels.forEach((l, i) => {
        if (!l.chip_path) return;
        map.addSource(`fade-${i}`, { type: "image", url: artifactUrl(l.chip_path), coordinates: [[w, n], [e, n], [e, s], [w, s]] });
        map.addLayer({
          id: `fade-${i}`,
          type: "raster",
          source: `fade-${i}`,
          paint: { "raster-opacity": i === 0 ? 1 : 0, "raster-opacity-transition": { duration: 0 }, "raster-resampling": "nearest", "raster-fade-duration": 0 },
        });
      });
      map.addSource("plot", { type: "geojson", data: { type: "Feature", properties: {}, geometry: ev.plot.geometry } });
      map.addLayer({ id: "plot-halo", type: "line", source: "plot", paint: { "line-color": "#FFFFFF", "line-width": 5 } });
      map.addLayer({ id: "plot-line", type: "line", source: "plot", paint: { "line-color": "#1E1913", "line-width": 2.5 } });
      setReady(true);
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
    // The geometry of a sealed evidence record does not change while this page is open.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [broken]);

  useEffect(() => {
    const m = mapRef.current;
    if (!m || !ready) return;
    levels.forEach((l, i) => {
      if (l.chip_path && m.getLayer(`fade-${i}`)) {
        m.setPaintProperty(`fade-${i}`, "raster-opacity", Math.max(0, 1 - Math.abs(pos - i)));
      }
    });
  }, [pos, ready, levels]);

  // One slow sweep the first time it is seen, then it belongs to the reader.
  useEffect(() => {
    if (!inView || reduced || touched.current || (!ready && !broken) || levels.length < 2) return;
    const start = performance.now();
    const dur = 1600 * (levels.length - 1);
    let raf = 0;
    const step = (now: number) => {
      if (touched.current) return;
      const p = Math.min(1, (now - start) / dur);
      setPos(p * (levels.length - 1));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    const hold = window.setTimeout(() => { raf = requestAnimationFrame(step); }, 900);
    return () => { window.clearTimeout(hold); cancelAnimationFrame(raf); };
  }, [inView, reduced, ready, broken, levels.length]);

  const near = Math.round(pos);
  const level = levels[near];
  const isSar = fade.sensor === "s1";
  const isNdvi = fade.statistic.toLowerCase().includes("ndvi");
  const dp = isSar ? 1 : 2;
  const unit = isSar ? " dB" : "";
  const first = levels[0]?.plot_cell_value ?? null;
  const last = levels[levels.length - 1]?.plot_cell_value ?? null;
  const dissolved = first !== null && last !== null && Math.abs(last) < Math.abs(first);

  const outline = ring.map(([x, y]) => `${(((x - w) / (e - w)) * 100).toFixed(3)},${(((n - y) / (n - s)) * 100).toFixed(3)}`).join(" ");
  const [pw, ps, pe, pn] = bboxOfRing(ring);
  const plotInside = pw >= w && pe <= e && ps >= s && pn <= n;

  return (
    <div className="vanish" ref={slot}>
      <p className="vanish-label">{t("van.label")}</p>
      <p className="vanish-context">{t("van.context")}</p>
      <div className="vanish-stage">
        <div className="vanish-map">
          {broken ? (
            <div className="vanish-flat">
              {levels.map((l, i) => l.chip_path ? (
                <img key={l.block_m} src={artifactUrl(l.chip_path)} alt="" loading="lazy" style={{ opacity: Math.max(0, 1 - Math.abs(pos - i)) }} />
              ) : null)}
              {plotInside && (
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polygon points={outline} className="vanish-outline" vectorEffect="non-scaling-stroke" /></svg>
              )}
            </div>
          ) : (
            <div ref={host} className="map-host" />
          )}
          <span className="vanish-stamp">{t("van.label_short")}</span>
        </div>

        <div className="vanish-side">
          <span className="lot-cap">{t("van.field_at", { scale: level ? scaleName(level.block_m) : "" })}</span>
          <b className="vanish-value mono" key={near}>
            {level && level.plot_cell_value !== null ? `${num(level.plot_cell_value, dp, { signed: true })}${unit}` : "—"}
          </b>
          {level && level.plot_cell_value === null && <p className="small">{t("van.no_value")}</p>}
          {level && !level.chip_path && <p className="small">{t("van.no_chip")}</p>}
          {level?.context_min !== null && level?.context_min !== undefined && (
            <p className="small faint">{t("van.context_min")} <span className="mono">{num(level.context_min, dp, { signed: true })}{unit}</span></p>
          )}
          <p className="vanish-word">{t(near === 0 ? "van.w_first" : near >= levels.length - 1 ? "van.w_last" : "van.w_mid")}</p>
        </div>
      </div>

      <div className="vanish-slider">
        <input
          type="range"
          min={0}
          max={Math.max(0, levels.length - 1)}
          step={0.01}
          value={pos}
          aria-label={t("van.slider")}
          aria-valuetext={level ? scaleName(level.block_m) : ""}
          onChange={(ev2) => { touched.current = true; setPos(Number(ev2.target.value)); }}
        />
        <ol className="vanish-ticks">
          {levels.map((l, i) => (
            <li key={l.block_m} className={i === near ? "on" : ""}>
              <button onClick={() => { touched.current = true; setPos(i); }}>
                <span className="mono">{scaleName(l.block_m)}</span>
                <span className="mono vanish-tick-v">{l.plot_cell_value !== null ? num(l.plot_cell_value, dp, { signed: true }) : "—"}</span>
              </button>
            </li>
          ))}
        </ol>
      </div>

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

      {first !== null && last !== null && !dissolved && <p>{t("van.no_local")}</p>}
      {dissolved && <p>{t("van.summary", { a: `${num(first, dp, { signed: true })}${unit}`, b: `${num(last, dp, { signed: true })}${unit}`, scale: scaleName(levels[levels.length - 1].block_m) })}</p>}
      <p className="small"><strong>{t("van.note")}</strong></p>
      <p className="small faint">
        {isNdvi ? t("van.stat_ndvi") : t("van.stat_sar")} · <span className="mono">{fade.statistic}</span> · {isSar ? "Sentinel-1" : "Sentinel-2"}
      </p>
    </div>
  );
}
