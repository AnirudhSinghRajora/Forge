"""Ask the witness: a farmer's question about their own result, answered from that case's record.

Gemini reads the record and the retrieved clauses and answers in the asked language. Its answer is
shown only if it cites what it used and passes the digit check and the phrase denylist. Anything else
falls back to the deterministic text, or to a refusal. Nothing here writes to the evidence.
"""
from __future__ import annotations

import logging
import re

from app.agent import llm, rubric, validate
from app.evidence.schema import Evidence
from app.tools import policy

log = logging.getLogger(__name__)

WITNESS_S = 30
MAX_ANSWER_CHARS = 1500
MAX_CLAUSES = 6

REFUSAL = {
    "hi": "मेरे रिकॉर्ड और दिशानिर्देशों में इसका जवाब नहीं है, इसलिए मैं अंदाज़ा नहीं लगाऊँगा।",
    "en": "My record and the guidelines do not answer that, so I will not guess.",
    # NEEDS NATIVE REVIEW
    "te": "నా రికార్డులో, మార్గదర్శకాల్లో దీనికి సమాధానం లేదు, కాబట్టి నేను ఊహించి చెప్పను.",
}
# Questions the record itself can answer with no model at all.
_ABOUT_RESULT = re.compile(
    r"(?i)\bweak\b|\bstrong\b|\bmoderate\b|\bmy (?:result|verdict|finding)\b|\bthis (?:result|verdict)\b"
    r"|\bkamzor\b|\bkamjor\b|\bnat[ie]+ja\b"
    r"|कमज़ोर|कमजोर|नतीजा|नतीजे|निष्कर्ष|బలహీన|ఫలితం"
)
_NEXT_STEP = re.compile(
    r"(?i)what (?:should|do|can|must) i do|what(?:'s| is)? next|next step|\bab kya\b|kya kar(?:u|oon|na)\b"
    r"|अब क्या|आगे क्या|क्या करूँ|क्या करूं|क्या करना|ఏం చేయాలి|ఏమి చేయాలి|ఇప్పుడు ఏం|తర్వాత ఏం"
)
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_TELUGU = re.compile(r"[ఀ-౿]")
# The fields behind the deterministic explanation.
_EXPLANATION_FIELDS = ("verdict.level", "verdict.reasons", "verdict.caveats", "optical.plot_delta_ndvi",
                       "weather.corroborated", "corroboration.sources")


def asked_language(question: str, lang: str) -> str:
    """The script the question is written in decides, and Latin letters leave the app's language."""
    if _TELUGU.search(question):
        return "te"
    if _DEVANAGARI.search(question):
        return "hi"
    return lang if lang in REFUSAL else "en"


def _in_script(text: str, lang: str) -> bool:
    if lang == "hi":
        return _DEVANAGARI.search(text) is not None
    if lang == "te":
        return _TELUGU.search(text) is not None
    return True


def _test_facts(prefix: str, test) -> dict:
    if test is None or test.insufficient_reason:
        return {}
    return {f"{prefix}.p_value": test.p_value, f"{prefix}.n_placebos": test.n_placebos,
            f"{prefix}.n_at_least_as_extreme": test.n_at_least_as_extreme}


