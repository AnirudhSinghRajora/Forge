"""Policy retrieval over the PMFBY clause corpus: BM25 plus optional Gemini embeddings.

`ask` refuses unless a clause was actually retrieved. With no corpus it says so rather than
answering from memory. Without a key it quotes the retrieved clause instead of paraphrasing it.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.agent import llm, validate
from app.config import get_settings
from app.db import PolicyEmbedding, session_scope
from app.evidence.schema import PolicyClause
from app.tools.actions import load_key_rules

log = logging.getLogger(__name__)
UNAVAILABLE = "policy corpus unavailable"
MIN_COVERAGE = 0.5
MIN_RULE_COVERAGE = 0.5
STRICT_COVERAGE = 0.75
RRF_K = 60
MAX_CLAUSE_CHARS = 1400
MAX_QUESTION_CHARS = 500  # applied before any regex

_STOP = {"a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does", "for", "from", "has", "have", "how", "i", "if", "in", "is", "it", "me", "my", "of", "on", "or", "our", "so", "that", "the", "their", "them", "there", "this", "to", "was", "we", "what", "when", "where", "which", "who", "why", "will", "with", "you", "your", "not", "no", "should", "would", "could", "about", "after", "before", "get", "got", "any", "all"}
# Hindi and Telugu terms, and Hinglish spellings, mapped to the corpus's English vocabulary.
_GLOSSARY = {
    "ओला": "hail hailstorm", "ओले": "hail hailstorm", "ओलावृष्टि": "hailstorm hail",
    "बीमा": "insurance insured", "फसल": "crop", "फ़सल": "crop", "नुकसान": "loss damage",
    "कटाई": "harvest harvesting", "कवर": "covered coverage cover", "बाढ़": "inundation flood",
    "जलभराव": "inundation waterlogging", "बारिश": "unseasonal rains rainfall",
    "सूचना": "intimation inform", "report": "intimation intimate report",
    "reporting": "intimation intimate reporting", "inform": "intimation inform", "समय": "time", "सीमा": "period limit", "घंटे": "hours",
    "दावा": "claim", "क्लेम": "claim", "प्रीमियम": "premium", "शिकायत": "grievance complaint",
    "सर्वे": "survey", "किसान": "farmer", "भुगतान": "payment", "चक्रवात": "cyclone cyclonic",
    "तूफान": "cyclone storm", "कीट": "pest", "सूखा": "drought", "पंजीकरण": "enrolment",
    "देर": "delay late", "बाद": "post after", "ऋण": "loan loanee", "कर्ज": "loan loanee",
    "వడగళ్ల": "hail hailstorm", "బీమా": "insurance", "పంట": "crop", "నష్టం": "loss damage",
    "కోత": "harvest harvesting", "తుఫాను": "cyclone cyclonic", "వరద": "inundation flood",
    "సమాచారం": "intimation", "క్లెయిమ్": "claim", "ప్రీమియం": "premium", "రైతు": "farmer",
    "గంటలు": "hours", "ఫిర్యాదు": "grievance complaint", "వర్షం": "rains rainfall",
    "contest": "grievance dispute", "dispute": "dispute grievance", "challenge": "dispute grievance",
    "disagree": "dispute grievance", "complain": "grievance", "complaint": "grievance",
    "appeal": "appeal grievance", "असहमत": "dispute grievance", "चुनौती": "dispute grievance",
    "fasal": "crop", "bima": "insurance", "nuksan": "loss damage", "katai": "harvest",
    "ola": "hail", "ole": "hail", "dava": "claim", "suchna": "intimation",
}
# A question has to touch crop insurance at all before it can be answered from this corpus.
_DOMAIN = re.compile(
    r"(?i)insur|pmfby|fasal|bima|crop|claim|premium|loss|damage|harvest|hail|inundat|flood|cyclon|"
    r"\breport|helpline|14447|contest|dispute|complain|appeal|25\s*(?:percent|per cent|%)|सर्वे|असहमत|"
    r"rain|drought|pest|intimat|survey|farmer|kisan|grievance|cut.?off|sum insured|loan|kcc|"
    r"notified|enrol|yes-tech|cce|deadline|72"
    r"|बीमा|फसल|फ़सल|नुकसान|कटाई|ओल|दावा|क्लेम|प्रीमियम|किसान|सूचना|शिकायत|बाढ़|बारिश|सूखा|तूफान|चक्रवात|कीट"
    r"|బీమా|పంట|నష్టం|రైతు|క్లెయిమ్|ప్రీమియం|తుఫాను|వరద|వర్షం|కోత"
)
NOT_COVERED = {
    "hi": "यह बात मेरे पास मौजूद दस्तावेज़ों में नहीं है।",
    "en": "This is not covered by the documents I have.",
    "te": "ఈ విషయం నా దగ్గర ఉన్న పత్రాల్లో లేదు.",
}
CORPUS_MISSING = {
    "hi": "नीति के दस्तावेज़ अभी उपलब्ध नहीं हैं, इसलिए मैं इसका जवाब नहीं दे सकता।",
    "en": "The policy documents are not available right now, so I cannot answer this.",
    "te": "విధాన పత్రాలు ప్రస్తుతం అందుబాటులో లేవు, కాబట్టి నేను సమాధానం చెప్పలేను.",
}
# Rule statements are our summaries of the cited clauses, so they are not introduced as quotes.
SUMMARY_INTRO = {
    "hi": "दिशानिर्देशों का हमारा सार, अंग्रेज़ी में (मूल धाराएँ नीचे हैं):",
    "en": "Our summary of the guidelines (the clauses are cited below):",
    "te": "మార్గదర్శకాల మా సారాంశం, ఆంగ్లంలో (మూల నిబంధనలు కింద ఉన్నాయి):",
}
QUOTE_INTRO = {
    "hi": "दिशानिर्देशों में यह लिखा है (अंग्रेज़ी में मूल पाठ):",
    "en": "The guidelines say:",
    "te": "మార్గదర్శకాల్లో ఇలా ఉంది (ఆంగ్లంలో మూల పాఠం):",
}


_HI_STOP = {"क्या", "है", "हैं", "में", "पर", "से", "को", "का", "की", "के", "और", "या", "तो", "यह", "वह", "कि", "कितने", "कितनी", "कितना", "कैसे", "कब", "कहाँ", "कौन", "मेरा", "मेरी", "मेरे", "मुझे", "हम", "हमें", "होता", "होती", "होते", "हो", "गया", "गई", "गए", "गिरने", "देनी", "देना", "करना", "करें", "चाहिए", "मिलता", "मिलती", "मिलेगा", "लिए", "बाद"}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[\wऀ-ॿఀ-౿]+", text.lower()) if t not in _STOP and t not in _HI_STOP]


def expand(tokens: list[str]) -> list[str]:
    out = []
    for token in tokens:
        mapped = _GLOSSARY.get(token)
        out.extend(mapped.split() if mapped else [token])
    return out


# Two whole-table records have interleaved columns; the split row records replace them. The PIB FAQ
# predates OG 2023 and has no 72-hour text, so key_rules.json says not to cite it for deadlines.
_INTERLEAVED_TABLES = {"21.5.10", "21.6.11"}


def _citable(row: dict) -> bool:
    if str(row.get("clause_id")) in _INTERLEAVED_TABLES:
        return False
    return not str(row.get("doc", "")).startswith("PIB Research Unit FAQ")


@dataclass
class Corpus:
    clauses: list[dict]
    bm25: BM25Okapi
    vocabulary: set[str]
    path_mtime: float


_corpus: Corpus | None = None
_lock = threading.Lock()


def load_corpus() -> Corpus | None:
    global _corpus
    path = get_settings().policy_dir / "clauses.jsonl"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    with _lock:
        if _corpus is not None and _corpus.path_mtime == mtime:
            return _corpus
        clauses = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("clause_id") and row.get("text") and _citable(row):
                    clauses.append(row)
        if not clauses:
            return None
        tokens = [tokenize(f"{c.get('section_title', '')} {c['text']}") for c in clauses]
        _corpus = Corpus(clauses, BM25Okapi(tokens), {t for row in tokens for t in row}, mtime)
        return _corpus


def _embedding_ranks(corpus: Corpus, query: str, candidates: list[int]) -> dict[int, int] | None:
    """Cosine rank over BM25's candidates. Vectors are cached in the DB by model and clause text."""
    if not llm.available():
        return None
    model = get_settings().gemini_model_embed
    keys = {}
    for idx in candidates:
        clause = corpus.clauses[idx]
        digest = hashlib.sha256(clause["text"].encode()).hexdigest()[:24]
        keys[idx] = f"{model}:{digest}"
    with session_scope() as s:
        vectors = {
            idx: row.vector for idx in candidates
            if (row := s.get(PolicyEmbedding, keys[idx])) is not None
        }
    missing = [i for i in candidates if i not in vectors]
    if missing:
        fresh = llm.embed(
            [corpus.clauses[i]["text"][:6000] for i in missing], is_query=False,
            titles=[corpus.clauses[i].get("section_title", "") for i in missing],
        )
        if fresh is None:
            return None
        with session_scope() as s:
            for idx, vector in zip(missing, fresh, strict=True):
                vectors[idx] = list(vector)
                s.merge(PolicyEmbedding(key=keys[idx], vector=list(vector)))
    query_vec = llm.embed([query], is_query=True)
    if not query_vec:
        return None

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
        return dot / norm if norm else 0.0

    scored = sorted(candidates, key=lambda i: cosine(query_vec[0], vectors[i]), reverse=True)
    return {idx: rank for rank, idx in enumerate(scored)}


