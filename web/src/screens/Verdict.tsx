import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { useI18n, translateRubric, keyLabel, type Key } from "../i18n";
import { ApiError, getCase, pdfUrl, startInvestigation, type CaseEnvelope } from "../api";
import { linkProps, navigate } from "../router";
import { Icon } from "../components/Icon";
import { Stamp } from "../components/Stamp";
import { ErrorNote, Loading, Missing, useInView } from "../components/Bits";
import { ObjectionCard } from "../components/ObjectionCard";
import { Voice } from "../components/Voice";
import { TenFieldDraw } from "../components/TenFieldDraw";
import { Testimony } from "../components/Testimony";
import { Countdown } from "../components/Countdown";
import { BeforeAfter } from "../charts/BeforeAfter";
import { PlaceboStrip } from "../charts/PlaceboStrip";
import { TwinChart } from "../charts/TwinChart";
import { TimelineChart } from "../charts/TimelineChart";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { dateTimeLabel, dayLabel, num, pct } from "../format";
import type { Evidence, VerdictLevel } from "../types";

const AnomalyMap = lazy(() => import("../map/AnomalyMap"));
const Vanishing = lazy(() => import("../map/Vanishing"));

const SCALE: VerdictLevel[] = ["strong", "moderate", "weak"];

function Exhibit({ mark, title, lead, children, id }: { mark: string; title: string; lead?: string; children: React.ReactNode; id: string }) {
  const { t } = useI18n();
  return (
    <section className="exhibit" id={id} aria-labelledby={`${id}-t`}>
      <header className="exhibit-side">
        <p className="exhibit-mark"><span>{t("ex.label")}</span> <b>{mark}</b></p>
        <h2 id={`${id}-t`} className="exhibit-title">{title}</h2>
        {lead && <p className="exhibit-lead">{lead}</p>}
      </header>
      <div className="exhibit-body">
        <ErrorBoundary>{children}</ErrorBoundary>
      </div>
    </section>
  );
}

function LevelScale({ level }: { level: VerdictLevel }) {
  const { t } = useI18n();
  const off = level === "insufficient" || level === "not_damage_likely_harvest";
  return (
    <div className="scale" role="img" aria-label={t(`level.${level}` as Key)}>
      <div className="scale-main">
        <span className="scale-cap">{t("scale.how_strong")}</span>
        <ol>
          {SCALE.map((l) => (
            <li key={l} className={l === level ? "on" : ""}>
              <i aria-hidden="true" />
              <span>{t(`scale.${l}` as Key)}</span>
            </li>
          ))}
        </ol>
      </div>
      <div className={`scale-other ${off ? "on" : ""}`}>
        {(["insufficient", "not_damage_likely_harvest"] as VerdictLevel[]).map((l) => (
          <span key={l} className={l === level ? "on" : ""}>{t(`scale.${l}` as Key)}</span>
        ))}
      </div>
    </div>
  );
}

function AnomalyExhibit({ ev }: { ev: Evidence }) {
  const { t } = useI18n();
  const [ref, seen] = useInView<HTMLDivElement>("400px");
  const chips = ev.chips.filter((c) => (c.kind === "delta_map" || c.kind === "sar_change") && c.bounds);
  if (chips.length === 0) {
    return <Missing what={t("anom.missing")} why={ev.optical.post ? null : t("anom.no_pair")} />;
  }
  return (
    <div ref={ref} className="anomaly-slot">
      {seen ? (
        <Suspense fallback={<Loading what={t("loading.map")} />}>
          <AnomalyMap chips={chips} polygon={ev.plot.geometry} />
        </Suspense>
      ) : <Loading what={t("loading.map")} />}
    </div>
  );
}

