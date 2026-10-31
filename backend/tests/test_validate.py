"""The number and claim validator, with Devanagari and Telugu digits and rounding."""
from app.agent import validate
from app.agent.explain import allowed_numbers
from tests.conftest import evidence


def check(text, allowed=(0.2345, 18, 200, 72)):
    return validate.validate_text(text, allowed)


def test_exact_number_passes():
    assert check("change of 0.2345 on 18 October").ok


def test_rounding_passes():
    assert check("about 0.23 or 0.2").ok


def test_fraction_as_percent_passes():
    assert check("23% of the field").ok and check("23.45 percent").ok


def test_invented_number_fails():
    result = check("change of 0.91 and 55 mm")
    assert not result.ok and result.bad_tokens == ["0.91", "55"]


def test_devanagari_digits_are_normalized():
    assert check("१८ अक्टूबर को ७२ घंटे").ok
    assert not check("९९ घंटे").ok


def test_telugu_digits_are_normalized():
    assert check("౧౮ అక్టోబర్").ok
    assert not check("౯౯ గంటలు").ok


def test_small_fraction_does_not_license_bare_one():
    assert not validate.validate_text("1 field", {0.7}).ok


def test_thousands_separator():
    assert validate.validate_text("1,200 pixels", {1200}).ok


def test_product_names_are_not_numbers():
    assert check("Sentinel-2 and Sentinel-1, also S2").ok


def test_no_digits_passes():
    assert check("no numbers here").ok


def test_money_and_promises_are_banned():
    for bad in ("you will receive payment", "₹ amount", "2 lakh", "मुआवज़ा मिलेगा", "guaranteed",
                "करोड़ों"):
        assert not validate.validate_text(bad, set()).ok, bad


def test_do_not_say_entries_are_banned():
    for bad in ("late means rejected", "your claim is lost", "the insurer must accept this",
                "go to a CSC", "everyone gets paid", "you no longer need to intimate",
                "the survey is a lottery", "this survey is unfair", "farmers can't contest"):
        assert not validate.validate_text(bad, set()).ok, bad


def test_insurer_names_are_banned():
    for bad in ("Agriculture Insurance Company", "ICICI Lombard", "HDFC ERGO"):
        assert not validate.validate_text(bad, set()).ok, bad


def test_collect_skips_identifiers_and_reads_dates():
    found = validate.collect_numbers({"seed": 12345, "evidence_hash": 9, "x": 1.5, "when": "2026-10-25"})
    assert 12345.0 not in found and 9.0 not in found
    assert {1.5, 2026.0, 10.0, 25.0} <= found


def test_real_evidence_numbers_are_allowed():
    ev = evidence()
    allowed = allowed_numbers(ev)
    assert validate.validate_text("NDVI 0.70 to 0.45, a change of -0.25 on 25 Oct", allowed).ok
    assert not validate.validate_text("NDVI fell by 0.99", allowed).ok