def retrieve(query: str, k: int = 4) -> list[dict]:
    """Clauses for a query, best first. Empty when the corpus doesn't actually speak to it."""
    corpus = load_corpus()
    if corpus is None:
        return []
    tokens = expand(tokenize(query))
    if not tokens:
        return []
    scores = corpus.bm25.get_scores(tokens)
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    pool = [i for i in order[:30] if scores[i] > 0]
    if not pool:
        return []
    bm25_rank = {idx: rank for rank, idx in enumerate(pool)}
    embed_rank = llm.bounded(12, _embedding_ranks, corpus, query, pool) if llm.available() else None
    if embed_rank:
        fused = {
            i: 1 / (RRF_K + bm25_rank[i]) + 1 / (RRF_K + embed_rank.get(i, len(pool)))
            for i in pool
        }
        pool = sorted(pool, key=lambda i: fused[i], reverse=True)
    return [corpus.clauses[i] for i in pool[:k]]


def _question_terms(question: str) -> list[list[str]]:
    """One group per word in the question; a glossary word counts if any translation appears.
    Hindi and Telugu words outside the glossary are dropped, since the corpus is in English."""
    groups = []
    for token in tokenize(question):
        if token in _GLOSSARY:
            groups.append(_GLOSSARY[token].split())
        elif token.isascii():
            groups.append([token])
    return groups


