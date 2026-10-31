import { useI18n, type Key } from "../i18n";
import { Icon } from "./Icon";
import { Missing } from "./Bits";
import { rawNum } from "../format";
import type { Evidence, PlaceboTest } from "../types";

type Answer = "yes" | "no" | "unmeasured";

function answerOf(test: PlaceboTest | null | undefined, pField: number | null): Answer {
  if (!test || test.insufficient_reason || !test.n_placebos || pField === null) return "unmeasured";
  return test.p_value <= pField && test.plot_value < test.placebo_median ? "yes" : "no";
}

type Band = { low: number; high: number } | null;

/** The API's band. Applies to a real fall only: a field that rose is not near this line. */
function isNear(test: PlaceboTest | null | undefined, band: Band): boolean {
  return !!band && !!test && test.plot_value < test.placebo_median && test.p_value >= band.low && test.p_value <= band.high;
}

function Card({ q, test, unmeasuredWhy, pField, band }: { q: Key; test: PlaceboTest | null | undefined; unmeasuredWhy: string; pField: number | null; band: Band }) {
  const { t } = useI18n();
  const a = answerOf(test, pField);
  const near = a !== "unmeasured" && isNear(test, band);
  return (
    <div className={`tq tq-${a} ${near ? "tq-near" : ""}`}>
      <p className="tq-q">{t(q)}</p>
      <p className="tq-a">
        {a === "yes" && <Icon name="check" size={26} stroke={2.2} />}
        {t((near ? `tq.${a}_near` : `tq.${a}`) as Key)}
      </p>
      {a === "unmeasured" ? (
        <p className="small">{test?.insufficient_reason ?? unmeasuredWhy}</p>
      ) : (
        <p className="small">
          {t("tq.count", { k: test!.n_at_least_as_extreme, n: test!.n_placebos })}{" "}
          <span className="mono faint">p = {rawNum(test!.p_value)} ({t("tq.threshold")} {pField})</span>
        </p>
      )}
    </div>
  );
}

/** Two tests, two different questions. "Far yes, ring no" reads "the effect does not look limited to your field", not as a weakness. */
export function TwoQuestions({ ev, pField, band, nearDecides }: { ev: Evidence; pField: number | null; band: Band; nearDecides: boolean }) {
  const { t } = useI18n();
  const n = ev.neighbours;
  const far = answerOf(n?.far_placebo, pField);
  const ring = answerOf(n?.placebo, pField);
  if (far === "unmeasured" && ring === "unmeasured") {
    return (
      <section className="two-q" aria-labelledby="tq-t">
        <h3 id="tq-t" className="h-sec">{t("tq.title")}</h3>
        <Missing what={t("tq.title")} why={t(pField === null ? "tq.no_threshold" : "tq.both_unmeasured")} />
      </section>
    );
  }
  const finding: Key = `tq.finding_${far}_${ring}` as Key;
  const big = ev.event.type === "cyclone" || ev.event.type === "flood";
  return (
    <section className="two-q" aria-labelledby="tq-t">
      <h3 id="tq-t" className="h-sec">{t("tq.title")}</h3>
      <div className="tq-grid">
        <Card q="tq.q_far" test={n?.far_placebo} unmeasuredWhy={t("tq.far_unmeasured")} pField={pField} band={band} />
        <Card q="tq.q_ring" test={n?.placebo} unmeasuredWhy={t("tq.ring_unmeasured")} pField={pField} band={band} />
      </div>
      <p className="tq-finding">{t(finding)}</p>
      {nearDecides && <p className="tq-near-note">{t("tq.near_note")}</p>}
      {big && <p className="small">{t("tq.big_event")}</p>}
    </section>
  );
}
