import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n, type Key } from "../i18n";
import { ApiError, getRadar } from "../api";
import { canRunMap, maplibregl, satelliteStyle } from "../map/base";
import { ErrorNote, Loading, Missing } from "../components/Bits";
import { dateTimeLabel, dayLabel, num } from "../format";

interface Cell {
  name?: string; state?: string; lat: number; lon: number; hours_left?: number | null;
  max_daily_mm?: number | null; precip_mm?: number | null; heavy_mm?: number | null; code?: number | null; weather_code?: number | null;
  heavy_date?: string | null; signal?: "heavy_rain" | "hail_code" | "thunder_code" | null;
}
interface RadarData {
  source?: string; fetched_at?: string; stale?: boolean; points_checked?: number; heavy_rain_mm_threshold?: number;
  window_hours?: number; basis?: string; grid_note?: string; cells: Cell[];
}

export default function Radar() {
  const { t, lang } = useI18n();
  const [data, setData] = useState<RadarData | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const host = useRef<HTMLDivElement | null>(null);
  const [broken] = useState(() => !canRunMap());

  const load = useCallback((signal?: AbortSignal) => {
    setErr(null);
    getRadar(signal).then((d) => setData(d as RadarData)).catch((e) => { if (!signal?.aborted) setErr(e); });
  }, []);
  useEffect(() => {
    const ctl = new AbortController();
    load(ctl.signal);
    return () => ctl.abort();
  }, [load]);

  useEffect(() => {
    if (broken || !host.current || !data || data.cells.length === 0) return;
    const map = new maplibregl.Map({
      container: host.current,
      style: satelliteStyle(),
      center: [79.5, 22.5],
      zoom: 3.6,
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: { compact: false },
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const markers = data.cells.map((c) => {
      const el = document.createElement("div");
      el.className = "radar-mark";
      el.textContent = c.hours_left !== null && c.hours_left !== undefined ? `${Math.round(c.hours_left)}h` : "?";
      el.title = [c.name, c.state].filter(Boolean).join(", ");
      return new maplibregl.Marker({ element: el }).setLngLat([c.lon, c.lat]).addTo(map);
    });
    const b = new maplibregl.LngLatBounds();
    data.cells.forEach((c) => b.extend([c.lon, c.lat]));
    map.fitBounds(b, { padding: 70, maxZoom: 8, duration: 0 });
    return () => {
      markers.forEach((m) => m.remove());
      map.remove();
    };
  }, [data, broken]);

  const sorted = data ? [...data.cells].sort((a, b) => (a.hours_left ?? 1e9) - (b.hours_left ?? 1e9)) : [];

  return (
    <div className="page radar">
      <p className="eyebrow">{t("radar.eyebrow")}</p>
      <h1 className="h-page">{t("radar.title")}</h1>
      <p className="lede">{t("radar.lede")}</p>
      <p className="small">{t("radar.not_rule")}</p>

      {err !== null && (err instanceof ApiError && err.status === 404
        ? <Missing what={t("radar.unavailable")} why={t("radar.unavailable_why")} />
        : <ErrorNote error={err} onRetry={() => load()} />)}
      {!data && err === null && <Loading what={t("radar.loading")} />}

      {data && data.cells.length === 0 && (
        <p className="missing">{t("radar.none", { n: data.points_checked ?? 0 })}</p>
      )}
      {data && data.cells.length > 0 && (
        <>
          {broken ? <p className="notice">{t("map.no_webgl")}</p> : <div className="radar-canvas"><div ref={host} className="map-host" /></div>}
          <div className="table-scroll">
            <table className="ledger">
              <thead><tr><th>{t("radar.place")}</th><th>{t("radar.when")}</th><th>{t("radar.signal")}</th><th>{t("radar.hours")}</th><th>{t("radar.rain")}</th></tr></thead>
              <tbody>
                {sorted.map((c, i) => (
                  <tr key={i}>
                    <td>{[c.name, c.state].filter(Boolean).join(", ") || `${c.lat.toFixed(2)}, ${c.lon.toFixed(2)}`}</td>
                    <td className="mono small">{c.heavy_date ? dayLabel(c.heavy_date, lang) : "—"}</td>
                    <td className="small">{c.signal ? t(`radar.sig_${c.signal}` as Key) : "—"}</td>
                    <td className="mono">{num(c.hours_left, 0)}</td>
                    <td className="mono">{num(c.max_daily_mm ?? c.heavy_mm ?? c.precip_mm, 1)} mm</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {data && (
        <p className="small faint">
          <span lang="en">{data.source}</span>{data.fetched_at ? <> · <span className="mono">{dateTimeLabel(data.fetched_at, lang)}</span></> : null}
          {data.stale && <> · {t("radar.stale")}</>}
          {data.points_checked !== undefined && <> · {t("radar.checked", { n: data.points_checked })}</>}
          {data.grid_note && <><br /><span lang="en">{data.grid_note}</span></>}
          {data.basis && <><br /><span lang="en">{data.basis}</span></>}
        </p>
      )}
    </div>
  );
}
