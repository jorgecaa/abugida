"""The morphological generator: are the candidates formable, and correct?

Two kinds of check. The structural ones state the contract (every form
carries a root, a base and an ending; every form is phonotactically
possible; generation is deterministic). The philological ones pin down
junction against forms the grammars give — those are the cases where a
plausible-looking rule quietly produces the wrong word.
"""

import random

import pytest

from abugida.iast import tokenize
from abugida.morphology import (
    KITA,
    ROOTS,
    Formation,
    analyse,
    consonantal,
    formations,
    is_formable,
    join,
    nominal_bases,
    noun_forms,
    pseudoform,
    pseudoword_morphological,
    verb_forms,
)
from abugida.phonotactics import is_possible, pseudoword


def test_every_form_is_phonotactically_possible():
    """The phonotactics are the floor: formability is added on top of
    `is_possible`, never traded against it."""
    for f in formations():
        assert is_possible(f.word), f


def test_every_form_carries_its_analysis():
    """Root + base + ending, the whole point: no candidate is unexplained."""
    for f in formations():
        assert f.root and f.base and f.ending and f.category
        assert f.kind in ("verb", "noun")
        assert f.word.startswith(f.base[:2])


def test_generation_is_deterministic():
    assert [f.word for f in formations()] == [f.word for f in formations()]


def test_roots_are_well_formed():
    for r in ROOTS:
        assert is_possible(r.stem + "ti") or is_possible(r.stem)
        assert r.gana and r.gloss
    assert len({r.root for r in ROOTS}) == len(ROOTS)


# --- junction: the cases where a wrong rule shows up ----------------------


@pytest.mark.parametrize(
    "base,ending,expected",
    [
        # thematic -a: plain concatenation
        ("paca", "ti", "pacati"),
        ("paca", "nti", "pacanti"),
        # lengthening before the first-person endings and imperative -hi
        ("paca", "mi", "pacāmi"),
        ("paca", "ma", "pacāma"),
        ("paca", "mhe", "pacāmhe"),
        ("paca", "hi", "pacāhi"),
        # hiatus: the thematic vowel goes
        ("paca", "antu", "pacantu"),
        ("paca", "e", "pace"),
        ("pacana", "ena", "pacanena"),
        ("pacana", "o", "pacano"),
        ("pacana", "ānaṃ", "pacanānaṃ"),
        # guṇa bases keep their vowel and the ending yields
        ("karo", "antu", "karontu"),
        ("core", "antu", "corentu"),
        # ... unless that would erase the ending completely
        ("karo", "e", "kare"),
        # long vowel shortens before a cluster
        ("jānā", "nti", "jānanti"),
        ("suṇā", "nti", "suṇanti"),
        # but not before a single consonant
        ("jānā", "ti", "jānāti"),
    ],
)
def test_junction(base, ending, expected):
    assert join(base, ending) == expected


def test_consonantal_strips_the_final_vowel():
    assert consonantal("paca") == "pac"
    assert consonantal("karo") == "kar"
    assert consonantal("jānā") == "jān"
    assert consonantal("mañña") == "maññ"


def test_retroflexion_after_r():
    """nati: intervocalic n → ṇ after r, blocked by an intervening coronal."""
    bases = {r.root: [b for b, _, _ in nominal_bases(r)] for r in ROOTS}
    assert "karaṇa" in bases["kar"]
    assert "caraṇa" in bases["car"]
    assert "saraṇa" in bases["sar"]
    assert "maraṇa" in bases["mar"]
    # blocked: the n and dh of the base intervene
    assert "rundhana" in bases["rudh"]
    # no r at all, nothing to trigger it
    assert "pacana" in bases["pac"]
    # not intervocalic: the participle keeps its n before the cluster
    assert "karanta" in bases["kar"]


