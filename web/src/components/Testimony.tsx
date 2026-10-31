import { useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { artifactUrl, testimonyAudioUrl } from "../api";
import { Icon } from "./Icon";
import { Stamp } from "./Stamp";
import { useInView, usePrefersReducedMotion } from "./Bits";
import { dayLabel, num } from "../format";
import { bboxOfRing } from "../geo";
import type { Chip, Evidence } from "../types";

interface Frame {
  date: string; sensor: "s2" | "s1"; ndvi: number | null; vh: number | null; qa: string | null; chip: Chip | null;
}

/** NDVI to the chip's own RdYlGn stretch (-0.1 to 0.9), so a silhouette and a chip read alike. */
function ndviColour(v: number): string {
  const stops: [number, [number, number, number]][] = [
    [0, [165, 0, 38]], [0.25, [244, 109, 67]], [0.5, [255, 255, 191]], [0.75, [102, 189, 99]], [1, [0, 104, 55]],
  ];
  const p = Math.max(0, Math.min(1, (v + 0.1) / 1.0));
  for (let i = 1; i < stops.length; i++) {
    if (p <= stops[i][0]) {
      const [a, ca] = stops[i - 1];
      const [b, cb] = stops[i];
      const f = (p - a) / (b - a);
      return `rgb(${ca.map((c, k) => Math.round(c + (cb[k] - c) * f)).join(",")})`;
    }
  }
  return "rgb(0,104,55)";
}

function vhGrey(db: number): string {
  // Typical VH over cropland runs about -25 to -10 dB. Brighter means stronger radar return.
  const p = Math.max(0, Math.min(1, (db + 25) / 15));
  const g = Math.round(70 + p * 150);
  return `rgb(${g},${g},${g})`;
}

function FieldShape({ ev, fill }: { ev: Evidence; fill: string }) {
  const ring = ev.plot.geometry.coordinates[0];
  const [w, s, e, n] = bboxOfRing(ring);
  const midLat = (s + n) / 2;
  const kx = Math.cos((midLat * Math.PI) / 180);
  const dw = (e - w) * kx || 1;
  const dh = n - s || 1;
  const scale = 80 / Math.max(dw, dh);
  const ox = (100 - dw * scale) / 2;
  const oy = (100 - dh * scale) / 2;
  const pts = ring.map(([x, y]) => `${(ox + (x - w) * kx * scale).toFixed(2)},${(oy + (n - y) * scale).toFixed(2)}`).join(" ");
  return (
    <svg viewBox="0 0 100 100" className="flip-shape" aria-hidden="true">
      <polygon points={pts} fill={fill} className="flip-shape-poly" />
    </svg>
  );
}

function sentences(text: string): string[] {
  // Whitespace must follow the stop, so decimals such as 0.80 stay whole.
  return text.split(/(?<=[।.!?])\s+/).map((x) => x.trim()).filter(Boolean);
}

const SPEECH = { hi: "hi-IN", te: "te-IN", en: "en-IN" } as const;

/** The result opens with the field itself speaking, over every pass the satellites made of it. */
export function Testimony({ ev, caseId, verdictLine }: { ev: Evidence; caseId: string; verdictLine: string | null }) {
  const { t, lang } = useI18n();
  const reduced = usePrefersReducedMotion();
  const text = (lang === "te" ? ev.testimony_te : lang === "hi" ? ev.testimony_hi : ev.testimony_en) ?? null;
  const fallbackOther = text ? null : ev.testimony_en ?? ev.testimony_hi ?? null;
  const shown = text ?? fallbackOther;
  const lines = useMemo(() => (shown ? sentences(shown) : []), [shown]);

  const frames = useMemo<Frame[]>(() => {
    const chipFor = (date: string, sensor: "s1" | "s2") =>
      sensor === "s2"
        ? ev.chips.find((c) => c.date === date && (c.kind === "true_colour_pre" || c.kind === "true_colour_post")) ?? null
        : null;
    return ev.timeline
      .filter((p) => (p.sensor === "s2" ? p.ndvi !== null && p.ndvi !== undefined : p.vh_db !== null && p.vh_db !== undefined) || p.qa === "rejected")
      .slice()
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((p) => ({ date: p.date, sensor: p.sensor, ndvi: p.ndvi ?? null, vh: p.vh_db ?? null, qa: p.qa ?? null, chip: chipFor(p.date, p.sensor) }));
  }, [ev]);

  const [slot, inView] = useInView<HTMLDivElement>("0px");
  const [i, setI] = useState(0);
  const [speaking, setSpeaking] = useState(false);
  const [lineAt, setLineAt] = useState(-1);
  const [note, setNote] = useState<string | null>(null);
  const userMoved = useRef(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const stopFlag = useRef(false);

  // The flipbook runs once on arrival, at the pace of pages being turned, and rests on the last pass.
  useEffect(() => {
    if (!inView || reduced || frames.length < 2) {
      if (reduced && frames.length) setI(frames.length - 1);
      return;
    }
    if (userMoved.current || i >= frames.length - 1) return;
    const id = window.setTimeout(() => setI((n) => n + 1), speaking ? 2200 : Math.max(280, 3200 / frames.length));
    return () => window.clearTimeout(id);
  }, [inView, reduced, frames.length, i, speaking]);

  const stop = () => {
    stopFlag.current = true;
    audio.current?.pause();
    audio.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setSpeaking(false);
    setLineAt(-1);
  };
  useEffect(() => { stop(); setNote(null); }, [lang]);
  useEffect(() => () => stop(), []);

  const speakBrowser = () => {
    if (!("speechSynthesis" in window) || lines.length === 0) {
      setNote(t("voice.unsupported"));
      setSpeaking(false);
      return;
    }
    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find((v) => v.lang.toLowerCase().startsWith(lang));
    if (!voice && voices.length > 0) setNote(t("voice.no_voice"));
    stopFlag.current = false;
    setSpeaking(true);
    const sayLine = (k: number) => {
      if (stopFlag.current || k >= lines.length) { setSpeaking(false); setLineAt(-1); return; }
      const u = new SpeechSynthesisUtterance(lines[k]);
      u.lang = SPEECH[lang];
      if (voice) u.voice = voice;
      u.rate = 0.92;
      u.onstart = () => setLineAt(k);
      u.onend = () => sayLine(k + 1);
      u.onerror = () => { setSpeaking(false); setLineAt(-1); };
      window.speechSynthesis.speak(u);
    };
    sayLine(0);
  };

  const listen = () => {
    if (speaking) { stop(); return; }
    setNote(null);
    stopFlag.current = false;
    if (!userMoved.current) setI(0);
    setSpeaking(true);
    const a = new Audio(testimonyAudioUrl(caseId, lang));
    audio.current = a;
    a.onended = () => { setSpeaking(false); };
    a.onerror = () => { audio.current = null; speakBrowser(); };
    a.play().catch(() => { if (audio.current === a) { audio.current = null; speakBrowser(); } });
  };

  const frame = frames[i];

  return (
    <section className="testimony" aria-labelledby="testimony-t" ref={slot}>
      <div className="testimony-book">
        {frame ? (
          <>
            <div className={`flip flip-${frame.qa ?? "accepted"}`} key={`${frame.date}${frame.sensor}`}>
              {frame.chip ? (
                <img src={artifactUrl(frame.chip.path)} alt={t("field.frame_alt", { date: dayLabel(frame.date, lang) })} />
              ) : frame.qa === "rejected" ? (
                <div className="flip-none"><FieldShape ev={ev} fill="transparent" /></div>
              ) : frame.sensor === "s2" && frame.ndvi !== null ? (
                <FieldShape ev={ev} fill={ndviColour(frame.ndvi)} />
              ) : frame.vh !== null ? (
                <FieldShape ev={ev} fill={vhGrey(frame.vh)} />
              ) : (
                <div className="flip-none"><FieldShape ev={ev} fill="transparent" /></div>
              )}
              {frame.qa === "rejected" && <Stamp size="md" tone="muted" className="flip-stamp">{t("trace.rejected")}</Stamp>}
            </div>
            <div className="flip-caption">
              <b className="mono">{dayLabel(frame.date, lang)}</b>
              <span>{frame.sensor === "s2" ? t("field.optical") : t("field.radar")}</span>
              <span className="mono">
                {frame.sensor === "s2" ? (frame.ndvi !== null ? `NDVI ${num(frame.ndvi, 2)}` : "NDVI —") : frame.vh !== null ? `VH ${num(frame.vh, 1)} dB` : "VH —"}
              </span>
            </div>
            {frames.length > 1 && (
              <input
                className="flip-range"
                type="range"
                min={0}
                max={frames.length - 1}
                value={i}
                aria-label={t("field.scrub")}
                aria-valuetext={dayLabel(frame.date, lang)}
                onChange={(e) => { userMoved.current = true; setI(Number(e.target.value)); }}
              />
            )}
            <p className="flip-note">{t(frame.chip ? "field.note_chip" : "field.note_shape")} · {t("field.count", { n: frames.length })}</p>
          </>
        ) : (
          <div className="flip-empty">
            <FieldShape ev={ev} fill="none" />
            <p>{t("field.no_passes")}</p>
          </div>
        )}
      </div>

      <div className="testimony-words">
        <p className="testimony-eyebrow" id="testimony-t">{t("field.eyebrow")}</p>
        {shown ? (
          <>
            <div className="testimony-text" lang={text ? lang : "en"}>
              {lines.map((l, k) => <span key={k} className={k === lineAt ? "said" : lineAt >= 0 ? "unsaid" : ""}>{l} </span>)}
            </div>
            {!text && <p className="small testimony-note">{t("field.other_lang")}</p>}
            <button className="btn btn-big testimony-listen" onClick={listen} aria-pressed={speaking}>
              <Icon name={speaking ? "pause" : "play"} /> {t(speaking ? "voice.stop" : "field.listen")}
            </button>
            {note && <p className="small testimony-note" role="status">{note}</p>}
          </>
        ) : (
          <p className="testimony-missing">
            <strong>{t("missing.label")}</strong> {t("field.missing")}
          </p>
        )}
        {verdictLine && <p className="testimony-verdict"><span>{t("field.finding")}</span> {verdictLine}</p>}
      </div>
    </section>
  );
}
