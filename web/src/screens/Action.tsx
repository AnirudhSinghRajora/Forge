import { useCallback, useEffect, useMemo, useState } from "react";
import { useI18n, keyLabel, translateRubric, type Key } from "../i18n";
import { ApiError, askPolicy, getCase, pdfUrl, postSubmission, type CaseEnvelope, type CaseRecord, type IntimationDraft } from "../api";
import { Icon } from "../components/Icon";
import { Stamp } from "../components/Stamp";
import { Countdown } from "../components/Countdown";
import { CopyButton, ErrorNote, Loading, Missing } from "../components/Bits";
import { linkProps } from "../router";
import { dateTimeLabel, localInputValue } from "../format";
import type { AskResponse, Evidence, PolicyClause } from "../types";

const CHANNELS: { id: string; key: Key }[] = [
  { id: "helpline_14447", key: "channel.helpline" },
  { id: "krph_portal", key: "channel.portal" },
  { id: "crop_insurance_app", key: "channel.app" },
  { id: "insurer", key: "channel.insurer" },
  { id: "bank", key: "channel.bank" },
  { id: "agri_officer", key: "channel.officer" },
  { id: "other", key: "channel.other" },
];

/** The clause itself is an English legal text, and is said to be one rather than left unmarked. */
function Clause({ c }: { c: PolicyClause }) {
  const { t, lang } = useI18n();
  return (
    <blockquote className="clause">
      {lang !== "en" && <p className="small faint clause-lang">{t("clause.in_english")}</p>}
      <p lang="en">{c.text}</p>
      <footer>
        <span className="mono">{t("clause.label")} {c.clause_id}</span> · <span lang="en">{c.doc}</span>
        {c.page ? <> · {t("clause.page")} <span className="mono">{c.page}</span></> : null}
        {c.url && <> · <a href={c.url} target="_blank" rel="noreferrer">{t("clause.open")}</a></>}
      </footer>
    </blockquote>
  );
}

function ClaimPathBlock({ ev, caseRecord }: { ev: Evidence | null; caseRecord: CaseRecord }) {
  const { t, lang } = useI18n();
  const cp = ev?.claim_path ?? null;
  const clauses = (cp?.clause_ids ?? []).map((id) => ev?.policy.find((c) => c.clause_id === id) ?? null);
  // The server keeps this text in every language, so switching language here needs no new run.
  const text = ev?.claim_path_text?.[lang];
  const reasons = text?.reasons ?? cp?.reasons ?? [];
  const nextSteps = text?.next_steps ?? cp?.next_steps ?? [];
  const evidenceUse = text?.evidence_use ?? cp?.evidence_use ?? null;
  return (
    <section className="claim-path" aria-labelledby="path-t">
      <p className="eyebrow">{t("path.eyebrow")}</p>
      {!cp ? (
        <>
          <h2 id="path-t" className="path-route">{t("path.none_t")}</h2>
          <Missing what={t("path.missing")} why={t(ev ? "path.missing_run" : "path.missing_noev")} />
        </>
      ) : (
        <>
          <h2 id="path-t" className="path-route">{t(`route.${cp.route}` as Key)}</h2>
          <p className="path-blurb">{t(`route.${cp.route}.blurb` as Key)}</p>
          <dl className="path-facts">
            <div><dt>{t("path.insured")}</dt><dd>{t(`insured.${cp.insured}` as Key)}</dd></div>
            <div><dt>{t("path.stage")}</dt><dd>{t(`stage.${cp.crop_stage}` as Key)}</dd></div>
            <div><dt>{t("path.intimation")}</dt><dd>{t(`intimation.${cp.intimation}` as Key)}</dd></div>
          </dl>
          {(cp.insured === "unknown" || cp.crop_stage === "unknown" || cp.route === "outside_cover") && (
            <p className="small">{t("path.tell_more")} <a {...linkProps(`/case/${encodeURIComponent(caseRecord.id)}/confirm`)}>{t("path.tell_link")}</a></p>
          )}
          <div className="path-grid">
            {reasons.length > 0 && <div><h3 className="h-mini">{t("path.why")}</h3><ul>{reasons.map((r, i) => <li key={i}>{translateRubric(r, lang)}</li>)}</ul></div>}
            {nextSteps.length > 0 && <div><h3 className="h-mini">{t("path.next")}</h3><ol>{nextSteps.map((r, i) => <li key={i}>{translateRubric(r, lang)}</li>)}</ol></div>}
            <div>
              <h3 className="h-mini">{t("path.useful")}</h3>
              {evidenceUse ? <p>{translateRubric(evidenceUse, lang)}</p> : <p className="faint">{t("missing.not_measured")}</p>}
              <p className="small">{t("path.no_must")}</p>
            </div>
            {cp.unknowns.length > 0 && <div><h3 className="h-mini">{t("path.unknown")}</h3><ul>{cp.unknowns.map((r, i) => <li key={i}>{keyLabel(r, lang)}</li>)}</ul></div>}
          </div>
          {cp.clause_ids.length > 0 && (
            <details className="fold" open>
              <summary>{t("path.clauses")} <span className="mono">({cp.clause_ids.length})</span></summary>
              {cp.clause_ids.map((id, i) => clauses[i] ? <Clause key={id} c={clauses[i]!} /> : <p key={id} className="small"><span className="mono">{t("clause.label")} {id}</span> · {t("path.clause_text_missing")}</p>)}
            </details>
          )}
        </>
      )}
    </section>
  );
}

