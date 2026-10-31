import type { Lang } from "./i18n";

const LOCALE: Record<Lang, string> = { hi: "hi-IN", te: "te-IN", en: "en-IN" };
const MINUS = "−";

export function num(v: number | null | undefined, dp = 2, opts: { signed?: boolean } = {}): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const abs = Math.abs(v).toFixed(dp);
  if (v < 0 && Number(abs) !== 0) return MINUS + abs;
  if (opts.signed && v > 0 && Number(abs) !== 0) return "+" + abs;
  return abs;
}

export function rawNum(v: number): string {
  // A number exactly as stored, without any rounding beyond what the engine already applied.
  const s = String(v);
  return s.startsWith("-") ? MINUS + s.slice(1) : s;
}

export function pct(fraction: number | null | undefined, dp = 0): string {
  if (fraction === null || fraction === undefined || Number.isNaN(fraction)) return "—";
  return `${(fraction * 100).toFixed(dp)}%`;
}

function parseDay(d: string): Date {
  // Calendar dates from the API are local to the event, so do not let a timezone shift them.
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? new Date(`${d}T12:00:00`) : new Date(d);
}

export function dayLabel(d: string | null | undefined, lang: Lang, withYear = true): string {
  if (!d) return "—";
  const dt = parseDay(d);
  if (Number.isNaN(dt.getTime())) return d;
  return new Intl.DateTimeFormat(LOCALE[lang], {
    day: "numeric",
    month: "short",
    ...(withYear ? { year: "numeric" } : {}),
    numberingSystem: "latn",
  }).format(dt);
}

export function dateTimeLabel(d: string | null | undefined, lang: Lang): string {
  if (!d) return "—";
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return d;
  return new Intl.DateTimeFormat(LOCALE[lang], {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    numberingSystem: "latn",
  }).format(dt);
}

export function clock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const p = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${p(m)}:${p(sec)}` : `${p(m)}:${p(sec)}`;
}

export function dayTime(d: Date): number {
  return d.getTime();
}

export function toDayNum(d: string): number {
  return parseDay(d).getTime() / 86400000;
}

/** Local datetime value for <input type="datetime-local">. */
export function localInputValue(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function todayInput(): string {
  return localInputValue(new Date()).slice(0, 10);
}
