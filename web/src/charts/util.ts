import { useEffect, useRef, useState } from "react";

export function linear(d0: number, d1: number, r0: number, r1: number) {
  const span = d1 - d0 || 1;
  return (v: number) => r0 + ((v - d0) / span) * (r1 - r0);
}

export function useWidth<T extends Element>(initial = 340): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [w, setW] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.getBoundingClientRect().width || initial);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((es) => {
      const next = es[0]?.contentRect.width;
      if (next) setW(next);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [initial]);
  return [ref, w];
}

/** Evenly spaced round ticks. */
export function ticks(lo: number, hi: number, count = 4): number[] {
  const span = hi - lo;
  if (!(span > 0)) return [lo];
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 5 ? 5 : norm >= 2 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-6; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

/** Split a series into runs without nulls, so a line never bridges a gap in the data. */
export function runs<T>(items: T[], ok: (t: T) => boolean): T[][] {
  const out: T[][] = [];
  let cur: T[] = [];
  for (const it of items) {
    if (ok(it)) cur.push(it);
    else if (cur.length) { out.push(cur); cur = []; }
  }
  if (cur.length) out.push(cur);
  return out;
}

export function nearestIndex(xs: number[], x: number): number {
  let best = 0;
  let d = Infinity;
  xs.forEach((v, i) => {
    const dd = Math.abs(v - x);
    if (dd < d) { d = dd; best = i; }
  });
  return best;
}