def _coverage(question: str, text: str) -> float:
    groups = _question_terms(question)
    if not groups:
        return 0.0
    words = set(tokenize(text))
    return sum(1 for g in groups if any(t in words for t in g)) / len(groups)


def _clause_by_id(clause_id: str) -> dict | None:
    corpus = load_corpus()
    if corpus is None:
        return None
    return next((c for c in corpus.clauses if str(c["clause_id"]) == clause_id), None)


_REPORTING = (r"report|intimat|inform|tell|notify|सूचना|सूचित|बताना|बताएँ|बताऊँ|रिपोर्ट|"
              r"సమాచారం|తెలియజేయ|నివేదించ")
_LATE = r"late|delay|missed|देर|विलंब|ఆలస్యం"
_PERIL_WORDS = (r"hail|rain|flood|cyclone|storm|drought|pest|landslide|peril|ओल|बारिश|बाढ़|तूफान|चक्रवात|सूखा|కీట|"
                r"వడగళ్ల|వర్షం|వరద|తుఫాను")
_COVER_WORDS = r"cover|insured|include|कवर|शामिल|కవర్"


def _word(pattern: str):
    compiled = re.compile(f"(?i){pattern}")
    return lambda question: compiled.search(question) is not None


def _in_order(*patterns: str):
    """Each pattern somewhere after the last. The same meaning as joining them with .*, in linear
    time: the earliest match of each is the best start for the next, so nothing is ever retried."""
    compiled = [re.compile(f"(?i){p}") for p in patterns]

    def check(question: str) -> bool:
        position = 0
        for pattern in compiled:
            found = pattern.search(question, position)
            if found is None:
                return False
            position = found.end()
        return True

    return check


