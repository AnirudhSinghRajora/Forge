import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n, type Key } from "../i18n";
import { ApiError, getCase, startInvestigation } from "../api";
import { readSse } from "../sse";
import { navigate, linkProps } from "../router";
import { Icon } from "../components/Icon";
import { Stamp } from "../components/Stamp";
import { ObjectionCard } from "../components/ObjectionCard";
import { ErrorNote, Loading, useNow, usePrefersReducedMotion } from "../components/Bits";
import { clock, dateTimeLabel, dayLabel } from "../format";
import { splitFacts, TechnicalFacts } from "../components/Facts";
import type { Objection, TraceEvent } from "../types";

type Conn = "connecting" | "open" | "retrying" | "closed" | "gone";

function loadCache(runId: string): TraceEvent[] {
  try {
    const raw = sessionStorage.getItem(`fs.trace.${runId}`);
    return raw ? (JSON.parse(raw) as TraceEvent[]) : [];
  } catch {
    return [];
  }
}

/**
 * Reads the run's trace and survives anything: a refresh resumes from the cached events with
 * ?after=seq, and a dropped connection reconnects from the last seq with backoff. The run itself
 * lives on the server, so the investigation does not depend on this page staying open.
 */
function useTrace(runId: string | null) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [restored, setRestored] = useState(0);
  const [conn, setConn] = useState<Conn>("connecting");
  const [attempt, setAttempt] = useState(0);
  const [resume, setResume] = useState(0);

  useEffect(() => {
    if (!runId) return;
    const ctl = new AbortController();
    const cached = loadCache(runId);
    let list = cached;
    let last = cached.length ? cached[cached.length - 1].seq : 0;
    setEvents(cached);
    setRestored(cached.length);
    let finished = cached.some((e) => e.type === "done");
    let tries = 0;
    let wake: (() => void) | null = null;

    const save = () => {
      try { sessionStorage.setItem(`fs.trace.${runId}`, JSON.stringify(list)); } catch { /* full or private */ }
    };
    const onOnline = () => wake?.();
    window.addEventListener("online", onOnline);

    (async () => {
      if (finished) { setConn("closed"); return; }
      for (;;) {
        if (ctl.signal.aborted) return;
        setConn(tries === 0 ? "connecting" : "retrying");
        setAttempt(tries);
        try {
          await readSse(
            `/api/runs/${encodeURIComponent(runId)}/stream?after=${last}`,
            (m) => {
              let ev: TraceEvent;
              try { ev = JSON.parse(m.data) as TraceEvent; } catch { return; }
              if (typeof ev.seq !== "number" || ev.seq <= last) return;
              last = ev.seq;
              list = [...list, ev];
              setEvents(list);
              save();
              tries = 0;
              if (ev.type === "done") finished = true;
            },
            ctl.signal,
            () => setConn("open"),
          );
          // The server ends the stream once it has sent everything for a finished run.
          if (finished) { setConn("closed"); return; }
        } catch (e) {
          if (ctl.signal.aborted) return;
          if ((e as { status?: number }).status === 404) { setConn("gone"); return; }
        }
        tries += 1;
        setConn("retrying");
        setAttempt(tries);
        const wait = Math.min(30000, 1000 * 2 ** Math.min(tries, 5));
        await new Promise<void>((res) => {
          const id = window.setTimeout(res, wait);
          wake = () => { window.clearTimeout(id); res(); };
          ctl.signal.addEventListener("abort", () => { window.clearTimeout(id); res(); }, { once: true });
        });
        wake = null;
      }
    })();

    return () => {
      ctl.abort();
      window.removeEventListener("online", onOnline);
    };
  }, [runId, resume]);

  return { events, restored, conn, attempt, reconnect: () => setResume((n) => n + 1) };
}

