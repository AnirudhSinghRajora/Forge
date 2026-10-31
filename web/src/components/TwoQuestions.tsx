import { useI18n, type Key } from "../i18n";
import { Icon } from "./Icon";
import { Missing } from "./Bits";
import { rawNum } from "../format";
import type { Evidence, PlaceboTest } from "../types";

/** The rubric's Bonferroni threshold across the two tests (contract, Addendum 4). */
const P_FIELD = 0.025;

type Answer = "yes" | "no" | "unmeasured";

function answerOf(test: PlaceboTest | null | undefined): Answer {
  if (!test || test.insufficient_reason || !test.n_placebos) return "unmeasured";
  return test.p_value <= P_FIELD && test.plot_value < test.placebo_median ? "yes" : "no";
}

function Card({ q, test, unmeasuredWhy }: { q: Key; test: PlaceboTest | null | undefined; unmeasuredWhy: string }) {
  const { t } = useI18n();
  const a = answerOf(test);
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
          <span className="mono faint">p = {rawNum(test!.p_value)} ({t("tq.threshold")} {P_FIELD})</span>
        </p>
      )}
    </div>
  );
}

/** Two tests, two different questions. "Far yes, ring no" is a finding about the area, not a weakness. */
export function TwoQuestions({ ev }: { ev: Evidence }) {
  const { t } = useI18n();
  const n = ev.neighbours;
  const far = answerOf(n?.far_placebo);
  const ring = answerOf(n?.placebo);
  if (far === "unmeasured" && ring === "unmeasured") {
    return (
      <section className="two-q" aria-labelledby="tq-t">
        <h3 id="tq-t" className="h-sec">{t("tq.title")}</h3>
        <Missing what={t("tq.title")} why={t("tq.both_unmeasured")} />
      </section>
    );
  }
  const finding: Key = `tq.finding_${far}_${ring}` as Key;
  const big = ev.event.type === "cyclone" || ev.event.type === "flood";
  return (
    <section className="two-q" aria-labelledby="tq-t">
      <h3 id="tq-t" className="h-sec">{t("tq.title")}</h3>
      <div className="tq-grid">
        <Card q="tq.q_far" test={n?.far_placebo} unmeasuredWhy={t("tq.far_unmeasured")} />
        <Card q="tq.q_ring" test={n?.placebo} unmeasuredWhy={t("tq.ring_unmeasured")} />
      </div>
      <p className="tq-finding">{t(finding)}</p>
      {big && <p className="small">{t("tq.big_event")}</p>}
    </section>
  );
}
