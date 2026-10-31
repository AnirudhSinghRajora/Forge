import { useState } from "react";
import { useI18n, type Key } from "../i18n";
import { patchCase, type ExhibitStatus } from "../api";
import { useHealth } from "../health";
import { Stamp } from "./Stamp";
import { ErrorNote } from "./Bits";
import { todayInput } from "../format";

const EARLIEST_DATE = "2015-06-23";
const EVENTS = ["hail", "unseasonal_rain", "flood", "cyclone", "wind", "pest", "drought", "other"] as const;
const STAGES = ["standing", "cut_and_spread", "harvested_stored", "unknown"] as const;

/** A model's look at the before and after images. Advisory, labelled so, and never a blocker. */
export function ImageOpinion({ entry }: { entry: ExhibitStatus | undefined }) {
  const { t, lang } = useI18n();
  const { health } = useHealth();
  const label = <p className="opinion-label">{t("opinion.label")}</p>;
  if (health?.gemini === false && entry?.status !== "done") {
    return <aside className="opinion opinion-off"><p className="small">{t("opinion.off")}</p></aside>;
  }
  if (!entry) return null;
  if (entry.status === "pending") {
    return (
      <aside className="opinion" role="status">
        {label}
        <p className="small"><span className="spinner" aria-hidden="true" /> {t("opinion.pending")}</p>
      </aside>
    );
  }
  if (entry.status === "failed") return <aside className="opinion opinion-off"><p className="small">{t("opinion.failed")}</p></aside>;
  if (entry.status === "not_applicable" || !entry.opinion) return <aside className="opinion opinion-off"><p className="small">{t("opinion.none")}</p></aside>;
  const o = entry.opinion;
  const text = lang === "te" ? o.description_te : lang === "hi" ? o.description_hi : o.description_en;
  return (
    <aside className={`opinion ${o.needs_person ? "opinion-person" : ""}`}>
      {label}
      <p>{text}</p>
      {o.needs_person ? (
        <>
          <Stamp size="sm" tone="soil">{t("opinion.needs_person")}</Stamp>
          <p className="small">{t("opinion.needs_person_why")}</p>
        </>
      ) : (
        <p className="small">{t(o.consistent === "yes" ? "opinion.fits" : "opinion.unclear")}</p>
      )}
    </aside>
  );
}

function dismissedKey(caseId: string, question: string) {
  return `fs.statement.${caseId}.${question.length}.${question.slice(0, 24)}`;
}

/** One question from comparing the farmer's statement with the evidence. It proposes and changes
 * nothing: the farmer's answer goes through the same PATCH as the confirm screen. */
export function StatementQuestion({ caseId, entry, onAnswered }: { caseId: string; entry: ExhibitStatus | undefined; onAnswered: () => void }) {
  const { t, lang } = useI18n();
  const q = entry?.status === "done" ? entry.question ?? null : null;
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);
  const [saved, setSaved] = useState<"plain" | "rerun" | null>(null);
  const key = q ? dismissedKey(caseId, q.en) : "";
  const [, setDismissed] = useState(false);
  if (!q) return null;
  const isDismissed = (() => { try { return localStorage.getItem(key) === "1"; } catch { return false; } })();
  if (isDismissed && !saved) return null;

  const close = () => {
    try { localStorage.setItem(key, "1"); } catch { /* private mode */ }
    setDismissed(true);
  };
  const save = async () => {
    if (!value) return;
    setBusy(true);
    setErr(null);
    const field = q.about === "date" ? "event_date" : q.about === "event" ? "event_type" : "crop_stage";
    try {
      await patchCase(caseId, { [field]: value });
      setSaved(q.about === "crop_stage" ? "plain" : "rerun");
      close();
      onAnswered();
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  if (saved) return <p className="notice small" role="status">{t(saved === "rerun" ? "statement.saved_rerun" : "statement.saved")}</p>;
  const text = lang === "te" ? q.te : lang === "hi" ? q.hi : q.en;
  return (
    <section className="statement-q" aria-labelledby="statement-q-t">
      <p className="opinion-label" id="statement-q-t">{t("statement.label")}</p>
      <p className="statement-q-text">{text}</p>
      <p className="small">{t("statement.note")}</p>
      <div className="btn-row wrap">
        {q.about === "date" && (
          <label className="field">
            <span className="field-label">{t("statement.date")}</span>
            <input type="date" value={value} min={EARLIEST_DATE} max={todayInput()} onChange={(e) => setValue(e.target.value)} />
          </label>
        )}
        {q.about === "event" && EVENTS.map((id) => (
          <button key={id} className={`chip ${value === id ? "chip-on" : ""}`} onClick={() => setValue(id)}>{t(`event.${id}` as Key)}</button>
        ))}
        {q.about === "crop_stage" && STAGES.map((id) => (
          <button key={id} className={`chip ${value === id ? "chip-on" : ""}`} onClick={() => setValue(id)}>{t(`stage.${id}` as Key)}</button>
        ))}
      </div>
      <div className="btn-row wrap">
        <button className="btn btn-primary" onClick={save} disabled={busy || !value}>{busy ? t("act.saving") : t("statement.save")}</button>
        <button className="btn" onClick={close}>{t("statement.stands")}</button>
      </div>
      {err !== null && <ErrorNote error={err} />}
    </section>
  );
}