/** Replayed backlogs are paced so a story can be read. Live events arrive at their real speed. */
function usePaced(events: TraceEvent[], restored: number) {
  const reduced = usePrefersReducedMotion();
  const [shown, setShown] = useState(0);
  useEffect(() => { setShown((s) => Math.max(s, restored)); }, [restored]);
  useEffect(() => {
    if (shown >= events.length) return;
    if (reduced) { setShown(events.length); return; }
    const id = window.setTimeout(() => setShown((s) => s + 1), events.length - shown > 12 ? 90 : 220);
    return () => window.clearTimeout(id);
  }, [shown, events.length, reduced]);
  return { shown: Math.min(shown, events.length), skip: () => setShown(events.length) };
}

/** The server sends the challenge as the event's title, and the rest of the objection as detail. */
const TOOL_NAMES: Record<string, Key> = {
  optical_compare: "tool.optical_compare", sar_compare: "tool.sar_compare", scale_fade: "tool.scale_fade",
  village_witness: "tool.village_witness", render_chips: "tool.render_chips", timeline: "tool.timeline",
  history: "tool.history", qa_scene: "tool.qa_scene", search_optical: "tool.search_optical", search_sar: "tool.search_sar",
};

const isProvisional = (ev: TraceEvent) => ev.type === "verdict" && ev.detail.provisional === true;

/** The line a reader sees for an event: never a machine name, and never a provisional result as a finding. */
function useEventTitle() {
  const { t, lang } = useI18n();
  return useCallback((ev: TraceEvent): string => {
    if (isProvisional(ev)) return t("trace.provisional");
    if (ev.type === "action" && ev.detail.action === "exhibit") {
      return `${t(`exhibit.${String(ev.detail.exhibit)}` as Key)}: ${t(`exhibit.st_${String(ev.detail.status)}` as Key)}`;
    }
    if (lang === "hi") return ev.title_hi;
    return ev.title_en.replace(/\b(optical_compare|sar_compare|scale_fade|village_witness|render_chips|timeline|history|qa_scene|search_optical|search_sar)\b/g, (m) => t(TOOL_NAMES[m]));
  }, [t, lang]);
}

function asObjection(ev: TraceEvent): Objection | null {
  const d = ev.detail as Partial<Objection>;
  if (typeof d.outcome !== "string") return null;
  return { ...d, challenge_hi: ev.title_hi, challenge_en: ev.title_en } as Objection;
}

const HIDDEN = new Set(["exhibit", "exhibits", "exhibits_pending", "exhibits_started", "provisional", "revised", "sealed", "signature", "pending", "n_clauses", "clause_ids", "unknowns", "intimation", "route", "reason", "objection", "reasons", "scene", "from", "to", "frm", "seq", "headline_hi", "headline_en", "headline_te", "rejected", "caveats", "budget", "country_code", "fallback_used", "tool", "args", "llm", "choice", "excluded", "start", "end", "duration_s", "action", "report", "open_followups", "round", "needed", "corroborated_by", "conceded", "evidence_hash", "due_at", "grid_note", "centroid", "crs", "warnings", "scenes", "rationale", "error", "error_ref"]);

function flatten(d: Record<string, unknown>, prefix = "", depth = 0): [string, unknown][] {
  const out: [string, unknown][] = [];
  for (const [k, v] of Object.entries(d)) {
    if (HIDDEN.has(k)) continue;
    // A tool's result is the event itself, so its fields are named without the wrapper.
    const key = prefix && prefix !== "result" ? `${prefix}.${k}` : k;
    if (v === null || v === undefined) continue;
    if (Array.isArray(v)) { if (v.length) out.push([key, v]); }
    else if (typeof v === "object" && depth < 1) out.push(...flatten(v as Record<string, unknown>, key, depth + 1));
    else if (typeof v !== "string" || v.length <= 60) out.push([key, v]);
  }
  return out;
}

