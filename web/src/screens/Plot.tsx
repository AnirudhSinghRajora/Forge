import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { ApiError, getCase, putPlot, startInvestigation } from "../api";
import { navigate } from "../router";
import PlotMap, { type DrawPhase, type PlotMapHandle } from "../map/PlotMap";
import { Icon } from "../components/Icon";
import { ErrorNote, Loading } from "../components/Bits";
import { closeRing, HA_PER_ACRE, HA_PER_BIGHA, ringAreaM2, selfIntersects } from "../geo";
import { num } from "../format";

export default function Plot({ caseId }: { caseId: string }) {
  const { t, lang } = useI18n();
  const mapRef = useRef<PlotMapHandle | null>(null);
  const [center, setCenter] = useState<{ lat: number; lon: number } | null>(null);
  const [initialRing, setInitialRing] = useState<number[][] | null>(null);
  const [ready, setReady] = useState(false);
  const [loadErr, setLoadErr] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  const [ring, setRing] = useState<number[][] | null>(null);
  const [corners, setCorners] = useState(0);
  const [phase, setPhase] = useState<DrawPhase>("loading");

  const [busy, setBusy] = useState<"" | "saving" | "starting">("");
  const [err, setErr] = useState<unknown>(null);
  const [saved, setSaved] = useState<{ area_ha: number; warnings: string[] } | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    setLoadErr(null);
    let stored: { lat: number; lon: number } | null = null;
    try {
      const raw = sessionStorage.getItem(`fs.loc.${caseId}`);
      stored = raw ? JSON.parse(raw) : null;
    } catch { /* fall through to the server's copy */ }
    getCase(caseId, ctl.signal)
      .then((env) => {
        const c = env.case;
        const lat = typeof c.lat === "number" ? c.lat : stored?.lat;
        const lon = typeof c.lon === "number" ? c.lon : stored?.lon;
        if (lat !== undefined && lon !== undefined) setCenter({ lat, lon });
        const poly = c.plot?.geometry ?? env.evidence?.plot?.geometry;
        if (poly?.coordinates?.[0]) setInitialRing(poly.coordinates[0]);
        if (c.active_run_id) navigate(`/case/${encodeURIComponent(caseId)}/investigate?run=${encodeURIComponent(c.active_run_id)}`, { replace: true });
        setReady(true);
      })
      .catch((e) => {
        if (ctl.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) setLoadErr(e);
        else if (stored) {
          setCenter(stored);
          setReady(true);
        } else setLoadErr(e);
      });
    return () => ctl.abort();
  }, [caseId, attempt]);

  const onRing = useCallback((r: number[][] | null, c: number, p: DrawPhase) => {
    setRing(r);
    setCorners(c);
    setPhase(p);
    setSaved(null);
    setErr(null);
  }, []);

  const closed = useMemo(() => (ring ? closeRing(ring) : null), [ring]);
  const areaHa = closed ? ringAreaM2(closed) / 10000 : 0;
  const crossing = phase === "editing" && !!closed && selfIntersects(closed);
  const canFinish = phase === "drawing" && corners >= 3;
  const valid = phase === "editing" && !!closed && closed.length >= 4 && !crossing && areaHa > 0;

  const begin = async () => {
    setBusy("starting");
    setErr(null);
    try {
      const { run_id } = await startInvestigation(caseId);
      navigate(`/case/${encodeURIComponent(caseId)}/investigate?run=${encodeURIComponent(run_id)}`);
    } catch (e) {
      setErr(e);
      setBusy("");
    }
  };

  const save = async () => {
    if (!closed || !valid) return;
    setBusy("saving");
    setErr(null);
    try {
      const res = await putPlot(caseId, { type: "Polygon", coordinates: [closed] });
      setSaved({ area_ha: res.area_ha, warnings: (lang === "hi" ? res.warnings_hi : null) ?? res.warnings ?? [] });
      if ((res.warnings ?? []).length === 0) {
        await begin();
        return;
      }
      setBusy("");
    } catch (e) {
      setErr(e);
      setBusy("");
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
  if (!ready) return <div className="page narrow"><Loading what={t("loading.case")} /></div>;

  const shownHa = saved ? saved.area_ha : areaHa;
  const showArea = phase === "editing" || corners >= 3;

  return (
    <div className="plot">
      <PlotMap ref={mapRef} center={center} initialRing={initialRing} onRing={onRing} />
      <section className="plot-sheet" aria-label={t("plot.title")}>
        <h1 className="h-sheet">{t("plot.title")}</h1>
        <div className="area" aria-live="polite">
          {showArea ? (
            <dl>
              <div><dd className="mono">{num(shownHa / HA_PER_ACRE, 2)}</dd><dt>{t("unit.acre")}</dt></div>
              <div><dd className="mono">{num(shownHa / HA_PER_BIGHA, 2)}</dd><dt>{t("unit.bigha")}</dt></div>
              <div><dd className="mono">{num(shownHa, 2)}</dd><dt>{t("unit.hectare")}</dt></div>
            </dl>
          ) : (
            <p className="area-empty">{t("plot.area_empty")}</p>
          )}
          {showArea && <p className="small faint">{t("plot.bigha_note")}</p>}
        </div>

        <p className="plot-hint" role="status">
          {phase === "editing" ? t("plot.hint_edit") : corners === 0 ? t("plot.hint_start") : corners < 3 ? t("plot.hint_more") : t("plot.hint_finish")}
        </p>

        <div className="btn-row plot-tools">
          {phase !== "editing" && (
            <button className="btn" onClick={() => mapRef.current?.undo()} disabled={corners === 0}>
              <Icon name="undo" /> {t("plot.undo")}
            </button>
          )}
          <button className="btn" onClick={() => mapRef.current?.clear()} disabled={corners === 0}>
            <Icon name="trash" /> {t("plot.clear")}
          </button>
          {phase !== "editing" && (
            <button className="btn btn-primary" onClick={() => mapRef.current?.finish()} disabled={!canFinish}>
              <Icon name="check" /> {t("plot.finish")}
            </button>
          )}
        </div>

        {crossing && <p className="notice" role="alert"><Icon name="warn" /> {t("plot.crossing")}</p>}

        {saved && saved.warnings.length > 0 && (
          <div className="notice" role="status">
            <p><strong>{t("plot.api_warnings")}</strong></p>
            <ul>{saved.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
          </div>
        )}

        {err !== null && <ErrorNote error={err} onRetry={saved ? begin : save} />}

        {phase === "editing" && (
          <div className="cta">
            {saved ? (
              <>
                <button className="btn btn-primary btn-big btn-wide" onClick={begin} disabled={busy !== ""}>
                  {busy === "starting" ? t("plot.starting") : t("plot.start_anyway")} <Icon name="arrow" />
                </button>
                <p className="small faint">{t("plot.adjust_note")}</p>
              </>
            ) : (
              <button className="btn btn-primary btn-big btn-wide" onClick={save} disabled={!valid || busy !== ""}>
                {busy === "saving" ? t("plot.saving") : busy === "starting" ? t("plot.starting") : t("plot.confirm")} <Icon name="arrow" />
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
