import { useCallback, useEffect, useMemo, useState } from "react";
import { useI18n, keyLabel } from "../i18n";
import { readSse } from "../sse";
import { Icon } from "../components/Icon";
import { Stamp } from "../components/Stamp";
import { useNow, usePrefersReducedMotion } from "../components/Bits";
import { clock, dayLabel } from "../format";

interface Row { key: string; stored: number | null; recomputed: number | null; state: "match" | "mismatch" | "unavailable" }
type Status = "verified" | "mismatch" | "unknown_hash" | "tampered" | "upstream_unavailable" | "nothing_to_recompute";
interface Result { status: Status; ok: boolean; matched?: number; total?: number; message_hi?: string; message_en?: string; recomputed_hash?: string; error?: string }
interface Start {
  hash_verified?: boolean; engine_version?: string; event_date?: string; optical_pre_id?: string | null; optical_post_id?: string | null;
  sar_pre_id?: string | null; sar_post_id?: string | null; history_scene_ids?: string[]; seed?: number; n_numbers?: number; tolerance?: number;
  numbers?: Record<string, number | null>;
}

type Conn = "connecting" | "open" | "done" | "failed";

function toRow(m: Record<string, unknown>): Row {
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  return {
    key: String(m.field),
    stored: num(m.stored),
    recomputed: num(m.recomputed),
    state: m.missing ? "unavailable" : m.match === true ? "match" : "mismatch",
  };
}

