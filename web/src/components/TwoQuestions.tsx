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

function Card({ q, test, unmeasuredWhy, pField }: { q: Key; test: PlaceboTest | null | undefined; unmeasuredWhy: string; pField: number | null }) {
  const { t } = useI18n();
  const a = answerOf(test, pField);
  return (
    <div className={`tq tq-${a}`}>
      <p className="tq-q">{t(q)}</p>
      <p className="tq-a">
        {a === "yes" && <Icon name="check" size={26} stroke={2.2} />}
        {t(`tq.${a}` as Key)}
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
export function TwoQuestions({ ev, pField }: { ev: Evidence; pField: number | null }) {
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
        <Card q="tq.q_far" test={n?.far_placebo} unmeasuredWhy={t("tq.far_unmeasured")} pField={pField} />
        <Card q="tq.q_ring" test={n?.placebo} unmeasuredWhy={t("tq.ring_unmeasured")} pField={pField} />
      </div>
      <p className="tq-finding">{t(finding)}</p>
      {big && <p className="small">{t("tq.big_event")}</p>}
    </section>
  );
}