def _either(*checks):
    return lambda question: any(check(question) for check in checks)


# Farmers ask in their own words, which rarely share vocabulary with a rule, so common intents route
# directly. Checked in order: the first match wins, so "report late" reaches late_intimation.
_INTENTS = [
    ("late_intimation", _either(
        _in_order(rf"{_LATE}|after the deadline", rf"{_REPORTING}|claim|दावा|క్లెయిమ్"),
        _in_order(_REPORTING, _LATE))),
    ("after_removal_from_field", _word(
        r"\bstored\b|\bstorage\b|godown|granary|removed from the field|taken (off|from) the field|"
        r"खेत से (हट|उठा)|गोदाम|रखी (हुई|गई)|నిల్వ")),
    ("post_harvest_14_day", _word(r"post.?harvest|after harvest|cut.and.spread|कटाई के बाद|కోత తర్వాత")),
    ("intimation_deadline", _either(
        _word(r"how long|how many (hours|days)|how much time|by when|time limit|deadline|last date|"
              r"कितने (घंटे|दिन)|कितना समय|कब तक|समय सीमा|ఎన్ని గంటల|ఎన్ని రోజుల|ఎప్పటి లోపు|గడువు"),
        _in_order(r"when|कब|ఎప్పుడు", _REPORTING))),
    ("intimation_contents", _in_order(
        r"what|which|क्या|कौन|ఏ", r"detail|information|document|जानकारी|दस्तावेज़|వివరాలు|పత్రాలు",
        rf"{_REPORTING}|intimation|claim")),
    ("channels", _either(
        _in_order(r"how|where|whom|who|helpline|phone|number|कैसे|कहाँ|किसे|किसको|हेल्पलाइन|ఎలా|ఎక్కడ|ఎవరికి", _REPORTING),
        _in_order(_REPORTING, r"how|where|whom|कैसे|कहाँ|किसे|किसको|ఎలా|ఎక్కడ|ఎవరికి"),
        _word(r"helpline|हेल्पलाइन|14447"))),
    ("grievance", _word(r"grievance|complain|contest|dispute|appeal|reject|शिकायत|असहमत|ఫిర్యాదు")),
    ("perils", _either(_in_order(_COVER_WORDS, _PERIL_WORDS), _in_order(_PERIL_WORDS, _COVER_WORDS))),
]


def rule_intent(question: str) -> str | None:
    """The verified rule this question asks about by name or intent, if any."""
    routed = _intent_rule(question, (load_key_rules() or {}).get("rules") or {})
    return routed[0] if routed else None


def conflicted(question: str) -> bool:
    """Official statements differ on paddy inundation, so only fixed text may answer this."""
    return bool(_PADDY.search(question) and _INUNDATION.search(question))


def _intent_rule(question: str, rules: dict) -> tuple[str, dict] | None:
    for name, matches in _INTENTS:
        rule = rules.get(name)
        if rule and str(rule.get("status", "")).startswith("verified") and matches(question):
            return name, rule
    return None


