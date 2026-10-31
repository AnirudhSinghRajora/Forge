import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useI18n, type Key } from "../i18n";
import { useHealth } from "../health";
import { navigate, linkProps } from "../router";
import { ApiError, createCase } from "../api";
import { Icon } from "../components/Icon";
import { ErrorNote, Loading } from "../components/Bits";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { clock } from "../format";

const PinMap = lazy(() => import("../map/PinMap"));

type RecState = "idle" | "asking" | "recording" | "recorded";
type MicProblem = "denied" | "nodevice" | "unsupported" | "insecure" | "failed" | null;
type GeoProblem = "denied" | "unavailable" | "timeout" | "unsupported" | null;

const MAX_SECONDS = 180;
const SPEECH_LANG = { hi: "hi-IN", te: "te-IN", en: "en-IN" } as const;

interface SpeechRec {
  lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void; abort(): void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}

function speechCtor(): (new () => SpeechRec) | null {
  const w = window as unknown as { SpeechRecognition?: new () => SpeechRec; webkitSpeechRecognition?: new () => SpeechRec };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function pickMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((m) => MediaRecorder.isTypeSupported(m));
}

export function Start() {
  const { t, lang } = useI18n();
  const { health } = useHealth();

  const [rec, setRec] = useState<RecState>("idle");
  const [micProblem, setMicProblem] = useState<MicProblem>(null);
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [interim, setInterim] = useState("");
  const [listening, setListening] = useState(false);

  const [loc, setLoc] = useState<{ lat: number; lon: number; source: "gps" | "pin"; accuracy?: number } | null>(null);
  const [geoBusy, setGeoBusy] = useState(false);
  const [geoProblem, setGeoProblem] = useState<GeoProblem>(null);
  const [near] = useState(() => {
    const m = new URLSearchParams(location.search).get("near")?.match(/^(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/);
    return m ? { lat: Number(m[1]), lon: Number(m[2]), zoom: 13 } : null;
  });
  const [pinOpen, setPinOpen] = useState(!!near);

  const [placeDate, setPlaceDate] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const speech = useRef<SpeechRec | null>(null);
  const raf = useRef(0);
  const timer = useRef(0);
  const audioCtx = useRef<AudioContext | null>(null);

  const [lastCase, setLastCase] = useState<string | null>(null);
  useEffect(() => {
    try { setLastCase(localStorage.getItem("fs.lastCase")); } catch { /* private mode */ }
  }, []);

  const cleanupMedia = useCallback(() => {
    window.clearInterval(timer.current);
    cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((tr) => tr.stop());
    stream.current = null;
    audioCtx.current?.close().catch(() => {});
    audioCtx.current = null;
    setLevel(0);
  }, []);

  useEffect(() => () => {
    cleanupMedia();
    speech.current?.abort();
  }, [cleanupMedia]);

  useEffect(() => {
    if (!audio) { setAudioUrl(null); return; }
    const u = URL.createObjectURL(audio);
    setAudioUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [audio]);

  const startSpeech = useCallback(() => {
    const Ctor = speechCtor();
    if (!Ctor) return;
    try {
      const r = new Ctor();
      r.lang = SPEECH_LANG[lang];
      r.continuous = true;
      r.interimResults = true;
      r.onresult = (e) => {
        let fin = "";
        let mid = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const res = e.results[i];
          if (res.isFinal) fin += res[0].transcript;
          else mid += res[0].transcript;
        }
        if (fin) setText((cur) => (cur ? `${cur.trimEnd()} ${fin.trim()}` : fin.trim()));
        setInterim(mid);
      };
      r.onerror = () => setListening(false);
      r.onend = () => { setListening(false); setInterim(""); };
      r.start();
      speech.current = r;
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [lang]);

  const stopRecording = useCallback(() => {
    speech.current?.stop();
    speech.current = null;
    if (recorder.current && recorder.current.state !== "inactive") recorder.current.stop();
    else {
      cleanupMedia();
      setRec("idle");
    }
  }, [cleanupMedia]);

  const startRecording = async () => {
    setErr(null);
    setMicProblem(null);
    if (!window.isSecureContext) { setMicProblem("insecure"); return; }
    const canRecord = !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
    if (!canRecord) {
      // No recorder, but the browser may still transcribe live.
      if (speechCtor()) startSpeech();
      else setMicProblem("unsupported");
      return;
    }
    setRec("asking");
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      stream.current = s;
      const mime = pickMime();
      const mr = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      mr.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(chunks, { type: mr.mimeType || mime || "audio/webm" });
        setAudio(blob.size ? blob : null);
        setRec(blob.size ? "recorded" : "idle");
        cleanupMedia();
      };
      mr.onerror = () => { setMicProblem("failed"); cleanupMedia(); setRec("idle"); };
      recorder.current = mr;
      mr.start(1000);
      setAudio(null);
      setRec("recording");
      setSeconds(0);
      const startedAt = Date.now();
      timer.current = window.setInterval(() => {
        const sec = (Date.now() - startedAt) / 1000;
        setSeconds(sec);
        if (sec >= MAX_SECONDS) stopRecording();
      }, 250);

      // The ring around the mic follows the real input level, so a silent mic is visible.
      try {
        const ctx = new AudioContext();
        audioCtx.current = ctx;
        const an = ctx.createAnalyser();
        an.fftSize = 512;
        ctx.createMediaStreamSource(s).connect(an);
        const buf = new Uint8Array(an.fftSize);
        const loop = () => {
          an.getByteTimeDomainData(buf);
          let peak = 0;
          for (const v of buf) peak = Math.max(peak, Math.abs(v - 128));
          setLevel(Math.min(1, peak / 80));
          raf.current = requestAnimationFrame(loop);
        };
        loop();
      } catch { /* no meter; recording still works */ }

      // On Android the recogniser and the recorder fight for the mic, so transcribe live only
      // where they can share it, or where the server cannot parse audio at all.
      const android = /Android/i.test(navigator.userAgent);
      if (speechCtor() && (!android || health?.gemini === false)) startSpeech();
    } catch (e) {
      cleanupMedia();
      setRec("idle");
      const name = e instanceof DOMException ? e.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") setMicProblem("denied");
      else if (name === "NotFoundError" || name === "OverconstrainedError") setMicProblem("nodevice");
      else setMicProblem("failed");
    }
  };

  const discardRecording = () => {
    setAudio(null);
    setRec("idle");
    setSeconds(0);
  };

  const askGps = () => {
    setGeoProblem(null);
    if (!navigator.geolocation) { setGeoProblem("unsupported"); setPinOpen(true); return; }
    setGeoBusy(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setGeoBusy(false);
        setLoc({ lat: p.coords.latitude, lon: p.coords.longitude, source: "gps", accuracy: p.coords.accuracy });
        setPinOpen(false);
      },
      (e) => {
        setGeoBusy(false);
        setGeoProblem(e.code === e.PERMISSION_DENIED ? "denied" : e.code === e.TIMEOUT ? "timeout" : "unavailable");
        setPinOpen(true);
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  };

  const statement = text.trim();
  const hasStatement = !!audio || statement.length > 0;
  const ready = hasStatement && !!loc && rec !== "recording" && rec !== "asking";

  const submit = async () => {
    if (!loc || !hasStatement) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await createCase({ audio, text: statement, lat: loc.lat, lon: loc.lon, lang });
      try {
        localStorage.setItem("fs.lastCase", res.case_id);
        sessionStorage.setItem(`fs.created.${res.case_id}`, JSON.stringify(res));
        sessionStorage.setItem(`fs.loc.${res.case_id}`, JSON.stringify({ lat: loc.lat, lon: loc.lon }));
        if (placeDate && loc.source === "pin") sessionStorage.setItem(`fs.placeDate.${res.case_id}`, placeDate);
      } catch { /* storage is only a convenience */ }
      navigate(`/case/${encodeURIComponent(res.case_id)}/confirm`);
    } catch (e) {
      setErr(e);
    } finally {
      setBusy(false);
    }
  };

  const micWord: Key = rec === "recording" ? "start.stop" : rec === "asking" ? "start.asking" : rec === "recorded" ? "start.record_again" : "start.speak";

  return (
    <div className="page start">
      <div className="start-grid">
        <section className="start-main" aria-labelledby="start-title">
          <p className="eyebrow">{t("start.eyebrow")}</p>
          {near && <p className="notice small">{t("start.neighbour")}</p>}
          <h1 id="start-title" className="display">{t("start.title")}</h1>
          <p className="lede">{t("start.lede")}</p>

          <div className="mic-wrap">
            <button
              className={`mic mic-${rec}`}
              onClick={rec === "recording" ? stopRecording : startRecording}
              disabled={rec === "asking"}
              aria-pressed={rec === "recording"}
              style={{ "--level": level } as React.CSSProperties}
            >
              <span className="mic-ring" aria-hidden="true" />
              <Icon name={rec === "recording" ? "stop" : "mic"} size={64} stroke={1.4} />
              <span className="mic-word">{t(micWord)}</span>
            </button>
            <div className="mic-status" aria-live="polite">
              {rec === "recording" && (
                <p className="mono rec-time">
                  <span className="rec-dot" aria-hidden="true" /> {clock(seconds)} / {clock(MAX_SECONDS)}
                </p>
              )}
              {rec === "recording" && listening && <p className="small faint">{t("start.live_on")}</p>}
              {rec === "recorded" && audioUrl && (
                <div className="take">
                  <p className="small"><Icon name="check" size={18} /> {t("start.recorded")} <span className="mono">{clock(seconds)}</span></p>
                  <audio src={audioUrl} controls preload="metadata" />
                  <button className="linkish" onClick={discardRecording}>{t("act.discard")}</button>
                </div>
              )}
            </div>
          </div>

          {micProblem && (
            <div className="notice" role="alert">
              <p><Icon name="warn" /> {t(`mic.${micProblem}` as Key)}</p>
            </div>
          )}

          <label className="field">
            <span className="field-label"><Icon name="edit" size={18} /> {t("start.or_type")}</span>
            <textarea
              rows={3}
              value={interim ? `${text}${text ? " " : ""}${interim}` : text}
              onChange={(e) => { setText(e.target.value); setInterim(""); }}
              placeholder={t("start.type_hint")}
              lang={lang}
            />
          </label>

          <section className="locate" aria-labelledby="loc-title">
            <h2 id="loc-title" className="h-sec"><Icon name="pin" /> {t("loc.title")}</h2>
            <div className="btn-row">
              <button className="btn btn-big" onClick={askGps} disabled={geoBusy}>
                <Icon name="gps" /> {geoBusy ? t("loc.finding") : t("loc.gps")}
              </button>
              <button className="btn btn-big" aria-expanded={pinOpen} onClick={() => setPinOpen((o) => !o)}>
                <Icon name="pin" /> {t("loc.pin")}
              </button>
            </div>
            {geoProblem && <p className="notice small" role="status">{t(`geo.${geoProblem}` as Key)}</p>}
            {loc && (
              <p className="loc-set" role="status">
                <Icon name="check" size={18} /> {loc.source === "gps" ? t("loc.set_gps") : t("loc.set_pin")}{" "}
                <span className="mono">{loc.lat.toFixed(5)}, {loc.lon.toFixed(5)}</span>
                {loc.accuracy !== undefined && <span className="mono faint"> ±{Math.round(loc.accuracy)} m</span>}
              </p>
            )}
            {pinOpen && (
              <ErrorBoundary>
                <Suspense fallback={<Loading what={t("loading.map")} />}>
                  <PinMap
                    start={loc ?? near}
                    onPlace={setPlaceDate}
                    onPick={(lat, lon) => {
                      setLoc({ lat, lon, source: "pin" });
                      setPinOpen(false);
                      setGeoProblem(null);
                    }}
                  />
                </Suspense>
              </ErrorBoundary>
            )}
          </section>

          {err !== null && <ErrorNote error={err instanceof ApiError && err.status === 422 ? new Error(t("err.case_rejected") + " " + err.message) : err} onRetry={submit} />}

          <div className="cta">
            <button className="btn btn-primary btn-big btn-wide" disabled={!ready || busy} onClick={submit}>
              {busy ? t("start.sending") : t("start.submit")} <Icon name="arrow" />
            </button>
            {!ready && !busy && (
              <p className="small faint" role="status">
                {rec === "recording" ? t("start.need_stop") : !hasStatement ? t("start.need_statement") : t("start.need_location")}
              </p>
            )}
            {busy && audio && <p className="small faint" role="status">{t("start.sending_audio")}</p>}
          </div>

          {lastCase && (
            <p className="resume">
              <a {...linkProps(`/case/${encodeURIComponent(lastCase)}`)}>
                <Icon name="doc" size={18} /> {t("start.resume")} <span className="mono">{lastCase.slice(0, 12)}</span>
              </a>
            </p>
          )}
        </section>

        <aside className="start-side" aria-label={t("start.contents")}>
          <h2 className="side-title">{t("start.contents")}</h2>
          <ol className="contents">
            {([1, 2, 3, 4, 5, 6] as const).map((n) => (
              <li key={n}>
                <strong>{t(`start.c${n}.t` as Key)}</strong>
                <span>{t(`start.c${n}.d` as Key)}</span>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </div>
  );
}
