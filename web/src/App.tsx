import { lazy, Suspense } from "react";
import { I18nProvider, useI18n } from "./i18n";
import { HealthProvider, useHealth } from "./health";
import { useLocationPath } from "./router";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Masthead, Footer } from "./components/Masthead";
import { Icon } from "./components/Icon";
import { Loading } from "./components/Bits";
import { Start } from "./screens/Start";

const Plot = lazy(() => import("./screens/Plot"));
const Investigate = lazy(() => import("./screens/Investigate"));
const VerdictScreen = lazy(() => import("./screens/Verdict"));
const ActionScreen = lazy(() => import("./screens/Action"));
const Verify = lazy(() => import("./screens/Verify"));
const Radar = lazy(() => import("./screens/Radar"));

interface Route { name: string; el: React.ReactNode; step?: number; caseId?: string; bleed?: boolean }

function matchRoute(path: string): Route {
  const clean = path.replace(/\/+$/, "") || "/";
  if (clean === "/") return { name: "start", el: <Start />, step: 1 };
  if (clean === "/radar") return { name: "radar", el: <Radar /> };
  let m = clean.match(/^\/verify\/([^/]+)$/);
  if (m) return { name: "verify", el: <Verify hash={decodeURIComponent(m[1])} /> };
  m = clean.match(/^\/case\/([^/]+)\/plot$/);
  if (m) { const id = decodeURIComponent(m[1]); return { name: "plot", el: <Plot caseId={id} />, step: 2, caseId: id, bleed: true }; }
  m = clean.match(/^\/case\/([^/]+)\/investigate$/);
  if (m) { const id = decodeURIComponent(m[1]); return { name: "investigate", el: <Investigate caseId={id} />, step: 3, caseId: id }; }
  m = clean.match(/^\/case\/([^/]+)\/action$/);
  if (m) { const id = decodeURIComponent(m[1]); return { name: "action", el: <ActionScreen caseId={id} />, step: 5, caseId: id }; }
  m = clean.match(/^\/case\/([^/]+)$/);
  if (m) { const id = decodeURIComponent(m[1]); return { name: "verdict", el: <VerdictScreen caseId={id} />, step: 4, caseId: id }; }
  return { name: "notfound", el: <NotFound /> };
}

function NotFound() {
  const { t } = useI18n();
  return (
    <section className="page narrow">
      <h1 className="display">{t("nf.title")}</h1>
      <p className="lede">{t("nf.body")}</p>
      <a className="btn btn-primary" href="/"><Icon name="arrow" /> {t("nf.home")}</a>
    </section>
  );
}

function ConnectionBanner() {
  const { t } = useI18n();
  const { reachable, health, recheck } = useHealth();
  if (reachable === false) {
    return (
      <div className="band band-off" role="status">
        <span>{t("health.down")}</span>
        <button className="linkish" onClick={recheck}>{t("act.retry")}</button>
      </div>
    );
  }
  if (health && !health.gemini) {
    return <div className="band band-quiet" role="status">{t("health.no_ai")}</div>;
  }
  return null;
}

function Shell() {
  const { t } = useI18n();
  const { path } = useLocationPath();
  const route = matchRoute(path);
  return (
    <div className={`shell route-${route.name}`}>
      <a className="skip" href="#main">{t("a11y.skip")}</a>
      <Masthead step={route.step} caseId={route.caseId} compact={route.name !== "start"} />
      <ConnectionBanner />
      <main id="main" className={route.bleed ? "main-bleed" : "main"}>
        <ErrorBoundary resetKey={path}>
          <Suspense fallback={<div className="page narrow"><Loading what={t("loading.page")} /></div>}>
            {route.el}
          </Suspense>
        </ErrorBoundary>
      </main>
      {!route.bleed && <Footer />}
    </div>
  );
}

export function App() {
  return (
    <I18nProvider>
      <HealthProvider>
        <Shell />
      </HealthProvider>
    </I18nProvider>
  );
}
