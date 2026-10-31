import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { canRunMapLazy, loadMap, type LoadedMap } from "../map/lazy";
import { Icon } from "./Icon";
import { CopyButton, Missing, useInView, usePrefersReducedMotion } from "./Bits";
import { linear, useWidth } from "../charts/util";
import { num, pct, rawNum } from "../format";

/** Small changes keep a third decimal, so +0.005 does not read as nothing. */
const change = (v: number | null | undefined) => num(v, v !== null && v !== undefined && Math.abs(v) < 0.1 ? 3 : 2, { signed: true });
import { bboxOfRing } from "../geo";
import type { Evidence, PolicyClause, SurveyLottery, VillageWitness } from "../types";

/** The exact wording, used only if the run's policy list did not carry the clause (key_rules.json, p. 105). */
const PARA_21_5_8: PolicyClause = {
  clause_id: "21.5.8",
  doc: "PMFBY Operational Guidelines 2023 (effective Kharif 2023)",
  page: 105,
  url: "https://pmfby.amnex.co.in/pmfby/pdf/operational_guidelines_pmfby.pdf",
  text:
    "Wide-spread Localized Calamity: If the Insured area under loss intimation under localized calamity claims in an IU is more than 25% of the total Insured area in the IU during a specific weather event having a single/similar peril, then the event shall be considered as Wide-spread Localized calamity and the sample loss survey will be conducted at 10 different randomly selected crop-land parcels using the loss intimation list across the affected Insurance Unit and average loss %age basis the sample survey shall be applicable to all intimations for the given IU during the specific weather event.",
};

const DROP_MS = 70;
const HOLD_MS = 1500;

function Histogram({ sim, shownDraws, fill, activeAverage }: {
  sim: SurveyLottery; shownDraws: number[]; fill: number; activeAverage: number | null;
}) {
  const { t } = useI18n();
  const [ref, width] = useWidth<HTMLDivElement>(340);
  const edges = sim.histogram_edges;
  const counts = sim.histogram_counts;
  const height = 150;
  const m = { l: 6, r: 6, t: 36, b: 24 };
  const pv = sim.plot_value;
  const lo = Math.min(edges[0], pv ?? edges[0]);
  const hi = Math.max(edges[edges.length - 1], pv ?? edges[0]);
  const span = hi - lo || 1;
  const x = linear(lo - span * 0.04, hi + span * 0.04, m.l, width - m.r);
  const maxC = Math.max(...counts, 1);
  const y = linear(0, maxC, height - m.b, m.t);
  const half = pv !== null ? pv / 2 : null;
  const belowHalf = (a: number, b: number) => half !== null && (pv as number) < 0 ? (a + b) / 2 > half : false;
  const binIdx = (v: number) => {
    const i = edges.findIndex((e, j) => j < counts.length && v >= e && v < edges[j + 1]);
    return i < 0 ? (v < edges[0] ? 0 : counts.length - 1) : i;
  };
  const dotStacks = new Map<number, number>();
  return (
    <div className="chart drw-hist" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={t("draw.hist_aria", { n: sim.n_simulations })}>
        <line x1={m.l} x2={width - m.r} y1={height - m.b} y2={height - m.b} className="axis" />
        {counts.map((c, i) => {
          const x0 = x(edges[i]);
          const x1 = x(edges[i + 1]);
          const w = Math.max(1, Math.abs(x1 - x0) - 1.5);
          const h = (height - m.b - y(c)) * fill;
          return <rect key={i} x={Math.min(x0, x1) + 0.75} width={w} y={height - m.b - h} height={h} rx={1} className={belowHalf(edges[i], edges[i + 1]) ? "bar bar-light" : "bar"}><title>{`${rawNum(edges[i])} … ${rawNum(edges[i + 1])}: ${c}`}</title></rect>;
        })}
        {shownDraws.map((a, i) => {
          const bin = binIdx(a);
          const k = dotStacks.get(bin) ?? 0;
          dotStacks.set(bin, k + 1);
          return <circle key={i} cx={x((edges[bin] + edges[bin + 1]) / 2)} cy={height - m.b - 5 - k * 8} r={3.4} className="drw-tick" />;
        })}
        {activeAverage !== null && (
          <g>
            <line x1={x(activeAverage)} x2={x(activeAverage)} y1={m.t - 6} y2={height - m.b} className="drw-now" />
            <text x={x(activeAverage)} y={m.t - 10} textAnchor={x(activeAverage) < width * 0.25 ? "start" : x(activeAverage) > width * 0.75 ? "end" : "middle"} className="drw-now-label">{t("draw.this_survey")}</text>
          </g>
        )}
        {pv !== null && (
          <g>
            <line x1={x(pv)} x2={x(pv)} y1={m.t - 16} y2={height - m.b} className="yours-stem" />
            <circle cx={x(pv)} cy={height - m.b} r={7} className="yours-dot" />
            <text x={x(pv)} y={m.t - 22} textAnchor={x(pv) < width * 0.25 ? "start" : x(pv) > width * 0.75 ? "end" : "middle"} className="yours-label">{t("placebo.yours")}</text>
          </g>
        )}
        <text x={m.l} y={height - 6} className="tick">{rawNum(edges[0])}</text>
        <text x={width - m.r} y={height - 6} textAnchor="end" className="tick">{rawNum(edges[edges.length - 1])}</text>
      </svg>
    </div>
  );
}