export default function Verify({ hash }: { hash: string }) {
  const { t, lang } = useI18n();
  const [arrived, setArrived] = useState<Row[]>([]);
  const [revealed, setRevealed] = useState(0);
  const [conn, setConn] = useState<Conn>("connecting");
  const [start, setStart] = useState<Start | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [run, setRun] = useState(0);
  const [startedAt, setStartedAt] = useState(() => Date.now());
  const [restartNote, setRestartNote] = useState(false);
  const reduced = usePrefersReducedMotion();
  const valid = /^[a-fA-F0-9]{16,128}$/.test(hash);

  useEffect(() => {
    if (!valid) return;
    const ctl = new AbortController();
    setArrived([]);
    setRevealed(0);
    setStart(null);
    setResult(null);
    setConn("connecting");
    setStartedAt(Date.now());
    let sawResult = false;
    (async () => {
      try {
        await readSse(
          `/api/verify/${encodeURIComponent(hash)}`,
          (m) => {
            let msg: Record<string, unknown>;
            try { msg = JSON.parse(m.data) as Record<string, unknown>; } catch { return; }
            if (msg.type === "start") setStart(msg as Start);
            else if (msg.type === "number") setArrived((r) => [...r, toRow(msg)]);
            else if (msg.type === "result") { sawResult = true; setResult(msg as unknown as Result); }
          },
          ctl.signal,
          () => setConn("open"),
        );
        if (!ctl.signal.aborted) setConn(sawResult ? "done" : "failed");
      } catch {
        if (!ctl.signal.aborted) setConn("failed");
      }
    })();
    return () => ctl.abort();
  }, [hash, run, valid]);

  // Numbers arrive in a burst when the recomputation ends. They are revealed one at a time so a
  // person can follow them; every value shown is the one the server sent.
  useEffect(() => {
    if (revealed >= arrived.length) return;
    if (reduced) { setRevealed(arrived.length); return; }
    const id = window.setTimeout(() => setRevealed((n) => n + 1), arrived.length > 60 ? 50 : 110);
    return () => window.clearTimeout(id);
  }, [revealed, arrived.length, reduced]);

  const retry = useCallback(() => {
    setRestartNote(true);
    setRun((r) => r + 1);
  }, []);

  const rows = arrived.slice(0, revealed);
  const counts = useMemo(() => {
    const c = { match: 0, mismatch: 0, unavailable: 0 };
    for (const r of rows) c[r.state] += 1;
    return c;
  }, [rows]);

  const total = start?.numbers ? Object.keys(start.numbers).length : start?.n_numbers ?? result?.total ?? arrived.length;
  const pending = Math.max(0, total - rows.length);
  const running = conn === "connecting" || conn === "open";
  const now = useNow(1000, running);
  const elapsed = (now - startedAt) / 1000;
  const settled = !running && revealed >= arrived.length;
  const status = result?.status;
  const refused = status === "unknown_hash" || status === "tampered" || status === "upstream_unavailable";
  const stored = start?.numbers ? Object.entries(start.numbers) : [];
  const pendingStored = stored.filter(([k]) => !rows.some((r) => r.key === k));
  const message = result ? (lang === "hi" ? result.message_hi : result.message_en) ?? result.message_en ?? null : null;

  const nothing = status === "nothing_to_recompute";
  const lineKind: "ok" | "bad" | "partial" | null = !settled || !result || refused
    ? null
    : nothing
      ? "partial"
      : counts.mismatch > 0
      ? "bad"
      : counts.unavailable > 0
        ? "partial"
        : "ok";

  const groups = useMemo(() => hash.match(/.{1,8}/g) ?? [hash], [hash]);

  return (
    <div className="page verify">
      <p className="eyebrow">{t("verify.eyebrow")}</p>
      <h1 className="display verify-title">{t("verify.title")}</h1>
      <p className="lede">{t("verify.lede")}</p>

      <div className="hash-block">
        <span className="hash-cap">{t("verify.hash")}</span>
        <code className="hash mono">{groups.map((g, i) => <span key={i}>{g}</span>)}</code>
      </div>

      {!valid && <p className="notice" role="alert">{t("verify.bad_hash")}</p>}

      {valid && (
        <>
          {start?.hash_verified && (
            <p className="hash-ok"><Icon name="check" size={20} stroke={2.2} /> {t("verify.hash_ok")}</p>
          )}

          {status === "unknown_hash" && <p className="notice notice-block" role="alert">{t("verify.not_found")}</p>}
          {status === "tampered" && (
            <div className="verify-line verify-bad" role="alert">
              <Stamp size="lg" tone="soil" className="stamp-thump">{t("verify.stamp_tampered")}</Stamp>
              <p>{message}</p>
              {result?.recomputed_hash && <code className="mono small break">{result.recomputed_hash}</code>}
            </div>
          )}
          {status === "upstream_unavailable" && (
            <div className="verify-line verify-partial" role="status">
              <Stamp size="lg" tone="muted">{t("verify.stamp_incomplete")}</Stamp>
              <p>{message}</p>
              <button className="btn" onClick={retry}><Icon name="retry" /> {t("verify.again")}</button>
            </div>
          )}

          {status !== "unknown_hash" && status !== "tampered" && (
            <>
              <div className="tally" aria-live="polite">
                <div><b className="mono">{counts.match}</b><span>{t("verify.matched")}</span></div>
                <div><b className="mono">{counts.mismatch}</b><span>{t("verify.mismatched")}</span></div>
                <div><b className="mono">{pending}</b><span>{t("verify.waiting")}</span></div>
                {counts.unavailable > 0 && <div><b className="mono">{counts.unavailable}</b><span>{t("verify.unavailable")}</span></div>}
                <div className="tally-clock"><b className="mono">{clock(elapsed)}</b><span>{running ? t("verify.elapsed") : t("verify.took")}</span></div>
              </div>
              {total > 0 && (
                <div className="meter" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={rows.length}>
                  <span style={{ width: `${(rows.length / total) * 100}%` }} />
                </div>
              )}
            </>
          )}

          {running && arrived.length === 0 && (
            <p className="loading" role="status">
              <span className="spinner" aria-hidden="true" /> {conn === "connecting" ? t("verify.connecting") : t("verify.working", { n: total })}
            </p>
          )}
          {running && arrived.length === 0 && elapsed > 20 && <p className="small faint">{t("verify.slow")}</p>}

          {(rows.length > 0 || pendingStored.length > 0) && (
            <div className="table-scroll">
              <table className="verify-table">
                <thead>
                  <tr>
                    <th scope="col">{t("verify.col_number")}</th>
                    <th scope="col" className="num">{t("verify.col_stored")}</th>
                    <th scope="col" className="num">{t("verify.col_recomputed")}</th>
                    <th scope="col">{t("verify.col_result")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.key} className={`vrow vrow-${r.state} ${reduced ? "" : "fresh"}`}>
                      <th scope="row">
                        {keyLabel(r.key, lang) !== r.key.replace(/_/g, " ") && <span className="vname">{keyLabel(r.key, lang)}</span>}
                        <span className="mono vkey">{r.key}</span>
                      </th>
                      <td className="mono num" data-label={t("verify.col_stored")}>{r.stored ?? "—"}</td>
                      <td className="mono num" data-label={t("verify.col_recomputed")}>{r.recomputed ?? "—"}</td>
                      <td className="vresult">
                        {r.state === "match" && <span className="v-ok"><Icon name="check" size={18} stroke={2.2} /> {t("verify.ok")}</span>}
                        {r.state === "mismatch" && <span className="v-bad"><Icon name="cross" size={18} stroke={2.2} /> {t("verify.bad")}</span>}
                        {r.state === "unavailable" && <span className="faint">{t("verify.unavailable")}</span>}
                      </td>
                    </tr>
                  ))}
                  {pendingStored.map(([k, v]) => (
                    <tr key={k} className="vrow vrow-waiting">
                      <th scope="row">
                        {keyLabel(k, lang) !== k.replace(/_/g, " ") && <span className="vname">{keyLabel(k, lang)}</span>}
                        <span className="mono vkey">{k}</span>
                      </th>
                      <td className="mono num" data-label={t("verify.col_stored")}>{v ?? "—"}</td>
                      <td className="num" data-label={t("verify.col_recomputed")}><span className="spinner" aria-label={t("verify.waiting")} /></td>
                      <td />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {lineKind && (
            <div className={`verify-line verify-${lineKind}`} role="status">
              <Stamp size="lg" tone={lineKind === "bad" ? "soil" : lineKind === "ok" ? "ink" : "muted"} className="stamp-thump">
                {t(nothing ? "verify.stamp_nothing" : lineKind === "ok" ? "verify.stamp_ok" : lineKind === "bad" ? "verify.stamp_bad" : "verify.stamp_partial")}
              </Stamp>
              <p>
                {lineKind === "ok" && t("verify.line_ok", { n: counts.match })}
                {lineKind === "bad" && t("verify.line_bad", { k: counts.mismatch, n: rows.length })}
                {lineKind === "partial" && (nothing ? message : t("verify.line_partial", { k: counts.match, n: rows.length }))}
              </p>
              {start?.tolerance !== undefined && lineKind !== "ok" && !nothing && <p className="small">{t("verify.tolerance", { t: start.tolerance })}</p>}
              {start?.tolerance !== undefined && lineKind === "ok" && <p className="small verify-sub">{t("verify.tolerance", { t: start.tolerance })}</p>}
            </div>
          )}

          {conn === "failed" && (
            <div className="notice notice-block" role="alert">
              <p>{t(arrived.length ? "verify.dropped" : "verify.failed")}</p>
              <button className="btn" onClick={retry}><Icon name="retry" /> {t("verify.again")}</button>
            </div>
          )}
          {restartNote && running && <p className="small faint">{t("verify.restarted")}</p>}

          {start && (
            <details className="fold">
              <summary>{t("verify.what_used")}</summary>
              <table className="ledger">
                <tbody>
                  <tr><th>{t("verify.m_engine")}</th><td className="mono">{start.engine_version ?? "—"}</td></tr>
                  <tr><th>{t("verify.m_event")}</th><td className="mono">{dayLabel(start.event_date, lang)}</td></tr>
                  <tr><th>{t("verify.m_seed")}</th><td className="mono">{start.seed ?? "—"}</td></tr>
                  <tr><th>{t("verify.m_opt")}</th><td className="mono small break">{start.optical_pre_id ?? "—"}<br />{start.optical_post_id ?? "—"}</td></tr>
                  <tr><th>{t("verify.m_sar")}</th><td className="mono small break">{start.sar_pre_id ?? "—"}<br />{start.sar_post_id ?? "—"}</td></tr>
                  {(start.history_scene_ids?.length ?? 0) > 0 && <tr><th>{t("verify.m_hist")}</th><td className="mono small break">{start.history_scene_ids!.join(" ")}</td></tr>}
                </tbody>
              </table>
            </details>
          )}

          <section className="how-verify">
            <h2 className="h-mini">{t("verify.how_t")}</h2>
            <p className="small">{t("verify.how_b")}</p>
          </section>
        </>
      )}
    </div>
  );
}