def evidence_facts(ev: Evidence) -> dict:
    """The record as the model may see it, under the field names it has to cite. Allow-listed, so ids,
    locations and anything else a sentence has no business quoting stay out."""
    o, n, h, s, w = ev.optical, ev.neighbours, ev.history, ev.sar, ev.weather
    facts = {
        "event.type": ev.event.type, "event.date": ev.event.date.isoformat(),
        "event.date_source": ev.event.date_source, "event.crop": ev.event.crop,
        "plot.area_ha": ev.plot.area_ha,
        "optical.plot_delta_ndvi": o.plot_delta_ndvi, "optical.drop_frac": o.drop_frac,
        "optical.post_bare_fraction": o.post_bare_fraction, "optical.within_plot_pattern": o.within_plot_pattern,
        "corroboration.sources": rubric.corroboration(ev),
        "alerts.matching_this_hazard": len(rubric.matching_alerts(ev)),
    }
    if ev.verdict is not None:
        facts["verdict.level"] = ev.verdict.level
        facts["verdict.reasons"] = ev.verdict.reasons
        facts["verdict.caveats"] = ev.verdict.caveats
        facts["verdict.near_threshold_could_change_it"] = rubric.level_could_change(ev, ev.verdict.level)
    for name, stats in (("pre", o.pre), ("post", o.post)):
        if stats is not None:
            facts[f"optical.{name}.date"] = stats.date.isoformat()
            facts[f"optical.{name}.ndvi_median"] = stats.ndvi_median
    if n is not None:
        facts.update({
            "neighbours.neighbour_median_delta": n.neighbour_median_delta,
            "neighbours.plot_minus_neighbour": n.plot_minus_neighbour,
            "neighbours.pretrend_delta": n.pretrend_delta,
            "neighbours.counterfactual.gap_at_post": n.counterfactual.gap_at_post if n.counterfactual else None,
            **_test_facts("neighbours.placebo", n.placebo), **_test_facts("neighbours.far_placebo", n.far_placebo),
        })
    if h is not None:
        facts.update({"history.typical_delta": h.typical_delta, "history.excess_vs_history": h.excess_vs_history,
                      "history.downweighted": h.downweighted})
    if s is not None:
        facts.update({"sar.usable": s.usable, "sar.vh_change_db": s.vh_change_db, "sar.new_water_frac": s.new_water_frac,
                      "sar.pre_date": s.pre_date.isoformat() if s.pre_date else None,
                      "sar.post_date": s.post_date.isoformat() if s.post_date else None,
                      **_test_facts("sar.placebo", s.placebo)})
    if w is not None:
        facts.update({"weather.corroborated": w.corroborated, "weather.max_daily_mm": w.max_daily_mm,
                      "weather.precip_mm_event_window": w.precip_mm_event_window,
                      "weather.hail_code_hours": w.hail_code_hours, "weather.max_gust_kmh": w.max_gust_kmh,
                      "weather.proposed_event_date": w.proposed_event_date.isoformat() if w.proposed_event_date else None})
    for objection in ev.cross_examination:
        facts[f"objection.{objection.id}.outcome"] = objection.outcome
        facts[f"objection.{objection.id}.finding"] = objection.finding_en
    if ev.claim_path is not None:
        facts.update({"claim_path.route": ev.claim_path.route, "claim_path.insured": ev.claim_path.insured,
                      "claim_path.crop_stage": ev.claim_path.crop_stage, "claim_path.intimation": ev.claim_path.intimation,
                      "claim_path.next_steps": ev.claim_path.next_steps, "claim_path.evidence_use": ev.claim_path.evidence_use,
                      "claim_path.unknowns": ev.claim_path.unknowns})
    for deadline in ev.deadlines:
        facts[f"deadline.{deadline.type}.status"] = deadline.status
    if ev.village is not None:
        facts["village.affected_share"] = ev.village.affected_share
        draw = ev.village.lottery
        if draw is not None and not draw.insufficient_reason:
            facts.update({"village.ten_field_draw.average_median": draw.average_median,
                          "village.ten_field_draw.average_p05": draw.average_p05,
                          "village.ten_field_draw.average_p95": draw.average_p95})
    return {k: v for k, v in facts.items() if v is not None and v != []}


def allowed_numbers(facts: dict, clause_texts: list[str] = ()) -> set[float]:
    """Numbers in the record's values, and those inside its own sentences, which code wrote."""
    allowed = validate.collect_numbers(facts)

    def from_text(value) -> None:
        if isinstance(value, str):
            allowed.update(llm._digits_in(value))
        elif isinstance(value, list):
            for item in value:
                from_text(item)

    for value in facts.values():
        from_text(value)
    for text in clause_texts:
        allowed.update(llm._digits_in(text))
    return allowed


