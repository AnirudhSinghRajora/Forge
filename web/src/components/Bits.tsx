import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { useI18n } from "../i18n";
import { ApiError } from "../api";

/** A section whose data is null says exactly what is missing and why. Never a blank chart. */
export function Missing({ what, why, children }: { what: string; why?: string | null; children?: React.ReactNode }) {
  const { t } = useI18n();
  return (
    <div className="missing">
      <p className="missing-what"><strong>{t("missing.label")}</strong> {what}</p>
      <p className="missing-why">{why ?? t("missing.not_measured")}</p>
      {children}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const net = error instanceof ApiError && error.isNetwork;
  const status = error instanceof ApiError ? error.status : null;
  const server = error instanceof ApiError && status && status >= 500;
  const msg = net ? t("err.network") : server ? t("err.server") : error instanceof Error ? error.message : String(error);
  return (
    <div className="notice" role="alert">
      <p><Icon name="warn" /> {msg}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          <Icon name="retry" /> {t("act.retry")}
        </button>
      )}
    </div>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <p className="loading" role="status">
      <span className="tick" aria-hidden="true" /> {what}
    </p>
  );
}

export function Facts({ rows }: { rows: [React.ReactNode, React.ReactNode][] }) {
  return (
    <dl className="facts">
      {rows.map(([k, v], i) => (
        <div key={i}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const { t } = useI18n();
  const [done, setDone] = useState<"" | "ok" | "fail">("");
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const copy = async () => {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      // Insecure origin or a denied permission: fall back to the old selection copy.
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { ok = document.execCommand("copy"); } catch { ok = false; }
      ta.remove();
    }
    setDone(ok ? "ok" : "fail");
    timer.current = window.setTimeout(() => setDone(""), 2500);
  };
  return (
    <button className="btn" onClick={copy}>
      <Icon name={done === "ok" ? "check" : "copy"} /> {done === "ok" ? t("act.copied") : done === "fail" ? t("act.copy_failed") : label}
    </button>
  );
}

export function usePrefersReducedMotion(): boolean {
  const [r, setR] = useState(() => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  useEffect(() => {
    const m = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!m) return;
    const on = () => setR(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return r;
}

export function useNow(intervalMs = 1000, active = true): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, active]);
  return now;
}

/** Runs when an element first comes near the viewport, so heavy exhibits load on demand. */
export function useInView<T extends Element>(rootMargin = "300px"): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    if (seen || !ref.current) return;
    if (!("IntersectionObserver" in window)) {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) {
        setSeen(true);
        io.disconnect();
      }
    }, { rootMargin });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [seen, rootMargin]);
  return [ref, seen];
}
