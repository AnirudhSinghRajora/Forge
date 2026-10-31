import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { audioUrl } from "../api";
import { Icon } from "./Icon";

const SPEECH = { hi: "hi-IN", te: "te-IN", en: "en-IN" } as const;
type Mode = "idle" | "loading" | "audio" | "browser";

/** Server audio first. On a 404 or any failure, the browser's own voice for the language. */
export function Voice({ caseId, text }: { caseId: string; text: string | null }) {
  const { t, lang } = useI18n();
  const [mode, setMode] = useState<Mode>("idle");
  const [note, setNote] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);

  const stop = () => {
    audio.current?.pause();
    audio.current = null;
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setMode("idle");
  };
  useEffect(() => { stop(); setNote(null); }, [lang]);  
  useEffect(() => () => stop(), []);

  const speakInBrowser = () => {
    if (!text) { setNote(t("voice.no_text")); setMode("idle"); return; }
    if (!("speechSynthesis" in window)) { setNote(t("voice.unsupported")); setMode("idle"); return; }
    const u = new SpeechSynthesisUtterance(text);
    u.lang = SPEECH[lang];
    const voice = window.speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(lang));
    if (voice) u.voice = voice;
    else if (window.speechSynthesis.getVoices().length > 0) setNote(t("voice.no_voice"));
    u.rate = 0.95;
    u.onend = () => setMode("idle");
    u.onerror = () => { setMode("idle"); setNote(t("voice.unsupported")); };
    setMode("browser");
    window.speechSynthesis.speak(u);
  };

  const play = () => {
    if (mode !== "idle") { stop(); return; }
    setNote(null);
    setMode("loading");
    const a = new Audio(audioUrl(caseId, lang));
    audio.current = a;
    a.onplaying = () => setMode("audio");
    a.onended = () => setMode("idle");
    a.onerror = () => { audio.current = null; speakInBrowser(); };
    a.play().catch(() => { if (audio.current === a) { audio.current = null; speakInBrowser(); } });
  };

  const on = mode === "audio" || mode === "browser";
  return (
    <div className="voice">
      <button className="btn btn-big voice-btn" onClick={play} aria-pressed={on}>
        <Icon name={on ? "pause" : "play"} /> {mode === "loading" ? t("voice.loading") : on ? t("voice.stop") : t("voice.listen")}
      </button>
      {note && <p className="small faint" role="status">{note}</p>}
    </div>
  );
}
