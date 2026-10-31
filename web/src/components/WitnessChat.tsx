import { useRef, useState } from "react";
import { useI18n, keyLabel, hasKeyLabel, type Key } from "../i18n";
import { askPolicy } from "../api";
import { useHealth } from "../health";
import { Icon } from "./Icon";
import { ErrorNote } from "./Bits";
import { TechnicalFacts } from "./Facts";
import type { AskCitation, AskResponse } from "../types";

interface Turn { id: number; q: string; a: AskResponse | null; err: unknown }

const SUGGESTED: Key[] = ["witness.q_why", "witness.q_next", "witness.q_rule"];

function Answer({ a }: { a: AskResponse }) {
  const { t, lang } = useI18n();
  const answer = a.answer ?? null;
  const refused = a.covered === false || !answer;
  const fields = a.evidence_fields ?? [];
  const clauses = (a.citations ?? []).filter((c): c is AskCitation => typeof c !== "string");
  const said = (a.lang ?? lang) as string;
  return (
    <div className={`wit-a ${refused ? "wit-a-refused" : ""}`}>
      <span className="wit-who"><Icon name="scale" size={16} /> {t("witness.who")}</span>
      <p lang={said}>{answer ?? t("witness.refused")}</p>
      {fields.some(hasKeyLabel) && (
        <p className="small wit-cites"><span>{t("witness.from_record")}</span> {fields.filter(hasKeyLabel).map((f) => <span key={f} className="wit-cite">{keyLabel(f, lang)}</span>)}</p>
      )}
      {clauses.length > 0 && (
        <details className="fine wit-clauses">
          <summary>{t("witness.clauses")} <span className="mono">{clauses.map((c) => c.clause_id).join(", ")}</span></summary>
          {clauses.map((c, i) => (
            <blockquote key={i} className="clause">
              {c.text && lang !== "en" && <p className="small faint clause-lang">{t("clause.in_english")}</p>}
              {c.text && <p lang="en">{c.text}</p>}
              <footer>
                <span className="mono">{t("clause.label")} {c.clause_id ?? "—"}</span>
                {c.doc ? ` · ${c.doc}` : ""}{c.page ? ` · ${t("clause.page")} ${c.page}` : ""}
                {c.url && <> · <a href={c.url} target="_blank" rel="noreferrer">{t("clause.open")}</a></>}
              </footer>
            </blockquote>
          ))}
        </details>
      )}
      {!refused && <p className="small faint">{t(a.llm_used ? "witness.by_gemini" : "witness.fixed")}</p>}
      <TechnicalFacts raw={fields.map((f) => ({ key: f, text: keyLabel(f, "en") }))} />
    </div>
  );
}

/** The farmer questions the record, in their own language, right under the result. */
export function WitnessChat({ caseId }: { caseId: string }) {
  const { t, lang } = useI18n();
  const { health } = useHealth();
  const [q, setQ] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const next = useRef(1);
  const off = health?.gemini === false;

  const send = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    const id = next.current++;
    setBusy(true);
    setQ("");
    setTurns((list) => [...list, { id, q: text, a: null, err: null }]);
    try {
      const a = await askPolicy(caseId, text, lang);
      setTurns((list) => list.map((x) => (x.id === id ? { ...x, a } : x)));
    } catch (err) {
      setTurns((list) => list.map((x) => (x.id === id ? { ...x, err } : x)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="witness" aria-labelledby="witness-t">
      <p className="eyebrow">{t("witness.eyebrow")}</p>
      <h2 id="witness-t" className="witness-title"><Icon name="question" /> {t("witness.title")}</h2>
      <p className="small">{t(off ? "witness.lead_off" : "witness.lead")}</p>
      {turns.length > 0 && (
        <ol className="wit-turns" aria-live="polite">
          {turns.map((turn) => (
            <li key={turn.id}>
              <div className="wit-q"><span className="wit-who">{t("witness.you")}</span><p>{turn.q}</p></div>
              {turn.a && <Answer a={turn.a} />}
              {!turn.a && !turn.err && <p className="wit-wait small"><span className="spinner" aria-hidden="true" /> {t("witness.busy")}</p>}
              {turn.err !== null && <ErrorNote error={turn.err} onRetry={() => send(turn.q)} />}
            </li>
          ))}
        </ol>
      )}
      <div className="wit-suggest">
        {SUGGESTED.map((k) => (
          <button key={k} className="chip" onClick={() => send(t(k))} disabled={busy}>{t(k)}</button>
        ))}
      </div>
      {!off && (
        <form className="ask" onSubmit={(e) => { e.preventDefault(); void send(q); }}>
          <textarea rows={2} value={q} maxLength={500} onChange={(e) => setQ(e.target.value)} placeholder={t("witness.placeholder")} lang={lang} aria-label={t("witness.placeholder")} />
          <button className="btn btn-primary" disabled={busy || !q.trim()} type="submit">{busy ? t("witness.busy") : t("witness.send")}</button>
        </form>
      )}
    </section>
  );
}
