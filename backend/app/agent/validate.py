"""Number and claim validator for all LLM text (contract non-negotiables 3 and 4).

Every digit sequence in LLM text has to correspond to a number in the evidence, allowing for
rounding and for fractions written as percentages. Devanagari and Telugu digits are normalised
first. Anything else is rejected, and the caller falls back to the deterministic template.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_DIGIT_MAP = str.maketrans("०१२३४५६७८९౦౧౨౩౪౫౬౭౮౯", "01234567890123456789")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
# Product names that contain digits but carry no measurement.
_NAMES = re.compile(r"(?i)sentinel[\s-]*[12]|सेंटिनल[\s-]*[12]|సెంటినెల్[\s-]*[12]|\bs[12]\b")

# Fields whose digits are identifiers or plumbing, not facts a sentence may quote.
_SKIP_KEYS = {
    "evidence_hash", "histogram_edges", "histogram_counts", "seed", "geometry", "polygon", "replay",
    "provenance", "url", "id", "scene_id", "pre_scene_id", "post_scene_id", "path", "bounds",
    "chips", "clause_id", "identifier", "run_id", "case_id",
}

# Rupee or payout talk and promises. No evidence field ever supports these.
_BANNED = re.compile(
    r"(?i)₹|\brs\.?\s*\d|\brupees?\b|\blakh\b|\bcrore\b|लाख|करोड़|रुपय|रुपये|రూపాయ|లక్ష|కోటి"
    r"|you will (?:get|receive|be paid)|will be paid|(?<!not )(?<!no )guarantee|मुआवज़ा मिलेगा|मुआवजा मिलेगा"
    r"|पैसा मिलेगा|क्लेम मिलेगा|పరిహారం వస్తుంది|డబ్బు వస్తుంది"
    # do_not_say entries from key_rules.json
    r"|late means reject|will be rejected|claim is lost|must accept|has to accept|\bCSC\b"
    r"|everyone gets paid|no longer need to intimate|रद्द हो जाएगा|ख़ारिज हो जाएगा|खारिज हो जाएगा"
    r"|मानना ही होगा|తిరస్కరిస్తారు"
    r"|\blottery\b|लॉटरी|లాటరీ|unfair|अनुचित"
    r"|paddy inundation is covered|can'?t contest|cannot contest"
    # No AP insurer is verified, so LLM text may name no insurer at all.
    r"|agriculture insurance company|\bAIC\b|icici lombard|bajaj allianz|hdfc ergo|reliance general"
    r"|sbi general|universal sompo|future generali|chola ?ms|tata aig|kshema|iffco.tokio"
    r"|oriental insurance|united india|national insurance|new india assurance"
)


@dataclass
class ValidationResult:
    ok: bool
    bad_tokens: list[str] = field(default_factory=list)
    banned: list[str] = field(default_factory=list)

    def reason(self) -> str:
        parts = []
        if self.bad_tokens:
            parts.append(f"numbers not in evidence: {', '.join(self.bad_tokens)}")
        if self.banned:
            parts.append(f"forbidden claim: {', '.join(self.banned)}")
        return "; ".join(parts) or "ok"


def normalize_digits(text: str) -> str:
    return text.translate(_DIGIT_MAP)


def collect_numbers(value, *, _key: str | None = None) -> set[float]:
    """Walks evidence-shaped data and returns every number a sentence may legitimately quote."""
    found: set[float] = set()
    if _key in _SKIP_KEYS:
        return found
    if isinstance(value, bool) or value is None:
        return found
    if isinstance(value, int | float):
        found.add(abs(float(value)))
    elif isinstance(value, str):
        if m := _ISO_DATE.match(value):
            found.update(float(g) for g in m.groups())
    elif isinstance(value, dict):
        for key, item in value.items():
            found |= collect_numbers(item, _key=key)
    elif isinstance(value, list | tuple | set):
        for item in value:
            found |= collect_numbers(item, _key=_key)
    return found


def _matches(token: str, allowed: Iterable[float]) -> bool:
    cleaned = token.replace(",", "")
    decimals = len(cleaned.split(".")[1]) if "." in cleaned else 0
    target = float(cleaned)
    for base in allowed:
        for value in (base, base * 100) if base <= 1 else (base,):
            if decimals == 0 and value != int(value) and value < 1.5:
                continue  # 0.7 must not license a bare "1"
            if abs(round(value, decimals) - target) < 1e-9:
                return True
    return False


def validate_text(text: str, allowed: Iterable[float]) -> ValidationResult:
    normalized = _NAMES.sub(" ", normalize_digits(text))
    allowed = set(allowed)
    bad = [t for t in _NUMBER.findall(normalized) if not _matches(t, allowed)]
    banned = sorted({m.group(0) for m in _BANNED.finditer(normalized)})
    return ValidationResult(ok=not bad and not banned, bad_tokens=bad, banned=banned)
