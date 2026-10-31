import { useEffect, useRef, useState } from "react";
import { useI18n, type Key } from "../i18n";
import { artifactUrl } from "../api";
import { dayLabel } from "../format";
import { Missing } from "../components/Bits";
import type { Chip, OpticalEvidence } from "../types";

type View = "true_colour" | "ndvi";

export function BeforeAfter({ chips, optical }: { chips: Chip[]; optical: OpticalEvidence }) {
  const { t, lang } = useI18n();
  const [view, setView] = useState<View>("true_colour");
  const [pos, setPos] = useState(50);
  const [failed, setFailed] = useState(false);
  const stage = useRef<HTMLDivElement | null>(null);
  const dragging = useRef(false);

  const has = (k: Chip["kind"]) => chips.find((c) => c.kind === k);
  const hasNdvi = !!(has("ndvi_pre") && has("ndvi_post"));
  const pre = has(`${view}_pre` as Chip["kind"]);
  const post = has(`${view}_post` as Chip["kind"]);

  useEffect(() => setFailed(false), [view]);

  if (!has("true_colour_pre") || !has("true_colour_post")) {
    const rejected = optical.scenes_considered.filter((s) => s.status !== "accepted");
    return (
      <Missing what={t("ba.missing")} why={optical.post ? null : t("ba.no_pair")}>
        {rejected.length > 0 && (
          <ul className="scene-reasons">
            {rejected.map((s) => (
              <li key={s.id}>
                <span className="mono">{dayLabel(s.date, lang)}</span> <span className="mono small break">{s.id}</span>
                <br />{s.reasons.join("; ")}
              </li>
            ))}
          </ul>
        )}
      </Missing>
    );
  }

  const setFromClient = (clientX: number) => {
    const rect = stage.current?.getBoundingClientRect();
    if (!rect) return;
    setPos(Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100)));
  };

  return (
    <div className="ba">
      {hasNdvi && (
        <div className="seg" role="group" aria-label={t("ba.view")}>
          {(["true_colour", "ndvi"] as View[]).map((v) => (
            <button key={v} aria-pressed={view === v} onClick={() => setView(v)}>{t(`ba.${v}` as Key)}</button>
          ))}
        </div>
      )}
      {failed ? (
        <Missing what={t("ba.failed")} why={t("ba.failed_why")} />
      ) : (
        <div
          className="ba-stage"
          ref={stage}
          onPointerDown={(e) => {
            dragging.current = true;
            e.currentTarget.setPointerCapture(e.pointerId);
            setFromClient(e.clientX);
          }}
          onPointerMove={(e) => { if (dragging.current) setFromClient(e.clientX); }}
          onPointerUp={() => { dragging.current = false; }}
          onPointerCancel={() => { dragging.current = false; }}
        >
          <img src={artifactUrl(post!.path)} alt={t("ba.after_alt", { date: dayLabel(post!.date, lang) })} draggable={false} onError={() => setFailed(true)} />
          <img
            src={artifactUrl(pre!.path)}
            alt={t("ba.before_alt", { date: dayLabel(pre!.date, lang) })}
            className="ba-top"
            draggable={false}
            onError={() => setFailed(true)}
            style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}
          />
          <span className="ba-tag ba-tag-l">{t("ba.before")}</span>
          <span className="ba-tag ba-tag-r">{t("ba.after")}</span>
          <span className="ba-handle" style={{ left: `${pos}%` }} aria-hidden="true"><i /></span>
          <input
            type="range"
            min={0}
            max={100}
            value={pos}
            onChange={(e) => setPos(Number(e.target.value))}
            aria-label={t("ba.slider")}
            className="ba-range"
          />
        </div>
      )}
      <div className="ba-caption">
        <p><strong>{t("ba.before")}</strong> <span className="mono">{dayLabel(pre!.date, lang)}</span><br /><span className="mono small break">{pre!.scene_id ?? t("ba.no_id")}</span></p>
        <p><strong>{t("ba.after")}</strong> <span className="mono">{dayLabel(post!.date, lang)}</span><br /><span className="mono small break">{post!.scene_id ?? t("ba.no_id")}</span></p>
      </div>
      <p className="small faint">{t("ba.outline_note")}</p>
      {view === "ndvi" && (
        <div className="ramp">
          <span className="ramp-bar ramp-ndvi" />
          <div className="ramp-ticks mono"><span>{"−"}0.1</span><span>0.4</span><span>0.9</span></div>
          <div className="ramp-words"><span>{t("ramp.ndvi_low")}</span><span>{t("ramp.ndvi_high")}</span></div>
        </div>
      )}
    </div>
  );
}
