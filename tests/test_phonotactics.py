"""P = the phonotactically possible: real Pāli in, Sanskrit out."""

import random

import pytest

from abugida.phonotactics import is_possible, pseudoword

#: 20 real words (attested in DPD) that between them cover the whole
#: alphabet — a convenient positive fixture.
WORDS = (
    "aṭṭha", "upekkhā", "kamma", "citta", "chanda", "jaḷa", "jhāna",
    "ṭhāna", "thūpa", "nibbāna", "paññā", "paṇḍita", "phala", "buddha",
    "bhava", "yoga", "vuḍḍhi", "saṅgha", "saṃsāra", "sīha",
)


# --- Positives -------------------------------------------------------------


def test_real_words_are_possible():
    for word in WORDS:
        assert is_possible(word), word


@pytest.mark.parametrize(
    "word",
    [
        "indriya",  # triple cluster ndr (nasal+homorganic stop + liquid)
        "lakkhyā",  # triple kkhy (aspirated geminate + y)
        "saṅkhāra",  # ṅ + the series aspirate
        "pañha",  # sonorant + h
        "taṇhā",
        "mayhaṃ",
        "jivhā",
        "brahmā",  # h + m
        "tasmā",  # s + nasal
        "tatra",  # C + r
        "katvā",  # C + v
        "sakya",  # C + y
        "plavati",  # C + l (marginal but real)
        "dve",  # initial cluster C+v
        "brāhmaṇa",  # initial br + internal hm
        "bhandati",  # invented but legal: P is wider than the lexicon
    ],
)
def test_possible(word):
    assert is_possible(word)


# --- Negatives -------------------------------------------------------------


@pytest.mark.parametrize(
    "word,reason",
    [
        ("dharma", "rm: the cluster Pāli assimilated (dhamma)"),
        ("karma", "rm (kamma)"),
        ("buddh", "final consonant"),
        ("satthar", "final consonant (a citation lemma, not a word)"),
        ("ṅḷkkā", "initial ṅ and an impossible cluster"),
        ("kṛṣṇa", "does not even tokenise: False, not an error"),
        ("ahaṇkāra", "ṇk is not homorganic (it would be ṅk)"),
        ("stana", "st opens no word (Pāli thana)"),
        ("bhakta", "kt: the cluster Pāli assimilated (bhatta)"),
        ("mṃa", "ṃ with no preceding vowel"),
        ("kkamma", "initial geminate"),
        ("", "empty"),
        ("kh", "no vowel"),
    ],
)
def test_impossible(word, reason):
    assert not is_possible(word), reason


@pytest.mark.parametrize("word", ["nhāru", "nhāyati", "nhusā", "nhātaka", "mhita"])
def test_aspirated_nasals_open_words(word):
    """nh and mh are unitary aspirated nasals and occur word-initially
    (Oberlies, Pali §15.1)."""
    assert is_possible(word)


@pytest.mark.parametrize("word", ["ñhāna", "ṇhāta", "lhāyati", "ḷhāna",
                                  "yhāna", "vhāyati"])
def test_only_nh_and_mh_open_words(word):
    """The other sonorant+h clusters stay word-internal: no initial example
    is attested, so admitting nh/mh must not admit them."""
    assert not is_possible(word)
    # …while the same clusters remain legal inside a word
    assert is_possible("a" + word)


@pytest.mark.parametrize("word", ["bhastā", "bhasta", "ghasta", "vaṅkaghasta",
                                  "viddhasta", "anuddhasta"])
def test_st_is_possible_word_internally(word):
    """st is one of the sibilant clusters Pāli sometimes leaves unassimilated
    (Oberlies, Pali §16 rem. (a): ghasta-, bhasta- 'bag', Th 1151). Until
    2026-10-13 bhastā was pinned here as impossible, as a "marginal
    Sanskritism"; the grammar lists it as Pāli."""
    assert is_possible(word)


@pytest.mark.parametrize("word", ["stana", "stūpa", "sthāna"])
def test_st_opens_no_word(word):
    """Admitting st inside a word must not admit it as an onset: Pāli has
    thana, thūpa, ṭhāna."""
    assert not is_possible(word)


def test_unassimilated_niggahita_is_legal():
    """ṃ + stop is valid manuscript orthography (saṃgha ~ saṅgha coexist,
    SPEC §9): the phonotactics accept both spellings."""
    assert is_possible("saṃtāna") and is_possible("santāna")
    assert is_possible("saṃgha") and is_possible("saṅgha")


# --- The three structural families, one by one -----------------------------


def test_aspirated_geminate_is_composition():
    """kkh, ddh, ṭṭh…: the second is the first ⊗ 0+. The whole family."""
    for pair in ("kkha", "ggha", "ccha", "jjha", "ṭṭha", "ḍḍha",
                 "ttha", "ddha", "ppha", "bbha"):
        assert is_possible("a" + pair)
    # and the aspirate cannot come first
    assert not is_possible("akhka")


def test_homorganic_nasal_is_the_meet():
    """The same rule as assimilate: non-empty meet of places."""
    assert is_possible("aṅga") and is_possible("añja")
    assert is_possible("aṇḍa") and is_possible("anta") and is_possible("amba")
    # crossed: empty meet
    assert not is_possible("aṅḍa")
    assert not is_possible("añta")
    assert not is_possible("amka")


def test_lone_n_between_vowels_is_not_nga():
    assert is_possible("anena")
    assert not is_possible("aṅena")  # ṅ lives only in a homorganic cluster


# --- The pseudo-Pāli generator ---------------------------------------------


def test_pseudoword_is_legal_and_deterministic():
    rng = random.Random(7)
    words = [pseudoword(rng) for _ in range(20)]
    assert all(is_possible(w) for w in words)
    rng2 = random.Random(7)
    assert [pseudoword(rng2) for _ in range(20)] == words