function Numbers({ detail }: { detail: Record<string, unknown> }) {
  const { t, lang } = useI18n();
  const { shown, raw } = useMemo(() => splitFacts(flatten(detail), lang, t), [detail, lang, t]);
  const [open, setOpen] = useState(false);
  if (shown.length === 0 && raw.length === 0) return null;
  const visible = open ? shown : shown.slice(0, 8);
  return (
    <>
      {shown.length > 0 && (
        <dl className="trace-numbers">
          {visible.map((f) => (
            <div key={f.key}>
              <dt>{f.label}</dt>
              <dd className="mono break">{f.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {shown.length > 8 && <button className="linkish small" onClick={() => setOpen((o) => !o)}>{open ? t("trace.less") : t("trace.more", { n: shown.length - 8 })}</button>}
      <TechnicalFacts raw={raw} />
    </>
  );
}

function SceneRejected({ ev, title }: { ev: TraceEvent; title: string }) {
  const { t, lang } = useI18n();
  const raw = (ev.detail.scene && typeof ev.detail.scene === "object" ? ev.detail.scene : ev.detail) as Record<string, unknown>;
  const id = String(raw.id ?? raw.scene_id ?? "");
  const date = typeof raw.date === "string" ? raw.date : null;
  const rs = raw.reasons ?? ev.detail.reasons ?? raw.reason ?? ev.detail.reason;
  const reasons = Array.isArray(rs) ? rs.map(String) : rs ? [String(rs)] : [];
  return (
    <div className="rejected fresh">
      <Stamp size="lg" tone="ink" className="stamp-thump rejected-stamp">{t("trace.rejected")}</Stamp>
      <p className="rejected-title">{title}</p>
      {date && <p className="mono">{dayLabel(date, lang)}</p>}
      {id && <p className="mono small break">{id}</p>}
      {reasons.length > 0 && (lang === "en"
        ? <ul className="rejected-reasons">{reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        : (
          <details className="fine">
            <summary>{t("exhibit.technical")}</summary>
            <ul className="rejected-reasons" lang="en">{reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
          </details>
        ))}
      <Numbers detail={Object.fromEntries(Object.entries(raw).filter(([k]) => !["id", "scene_id", "date", "reasons", "reason", "status", "collection"].includes(k)))} />
    </div>
  );
}

function SensorSwitch({ ev, title }: { ev: TraceEvent; title: string }) {
  const { t, lang } = useI18n();
  const rejected = Array.isArray(ev.detail.rejected) ? (ev.detail.rejected as { id?: string; date?: string; reasons?: string[] }[]) : [];
  return (
    <div className="switch fresh">
      <p className="switch-flow">
        <span className="switch-from"><Icon name="satellite" size={30} /> {t("trace.optical")}</span>
        <span className="switch-arrow" aria-hidden="true">{ev.detail.optical_continues === true ? <b>+</b> : <Icon name="arrow" size={34} />}</span>
        <span className="switch-to"><Icon name="radar" size={30} /> {t("trace.radar")}</span>
      </p>
      <p className="switch-title">{title}</p>
      {rejected.length > 0 && (
        <details className="fine switch-tech">
          <summary>{t("exhibit.technical")}</summary>
          <ul className="small switch-rejected">
            {rejected.map((r, i) => <li key={i}><span className="mono">{dayLabel(r.date, lang)}</span> <span lang="en">{(r.reasons ?? []).join("; ")}</span></li>)}
          </ul>
        </details>
      )}
      <p className="small switch-why">{t("trace.radar_why")}</p>
    </div>
  );
}

function TraceLine({ ev, base, fresh, n }: { ev: TraceEvent; base: number; fresh: boolean; n: number }) {
  const { t } = useI18n();
  const title = useEventTitle()(ev);
  const offset = (new Date(ev.ts).getTime() - base) / 1000;
  const obj = ev.type === "objection" ? asObjection(ev) : null;

  let body: React.ReactNode;
  switch (ev.type) {
    case "scene_rejected": body = <SceneRejected ev={ev} title={title} />; break;
    case "sensor_switch": body = <SensorSwitch ev={ev} title={title} />; break;
    case "objection": body = obj ? <ObjectionCard o={obj} fresh={fresh} /> : <><p>{title}</p><Numbers detail={ev.detail} /></>; break;
    case "step_started": body = <h3 className="trace-step">{title}</h3>; break;
    case "tool_called": body = <p className="trace-asked"><Icon name="satellite" size={18} /> {title}</p>; break;
    case "decision": body = <><p className="trace-decision">{title}</p><Numbers detail={ev.detail} /></>; break;
    case "warning": body = <><p className="trace-warn"><Icon name="warn" size={18} /> {title}</p><Numbers detail={ev.detail} /></>; break;
    case "error": body = <><p className="trace-warn"><Icon name="warn" size={18} /> {title}</p><Numbers detail={ev.detail} /></>; break;
    case "verdict": body = isProvisional(ev) ? <p className="trace-asked"><span className="spinner" aria-hidden="true" /> {title}</p> : <>{ev.detail.revised === true && <p className="small">{t("trace.revised")}</p>}<p className="trace-verdict">{title}</p>{typeof ev.detail.level === "string" && <Stamp size="md" tone="ink" className={fresh ? "stamp-thump" : ""}>{t(`scale.${ev.detail.level}` as Key)}</Stamp>}</>; break;
    case "done": body = <p className="trace-done">{title}</p>; break;
    default: body = <><p>{title}</p><Numbers detail={ev.detail} /></>;
  }
  return (
    <li className={`tline tline-${ev.type} ${fresh ? "fresh" : ""}`}>
      <span className="tline-no mono" aria-hidden="true">{n}</span>
      <span className="tline-at mono" aria-label={`${Math.round(offset)} s`}>+{clock(offset)}</span>
      <div className="tline-body">{body}</div>
    </li>
  );
}

export default function Investigate({ caseId }: { caseId: string }) {
  const { t, lang } = useI18n();
  const [openedAt] = useState(() => Date.now());
  const [runId, setRunId] = useState<string | null>(() => new URLSearchParams(location.search).get("run"));
  const [boot, setBoot] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
  const [restarting, setRestarting] = useState(false);

  useEffect(() => {
    if (runId) return;
    const ctl = new AbortController();
    setBoot(null);
    (async () => {
      const env = await getCase(caseId, ctl.signal);
      const id = env.case.active_run_id ?? env.case.latest_run?.id ?? env.evidence?.run_id;
      if (id) return id;
      if (!env.case.plot) {
        navigate(`/case/${encodeURIComponent(caseId)}/plot`, { replace: true });
        return null;
      }
      const started = await startInvestigation(caseId);
      return started.run_id;
    })()
      .then((id) => {
        if (id) {
          setRunId(id);
          history.replaceState(null, "", `${location.pathname}?run=${encodeURIComponent(id)}`);
        }
      })
      .catch((e) => { if (!ctl.signal.aborted) setBoot(e); });
    return () => ctl.abort();
  }, [caseId, runId, attempt]);

  const { events, restored, conn, attempt: tries, reconnect } = useTrace(runId);
  const { shown, skip } = usePaced(events, restored);
  const visible = events.slice(0, shown);
  const last = visible[visible.length - 1];
  const done = events.some((e) => e.type === "done");
  const fullyShown = shown >= events.length;
  const doneEvent = events.find((e) => e.type === "done");
  const finalStatus = doneEvent?.detail.status;
  // Finished before this page opened: what follows is a recording, and it says so, with its time.
  const replay = !!doneEvent && new Date(doneEvent.ts).getTime() < openedAt - 5000;
  const failed = done && (finalStatus === "failed" || finalStatus === "interrupted");
  const lastError = [...events].reverse().find((e) => e.type === "error");
  const hasVerdict = events.some((e) => e.type === "verdict" && !isProvisional(e));
  const titleOf = useEventTitle();

  const running = !!runId && !done && conn !== "gone";
  const now = useNow(1000, running);
  const base = events[0] ? new Date(events[0].ts).getTime() : now;
  const elapsed = (now - base) / 1000;
  const lastTs = events.length ? new Date(events[events.length - 1].ts).getTime() : now;
  const quiet = Math.max(0, (now - lastTs) / 1000);

  // Follow the newest line, unless the reader has scrolled up to read something.
  const endRef = useRef<HTMLDivElement | null>(null);
  const following = useRef(true);
  useEffect(() => {
    const on = () => {
      const d = document.documentElement;
      following.current = d.scrollHeight - d.scrollTop - d.clientHeight < 260;
    };
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  const reduced = usePrefersReducedMotion();
  useEffect(() => {
    if (following.current && shown > 0) endRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "end" });
  }, [shown, reduced]);

  const rerun = useCallback(async () => {
    setRestarting(true);
    try {
      const { run_id } = await startInvestigation(caseId);
      setRunId(run_id);
      history.replaceState(null, "", `${location.pathname}?run=${encodeURIComponent(run_id)}`);
    } catch (e) {
      setBoot(e);
    } finally {
      setRestarting(false);
    }
  }, [caseId]);

  if (boot) {
    const gone = boot instanceof ApiError && boot.status === 404;
    return (
      <div className="page narrow">
        {gone ? <p className="notice">{t("case.not_found")}</p> : <ErrorNote error={boot} onRetry={() => setAttempt((a) => a + 1)} />}
      </div>
    );
  }

  const nowTitle = last ? titleOf(last) : t("trace.waiting_first");

  return (
    <div className="page trace-page">
      <header className="trace-head">
        <p className="eyebrow">{t("trace.eyebrow")}</p>
        <h1 className="h-page">{t(failed ? "trace.failed" : done ? "trace.title_done" : "trace.title")}</h1>
        <p className="lede">{replay ? t("trace.lede_replay", { when: dateTimeLabel(events[0].ts, lang) }) : t(done ? "trace.lede_done" : "trace.lede")}</p>
      </header>

      {!runId && <Loading what={t("trace.starting")} />}
      {conn === "gone" && <p className="notice" role="alert">{t("trace.gone")}</p>}

      <ol className="transcript" aria-live="polite" aria-relevant="additions">
        {visible.map((ev, i) => (
          <TraceLine key={ev.seq} ev={ev} base={base} fresh={i >= restored} n={i + 1} />
        ))}
      </ol>
      <div ref={endRef} />

      {!fullyShown && (
        <button className="linkish skip-replay" onClick={skip}>{t("trace.skip", { n: events.length - shown })}</button>
      )}

      {hasVerdict && !done && fullyShown && (
        <section className="trace-end">
          <a className="btn btn-primary btn-big btn-wide" {...linkProps(`/case/${encodeURIComponent(caseId)}`)}>
            {t("trace.read_verdict")} <Icon name="arrow" />
          </a>
          <p className="small">{t("trace.exhibits_filling")}</p>
        </section>
      )}

      {done && fullyShown && (
        <section className="trace-end">
          {failed ? (
            <>
              <h2 className="h-sec">{t(finalStatus === "interrupted" ? "trace.interrupted" : "trace.failed")}</h2>
              {lastError && <p className="small">{titleOf(lastError)}</p>}
              <p>{t("trace.failed_help")}</p>
              <div className="btn-row">
                <button className="btn btn-primary btn-big" onClick={rerun} disabled={restarting}>
                  <Icon name="retry" /> {t("trace.run_again")}
                </button>
                <a className="btn btn-big" {...linkProps(`/case/${encodeURIComponent(caseId)}`)}>{t("trace.see_partial")}</a>
              </div>
            </>
          ) : (
            <a className="btn btn-primary btn-big btn-wide" {...linkProps(`/case/${encodeURIComponent(caseId)}`)}>
              {t(hasVerdict ? "trace.read_verdict" : "trace.read_record")} <Icon name="arrow" />
            </a>
          )}
        </section>
      )}

      {running && (
        <aside className="activity" aria-live="off">
          <div className="activity-now">
            <span className="spinner" aria-hidden="true" />
            <span className="activity-title">{nowTitle}</span>
          </div>
          <div className="activity-meta">
            <span className="mono">{clock(elapsed)}</span>
            {conn === "retrying" ? (
              <button className="linkish small" onClick={reconnect}>{t("trace.reconnecting", { n: tries })}</button>
            ) : conn === "connecting" ? (
              <span className="small">{t("trace.connecting")}</span>
            ) : quiet > 5 ? (
              <span className="small">{t("trace.on_step")} <span className="mono">{clock(quiet)}</span></span>
            ) : null}
          </div>
          {quiet > 60 && <p className="small activity-note">{t("trace.slow")}</p>}
        </aside>
      )}
    </div>
  );
}