def _key_rule_hit(question: str) -> tuple[str, dict] | None:
    """A verified rule summary from key_rules.json that speaks to the question, if any."""
    rules = (load_key_rules() or {}).get("rules") or {}
    routed = _intent_rule(question, rules)
    if routed:
        return routed
    best, best_score = None, 0.0
    for name, rule in rules.items():
        statement = rule.get("statement")
        if not statement or not str(rule.get("status", "")).startswith("verified"):
            continue
        title = name.replace("_", " ")
        score = _coverage(question, f"{title} {statement}")
        ranked = score + 0.5 * _coverage(question, title)  # a rule named for the topic beats a mention
        if score >= MIN_RULE_COVERAGE and ranked > best_score:
            best, best_score = (name, rule), ranked
    return best


def to_clause(row: dict, applies_because: str | None = None) -> PolicyClause:
    return PolicyClause(
        clause_id=str(row["clause_id"]), doc=row.get("doc") or "PMFBY document",
        page=row.get("page"), text=row["text"][:MAX_CLAUSE_CHARS],
        applies_because=applies_because, url=row.get("url"),
    )


def _citation(row: dict) -> dict:
    return {"clause_id": str(row["clause_id"]), "doc": row.get("doc"), "page": row.get("page"),
            "text": row["text"][:MAX_CLAUSE_CHARS], "url": row.get("url")}


_PADDY = re.compile(r"(?i)paddy|\brice\b|\bdhan\b|धान|వరి")
_INUNDATION = re.compile(r"(?i)inundat|flood|waterlog|बाढ़|जलभराव|వరద|ముంపు")
PADDY_INUNDATION = {
    "hi": "धान में जलभराव के कवर पर सरकारी बयान आपस में मेल नहीं खाते, इसलिए मैं यह नहीं कह सकता कि यह कवर है। अपने बैंक या 14447 से पुष्टि करें।",
    "en": "Official statements conflict on paddy inundation cover, so I cannot say it is covered. Please confirm with your bank or 14447.",
    "te": "వరి ముంపు కవర్‌పై అధికారిక ప్రకటనలు ఒకదానికొకటి సరిపోలడం లేదు, కాబట్టి కవర్ అవుతుందని చెప్పలేను. మీ బ్యాంకు లేదా 14447 ద్వారా నిర్ధారించుకోండి.",
}
# Said with any answer drawing on 21.5.9.4, which must never read as a selling point.
TECHNOLOGY_NOTE = {
    "hi": "ध्यान दें: 70/30 का भार विवाद में राज्य समिति चलाती है; किसान का PDF इसे शुरू नहीं करता, और नतीजा किसान पर भी बाध्यकारी होता है।",
    "en": "Note: the 70/30 weighting is run by the State committee in a dispute; a farmer's PDF does not trigger it, and the result binds the farmer too.",
    "te": "గమనిక: 70/30 వెయిటేజీని వివాదంలో రాష్ట్ర కమిటీ అమలు చేస్తుంది; రైతు PDF దాన్ని ప్రారంభించదు, ఫలితం రైతుకూ వర్తిస్తుంది.",
}


def _unverified_citations(item: str) -> list[dict]:
    entries = (load_key_rules() or {}).get("unverified") or []
    found = next((e for e in entries if e.get("item") == item), {})
    rows = [_clause_by_id(str(c.get("clause_id"))) for c in found.get("citations", [])]
    return [_citation(r) for r in rows if r is not None]


