import { useMemo, useState } from "react";
import { useI18n } from "../i18n";
import { linear, ticks, useWidth } from "./util";
import { num, rawNum } from "../format";
import { Missing } from "../components/Bits";
import type { PlaceboTest } from "../types";

interface Dot { cx: number; cy: number; hot: boolean }

/**
 * Each dot is one look-alike field. Dots are stacked in the histogram's bins, because the API
 * reports bins and not per-field values. Exactly n_at_least_as_extreme dots are darkened,
 * counted in from the extreme end, so the picture and the sentence cannot disagree.
 */
export function PlaceboStrip({ test, kind }: { test: PlaceboTest | null | undefined; kind: "optical" | "sar" }) {
  const { t, lang } = useI18n();
  const [ref, width] = useWidth<HTMLDivElement>(340);
  const [hover, setHover] = useState<number | null>(null);

  const usable = !!test && !test.insufficient_reason && test.n_placebos > 0 && test.histogram_counts.length > 0 && test.histogram_edges.length === test.histogram_counts.length + 1;

  const model = useMemo(() => {
    if (!usable || !test) return null;
    const { histogram_edges: edges, histogram_counts: counts, plot_value, placebo_median, n_at_least_as_extreme: k } = test;
    const m = { l: 10, r: 10, t: 54, b: 34 };
    const lo = Math.min(edges[0], plot_value);
    const hi = Math.max(edges[edges.length - 1], plot_value);
    const span = hi - lo || 1;
    const x = linear(lo - span * 0.03, hi + span * 0.03, m.l, width - m.r);
    const maxCount = Math.max(...counts, 1);
    const binW = Math.max(2, Math.abs(x(edges[1]) - x(edges[0])));
    // Dots fill each bin's width in rows, so one dot stays one readable field at any chart width.
    const maxH = width < 480 ? 170 : 230;
    const fit = (dd: number) => {
      const cols = Math.max(1, Math.floor(binW / dd));
      return Math.ceil(maxCount / cols) * dd;
    };
    let d = width < 480 ? 7 : 10;
    while (d > 2.4 && fit(d) > maxH) d -= 0.4;
    const cols = Math.max(1, Math.floor(binW / d));
    const plotH = Math.max(70, fit(d));
    const base = m.t + plotH;
    const height = base + m.b;

    const lowSide = plot_value <= placebo_median;
    const order = counts.map((_, i) => i);
    if (!lowSide) order.reverse();
    let left = k;
    const hotInBin: number[] = counts.map(() => 0);
    for (const i of order) {
      const take = Math.min(left, counts[i]);
      hotInBin[i] = take;
      left -= take;
      if (left <= 0) break;
    }
    const dots: Dot[] = [];
    counts.forEach((c, i) => {
      const center = x((edges[i] + edges[i + 1]) / 2);
      for (let j = 0; j < c; j++) {
        const col = j % cols;
        const row = Math.floor(j / cols);
        dots.push({ cx: center + (col - (cols - 1) / 2) * d, cy: base - (row + 0.5) * d, hot: j < hotInBin[i] });
      }
    });
    const sum = counts.reduce((a, b) => a + b, 0);
    return { m, x, d, base, height, dots, edges, counts, lowSide, sum, lo, hi, binW };
  }, [usable, test, width]);

  if (!test) {
    return <Missing what={t(kind === "sar" ? "placebo.missing_sar" : "placebo.missing_optical")} />;
  }
  if (!model) {
    return (
      <Missing what={t(kind === "sar" ? "placebo.missing_sar" : "placebo.missing_optical")}
        why={test.insufficient_reason ?? t("placebo.no_hist")} />
    );
  }

  const { m, x, d, base, height, dots, edges, counts, sum } = model;
  const px = x(test.plot_value);
  const labelAnchor = px < width * 0.3 ? "start" : px > width * 0.7 ? "end" : "middle";
  const greenness = test.statistic.toLowerCase().includes("ndvi");
  const rare = test.p_value <= 0.05;
  const axisTicks = ticks(model.lo, model.hi, width < 480 ? 3 : 6);
  const hb = hover !== null ? { from: edges[hover], to: edges[hover + 1], n: counts[hover] } : null;
  const hoverLeft = hover !== null ? x((edges[hover] + edges[hover + 1]) / 2) : 0;

  return (
    <div className="placebo">
      <p className="placebo-head">
        {test.n_at_least_as_extreme === 0 ? (
          <span>{t("placebo.none", { n: test.n_placebos })}</span>
        ) : (
          <>
            {/* "4 of 200" in English; Hindi and Telugu put the whole first: "200 में से 4". */}
            <span className="big-count mono">{lang === "en" ? test.n_at_least_as_extreme : test.n_placebos}</span>
            <span className="big-of"> {t("placebo.of")} </span>
            <span className="big-count mono">{lang === "en" ? test.n_placebos : test.n_at_least_as_extreme}</span>{" "}
            <span>{t(rare ? "placebo.rare" : "placebo.common")}</span>
          </>
        )}
      </p>
      <p className="how-to-read">{t("placebo.read")}</p>

      <div className="chart" ref={ref} onMouseLeave={() => setHover(null)}>
        <svg width={width} height={height} role="img" aria-label={t("placebo.aria", { k: test.n_at_least_as_extreme, n: test.n_placebos })}>
          <line x1={m.l} x2={width - m.r} y1={base} y2={base} className="axis" />
          {axisTicks.map((v) => (
            <g key={v} transform={`translate(${x(v)},${base})`}>
              <line y2={5} className="axis" />
              <text y={18} textAnchor="middle" className="tick">{rawNum(v)}</text>
            </g>
          ))}
          {dots.map((p, i) => (
            <circle key={i} cx={p.cx} cy={p.cy} r={Math.max(1, d / 2 - 0.5)} className={p.hot ? "dot dot-hot" : "dot"} />
          ))}
          <line x1={px} x2={px} y1={m.t - 14} y2={base} className="yours-stem" />
          <circle cx={px} cy={base} r={9} className="yours-dot" />
          <text x={px} y={m.t - 34} textAnchor={labelAnchor} className="yours-label">{t("placebo.yours")}</text>
          <text x={px} y={m.t - 18} textAnchor={labelAnchor} className="yours-value">{rawNum(test.plot_value)}</text>
          {counts.map((c, i) => (
            <rect
              key={i}
              x={Math.min(x(edges[i]), x(edges[i + 1]))}
              y={m.t}
              width={Math.max(8, Math.abs(x(edges[i + 1]) - x(edges[i])))}
              height={base - m.t}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onClick={() => setHover((h) => (h === i ? null : i))}
            >
              <title>{`${rawNum(edges[i])} … ${rawNum(edges[i + 1])}: ${c}`}</title>
            </rect>
          ))}
        </svg>
        {hb && (
          <div className="tip" style={{ left: Math.min(width - 150, Math.max(0, hoverLeft - 70)), top: 2 }}>
            <span className="mono">{rawNum(hb.from)} … {rawNum(hb.to)}</span>
            <span>{t("placebo.tip", { n: hb.n })}</span>
          </div>
        )}
      </div>
      <div className="axis-words">
        <span>← {t(greenness ? "placebo.left_green" : "placebo.left_sar")}</span>
        <span>{t(greenness ? "placebo.right_green" : "placebo.right_sar")} →</span>
      </div>

      <div className="legend">
        <span><i className="key key-dot-hot" /> {t("placebo.key_hot")}</span>
        <span><i className="key key-dot" /> {t("placebo.key_rest")}</span>
        <span><i className="key key-yours" /> {t("placebo.yours")}</span>
      </div>

      <details className="fine">
        <summary>{t("placebo.numbers")}</summary>
        <table className="ledger">
          <tbody>
            <tr><th>{t("placebo.n")}</th><td className="mono">{test.n_placebos}</td></tr>
            <tr><th>{t("placebo.k")}</th><td className="mono">{test.n_at_least_as_extreme}</td></tr>
            <tr><th>{t("placebo.p")}</th><td className="mono">{rawNum(test.p_value)}</td></tr>
            <tr><th>{t("placebo.statistic")}</th><td className="mono">{test.statistic}</td></tr>
            <tr><th>{t("placebo.yours")}</th><td className="mono">{rawNum(test.plot_value)}</td></tr>
            <tr><th>{t("placebo.median")}</th><td className="mono">{rawNum(test.placebo_median)}</td></tr>
            <tr><th>{t("placebo.range90")}</th><td className="mono">{num(test.placebo_p05, 4)} … {num(test.placebo_p95, 4)}</td></tr>
            <tr><th>{t("placebo.seed")}</th><td className="mono">{test.seed}</td></tr>
            {sum !== test.n_placebos && <tr><th>{t("placebo.binned")}</th><td className="mono">{sum}</td></tr>}
          </tbody>
        </table>
      </details>
    </div>
  );
}
