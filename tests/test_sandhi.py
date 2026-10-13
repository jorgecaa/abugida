"""Word-level sandhi, checked against real lexicon."""

import pytest

from abugida.distance import distance
from abugida.sandhi import assimilate_word, contract_word, sandhi_join


# --- Before a stop: each series' nasal (the lattice meet) ------------------


@pytest.mark.parametrize(
    "raw,assimilated",
    [
        ("saṃgha", "saṅgha"),  # guttural
        ("saṃkappa", "saṅkappa"),
        ("saṃjāta", "sañjāta"),  # palatal
        ("saṃcicca", "sañcicca"),
        ("saṃṭhāna", "saṇṭhāna"),  # cerebral
        ("saṃtāna", "santāna"),  # dental
        ("saṃdiṭṭhi", "sandiṭṭhi"),
        ("saṃbodhi", "sambodhi"),  # labial
        ("saṃpanna", "sampanna"),
    ],
)
def test_assimilation_before_a_stop(raw, assimilated):
    assert assimilate_word(raw) == assimilated


def test_several_niggahitas_in_one_word():
    assert assimilate_word("saṃgaṃkāra") == "saṅgaṅkāra"


# --- ṃ + y → ññ ------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,assimilated",
    [
        ("saṃyutta", "saññutta"),
        ("saṃyojana", "saññojana"),
        ("saṃyoga", "saññoga"),
    ],
)
def test_nasalisation_of_y(raw, assimilated):
    assert assimilate_word(raw) == assimilated


# --- Where the glut stays unresolved ---------------------------------------


@pytest.mark.parametrize(
    "word",
    [
        "saṃsāra",  # before s
        "saṃharati",  # before h
        "saṃvara",  # before v
        "saṃrāga",  # before r
        "evaṃ",  # word-final
        "taṃahaṃ",  # before a vowel (an already-joined junction)
    ],
)
def test_no_resolution(word):
    """With no stop or y to confer a place, ṃ stays: residual nasalisation —
    exactly the glut/gap divergence of SPEC §2, on the glut side."""
    assert assimilate_word(word) == word


# --- Input normalisation ---------------------------------------------------


def test_accepts_orthographic_variants():
    assert assimilate_word("Saṁgha") == "saṅgha"


def test_is_idempotent():
    for word in ("saṃgha", "saṃyutta", "saṃsāra", "evaṃ"):
        once = assimilate_word(word)
        assert assimilate_word(once) == once


# --- Vowel sandhi: the lattice join ----------------------------------------


@pytest.mark.parametrize(
    "left,right,result",
    [
        ("upa", "ikkhā", "upekkhā"),  # a+i → e: {G}∪{P}, attested in DPD
        ("mahā", "udadhi", "mahodadhi"),  # ā+u → o; DPD: mahā + udadhi
        ("ca", "eva", "ceva"),  # a+e → e: the union already is the compound
        ("tatra", "ayaṃ", "tatrāyaṃ"),  # a+a → ā: same places, long
        ("bhava", "abhava", "bhavābhava"),
        ("yathā", "iva", "yatheva"),  # ā+i → e
    ],
)
def test_vowel_join(left, right, result):
    assert sandhi_join(left, right) == result


@pytest.mark.parametrize(
    "left,right",
    [
        ("aggi", "agāraṃ"),  # i+a: glide formation, not the join — untouched
        ("cakkhu", "indriya"),  # u+i: not the guṇa pattern either
        ("phala", "gata"),  # consonant boundary: nothing to resolve
    ],
)
def test_outside_the_guna_pattern_untouched(left, right):
    assert sandhi_join(left, right) == left + right


def test_same_vowel_long_beats_short():
    """ī+i, ū+u…: same places → the long one, wherever it comes from."""
    assert sandhi_join("gāmī", "iva") == "gāmīva"
    assert sandhi_join("bahū", "upamā") == "bahūpamā"


# --- contraction: the lattice join applied word-internally ----------------


def test_contraction_is_the_place_lattice_join():
    """aya → e is {guttural} ∪ {palatal}; o's places sit inside
    {guttural} ∪ {labial}. The same join `sandhi_join` does at a boundary."""
    from abugida.phonology import phoneme
    assert phoneme("a").places | phoneme("y").places == phoneme("e").places
    assert phoneme("o").places <= phoneme("a").places | phoneme("v").places


@pytest.mark.parametrize(
    "word,expected",
    [
        ("abhibhavati", "abhibhoti"),
        ("anavakāsa", "anokāsa"),
        ("anavaññāta", "anoññāta"),
        ("palayati", "paleti"),
        ("sayati", "seti"),
        ("bhavati", "bhoti"),
        ("kamma", "kamma"),          # nothing to contract
        ("iyaka", "iyaka"),          # the i-series is deliberately out
        ("āyati", "āyati"),          # so are the long-vowel variants
    ],
)
def test_contract_word(word, expected):
    assert contract_word(word) == expected


def test_contract_word_normalises_and_is_idempotent():
    assert contract_word("ABHIBHAVATI") == "abhibhoti"
    once = contract_word("anavakāsa")
    assert contract_word(once) == once


def test_contraction_brings_real_variants_together():
    """The pipeline shape the docs prescribe: phonology first, metric
    second. These pairs sit above 1.5 without it."""
    for a, b in [("abhibhavati", "abhibhoti"), ("anavakāsa", "anokāsa"),
                 ("palayati", "paleti")]:
        assert distance(a, b) > 1.4
        assert distance(contract_word(a), contract_word(b)) == 0.0


def test_contraction_leaves_the_metric_untouched():
    """It is a normalisation, not a distance operation — the guarantee the
    metric carries is unaffected because `distance` never sees it."""
    assert distance("abhibhavati", "kave") <= (
        distance("abhibhavati", "bhavati") + distance("bhavati", "kave")
        + 1e-9)


def test_ayi_contraction_reaches_the_causative_absolutive():
    """`ayi` → `e` is the same lattice join as `aya` → `e`, before a front
    vowel, and the causative absolutive is what makes it productive. Found by
    a dpd-db integration benchmark: these sat at d=1.65, which no threshold
    reaches. Measured at +0.86 recall points for ~0 volume (SPEC §9.1)."""
    from abugida import contract_word, distance
    from abugida.sandhi import CONTRACTIONS

    assert ("ayi", "e") in CONTRACTIONS
    for long, short in [("bhāvayitvā", "bhāvetvā"),
                        ("pakappayitvā", "pakappetvā"),
                        ("visosayitvā", "visosetvā")]:
        assert contract_word(long) == short
        assert distance(contract_word(long), contract_word(short)) == 0.0
