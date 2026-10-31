import { useI18n } from "../i18n";
import { dayLabel, num } from "../format";
import { greennessWords, ndviColour } from "../plain";
import type { PlotStats } from "../types";

/** Before and after as two bars and one sentence, with the exact values beside them. */
export function GreennessBars({ pre, post }: { pre: PlotStats; post: PlotStats }) {
  const { t, lang } = useI18n();
  const words = greennessWords(pre.ndvi_median, post.ndvi_median);
  const row = (label: string, s: PlotStats) => (
    <div className="gbar">
      <span className="gbar-when">{label} <span className="mono">{dayLabel(s.date, lang, false)}</span></span>
      <span className="gbar-track">
        <i style={{ width: `${Math.max(0, Math.min(1, s.ndvi_median)) * 100}%`, background: ndviColour(s.ndvi_median) }} />
      </span>
      <b className="mono">{num(s.ndvi_median, 2)}</b>
    </div>
  );
  return (
    <div className="gbars">
      <p className="gbars-say">{t(words.key, words.vars)}</p>
      {row(t("ba.before"), pre)}
      {row(t("ba.after"), post)}
      <p className="small faint">{t("plain.scale_note")}</p>
    </div>
  );
}
