import { useEffect, useState } from "react";
import { useI18n, type Key } from "../i18n";
import { ApiError, getCase, patchCase, type CaseRecord } from "../api";
import { navigate } from "../router";
import { Icon } from "../components/Icon";
import { ErrorNote, Loading } from "../components/Bits";
import { dayLabel, localInputValue, todayInput } from "../format";

// Sentinel-2's launch. No image from before it can exist, so no such date can be checked.
const EARLIEST_DATE = "2015-06-23";
import type { CreateCaseResponse, EventType } from "../types";

const EVENTS: { id: EventType; icon: string }[] = [
  { id: "hail", icon: "hail" },
  { id: "unseasonal_rain", icon: "rain" },
  { id: "flood", icon: "flood" },
  { id: "cyclone", icon: "cyclone" },
  { id: "wind", icon: "wind" },
  { id: "pest", icon: "pest" },
  { id: "drought", icon: "sun" },
  { id: "other", icon: "other" },
];

// Chips send the canonical name: the server's routing compares crop names in English.
const CROPS = ["paddy", "cotton", "wheat", "sugarcane", "maize", "mustard", "soybean", "groundnut"] as const;

function daysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return localInputValue(d).slice(0, 10);
}

function readCreated(id: string): CreateCaseResponse | null {
  try {
    const raw = sessionStorage.getItem(`fs.created.${id}`);
    return raw ? (JSON.parse(raw) as CreateCaseResponse) : null;
  } catch {
    return null;
  }
}

