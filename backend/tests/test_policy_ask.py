"""Natural farmer questions must reach the right verified rule, and off-topic ones must not."""
import pytest

from app.tools import policy


@pytest.mark.parametrize("question, rule", [
    ("How long do I have to report hail damage?", "intimation_deadline"),
    ("When should I report my crop loss?", "intimation_deadline"),
    ("What is the deadline for intimation of localized calamity?", "intimation_deadline"),
    ("ओले गिरने के बाद कितने घंटे में सूचना देनी है?", "intimation_deadline"),
    ("నష్టం సమాచారం ఎన్ని గంటల్లో ఇవ్వాలి?", "intimation_deadline"),
    ("What if I report late?", "late_intimation"),
    ("देर से सूचना दी तो क्या होगा?", "late_intimation"),
    ("Is post-harvest loss covered?", "post_harvest_14_day"),
    ("How do I report my crop loss?", "channels"),
    ("फसल नुकसान की सूचना कहाँ दूँ?", "channels"),
    ("What details do I need to report a loss?", "intimation_contents"),
    ("क्या ओले से नुकसान कवर है?", "perils"),
    ("Is cyclone damage covered?", "perils"),
    ("How can I complain about my claim?", "grievance"),
])
def test_natural_questions_reach_the_right_rule(question, rule):
    assert policy._key_rule_hit(question)[0] == rule
    answer = policy.ask(question, "en")
    assert answer["covered"] is True
    assert answer["citations"]


@pytest.mark.parametrize("question", [
    "Who won the cricket world cup?", "What is the capital of France?", "How long is the Ganga?",
    "",
])
def test_off_topic_questions_are_refused(question):
    answer = policy.ask(question, "en")
    assert answer["covered"] is False
    assert answer["citations"] == []


def test_rule_answers_do_not_claim_to_be_quotes():
    answer = policy.ask("How long do I have to report hail damage?", "en")["answer"]
    assert answer.startswith(policy.SUMMARY_INTRO["en"])
    assert not answer.startswith(policy.QUOTE_INTRO["en"])


def test_paddy_inundation_is_never_called_covered():
    answer = policy.ask("Is paddy flood damage covered?", "en")["answer"]
    assert "cannot say it is covered" in answer
