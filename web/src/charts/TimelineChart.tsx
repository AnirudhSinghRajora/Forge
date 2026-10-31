import { useMemo, useState } from "react";
import { useI18n } from "../i18n";
import { linear, nearestIndex, ticks, useWidth } from "./util";
import { dayLabel, num, toDayNum } from "../format";
import { Missing } from "../components/Bits";
import type { TimelinePoint, WeatherEvidence } from "../types";

const isNum = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

/** Three small multiples on one time axis. Never two scales on one plot. */
export function TimelineChart({ points, weather, eventDate, weatherWhy }: {
  points: TimelinePoint[];
  weather: WeatherEvidence | null | undefined;
  eventDate: string;
  weatherWhy?: string | null;
}) {
  const { t, lang } = useI18n();
  const [ref, width] = useWidth<HTMLDivElement>(340);
  const [hover, setHover] = useState<number | null>(null);

  const opt = useMemo(() => points.filter((p) => p.sensor === "s2" && isNum(p.ndvi)).sort((a, b) => a.date.localeCompare(b.date)), [points]);
  const sar = useMemo(() => points.filter((p) => p.sensor === "s1" && isNum(p.vh_db)).sort((a, b) => a.date.localeCompare(b.date)), [points]);
  const days = useMemo(() => (weather?.days ?? []).slice().sort((a, b) => a.date.localeCompare(b.date)), [weather]);

  const allDates = [...opt.map((p) => p.date), ...sar.map((p) => p.date), ...days.map((d) => d.date), eventDate];
  if (opt.length === 0 && sar.length === 0 && days.length === 0) {
    return <Missing what={t("tl.missing")} why={weatherWhy ?? null} />;
  }

  const dn = allDates.map(toDayNum);
  const d0 = Math.min(...dn);
  const d1 = Math.max(...dn);
  const uniq = [...new Set(allDates)].sort();
  const m = { l: 44, r: 12 };
  const x = linear(d0 - 0.5, d1 + 0.5, m.l, width - m.r);
  const rowH = width < 480 ? 96 : 118;
  const gap = 34;
  const top = [26, 26 + rowH + gap, 26 + 2 * (rowH + gap)];
  const height = top[2] + rowH + 30;
  const evX = x(toDayNum(eventDate));

  const yNdvi = (() => {
    const v = opt.map((p) => p.ndvi as number);
    const lo = Math.min(0, ...v), hi = Math.max(0.8, ...v);
    return { f: linear(lo, hi, top[0] + rowH, top[0]), t: ticks(lo, hi, 2) };
  })();
  const ySar = (() => {
    const v = sar.map((p) => p.vh_db as number);
    if (!v.length) return { f: (_: number) => 0, t: [] as number[] };
    const lo = Math.min(...v) - 1, hi = Math.max(...v) + 1;
    return { f: linear(lo, hi, top[1] + rowH, top[1]), t: ticks(lo, hi, 2) };
  })();
  const yRain = (() => {
    const hi = Math.max(5, ...days.map((d) => d.precip_mm ?? 0));
    return { f: linear(0, hi, top[2] + rowH, top[2]), t: ticks(0, hi, 2) };
  })();

  const barW = Math.max(2, Math.min(18, ((width - m.l - m.r) / Math.max(1, d1 - d0 + 1)) * 0.7));
  const hoverDate = hover !== null ? uniq[hover] : null;
  const onPointer = (clientX: number, el: Element) => {
    const rect = el.getBoundingClientRect();
    setHover(nearestIndex(uniq.map((d) => x(toDayNum(d))), clientX - rect.left));
  };
  const hOpt = hoverDate ? opt.filter((p) => p.date === hoverDate) : [];
  const hSar = hoverDate ? sar.filter((p) => p.date === hoverDate) : [];
  const hDay = hoverDate ? days.find((d) => d.date === hoverDate) : undefined;

  return (
    <div className="timeline">
      <p className="how-to-read">{t("tl.read")}</p>
      <div className="readout" aria-live="off">
        {hoverDate ? (
          <>
            <span className="mono">{dayLabel(hoverDate, lang)}</span>
            {hOpt[0] && <span>{t("tl.ndvi_short")} <b className="mono">{num(hOpt[0].ndvi, 3)}</b>{hOpt[0].qa && hOpt[0].qa !== "accepted" ? ` (${t(`qa.${hOpt[0].qa}`)})` : ""}</span>}
            {hSar[0] && <span>VH <b className="mono">{num(hSar[0].vh_db, 2)} dB</b></span>}
            {hDay && <span>{t("tl.rain_short")} <b className="mono">{num(hDay.precip_mm, 1)} mm</b></span>}
          </>
        ) : (
          <span className="faint">{t("tl.hover")}</span>
        )}
      </div>
      <div className="chart" ref={ref}>
        <svg width={width} height={height} role="img" aria-label={t("tl.aria")}
          onMouseMove={(e) => onPointer(e.clientX, e.currentTarget)}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => onPointer(e.clientX, e.currentTarget)}
        >
          <text x={m.l} y={top[0] - 10} className="row-title">{t("tl.row_ndvi")}</text>
          <text x={m.l} y={top[1] - 10} className="row-title">{t("tl.row_sar")}</text>
          <text x={m.l} y={top[2] - 10} className="row-title">{t("tl.row_rain")}</text>

          {yNdvi.t.map((v) => <g key={v}><line x1={m.l} x2={width - m.r} y1={yNdvi.f(v)} y2={yNdvi.f(v)} className="grid" /><text x={m.l - 6} y={yNdvi.f(v) + 4} textAnchor="end" className="tick">{num(v, 1)}</text></g>)}
          {ySar.t.map((v) => <g key={v}><line x1={m.l} x2={width - m.r} y1={ySar.f(v)} y2={ySar.f(v)} className="grid" /><text x={m.l - 6} y={ySar.f(v) + 4} textAnchor="end" className="tick">{num(v, 0)}</text></g>)}
          {yRain.t.map((v) => <g key={v}><line x1={m.l} x2={width - m.r} y1={yRain.f(v)} y2={yRain.f(v)} className="grid" /><text x={m.l - 6} y={yRain.f(v) + 4} textAnchor="end" className="tick">{num(v, 0)}</text></g>)}

          <line x1={evX} x2={evX} y1={top[0] - 4} y2={top[2] + rowH} className="event-rule" />
          <text x={evX} y={13} textAnchor={evX > width * 0.65 ? "end" : "middle"} className="event-label">{t("chart.event")} · {dayLabel(eventDate, lang, false)}</text>

          {opt.length === 0 && <text x={(m.l + width - m.r) / 2} y={top[0] + rowH / 2} textAnchor="middle" className="row-empty">{t("tl.no_ndvi")}</text>}
          {sar.length === 0 && <text x={(m.l + width - m.r) / 2} y={top[1] + rowH / 2} textAnchor="middle" className="row-empty">{t("tl.no_sar")}</text>}
          {days.length === 0 && <text x={(m.l + width - m.r) / 2} y={top[2] + rowH / 2} textAnchor="middle" className="row-empty">{t("tl.no_rain")}</text>}

          {opt.filter((p) => p.qa !== "rejected").length > 1 && (
            <path className="line line-obs line-thin" d={opt.filter((p) => p.qa !== "rejected").map((p, i) => `${i ? "L" : "M"}${x(toDayNum(p.date)).toFixed(1)},${yNdvi.f(p.ndvi as number).toFixed(1)}`).join("")} />
          )}
          {opt.map((p) => {
            const cx = x(toDayNum(p.date));
            const cy = yNdvi.f(p.ndvi as number);
            if (p.qa === "rejected") return <path key={p.date} d={`M${cx - 5},${cy - 5}L${cx + 5},${cy + 5}M${cx + 5},${cy - 5}L${cx - 5},${cy + 5}`} className="mark-rejected" />;
            if (p.qa === "suspect") return <circle key={p.date} cx={cx} cy={cy} r={4.5} className="mark-suspect" />;
            return <circle key={p.date} cx={cx} cy={cy} r={4.5} className="mark-obs" />;
          })}

          {sar.length > 1 && <path className="line line-exp line-thin" d={sar.map((p, i) => `${i ? "L" : "M"}${x(toDayNum(p.date)).toFixed(1)},${ySar.f(p.vh_db as number).toFixed(1)}`).join("")} />}
          {sar.map((p) => <circle key={`${p.date}${p.vh_db}`} cx={x(toDayNum(p.date))} cy={ySar.f(p.vh_db as number)} r={4.5} className="mark-exp" />)}

          {days.map((d) => isNum(d.precip_mm) && d.precip_mm > 0 ? (
            <rect key={d.date} x={x(toDayNum(d.date)) - barW / 2} width={barW} y={yRain.f(d.precip_mm)} height={Math.max(1, top[2] + rowH - yRain.f(d.precip_mm))} className="bar" />
          ) : null)}
          {days.map((d) => d.precip_mm === null ? <text key={`n${d.date}`} x={x(toDayNum(d.date))} y={top[2] + rowH - 4} textAnchor="middle" className="tick">?</text> : null)}

          <text x={m.l} y={height - 8} className="tick">{dayLabel(uniq[0], lang, false)}</text>
          <text x={width - m.r} y={height - 8} textAnchor="end" className="tick">{dayLabel(uniq[uniq.length - 1], lang, false)}</text>
          {hoverDate && <line x1={x(toDayNum(hoverDate))} x2={x(toDayNum(hoverDate))} y1={top[0] - 4} y2={top[2] + rowH} className="crosshair-line" />}
        </svg>
      </div>
      <div className="legend">
        <span><i className="key key-mark-obs" /> {t("tl.key_accepted")}</span>
        <span><i className="key key-mark-suspect" /> {t("qa.suspect")}</span>
        <span><i className="key key-mark-rejected">×</i> {t("qa.rejected")}</span>
      </div>
      <details className="fine">
        <summary>{t("chart.table")}</summary>
        <div className="table-scroll">
          <table className="ledger">
            <thead><tr><th>{t("chart.date")}</th><th>{t("tl.sensor")}</th><th>{t("tl.value")}</th><th>{t("tl.qa")}</th></tr></thead>
            <tbody>
              {opt.map((p) => <tr key={`o${p.date}`}><td className="mono">{dayLabel(p.date, lang)}</td><td>Sentinel-2</td><td className="mono">NDVI {num(p.ndvi, 3)}</td><td>{p.qa ? t(`qa.${p.qa}`) : "—"}</td></tr>)}
              {sar.map((p) => <tr key={`s${p.date}${p.vh_db}`}><td className="mono">{dayLabel(p.date, lang)}</td><td>Sentinel-1</td><td className="mono">VH {num(p.vh_db, 2)} dB</td><td>{p.qa ? t(`qa.${p.qa}`) : "—"}</td></tr>)}
              {days.map((d) => <tr key={`w${d.date}`}><td className="mono">{dayLabel(d.date, lang)}</td><td lang="en">{weather?.source}</td><td className="mono">{num(d.precip_mm, 1)} mm</td><td>—</td></tr>)}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