function PastYears({ ev }: { ev: Evidence }) {
  const { t } = useI18n();
  const h = ev.history;
  if (!h || h.years.length === 0) return <Missing what={t("hist.missing")} why={h?.note ?? null} />;
  return (
    <>
      <div className="table-scroll">
        <table className="ledger">
          <thead><tr><th>{t("hist.year")}</th><th>{t("hist.pre")}</th><th>{t("hist.delta")}</th><th>{t("hist.note")}</th></tr></thead>
          <tbody>
            {h.years.map((y) => (
              <tr key={y.year}>
                <td className="mono">{y.year}</td>
                <td className="mono">{num(y.pre_ndvi, 3)}</td>
                <td className="mono">{num(y.delta_ndvi, 3, { signed: true })}</td>
                <td className="small" lang="en">{y.note ?? (y.pre_scene_id ? "" : t("hist.no_scene"))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">
        {t("hist.typical")}: <span className="mono">{num(h.typical_delta, 3, { signed: true })}</span> · {t("hist.excess")}: <span className="mono">{num(h.excess_vs_history, 3, { signed: true })}</span>
      </p>
      {h.downweighted && <p className="small">{t("hist.downweighted")}</p>}
      {h.note && <p className="small" lang="en">{h.note}</p>}
    </>
  );
}

function Corroboration({ ev }: { ev: Evidence }) {
  const { t, lang } = useI18n();
  const w = ev.weather;
  return (
    <div className="corro">
      {w ? (
        <div>
          <p className="corro-line">
            <Stamp size="sm" tone={w.corroborated ? "ink" : "muted"}>{t(w.corroborated ? "corro.yes" : "corro.silent")}</Stamp>
          </p>
          {!w.corroborated && <p>{t("corro.cant_see")}</p>}
          <p className="small" lang="en">{w.grid_note}</p>
          <table className="ledger">
            <tbody>
              <tr><th>{t("corro.rain_window")}</th><td className="mono">{num(w.precip_mm_event_window, 1)} mm</td></tr>
              <tr><th>{t("corro.max_day")}</th><td className="mono">{num(w.max_daily_mm, 1)} mm</td></tr>
              <tr><th>{t("corro.hail_hours")}</th><td className="mono">{w.hail_code_hours ?? "—"}</td></tr>
              <tr><th>{t("corro.thunder_hours")}</th><td className="mono">{w.thunder_hours ?? "—"}</td></tr>
              <tr><th>{t("corro.gust")}</th><td className="mono">{num(w.max_gust_kmh, 0)} km/h</td></tr>
              <tr><th>{t("corro.source")}</th><td><span lang="en">{w.source}</span> · <span className="mono small">{dateTimeLabel(w.fetched_at, lang)}</span></td></tr>
            </tbody>
          </table>
          {w.proposed_event_date && (
            <p className="note-line">{t("corro.proposed")} <span className="mono">{dayLabel(w.proposed_event_date, lang)}</span></p>
          )}
        </div>
      ) : (
        <Missing what={t("corro.no_weather")} />
      )}
      <h3 className="h-mini">{t("corro.alerts")}</h3>
      {ev.alerts.length === 0 ? (
        <p className="small faint">{t("corro.no_alerts")}</p>
      ) : (
        <ul className="plain">
          {ev.alerts.map((a) => (
            <li key={a.identifier}>
              {a.url ? <a href={a.url} target="_blank" rel="noreferrer">{a.headline ?? a.identifier}</a> : a.headline ?? a.identifier}
              <br /><span className="small faint" lang="en">{a.source}{a.area ? ` · ${a.area}` : ""}{a.severity ? ` · ${a.severity}` : ""}</span>
              {a.issued && <span className="mono small faint"> · {dateTimeLabel(a.issued, lang)}</span>}
            </li>
          ))}
        </ul>
      )}
      <h3 className="h-mini">{t("corro.news")}</h3>
      {ev.news.length === 0 ? (
        <p className="small faint">{t("corro.no_news")}</p>
      ) : (
        <ul className="plain">
          {ev.news.map((n) => (
            <li key={n.url}>
              <a href={n.url} target="_blank" rel="noreferrer">{n.title}</a>
              {n.date && <span className="mono small faint"> · {n.date}</span>}
              {n.snippet && <p className="small">{n.snippet}</p>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Sources({ ev }: { ev: Evidence }) {
  const { t, lang } = useI18n();
  const numbers = Object.entries(ev.replay?.numbers ?? {});
  return (
    <div className="sources">
      <details className="fold" open={ev.provenance.length <= 6}>
        <summary>{t("src.prov")} <span className="mono">({ev.provenance.length})</span></summary>
        {ev.provenance.length === 0 ? (
          <Missing what={t("src.no_prov")} />
        ) : (
          <div className="table-scroll">
            <table className="ledger">
              <thead><tr><th>{t("src.field")}</th><th>{t("src.source")}</th><th>{t("src.asset")}</th><th>{t("src.when")}</th></tr></thead>
              <tbody>
                {ev.provenance.map((p, i) => (
                  <tr key={i}>
                    <td className="mono small break">{p.field}</td>
                    <td className="small">{p.url ? <a href={p.url} target="_blank" rel="noreferrer">{p.source}</a> : p.source}</td>
                    <td className="mono small break">{p.asset ?? "—"}</td>
                    <td className="mono small">{dateTimeLabel(p.retrieved_at, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>

      <details className="fold">
        <summary>{t("src.scenes")} <span className="mono">({ev.optical.scenes_considered.length})</span></summary>
        {ev.optical.scenes_considered.length === 0 ? (
          <p className="small faint">{t("src.no_scenes")}</p>
        ) : (
          <div className="table-scroll">
            <table className="ledger">
              <thead><tr><th>{t("chart.date")}</th><th>{t("src.scene")}</th><th>{t("tl.qa")}</th><th>{t("src.cloud")}</th><th>{t("src.valid")}</th><th>{t("src.reasons")}</th></tr></thead>
              <tbody>
                {ev.optical.scenes_considered.map((s) => (
                  <tr key={s.id}>
                    <td className="mono small">{dayLabel(s.date, lang)}</td>
                    <td className="mono small break">{s.id}</td>
                    <td>{t(`qa.${s.status}`)}</td>
                    <td className="mono">{num(s.metadata_cloud_pct, 1)}</td>
                    <td className="mono">{pct(s.plot_valid_frac)}</td>
                    <td className="small" lang="en">{s.reasons.join("; ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>

      <details className="fold">
        <summary>{t("src.numbers")} <span className="mono">({numbers.length})</span></summary>
        {numbers.length === 0 ? (
          <Missing what={t("src.no_numbers")} />
        ) : (
          <div className="table-scroll">
            <table className="ledger">
              <tbody>
                {numbers.map(([k, v]) => (
                  <tr key={k}><th className="mono small break">{k}</th><td className="mono">{v ?? t("missing.short")}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </div>
  );
}

function RunAgain({ caseId }: { caseId: string }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const go = async () => {
    setBusy(true);
    setErr(null);
    try {
      const { run_id } = await startInvestigation(caseId);
      navigate(`/case/${encodeURIComponent(caseId)}/investigate?run=${encodeURIComponent(run_id)}`);
    } catch (e) {
      setErr(e);
      setBusy(false);
    }
  };
  return (
    <>
      <button className="btn btn-primary btn-big" onClick={go} disabled={busy}><Icon name="retry" /> {t("trace.run_again")}</button>
      {err !== null && <ErrorNote error={err} />}
    </>
  );
}

export default function VerdictScreen({ caseId }: { caseId: string }) {
  const { t, lang } = useI18n();
  const [env, setEnv] = useState<CaseEnvelope | null>(null);
  const [err, setErr] = useState<unknown>(null);

  const load = useCallback((signal?: AbortSignal) => {
    setErr(null);
    getCase(caseId, signal).then(setEnv).catch((e) => { if (!signal?.aborted) setErr(e); });
  }, [caseId]);

  useEffect(() => {
    const ctl = new AbortController();
    load(ctl.signal);
    return () => ctl.abort();
  }, [load]);

  if (err) {
    const gone = err instanceof ApiError && err.status === 404;
    return <div className="page narrow">{gone ? <p className="notice">{t("case.not_found")}</p> : <ErrorNote error={err} onRetry={() => load()} />}</div>;
  }
  if (!env) return <div className="page narrow"><Loading what={t("loading.case")} /></div>;

  const ev = env.evidence;
  const c = env.case;

  if (!ev) {
    const active = c.active_run_id;
    const nextPath = !c.plot ? `/case/${encodeURIComponent(caseId)}/plot` : `/case/${encodeURIComponent(caseId)}/investigate${active ? `?run=${encodeURIComponent(active)}` : ""}`;
    return (
      <div className="page narrow">
        <p className="eyebrow">{t("verdict.eyebrow")}</p>
        <h1 className="h-page">{t(active ? "verdict.running" : "verdict.none")}</h1>
        <p className="lede">{t(active ? "verdict.running_body" : !c.plot ? "verdict.none_plot" : "verdict.none_body")}</p>
        {c.latest_run?.error && <p className="small" lang="en">{c.latest_run.error}</p>}
        <a className="btn btn-primary btn-big" {...linkProps(nextPath)}>{t(active ? "verdict.watch" : !c.plot ? "verdict.go_plot" : "verdict.go_run")} <Icon name="arrow" /></a>
      </div>
    );
  }

  const v = ev.verdict;
  const headline = v ? (lang === "te" ? v.headline_te ?? v.headline_en : lang === "hi" ? v.headline_hi : v.headline_en) : null;
  const explanation = (lang === "te" ? ev.explanation_te ?? null : lang === "hi" ? ev.explanation_hi : ev.explanation_en) ?? null;
  const voiceText = explanation ?? headline;
  const intimation = ev.deadlines.find((d) => d.type === "intimation_72h");
  // A countdown is shown only for routes where the guidelines set one, and only while it is open.
  const countdown = ev.claim_path?.countdown_applies && intimation?.status === "open" ? intimation : null;
  const recheck = ev.deadlines.find((d) => d.type === "recheck");
  const twinWhy = ev.neighbours?.placebo?.insufficient_reason ?? (ev.optical.post ? null : t("twin.no_post"));
  const sealed = !!ev.evidence_hash;

  return (
    <div className="page verdict">
      <Testimony ev={ev} caseId={caseId} verdictLine={headline} />
      <header className="verdict-top">
        <div className="verdict-main">
          <p className="eyebrow">{t("verdict.eyebrow")} · <span className="mono">{caseId.slice(0, 12)}</span></p>
          {v ? (
            <>
              <h1 className={`verdict-headline level-${v.level}`}>{headline}</h1>
              <LevelScale level={v.level} />
              <p className="plain-level">{t(`level.${v.level}` as Key)}</p>
            </>
          ) : (
            <>
              <h1 className="verdict-headline">{t("verdict.no_verdict")}</h1>
              <p className="lede">{t(c.latest_run?.status === "interrupted" ? "verdict.no_verdict_interrupted" : "verdict.no_verdict_body")}</p>
              {!c.active_run_id && <RunAgain caseId={caseId} />}
            </>
          )}
          {explanation && <p className="explanation">{explanation}</p>}
          {!explanation && v && lang === "te" && <p className="small faint">{t("verdict.te_missing")}</p>}
          <Voice caseId={caseId} text={voiceText} />
          {ev.llm_used === false && <p className="small faint">{t("verdict.no_llm")}</p>}
        </div>

        <aside className="verdict-side">
          <a className={`deadline-card ${countdown ? "deadline-open" : "deadline-path"}`} {...linkProps(`/case/${encodeURIComponent(caseId)}/action`)}>
            {countdown ? (
              <>
                <span className="deadline-cap">{t("deadline.cap_open")}</span>
                <Countdown dueAt={countdown.due_at} size="sm" />
              </>
            ) : (
              <>
                <span className="deadline-cap">{t("path.card_cap")}</span>
                <strong>{ev.claim_path ? t(`route.${ev.claim_path.route}` as Key) : t("path.card_none")}</strong>
              </>
            )}
            <span className="deadline-go">{t("path.card_go")} <Icon name="arrow" size={18} /></span>
          </a>
          {recheck && (
            <p className="small">{t("deadline.recheck")} <span className="mono">{dateTimeLabel(recheck.due_at, lang)}</span></p>
          )}
          <div className="file-facts">
            <p><span>{t("facts.event")}</span> <b>{t(`event.${ev.event.type}` as Key)}</b> · <span className="mono">{dayLabel(ev.event.date, lang)}</span>
              {ev.event.date_source !== "farmer" && <em className="small"> ({t(`date_source.${ev.event.date_source}` as Key)})</em>}</p>
            {ev.event.crop && <p><span>{t("facts.crop")}</span> <b>{ev.event.crop}</b></p>}
            <p><span>{t("facts.area")}</span> <b className="mono">{num(ev.plot.area_ha, 2)} {t("unit.hectare")}</b></p>
          </div>
          <div className="side-actions">
            {sealed ? (
              <>
                <a className="btn" href={pdfUrl(caseId, lang)} target="_blank" rel="noreferrer"><Icon name="download" /> {t("verdict.pdf")}</a>
                <a className="btn" {...linkProps(`/verify/${ev.evidence_hash}`)}><Icon name="check" /> {t("verdict.verify")}</a>
              </>
            ) : (
              <p className="small faint">{t("verdict.not_sealed")}</p>
            )}
          </div>
        </aside>
      </header>

      {v && (v.caveats.length > 0 || v.reasons.length > 0) && (
        <section className="why-grid">
          {v.caveats.length > 0 && (
            <div className="caveats">
              <h2 className="h-sec">{t("verdict.caveats")}</h2>
              <ul>{v.caveats.map((c2, i) => <li key={i}>{translateRubric(c2, lang)}</li>)}</ul>
            </div>
          )}
          {v.reasons.length > 0 && (
            <div className="reasons">
              <h2 className="h-sec">{t("verdict.reasons")}</h2>
              <ul>{v.reasons.map((r, i) => <li key={i}>{translateRubric(r, lang)}</li>)}</ul>
              <p className="small faint">{t("verdict.rubric")} <span className="mono">{v.rubric_version}</span></p>
            </div>
          )}
        </section>
      )}
      {ev.plot.warnings.length > 0 && (
        <p className="notice small">{ev.plot.warnings.map((w) => keyLabel(w, lang)).join(" · ")}</p>
      )}

      <div className="exhibits">
        <section className="signature" aria-labelledby="draw-t">
          <p className="exhibit-mark"><span>{t("ex.label")}</span> <b>{t("ex.draw")}</b></p>
          <h2 id="draw-t" className="signature-title">{t("ex.draw_t")}</h2>
          <ErrorBoundary><TenFieldDraw ev={ev} /></ErrorBoundary>
        </section>

        <section className="signature" aria-labelledby="van-t">
          <p className="exhibit-mark"><span>{t("ex.label")}</span> <b>{t("ex.van")}</b></p>
          <h2 id="van-t" className="signature-title">{t("ex.van_t")}</h2>
          <ErrorBoundary>
            {ev.scale_fade && ev.scale_fade.levels.length > 0 ? (
              <Suspense fallback={<Loading what={t("loading.map")} />}>
                <Vanishing ev={ev} fade={ev.scale_fade} />
              </Suspense>
            ) : (
              <Missing what={t("van.missing")} why={t("van.missing_why")} />
            )}
          </ErrorBoundary>
        </section>

        <Exhibit id="ex-a" mark={t("ex.a")} title={t("ex.ba_t")} lead={t("ex.ba_l")}>
          <BeforeAfter chips={ev.chips} optical={ev.optical} />
          <table className="ledger ledger-keynums">
            <tbody>
              <tr><th>{t("nums.pre")}</th><td className="mono">{num(ev.optical.pre?.ndvi_median, 3)}</td></tr>
              <tr><th>{t("nums.post")}</th><td className="mono">{num(ev.optical.post?.ndvi_median, 3)}</td></tr>
              <tr><th>{t("nums.delta")}</th><td className="mono">{num(ev.optical.plot_delta_ndvi, 3, { signed: true })}</td></tr>
              <tr><th>{t("nums.drop_frac")}</th><td className="mono">{pct(ev.optical.drop_frac)}</td></tr>
              <tr><th>{t("nums.bare")}</th><td className="mono">{pct(ev.optical.post_bare_fraction)}</td></tr>
              <tr><th>{t("nums.pattern")}</th><td>{ev.optical.within_plot_pattern ? t(`pattern.${ev.optical.within_plot_pattern}` as Key) : t("missing.short")}</td></tr>
            </tbody>
          </table>
        </Exhibit>

        <Exhibit id="ex-b" mark={t("ex.b")} title={t("ex.placebo_t")} lead={t("ex.placebo_l")}>
          <PlaceboStrip test={ev.neighbours?.placebo ?? null} kind="optical" />
          {ev.sar?.placebo && <><h3 className="h-mini">{t("placebo.radar_head")}</h3><PlaceboStrip test={ev.sar.placebo} kind="sar" /></>}
        </Exhibit>

        <Exhibit id="ex-c" mark={t("ex.c")} title={t("ex.twin_t")} lead={t("ex.twin_l")}>
          <TwinChart twin={ev.neighbours?.counterfactual ?? null} eventDate={ev.event.date} why={twinWhy} />
        </Exhibit>

        <Exhibit id="ex-d" mark={t("ex.d")} title={t("ex.anom_t")} lead={t("ex.anom_l")}>
          <AnomalyExhibit ev={ev} />
        </Exhibit>

        <Exhibit id="ex-e" mark={t("ex.e")} title={t("ex.tl_t")} lead={t("ex.tl_l")}>
          <TimelineChart points={ev.timeline} weather={ev.weather} eventDate={ev.event.date} />
          <h3 className="h-mini">{t("ex.radar_numbers")}</h3>
          {ev.sar ? (
            ev.sar.usable ? (
              <table className="ledger">
                <tbody>
                  <tr><th>{t("sar.pair")}</th><td className="mono small">{dayLabel(ev.sar.pre_date, lang)} → {dayLabel(ev.sar.post_date, lang)}</td></tr>
                  <tr><th>{t("sar.orbit")}</th><td className="mono small">{ev.sar.orbit_direction ?? "—"} / {ev.sar.relative_orbit ?? "—"}</td></tr>
                  <tr><th>{t("sar.vh")}</th><td className="mono">{num(ev.sar.vh_change_db, 2, { signed: true })} dB</td></tr>
                  <tr><th>{t("sar.nvh")}</th><td className="mono">{num(ev.sar.neighbour_vh_change_db, 2, { signed: true })} dB</td></tr>
                  <tr><th>{t("sar.water")}</th><td className="mono">{pct(ev.sar.new_water_frac, 1)}</td></tr>
                </tbody>
              </table>
            ) : <Missing what={t("sar.missing")} why={ev.sar.reason ?? null} />
          ) : <Missing what={t("sar.missing")} />}
          <h3 className="h-mini">{t("hist.title")}</h3>
          <PastYears ev={ev} />
        </Exhibit>

        <Exhibit id="ex-f" mark={t("ex.f")} title={t("ex.exam_t")} lead={t("ex.exam_l")}>
          {ev.cross_examination.length === 0 ? (
            <Missing what={t("exam.missing")} />
          ) : (
            <div className="record">
              {ev.cross_examination.map((o, i) => <ObjectionCard key={o.id} o={o} index={i} />)}
            </div>
          )}
        </Exhibit>

        <Exhibit id="ex-g" mark={t("ex.g")} title={t("ex.corro_t")} lead={t("ex.corro_l")}>
          <Corroboration ev={ev} />
        </Exhibit>

        <Exhibit id="ex-h" mark={t("ex.h")} title={t("ex.src_t")} lead={t("ex.src_l")}>
          <Sources ev={ev} />
          {ev.evidence_hash && (
            <p className="seal">
              <span>{t("src.hash")}</span>
              <code className="mono break">{ev.evidence_hash}</code>
            </p>
          )}
        </Exhibit>
      </div>

      <div className="cta verdict-next">
        <button className="btn btn-primary btn-big btn-wide" onClick={() => navigate(`/case/${encodeURIComponent(caseId)}/action`)}>
          {t("verdict.next")} <Icon name="arrow" />
        </button>
      </div>
    </div>
  );
}