function ParcelField({ ev, sim, drawIndex, landed }: { ev: Evidence; sim: SurveyLottery; drawIndex: number; landed: number }) {
  const { t } = useI18n();
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LoadedMap | null>(null);
  const [tick, setTick] = useState(0);
  const [noMap, setNoMap] = useState(false);
  const ring = ev.plot.geometry.coordinates[0];
  const [centroidLon, centroidLat] = ev.plot.centroid;
  const allParcels = useMemo(() => sim.sample_draws.flatMap((d) => d.parcels), [sim]);
  const bounds = useMemo(() => bboxOfRing([...allParcels, ...ring]), [allParcels, ring]);

  useEffect(() => {
    let cancelled = false;
    let cleanup = () => {};
    if (!canRunMapLazy() || !host.current) { setNoMap(true); return; }
    loadMap().then((lib) => {
      if (cancelled || !host.current) return;
      const m = new lib.maplibregl.Map({
        container: host.current,
        style: lib.satelliteStyle(),
        bounds: [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
        fitBoundsOptions: { padding: 44 },
        interactive: false,
        attributionControl: { compact: false },
      });
      const rerender = () => setTick((n) => n + 1);
      m.on("move", rerender);
      m.on("resize", rerender);
      m.on("load", rerender);
      mapRef.current = m as unknown as LoadedMap;
      rerender();
      cleanup = () => { m.remove(); mapRef.current = null; };
    }).catch(() => setNoMap(true));
    return () => { cancelled = true; cleanup(); };
  }, [bounds]);

  void tick;

  const [boxRef, width] = useWidth<HTMLDivElement>(340);
  const height = width < 480 ? 300 : 420;
  // Without a map, the same geometry is drawn on plain paper, on a scale fitted to the data.
  const fx = linear(bounds[0], bounds[2], 30, width - 30);
  const fy = linear(bounds[1], bounds[3], height - 30, 30);
  const proj = (lon: number, lat: number): [number, number] => {
    const m = mapRef.current;
    if (m) {
      const p = m.project([lon, lat]);
      return [p.x, p.y];
    }
    return [fx(lon), fy(lat)];
  };

  // Parcels share the plot's shape and size: a farmer-shaped footprint at each real centre.
  const shape = (lon: number, lat: number) =>
    ring.map(([x, y]) => proj(x - centroidLon + lon, y - centroidLat + lat).map((v) => v.toFixed(1)).join(",")).join(" ");
  const plotPts = ring.map(([x, y]) => proj(x, y).map((v) => v.toFixed(1)).join(",")).join(" ");
  const draw = sim.sample_draws[drawIndex];

  return (
    <div className={`drw-map ${noMap ? "drw-map-paper" : ""}`} ref={boxRef} style={{ height }}>
      <div ref={host} className="map-host" />
      <svg className="drw-overlay" width={width} height={height} aria-hidden="true">
        {draw?.parcels.slice(0, landed).map(([lon, lat], i) => {
          const [cx, cy] = proj(lon, lat);
          return (
            <g key={`${drawIndex}-${i}`} className="parcel" style={{ transformOrigin: `${cx}px ${cy}px` }}>
              <polygon points={shape(lon, lat)} className="parcel-shape" />
              {/* A parcel can be a few pixels wide on this map, so a ring keeps it findable. */}
              <circle cx={cx} cy={cy} r={8} className="parcel-ring" />
              <text x={cx} y={cy + 4} textAnchor="middle" className="parcel-no">{i + 1}</text>
            </g>
          );
        })}
        <polygon points={plotPts} className="drw-plot" />
        <circle cx={proj(centroidLon, centroidLat)[0]} cy={proj(centroidLon, centroidLat)[1]} r={12} className="drw-plot-ring" />
      </svg>
      <span className="drw-yours-tag">{t("draw.map_key")}</span>
      {noMap && <p className="map-note">{t("draw.no_basemap")}</p>}
    </div>
  );
}

function AffectedShare({ v }: { v: VillageWitness }) {
  const { t } = useI18n();
  if (v.affected_share === null) {
    return <Missing what={t("draw.share_missing")} why={v.affected_definition} />;
  }
  const share = Math.max(0, Math.min(1, v.affected_share));
  return (
    <div className="affected">
      <h3 className="h-mini">{t("draw.share_title")}</h3>
      <p className="affected-big"><b className="mono">{pct(v.affected_share)}</b> <span>{t("draw.share_sentence", { km: num(v.radius_m / 1000, 1) })}</span></p>
      <div className="affected-bar" role="img" aria-label={t("draw.share_aria", { pct: pct(v.affected_share) })}>
        <span className="affected-fill" style={{ width: `${share * 100}%` }} />
        <span className="affected-line" style={{ left: "25%" }} />
        <span className="affected-line-label" style={{ left: "25%" }}>{t("draw.line25")}</span>
      </div>
      <p className="small"><strong>{t("draw.share_indicator")}</strong></p>
      <p className="small faint" lang="en">{v.affected_definition} · <span className="mono">{v.n_cropland_pixels}</span> px · {v.sensor === "s2" ? "Sentinel-2" : "Sentinel-1"}</p>
    </div>
  );
}

function ShareBlock({ ev, v, applies }: { ev: Evidence; v: VillageWitness | null | undefined; applies: boolean }) {
  const { t } = useI18n();
  const [lon, lat] = ev.plot.centroid;
  // Rounded to about a kilometre, so the link shows the area and not this farmer's field.
  const url = `${location.origin}/?near=${lat.toFixed(2)},${lon.toFixed(2)}`;
  const msg = `${t("draw.share_msg")} ${url}`;
  const share = async () => {
    try { await navigator.share({ text: t("draw.share_msg"), url }); } catch { /* the reader closed it */ }
  };
  return (
    <div className="drw-share">
      <h3 className="h-mini">{t("draw.share_h")}</h3>
      <p className="small">{t(applies ? "draw.share_why" : "draw.share_why_illus")}</p>
      {typeof v?.nearby_real_cases === "number" && v.nearby_real_cases > 0 && (
        <p className="nearby"><b className="mono">{v.nearby_real_cases}</b> {t("draw.nearby")}</p>
      )}
      <div className="btn-row wrap">
        {"share" in navigator && <button className="btn" onClick={share}><Icon name="share" /> {t("draw.share_btn")}</button>}
        <a className="btn" href={`https://wa.me/?text=${encodeURIComponent(msg)}`} target="_blank" rel="noreferrer"><Icon name="share" /> WhatsApp</a>
        <CopyButton text={url} label={t("draw.copy_link")} />
      </div>
    </div>
  );
}

/** The headline exhibit: para 21.5.8's sampling run on real pixels, to show how far one draw's average can move. */
export function TenFieldDraw({ ev }: { ev: Evidence }) {
  const { t } = useI18n();
  const reduced = usePrefersReducedMotion();
  const v = ev.village;
  const sim = v?.lottery ?? null;
  const [slot, inView] = useInView<HTMLDivElement>("-10%");
  const [drawIndex, setDrawIndex] = useState(0);
  const [landed, setLanded] = useState(0);
  const [phase, setPhase] = useState<"idle" | "dropping" | "settled" | "final">("idle");
  const [playing, setPlaying] = useState(false);
  const [fill, setFill] = useState(0);
  const [doneDraws, setDoneDraws] = useState<number[]>([]);
  const timer = useRef(0);

  const draws = sim?.sample_draws ?? [];
  const usable = !!sim && !sim.insufficient_reason && sim.histogram_counts.length > 0 && sim.histogram_edges.length === sim.histogram_counts.length + 1;

  const toFinal = useCallback(() => {
    window.clearTimeout(timer.current);
    setPlaying(false);
    setPhase("final");
    setFill(1);
    setLanded(sim?.sample_draws[0]?.parcels.length ?? 0);
    setDoneDraws(sim?.sample_draws.map((d) => d.average) ?? []);
  }, [sim]);

  const play = useCallback(() => {
    if (!draws.length) { toFinal(); return; }
    setDrawIndex(0);
    setDoneDraws([]);
    setFill(0);
    setLanded(0);
    setPhase("dropping");
    setPlaying(true);
  }, [draws.length, toFinal]);

  // Starts itself once, when it scrolls into view.
  const started = useRef(false);
  useEffect(() => {
    if (!usable || started.current || !inView) return;
    started.current = true;
    if (reduced) toFinal();
    else play();
  }, [usable, inView, reduced, play, toFinal]);

  useEffect(() => {
    if (!playing) return;
    const draw = draws[drawIndex];
    if (!draw) return;
    const total = draw.parcels.length;
    if (phase === "dropping") {
      // The first draws are read slowly, and later ones speed up as the pattern becomes clear.
      const pace = drawIndex < 2 ? DROP_MS * 2 : DROP_MS;
      if (landed < total) {
        timer.current = window.setTimeout(() => setLanded((n) => n + 1), pace);
      } else {
        setPhase("settled");
        setDoneDraws((d) => [...d, draw.average]);
      }
    } else if (phase === "settled") {
      const hold = drawIndex < 2 ? HOLD_MS : Math.max(500, HOLD_MS - 300 * drawIndex);
      timer.current = window.setTimeout(() => {
        if (drawIndex + 1 < draws.length) {
          setDrawIndex((i) => i + 1);
          setLanded(0);
          setPhase("dropping");
        } else {
          setPlaying(false);
          setPhase("final");
        }
      }, hold);
    }
    return () => window.clearTimeout(timer.current);
  }, [playing, phase, landed, drawIndex, draws]);

  // The full histogram grows only after the real draws have been shown.
  useEffect(() => {
    if (phase !== "final") return;
    if (reduced) { setFill(1); return; }
    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / 1400);
      setFill(p * p * (3 - 2 * p));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [phase, reduced]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  // The corpus holds para 21.5.8 whole, which runs to pages. The quote is the sentence the exhibit is about.
  const found = ev.policy.find((c) => c.clause_id === "21.5.8" && c.text.includes("10 different"));
  const clause = found && found.text.length <= 900 ? found : PARA_21_5_8;

  if (!v) {
    return <div className="tenfield"><Quote clause={clause} /><Missing what={t("draw.missing")} /><Caveats /></div>;
  }
  if (!usable || !sim) {
    return (
      <div className="tenfield">
        <Quote clause={clause} />
        <Missing what={t("draw.missing")} why={sim?.insufficient_reason ?? (sim ? t("draw.no_hist") : null)} />
        <AffectedShare v={v} />
        <Caveats />
        <ShareBlock ev={ev} v={v} applies={sim?.rule_applicability === "may_apply"} />
      </div>
    );
  }

  const draw = draws[drawIndex];
  const applies = sim.rule_applicability === "may_apply";
  const settled = phase === "settled" || phase === "final";
  const isFinal = phase === "final";
  const shownAverage = settled && draw && !isFinal ? draw.average : null;
  const share = sim.share_below_half_of_plot;

  return (
    <div className="tenfield" ref={slot}>
      <p className={`drw-applies ${applies ? "" : "drw-applies-no"}`}>{t(applies ? "draw.may_apply" : "draw.illustration")}</p>
      <p className="drw-claim">
        {t("draw.claim_a")} <b className="mono">{sim.parcels_per_survey}</b> {t("draw.claim_b")}
      </p>

      <div className="drw-stage">
        <div className="drw-left">
          {draws.length > 0 ? (
            <ParcelField ev={ev} sim={sim} drawIndex={drawIndex} landed={landed} />
          ) : (
            <Missing what={t("draw.no_draws")} />
          )}
          <div className="drw-controls">
            <button className="btn" onClick={play}><Icon name="retry" /> {t("draw.again")}</button>
            {draws.length > 0 && (
              <span className="small faint">
                {isFinal ? t("draw.drawn_all", { n: draws.length }) : t("draw.draw_of", { i: drawIndex + 1, n: draws.length })}
              </span>
            )}
            {!isFinal && <button className="linkish small" onClick={toFinal}>{t("draw.skip")}</button>}
          </div>
        </div>

        <div className="drw-right">
          <div className="drw-numbers">
            <div className="drw-num drw-num-yours">
              <span className="drw-cap">{t("draw.your_field")}</span>
              <b className="mono">{change(sim.plot_value)}</b>
            </div>
            <div className={`drw-num drw-num-avg ${settled && !isFinal ? "drw-settle" : ""}`} key={isFinal ? "final" : `${drawIndex}-${settled}`}>
              <span className="drw-cap">{isFinal ? t("draw.median") : t("draw.avg_of_10", { n: sim.parcels_per_survey })}</span>
              <b className="mono">
                {isFinal ? change(sim.average_median) : shownAverage !== null ? change(shownAverage) : "…"}
              </b>
            </div>
          </div>
          <Histogram sim={sim} shownDraws={doneDraws} fill={fill} activeAverage={shownAverage} />
          <p className="small faint drw-axis-word">{t("draw.axis")}</p>
          <div className={`drw-verdict ${isFinal ? "drw-verdict-on" : ""}`}>
            {sim.plot_value !== null && sim.plot_value >= 0 && <p className="drw-big-sentence">{t("draw.no_fall")}</p>}
            {share !== null && sim.plot_value !== null && sim.plot_value < 0 && (
              <p className="drw-big-sentence">
                {t("draw.of_surveys", { n: sim.n_simulations })} <b className="mono">{pct(share)}</b> {t("draw.below_half")}
              </p>
            )}
            {sim.plot_value === null && <p className="small">{t("draw.no_half")}</p>}
            <p className="small">
              {t("draw.range_a")} <b className="mono">{change(sim.average_p05)}</b> {t("draw.range_b")} <b className="mono">{change(sim.average_p95)}</b> {t("draw.range_c")}
            </p>
            <p className="drw-move">{t("draw.how_much")}</p>
          </div>
        </div>
      </div>

      <div className="drw-below">
        <Quote clause={clause} />
        <Caveats />
      </div>
      <div className="drw-below">
        <AffectedShare v={v} />
        <ShareBlock ev={ev} v={v} applies={sim?.rule_applicability === "may_apply"} />
      </div>
      <p className="small faint">
        {t("draw.tech", { n: sim.n_simulations, c: sim.n_candidate_parcels })} · <span className="mono">{sim.statistic}</span> · seed <span className="mono">{sim.seed}</span>
      </p>
    </div>
  );
}

function Quote({ clause }: { clause: PolicyClause }) {
  const { t } = useI18n();
  return (
    <figure className="drw-quote">
      <figcaption>{t("draw.quote_cap")}</figcaption>
      <blockquote lang="en">{clause.text}</blockquote>
      <footer>
        <span className="mono">{t("clause.label")} {clause.clause_id}</span> · <span lang="en">{clause.doc}</span>
        {clause.page ? <> · {t("clause.page")} <span className="mono">{clause.page}</span></> : null}
        {clause.url && <> · <a href={clause.url} target="_blank" rel="noreferrer">{t("clause.open")}</a></>}
      </footer>
      <p className="small drw-gloss">{t("draw.gloss")}</p>
    </figure>
  );
}

function Caveats() {
  const { t } = useI18n();
  return (
    <div className="drw-caveats">
      <h3 className="h-mini">{t("draw.caveats_h")}</h3>
      <ul>
        <li>{t("draw.cav1")}</li>
        <li>{t("draw.cav2")}</li>
        <li>{t("draw.cav3")}</li>
      </ul>
    </div>
  );
}