def ask(question: str, lang: str = "hi") -> dict:
    lang = lang if lang in NOT_COVERED else "en"
    question = question[:MAX_QUESTION_CHARS]
    if load_corpus() is None:
        return {"answer": CORPUS_MISSING[lang], "citations": [], "covered": False,
                "reason": UNAVAILABLE}
    not_covered = {"answer": NOT_COVERED[lang], "citations": [], "covered": False}
    if conflicted(question):
        return {"answer": PADDY_INUNDATION[lang],
                "citations": _unverified_citations("paddy_localized_inundation_kharif_2026"),
                "covered": True, "llm_used": False}
    if not question.strip() or not _DOMAIN.search(question):
        return not_covered
    rule_hit = _key_rule_hit(question)
    rule_clauses = []
    if rule_hit:
        for cite in rule_hit[1].get("citations", []):
            row = _clause_by_id(str(cite.get("clause_id")))
            if row is not None and row not in rule_clauses:
                rule_clauses.append(row)
    # A word the corpus has never used (mars, say) means it probably does not speak to this.
    vocabulary = load_corpus().vocabulary
    terms = [t for group in _question_terms(question) for t in group]
    needed = STRICT_COVERAGE if any(t not in vocabulary for t in terms) else MIN_COVERAGE
    hits = rule_clauses[:3] + [
        h for h in retrieve(question)
        if _coverage(question, f"{h.get('section_title', '')} {h['text']}") >= needed
        and h not in rule_clauses
    ]
    if not hits:
        return not_covered

    generated = llm.bounded(
        30, llm.answer_from_clauses, question,
        [{"clause_id": str(h["clause_id"]), "text": h["text"][:MAX_CLAUSE_CHARS]} for h in hits[:5]],
        lang,
    ) if llm.available() else None
    if generated is not None and generated.cited_clause_ids:
        by_id = {str(h["clause_id"]): h for h in hits}
        cited = [by_id[c] for c in generated.cited_clause_ids if c in by_id]
        allowed = set()
        for row in cited:
            allowed |= {float(t.replace(",", "")) for t in re.findall(r"\d+(?:\.\d+)?", row["text"])}
        if cited and validate.validate_text(generated.answer, allowed).ok:
            return {"answer": generated.answer, "citations": [_citation(c) for c in cited],
                    "covered": True, "llm_used": True}
    if rule_hit and rule_clauses:
        note = f" {TECHNOLOGY_NOTE[lang]}" if rule_hit[0] == "technology_and_evidence" else ""
        return {
            "answer": f"{SUMMARY_INTRO[lang]} {rule_hit[1]['statement']}{note}",
            "citations": [_citation(c) for c in rule_clauses[:3]],
            "covered": True,
            "llm_used": False,
        }
    best = hits[0]
    return {
        "answer": f"{QUOTE_INTRO[lang]} {best['text'][:MAX_CLAUSE_CHARS]}",
        "citations": [_citation(best)],
        "covered": True,
        "llm_used": False,
    }


def ensure_cited(path, clauses: list[PolicyClause], deadlines=()) -> None:
    """Every clause id on the route has its text in `clauses`. An id with no text in the corpus is
    dropped from the route rather than shown as a citation nobody can read."""
    have = {c.clause_id for c in clauses}
    keep = []
    for clause_id in dict.fromkeys([*path.clause_ids, *(d.basis for d in deadlines)]):
        row = _clause_by_id(clause_id)
        if row is None:
            log.warning("cited clause %s is not in the corpus", clause_id)
            continue
        keep.append(clause_id)
        if clause_id not in have:
            clauses.append(to_clause(row, "Cited on your claim route"))
            have.add(clause_id)
    path.clause_ids = keep


def clauses_for_rules(rule_names: list[tuple[str, str]]) -> list[PolicyClause]:
    """Clauses cited by named key rules, each with the reason it applies to this case."""
    rules = (load_key_rules() or {}).get("rules") or {}
    seen, out = set(), []
    for name, because in rule_names:
        for cite in (rules.get(name) or {}).get("citations", [])[:2]:
            cid = str(cite.get("clause_id"))
            if cid in seen:
                continue
            row = _clause_by_id(cid)
            if row is None:
                continue
            seen.add(cid)
            out.append(to_clause(row, because))
    return out
