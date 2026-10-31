import { useCallback, useEffect, useMemo, useState } from "react";
import { useI18n, keyLabel, type Key } from "../i18n";
import { readSse } from "../sse";
import { Icon } from "../components/Icon";
import { Stamp } from "../components/Stamp";
import { CopyButton, useNow, usePrefersReducedMotion } from "../components/Bits";
import { clock, dateTimeLabel, dayLabel } from "../format";

interface Row { key: string; label: string; stored: number | null; recomputed: number | null; state: "match" | "mismatch" | "unavailable" }
type Status = "verified" | "mismatch" | "partial" | "field_verified" | "unknown_hash" | "tampered" | "upstream_unavailable" | "archive_mismatch" | "nothing_to_recompute";
interface Cachable { cached?: boolean; checked_at?: string | null; rerun?: string }
interface Result extends Cachable {
  status: Status; ok: boolean; matched?: number; total?: number; checked?: number; unchecked?: string[]; errors?: Record<string, string> | string[];
  field_verified?: boolean; message_hi?: string; message_en?: string; recomputed_hash?: string; error?: string; elapsed_s?: number;
}
interface Start extends Cachable {
  hash_verified?: boolean; engine_version?: string; event_date?: string; optical_pre_id?: string | null; optical_post_id?: string | null;
  sar_pre_id?: string | null; sar_post_id?: string | null; history_scene_ids?: string[]; seed?: number; n_numbers?: number; tolerance?: number;
  numbers?: Record<string, number | null>; superseded?: boolean; started_at?: string;
  last_full_check?: { status: string; checked: number | null; total: number | null; finished_at: string | null } | null;
}
interface Stage { status: "field_verified" | "field_mismatch" | "field_failed"; matched: number; total: number; remaining: number }
interface GroupState { name: string; state: "running" | "done" | "failed"; n?: number; budget?: number; elapsed?: number; startedAt?: number; reason?: string; fields?: string[] }
interface StreamEvent extends Record<string, unknown> { type: string; seq?: number; run_id?: string }

type Conn = "connecting" | "open" | "retrying" | "done" | "gone";

/** The order the server works through. Groups a record doesn't need are dropped once the check ends. */
const GROUP_ORDER = ["field_pre", "field_post", "field_extra", "sar_field", "history", "ring", "far_twin", "radar", "village", "scale_fade"];

/** Sealed keys hold an internal name that readers should never see. */
const displayKey = (k: string) => k.replace("village.lottery.", "village.ten_field_draw.");

function toRow(m: Record<string, unknown>): Row {
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  return {
    key: String(m.field),
    label: typeof m.label === "string" ? m.label : displayKey(String(m.field)),
    stored: num(m.stored),
    recomputed: num(m.recomputed),
    state: m.missing ? "unavailable" : m.match === true ? "match" : "mismatch",
  };
}

const snapshotKey = (hash: string) => `fs.verify.${hash}`;

function loadSnapshot(hash: string): StreamEvent[] {
  try {
    const raw = localStorage.getItem(snapshotKey(hash));
    return raw ? (JSON.parse(raw) as StreamEvent[]) : [];
  } catch {
    return [];
  }
}