export default function Confirm({ caseId }: { caseId: string }) {
  const { t, lang } = useI18n();
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const [transcript, setTranscript] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [needs, setNeeds] = useState<string[]>([]);
  const [questions, setQuestions] = useState<Record<string, Record<string, string>>>({});
  const [dateNote, setDateNote] = useState<string | null>(null);
  const [crop, setCrop] = useState("");
  const [eventType, setEventType] = useState<string>("");
  const [eventDate, setEventDate] = useState("");
  const [eventTime, setEventTime] = useState("");

  const [insured, setInsured] = useState<"" | "yes" | "no" | "unknown">("");
  const [stage, setStage] = useState<"" | "standing" | "cut_and_spread" | "harvested_stored" | "unknown">("");

  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<unknown>(null);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    const ctl = new AbortController();
    setLoadErr(null);
    const created = readCreated(caseId);
    if (created) {
      setTranscript(created.parsed?.transcript ?? null);
      setConfidence(created.parsed?.confidence ?? null);
      setNeeds(created.needs ?? []);
      setCrop(created.parsed?.crop ?? "");
      setEventType(created.parsed?.event_type && created.parsed.event_type !== "unknown" ? created.parsed.event_type : "");
      setEventDate(created.parsed?.event_date ?? "");
      setEventTime(created.parsed?.event_time ?? "");
      setQuestions(created.questions ?? {});
      setDateNote(created.parsed?.date_note ?? null);
      setLoaded(true);
    }
    getCase(caseId, ctl.signal)
      .then((env) => {
        const c: CaseRecord = env.case;
        if (!created) {
          setQuestions(c.questions ?? {});
          setConfidence(c.parsed?.confidence ?? null);
          setDateNote(c.parsed?.date_note ?? null);
          setTranscript(c.transcript ?? null);
          setNeeds(Array.isArray(c.needs) ? c.needs : []);
          setCrop(c.crop ?? "");
          setEventType(c.event_type && c.event_type !== "unknown" ? c.event_type : "");
          setEventDate(c.event_date ?? "");
          setEventTime(c.event_time ?? "");
          if (c.insured === "yes" || c.insured === "no" || c.insured === "unknown") setInsured(c.insured);
          if (c.crop_stage === "standing" || c.crop_stage === "cut_and_spread" || c.crop_stage === "harvested_stored" || c.crop_stage === "unknown") setStage(c.crop_stage);
        }
        setLoaded(true);
      })
      .catch((e) => {
        if (!ctl.signal.aborted && !created) setLoadErr(e);
      });
    return () => ctl.abort();
  }, [caseId, attempt]);

  const needed = (f: string) => needs.includes(f);
  const ask = (f: string) => questions[f]?.[lang] ?? questions[f]?.en ?? t("confirm.please_tell");
  const missingDate = !eventDate;
  const futureDate = !!eventDate && eventDate > todayInput();
  const earlyDate = !!eventDate && eventDate < EARLIEST_DATE;
  // The server names a date it refused in a report. The reader gets a sentence, never that code.
  const noteKind = dateNote?.split(":")[0];
  const noteText = noteKind === "future_date_refused" ? t("confirm.date_future") : noteKind === "too_old_refused" ? t("confirm.note_old") : dateNote;
  // The plot is the next screen, and the three fields below ask for themselves.
  const known = new Set(["crop", "event_type", "event_date", "plot", "insured", "crop_stage"]);
  const otherNeeds = needs.filter((n) => !known.has(n));

  const save = async () => {
    setTouched(true);
    if (missingDate || futureDate || earlyDate) return;
    setSaving(true);
    setSaveErr(null);
    try {
      const patch: Record<string, unknown> = { event_date: eventDate };
      if (crop.trim()) patch.crop = crop.trim();
      if (eventType) patch.event_type = eventType;
      if (eventTime) patch.event_time = eventTime;
      if (insured) patch.insured = insured;
      if (stage) patch.crop_stage = stage;
      await patchCase(caseId, patch);
      navigate(`/case/${encodeURIComponent(caseId)}/plot`);
    } catch (e) {
      setSaveErr(e);
    } finally {
      setSaving(false);
    }
  };

  if (loadErr) {
    const gone = loadErr instanceof ApiError && loadErr.status === 404;
    return (
      <div className="page narrow">
        {gone ? <p className="notice">{t("case.not_found")}</p> : <ErrorNote error={loadErr} onRetry={() => setAttempt((a) => a + 1)} />}
      </div>
    );
  }
  if (!loaded) return <div className="page narrow"><Loading what={t("loading.case")} /></div>;

  return (
    <div className="page narrow confirm">
      <p className="eyebrow">{t("confirm.eyebrow")}</p>
      <h1 className="h-page">{t("confirm.title")}</h1>

      <figure className="statement">
        <figcaption>{t("confirm.you_said")}</figcaption>
        {transcript ? (
          <blockquote>{transcript}</blockquote>
        ) : (
          <p className="faint">{t("confirm.no_transcript")}</p>
        )}
        {confidence !== null && confidence < 0.6 && <p className="small">{t("confirm.low_conf")}</p>}
      </figure>

      {otherNeeds.length > 0 && (
        <div className="ask-list">
          <p><strong>{t("confirm.needs")}</strong></p>
          <ul>{otherNeeds.map((n) => <li key={n}>{questions[n]?.[lang] ?? questions[n]?.en ?? n}</li>)}</ul>
        </div>
      )}

      <fieldset className={`q ${needed("event_type") ? "q-need" : ""}`}>
        <legend>{t("confirm.q_event")}</legend>
        {needed("event_type") && <p className="q-ask">{ask("event_type")}</p>}
        <div className="event-grid" role="radiogroup">
          {EVENTS.map((e) => (
            <button
              key={e.id}
              role="radio"
              aria-checked={eventType === e.id}
              className={`event ${eventType === e.id ? "event-on" : ""}`}
              onClick={() => setEventType(e.id)}
            >
              <Icon name={e.icon} size={30} stroke={1.5} />
              <span>{t(`event.${e.id}` as Key)}</span>
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset className={`q ${needed("event_date") ? "q-need" : ""}`}>
        <legend>{t("confirm.q_date")}</legend>
        {needed("event_date") && <p className="q-ask">{ask("event_date")}</p>}
        {noteText && <p className="small">{noteText}</p>}
        <div className="btn-row wrap">
          {([["confirm.today", 0], ["confirm.yesterday", 1], ["confirm.before_yesterday", 2]] as [Key, number][]).map(([k, n]) => (
            <button key={k} className={`chip chip-big ${eventDate === daysAgo(n) ? "chip-on" : ""}`} onClick={() => setEventDate(daysAgo(n))}>
              {t(k)}
            </button>
          ))}
        </div>
        <div className="input-row">
          <label className="field">
            <span className="field-label">{t("confirm.date")}</span>
            <input type="date" value={eventDate} min={EARLIEST_DATE} max={todayInput()} onChange={(e) => setEventDate(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">{t("confirm.time")}</span>
            <input type="time" value={eventTime} onChange={(e) => setEventTime(e.target.value)} />
          </label>
        </div>
        {eventDate && <p className="small mono faint">{dayLabel(eventDate, lang)}</p>}
        {touched && missingDate && <p className="notice small" role="alert">{t("confirm.date_required")}</p>}
        {futureDate && <p className="notice small" role="alert">{t("confirm.date_future")}</p>}
        {earlyDate && <p className="notice small" role="alert">{t("confirm.date_early")}</p>}
      </fieldset>

      <fieldset className={`q ${needed("crop") ? "q-need" : ""}`}>
        <legend>{t("confirm.q_crop")}</legend>
        {needed("crop") && <p className="q-ask">{ask("crop")}</p>}
        <div className="btn-row wrap">
          {CROPS.map((id) => (
            <button key={id} className={`chip chip-big ${crop.trim().toLowerCase() === id ? "chip-on" : ""}`} onClick={() => setCrop(id)}>
              {t(`crop.${id}` as Key)}
            </button>
          ))}
        </div>
        <label className="field">
          <span className="field-label">{t("confirm.crop_other")}</span>
          <input value={(CROPS as readonly string[]).includes(crop.trim().toLowerCase()) ? "" : crop} maxLength={64} onChange={(e) => setCrop(e.target.value)} lang={lang} />
        </label>
      </fieldset>

      <fieldset className="q">
        <legend>{t("confirm.q_insured")}</legend>
        <p className="small faint">{t("confirm.optional")}</p>
        <div className="btn-row wrap" role="radiogroup">
          {(["yes", "no", "unknown"] as const).map((v) => (
            <button key={v} role="radio" aria-checked={insured === v} className={`chip chip-big ${insured === v ? "chip-on" : ""}`} onClick={() => setInsured(insured === v ? "" : v)}>
              {t(`insured.${v}` as Key)}
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset className="q">
        <legend>{t("confirm.q_stage")}</legend>
        <p className="small faint">{t("confirm.optional")}</p>
        <div className="btn-row wrap" role="radiogroup">
          {(["standing", "cut_and_spread", "harvested_stored", "unknown"] as const).map((v) => (
            <button key={v} role="radio" aria-checked={stage === v} className={`chip chip-big ${stage === v ? "chip-on" : ""}`} onClick={() => setStage(stage === v ? "" : v)}>
              {t(`stage.${v}` as Key)}
            </button>
          ))}
        </div>
      </fieldset>

      {saveErr !== null && <ErrorNote error={saveErr} onRetry={save} />}
      <div className="cta">
        <button className="btn btn-primary btn-big btn-wide" onClick={save} disabled={saving}>
          {saving ? t("act.saving") : t("confirm.next")} <Icon name="arrow" />
        </button>
      </div>
    </div>
  );
}
