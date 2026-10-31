import { useI18n } from "../i18n";
import { useNow } from "./Bits";

export function useRemaining(dueAt: string | null | undefined) {
  const now = useNow(1000, !!dueAt);
  if (!dueAt) return null;
  const due = new Date(dueAt).getTime();
  if (Number.isNaN(due)) return null;
  return Math.floor((due - now) / 1000);
}

/** The one place on screen allowed to use the urgent colour. */
export function Countdown({ dueAt, size = "lg" }: { dueAt: string; size?: "sm" | "lg" }) {
  const { t } = useI18n();
  const left = useRemaining(dueAt);
  if (left === null) return null;
  if (left <= 0) return <span className={`clock clock-${size} clock-over mono`}>00:00:00</span>;
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    <span className={`clock clock-${size}`} role="timer" aria-label={t("deadline.left_aria", { h, m })}>
      <span className="clock-part"><b className="mono">{p(h)}</b><i>{t("deadline.h")}</i></span>
      <span className="clock-sep mono" aria-hidden="true">:</span>
      <span className="clock-part"><b className="mono">{p(m)}</b><i>{t("deadline.m")}</i></span>
      <span className="clock-sep mono" aria-hidden="true">:</span>
      <span className="clock-part"><b className="mono">{p(s)}</b><i>{t("deadline.s")}</i></span>
    </span>
  );
}
