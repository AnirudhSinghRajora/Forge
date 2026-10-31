"""The deterministic wording, as it reads today, over a stored record.

Testimony, explanation and findings are templates over evidence values and sit outside the sealed
core, so a record sealed earlier can show a corrected sentence without touching its hash. This runs on
read and changes only what is returned: the stored row, the level and every outcome stay as they are.
"""
from __future__ import annotations

import logging

from app.agent import cross_exam, explain, testimony
from app.evidence.schema import Evidence

log = logging.getLogger(__name__)


def refresh(evidence: dict) -> dict:
    """Text polished by an LLM under LLM_POLISH is left as it was written."""
    if not evidence.get("verdict") or evidence.get("llm_used"):
        return evidence
    try:
        ev = Evidence.model_validate(evidence)
        evidence["testimony_hi"], evidence["testimony_en"], evidence["testimony_te"] = testimony.templates(ev)
        evidence["explanation_hi"], evidence["explanation_en"], evidence["explanation_te"] = (
            explain.template_explanation(ev, ev.verdict.level))
        current = cross_exam.check_regional_trend(ev)
        objections = []
        for stored in evidence.get("cross_examination") or []:
            if stored.get("id") == current.id and stored.get("outcome") == current.outcome:
                stored = {**stored, "finding_hi": current.finding_hi, "finding_en": current.finding_en,
                          "finding_te": current.finding_te, "challenge_te": current.challenge_te}
            objections.append(stored)
        evidence["cross_examination"] = objections
    except Exception:  # a record it cannot read keeps the words it was stored with
        log.exception("could not refresh the wording of a stored record")
    return evidence