function phoneOf(channels: unknown[] | undefined): string | null {
  for (const c of channels ?? []) {
    const s = typeof c === "string" ? c : JSON.stringify(c);
    const m = s.match(/\b(1\d{4}|\d{10})\b/);
    if (m) return m[1];
  }
  return null;
}

function Channel({ c }: { c: unknown }) {
  const { lang } = useI18n();
  if (typeof c === "string") return <>{c}</>;
  if (!c || typeof c !== "object") return null;
  const o = c as Record<string, unknown>;
  const label = String(o[`label_${lang}`] ?? o.label_en ?? o.label_hi ?? o.kind ?? "");
  const value = typeof o.value === "string" ? o.value : null;
  const url = typeof o.url === "string" ? o.url : null;
  const isPhone = !!value && /^\d{5,12}$/.test(value);
  const href = url ?? (isPhone ? `tel:${value}` : null);
  // The label often already names the number or address; link it once instead of repeating it.
  const shown = value && !label.includes(value) ? value : null;
  return (
    <>
      {href && !shown ? <a href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">{label}</a> : label}
      {shown && <>{" "}{href ? <a className="mono break" href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">{shown}</a> : <span className="mono break">{shown}</span>}</>}
    </>
  );
}

function FiledBlock({ env, onFiled }: { env: CaseEnvelope; onFiled: () => void }) {
  const { t, lang } = useI18n();
  const caseId = env.case.id;
  const filed = (env.actions ?? []).filter((a) => a.type === "submission" && a.payload?.reference_no);
  const [channel, setChannel] = useState("helpline_14447");
  const [ref, setRef] = useState("");
  const [when, setWhen] = useState(() => localInputValue(new Date()));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [tried, setTried] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTried(true);
    if (!ref.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await postSubmission(caseId, { channel, reference_no: ref.trim(), submitted_at: new Date(when).toISOString() });
      onFiled();
      setShowForm(false);
      setRef("");
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  };

  const form = (
    <form className="filing" onSubmit={submit} noValidate>
      <label className="field">
        <span className="field-label">{t("file.channel")}</span>
        <select value={channel} onChange={(e) => setChannel(e.target.value)}>
          {CHANNELS.map((c) => <option key={c.id} value={c.id}>{t(c.key)}</option>)}
        </select>
      </label>
      <label className={`field ${tried && !ref.trim() ? "field-err" : ""}`}>
        <span className="field-label">{t("file.ref")} *</span>
        <input value={ref} maxLength={100} onChange={(e) => setRef(e.target.value)} className="mono" autoComplete="off" aria-required="true" aria-invalid={tried && !ref.trim()} />
      </label>
      {tried && !ref.trim() && <p className="notice small" role="alert">{t("file.ref_required")}</p>}
      <label className="field">
        <span className="field-label">{t("file.when")}</span>
        <input type="datetime-local" value={when} max={localInputValue(new Date())} onChange={(e) => setWhen(e.target.value)} />
      </label>
      {err !== null && <ErrorNote error={err} />}
      <button className="btn btn-primary btn-big btn-wide" type="submit" disabled={busy}>
        <Icon name="check" /> {busy ? t("act.saving") : t("file.save")}
      </button>
    </form>
  );

  if (filed.length === 0) {
    return (
      <>
        <p className="not-filed"><Icon name="doc" size={20} /> {t("file.not_yet")}</p>
        {form}
      </>
    );
  }
  return (
    <div className="filed">
      {filed.map((a, i) => (
        <div key={a.id ?? i} className="filed-row">
          <Stamp size="lg" tone="ink" className="filed-stamp">{t("file.stamp")}</Stamp>
          <dl className="facts">
            <div><dt>{t("file.ref")}</dt><dd className="mono break">{String(a.payload?.reference_no)}</dd></div>
            <div><dt>{t("file.channel")}</dt><dd>{(() => { const c = CHANNELS.find((x) => x.id === a.payload?.channel); return c ? t(c.key) : String(a.payload?.channel ?? "—"); })()}</dd></div>
            <div><dt>{t("file.when")}</dt><dd className="mono">{dateTimeLabel(String(a.payload?.submitted_at ?? ""), lang)}</dd></div>
          </dl>
        </div>
      ))}
      <p className="small">{t("file.self_reported")}</p>
      {!showForm && <button className="linkish" onClick={() => setShowForm(true)}>{t("file.add_another")}</button>}
      {showForm && form}
    </div>
  );
}

function AskBox({ caseId }: { caseId: string }) {
  const { t, lang } = useI18n();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [res, setRes] = useState<AskResponse | null>(null);
  const [asked, setAsked] = useState("");

  const ask = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!q.trim()) return;
    setBusy(true);
    setErr(null);
    setRes(null);
    try {
      setAsked(q.trim());
      setRes(await askPolicy(caseId, q.trim(), lang));
    } catch (x) {
      setErr(x);
    } finally {
      setBusy(false);
    }
  };

  const answer = res?.answer ?? (lang === "hi" ? res?.answer_hi : res?.answer_en) ?? res?.answer_en ?? res?.answer_hi ?? null;
  const notCovered = res && (res.not_covered === true || res.covered === false || !answer);
  const cites = res?.citations ?? [];

  return (
    <section className="block" aria-labelledby="ask-t">
      <h2 id="ask-t" className="h-sec"><Icon name="question" /> {t("ask.title")}</h2>
      <p className="small">{t("ask.lead")}</p>
      <form className="ask" onSubmit={ask}>
        <textarea rows={2} value={q} maxLength={500} onChange={(e) => setQ(e.target.value)} placeholder={t("ask.placeholder")} lang={lang} />
        <button className="btn btn-primary" disabled={busy || !q.trim()} type="submit">{busy ? t("ask.busy") : t("ask.send")}</button>
      </form>
      {err !== null && <ErrorNote error={err} onRetry={() => ask()} />}
      {res && (
        <div className="answer" aria-live="polite">
          <p className="answer-q small faint">{asked}</p>
          {notCovered && !answer ? <p><strong>{t("ask.not_covered")}</strong></p> : <p>{answer}</p>}
          {notCovered && answer && <p className="small faint">{t("ask.not_covered")}</p>}
          {cites.length > 0 && (
            <>
              <h3 className="h-mini">{t("ask.citations")}</h3>
              {cites.map((c, i) =>
                typeof c === "string" ? (
                  <p key={i} className="mono small">{c}</p>
                ) : (
                  <blockquote key={i} className="clause">
                    {c.text && lang !== "en" && <p className="small faint clause-lang">{t("clause.in_english")}</p>}
                    {c.text && <p lang="en">{c.text}</p>}
                    <footer>
                      <span className="mono">{t("clause.label")} {c.clause_id ?? "—"}</span>
                      {c.doc ? ` · ${c.doc}` : ""}{c.page ? ` · ${t("clause.page")} ${c.page}` : ""}
                      {c.url && <> · <a href={c.url} target="_blank" rel="noreferrer">{t("clause.open")}</a></>}
                    </footer>
                  </blockquote>
                ),
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

export default function ActionScreen({ caseId }: { caseId: string }) {
  const { t, lang } = useI18n();
  const [env, setEnv] = useState<CaseEnvelope | null>(null);
  const [err, setErr] = useState<unknown>(null);

  const load = useCallback((signal?: AbortSignal) => {
    getCase(caseId, signal).then((e) => { setEnv(e); setErr(null); }).catch((e) => { if (!signal?.aborted) setErr(e); });
  }, [caseId]);
  useEffect(() => {
    const ctl = new AbortController();
    load(ctl.signal);
    return () => ctl.abort();
  }, [load]);

  const draft = useMemo<IntimationDraft | null>(() => {
    const a = (env?.actions ?? []).filter((x) => x.payload && ("text_hi" in x.payload || "available" in x.payload)).pop();
    return (a?.payload as unknown as IntimationDraft) ?? null;
  }, [env]);

  if (err) {
    const gone = err instanceof ApiError && err.status === 404;
    return <div className="page narrow">{gone ? <p className="notice">{t("case.not_found")}</p> : <ErrorNote error={err} onRetry={() => load()} />}</div>;
  }
  if (!env) return <div className="page narrow"><Loading what={t("loading.case")} /></div>;

  const ev = env.evidence;
  const deadline = ev?.deadlines.find((d) => d.type === "intimation_72h") ?? null;
  const basis = deadline ? ev?.policy.find((c) => c.clause_id === deadline.basis) ?? null : null;
  const countdownApplies = ev?.claim_path?.countdown_applies === true;
  // A passed time limit is not a countdown: it is said plainly on routes where intimation matters.
  const essential = ev?.claim_path?.intimation === "essential";
  const lapsed = deadline?.status === "lapsed" || draft?.deadline_status === "lapsed";
  const lapsedNote = lang === "hi" ? draft?.lapsed_note_hi : lang === "te" ? draft?.lapsed_note_te ?? draft?.lapsed_note_en : draft?.lapsed_note_en;
  const text = draft?.available ? (lang === "te" ? draft.text_te ?? draft.text_en : lang === "hi" ? draft.text_hi : draft.text_en) ?? null : null;
  const partialNote = (lang === "te" ? draft?.partial_allowed_note_te : lang === "hi" ? draft?.partial_allowed_note_hi : draft?.partial_allowed_note_en) ?? null;
  const phone = phoneOf(draft?.channels) ?? "14447";
  const wa = (lang === "te" ? draft?.whatsapp_url_te : lang === "hi" ? draft?.whatsapp_url_hi : draft?.whatsapp_url_en) ?? (text ? `https://wa.me/?text=${encodeURIComponent(text)}` : null);

  const download = () => {
    if (!text) return;
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `fasalsaakshi-intimation-${caseId.slice(0, 8)}-${lang}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page action">
      <p className="eyebrow">{t("action.eyebrow")} · <span className="mono">{caseId.slice(0, 12)}</span></p>
      <h1 className="h-page">{t("action.title")}</h1>

      {countdownApplies && deadline?.status === "open" && (
        <section className="clock-panel clock-panel-open" aria-labelledby="dl-t">
          <h2 id="dl-t" className="clock-cap">{t("deadline.cap_open")}</h2>
          <Countdown dueAt={deadline.due_at} />
          <p className="clock-due">{t("deadline.by")} <span className="mono">{dateTimeLabel(deadline.due_at, lang)}</span></p>
          <p className="small">{t("deadline.if_notified")}</p>
          {draft?.time_assumed && <p className="small">{t("deadline.time_assumed")}</p>}
          {basis && <Clause c={basis} />}
          {!basis && <p className="small faint">{t("clause.label")} <span className="mono">{deadline.basis}</span></p>}
        </section>
      )}
      {essential && lapsed && (
        <section className="clock-panel clock-panel-lapsed" aria-labelledby="dl-t">
          <h2 id="dl-t" className="clock-cap">{t("deadline.lapsed")}</h2>
          {(deadline?.due_at ?? draft?.due_at) && <p className="clock-due">{t("deadline.was")} <span className="mono">{dateTimeLabel(deadline?.due_at ?? draft?.due_at, lang)}</span></p>}
          <p>{lapsedNote ?? t("deadline.lapsed_body")}</p>
          <p className="small faint">{t("clause.label")} <span className="mono">{draft?.lapsed_basis ?? "21.5.9.2"}</span></p>
        </section>
      )}
      {countdownApplies && deadline?.status === "met" && (
        <section className="clock-panel" aria-labelledby="dl-t">
          <h2 id="dl-t" className="clock-cap clock-cap-calm">{t("deadline.met")}</h2>
          <p className="clock-due">{t("deadline.was")} <span className="mono">{dateTimeLabel(deadline.due_at, lang)}</span></p>
        </section>
      )}

      <ClaimPathBlock ev={ev} caseRecord={env.case} />

      <div className="action-grid">
        <section className="block" aria-labelledby="draft-t">
          <h2 id="draft-t" className="h-sec"><Icon name="doc" /> {t("draft.title")}</h2>
          {draft?.needed === false && <p className="draft-not-needed">{t(ev?.claim_path?.route === "outside_cover" ? "draft.outside" : "draft.not_needed")}</p>}
          {text ? (
            <>
              <pre className="draft" lang={lang}>{text}</pre>
              <p className="small">{t("draft.fill")}</p>
              {partialNote && <p className="small">{partialNote}</p>}
              <div className="btn-grid">
                <a className="btn btn-big btn-primary" href={`tel:${phone}`}><Icon name="phone" /> {t("draft.call")} <span className="mono">{phone}</span></a>
                <CopyButton text={text} label={t("draft.copy")} />
                {wa && <a className="btn" href={wa} target="_blank" rel="noreferrer"><Icon name="share" /> {t("draft.share")}</a>}
                <button className="btn" onClick={download}><Icon name="download" /> {t("draft.download")}</button>
              </div>
              {(draft?.channels?.length ?? 0) > 0 && (
                <>
                  <h3 className="h-mini">{t("draft.channels")}</h3>
                  <ul className="plain">{draft!.channels!.map((c, i) => <li key={i}><Channel c={c} /></li>)}</ul>
                </>
              )}
            </>
          ) : (
            <Missing what={t("draft.missing")} why={draft?.reason ? translateRubric(draft.reason, lang) : t(ev ? "draft.no_draft" : "draft.no_evidence")}>
              <a className="btn" href={`tel:${phone}`}><Icon name="phone" /> {t("draft.call")} <span className="mono">{phone}</span></a>
            </Missing>
          )}
        </section>

        <section className="block" aria-labelledby="file-t">
          <h2 id="file-t" className="h-sec"><Icon name="check" /> {t("file.title")}</h2>
          <FiledBlock env={env} onFiled={() => load()} />
        </section>
      </div>

      <section className="block" aria-labelledby="pack-t">
        <h2 id="pack-t" className="h-sec"><Icon name="download" /> {t("pack.title")}</h2>
        {ev?.evidence_hash ? (
          <>
            <p>{t("pack.lead")}</p>
            <div className="btn-row wrap">
              <a className="btn btn-big" href={pdfUrl(caseId, lang)} target="_blank" rel="noreferrer"><Icon name="doc" /> {t("verdict.pdf")}</a>
              <a className="btn btn-big" {...linkProps(`/verify/${ev.evidence_hash}`)}><Icon name="check" /> {t("verdict.verify")}</a>
            </div>
          </>
        ) : (
          <Missing what={t("pack.missing")} why={t("verdict.not_sealed")} />
        )}
      </section>

      {ev && ev.policy.length > 0 && (
        <section className="block">
          <details className="fold">
            <summary>{t("policy.title")} <span className="mono">({ev.policy.length})</span></summary>
            {ev.policy.map((c) => (
              <div key={c.clause_id}>
                <Clause c={c} />
                {c.applies_because && <p className="small">{translateRubric(c.applies_because, lang)}</p>}
              </div>
            ))}
          </details>
        </section>
      )}

      <AskBox caseId={caseId} />
    </div>
  );
}
