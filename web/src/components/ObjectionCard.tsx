import { useI18n, type Key } from "../i18n";
import { Stamp } from "./Stamp";
import { Icon } from "./Icon";
import { splitFacts, TechnicalFacts } from "./Facts";
import type { Objection } from "../types";

export function ObjectionCard({ o, index, fresh }: { o: Objection; index?: number; fresh?: boolean }) {
  const { t, lang } = useI18n();
  const challenge = lang === "hi" ? o.challenge_hi : lang === "te" ? o.challenge_te ?? o.challenge_en : o.challenge_en;
  const finding = lang === "hi" ? o.finding_hi : lang === "te" ? o.finding_te ?? o.finding_en : o.finding_en;
  const { shown, raw } = splitFacts(Object.entries(o.measured ?? {}), lang, t, true);
  return (
    <article className={`exchange exchange-${o.outcome} ${fresh ? "fresh" : ""}`}>
      <div className="ex-who ex-surveyor">
        <span className="ex-role"><Icon name="question" size={18} /> {t("exam.surveyor")}{index !== undefined ? ` · ${t("exam.objection")} ${index + 1}` : ""}</span>
        <p className="ex-challenge">{challenge}</p>
      </div>
      <div className="ex-test">
        <span className="ex-role"><Icon name="satellite" size={18} /> {t("exam.test")}</span>
        {lang === "en" ? <p>{o.test}</p> : (
          <details className="fine">
            <summary>{t("exam.tech_def")}</summary>
            <p lang="en">{o.test}</p>
          </details>
        )}
        {shown.length > 0 && (
          <table className="ledger ledger-tight">
            <tbody>
              {shown.map((f) => (
                <tr key={f.key}>
                  <th>{f.label}</th>
                  <td className={f.missing ? "faint" : "mono"}>{f.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <TechnicalFacts raw={raw} />
      </div>
      <div className="ex-who ex-witness">
        <span className="ex-role"><Icon name="scale" size={18} /> {t("exam.witness")}</span>
        <p className="ex-finding">{finding}</p>
        <Stamp size="md" tone={o.outcome === "conceded" ? "soil" : o.outcome === "unresolved" ? "muted" : "ink"} className={fresh ? "stamp-thump" : ""}>
          {t(`outcome.${o.outcome}` as Key)}
        </Stamp>
      </div>
    </article>
  );
}
