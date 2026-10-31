// Plain words derived only from evidence values. Exact numbers stay visible next to these.
import type { Key } from "./i18n";

/** NDVI to the chip's own RdYlGn stretch (-0.1 to 0.9), so bars, silhouettes and chips read alike. */
export function ndviColour(v: number): string {
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

/** Below this a change in median NDVI is worded as "about the same"; the exact value is still shown. */
const SAME = 0.03;

export function greennessWords(pre: number, post: number): { key: Key; vars?: Record<string, number> } {
  const d = post - pre;
  if (Math.abs(d) < SAME || pre <= 0) return { key: "plain.same" };
  const pct = Math.round((Math.abs(d) / pre) * 100);
  if (d > 0) return { key: "plain.rose_pct", vars: { p: pct } };
  if (pct >= 45 && pct <= 55) return { key: "plain.fell_half" };
  if (pct >= 22 && pct <= 28) return { key: "plain.fell_quarter" };
  if (pct >= 30 && pct <= 37) return { key: "plain.fell_third" };
  if (pct >= 62 && pct <= 70) return { key: "plain.fell_two_thirds" };
  if (pct >= 72 && pct <= 78) return { key: "plain.fell_three_quarters" };
  return { key: "plain.fell_pct", vars: { p: pct } };
}

/** One change value on the 0 to 1 greenness scale, in words. */
export function moveWords(v: number): { key: Key; vars?: Record<string, string> } {
  if (Math.abs(v) < 0.02) return { key: "plain.move_none" };
  const by = Math.abs(v).toFixed(2);
  return v < 0 ? { key: "plain.move_fell", vars: { v: by } } : { key: "plain.move_rose", vars: { v: by } };
}
