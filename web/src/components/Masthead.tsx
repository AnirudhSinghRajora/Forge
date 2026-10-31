import { LANGS, useI18n, type Lang, type Key } from "../i18n";
import { linkProps } from "../router";
import { Icon } from "./Icon";

const LABEL: Record<Lang, string> = { hi: "हिन्दी", te: "తెలుగు", en: "English" };
const SHORT: Record<Lang, string> = { hi: "हिं", te: "తె", en: "En" };

const STEPS: { n: number; key: Key; icon: string; to: (id?: string) => string | null }[] = [
  { n: 1, key: "step.1", icon: "mic", to: () => "/" },
  { n: 2, key: "step.2", icon: "field", to: (id) => (id ? `/case/${id}/plot` : null) },
  { n: 3, key: "step.3", icon: "satellite", to: (id) => (id ? `/case/${id}/investigate` : null) },
  { n: 4, key: "step.4", icon: "scale", to: (id) => (id ? `/case/${id}` : null) },
  { n: 5, key: "step.5", icon: "doc", to: (id) => (id ? `/case/${id}/action` : null) },
];

export function LangSwitch() {
  const { lang, setLang, t } = useI18n();
  return (
    <div className="lang" role="group" aria-label={t("a11y.lang")}>
      {LANGS.map((l) => (
        <button key={l} lang={l} aria-pressed={l === lang} title={LABEL[l]} aria-label={LABEL[l]} onClick={() => setLang(l)}>
          {SHORT[l]}
        </button>
      ))}
    </div>
  );
}

export function Masthead({ step, caseId, compact }: { step?: number; caseId?: string; compact?: boolean }) {
  const { t } = useI18n();
  return (
    <header className={`mast ${compact ? "mast-compact" : ""}`}>
      <div className="mast-top">
        <a className="wordmark" {...linkProps("/")}>
          <span className="wordmark-main">{t("brand.name")}</span>
          <span className="wordmark-sub">{t("brand.tag")}</span>
        </a>
        <LangSwitch />
      </div>
      {step && (
        <nav className="steps" aria-label={t("a11y.steps")}>
          <ol>
            {STEPS.map((s) => {
              const to = s.to(caseId);
              const state = s.n === step ? "now" : s.n < step ? "past" : "next";
              const inner = (
                <>
                  <Icon name={s.icon} size={18} />
                  <span>{t(s.key)}</span>
                </>
              );
              return (
                <li key={s.n} className={`step step-${state}`} aria-current={s.n === step ? "step" : undefined}>
                  {to && state !== "next" ? <a {...linkProps(to)}>{inner}</a> : <span className="step-off">{inner}</span>}
                </li>
              );
            })}
          </ol>
        </nav>
      )}
    </header>
  );
}

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="foot">
      <p>{t("foot.promise")}</p>
      <p className="foot-links">
        <a {...linkProps("/radar")}>{t("foot.radar")}</a>
      </p>
    </footer>
  );
}
