"""Side-by-side battery: does the comparator behave as a Pāli philologist
would expect, and does Levenshtein?

Each case is a **discrimination triple** (base, nearer, farther) where
linguistics fixes the answer: `nearer` differs from `base` by a smaller
phonological step than `farther` does. A measure passes a case when it ranks
them in that order; a tie counts as a failure, since a tie forces the caller
to guess.

Some `farther` forms are invented controlled minimal pairs. That is
deliberate: the battery measures the metric, not the lexicon, and it must run
without any dictionary.

Run `python tests/test_battery.py` to print the side-by-side report.
"""

import itertools

import pytest

from abugida import assimilate_word, distance, levenshtein

# family, base, nearer, farther, rationale
CASES = [
    # --- vowel length: the commonest transmission variant of all ----------
    ("length", "pala", "pāla", "paya",
     "lengthening vs a different consonant"),
    ("length", "nibbāna", "nibbana", "nibbāta",
     "shortening vs a different consonant"),
    ("length", "buddha", "buddhā", "buddhi",
     "final lengthening vs a different final vowel"),
    ("length", "bhikkhu", "bhikkhū", "bhikkhi",
     "final lengthening vs a different final vowel"),
    ("length", "rūpa", "rupa", "rūba",
     "shortening vs voicing the stop"),
    # --- aspiration -------------------------------------------------------
    ("aspiration", "kamma", "khamma", "yamma",
     "aspirating the onset vs an unrelated onset"),
    ("aspiration", "khandha", "khandhā", "khantha",
     "lengthening vs devoicing inside the cluster"),
    ("aspiration", "tathā", "tathā", "tadhā",
     "identity vs voicing the medial stop"),
    # --- voicing ----------------------------------------------------------
    ("voicing", "kamma", "gamma", "yamma",
     "voicing the onset vs an unrelated onset"),
    ("voicing", "loka", "loga", "lopa",
     "voicing vs a change of place"),
    ("voicing", "magga", "makka", "mabba",
     "devoicing the geminate vs moving its place"),
    ("voicing", "saccā", "sacca", "sajjā",
     "shortening vs voicing the geminate"),
    # --- place: the retroflex/dental confusion of the manuscripts ---------
    ("place", "taṇhā", "tanhā", "tavhā",
     "retroflex → dental nasal vs nasal → v"),
    ("place", "paṭi", "pati", "payi",
     "retroflex → dental stop vs stop → glide"),
    ("place", "ñāṇa", "ñāna", "ñāya",
     "retroflex → dental nasal vs nasal → glide"),
    # --- nasals -----------------------------------------------------------
    ("nasal", "citta", "cinta", "cimta",
     "homorganic nasal insertion vs a non-homorganic one"),
    ("nasal", "saṃsāra", "saṅsāra", "salsāra",
     "niggahīta → series nasal vs nasal → l"),
    ("nasal", "puñña", "puñja", "pukka",
     "within the palatal cluster vs a full shift of place"),
    # --- clusters and gemination -----------------------------------------
    ("cluster", "attha", "atha", "akkha",
     "cluster simplification vs place change plus gemination"),
    ("cluster", "dukkha", "dukkhā", "dubbha",
     "lengthening vs rebuilding the cluster"),
    ("cluster", "sutta", "suttā", "sukka",
     "lengthening vs a different geminate"),
    # --- Sanskrit reflexes ------------------------------------------------
    ("tadbhava", "dhamma", "dhammā", "dharma",
     "an inflected form vs the unassimilated Sanskrit cluster"),
    ("tadbhava", "mitta", "mittā", "mitra",
     "an inflected form vs the Sanskrit cluster"),
    # --- morphology -------------------------------------------------------
    ("morphology", "gacchati", "gacchanti", "gacchāmi",
     "one nasal insertion vs two changes"),
    ("morphology", "phala", "phalā", "bhala",
     "inflection vs voicing the onset"),
    ("morphology", "vedanā", "vedanā", "vedatā",
     "identity vs one change"),
    ("morphology", "kāya", "kāyā", "kāla",
     "inflection vs a different consonant"),
    ("morphology", "bhava", "bhāva", "bhaya",
     "lengthening vs a different consonant"),
    ("morphology", "jhāna", "jhānā", "jhāta",
     "inflection vs a different consonant"),
]

#: The one case the comparator is documented to get wrong (SPEC §14): the
#: glut inflates ṃ's norm, so the real orthographic variant saṃgha lands
#: further away than the ill-formed saṇgha. Kept in the battery rather than
#: quietly dropped — with its remedy tested below.
KNOWN_LIMITATION = (
    "nasal", "saṅgha", "saṃgha", "saṇgha",
    "attested unassimilated spelling vs a wrong-place nasal",
)


def _wins(measure, base, nearer, farther):
    """A measure passes only on a strict ordering: a tie is a failure."""
    return measure(base, nearer) < measure(base, farther) - 1e-9


# --- Case by case ----------------------------------------------------------


@pytest.mark.parametrize(
    "family,base,nearer,farther,why",
    CASES,
    ids=[f"{c[0]}:{c[1]}" for c in CASES],
)
def test_phonological_distance_ranks_correctly(family, base, nearer, farther, why):
    assert _wins(distance, base, nearer, farther), why