@pytest.mark.parametrize(
    "root,expected",
    [
        ("pac", {"pacati", "pacanti", "pacāmi", "pacissati", "paceyya",
                 "pacāhi", "pacantu"}),
        ("bhū", {"bhavati", "bhavanti", "bhavāmi", "bhavissati", "bhaveyya"}),
        ("gam", {"gacchati", "gacchāmi", "gacchantu"}),
        ("kar", {"karoti", "karonti", "karissati", "kareyya", "karontu"}),
        ("su", {"suṇāti", "suṇanti", "suṇāmi"}),
        ("ñā", {"jānāti", "jānanti", "jānāmi"}),
        ("cur", {"coreti", "corenti", "corentu"}),
        ("budh", {"bujjhati", "bujjhanti"}),
        ("muc", {"muñcati", "muñcanti"}),
    ],
)
def test_attested_verb_forms_are_generated(root, expected):
    """Forms the grammars actually give must come out of the generator."""
    r = next(x for x in ROOTS if x.root == root)
    produced = {f.word for f in verb_forms(r)}
    assert expected <= produced, expected - produced


@pytest.mark.parametrize(
    "root,expected",
    [
        ("pac", {"pacako", "pacanaṃ", "pacitabbo"}),
        ("kar", {"karaṇaṃ", "karaṇena", "karitabbo"}),
        ("car", {"caraṇaṃ", "caraṇesu"}),
    ],
)
def test_attested_noun_forms_are_generated(root, expected):
    r = next(x for x in ROOTS if x.root == root)
    produced = {f.word for f in noun_forms(r)}
    assert expected <= produced, expected - produced


def test_every_root_yields_both_kinds():
    for r in ROOTS:
        assert list(verb_forms(r)), r
        assert list(noun_forms(r)), r
        assert len(list(nominal_bases(r))) == len(KITA), r


# --- the sampling surface -------------------------------------------------


def test_pseudoform_is_reproducible_and_analysed():
    a = pseudoform(random.Random(7))
    b = pseudoform(random.Random(7))
    assert a == b
    assert isinstance(a, Formation)
    assert is_possible(a.word)


def test_pseudoform_kind_filter():
    rng = random.Random(0)
    assert all(pseudoform(rng, "verb").kind == "verb" for _ in range(50))
    assert all(pseudoform(rng, "noun").kind == "noun" for _ in range(50))
    with pytest.raises(ValueError):
        pseudoform(rng, "adjective")


# --- the criterion applied to strings the generator did not build ---------


def test_everything_generated_passes_its_own_criterion():
    for f in formations():
        assert is_formable(f.word), f


def test_analyse_finds_the_ending():
    assert ("paca", "ti") in analyse("pacati")
    assert ("pacan", "assa") in analyse("pacanassa")
    assert analyse("") == []


def test_formability_is_stricter_than_possibility():
    """The two criteria are not the same question: a legal syllable sequence
    need not be a formable word."""
    assert is_possible("kaṭubha") and not is_formable("kaṭubha")
    assert is_formable("pacati")


def test_the_criterion_prunes_the_phonotactic_generator():
    """How much the second criterion removes, at two strengths.

    The necessary criterion (any known ending over a syllabic base) is
    permissive, since the single-grapheme case endings -e, -o and -ā are
    satisfied by any vowel-final word; requiring an ending of two or more
    graphemes is the discriminating version. Both are reported in SPEC
    §13.1; this test pins the order of magnitude so the claim cannot drift.
    """
    rng = random.Random(20260801)
    words = [pseudoword(rng) for _ in range(2000)]
    loose = sum(is_formable(w) for w in words) / len(words)
    strict = sum(
        any(len(tokenize(e)) >= 2 for _, e in analyse(w)) for w in words
    ) / len(words)
    assert 0.30 < loose < 0.45, loose      # ~36% survive: ~64% pruned
    assert 0.05 < strict < 0.15, strict    # ~9% survive: ~91% pruned
    assert strict < loose


def test_junction_never_leaves_the_phonotactics():
    """Measured 0 discards over the whole generable space: the junction
    rules are closed with respect to P, they never need repair."""
    attempted = 0
    for r in ROOTS:
        attempted += 5 * 6  # five verbal tables, six persons each
        for _suffix, _sense, declension in KITA:
            attempted += 8 if declension == "ā" else 13
    assert len(list(formations())) == attempted


def test_pseudoword_morphological_matches_pseudoword_shape():
    """Drop-in for `phonotactics.pseudoword`: rng in, legal string out."""
    rng = random.Random(3)
    for _ in range(100):
        w = pseudoword_morphological(rng)
        assert isinstance(w, str) and is_possible(w)
