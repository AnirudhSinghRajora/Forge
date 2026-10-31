import { useI18n, keyLabel, type Key } from "../i18n";
import { Stamp } from "./Stamp";
import { Icon } from "./Icon";
import type { Objection } from "../types";

function value(v: unknown, notMeasured: string): React.ReactNode {
  if (v === null || v === undefined) return <span className="faint">{notMeasured}</span>;
  if (typeof v === "number") return <span className="mono">{v}</span>;
  if (typeof v === "boolean") return <span className="mono">{String(v)}</span>;
  if (typeof v === "string") return <span className="mono">{v}</span>;
  return <span className="mono small break">{JSON.stringify(v)}</span>;
}

export function ObjectionCard({ o, index, fresh }: { o: Objection; index?: number; fresh?: boolean }) {
  const { t, lang } = useI18n();
  const challenge = lang === "hi" ? o.challenge_hi : o.challenge_en;
  const finding = lang === "hi" ? o.finding_hi : o.finding_en;
  const entries = Object.entries(o.measured ?? {});
  return (
    <article className={`exchange exchange-${o.outcome} ${fresh ? "fresh" : ""}`}>
      <div className="ex-who ex-surveyor">
        <span className="ex-role"><Icon name="question" size={18} /> {t("exam.surveyor")}{index !== undefined ? ` · ${t("exam.objection")} ${index + 1}` : ""}</span>
        <p className="ex-challenge">{challenge}</p>
      </div>
      <div className="ex-test">
        <span className="ex-role"><Icon name="satellite" size={18} /> {t("exam.test")}</span>
        <p lang="en">{o.test}</p>
        {entries.length > 0 && (
          <table className="ledger ledger-tight">
            <tbody>
              {entries.map(([k, v]) => (
                <tr key={k}>
                  <th>{keyLabel(k, lang)}</th>
                  <td>{value(v, t("missing.short"))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
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
