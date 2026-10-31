import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { canRunMap, maplibregl, satelliteStyle } from "./base";
import { useI18n, type Key } from "../i18n";
import { artifactUrl } from "../api";
import { Icon } from "../components/Icon";
import { useInView, usePrefersReducedMotion } from "../components/Bits";
import { bboxOfRing } from "../geo";
import { num } from "../format";
import { moveWords } from "../plain";
import type { Evidence, ScaleFade } from "../types";

function scaleName(m: number): string {
  return m >= 1000 ? `${m / 1000} km` : `${m} m`;
}

const HOLD_MS = 1500;
const MOVE_MS = 1300;

/** Eases between stops, so the eye rests on each scale instead of sliding past it. */
function sweep(t: number, stops: number): number {
  const period = HOLD_MS + MOVE_MS;
  const i = Math.floor(t / period);
  if (i >= stops - 1) return stops - 1;
  const inPeriod = t - i * period;
  if (inPeriod < HOLD_MS) return i;
  const f = (inPeriod - HOLD_MS) / MOVE_MS;
  return i + f * f * (3 - 2 * f);
}

export default function Vanishing({ ev, fade }: { ev: Evidence; fade: ScaleFade }) {
  const { t, lang } = useI18n();
  const reduced = usePrefersReducedMotion();
  const levels = useMemo(() => [...fade.levels].sort((a, b) => a.block_m - b.block_m), [fade]);
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [slot, inView] = useInView<HTMLDivElement>("-20%");
  const [pos, setPos] = useState(reduced ? Math.max(0, levels.length - 1) : 0);
  const [ready, setReady] = useState(false);
  const [broken] = useState(() => !canRunMap());
  const [runId, setRunId] = useState(0);
  const touched = useRef(false);
  const ring = ev.plot.geometry.coordinates[0];
  const [w, s, e, n] = fade.bounds;

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
    // Two neighbouring scales cross-fade, and the lower one stays opaque so no satellite shows through.
    const below = Math.floor(pos);
    const f = pos - below;
    levels.forEach((l, i) => {
      if (!l.chip_path || !m.getLayer(`fade-${i}`)) return;
      m.setPaintProperty(`fade-${i}`, "raster-opacity", i === below ? 1 : i === below + 1 ? f : 0);
    });
  }, [pos, ready, levels]);

  // A slow walk through the scales when it comes into view, and again on request.
  useEffect(() => {
    if (!inView || reduced || touched.current || (!ready && !broken) || levels.length < 2) return;
    setPos(0);
    const start = performance.now() + 700;
    let raf = 0;
    const step = (now: number) => {
      if (touched.current) return;
      const v = sweep(Math.max(0, now - start), levels.length);
      setPos(v);
      if (v < levels.length - 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, reduced, ready, broken, levels.length, runId]);

  const replay = useCallback(() => {
    touched.current = false;
    setRunId((r) => r + 1);
  }, []);

  const near = Math.round(pos);
  const level = levels[near];
  const isSar = fade.sensor === "s1";
  const dp = isSar ? 1 : 2;
  const unit = isSar ? " dB" : "";
  const first = levels[0]?.plot_cell_value ?? null;
  const last = levels[levels.length - 1]?.plot_cell_value ?? null;
  // The message comes only from the values, so a strong fade and a change that holds at every scale both read true.
  const fell = first !== null && last !== null && first < 0 && Math.abs(first) >= (isSar ? 0.5 : 0.05);
  const keptPct = fell ? Math.round((Math.abs(last as number) / Math.abs(first as number)) * 100) : null;
  const reading = keptPct === null ? (first !== null && last !== null ? "van.read_none" : null) : keptPct < 50 ? "van.read_fades" : "van.read_holds";
  // Once the finest level is the plot's own median, it is the field's own number and says so.
  const finestIsField = first !== null && ev.optical.plot_delta_ndvi !== null && ev.optical.plot_delta_ndvi !== undefined
    && Math.abs(first - ev.optical.plot_delta_ndvi) < 0.0006;
  const biggest = Math.max(...levels.map((l) => Math.abs(l.plot_cell_value ?? 0)), 0.0001);
  const atEnd = pos >= levels.length - 1 - 0.01;

  const outline = ring.map(([x, y]) => `${(((x - w) / (e - w)) * 100).toFixed(3)},${(((n - y) / (n - s)) * 100).toFixed(3)}`).join(" ");
  const [pw, ps, pe, pn] = bboxOfRing(ring);
  const plotInside = pw >= w && pe <= e && ps >= s && pn <= n;
  const pinLeft = (((pw + pe) / 2 - w) / (e - w)) * 100;
  const pinTop = ((n - (ps + pn) / 2) / (n - s)) * 100;
  const words = level && level.plot_cell_value !== null && !isSar ? moveWords(level.plot_cell_value) : null;

  return (
    <div className="vanish" ref={slot}>
      <p className="vanish-lede">{t("van.lede")}</p>

      <div className="vanish-stage">
        <div className="vanish-mapcol">
          <div className="vanish-map">
            {broken ? (
              <div className="vanish-flat">
                {levels.map((l, i) => l.chip_path ? (
                  <img key={l.block_m} src={artifactUrl(l.chip_path)} alt="" loading="lazy" style={{ opacity: i === Math.floor(pos) ? 1 : i === Math.floor(pos) + 1 ? pos - Math.floor(pos) : 0 }} />
                ) : null)}
                {plotInside && (
                  <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polygon points={outline} className="vanish-outline" vectorEffect="non-scaling-stroke" /></svg>
                )}
              </div>
            ) : (
              <div ref={host} className="map-host" />
            )}
            {plotInside && (
              <span className="vanish-pin" style={{ left: `${pinLeft}%`, top: `${pinTop}%` }} aria-hidden="true">
                <i /><b>{t("placebo.yours")}</b>
              </span>
            )}
            <span className="vanish-stamp">{t("van.label_short")}</span>
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
              onChange={(e2) => { touched.current = true; setPos(Number(e2.target.value)); }}
            />
            <div className="vanish-ends mono"><span>{scaleName(levels[0]?.block_m ?? 10)}</span><span>{scaleName(levels[levels.length - 1]?.block_m ?? 3000)}</span></div>
          </div>
        </div>

        <div className="vanish-side">
          <span className="drw-cap">{near === 0 && finestIsField ? t("placebo.yours") : t("van.field_at", { scale: level ? scaleName(level.block_m) : "" })}</span>
          <b className="vanish-value mono" key={near}>
            {level && level.plot_cell_value !== null ? `${num(level.plot_cell_value, dp, { signed: true })}${unit}` : "—"}
          </b>
          {words && <p className="vanish-say" key={`w${near}`}>{t(words.key, words.vars)}</p>}
          {level && level.plot_cell_value === null && <p className="small">{t("van.no_value")}</p>}
          {level && !level.chip_path && <p className="small">{t("van.no_chip")}</p>}
          <ol className="ladder" aria-label={t("van.ladder")}>
            {levels.map((l, i) => {
              const v = l.plot_cell_value;
              const pct = v === null ? 0 : (Math.abs(v) / biggest) * 100;
              return (
                <li key={l.block_m} className={i === near ? "on" : ""}>
                  <button onClick={() => { touched.current = true; setPos(i); }}>
                    <span className="ladder-scale mono">{i === 0 && finestIsField ? t("van.field_short") : scaleName(l.block_m)}</span>
                    <span className="ladder-track"><i style={{ width: `${pct}%` }} className={v !== null && v > 0 ? "up" : ""} /></span>
                    <span className="ladder-v mono">{v !== null ? num(v, dp === 2 ? 3 : 1, { signed: true }) : "—"}</span>
                  </button>
                </li>
              );
            })}
          </ol>
          {reading && (
            <p className={`vanish-end ${atEnd ? "vanish-end-on" : ""}`}>
              {t(reading as Key, { pct: keptPct ?? 0, scale: scaleName(levels[levels.length - 1].block_m) })}
            </p>
          )}
          <button className="linkish small vanish-replay" onClick={replay}><Icon name="retry" size={16} /> {t("van.replay")}</button>
        </div>
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

      <p className="vanish-label">{t("van.label")}</p>
      <p className="vanish-context">{t("van.context")}</p>
      <p className="small">{t("van.note")}</p>
      <p className="small">{t("van.cause")}</p>
    </div>
  );
}