def test_phonological_score():
    """The whole battery, including the known limitation in the denominator."""
    everything = CASES + [KNOWN_LIMITATION]
    hits = sum(_wins(distance, b, n, f) for _, b, n, f, _ in everything)
    assert hits == len(everything)  # the former limitation included (below)


def test_levenshtein_score_is_far_behind():
    """The baseline, measured on the same battery.

    This is not a test of Levenshtein but a regression lock on the margin:
    should the phonological cost ever degrade towards uniform edits, this
    fails alongside the score above.
    """
    everything = CASES + [KNOWN_LIMITATION]
    lev_hits = sum(_wins(levenshtein, b, n, f) for _, b, n, f, _ in everything)
    phon_hits = sum(_wins(distance, b, n, f) for _, b, n, f, _ in everything)
    assert lev_hits < phon_hits / 2


# --- Resolution: the mechanism behind the margin ---------------------------

WORDS = (
    "aṭṭha", "upekkhā", "kamma", "citta", "chanda", "jaḷa", "jhāna",
    "ṭhāna", "thūpa", "nibbāna", "paññā", "paṇḍita", "phala", "buddha",
    "bhava", "yoga", "vuḍḍhi", "saṅgha", "saṃsāra", "sīha",
)


def test_phonological_distance_resolves_far_more_finely():
    """Over the same 190 pairs, Levenshtein produces a handful of distinct
    values and the phonological distance produces almost as many as there are
    pairs. Ties are what force a caller to guess."""
    pairs = list(itertools.combinations(WORDS, 2))
    phon_values = {round(distance(a, b), 6) for a, b in pairs}
    lev_values = {levenshtein(a, b) for a, b in pairs}
    assert len(pairs) == 190
    assert len(lev_values) <= 10
    assert len(phon_values) > 0.8 * len(pairs)


# --- The known limitation, stated and remedied -----------------------------


def test_the_former_limitation_is_resolved():
    """saṅgha~saṃgha (a real spelling variant) used to land further than
    saṅgha~saṇgha (ill-formed), because the glut gives ṃ all five places.
    With heavy units ṅgh and ṃgh are both one nasal+stop unit and differ only
    in the nasal half, while ṇgh is no unit (ṇ and gh share no place), so the
    variant now wins. Pinned so the day it changes back we notice."""
    _, base, nearer, farther, _ = KNOWN_LIMITATION
    assert _wins(distance, base, nearer, farther)
    assert distance(base, nearer) < distance(base, farther)


def test_the_documented_remedy_fixes_it():
    """Resolve sandhi first, compare second — the pipeline of
    docs/comparator.md. It turns the failure into the strongest possible
    hit: the two spellings become the same word."""
    _, base, nearer, farther, _ = KNOWN_LIMITATION
    resolved = lambda a, b: distance(assimilate_word(a), assimilate_word(b))
    assert resolved(base, nearer) == 0.0
    assert resolved(base, nearer) < resolved(base, farther)


# --- Sanity floor: unrelated words must stay far ---------------------------


def test_unrelated_words_are_not_close():
    """A discriminating metric must also refuse false positives."""
    for a, b in itertools.combinations(("yoga", "sīha", "phala", "citta"), 2):
        assert distance(a, b) >= 1.0


def test_distance_stays_under_levenshtein_on_the_battery_words():
    """True of these words; not a law (a heavy unit against two letters can
    exceed it: see test_distance.py)."""
    for a, b in itertools.combinations(WORDS, 2):
        assert distance(a, b) <= levenshtein(a, b) + 1e-9


# --- Side-by-side report ---------------------------------------------------


def _report():
    everything = CASES + [KNOWN_LIMITATION]
    print(f"\n{'family':11} {'base':10} {'nearer':10} {'farther':10} "
          f"{'d(near)':>8} {'d(far)':>8} {'phon':>5}  {'L':>5} {'lev':>5}")
    print("-" * 88)
    phon_hits = lev_hits = 0
    for family, base, nearer, farther, _ in everything:
        dn, df = distance(base, nearer), distance(base, farther)
        ln, lf = levenshtein(base, nearer), levenshtein(base, farther)
        p_ok = dn < df - 1e-9
        l_ok = ln < lf
        phon_hits += p_ok
        lev_hits += l_ok
        print(f"{family:11} {base:10} {nearer:10} {farther:10} "
              f"{dn:8.3f} {df:8.3f} {'OK' if p_ok else 'MISS':>5}  "
              f"{ln}/{lf:<3} {'OK' if l_ok else 'tie':>5}")
    n = len(everything)
    print("-" * 88)
    print(f"phonological {phon_hits}/{n} ({phon_hits / n:.1%})    "
          f"levenshtein {lev_hits}/{n} ({lev_hits / n:.1%})")

    pairs = list(itertools.combinations(WORDS, 2))
    phon_values = {round(distance(a, b), 6) for a, b in pairs}
    lev_values = {levenshtein(a, b) for a, b in pairs}
    print(f"\nresolution over {len(pairs)} pairs: "
          f"phonological {len(phon_values)} distinct values, "
          f"levenshtein {len(lev_values)}")


if __name__ == "__main__":
    _report()