def _clauses(question: str, ev: Evidence) -> dict[str, dict]:
    """Clauses on this case's own route first, then the ones retrieved for this question."""
    found: dict[str, dict] = {}
    for clause in ev.policy:
        found.setdefault(clause.clause_id, {"clause_id": clause.clause_id, "doc": clause.doc, "page": clause.page,
                                            "text": clause.text[:policy.MAX_CLAUSE_CHARS], "url": clause.url})
    for row in policy.retrieve(question):
        found.setdefault(str(row["clause_id"]), policy._citation(row))
    return dict(list(found.items())[-MAX_CLAUSES:] if len(found) > MAX_CLAUSES else found.items())


def accepted(raw, facts: dict, clauses: dict[str, dict], lang: str) -> dict | None:
    """The answer as a reader may see it, or None. Every check fails closed."""
    answer = (raw.answer or "").strip()
    if not raw.covered or not answer or len(answer) > MAX_ANSWER_CHARS or not _in_script(answer, lang):
        return None
    fields = [f for f in dict.fromkeys(raw.cited_fields) if f in facts]
    cited = [clauses[c] for c in dict.fromkeys(raw.cited_clause_ids) if c in clauses]
    if not fields and not cited:
        return None  # an answer that cannot say what it rests on is not shown
    result = validate.validate_text(answer, allowed_numbers(facts, [c["text"] for c in cited]))
    if not result.ok:
        log.warning("witness answer rejected by the validator: %s", result.reason())
        return None
    return {"answer": answer, "citations": cited, "evidence_fields": fields, "covered": True,
            "llm_used": True, "mode": "witness", "lang": lang}


def _deterministic(ev: Evidence, question: str, lang: str, next_steps: dict | None) -> dict | None:
    """Without a model, the two questions the record already answers, in its own fixed words."""
    if policy.rule_intent(question) is not None:
        return None  # a question about a rule goes to the rule
    base = {"citations": [], "covered": True, "llm_used": False, "mode": "record", "lang": lang}
    if _NEXT_STEP.search(question):
        steps = ((next_steps or {}).get(lang) or {}).get("next_steps") or []
        if steps:
            return {**base, "answer": " ".join(steps), "evidence_fields": ["claim_path.next_steps"]}
    elif _ABOUT_RESULT.search(question):
        text = getattr(ev, f"explanation_{lang}", None)
        if text:
            return {**base, "answer": text,
                    "evidence_fields": [f for f in _EXPLANATION_FIELDS if f in evidence_facts(ev)]}
    return None


def _refusal(lang: str) -> dict:
    return {"answer": REFUSAL[lang], "citations": [], "evidence_fields": [], "covered": False,
            "llm_used": False, "mode": "refused", "lang": lang}


def _policy_answer(question: str, lang: str) -> dict:
    return {"evidence_fields": [], "mode": "policy", "lang": lang, "llm_used": False,
            **policy.ask(question, lang)}


def ask(question: str, lang: str, ev: Evidence | None, next_steps: dict | None = None) -> dict:
    lang = asked_language(question, lang)
    if ev is None or ev.verdict is None or not question.strip():
        return _policy_answer(question, lang)
    if policy.conflicted(question):  # official statements differ, and only fixed text may say so
        return _policy_answer(question, lang)
    if llm.available():
        facts = evidence_facts(ev)
        clauses = _clauses(question, ev)
        raw = llm.bounded(WITNESS_S, llm.answer_from_record, question, facts, list(clauses.values()), lang)
        shown = accepted(raw, facts, clauses, lang) if raw is not None else None
        if shown is not None:
            return shown
        if raw is not None and not raw.covered:
            answer = _policy_answer(question, lang)
            return answer if answer.get("covered") else _refusal(lang)
    fixed = _deterministic(ev, question, lang, next_steps)
    if fixed is not None:
        return fixed
    answer = _policy_answer(question, lang)
    return answer if answer.get("covered") or answer.get("reason") else _refusal(lang)