export default function Verify({ hash }: { hash: string }) {
  const { t, lang } = useI18n();
  const [arrived, setArrived] = useState<Row[]>([]);
  const [revealed, setRevealed] = useState(0);
  const [conn, setConn] = useState<Conn>("connecting");
  const [start, setStart] = useState<Start | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [stage, setStage] = useState<Stage | null>(null);
  const [groupList, setGroupList] = useState<GroupState[]>([]);
  const [sourceSeen, setSourceSeen] = useState(false);
  const [note, setNote] = useState<{ message_hi?: string; message_en?: string } | null>(null);
  const [nonce, setNonce] = useState<{ n: number; rerun: boolean }>({ n: 0, rerun: false });
  const [firstSeen, setFirstSeen] = useState(() => Date.now());
  const reduced = usePrefersReducedMotion();
  const valid = /^[a-fA-F0-9]{16,128}$/.test(hash);

  // Pure, so a restored snapshot and a live event take the same path.
  const apply = useCallback((msg: StreamEvent) => {
    switch (msg.type) {
      case "start": setStart(msg as Start); break;
      case "note": if (msg.message_en) setNote(msg as { message_hi?: string; message_en?: string }); else setSourceSeen(true); break;
      case "number": setArrived((r) => (r.some((x) => x.key === String(msg.field)) ? r : [...r, toRow(msg)])); break;
      case "stage_result": setStage(msg as unknown as Stage); break;
      case "result": setResult(msg as unknown as Result); break;
      case "group_started":
        setSourceSeen(true);
        setGroupList((g) => [...g.filter((x) => x.name !== msg.group), { name: String(msg.group), state: "running", n: msg.n_numbers as number, budget: msg.budget_s as number, startedAt: (msg.seen_at as number) ?? Date.now() }]);
        break;
      case "group_done":
        setGroupList((g) => g.map((x) => (x.name === msg.group ? { ...x, state: "done", elapsed: msg.elapsed_s as number, n: msg.n_numbers as number } : x)));
        break;
      case "group_failed":
        setGroupList((g) => {
          const failed: GroupState = { name: String(msg.group), state: "failed", reason: String(msg.reason ?? ""), fields: (msg.fields as string[]) ?? [], n: msg.n_numbers as number };
          return g.some((x) => x.name === msg.group) ? g.map((x) => (x.name === msg.group ? failed : x)) : [...g, failed];
        });
        break;
      default: break;
    }
  }, []);

  useEffect(() => {
    if (!valid) return;
    const ctl = new AbortController();
    setArrived([]);
    setRevealed(0);
    setStart(null);
    setResult(null);
    setStage(null);
    setGroupList([]);
    setNote(null);
    setSourceSeen(false);
    setConn("connecting");
    setFirstSeen(Date.now());

    // Coming back to this page picks the same check up where it left off. The job runs on the
    // server regardless, so nothing is lost by leaving, and returning never starts a new download.
    let log: StreamEvent[] = nonce.rerun ? [] : loadSnapshot(hash);
    if (nonce.rerun) {
      try { localStorage.removeItem(snapshotKey(hash)); } catch { /* a convenience only */ }
    }
    log.forEach(apply);
    let lastSeq = log.length ? log[log.length - 1].seq ?? 0 : 0;
    let runId = log.length ? log[log.length - 1].run_id : undefined;
    let finished = log.some((e) => e.type === "result");
    let askRerun = nonce.rerun;
    let tries = 0;
    let wake: (() => void) | null = null;
    const onOnline = () => wake?.();
    window.addEventListener("online", onOnline);

    (async () => {
      if (finished) {
        setConn("done");
        const probe = new AbortController();
        const stop = () => probe.abort();
        ctl.signal.addEventListener("abort", stop, { once: true });
        const timer = window.setTimeout(stop, 4000);
        try {
          await readSse(`/api/verify/${encodeURIComponent(hash)}?after=${lastSeq}`, (m) => {
            let msg: StreamEvent;
            try { msg = JSON.parse(m.data) as StreamEvent; } catch { return; }
            if (msg.run_id && msg.run_id !== runId) {
              try { localStorage.removeItem(snapshotKey(hash)); } catch { /* a convenience only */ }
              setNonce((x) => ({ n: x.n + 1, rerun: false }));
              probe.abort();
            }
          }, probe.signal);
        } catch { /* the remembered result still stands */ }
        window.clearTimeout(timer);
        return;
      }
      for (;;) {
        if (ctl.signal.aborted) return;
        setConn(tries === 0 ? "connecting" : "retrying");
        try {
          const params = [lastSeq > 0 ? `after=${lastSeq}` : "", askRerun ? "rerun=1" : ""].filter(Boolean).join("&");
          await readSse(
            `/api/verify/${encodeURIComponent(hash)}${params ? `?${params}` : ""}`,
            (m) => {
              let msg: StreamEvent;
              try { msg = JSON.parse(m.data) as StreamEvent; } catch { return; }
              if (typeof msg.seq === "number") {
                if (runId && msg.run_id && msg.run_id !== runId) {
                  // The server has moved to a newer check, so read that one from its beginning.
                  log = [];
                  lastSeq = 0;
                  runId = undefined;
                  setArrived([]);
                  setRevealed(0);
                  setStage(null);
                  setGroupList([]);
                  setResult(null);
                  try { localStorage.removeItem(snapshotKey(hash)); } catch { /* a convenience only */ }
                  throw new Error("newer check");
                }
                if (msg.seq <= lastSeq) return;
                lastSeq = msg.seq;
                runId = msg.run_id ?? runId;
              }
              tries = 0;
              if (msg.type !== "progress") {
                msg.seen_at = Date.now();
                log = [...log, msg];
                try { localStorage.setItem(snapshotKey(hash), JSON.stringify(log)); } catch { /* full or private */ }
              }
              if (msg.type === "result") {
                finished = true;
                // The server keeps a full check, so only a check that ended short needs remembering:
                // reopening one with no history would quietly start a new download.
                if (msg.status !== "field_verified" && msg.status !== "partial") {
                  try { localStorage.removeItem(snapshotKey(hash)); } catch { /* a convenience only */ }
                }
              }
              apply(msg);
            },
            ctl.signal,
            () => { setConn("open"); askRerun = false; },
          );
          if (finished) { setConn("done"); return; }
        } catch (e) {
          if (ctl.signal.aborted) return;
          if ((e as { status?: number }).status === 404) { setConn("gone"); return; }
        }
        tries += 1;
        setConn("retrying");
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
  }, [hash, nonce, valid, apply]);

  // Numbers arrive in a burst when the recomputation ends. They are revealed one at a time so a
  // person can follow them; every value shown is the one the server sent.
  useEffect(() => {
    if (revealed >= arrived.length) return;
    // A stored check appears at once. Ticking it out would look like a calculation happening now.
    if (reduced || start?.cached) { setRevealed(arrived.length); return; }
    const id = window.setTimeout(() => setRevealed((n) => n + 1), arrived.length > 60 ? 50 : 110);
    return () => window.clearTimeout(id);
  }, [revealed, arrived.length, reduced, start?.cached]);

  const again = useCallback(() => setNonce((x) => ({ n: x.n + 1, rerun: true })), []);

  const rows = arrived.slice(0, revealed);
  const counts = useMemo(() => {
    const c = { match: 0, mismatch: 0, unavailable: 0 };
    for (const r of rows) c[r.state] += 1;
    return c;
  }, [rows]);

  const total = result?.total ?? (start?.numbers ? Object.keys(start.numbers).length : start?.n_numbers ?? arrived.length);
  const running = conn === "connecting" || conn === "open" || conn === "retrying";
  const pending = running ? Math.max(0, total - rows.length) : 0;
  const now = useNow(1000, running);
  const startedMs = start?.started_at ? new Date(start.started_at).getTime() : firstSeen;
  const elapsed = (now - startedMs) / 1000;
  const settled = !running && revealed >= arrived.length;
  const status = result?.status;
  const cached = !!(start?.cached || result?.cached);
  const checkedAt = result?.checked_at ?? start?.checked_at ?? null;
  const refused = status === "unknown_hash" || status === "tampered" || status === "upstream_unavailable" || status === "archive_mismatch";
  const stored = start?.numbers ? Object.entries(start.numbers) : [];
  const failedKeys = useMemo(() => new Set(groupList.flatMap((g) => g.fields ?? [])), [groupList]);
  const pendingStored = stored.filter(([k]) => !rows.some((r) => r.key === k));
  const message = result ? (lang === "hi" ? result.message_hi : result.message_en) ?? result.message_en ?? null : null;
  const unchecked = result?.unchecked?.length ?? Math.max(0, total - (result?.checked ?? rows.length));

  const nothing = status === "nothing_to_recompute";
  // "ok" comes only from the server's `verified`. Everything short of that says how far it got.
  const lineKind: "ok" | "bad" | "field" | "partial" | null = !settled || !result || refused
    ? null
    : status === "verified"
      ? "ok"
      : status === "mismatch" || counts.mismatch > 0
        ? "bad"
        : status === "field_verified"
          ? "field"
          : "partial";

  const shownGroups = useMemo(() => {
    const seen = new Map(groupList.map((g) => [g.name, g]));
    const known = GROUP_ORDER.filter((n) => seen.has(n) || (running && !cached));
    const extra = groupList.map((g) => g.name).filter((n) => !GROUP_ORDER.includes(n));
    return [...known, ...extra].map((n) => seen.get(n) ?? ({ name: n, state: "waiting" } as unknown as GroupState));
  }, [groupList, running, cached]);
  const activeGroup = groupList.find((g) => g.state === "running");

  const groups = useMemo(() => hash.match(/.{1,8}/g) ?? [hash], [hash]);

  return (
    <div className="page verify">
      <p className="eyebrow">{t("verify.eyebrow")}</p>
      <h1 className="display verify-title">{t(cached ? "verify.title_stored" : running ? "verify.title" : "verify.title_done")}</h1>
      <p className="lede">{t(cached ? "verify.lede_stored" : "verify.lede")}</p>

      <div className="hash-block">
        <span className="hash-cap">{t("verify.hash")}</span>
        <code className="hash mono">{groups.map((g, i) => <span key={i}>{g}</span>)}</code>
      </div>

      {!valid && <p className="notice" role="alert">{t("verify.bad_hash")}</p>}

      {valid && (
        <>
          {start?.superseded && <p className="notice small">{t("verify.superseded")}</p>}
          {start?.hash_verified && (
            <p className="hash-ok"><Icon name="check" size={20} stroke={2.2} /> {t("verify.hash_ok")}</p>
          )}

          {cached && (
            <div className="stored-check" role="status">
              <p><strong>{t("verify.stored_label")}</strong>{checkedAt && <> <span className="mono">{dateTimeLabel(checkedAt, lang)}</span></>}</p>
              <p className="small">{t("verify.stored_body")}</p>
              <button className="btn" onClick={again}><Icon name="retry" /> {t("verify.check_again")}</button>
            </div>
          )}
          {!cached && start?.last_full_check?.finished_at && (
            <p className="small faint">{t("verify.last_full")} <span className="mono">{dateTimeLabel(start.last_full_check.finished_at, lang)}</span></p>
          )}

          {stage && !result && (
            <div className={`stage stage-${stage.status}`} role="status">
              <p className="stage-big">
                {stage.status === "field_failed"
                  ? t("verify.stage_failed", { m: stage.matched, n: stage.total })
                  : stage.status === "field_mismatch"
                    ? t("verify.stage_mismatch", { m: stage.matched, n: stage.total })
                    : t("verify.stage_ok", { m: stage.matched, n: stage.total })}
              </p>
              <p className="stage-rest"><span className="spinner" aria-hidden="true" /> {t("verify.stage_rest", { r: stage.remaining })}</p>
              <p className="small">{t("verify.stage_not_full")}</p>
            </div>
          )}

          {lineKind && (
            <div className={`verify-line verify-${lineKind}`} role="status">
              <Stamp size="lg" tone={lineKind === "bad" ? "soil" : lineKind === "ok" ? "ink" : "muted"} className="stamp-thump">
                {nothing
                  ? t("verify.stamp_nothing")
                  : lineKind === "ok"
                    ? t("verify.stamp_ok")
                    : lineKind === "bad"
                      ? t("verify.stamp_bad")
                      : t("verify.stamp_checked", { k: result?.checked ?? rows.length, n: result?.total ?? total })}
              </Stamp>
              <p>
                {lineKind === "ok" && t("verify.line_ok", { n: result?.matched ?? counts.match })}
                {lineKind === "bad" && t("verify.line_bad", { k: counts.mismatch, n: rows.length })}
                {lineKind === "field" && t("verify.line_field", { f: stage?.total ?? 0, k: result?.checked ?? rows.length, n: result?.total ?? total, u: unchecked })}
                {lineKind === "partial" && (nothing ? message : t("verify.line_checked", { k: result?.checked ?? rows.length, n: result?.total ?? total, m: result?.matched ?? counts.match }))}
              </p>
              {lineKind === "partial" && !nothing && message && <p className="small">{message}</p>}
              {start?.tolerance !== undefined && !nothing && <p className={lineKind === "ok" ? "small verify-sub" : "small"}>{t("verify.tolerance", { t: start.tolerance })}</p>}
              {!cached && (lineKind === "field" || (lineKind === "partial" && !nothing)) && <button className="btn" onClick={again}><Icon name="retry" /> {t("verify.check_rest")}</button>}
            </div>
          )}

          {running && !cached && start && (
            <div className="leave-safe" role="note">
              <p><strong>{t("verify.leave_t")}</strong> {t("verify.leave_b")}</p>
              <CopyButton text={location.href} label={t("verify.leave_copy")} />
            </div>
          )}
          {conn === "retrying" && <p className="small" role="status">{t("verify.reconnecting")}</p>}

          {status === "unknown_hash" && <p className="notice notice-block" role="alert">{t("verify.not_found")}</p>}
          {status === "tampered" && (
            <div className="verify-line verify-bad" role="alert">
              <Stamp size="lg" tone="soil" className="stamp-thump">{t("verify.stamp_tampered")}</Stamp>
              <p>{message}</p>
              {result?.recomputed_hash && <code className="mono small break">{result.recomputed_hash}</code>}
            </div>
          )}
          {(status === "upstream_unavailable" || status === "archive_mismatch") && (
            <div className="verify-line verify-partial" role="status">
              <Stamp size="lg" tone="muted">{t("verify.stamp_incomplete")}</Stamp>
              <p>{message}</p>
              <button className="btn" onClick={again}><Icon name="retry" /> {t("verify.again")}</button>
            </div>
          )}

          {status !== "unknown_hash" && status !== "tampered" && (
            <>
              <div className="tally" aria-live="polite">
                <div><b className="mono">{counts.match}</b><span>{t("verify.matched")}</span></div>
                <div><b className="mono">{counts.mismatch}</b><span>{t("verify.mismatched")}</span></div>
                <div><b className="mono">{pending}</b><span>{t("verify.waiting")}</span></div>
                {counts.unavailable > 0 && <div><b className="mono">{counts.unavailable}</b><span>{t("verify.unavailable")}</span></div>}
                {running && !cached && <div className="tally-clock"><b className="mono">{clock(elapsed)}</b><span>{t("verify.elapsed")}</span></div>}
                {!running && !cached && typeof result?.elapsed_s === "number" && <div className="tally-clock"><b className="mono">{clock(result.elapsed_s)}</b><span>{t("verify.took")}</span></div>}
              </div>
              {total > 0 && (
                <div className="meter" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={rows.length}>
                  <span style={{ width: `${(rows.length / total) * 100}%` }} />
                </div>
              )}
            </>
          )}

          {running && !start && (
            <p className="loading" role="status"><span className="spinner" aria-hidden="true" /> {t("verify.connecting")}</p>
          )}
          {shownGroups.length > 0 && (
            <ol className="vgroups" aria-label={t("verify.groups_label")}>
              {shownGroups.map((g) => (
                <li key={g.name} className={`vgroup vgroup-${g.state}`}>
                  <span className="vgroup-mark" aria-hidden="true">
                    {g.state === "done" ? <Icon name="check" size={16} stroke={2.4} /> : g.state === "running" ? <span className="spinner" /> : g.state === "failed" ? <Icon name="cross" size={16} stroke={2.2} /> : null}
                  </span>
                  <span className="vgroup-name">{t(`verify.group_${g.name}` as Key)}</span>
                  <span className="vgroup-meta mono">
                    {g.state === "done" && typeof g.elapsed === "number" && clock(g.elapsed)}
                    {g.state === "running" && !!g.startedAt && clock((now - g.startedAt) / 1000)}
                    {g.state === "failed" && t("verify.group_failed")}
                  </span>
                </li>
              ))}
            </ol>
          )}
          {activeGroup?.name === "far_twin" && <p className="small">{t("verify.far_twin_slow")}</p>}
          {sourceSeen && !cached && <p className="small verify-source">{t("verify.source")}</p>}
          {note && <p className="notice small">{(lang === "hi" ? note.message_hi : note.message_en) ?? note.message_en}</p>}

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
                        <span className="mono vkey">{r.label}</span>
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
                        <span className="mono vkey">{displayKey(k)}</span>
                      </th>
                      <td className="mono num" data-label={t("verify.col_stored")}>{v ?? "—"}</td>
                      <td className="num" data-label={t("verify.col_recomputed")}>{running && !failedKeys.has(k) ? <span className="spinner" aria-label={t("verify.waiting")} /> : "—"}</td>
                      <td className="vresult">{(!running || failedKeys.has(k)) && <span className="faint">{t("verify.unavailable")}</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {conn === "gone" && (
            <div className="notice notice-block" role="alert">
              <p>{t("verify.failed")}</p>
              <button className="btn" onClick={again}><Icon name="retry" /> {t("verify.again")}</button>
            </div>
          )}

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
