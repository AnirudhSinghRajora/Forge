import { useMemo, useState } from "react";
import { useI18n } from "../i18n";
import { linear, nearestIndex, runs, ticks, useWidth } from "./util";
import { dayLabel, num, toDayNum } from "../format";
import { Missing } from "../components/Bits";
import type { Counterfactual, CounterfactualPoint } from "../types";

const isNum = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

export function TwinChart({ twin, eventDate, why }: { twin: Counterfactual | null | undefined; eventDate: string; why?: string | null }) {
  const { t, lang } = useI18n();
  const [ref, width] = useWidth<HTMLDivElement>(340);
  const [hover, setHover] = useState<number | null>(null);

  const series = useMemo(() => (twin?.series ?? []).filter((p) => p.date).slice().sort((a, b) => a.date.localeCompare(b.date)), [twin]);
  const hasObs = series.some((p) => isNum(p.observed));
  const hasExp = series.some((p) => isNum(p.expected));

  if (!twin || series.length === 0 || (!hasObs && !hasExp)) {
    return <Missing what={t("twin.missing")} why={why ?? null} />;
  }

  const height = width < 480 ? 260 : 340;
  const m = { l: 40, r: width < 480 ? 12 : 92, t: 34, b: 28 };
  const days = series.map((p) => toDayNum(p.date));
  const ev = toDayNum(eventDate);
  const d0 = Math.min(...days, ev);
  const d1 = Math.max(...days, ev);
  const x = linear(d0, d1, m.l, width - m.r);
  const vals = series.flatMap((p) => [p.observed, p.expected, p.expected_low, p.expected_high]).filter(isNum);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  const pad = (hi - lo || 0.1) * 0.12;
  lo -= pad; hi += pad;
  const y = linear(lo, hi, height - m.b, m.t);
  const path = (pts: CounterfactualPoint[], key: "observed" | "expected") =>
    pts.map((p, i) => `${i ? "L" : "M"}${x(toDayNum(p.date)).toFixed(1)},${y(p[key] as number).toFixed(1)}`).join("");
  const bandRuns = runs(series, (p) => isNum(p.expected_low) && isNum(p.expected_high));
  const obsRuns = runs(series, (p) => isNum(p.observed));
  const expRuns = runs(series, (p) => isNum(p.expected));
  const yTicks = ticks(lo, hi, 4);
  const xTickIdx = width < 480 ? [0, series.length - 1] : series.map((_, i) => i).filter((i) => i % Math.ceil(series.length / 5) === 0 || i === series.length - 1);
  const lastObs = [...series].reverse().find((p) => isNum(p.observed));
  const lastExp = [...series].reverse().find((p) => isNum(p.expected));
  const hp = hover !== null ? series[hover] : null;
  const pointer = (clientX: number, el: Element) => {
    const rect = el.getBoundingClientRect();
    setHover(nearestIndex(days.map(x), clientX - rect.left));
  };
  const evX = x(ev);

  return (
    <div className="twin">
      {isNum(twin.gap_at_post) && (
        <p className="placebo-head">
          <span className="big-count mono">{num(twin.gap_at_post, 2, { signed: true })}</span>{" "}
          <span>{t(twin.gap_at_post < 0 ? "twin.gap_below" : "twin.gap_above")}</span>
        </p>
      )}
      <p className="how-to-read">{t("twin.read")}</p>
      <div className="legend">
        <span><i className="key key-line-obs" /> {t("twin.observed")}</span>
        <span><i className="key key-line-exp" /> {t("twin.expected")}</span>
        <span><i className="key key-band" /> {t("twin.band")}</span>
      </div>
      <div className="chart" ref={ref}>
        <svg
          width={width}
          height={height}
          role="img"
          aria-label={t("twin.aria")}
          onMouseMove={(e) => pointer(e.clientX, e.currentTarget)}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => pointer(e.clientX, e.currentTarget)}
        >
          {yTicks.map((v) => (
            <g key={v}>
              <line x1={m.l} x2={width - m.r} y1={y(v)} y2={y(v)} className="grid" />
              <text x={m.l - 6} y={y(v) + 4} textAnchor="end" className="tick">{num(v, 2)}</text>
            </g>
          ))}
          {bandRuns.map((r, i) => (
            <path
              key={i}
              className="twin-band"
              d={
                r.map((p, j) => `${j ? "L" : "M"}${x(toDayNum(p.date)).toFixed(1)},${y(p.expected_high as number).toFixed(1)}`).join("") +
                r.slice().reverse().map((p) => `L${x(toDayNum(p.date)).toFixed(1)},${y(p.expected_low as number).toFixed(1)}`).join("") + "Z"
              }
            />
          ))}
          <line x1={evX} x2={evX} y1={m.t - 8} y2={height - m.b} className="event-rule" />
          <text x={evX} y={m.t - 14} textAnchor={evX > width * 0.65 ? "end" : "middle"} className="event-label">
            {t("chart.event")} · {dayLabel(eventDate, lang, false)}
          </text>
          {expRuns.map((r, i) => <path key={i} d={path(r, "expected")} className="line line-exp" />)}
          {obsRuns.map((r, i) => <path key={i} d={path(r, "observed")} className="line line-obs" />)}
          {series.map((p, i) => isNum(p.observed) ? <circle key={i} cx={x(days[i])} cy={y(p.observed)} r={4.5} className="mark-obs" /> : null)}
          {width >= 480 && lastObs && <text x={x(toDayNum(lastObs.date)) + 10} y={y(lastObs.observed as number) + 4} className="direct">{t("twin.observed_short")}</text>}
          {width >= 480 && lastExp && <text x={x(toDayNum(lastExp.date)) + 10} y={y(lastExp.expected as number) + 4} className="direct direct-exp">{t("twin.expected_short")}</text>}
          {xTickIdx.map((i) => (
            <text key={i} x={x(days[i])} y={height - 8} textAnchor={i === 0 ? "start" : i === series.length - 1 ? "end" : "middle"} className="tick">
              {dayLabel(series[i].date, lang, false)}
            </text>
          ))}
          {hover !== null && <line x1={x(days[hover])} x2={x(days[hover])} y1={m.t} y2={height - m.b} className="crosshair-line" />}
        </svg>
        {hp && hover !== null && (
          <div className="tip" style={{ left: Math.min(width - 170, Math.max(0, x(days[hover]) - 80)), top: 0 }}>
            <span className="mono">{dayLabel(hp.date, lang)}</span>
            <span>{t("twin.observed_short")}: <b className="mono">{num(hp.observed, 3)}</b></span>
            <span>{t("twin.expected_short")}: <b className="mono">{num(hp.expected, 3)}</b></span>
          </div>
        )}
      </div>
      <details className="fine">
        <summary>{t("chart.table")}</summary>
        <div className="table-scroll">
          <table className="ledger">
            <thead><tr><th>{t("chart.date")}</th><th>{t("twin.observed_short")}</th><th>{t("twin.expected_short")}</th><th>{t("twin.low")}</th><th>{t("twin.high")}</th></tr></thead>
            <tbody>
              {series.map((p) => (
                <tr key={p.date}>
                  <td className="mono">{dayLabel(p.date, lang)}</td>
                  <td className="mono">{num(p.observed, 3)}</td>
                  <td className="mono">{num(p.expected, 3)}</td>
                  <td className="mono">{num(p.expected_low, 3)}</td>
                  <td className="mono">{num(p.expected_high, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small faint">
          {t("twin.controls")}: <span className="mono">{twin.n_control_pixels}</span> · {t("twin.rmse")}: <span className="mono">{num(twin.pre_fit_rmse, 3)}</span> · <span lang="en">{twin.method}</span>
        </p>
      </details>
    </div>
  );
}
